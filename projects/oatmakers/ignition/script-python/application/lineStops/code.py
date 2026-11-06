"""Line stops: speed, temperature and production from the line tags' history."""
import time
from java.lang import Exception as JavaException
from java.util.concurrent.locks import ReentrantLock

TAG_ROOT = '[default]OatmakersDemo'
LINES = (1, 2, 3)
# A line below this share of its nominal output for longer than STOP_MINUTES
# has an unplanned stop. A 5-minute changeover stays below the limit.
STOP_BELOW_PCT = 50.0
STOP_MINUTES = 10
MAX_RANGE_DAYS = 7
HISTORY_DAYS = 7
_cache = {}
_lock = ReentrantLock()


def _path(line, name):
	return '{0}/Line{1}/{2}'.format(TAG_ROOT, line, name)


# The tags record one row per minute at most. Before they existed, and while
# the gateway was down, the minute samples of the simulation fill the gaps, so
# the history reaches back HISTORY_DAYS from the first start.
_BACKFILL = """INSERT INTO tsdb_data (time, tag_id, value_double, value_string, quality)
SELECT m.ms, t.id,
 CASE t.name WHEN 'SpeedPct' THEN round(s.total_kg / l.nominal_kg_min * 100, 3) WHEN 'Temperature' THEN s.temperature END,
 CASE t.name WHEN 'Producing' THEN CASE WHEN s.total_kg > 0 THEN 'true' ELSE 'false' END END,
 192
FROM (SELECT te.id, split_part(te.tag_path, '/', 3) AS name, substr(split_part(te.tag_path, '/', 2), 5)::integer AS line
	FROM tsdb_te te JOIN tsdb_drv d ON d.id = te.driver_id
	WHERE d.provider = 'default' AND te.retired IS NULL
	AND te.tag_path ~ '^OatmakersDemo/Line[123]/(SpeedPct|Temperature|Producing)$') t
JOIN oat_demo.sample s ON s.line_id = t.line
JOIN oat_demo.line l ON l.id = s.line_id
CROSS JOIN LATERAL (SELECT (extract(epoch FROM s.at) * 1000)::bigint AS ms) m
WHERE s.at >= greatest(now() - make_interval(days => ?), to_timestamp(? / 1000.0))
AND s.at < now() - interval '2 minutes'
AND NOT EXISTS (SELECT 1 FROM tsdb_data x WHERE x.tag_id = t.id AND x.time > m.ms - 60000 AND x.time < m.ms + 60000)"""
_checkedTo = [0]


def backfillHistory():
	"""Fill the line tags' history gaps from the minute samples. Called every minute."""
	try:
		since = max(0, _checkedTo[0] - 15 * 60 * 1000)
		now = system.date.toMillis(system.date.now())
		inserted = system.db.runPrepUpdate(_BACKFILL, [HISTORY_DAYS, since], application.demo.DATABASE)
		_checkedTo[0] = now
		if inserted:
			system.util.getLogger('Oatmakers.LineStops').info('Filled {0} history rows from the minute samples'.format(inserted))
	except (Exception, JavaException) as exc:
		# The historian creates its tables when the first tag records; until then there is nothing to fill.
		system.util.getLogger('Oatmakers.LineStops').debug('History backfill skipped: {0}'.format(exc))


def stopPeriods(samples, end):
	"""Periods in which one line stays below STOP_BELOW_PCT for more than STOP_MINUTES.

	samples: (epochMs, speedPct) sorted by time; each value holds until the next.
	A period still open at end counts when it is long enough already.
	"""
	periods, start = [], None
	for ts, value in list(samples) + [(end, None)]:
		low = value is not None and value < STOP_BELOW_PCT
		if low and start is None:
			start = ts
		elif not low and start is not None:
			if ts - start > STOP_MINUTES * 60 * 1000:
				periods.append((start, ts))
			start = None
	return periods


def _merge(periods):
	merged = []
	for start, end in sorted(periods):
		if merged and start <= merged[-1][1]:
			merged[-1] = (merged[-1][0], max(merged[-1][1], end))
		else:
			merged.append((start, end))
	return merged


