#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — scheduled maintenance: age-based cleanup and orphan handling
#########################################################################

"""
Scheduled maintenance: age-based log cleanup (delete or compact, per
database_maxage/database_maxage_action) and orphan item/log handling (data left behind
by items removed from the item tree).

See doc/dev/database/database.md §7 for the delete-vs-compact design, and
img/compacting_pruning_flow.svg for the full call sequence including every requeue and
failure branch.
"""

import datetime
import threading
import time

from .constants import COL_ITEM_NAME, BufferEntry, QUALITY_VALID


class MaintenanceManager:
    """Owns remove_older_than_maxage()/_compact_maxage() (age-based cleanup, scheduled)
    and build_orphanlist()/remove_orphan_items()/reassign_orphaned_id()/cleanup()
    (orphan handling). Takes a back-reference to the Database plugin instance
    (*plugin*) rather than individual parameters - see maxage.py's MaxageResolver for
    the same pattern and database.md §2's "Dependency wiring" note on why.

    Internal cross-calls to other methods that moved here go through the plugin's own
    delegate (e.g. plugin.build_orphanlist()) rather than calling siblings directly
    (self.build_orphanlist()) - the test suite mocks several of these at the plugin
    level, predating this module's existence, and a direct sibling call would silently
    bypass those mocks (found the hard way while extracting timescale.py).
    """

    def __init__(self, plugin):
        self._plugin = plugin

    def build_orphanlist(self, log_activity=False):
        """
        Create a list of database entries which have no corresponding item in the item tree

        Called once at run() and, if that attempt failed (no DB connection
        yet), retried once per _dump() cycle until it succeeds - see
        self._orphanlist_built.

        :return: True if the list was actually (re)built against a live
                 connection, False if the attempt failed (e.g. DB not
                 connected) - an empty self.orphanlist alone doesn't tell
                 the caller which of those happened.
        :rtype: bool
        """
        plugin = self._plugin
        if log_activity:
            plugin.logger.info('build_orphan_list: Started')
        plugin.orphanitemlist = []
        plugin.orphanlist = []
        # cleared up front, not just left at its previous value: a failed
        # rebuild below wipes the list above regardless, so a stale True
        # here would let remove_orphan_items() mistake "rebuild just
        # failed" for "confirmed empty" on this attempt's now-empty list.
        plugin._orphanlist_built = False

        items = [item.property.path for item in plugin._buffer_mgr.items()]
        # transaction() serializes this against self._db_maint's other
        # users - the scheduler-driven maxage/orphan cleanup also runs on
        # this same connection.
        try:
            with plugin._db_maint.transaction() as cur:
                return_list = plugin.readItems(cur=cur)
                if return_list:
                    for item in return_list:
                        if item[COL_ITEM_NAME] not in items:
                            if log_activity:
                                plugin.logger.info(
                                    f'- Found data for item w/o database attribute: {item[COL_ITEM_NAME]}'
                                )
                            plugin.orphanitemlist.append(item)
                            plugin.orphanlist.append(item[COL_ITEM_NAME])
        except Exception as e:
            plugin._log_db_exception(e, 'Database build_orphan_list failed: {}'.format(e), db=plugin._db_maint)
            return False

        plugin._orphanlist_built = True
        plugin._count_orphanlogentries()
        if log_activity:
            plugin.logger.info('build_orphan_list: Finished')

        return True

    def count_orphanlogentries(self):
        """
        count number of log entries for all items in database

        to be called by eval syntax checker
        """
        plugin = self._plugin
        plugin.logger.info('_count_orphanlogentries: # orphan items = {}'.format(len(plugin.orphanlist)))
        plugin._items_total_entries = 0
        for item in plugin.orphanlist:
            item_id = plugin.id(item, create=False)
            if item_id is None:
                plugin.logger.warning(f'_count_orphanlogentries: No valid id found for orphan item {item} - skipping')
                continue
            logcount = plugin.readLogCount(item_id)
            logcount_str = f'{logcount:,}'.replace(',', '.')
            plugin.logger.info(f'Orphan {item} (id={item_id}): {logcount_str} entries')
            plugin._orphan_logcount[item_id] = logcount

        return

    def reassign_orphaned_id(self, orphan_id, to):
        """
        Reassign values from orphaned item ID to given item ID

        :param orphan_id: item id of the orphaned item
        :param to: item id of the target item
        :type orphan_id: int
        :type to: int
        """
        plugin = self._plugin
        log_info = plugin.logger.info  # warning  # info
        log_debug = plugin.logger.debug  # error  # debug
        # transaction() serializes this against self._db_maint's other
        # users. One transaction per UPDATE chunk, not one around the whole
        # loop - the LIMIT batching exists to keep individual transactions
        # bounded, and a partially-reassigned state is safe to resume from
        # (remaining rows still carry orphan_id). The item row is only
        # deleted once every log row has moved.
        try:
            log_info(f'reassigning orphaned data from (old) id {orphan_id} to (new) id {to}')
            with plugin._db_maint.transaction() as cur:
                count = plugin.readLogCount(orphan_id, cur=cur)
            log_debug(f'found {count} entries to reassign, reassigning {plugin.max_reassign_logentries} at once')

            while count > 0:
                log_debug(f'reassigning {min(count, plugin.max_reassign_logentries)} log entries')
                with plugin._db_maint.transaction() as cur:
                    # (item_id, time)-matched, double-wrapped subquery, not
                    # rowid-based - same two reasons as the bulk-delete
                    # statements' fix (remove_older_than_maxage(),
                    # _delete_orphan()): {log} has no primary key so
                    # MySQL/MariaDB exposes no rowid for it, and MariaDB
                    # separately rejects LIMIT directly inside IN(subquery).
                    plugin._execute(
                        plugin._prepare(
                            'UPDATE {log} SET item_id = :newid WHERE item_id = :orphanid AND time IN '
                            '(SELECT time FROM (SELECT time FROM {log} WHERE item_id = :orphanid '
                            'LIMIT :limit) AS upd_batch);'
                        ),
                        {'newid': to, 'orphanid': orphan_id, 'limit': plugin.max_reassign_logentries},
                        cur=cur,
                    )
                count -= plugin.max_reassign_logentries

            with plugin._db_maint.transaction() as cur:
                plugin._execute(
                    plugin._prepare('DELETE FROM {item} WHERE id = :orphanid;'), {'orphanid': orphan_id}, cur=cur
                )
            log_info(f'reassigned orphaned id {orphan_id} to new id {to}')
            log_debug('rebuilding orphan list')
            plugin.build_orphanlist()
        except Exception as e:
            plugin._log_db_exception(e, f'error on reassigning id {orphan_id} to {to}: {e}', db=plugin._db_maint)
            return e

    def delete_orphan(self, item_path):
        """
        Delete orphan item or logentries it

        :param item_path: path_name of the (orphan) item to work on
        :param limit: Maximum log entries to delete

        :return: True, if item was deleted; False if only logentries were deleted
        """
        plugin = self._plugin
        # This method deliberately has no except of its own - a failure
        # propagates uncaught to remove_orphan_items()'s own try/except,
        # which logs it and requeues the item for the next cycle. Both
        # branches below use transaction() to serialize against
        # self._db_maint's other users while preserving that.
        item_id = plugin.id(item_path, create=False)
        logcount = plugin.readLogCount(item_id)
        if logcount == 0:
            plugin.logger.info(f'_delete_orphan: Item {item_path} has no log entries')
            with plugin._db_maint.transaction() as cur:
                plugin._execute(plugin._prepare('DELETE FROM {item} WHERE id = :id;'), {'id': item_id}, cur=cur)
            plugin.logger.info(f'_delete_orphan: Deleted item entry for {item_path}')
            return True

        with plugin._db_maint.transaction() as cur:
            # Not a bare DELETE...LIMIT (invalid SQLite syntax without a
            # non-default compile flag) or a rowid-subquery ({log} has no
            # primary key, and MySQL/MariaDB - unlike SQLite - has no
            # queryable row id for a table without one). Matches on
            # (item_id, time) instead, via the UNIQUE KEY
            # {log}_{item}_id_time already on this table (see _setup).
            # Double-wrapped, not single-wrap: MariaDB separately rejects
            # LIMIT directly inside an IN(subquery).
            plugin._execute(
                plugin._prepare(
                    'DELETE FROM {log} WHERE item_id = :id AND time IN (SELECT time FROM '
                    '(SELECT time FROM {log} WHERE item_id = :id LIMIT :maxrecords) AS del_batch);'
                ),
                {'id': item_id, 'maxrecords': plugin.delete_orphan_chunk_size},
                cur=cur,
            )
        delete_orphan_chunk_size_str = f'{plugin.delete_orphan_chunk_size:,}'.replace(',', '.')
        plugin.logger.info(
            f'_delete_orphan: Deleted (up to) {delete_orphan_chunk_size_str} log entries for Item {item_path}'
        )

        return False

    def remove_orphan_items(self):
        """
        Delete item and logdata of items that have no correspondance in itemtree
        """
        plugin = self._plugin
        if len(plugin.orphanlist) == 0:
            plugin.build_orphanlist()

        if len(plugin.orphanlist) == 0:
            if not plugin._orphanlist_built:
                # build_orphanlist() just failed (e.g. DB not connected) -
                # an empty list here doesn't mean "confirmed no orphans".
                # Leave self.remove_orphan set so the next
                # remove_older_than_maxage() cycle retries this instead of
                # silently disabling cleanup over a connectivity hiccup.
                plugin.logger.warning('remove_orphan_items: could not check for orphans (DB not connected), will retry')
                return
            plugin.remove_orphan = False
            plugin.logger.info('remove_orphan_items: No orphans found, cleanup finished')
            return

        item = plugin.orphanlist.pop(0)
        try:
            deleted = plugin._delete_orphan(item)
        except Exception as e:
            # e.g. the maintenance connection (_db_maint) went stale independently
            # of the main connection (see smarthomeNG/plugins#1004) - keep the item
            # queued and retry on the next cycle instead of crashing the scheduler task.
            plugin._log_db_exception(
                e,
                f'remove_orphan_items: Deletion of orphan {item} failed, will retry: {e}',
                db=plugin._db_maint,
                fallback=plugin.logger.warning,
            )
            plugin.orphanlist.append(item)
            return

        if not deleted:
            plugin.orphanlist.append(item)

        if len(plugin.orphanlist) == 0:
            plugin.remove_orphan = False
            plugin.logger.info('remove_orphan_items: Database cleanup finished')

        return

    def cleanup(self):
        """
        Cleanup database
        deletes item/log records in the database if the corresponding item does not exist any more

        This is a public function of the plugin

        :return:
        """
        plugin = self._plugin
        plugin.remove_orphan = True
        plugin.cleanup_active = True
        plugin.logger.info('Database cleanup started (removal of entries without defined item)')
        return

    def compact_maxage(self, item, item_id, itempath, time_end, action):
        """
        Compact log entries older than maxage into one aggregate value per
        database_maxage_interval, instead of deleting them (called from
        remove_older_than_maxage() instead of the delete path when *action*
        is not 'delete').

        No persisted resume cursor is kept: the next interval to compact is
        always simply the oldest remaining raw data for this item
        (self._log_store.oldest_time - a cheap MIN(time) index seek).
        Compaction always proceeds oldest-first and only deletes an
        interval's raw rows in the same transaction as writing its
        aggregate, so this is self-healing across restarts/crashes by
        construction - there is no separate state file to get out of sync.

        Bounded by self.max_aggregate_intervals per call (the aggregate-mode
        analogue of max_delete_logentries' row-count bound - one interval's
        aggregate query can still cover an arbitrary number of raw rows for
        a hot item, so the bound here is on intervals, not rows).

        Changing an item's database_maxage_interval after some data is
        already compacted is safe for avg/min/max/sum/integrate/duty_cycle -
        an old aggregate row swept into a differently-sized new interval
        still combines correctly (the schema's uniform (time,duration,value)
        shape makes AVG(x)/AVG(y) reduce to SUM(x)/SUM(y) regardless of row
        count, and MIN/MAX/SUM are trivially associative). It is NOT safe
        for countall: an old aggregate row representing N original raw rows
        counts as 1 row, silently undercounting. Accepted as-is - this only
        happens on a deliberate config change, not spontaneously, and is not
        worth a schema change to detect for one action's edge case.

        :param item: the item being compacted
        :param item_id: database id of item
        :param itempath: item.property.path, for logging
        :param time_end: datetime - the maxage cutoff; only intervals
            entirely older than this are touched
        :param action: resolved database_maxage_action (already validated
            via _maxage_action_for - never 'delete' here)
        """
        plugin = self._plugin
        edge_order = plugin._maxage._MAXAGE_EDGE_ACTIONS.get(action)
        expr = None if edge_order else plugin._maxage._MAXAGE_AGGREGATE_EXPR[action]
        interval_ms = plugin._maxage.interval_seconds_for(item) * 1000
        cutoff_ms = plugin._timestamp(time_end)
        item_type = item.type()

        intervals_done = 0
        stalled = False
        connection_failed = False
        while intervals_done < plugin.max_aggregate_intervals:
            try:
                # exclude_duration=interval_ms: skip rows this method already produced itself -
                # without it, oldest_time() can't tell a just-compacted row from raw data (both are
                # plain (time, duration, value) rows), so it re-selects the same already-compacted
                # interval forever and never reaches newer raw data (found live 2026-09-04).
                oldest = plugin._log_store.oldest_time(item_id, exclude_duration=interval_ms)
            except Exception as e:
                # Same self-healing case as the transaction() except-block
                # below - a connection error reading oldest_time() itself
                # means nothing this cycle can proceed; requeue below rather
                # than trusting a follow-up oldest_time() call to succeed.
                plugin._log_db_exception(
                    e,
                    f'remove_older_: {itempath} could not read oldest log time, giving up this cycle: {e}',
                    exc_info=True,
                )
                connection_failed = True
                break
            if oldest is None:
                break  # nothing left to compact

            interval_start = (oldest // interval_ms) * interval_ms
            interval_end = interval_start + interval_ms
            if interval_end > cutoff_ms:
                break  # this interval isn't entirely past the cutoff yet - leave it raw

            # transaction() ensures a failure here (e.g. a protocol
            # desync/dropped connection mid-statement) triggers a rollback
            # before the lock releases - without it, self._conn's broken
            # state is left uncleaned for the next caller to inherit.
            # timeout=300 preserves the original hardcoded value (still
            # independent of db_query_timeout - a separate, already-
            # documented issue). The value read (edge/aggregate) happens
            # inside this same transaction(), not before it - _dump() runs
            # under a different lock (_dump_lock, not self._db._fdb_lock)
            # and could otherwise write a new row into this exact interval
            # between an earlier read and this delete, which would then be
            # deleted without ever having contributed to the value just
            # computed.
            try:
                with plugin._db.transaction(timeout=300) as cur:
                    # Cross-checked against item.last_change(), not the buffer (forgotten once
                    # flushed) - a crash orphan looks identical in storage but fails this check.
                    open_time = plugin._log_store.find_open(item_id, cur=cur)
                    open_in_interval = open_time is not None and interval_start <= open_time < interval_end
                    open_is_live = open_in_interval and plugin._timestamp(item.last_change()) == open_time

                    if edge_order:
                        # 'first'/'last': keep the actual oldest/newest raw
                        # value as-is (works for str too - encode_value/
                        # decode_value round-trip it via val_str, unlike the
                        # val_num-based aggregate expressions).
                        edge = plugin._log_store.edge_value(
                            item_id, edge_order, time_start=interval_start - 1, time_end=interval_end, cur=cur
                        )
                        value = plugin._item_value_tuple_rev(item_type, edge) if edge else None
                    elif open_is_live and action in ('avg', 'integrate', 'duty_cycle'):
                        # Clipped to interval_end, not "now" - a provable bound (still open, so
                        # certainly still this value then), same technique as _series()'s duration_now.
                        clipped_expr = expr.replace('duration', f'COALESCE(duration, {interval_end} - time)')
                        value = plugin._log_store.aggregate(
                            item_id, clipped_expr, time_start=interval_start - 1, time_end=interval_end, cur=cur
                        )
                    else:
                        value = plugin._log_store.aggregate(
                            item_id, expr, time_start=interval_start - 1, time_end=interval_end, cur=cur
                        )

                    if value is None:
                        # Valid rows may remain unrepresented (e.g. a crash orphan) - leave the
                        # interval raw rather than delete without writing anything; gap-only
                        # intervals are still cleaned up.
                        valid_rows = plugin._log_store.count(
                            item_id, time_start=interval_start - 1, time_end=interval_end, exclude_gaps=True, cur=cur
                        )
                        if valid_rows:
                            plugin.logger.warning(
                                f'remove_older_: {itempath} interval at {interval_start} has {valid_rows} '
                                f"valid rows but action '{action}' produced no value (all durations NULL?) - "
                                f'leaving interval raw'
                            )
                            stalled = True
                            break

                    # Re-anchor before delete: moving to interval_end makes the delete below
                    # (time < interval_end) naturally skip it - value/quality untouched.
                    if open_is_live:
                        plugin._log_store.reanchor_open(item_id, open_time, interval_end, cur=cur)

                    # delete before insert: interval_start is derived from
                    # the oldest raw row's own timestamp, so a raw row can
                    # legally sit at exactly that timestamp - inserting
                    # the aggregate there first would collide with the
                    # (item_id, time) unique constraint. Both statements
                    # still share one transaction, so a crash between them
                    # can never leave a duplicate aggregate behind on the
                    # next run's self-healing resume.
                    plugin._log_store.delete_range(
                        item_id, time_start=interval_start - 1, time_end=interval_end, cur=cur
                    )
                    if value is not None:
                        now_ms = plugin._timestamp(plugin.shtime.now())
                        entry = BufferEntry(
                            time=interval_start, duration=interval_ms, value=value, quality=QUALITY_VALID
                        )
                        plugin._log_store.insert(item_id, entry, item_type, now_ms, cur=cur)
            except TimeoutError:
                plugin.logger.info(
                    f'remove_older_: {itempath} could not acquire database lock, giving up this compaction cycle'
                    f'{plugin._db.lock_holder_description()}'
                )
                connection_failed = True
                break
            except Exception as e:
                # transaction() already rolled back and reset connection
                # state - the interval stays raw, exactly like the
                # TimeoutError case above, and the next cycle's oldest_time()
                # picks it back up unchanged. A connection error here is the
                # same self-healing case _dump() already handles quietly;
                # anything else is a real bug worth the loud ERROR - same
                # exc_info=True traceback _dump() already gives that case,
                # since this runs on every scheduler cycle just as often.
                plugin._log_db_exception(
                    e, f'remove_older_: {itempath} compaction failed, giving up this cycle: {e}', exc_info=True
                )
                connection_failed = True
                break

            intervals_done += 1

        if intervals_done:
            plugin.logger.info(
                f"remove_older_: {itempath} compacted {intervals_done} interval(s) using action='{action}'"
            )

        # more intervals might already be past the cutoff but weren't
        # reached this cycle (max_aggregate_intervals) - requeue like the
        # delete path does. If we stopped because the next interval isn't
        # past the cutoff yet, this correctly does not requeue. A stalled
        # interval (left raw above) blocks everything behind it - requeuing
        # would just spin on it within the same cycle.
        if connection_failed:
            # Can't reliably tell if there's more work without querying the
            # DB again, which is exactly what just failed - requeue
            # unconditionally so this item is retried next cycle rather
            # than waiting for the worklist to rotate all the way around.
            plugin._maxage_worklist.append(item)
        else:
            oldest = plugin._log_store.oldest_time(item_id)
            if not stalled and oldest is not None and oldest + interval_ms <= cutoff_ms:
                plugin._maxage_worklist.append(item)

    def remove_older_than_maxage(self):
        """
        Remove log entries older than maxage of an item

        Called by scheduler
        """
        plugin = self._plugin
        if plugin.lock_remove_older:
            if not plugin._remove_older_skipped:
                plugin.logger.info('remove_older_than_maxage task is manually locked')
                plugin._remove_older_skipped = True
            return

        if not plugin._db.connected():
            plugin.logger.warning('remove_older_than_maxage skipped because db is not connected')
            return False

        # prevent creation of more than one thread
        current_thread = threading.current_thread()
        current_thread_name = current_thread.name
        for t in threading.enumerate():
            if t is current_thread:
                continue
            if t.name == current_thread_name:
                if not plugin._remove_older_skipped:
                    plugin.logger.info(
                        'remove_older_than_maxage skipped because a thread with this task is already running'
                    )
                plugin._remove_older_skipped = True
                return

        plugin._remove_older_skipped = False

        if plugin.remove_orphan:
            plugin.remove_orphan_items()

        # go to work
        if plugin._maxage_worklist == []:
            # Fill work list, if it is empty
            if plugin._default_maxage == 0:
                plugin._maxage_worklist = [i for i in plugin._items_with_maxage]
            else:
                plugin._maxage_worklist = [i for i in plugin._handled_items]
            plugin.logger.info(f'remove_older_: Worklist filled with {len(plugin._maxage_worklist)} items')

        if not plugin._maxage_worklist:
            return  # nothing to do this cycle (no items with 'database' set)

        item = plugin._maxage_worklist.pop(0)
        itempath = item.property.path

        item_id = None  # initialise before try so the except clause can reference it safely
        try:
            item_id = plugin.id(item, create=False)
        except Exception:
            if item_id is None:
                plugin.logger.info(f'remove_older_: no id for item {itempath}')
            else:
                plugin.logger.critical(f'remove_older_: no id for item {itempath}')
            return

        time_end = plugin.get_maxage_ts(item)
        if time_end is None:
            # no usable maxage for this item (e.g. an invalid database_maxage
            # value, already logged by get_maxage_ts) - nothing to do
            return
        timestamp_end = plugin._timestamp(time_end)

        maxage_action = plugin._maxage.action_for(item)
        if maxage_action != 'delete':
            # compaction always replaces raw rows with an aggregate row in
            # the same transaction as deleting them, so the item's log can
            # never end up empty as a side effect - the database: init
            # last-value-preservation logic below is a delete-path-only
            # concern and doesn't apply here.
            plugin._compact_maxage(item, item_id, itempath, time_end, maxage_action)
            logcount = plugin.readLogCount(item_id)
            plugin._item_logcount[item_id] = logcount
            plugin._webdata[item.property.path].update({'logcount': logcount})
            return

        # if delete would also remove the last logged value for the item then there might be no chance for
        # ``database: init`` to retrieve the latest value.
        remaining = 1
        if plugin.get_iattr_value(item.conf, 'database').lower() == 'init':
            # find out if there are still log entries after deletion of the logs
            remaining = plugin.readLogCount(
                item_id, time_start=plugin._timestamp(time_end + datetime.timedelta(microseconds=1))
            )
            # remaining can be larger than self._item_logcount[item_id], it depends on the rate of database updates
            # self.logger.info(f"remove_older_: {itempath} has attribute init with {self._item_logcount[item_id]} log entries and will have {remaining} log entries after deletion")

        if remaining <= 0:
            # no log entries will be there after deletion, need to go back in time for the latest logentry
            try:
                new_must_keep_timestamp = plugin.readLatestLog(item_id, timestamp_end)
            except Exception as e:
                # Can't safely proceed without this - deleting blind here
                # risks wiping an item's last remaining value. Requeue and
                # retry next cycle, same as every other connection-loss path
                # in this function.
                plugin._log_db_exception(
                    e,
                    f'remove_older_: {itempath} could not read latest log entry, retrying next cycle: {e}',
                    exc_info=True,
                )
                plugin._maxage_worklist.append(item)
                return
            if new_must_keep_timestamp is None:
                return
            new_must_keep_time = plugin._datetime(new_must_keep_timestamp)
            plugin.logger.info(
                f'remove_older_: {itempath} no remaining log entry between {time_end} and now, thus can not remove log entries older than maxage, latest log is {new_must_keep_time}'
            )
            time_end = new_must_keep_time + datetime.timedelta(microseconds=-1)
            timestamp_end = plugin._timestamp(time_end)

        # readLogCount's time_end is inclusive (time <= time_end) but
        # deleteLog()/delete_range's is exclusive (time < time_end) - the
        # "- 1" (timestamps are integer ms) makes this count match exactly
        # what the deletion below will remove; without it, a log entry
        # landing exactly on timestamp_end would be counted here but left
        # behind by the actual DELETE.
        count_log_records_to_delete = plugin.readLogCount(item_id, time_end=timestamp_end - 1)
        count_log_records_to_delete_str = f'{count_log_records_to_delete:,}'.replace(',', '.')
        max_delete_logentries_str = f'{plugin.max_delete_logentries:,}'.replace(',', '.')
        time_end_str = time_end.strftime('%d.%m.%Y - %H:%M')
        plugin.logger.debug(
            f'remove_older_: {itempath} remove older than {time_end_str} - {count_log_records_to_delete_str} records to delete'
        )

        if count_log_records_to_delete > plugin.max_delete_logentries:
            time_start_deletion = time.time()
            # transaction() commits this DELETE itself, rather than relying
            # on some unrelated later commit()
            # Not a bare DELETE...ORDER BY...LIMIT (invalid SQLite syntax
            # without a non-default compile flag) or a rowid-subquery (the
            # {log} table has no primary key, and MySQL/MariaDB - unlike
            # SQLite - has no queryable row id for a table without one).
            # Matches on (item_id, time) instead, via the UNIQUE KEY
            # Double-wrapped, not single-wrap: MariaDB separately rejects
            # LIMIT directly inside an IN(subquery).
            try:
                with plugin._db.transaction(timeout=300) as cur:
                    plugin._execute(
                        plugin._prepare(
                            'DELETE FROM {log} WHERE item_id = :id AND time IN (SELECT time FROM '
                            '(SELECT time FROM {log} WHERE item_id = :id ORDER BY time ASC LIMIT :maxrecords) '
                            'AS del_batch);'
                        ),
                        {'id': item_id, 'maxrecords': plugin.max_delete_logentries},
                        cur=cur,
                    )
            except TimeoutError:
                plugin.logger.info(
                    f'remove_older_: {itempath} could not acquire database lock for deletion, retrying next cycle'
                    f'{plugin._db.lock_holder_description()}'
                )
                plugin._maxage_worklist.append(item)
                return
            except Exception as e:
                # Same self-healing case as _compact_maxage()'s equivalent
                # except-block - requeue so this item's batch delete is
                # retried next cycle instead of waiting for the worklist to
                # rotate all the way around. Same exc_info=True convention
                # as that block too, for the same reason.
                plugin._log_db_exception(
                    e, f'remove_older_: {itempath} deletion failed, retrying next cycle: {e}', exc_info=True
                )
                plugin._maxage_worklist.append(item)
                return
            time_used_for_deletion = time.time() - time_start_deletion
            plugin.logger.info(
                f'remove_older_: {itempath} deleted {max_delete_logentries_str} of {count_log_records_to_delete_str} log entries - took {time_used_for_deletion:.2f} seconds, averaging {100 * time_used_for_deletion / plugin.max_delete_logentries:.4f} seconds per 100 entries'
            )

            # Re-Add item to worklist, since there are more records to be deleted
            plugin._maxage_worklist.append(item)

        elif count_log_records_to_delete:
            time_start_deletion = time.time()
            plugin.deleteLog(item_id, time_end=timestamp_end)
            time_used_for_deletion = time.time() - time_start_deletion
            time_end_str = time_end.strftime('%d.%m.%Y - %H:%M')
            plugin.logger.info(
                f'remove_older_: {itempath} deleted {count_log_records_to_delete_str} log entries until {time_end_str} took {time_used_for_deletion:.2f} seconds, averaging {100 * time_used_for_deletion / count_log_records_to_delete:.4f} seconds per 100 entries'
            )

        # update the logCount for the item
        logcount = plugin.readLogCount(item_id)
        plugin._item_logcount[item_id] = logcount
        plugin._webdata[item.property.path].update({'logcount': logcount})

        return

    def get_maxage_ts(self, item):
        """
        Get the actual maxage-timestamp for a given item

        :param item:

        :return:
        """
        plugin = self._plugin
        maxage = None
        if plugin.has_iattr(item.conf, 'database_maxage'):
            maxage = plugin.get_iattr_value(item.conf, 'database_maxage')
        elif plugin._default_maxage > 0:
            maxage = plugin._default_maxage

        if maxage:
            try:
                maxage = float(maxage)
            except (TypeError, ValueError):
                plugin.logger.warning(
                    f"Item {item.property.path}: database_maxage value '{maxage}' is not a number, ignoring"
                )
                return None
            if maxage > 0:
                dt = plugin.shtime.now()
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                dt = dt - datetime.timedelta(maxage)
                return dt
        return None

    def count_logentries(self):
        """
        count number of log entries for all items in database

        called by scheduler once on start
        """
        plugin = self._plugin
        plugin.logger.info('_count_logentries: # handled items = {}'.format(len(plugin._handled_items)))
        plugin._items_still_counting = True
        plugin._items_total_entries = 0
        for item in plugin._handled_items:
            item_id = plugin.id(item, create=False)
            logcount = plugin.readLogCount(item_id)
            plugin._item_logcount[item_id] = logcount
            plugin._items_total_entries += logcount
            plugin._webdata[item.property.path].update({'logcount': logcount})
            # self._webdata[item.property.path].update({'logcount': f"{logcount:,}".replace(',', '.')})

        plugin._items_still_counting = False
        return
