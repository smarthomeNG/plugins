#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — driver-alias resolution and TimescaleDB feature activation
#########################################################################

"""
Friendly driver name resolution and PostgreSQL/TimescaleDB-specific feature activation:
hypertable conversion, native compression, native continuous aggregation, and native
retention. All of this is a no-op (or returns early) on every other driver.

See doc/dev/database/database.md §8 for the end-to-end design, and
img/timescale_native_setup_flow.svg for the full call sequence including every failure
branch.
"""

import importlib

import lib.db


class TimescaleManager:
    """Owns driver-alias resolution and every PostgreSQL/TimescaleDB-specific
    activation/status method. Takes a back-reference to the Database plugin instance
    (*plugin*) rather than individual parameters - see maxage.py's MaxageResolver for
    the same pattern and database.md §2's "Dependency wiring" note on why.

    Constructed as the very first thing in Database.__init__(), before self._db or any
    other plugin state exists - _resolve_driver_alias()/_resolve_postgres_driver_alias()
    only ever touch the two alias constants below plus self._plugin.logger, so this is
    safe; every other method here is only ever called later (from _initialize_db() or
    run()), by which point the rest of the plugin's state is set up.
    """

    # Friendly driver names resolved to a real, importable DB-API2 module
    # name in __init__() before self.driver is used anywhere - everything
    # downstream still only ever sees the real module names.
    _DRIVER_ALIASES = {'mysql': 'pymysql', 'mariadb': 'pymysql'}
    # 'postgres'/'timescaledb' etc. don't map to one fixed module: psycopg2
    # and psycopg (v3) are two different installable packages, so these are
    # resolved by probing for whichever one is actually installed instead
    # (see resolve_postgres_driver_alias()).
    _POSTGRES_DRIVER_ALIASES = frozenset({'postgres', 'postgresql', 'timescale', 'timescaledb'})

    def __init__(self, plugin):
        self._plugin = plugin

    def resolve_driver_alias(self, driver_value):
        """Resolve a friendly driver name (e.g. 'mysql', 'timescaledb') to
        the real, importable DB-API2 module name lib.db.Database expects.
        Returns *driver_value* unchanged if it isn't a known alias -
        including when it's already a real module name.

        :param driver_value: the raw 'driver' parameter value.
        :returns: a real DB-API2 module name.
        """
        driver_lower = driver_value.lower()
        if driver_lower in self._DRIVER_ALIASES:
            return self._DRIVER_ALIASES[driver_lower]
        if driver_lower in self._POSTGRES_DRIVER_ALIASES:
            return self.resolve_postgres_driver_alias(driver_value)
        return driver_value

    def resolve_postgres_driver_alias(self, alias):
        """Probe for whichever of psycopg2/psycopg is actually installed,
        preferring psycopg2. Falls back to 'psycopg2' (without having
        confirmed it imports) if neither is found, so the resulting error
        from lib.db.Database's own import attempt names a real package
        instead of the friendly alias someone would otherwise need to
        search for.

        :param alias: the friendly name as configured (only used for logging).
        :returns: 'psycopg2' or 'psycopg'.
        """
        for candidate in ('psycopg2', 'psycopg'):
            try:
                importlib.import_module(candidate)
            except ImportError:
                continue
            self._plugin.logger.info(f"Database: driver '{alias}' resolved to '{candidate}'")
            return candidate
        self._plugin.logger.warning(
            f"Database: driver '{alias}' requires psycopg2 or psycopg to be installed, neither found - "
            "falling back to 'psycopg2'"
        )
        return 'psycopg2'

    def enable_hypertable(self):
        """Activate the TimescaleDB extension and convert {log} into a hypertable.

        Called once, from _initialize_db()'s self._db setup path only - both
        operations are database-global, not per-connection, so running them
        again from self._db_maint's own init would just be redundant work
        against the already-converted table (create_hypertable() is called
        with if_not_exists=True, so it's harmless, just wasted).

        Non-fatal on any failure (missing extension on the server,
        insufficient privilege, ...): logs a clear warning and leaves the
        table as a plain table - every other part of the plugin works
        identically either way, since a hypertable is queried exactly like
        a regular table.
        """
        plugin = self._plugin
        log_table = plugin._replace['log']
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute('CREATE EXTENSION IF NOT EXISTS timescaledb;', cur=cur)
        except Exception as e:
            plugin.logger.warning(
                f'Database: timescale_hypertable is enabled but the TimescaleDB extension could not be '
                f'activated ({e}) - continuing with {log_table} as a plain table'
            )
            return
        try:
            # create_hypertable()'s first argument is typed regclass, not a
            # raw SQL identifier position - it accepts a plain string that
            # casts, so it binds through the normal :name mechanism like
            # any other value (confirmed against a live instance) rather
            # than needing hand-rolled identifier quoting.
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    "SELECT create_hypertable(:table, 'time', chunk_time_interval => :chunk_ms, "
                    'if_not_exists => TRUE, migrate_data => TRUE);',
                    {'table': log_table, 'chunk_ms': plugin._timescale_chunk_interval_ms},
                    cur=cur,
                )
            plugin.logger.notice(
                f'Database: {log_table} converted to a TimescaleDB hypertable '
                f'(chunk_time_interval={plugin._timescale_chunk_interval_ms}ms)'
            )
        except Exception as e:
            plugin.logger.warning(f'Database: could not convert {log_table} to a hypertable ({e})')

    def enable_compression(self):
        """Enable native columnar compression on {log} and add a policy compressing
        everything older than one chunk width, leaving the current chunk alone.

        The current chunk is the only one that can hold a mutable "open row" (see
        _compact_maxage()'s find_open()/open_time handling) - every item's live
        interval is always within it, so leaving exactly that one chunk uncompressed
        is sufficient; no separate threshold is needed since it's already the same
        interval as timescale_chunk_interval. compress_after reuses
        plugin._timescale_chunk_interval_ms directly rather than a second parameter.

        Compaction eventually reaching an already-compressed chunk (at whatever
        database_maxage the item configures) forces a one-time decompress on that
        chunk - acceptable, since compaction only ever touches a given interval
        once. A manual WebIf edit/delete on old data forces the same one-time
        decompress; also acceptable, since that's a rare, human-triggered path, not
        one of the plugin's high-throughput core methods.

        Non-fatal on any failure, same rationale as enable_hypertable():
        leaves {log} uncompressed, every other part of the plugin is unaffected.
        """
        plugin = self._plugin
        log_table = plugin._replace['log']
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    f'ALTER TABLE {log_table} SET (timescaledb.compress, '
                    "timescaledb.compress_segmentby = 'item_id', "
                    "timescaledb.compress_orderby = 'time DESC');",
                    cur=cur,
                )
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    'SELECT add_compression_policy(:table, compress_after => :compress_after_ms, '
                    'if_not_exists => TRUE);',
                    {'table': log_table, 'compress_after_ms': plugin._timescale_chunk_interval_ms},
                    cur=cur,
                )
            plugin.logger.notice(
                f'Database: {log_table} compression enabled (compress_after={plugin._timescale_chunk_interval_ms}ms)'
            )
        except Exception as e:
            plugin.logger.warning(f'Database: could not enable compression on {log_table} ({e})')

    def enable_native_aggregation(self):
        """Register the integer-now function TimescaleDB needs for continuous
        aggregates on this bigint-epoch-ms schema, then create one continuous
        aggregate per distinct database_maxage_interval actually in use
        (grouped across items - one cagg per interval width, not per item or
        per action, matching the 2026-09-03 prototype's finding that actions
        are cheap extra SELECT-list columns on a shared view).

        Called once from run(), not _initialize_db()'s setup path - unlike
        hypertable/compression, this needs the real item list
        (_items_with_maxage/_handled_items), which parse_item() has not
        populated yet at __init__()'s own _initialize_db() call.

        Items resolving to action 'delete' are skipped entirely - native
        retention (if enabled) handles them directly by dropping raw chunks,
        no aggregate needed. Non-fatal on any failure, same rationale as
        hypertable/compression: leaves native aggregation inactive for the
        affected interval, every other part of the plugin is unaffected.
        """
        plugin = self._plugin
        log_table = plugin._replace['log']
        now_func = f'{log_table}_time_now'
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    f'CREATE OR REPLACE FUNCTION {now_func}() RETURNS BIGINT LANGUAGE SQL STABLE AS '
                    # CAST(... AS BIGINT), not ::bigint - lib.db's :name param regex (r':(\w+)') also
                    # matches the second colon of a :: cast, misreading it as a missing bind param.
                    '$$ SELECT CAST(extract(epoch from now()) * 1000 AS BIGINT) $$;',
                    cur=cur,
                )
        except Exception as e:
            plugin.logger.warning(
                f'Database: could not create the integer-now function for native aggregation ({e}) - '
                'native mode cannot activate'
            )
            return
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute(f"SELECT set_integer_now_func('{log_table}', '{now_func}');", cur=cur, quiet=True)
        except Exception as e:
            # set_integer_now_func() is not idempotent - it errors on every call after the first,
            # even re-registering the same function, unlike every other IF NOT EXISTS-style call
            # here. "already set" is the expected, harmless case on every restart after the first
            # successful one; anything else is a real failure. quiet=True above since this
            # expected case would otherwise ERROR-log on every single restart - this except
            # block already reports the genuinely-bad case itself, just without lib.db's noise.
            if 'already set' not in str(e).lower():
                plugin.logger.warning(
                    f'Database: could not register integer-now function for native aggregation ({e}) - '
                    'native mode cannot activate'
                )
                return

        intervals_ms = set()
        for item in plugin._maxage.native_relevant_items():
            if plugin._maxage.action_for(item) == 'delete':
                continue
            intervals_ms.add(plugin._maxage.interval_seconds_for(item) * 1000)
        for interval_ms in sorted(intervals_ms):
            self.create_native_cagg(log_table, interval_ms)

    def create_native_cagg(self, log_table, interval_ms):
        """Create one continuous aggregate (+ thin wrapper view + refresh
        policy) for a single database_maxage_interval width, materializing
        every 2026-09-03 prototype-proven action as its own column: additive
        aggregates (sum/min/max/countall) directly, ratio-based ones
        (avg/duty_cycle/integrate) as component sums divided in the wrapper
        view (never pre-divided - that breaks incremental refresh, since
        only additive aggregates re-merge validly across partial refreshes),
        and first/last via TimescaleDB's core first()/last() aggregate
        functions across all three value columns (val_str/val_num/val_bool),
        matching LogStore.edge_value()'s own all-three-columns shape.

        Deliberately always materializes all columns regardless of which
        actions any given item actually configures - SQL aggregates over an
        item's always-NULL columns (e.g. val_bool for a 'num' item) just
        produce NULL harmlessly, and one shared, simple column set per
        interval is far easier to keep correct than tracking which actions
        are in use at each width. WITH NO DATA defers the full historical
        backfill to the refresh policy's own incremental catch-up, avoiding
        one large synchronous materialization at creation time.
        """
        plugin = self._plugin
        cagg_name = f'{log_table}_cagg_{interval_ms // 1000}s'
        final_view = f'{cagg_name}_final'
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    f'CREATE MATERIALIZED VIEW IF NOT EXISTS {cagg_name} WITH (timescaledb.continuous) AS '
                    f'SELECT time_bucket({interval_ms}, time) AS bucket, item_id, '
                    'SUM(val_num * duration) AS sum_val_duration, '
                    'SUM(duration) AS sum_duration, '
                    'SUM(val_bool * duration) AS sum_val_bool_duration, '
                    'SUM(val_num) AS sum_value, '
                    'MIN(val_num) AS min_value, '
                    'MAX(val_num) AS max_value, '
                    'COUNT(*) AS countall_value, '
                    'first(val_str, time) AS first_val_str, '
                    'first(val_num, time) AS first_val_num, '
                    'first(val_bool, time) AS first_val_bool, '
                    'last(val_str, time) AS last_val_str, '
                    'last(val_num, time) AS last_val_num, '
                    'last(val_bool, time) AS last_val_bool '
                    f'FROM {log_table} GROUP BY bucket, item_id WITH NO DATA;',
                    cur=cur,
                )
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    f'CREATE OR REPLACE VIEW {final_view} AS SELECT bucket, item_id, '
                    'sum_val_duration / NULLIF(sum_duration, 0) AS avg_value, '
                    'sum_val_duration AS integrate_value, '
                    'sum_val_bool_duration / NULLIF(sum_duration, 0) AS duty_cycle_value, '
                    'sum_value, min_value, max_value, countall_value, '
                    'first_val_str, first_val_num, first_val_bool, '
                    f'last_val_str, last_val_num, last_val_bool FROM {cagg_name};',
                    cur=cur,
                )
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    f"SELECT add_continuous_aggregate_policy('{cagg_name}', start_offset => NULL, "
                    f"end_offset => {interval_ms}, schedule_interval => INTERVAL '1 hour', if_not_exists => TRUE);",
                    cur=cur,
                )
            plugin.logger.notice(f'Database: created native cagg {cagg_name} (interval={interval_ms}ms)')
        except Exception as e:
            plugin.logger.warning(f'Database: could not create native cagg {cagg_name} ({e})')

    def enable_native_retention(self):
        """Add a retention policy dropping raw chunks once they're older
        than the longest configured database_maxage across all relevant
        items, plus one chunk width as a safety margin (covers downtime -
        see plugin.yaml's own parameter description). Safe specifically
        because native aggregation (see above) already materializes
        aggregates into their own, separate hypertable before this ever
        runs - dropping a raw chunk here never touches cagg-owned storage.

        Skips (with a warning, non-fatal) if no item and no default_maxage
        configures a maxage at all - there is nothing to retain against.

        DESIGN DECISION - deliberate, not a gap: this is one global
        threshold for the whole hypertable, not a per-item one. A
        database_maxage_action: delete item configured for e.g. 5 days
        still keeps its raw data until the *longest* maxage among every
        item sharing its chunks has passed, the same as every other item -
        native mode never runs remove_older_than_maxage()'s old per-item
        row-by-row DELETE either (see _start_schedulers()), even for
        delete-action items specifically. This is intentional, not an
        oversight to "fix" by resurrecting manual deletion for delete-only
        items: doing so would defeat the reason a coarse global threshold
        is acceptable at all - native columnar compression (Tier 2 part 3,
        measured 17.39x on real data) already absorbs the cost of keeping
        raw data around longer than any single item strictly needs, so
        precise per-item pruning stops being worth the complexity once
        compression is doing the real work. If timescale_native_retention
        is off entirely, the same logic still applies one step further:
        nothing prunes raw data at all, indefinitely - also deliberate, not
        a gap (see timescale_native_retention's own plugin.yaml
        description).
        """
        plugin = self._plugin
        log_table = plugin._replace['log']
        max_maxage_days = plugin._default_maxage if plugin._default_maxage > 0 else 0.0
        for item in plugin._items_with_maxage:
            if plugin.has_iattr(item.conf, 'database_maxage'):
                try:
                    max_maxage_days = max(max_maxage_days, float(plugin.get_iattr_value(item.conf, 'database_maxage')))
                except (TypeError, ValueError):
                    continue
        if max_maxage_days <= 0:
            plugin.logger.warning(
                'Database: timescale_native_retention is enabled but no item (or default_maxage) configures a '
                'database_maxage - nothing to retain against, skipping'
            )
            return
        drop_after_ms = int(max_maxage_days * 86400000) + plugin._timescale_chunk_interval_ms
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    'SELECT add_retention_policy(:table, drop_after => :drop_after_ms, if_not_exists => TRUE);',
                    {'table': log_table, 'drop_after_ms': drop_after_ms},
                    cur=cur,
                )
            plugin.logger.notice(f'Database: native retention enabled on {log_table} (drop_after={drop_after_ms}ms)')
        except Exception as e:
            plugin.logger.warning(f'Database: could not enable native retention on {log_table} ({e})')

    def native_retention_active_in_db(self):
        """True if a native retention (chunk-drop) job is currently
        scheduled against {log}, regardless of what this instance's own
        config claims - a TimescaleDB policy is the database server's own
        background job, entirely independent of shng being up, down, or
        ever started (see reconcile_native_retention_reality())."""
        plugin = self._plugin
        log_table = plugin._replace['log']
        result = plugin._fetchall(
            "SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' "
            'AND hypertable_name = :table LIMIT 1;',
            {'table': log_table},
        )
        return bool(result)

    def hypertable_active_in_db(self):
        """True if {log} is currently a TimescaleDB hypertable in the real
        database, regardless of what timescale_hypertable currently says -
        same reality-over-config rationale as native_retention_active_in_db().
        Raises like that method does; callers needing a non-raising check
        (e.g. against a plain PostgreSQL server with no TimescaleDB
        extension) should use status()."""
        plugin = self._plugin
        log_table = plugin._replace['log']
        result = plugin._fetchall(
            'SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = :table LIMIT 1;',
            {'table': log_table},
        )
        return bool(result)

    def native_cagg_active_in_db(self):
        """True if at least one native TimescaleDB continuous aggregate
        exists for {log} in the real database, regardless of what
        timescale_native_aggregation currently says - same reality-over-
        config rationale as native_retention_active_in_db()."""
        plugin = self._plugin
        log_table = plugin._replace['log']
        result = plugin._fetchall(
            'SELECT 1 FROM timescaledb_information.continuous_aggregates WHERE hypertable_name = :table LIMIT 1;',
            {'table': log_table},
        )
        return bool(result)

    def status(self):
        """Reality-checked TimescaleDB status for {log}, independent of
        what timescale_hypertable/timescale_native_aggregation/
        timescale_native_retention currently say in plugin.yaml - config
        can drift from the database's actual state (see
        reconcile_native_retention_reality()'s docstring for why). Used by
        the dashboard's database-properties widget to show what's actually
        active, not what's configured.

        A value of None means the check itself failed (e.g. the
        TimescaleDB extension isn't installed, so its catalog views don't
        exist) - distinct from False, which means the check ran and found
        the feature inactive.

        :return: {'hypertable': bool | None, 'native_cagg': bool | None,
            'native_retention': bool | None}, or {} for a non-psycopg driver.
        """
        plugin = self._plugin
        if plugin.driver.lower() not in lib.db.Database._psycopg_driver_names:
            return {}
        # Through the plugin's own delegates (plugin._hypertable_active_in_db, ...), not
        # self.hypertable_active_in_db directly - the test suite mocks these at the plugin
        # level (plugin._hypertable_active_in_db etc.), predating this module's existence.
        checks = {
            'hypertable': plugin._hypertable_active_in_db,
            'native_cagg': plugin._native_cagg_active_in_db,
            'native_retention': plugin._native_retention_active_in_db,
        }
        status = {}
        for key, check in checks.items():
            try:
                status[key] = check()
            except Exception as e:
                plugin.logger.warning(f'Database: could not check {key} status ({e})')
                status[key] = None
        return status

    def disable_native_retention_policy(self):
        """Remove an active retention policy - the one deliberate exception
        to this plugin never tearing down a TimescaleDB policy on its own
        (see timescale_compress/timescale_native_retention's own plugin.yaml
        descriptions on why that's normally not done). Justified here
        specifically because remove_retention_policy() only stops *future*
        drops - it cannot undo chunks already gone - so automating it
        carries none of the casual-reversal risk that ruled out automatic
        teardown everywhere else.

        :returns: True if the policy was actually removed, False on failure -
            the caller falls back to force_native_mode_for_safety() when
            False, since the policy stays active either way.
        """
        plugin = self._plugin
        log_table = plugin._replace['log']
        try:
            with plugin._db.transaction() as cur:
                plugin._db.execute(
                    'SELECT remove_retention_policy(:table, if_exists => TRUE);', {'table': log_table}, cur=cur
                )
            plugin.logger.critical(f'Database: removed the active native retention policy on {log_table}.')
            return True
        except Exception as e:
            plugin.logger.critical(
                f'Database: could not remove the active native retention policy on {log_table} ({e}).'
            )
            return False

    def force_native_mode_for_safety(self, reason):
        """Force timescale_native_aggregation to True for this run only -
        never rewrites plugin.yaml. Shared by every reconcile_native_
        retention_reality() branch that ends up here, so the corrective
        action and its message stay identical regardless of which
        real/configured-state mismatch triggered it.

        :param reason: One sentence, no trailing period - what was found
            that makes this necessary.
        """
        plugin = self._plugin
        plugin.logger.critical(
            f'Database: {reason} - forcing native mode for THIS RUN to prevent data loss. Stopping shng does NOT '
            'stop the retention policy. Edit plugin.yaml (timescale_native_aggregation: true) to make this '
            'permanent and clear this warning.'
        )
        plugin._timescale_native_aggregation = True

    def reconcile_native_retention_reality(self):
        """Called once per run(), before any native-mode setup: checks
        whether a retention policy is *actually* active against the real
        database, independent of what timescale_native_retention/
        timescale_native_aggregation currently say - config can drift from
        reality (an admin edits plugin.yaml while shng is stopped, an
        unattended restart never surfaces a critical log to anyone), and a
        TimescaleDB retention policy runs on its own schedule regardless of
        shng's state, so passive logging alone cannot prevent the unsafe
        combination (native retention dropping chunks while plugin-mode
        compaction stores aggregates in-place in those same chunks) from
        silently causing data loss. 2026-09-04 design decision: self-correct
        rather than merely warn, since a wrong auto-correction is a loud,
        recoverable inconvenience (edit plugin.yaml, done) while leaving the
        unsafe combination running is an irreversible one.

        Four cases, always logged at CRITICAL except the last:

        - Active + configured active, but timescale_native_aggregation is
          False: force native mode for this run.
        - Active but configured off: remove the policy. If that fails,
          same forced-native fallback as above - the policy stays active
          either way, so the run still needs to be safe under it.
        - Not active, but configured active with timescale_native_aggregation
          False: refuse to enable it this run - nothing dangerous is
          happening yet, so no self-correction is needed, just don't create
          it.
        - Not active, configured active, timescale_native_aggregation
          already True: the normal, safe, aligned state - no warning,
          proceeds as usual.
        """
        plugin = self._plugin
        try:
            # plugin._native_retention_active_in_db, not self.native_retention_active_in_db -
            # the test suite mocks this at the plugin level, predating this module's existence.
            active = plugin._native_retention_active_in_db()
        except Exception as e:
            plugin.logger.warning(f'Database: could not check for an active native retention policy ({e})')
            return

        if active and plugin._timescale_native_retention:
            if not plugin._timescale_native_aggregation:
                self.force_native_mode_for_safety(
                    'native retention is active but timescale_native_aggregation is not enabled'
                )
        elif active and not plugin._timescale_native_retention:
            plugin.logger.critical(
                'Database: native retention is active but timescale_native_retention is False in plugin.yaml - '
                'removing the policy to match configured intent. This does not undo raw data already deleted.'
            )
            removed = plugin._disable_native_retention_policy()
            if not removed and not plugin._timescale_native_aggregation:
                self.force_native_mode_for_safety(
                    'native retention is active, not configured, and could not be removed'
                )
        elif not active and plugin._timescale_native_retention and not plugin._timescale_native_aggregation:
            plugin.logger.critical(
                'Database: timescale_native_retention is enabled but timescale_native_aggregation is not - '
                'refusing to enable retention this run. Set timescale_native_aggregation: true to enable '
                'native retention.'
            )
            plugin._timescale_native_retention = False