def _raw(paths, start, end):
	"""Recorded rows per path as (epochMs, value), oldest first."""
	data = system.historian.queryRawPoints(paths, system.date.fromMillis(start), system.date.fromMillis(end), returnFormat='Tall')
	rows = dict((path, []) for path in paths)
	for i in range(data.getRowCount()):
		# The historian answers with prov:default:/tag:OatmakersDemo/Line1/SpeedPct.
		tag = str(data.getValueAt(i, 'path')).split('/tag:')[-1].lower()
		key = next((p for p in paths if p.split(']')[-1].lower() == tag), None)
		if key is not None:
			rows[key].append((system.date.toMillis(data.getValueAt(i, 'timestamp')), data.getValueAt(i, 'value')))
	for values in rows.values():
		values.sort(key=lambda row: row[0])
	return rows


def _averaged(name, start, end):
	paths = [_path(line, name) for line in LINES]
	data = system.historian.queryAggregatedPoints(paths, system.date.fromMillis(start), system.date.fromMillis(end),
		aggregates=['Average'] * len(paths), returnSize=600, returnFormat='Wide')
	points = []
	for i in range(data.getRowCount()):
		point = {'ts': system.date.toMillis(data.getValueAt(i, 0))}
		for line in LINES:
			value = data.getValueAt(i, line)
			point['line{0}'.format(line)] = None if value is None else round(float(value), 2)
		points.append(point)
	return points


def _producing(rows, start, end):
	"""0/1 steps: the state at the window start, every change as two points with
	the same time (old value, then new value), and the state at the window end."""
	points = []
	for line in LINES:
		key = 'line{0}'.format(line)
		states = [(ts, 1 if str(value).lower() in ('true', '1') else 0) for ts, value in rows[_path(line, 'Producing')]]
		before = [on for ts, on in states if ts <= start]
		state = before[-1] if before else (states[0][1] if states else None)
		if state is None:
			continue
		points.append({'ts': start, key: state})
		for ts, on in states:
			if start < ts <= end and on != state:
				points.extend([{'ts': ts, key: state}, {'ts': ts, key: on}])
				state = on
		points.append({'ts': end, key: state})
	points.sort(key=lambda p: p['ts'])
	return points


def _speed(start, end, periods):
	"""Averaged speed rows carrying the at-speed band (low/high) and the red stops
	(stop = 120 inside a stop, 0 outside). A 0 row one second before and after
	each stop keeps its edges vertical."""
	rows = _averaged('SpeedPct', start, end)
	shown = [(max(b, start) // 1000 * 1000, min(e, end) // 1000 * 1000) for b, e in periods if e > start and b < end]
	for b, e in shown:
		rows.extend([{'ts': b - 1000}, {'ts': b}, {'ts': e}, {'ts': e + 1000}])
	rows.sort(key=lambda r: r['ts'])
	for row in rows:
		row.update({'low': 80, 'high': 100})
		row['stop'] = 120 if any(b <= row['ts'] <= e for b, e in shown) else 0
	return rows


def trend(start, end):
	"""Data for the three Line stops charts over one picker range."""
	if not start or not end or long(end) <= long(start):
		return {'speed': [], 'temperature': [], 'producing': [], 'message': 'Choose a date and time range.'}
	start, end = long(start), long(end)
	if end - start > MAX_RANGE_DAYS * 86400000:
		return {'speed': [], 'temperature': [], 'producing': [], 'message': 'Choose a range of at most 7 days.'}
	key = (start // 30000, end // 30000)
	_lock.lock()
	try:
		cached = _cache.get(key)
		if cached and time.time() - cached[0] < 30:
			return cached[1]
	finally:
		_lock.unlock()
	try:
		paths = [_path(line, name) for line in LINES for name in ('SpeedPct', 'Producing')]
		rows = _raw(paths, start - 3600000, end)
		periods = []
		for line in LINES:
			samples = [(ts, None if v is None else float(v)) for ts, v in rows[_path(line, 'SpeedPct')]]
			periods.extend(stopPeriods(samples, end))
		periods = _merge(periods)
		result = {'speed': _speed(start, end, periods), 'temperature': _averaged('Temperature', start, end),
			'producing': _producing(rows, start, end),
			'message': '{0} unplanned stops in this range'.format(len([p for p in periods if p[1] > start and p[0] < end]))}
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.LineStops').warn('Line stops query failed: {0}'.format(exc))
		return {'speed': [], 'temperature': [], 'producing': [], 'message': 'Line history unavailable.'}
	_lock.lock()
	try:
		if len(_cache) > 64:
			_cache.clear()
		_cache[key] = (time.time(), result)
	finally:
		_lock.unlock()
	return result
