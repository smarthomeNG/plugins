#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — on-demand analytics (item.series/item.db, native-cagg routing)
#########################################################################

"""
On-demand analytics for the websocket plugin (item.series, bound in parse_item()) and
logics (item.db). Also the native-TimescaleDB-cagg routing counterparts consumed by
readLogCount() (which stays on Database - see __init__.py).

See doc/dev/database/database.md §8 for the merge/exclusive/additive routing design
between raw data and native continuous aggregates, and img/query_read_flow.svg for the
full call sequence.
"""

import decimal
import re


class QueryEngine:
    """Owns _series()/_single() and every native-cagg query-routing method. Takes a
    back-reference to the Database plugin instance (*plugin*) rather than individual
    parameters - see maxage.py's MaxageResolver for the same pattern and database.md
    §2's "Dependency wiring" note on why.

    Internal cross-calls to fetch_log()/native_cagg_single()/native_cagg_series() go
    through the plugin's own delegate (e.g. plugin._fetch_log()) rather than calling
    siblings directly - the test suite mocks these at the plugin level, predating this
    module's existence (same reasoning as maintenance.py/timescale.py).
    """

    # func -> cagg re-aggregation expression, applied across every matching
    # bucket row (see native_cagg_single()). Ratio actions (avg/on/
    # duty_cycle) sum both components first and divide once - never average
    # the per-bucket wrapper view's already-divided value, which would be
    # wrong the same way it would for the materialized view itself (see
    # TimescaleManager.create_native_cagg()'s own docstring). min/max compose
    # validly because MIN-of-MINs/MAX-of-MAXs across a partition equals the
    # overall MIN/MAX; sum/integrate/countall are already additive.
    _NATIVE_CAGG_SINGLE_EXPR = {
        'avg': 'SUM(sum_val_duration) / SUM(sum_duration)',
        'integrate': 'SUM(sum_val_duration)',
        'sum': 'SUM(sum_value)',
        'min': 'MIN(min_value)',
        'max': 'MAX(max_value)',
        'countall': 'SUM(countall_value)',
        'on': 'SUM(sum_val_bool_duration) / SUM(sum_duration)',
        'duty_cycle': 'SUM(sum_val_bool_duration) / SUM(sum_duration)',
    }
    _NATIVE_CAGG_SINGLE_PRECISION_FUNCS = ('avg', 'on', 'duty_cycle')

    def __init__(self, plugin):
        self._plugin = plugin

    def series(self, func, start, end='now', count=100, ratio=1, update=False, step=None, sid=None, item=None):
        """
        This method is called (via the item object) from the websocket plugin,
        when a data series for an item is requested for the visu

        It returns the data structure in the form needed by the websocket plugin to directly
        return it to the visu

        :param func:
        :param start:
        :param end:
        :param count:
        :param ratio:
        :param update:
        :param step:
        :param sid:
        :param item:

        :return: data structure in the form needed by the websocket plugin return it to the visu
        """
        plugin = self._plugin
        # self.logger.debug("_series: item={}, func={}, start={}, end={}, count={}".format(item, func, start, end, count))
        init = not update
        if sid is None:
            sid = item + '|' + func + '|' + str(start) + '|' + str(end) + '|' + str(count)
        func, expression = self.expression(func)
        # 'diff'/'differentiate' need LAG(...) OVER (ORDER BY time) computed
        # per raw row before any GROUP BY - mixing a window function with an
        # aggregate GROUP BY in one SELECT (the previous approach) errors
        # outright under MySQL 8/5.7's default ONLY_FULL_GROUP_BY, and
        # returns an undefined arbitrary-row's LAG value per bucket on
        # MariaDB's default (permissive) mode - verified against a real
        # MariaDB target. This subquery computes the per-row diff/time-gap
        # first; the outer query then buckets by summing across rows in
        # each bucket, which telescopes correctly across bucket boundaries
        # (sum of consecutive diffs = last value - first value spanned).
        diff_window_table = (
            '(SELECT time, val_num, '
            '(val_num - LAG(val_num,1) OVER (ORDER BY time)) AS diffval, '
            '(time - LAG(time,1) OVER (ORDER BY time)) AS timegap '
            'FROM {log} WHERE ' + self.fetch_log_base_where() + ') w'
        )
        queries = {
            'avg': self.time_precision_query('MIN(time)')
            + ', '
            + self.precision_query('AVG(val_num * duration) / AVG(duration)'),
            'avg.order': 'ORDER BY time ASC',
            'integrate': self.time_precision_query('MIN(time)') + ', SUM(val_num * duration)',
            # SUM(diffval): total net change during the bucket. Rows with no
            # predecessor (diffval IS NULL - the very first row in range)
            # are ignored by SUM, same as they always were as a single
            # ungrouped row.
            'diff': self.time_precision_query('MIN(time)') + ', SUM(diffval)',
            'diff.table': diff_window_table,
            'duration': self.time_precision_query('MIN(time)') + ', duration',
            # differentiate (d/dt) is scaled to match the conversion from d/dt (kWh) = kWh: time is in ms, val_num in kWh, therefore scale by 1000ms and 3600s/h to obtain the result in kW:
            # total change over the bucket / total time spanned by the
            # bucket, in hours - the physically correct average rate over
            # an interval built from irregular samples (not an average of
            # per-row rates, which would over-weight short gaps). 3600.0
            # (not 3600): SUM(timegap) is an integer column - on SQLite,
            # dividing two integers is integer (floor) division, so any
            # bucket spanning under an hour would floor-divide to 0 and
            # then divide-by-zero to NULL; the float literal forces real
            # division. MariaDB/MySQL always do real division for '/'
            # regardless of operand type, so this was sqlite-only.
            'differentiate': self.time_precision_query('MIN(time)')
            + ', SUM(diffval) / (SUM(timegap) / (3600.0 * 1000))',
            'differentiate.table': diff_window_table,
            'count': self.time_precision_query('MIN(time)')
            + ', SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': self.time_precision_query('MIN(time)') + ', COUNT(*)',
            'min': self.time_precision_query('MIN(time)') + ', MIN(val_num)',
            'max': self.time_precision_query('MIN(time)') + ', MAX(val_num)',
            'on': self.time_precision_query('MIN(time)')
            + ', '
            + self.precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'on.order': 'ORDER BY time ASC',
            # 'duty_cycle': same query as 'on' under its more descriptive name - both accepted, kept in sync.
            'duty_cycle': self.time_precision_query('MIN(time)')
            + ', '
            + self.precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'duty_cycle.order': 'ORDER BY time ASC',
            'sum': self.time_precision_query('MIN(time)') + ', SUM(val_num)',
            'raw': self.time_precision_query('time') + ', val_num',
            'raw.order': 'ORDER BY time ASC',
            'raw.group': '',
        }
        if func not in queries:
            raise NotImplementedError

        order = '' if func + '.order' not in queries else queries[func + '.order']
        # (time - (time % :step)), not ROUND(time / :step): sqlite's integer
        # '/' floors while MariaDB's decimal '/' + ROUND() rounds half-up,
        # so the same data bucketed differently per backend. The modulo form
        # is exact integer math on both and keeps sqlite's historical floor
        # partitioning.
        group = 'GROUP BY (time - (time % :step))' if func + '.group' not in queries else queries[func + '.group']
        table = queries.get(func + '.table')
        logs = plugin._fetch_log(
            item, queries[func], start, end, step=step, count=count, group=group, order=order, table=table
        )
        native_tuples = plugin._native_cagg_series(func, logs['istart'], logs['iend'], logs['step'], logs['item'])
        if native_tuples:
            logs['tuples'] = native_tuples + logs['tuples']
        tuples = logs['tuples']

        # Append tuples by addition values (not for func differentiate)
        if func != 'differentiate':
            if tuples:
                if logs['istart'] > tuples[0][0]:
                    tuples[0] = (logs['istart'], tuples[0][1])
                if end != 'now':
                    tuples.append((logs['iend'], tuples[-1][1]))
            else:
                tuples = []
            item_change = plugin._timestamp(logs['item'].last_change())
            if item_change < logs['iend']:
                value = float(logs['item']())
                if item_change < logs['istart']:
                    tuples.append((logs['istart'], value))
                elif init:
                    tuples.append((item_change, value))
                if init:
                    tuples.append((logs['iend'], value))

        if expression['finalizer']:
            tuples = self.finalize(expression['finalizer'], tuples)

        result = {
            'cmd': 'series',
            'series': tuples,
            'sid': sid,
            'params': {
                'update': True,
                'item': item,
                'func': func,
                'start': logs['iend'],
                'end': end,
                'step': logs['step'],
                'sid': sid,
            },
            'update': plugin.shtime.add_seconds(plugin.shtime.now(), int(logs['step'] / 1000)),
        }
        plugin.logger.dbgmed(
            f'_series: {sid=}, {step=}, update={result["update"]}, delta={int(logs["step"] / 1000)}, now={plugin.shtime.now()}'
        )
        # self.logger.debug("_series: result={}".format(result))

        return result

    def single(self, func, start, end='now', item=None):
        """
        This function is not used by any other plugin but can be used in logics

        :param func:
        :param start:
        :param end:
        :param item:
        :return:
        """
        plugin = self._plugin
        func, expression = self.expression(func)
        queries = {
            'avg': self.precision_query('AVG(val_num * duration) / AVG(duration)'),
            'integrate': 'SUM(val_num * duration)',
            'count': 'SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': 'COUNT(*)',
            'min': 'MIN(val_num)',
            'max': 'MAX(val_num)',
            'diff': 'MAX(val_num) - MIN(val_num)',
            'on': self.precision_query('SUM(val_bool * duration) / SUM(duration)'),
            # 'duty_cycle': same query as 'on' under its more descriptive name - both accepted, kept in sync.
            'duty_cycle': self.precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'sum': 'SUM(val_num)',
            'raw': 'val_num',
            'raw.order': 'ORDER BY time DESC',
            'raw.group': '',
        }
        if func not in queries:
            plugin.logger.warning('Unknown export function: {0}'.format(func))
            return
        native_result = plugin._native_cagg_single(func, start, end, item)
        if native_result is not None:
            return native_result[0]
        order = '' if func + '.order' not in queries else queries[func + '.order']
        logs = plugin._fetch_log(item, queries[func], start, end, order=order)
        # Every func here except 'raw' is an ungrouped SQL aggregate
        # (MIN/MAX/SUM/...), which always returns exactly one row - a NULL
        # one if nothing matched, not zero rows. 'raw' has no aggregate and
        # no GROUP BY (see 'raw.group': ''), so an empty range genuinely
        # returns zero rows there - _fetchall() then returns [], not None,
        # so an `is None` check alone let logs['tuples'][0][0] raise
        # IndexError instead of reporting "no data" like every other func.
        if not logs['tuples']:
            return None
        return logs['tuples'][0][0]

    def native_cagg_view(self, item):
        """Resolve *item* to its native-mode cagg's table name, or None if
        not covered - native mode inactive, or this item isn't one
        _enable_timescale_native_aggregation() actually built a cagg for
        (mirrors that method's own item-selection exactly: must be in
        _native_relevant_items(), action must not resolve to 'delete')."""
        plugin = self._plugin
        if not plugin._timescale_native_aggregation:
            return None
        if item not in plugin._maxage.native_relevant_items():
            return None
        if plugin._maxage.action_for(item) == 'delete':
            return None
        interval_ms = plugin._maxage.interval_seconds_for(item) * 1000
        return f'{plugin._replace["log"]}_cagg_{interval_ms // 1000}s'

    def item_for_id(self, item_id):
        """Resolve a database item_id back to its live Item object, cached.

        readLogCount() only ever receives a raw id, not the item _single()/
        _series() get directly, and native-mode cagg routing needs the real
        item to check coverage. Cached permanently - an item's own database
        id never changes once assigned, so there is no staleness to worry
        about, only a one-time DB round-trip per id across this instance's
        whole lifetime.
        """
        plugin = self._plugin
        if item_id in plugin._item_by_id_cache:
            return plugin._item_by_id_cache[item_id]
        result = plugin._fetchall('SELECT name FROM {item} WHERE id=:id;', {'id': item_id})
        item = plugin.items.return_item(result[0][0]) if result else None
        plugin._item_by_id_cache[item_id] = item
        return item

    def native_cagg_single(self, func, start, end, item):
        """_single()'s native-mode cagg path - deliberately narrow: only
        handles the case where the *entire* [start, end) range predates the
        raw floor (native retention has already dropped raw data for all of
        it), so there is no straddling raw/cagg-only boundary to stitch
        together. Any range that still overlaps raw-covered data falls
        through to the normal, precise raw-log path unchanged - a real,
        documented limitation (see timescale_native_aggregation's known
        limitations), not silently approximated.

        :returns: 1-tuple wrapping the (possibly None) result if this range
            was handled via the cagg; bare None if not applicable at all -
            the caller must fall through to the normal raw-log path in that
            case, not treat it as "no data".
        """
        plugin = self._plugin
        expr = self._NATIVE_CAGG_SINGLE_EXPR.get(func)
        if expr is None:
            return None
        _item = plugin.items.return_item(item)
        cagg_name = self.native_cagg_view(_item)
        if cagg_name is None:
            return None
        item_id = plugin.id(_item, create=False)
        if item_id is None:
            return None
        oldest = plugin._log_store.oldest_time(item_id)
        if oldest is None:
            # No raw data at all (never logged, or a genuinely empty item) -
            # let the normal path report "no data" the same way it always has.
            return None
        istart = self.parse_ts(start)
        iend = self.parse_ts(end)
        if iend > oldest:
            return None  # touches still-raw territory - use the precise raw path, not a coarser cagg stitch
        if func in self._NATIVE_CAGG_SINGLE_PRECISION_FUNCS:
            expr = self.precision_query(expr)
        result = plugin._fetchall(
            f'SELECT {expr} FROM {cagg_name} WHERE item_id=:id AND bucket >= :time_start AND bucket < :time_end;',
            {'id': item_id, 'time_start': istart, 'time_end': iend},
        )
        if not result:
            return (None,)
        return (result[0][0],)

    def native_cagg_series(self, func, istart, iend, step, item):
        """_series()'s native-mode cagg supplement - covers whatever portion
        of [istart, iend) predates the raw floor, re-bucketed to the
        caller's own :step width via the same modulo-regroup _series()
        already uses for raw data (`bucket - (bucket % :step)` instead of
        `time - (time % :step)`). Reuses _NATIVE_CAGG_SINGLE_EXPR - valid
        per-bucket here for the same reason it's valid for _single()'s
        whole-range case: SUM-of-SUMs/MIN-of-MINs/MAX-of-MAXs compose
        correctly across a re-partition into wider buckets.

        A :step finer than the cagg's own interval_ms needs no special
        case: each existing cagg row still lands in its own sub-bucket via
        plain GROUP BY, which never synthesizes an empty-bucket row -
        confirmed live to behave identically to how a plain raw-log query
        already handles a step finer than the actual data density (sparse,
        real rows only, no interpolation, no error).

        Takes istart/iend/step/item already resolved by the caller's own
        _fetch_log() call (not start/end/item as given by the user) so
        _fetch_log() itself stays completely unchanged - this only
        prepends extra tuples to its result, on the same istart/iend/step
        basis it already used for the raw portion.

        :returns: list of (bucket, value) tuples for the cagg-covered
            portion, to prepend to _fetch_log()'s own tuples; None if not
            applicable at all (not native mode, item not covered, func has
            no cagg column, or nothing in this range predates the raw
            floor) - the caller then uses today's raw-only result unchanged.
        """
        plugin = self._plugin
        expr = self._NATIVE_CAGG_SINGLE_EXPR.get(func)
        if expr is None or not step or step <= 0:
            return None
        cagg_name = self.native_cagg_view(item)
        if cagg_name is None:
            return None
        item_id = plugin.id(item, create=False)
        if item_id is None:
            return None
        oldest = plugin._log_store.oldest_time(item_id)
        if oldest is None:
            return None
        cagg_end = min(iend, oldest)
        if istart >= cagg_end:
            return None  # nothing in this range predates the raw floor
        if func in self._NATIVE_CAGG_SINGLE_PRECISION_FUNCS:
            expr = self.precision_query(expr)
        result = plugin._fetchall(
            f'SELECT (bucket - (bucket % :step)) AS out_bucket, {expr} FROM {cagg_name} '
            'WHERE item_id=:id AND bucket >= :time_start AND bucket < :time_end '
            'GROUP BY out_bucket ORDER BY out_bucket;',
            {'id': item_id, 'time_start': istart, 'time_end': cagg_end, 'step': step},
        )
        if not result:
            return None
        return [(row[0], row[1]) for row in result]

    def native_cagg_count(self, item, item_id, time_start, time_end):
        """readLogCount()'s native-mode cagg supplement - adds
        SUM(countall_value) from the cagg for whatever portion of
        [time_start, time_end] predates the raw floor, on top of the
        caller's own already-computed raw COUNT(*). Purely additive: the
        raw count already correctly reflects only the rows actually still
        present, needs no clipping.

        :returns: cagg-side row count (int, possibly 0) if applicable;
            None if not applicable at all (not native mode, item not
            covered, or the whole requested range is already raw-covered)
            - the caller then uses its raw-only count unchanged.
        """
        plugin = self._plugin
        cagg_name = self.native_cagg_view(item)
        if cagg_name is None:
            return None
        oldest = plugin._log_store.oldest_time(item_id)
        if oldest is None:
            return None
        if time_start is not None and time_start >= oldest:
            return None  # whole requested range is already raw-covered
        cagg_end = oldest if time_end is None else min(time_end, oldest)
        where = 'item_id=:id AND bucket < :time_end'
        params = {'id': item_id, 'time_end': cagg_end}
        if time_start is not None:
            where += ' AND bucket >= :time_start'
            params['time_start'] = time_start
        result = plugin._fetchall(f'SELECT SUM(countall_value) FROM {cagg_name} WHERE {where};', params)
        if not result or result[0][0] is None:
            return 0
        return int(result[0][0])

    def expression(self, func):
        expression = {'params': {'op': '!=', 'value': '0'}, 'finalizer': None}
        if ':' in func:
            expression['finalizer'] = func[: func.index(':')]
            func = func[func.index(':') + 1 :]
        if func == 'count' or func.startswith('count'):
            parts = re.match(r'(count)((<>|!=|<|=|>)(\d+))?', func)
            func = 'count'
            if parts and parts.group(3) is not None:
                expression['params']['op'] = parts.group(3)
            if parts and parts.group(4) is not None:
                expression['params']['value'] = parts.group(4)
        return func, expression

    def finalize(self, func, tuples):
        if func == 'diff':
            final_tuples = []
            for i in range(1, len(tuples) - 1):
                final_tuples.append((tuples[i][0], tuples[i][1] - tuples[i - 1][1]))
            return final_tuples
        else:
            return tuples

    def precision_query(self, query):
        plugin = self._plugin
        if plugin._precision >= 0:
            # CAST(... AS DECIMAL(30,10)), not a bare ROUND(double precision, integer) - PostgreSQL has
            # no such overload (only ROUND(numeric, integer)), and AVG()/SUM() over real/bigint columns
            # produce double precision. DECIMAL, not NUMERIC - MariaDB rejects NUMERIC as a CAST target
            # (DECIMAL is the one spelling all three backends accept). (30,10): generous headroom for
            # val_num*duration without overflow, well past double precision's own ~15-17 significant
            # digits, so nothing meaningful is lost before the final ROUND to self._precision.
            return 'ROUND(CAST({} AS DECIMAL(30,10)), {})'.format(query, plugin._precision)
        return query

    def time_precision_query(self, query):
        plugin = self._plugin
        if plugin._time_precision < 3:
            return 'ROUND({}, {})'.format(query, plugin._time_precision - 3)
        return query

    def fetch_log_base_where(self):
        """The WHERE clause shared by every _fetch_log() query: item/quality
        filtering plus the one-row-before-:time_start lookback that lets a
        row spanning into the requested range still contribute its
        duration. Factored out so a caller building its own subquery (e.g.
        _series()'s diff/differentiate window-function subquery) can apply
        the identical filter instead of duplicating it.
        """
        return (
            'item_id = :id AND '
            '(val_quality IS NULL OR val_quality = 0) AND '
            'time >= (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start) AND '
            'time <= :time_end AND '
            'time + duration_now > (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start)'
        )

    def fetch_log(self, item, columns, start, end, step=None, count=100, group='', order='', table=None):
        plugin = self._plugin
        _item = plugin.items.return_item(item)

        istart = self.parse_ts(start)
        iend = self.parse_ts(end)
        inow = self.parse_ts('now')
        id = plugin.id(_item, create=False)

        if inow > iend:
            inow = iend

        if step is None:
            if count != 0:
                step = int((iend - istart) / int(count))
            else:
                step = iend - istart

        if plugin._buffer_mgr.pending_count(_item):
            plugin._dump(items=[_item])

        params = {'id': id, 'time_start': istart, 'time_end': iend, 'inow': inow, 'step': step}
        duration_now = 'COALESCE(duration, :inow - time)'

        # Duration calculation (S=Start, E=End):
        duration = (
            '('
            #    ----------|<--------------------------->|---------->
            # 1. Duration for items within the given start/end range
            #    -----------------[S]======[E]---------------------->
            'COALESCE(duration * (time >= :time_start) * (time + duration <= :time_end), 0) + '
            # 2. Duration for items partially before start but ends after start
            #    -----[S]======[E]---------------------------------->
            'COALESCE(duration / duration * (time + duration - :time_start) * (time < :time_start) * (time + duration >= :time_start), 0) + '
            #    ----------------------------------[S]======[E]----->
            # 3. Duration for items partially after end but starts before end
            'COALESCE(duration_now / duration_now * (:time_end - time) * (time + duration_now >= :time_end), 0)'
            ')'
        )

        # Replace duration fields with calculated durations from previous
        # generated expressions to include all three cases.
        columns = columns.replace('duration', duration)

        # Create base query including the replaced columns
        # val_quality != 0 rows (no-data gaps) are excluded entirely - not
        # just their value (NULL propagation already skips that in e.g.
        # AVG(val_num*duration)) but their duration too, since otherwise a
        # gap's duration would still count in a denominator like
        # AVG(duration) while its value silently drops out of the
        # numerator, skewing the result instead of the gap contributing
        # nothing as intended.
        base_where = self.fetch_log_base_where()
        if table is None:
            # Default shape: aggregate columns select directly off {log}.
            query = 'SELECT ' + columns + ' FROM {log} WHERE ' + base_where + ' ' + group + ' ' + order
        else:
            # table is a caller-built "(SELECT ... FROM {log} WHERE ...) alias"
            # subquery (e.g. one computing a window function per raw row) -
            # the caller is responsible for applying base_where itself inside
            # that subquery; columns/group/order here then operate on the
            # subquery's already-filtered, already-windowed output rows.
            query = 'SELECT ' + columns + ' FROM ' + table + ' ' + group + ' ' + order

        # Replace duration_now with value from start time til current time to
        # get a duration value referring to the current timestamp - if required.
        query = query.replace('duration_now', duration_now)

        logs = plugin._fetchall(query, params)
        if logs:
            # MariaDB/MySQL return Decimal (not float) for SUM()/AVG() over
            # exact-numeric columns - e.g. 'on''s SUM(val_bool * duration),
            # both integer-typed columns (val_num's own aggregates stay
            # DOUBLE/float, since it's an approximate-numeric column;
            # sqlite never returns Decimal at all). Decimal arithmetic
            # doesn't mix with float - _finalize()'s 'diff' subtracts
            # adjacent tuple values directly, and _series() injects plain
            # float boundary values via float(item()), so a Decimal row
            # next to a float one would raise TypeError. Coercing here, at
            # the single choke point both _series() and _single() read
            # through, avoids the driver-dependent type difference
            # entirely rather than patching each affected func downstream.
            logs = [tuple(float(v) if isinstance(v, decimal.Decimal) else v for v in row) for row in logs]

        return {'tuples': logs, 'item': _item, 'istart': istart, 'iend': iend, 'step': step, 'count': count}

    def parse_ts(self, dts):
        """
        Parse a duration-timestamp in the form '1w 2y 3h 1d 39i 15s' and return the duration in seconds as
        an integer value

        :return:
        """
        plugin = self._plugin
        ts = plugin._timestamp(plugin.shtime.now())
        try:
            return min(ts, int(dts))  # rts, if dts is an integer value, return now, if dts is a timestamp in th future
        except (TypeError, ValueError):
            pass

        duration = 0
        if isinstance(dts, str):
            if dts == 'now':
                duration = 0
            else:
                for frame in dts.split(' '):
                    if frame != 'now':
                        duration += self.parse_single(frame)

        if duration < 0:
            duration = 0

        ts = ts - int(duration)
        return ts

    def parse_single(self, frame):
        """
        Parse one frame of a duration-timestamp to a duration (in seconds)

        :param frame:
        :return:
        """
        plugin = self._plugin
        second = 1000
        minute = 60 * 1000
        hour = 60 * minute
        day = 24 * hour
        week = 7 * day
        month = 30 * day
        year = 365 * day

        _frames = {'s': second, 'i': minute, 'h': hour, 'd': day, 'w': week, 'm': month, 'y': year}
        try:
            return int(frame)
        except (TypeError, ValueError):
            pass
        ts = plugin._timestamp(plugin.shtime.now())
        # if frame == 'now':
        #     fac = 0
        #     frame = 0
        if frame[-1] in _frames:
            fac = _frames[frame[-1]]
            frame = frame[:-1]
        else:
            # return parameter unchaned
            return frame
        try:
            ts = int(float(frame) * fac)
        except (TypeError, ValueError):
            plugin.logger.warning("Database: Unknown time frame '{0}'".format(frame))
        return ts
