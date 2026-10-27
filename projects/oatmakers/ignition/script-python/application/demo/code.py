"""Customer demonstration services. All writes are confined to oat_demo."""
import re
import time
from java.util import UUID
from java.lang import Exception as JavaException
from java.util.concurrent.locks import ReentrantLock

DATABASE = 'OatmakersDemo'
REVISION = 'showroom-4.4.4'
_cache = {}
_lock = ReentrantLock()


def _queryJson(sql, args=None):
	rows = system.db.runPrepQuery(sql, args or [], DATABASE)
	return system.util.jsonDecode(unicode(rows[0][0]))


def tick():
	try:
		_queryJson('SELECT oat_demo.tick_live()')
		_writeLiveTags(_queryJson('SELECT oat_demo.live_overview()'))
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').error('Demo continuity tick failed: {0}'.format(exc))
	try:
		_writeScadaTags()
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').error('SCADA tag simulation failed: {0}'.format(exc))


def health():
	try:
		result = _queryJson('SELECT oat_demo.health_live()')
		result['appRevision'] = REVISION
		return result
	except (Exception, JavaException):
		return {'ok': False, 'simulation': True, 'appRevision': REVISION,
			'message': 'Demo database unavailable. Inspect gateway connection OatmakersDemo.'}


def _empty(message):
	return {'ready': False, 'stale': True, 'simulated': True, 'message': message,
		'metrics': [], 'lines': [], 'trend': [], 'orders': [], 'planning': [], 'events': [],
		'losses': [], 'quality': [], 'batchOptions': [],
		'selectedBatch': {'reference': 'No batch available', 'product': '', 'quality': 'Awaiting data'},
		'inspection': {}, 'submissions': [], 'clock': '', 'window': '', 'health': {'ok': False, 'ageSeconds': 'n/a', 'coverageDays': 'n/a', 'lineCount': 'n/a', 'sampleCount': 'n/a'},
		'availability': 'n/a', 'performance': 'n/a', 'yield': 'n/a'}


def snapshot(scene='live', period='day', line=0, batch=''):
	key = (str(scene), str(period), int(line or 0), str(batch or ''))
	if key[0] not in ('live', 'stoppage', 'quality', 'recovery'):
		raise ValueError('Unknown scenario')
	if key[1] not in ('shift', 'day', 'week', 'month') or key[2] not in (0, 1, 2, 3):
		raise ValueError('Unknown filter')
	_lock.lock()
	try:
		now = time.time()
		cached = _cache.get(key)
		if cached and now-cached[0] < 8:
			return cached[1]
		try:
			result = _queryJson('SELECT oat_demo.snapshot(?, ?, ?, ?)', list(key))
			if not result.get('ready'):
				result = _empty(result.get('message', 'Preparing demonstration history.'))
			for line_data in result.get('lines', []):
				line_data['lineNumber'] = line_data.pop('id')
			result['orders'] = list(result.get('orders', []))
			result['submissions'] = recentOrders()
			result['appRevision'] = REVISION
		except (Exception, JavaException) as exc:
			system.util.getLogger('Oatmakers.Demo').warn('Demo snapshot unavailable: {0}'.format(exc))
			result = _empty('Demo data is temporarily unavailable. Check Demo health for connection status.')
		if len(_cache) > 128:
			_cache.clear()
		_cache[key] = (now, result)
		return result
	finally:
		_lock.unlock()


def recentOrders():
	return _queryJson("""SELECT coalesce(jsonb_agg(to_jsonb(x)), '[]') FROM (
		SELECT reference,product,quantity_kg,bags,mode,source,
		to_char(created_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') AS submitted
		FROM oat_demo.operator_order ORDER BY created_at DESC LIMIT 100) x""")


def validateOrder(values):
	checks = {
		'reference': common.validation.input.validateTextInput(values.get('reference'), required=True),
		'product': common.validation.input.validateDropdownInput(values.get('product'), required=True,
			allowedValues=['Rolled oats', 'Steel-cut oats', 'Oat flour']),
		'quantity': common.validation.input.validateNumericInput(values.get('quantity'), negativeAllowed=False, decimalAllowed=True, required=True),
		'bags': common.validation.input.validateNumericInput(values.get('bags'), negativeAllowed=False, decimalAllowed=False, required=True),
		'mode': common.validation.input.validateDropdownInput(values.get('mode'), required=True, allowedValues=['Trial', 'Production', 'Hold'])
	}
	errors = dict((k, v['errorMessage']) for k, v in checks.items() if v['errorMessage'])
	clean = dict((k, v['validatedOutput']) for k, v in checks.items())
	if clean['reference'] and len(clean['reference']) > 40:
		errors['reference'] = 'Use at most 40 characters.'
	if clean['quantity'] is not None and not 0 < clean['quantity'] <= 100000:
		errors['quantity'] = 'Planned quantity must be above 0 and at most 100,000 kg.'
	if clean['bags'] is not None and not 0 < clean['bags'] <= 10000:
		errors['bags'] = 'Planned bags must be between 1 and 10,000.'
	return {'valid': not bool(errors), 'errors': errors, 'values': clean,
		'message': '' if not errors else ' '.join(errors[k] for k in sorted(errors))}


def createOrder(values, requestId):
	validation = validateOrder(values)
	if not validation['valid']:
		raise ValueError(validation['message'])
	requestId = str(UUID.fromString(str(requestId)))
	v = validation['values']
	# The unique request ID makes repeat clicks and retried requests idempotent.
	result = _queryJson("""WITH inserted AS (
		INSERT INTO oat_demo.operator_order(request_id,reference,product,quantity_kg,bags,mode)
		SELECT CAST(? AS uuid),?,?,?,?,?
		WHERE (SELECT count(*) FROM oat_demo.operator_order WHERE created_at>now()-interval '1 minute')<60
		ON CONFLICT(request_id) DO NOTHING RETURNING reference
	) SELECT jsonb_build_object('created',EXISTS(SELECT 1 FROM inserted),
		'exists',EXISTS(SELECT 1 FROM oat_demo.operator_order WHERE request_id=CAST(? AS uuid) AND reference=? AND product=? AND quantity_kg=? AND bags=? AND mode=?))""",
		[requestId,v['reference'],v['product'],v['quantity'],v['bags'],v['mode'],requestId,v['reference'],v['product'],v['quantity'],v['bags'],v['mode']])
	if not result['created'] and not result['exists']:
		raise ValueError('Demo is busy. Try again in one minute.')
	_lock.lock()
	try:
		_cache.clear()
	finally:
		_lock.unlock()
	return 'Production order {0} created.'.format(v['reference'])


def recordInspection(reference):
	batch = batchDetails(reference)
	if not reference or not batch.get('available') or batch.get('status') == 'Scheduled':
		raise ValueError('Select a recorded production batch before recording its check.')
	saved = _queryJson("""WITH saved AS (
		INSERT INTO oat_demo.inspection(batch_reference,decision,peak_moisture,temperature)
		VALUES(?,?,?,?) ON CONFLICT(batch_reference) DO NOTHING RETURNING decision
	) SELECT jsonb_build_object('decision',coalesce((SELECT decision FROM saved),(SELECT decision FROM oat_demo.inspection WHERE batch_reference=?)))""",
		[str(reference), batch['quality'], batch['peak_moisture'], batch['temperature'],str(reference)])
	_lock.lock()
	try:
		_cache.clear()
	finally:
		_lock.unlock()
	return 'Demo inspection recorded for {0}: {1}.'.format(reference, saved['decision'])


def newRequestId():
	return str(UUID.randomUUID())

# Live SCADA and explicit range services for the Mustry UI screens.
TAG_ROOT = '[default]OatmakersDemo'
METRICS = {
	'rate': ('Throughput', 'Throughput', 'kg/h'),
	'temperature': ('Temperature', 'Temperature', u'\u00b0C'),
	'moisture': ('Moisture', 'Moisture', '%'),
	'pressure': ('Pressure', 'Pressure', 'bar'),
	'power': ('Power', 'Power', 'kW')
}


def _cachedQuery(key, ttl, sql, args):
	_lock.lock()
	try:
		now = time.time()
		cached = _cache.get(key)
		if cached and now-cached[0] < ttl:
			return cached[1]
		result = _queryJson(sql, args)
		if len(_cache) > 128:
			_cache.clear()
		_cache[key] = (now, result)
		return result
	finally:
		_lock.unlock()


def live(line=0):
	try:
		return _cachedQuery(('live5', int(line or 0)), 0.4, 'SELECT oat_demo.live_overview(?)', [int(line or 0)])
	except (Exception, JavaException):
		return {'ready': False, 'updatedEpochMs': 0, 'updatedAt': 'Unavailable',
			'lines': [], 'metrics': [], 'trend': [], 'shiftStart': ''}


def history(start, end, line=0, metric='rate'):
	if not start or not end or long(end) <= long(start):
		return {'points': [], 'count': 0, 'message': 'Choose a date and time range.'}
	if metric not in METRICS:
		raise ValueError('Unknown measurement')
	try:
		args = [long(start), long(end), int(line or 0), str(metric)]
		return _cachedQuery(('history4',)+tuple(args), 5, 'SELECT oat_demo.history_range(CAST(? AS bigint), CAST(? AS bigint), ?, ?)', args)
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').warn('History query failed: {0}'.format(exc))
		return {'points': [], 'count': 0, 'message': 'History unavailable. Choose a recorded range within 90 days.'}


def scadaSetpoint(line, metric):
	# These are the nominal operating targets used by the demonstration model.
	# Power is consumption, so it deliberately has no control setpoint.
	if metric == 'rate':
		return (32.0, 25.0, 21.0)[int(line)-1] * 60
	return {'temperature': 82.0, 'moisture': 11.4, 'pressure': 2.4}.get(metric)


def scadaTrend(line, metric):
	end = system.date.toMillis(system.date.now())
	result = history(end - 15*60*1000, end, int(line), metric)
	points = []
	setpoint = scadaSetpoint(line, metric)
	limits = {'temperature': (55.0, 86.0), 'moisture': (10.5, 13.0)}.get(metric, (None, None))
	for point in result.get('points', []):
		points.append({'ts': point['ts'], 'pv': point.get('line' + str(int(line))), 'sp': setpoint, 'low': limits[0], 'high': limits[1]})
	return {'points': points, 'message': result.get('message', '')}


def rangeSnapshot(start, end, line=0):
	if not start or not end or long(end) <= long(start):
		return _empty('Choose a date and time range.')
	try:
		return _cachedQuery(('range4',long(start),long(end),int(line or 0)), 5,
			'SELECT oat_demo.snapshot_range(CAST(? AS bigint), CAST(? AS bigint), ?)', [long(start),long(end),int(line or 0)])
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').warn('Range query failed: {0}'.format(exc))
		return _empty('Recorded data is unavailable for this range.')


def batches(start, end, line=0):
	if not start or not end or long(end) <= long(start):
		return []
	try:
		return _cachedQuery(('batches4',long(start),long(end),int(line or 0)), 5,
			'SELECT oat_demo.batches_range(CAST(? AS bigint), CAST(? AS bigint), ?)', [long(start),long(end),int(line or 0)])
	except (Exception, JavaException):
		return []


def timeline(start, end):
	if not start or not end or long(end) <= long(start):
		return []
	try:
		rows = _cachedQuery(('timeline5',long(start),long(end)), 5,
			'SELECT oat_demo.timeline_range(CAST(? AS bigint), CAST(? AS bigint), ?)', [long(start),long(end),0])
	except (Exception, JavaException):
		return []
	return [dict(row, id=row['reference'],
		description='{0} / {1}'.format(row['line'], row.get('status') or row.get('title')))
		for row in rows]


def batchDetails(reference):
	if not reference:
		return {'available': False, 'reference': '', 'message': 'Select a batch to inspect its measurements.'}
	try:
		return _cachedQuery(('batch4',str(reference)), 5, 'SELECT oat_demo.batch_detail(?)', [str(reference)])
	except (Exception, JavaException):
		return {'available': False, 'reference': str(reference), 'message': 'This batch is unavailable.'}


def showBatch(reference):
	if not str(reference).startswith('OM-'):
		return   # a stop or changeover bar carries no batch record
	system.perspective.openPopup('batch-details', 'Popups/BatchDetails',
		params={'reference': str(reference)}, title='Batch details',
		position={'width': 920, 'height': 400}, modal=False, draggable=True, resizable=True)


def showHistory(line, metric):
	line = int(line)
	if line not in (1,2,3) or metric not in METRICS:
		raise ValueError('Unknown demonstration tag')
	name, title, _unit = METRICS[metric]
	system.perspective.openPopup('history-{0}-{1}'.format(line,metric), 'Popups/TagHistory',
		params={'lineNumber': line, 'metric': metric, 'title': title,
			'tagPath': '{0}/Line{1}/{2}'.format(TAG_ROOT,line,name)},
		title='Line {0} / {1}'.format(line,title), position={'width': 980, 'height': 620},
		modal=False, draggable=True, resizable=True)


def _writeLiveTags(data):
	if not data.get('ready'):
		return
	if not system.tag.exists(TAG_ROOT+'/SchemaVersion'):
		folders = []
		for line in (1,2,3):
			tags = [{'name': values[0], 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'Float8', 'value': 0.0} for values in METRICS.values()]
			tags.extend([{'name': 'State', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'String', 'value': 'Starting'},
				{'name': 'LastUpdate', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'DateTime', 'value': system.date.fromMillis(0)}])
			folders.append({'name': 'Line{0}'.format(line), 'tagType': 'Folder', 'tags': tags})
		folders.append({'name': 'SchemaVersion', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'String', 'value': '4'})
		qualities = system.tag.configure('[default]', [{'name':'OatmakersDemo','tagType':'Folder','tags':folders}], 'm')
		if any(not quality.isGood() for quality in qualities):
			raise ValueError('Could not initialize demo memory tags')
	paths, values = [], []
	for line in data['lines']:
		base = '{0}/Line{1}/'.format(TAG_ROOT,line['lineNumber'])
		for key, metadata in METRICS.items():
			paths.append(base+metadata[0]); values.append(float(line[key]))
		paths.extend([base+'State',base+'LastUpdate'])
		values.extend([line['state'],system.date.fromMillis(long(line['updatedEpochMs']))])
	qualities = system.tag.writeBlocking(paths, values)
	if any(not quality.isGood() for quality in qualities):
		raise ValueError('A demo tag write failed')


# Process SCADA. Each area has deterministic signals (base, amplitude, period in
# seconds); the production line areas take throughput, temperature, moisture,
# steam pressure and power from the recorded line telemetry. The timer writes
# them into the [default]OatMill UDT instances, which carry the signal name as
# a parameter; the screens bind to those tags. Read-only: no view writes plant
# tags or control setpoints.
SCADA = {
	'overview': {'title': 'Plant overview', 'line': 0, 'signals': {}},
	'intake': {'title': 'Intake & raw oat silos', 'line': 0, 'signals': {
		'intake': (32.0, 3.5, 47.0), 'moistIn': (13.6, 0.3, 83.0), 'elevAmps': (18.4, 1.1, 37.0), 'filterDp': (9.6, 0.6, 61.0),
		'lvl1': (78.0, 4.0, 900.0), 'lvl2': (61.0, 5.0, 1100.0), 'lvl3': (34.0, 6.0, 1300.0), 'lvl4': (88.0, 2.0, 700.0),
		'tg1': (14.2, 0.3, 301.0), 'tg2': (13.1, 0.3, 277.0), 'tg3': (15.4, 0.3, 263.0), 'tg4': (12.8, 0.3, 251.0)},
		'tile': [('Intake', 'intake', 't/h', 1), ('Silo SI101 level', 'lvl1', '%', 0), ('Grain moisture', 'moistIn', '%', 1)]},
	'cleaning': {'title': 'Cleaning', 'line': 0, 'signals': {
		'feed': (18.2, 0.6, 53.0), 'sieveAmps': (6.8, 0.3, 41.0), 'aspDp': (7.4, 0.4, 59.0), 'airFlow': (5200.0, 120.0, 71.0),
		'stonerAmps': (4.1, 0.2, 43.0), 'trieurSpeed': (42.0, 0.4, 67.0), 'rejects': (1.8, 0.25, 47.0), 'purity': (99.6, 0.08, 89.0)},
		'tile': [('Feed', 'feed', 't/h', 1), ('Purity', 'purity', '%', 1), ('Sorter rejects', 'rejects', '%', 1)]},
	'dehulling': {'title': 'Dehulling', 'line': 0, 'signals': {
		'feed': (16.8, 0.5, 53.0), 'rotorSpeed': (1480.0, 12.0, 41.0), 'hullerAmps': (62.0, 2.5, 37.0), 'aspDp': (8.1, 0.4, 59.0),
		'efficiency': (92.4, 0.8, 73.0), 'broken': (3.1, 0.3, 61.0), 'groats': (11.6, 0.4, 53.0), 'hulls': (4.9, 0.2, 53.0)},
		'tile': [('Feed', 'feed', 't/h', 1), ('Hulling efficiency', 'efficiency', '%', 1), ('Broken groats', 'broken', '%', 1)]},
	'kiln': {'title': 'Kilning & stabilisation', 'line': 0, 'signals': {
		'feed': (11.4, 0.3, 53.0), 'steamFlow': (820.0, 25.0, 47.0), 'steamPressure': (3.2, 0.05, 31.0),
		'kilnTop': (102.0, 0.8, 67.0), 'kilnMid': (98.5, 0.6, 61.0), 'kilnBottom': (96.2, 0.6, 57.0),
		'moisture': (9.6, 0.15, 89.0), 'coolerOut': (24.5, 0.6, 71.0)},
		'tile': [('Kiln temperature', 'kilnMid', u'°C', 1), ('Groat moisture', 'moisture', '%', 1), ('Steam', 'steamFlow', 'kg/h', 0)]},
	'flaking': {'title': u'Line 01 · Steaming & flaking', 'line': 1, 'flows': ('rollSpeed',), 'signals': {
		'rate': (1920.0, 60.0, 53.0), 'temperature': (82.0, 1.5, 61.0), 'moisture': (11.4, 0.2, 71.0), 'pressure': (2.4, 0.05, 31.0), 'power': (52.0, 2.0, 43.0),
		'rollGap': (0.62, 0.01, 97.0), 'rollSpeed': (310.0, 2.0, 43.0), 'dryerTemp': (96.0, 1.2, 71.0), 'coolerOut': (26.0, 0.6, 67.0)},
		'tile': [('Throughput', 'rate', 'kg/h', 0), ('Flake moisture', 'moisture', '%', 1), ('Steamer', 'temperature', u'°C', 1)]},
	'cutting': {'title': u'Line 02 · Groat cutting', 'line': 2, 'flows': ('drum1', 'drum2', 'oversize'), 'signals': {
		'rate': (1500.0, 50.0, 53.0), 'temperature': (82.0, 1.5, 61.0), 'moisture': (11.4, 0.2, 71.0), 'pressure': (2.4, 0.05, 31.0), 'power': (44.0, 2.0, 43.0),
		'drum1': (58.0, 0.5, 43.0), 'drum2': (58.0, 0.5, 47.0), 'oversize': (6.5, 0.5, 61.0), 'uniformity': (94.2, 0.6, 83.0)},
		'tile': [('Throughput', 'rate', 'kg/h', 0), ('Moisture', 'moisture', '%', 1), ('Cut uniformity', 'uniformity', '%', 1)]},
	'milling': {'title': u'Line 03 · Oat flour milling', 'line': 3, 'flows': ('millSpeed', 'pneuDp'), 'signals': {
		'rate': (1260.0, 40.0, 53.0), 'temperature': (82.0, 1.5, 61.0), 'moisture': (11.4, 0.2, 71.0), 'pressure': (2.4, 0.05, 31.0), 'power': (61.0, 2.0, 43.0),
		'millSpeed': (2950.0, 15.0, 41.0), 'pneuDp': (42.0, 2.0, 53.0), 'fineness': (212.0, 4.0, 79.0), 'branYield': (18.5, 0.6, 97.0)},
		'tile': [('Throughput', 'rate', 'kg/h', 0), ('Flour fineness', 'fineness', u'µm', 0), ('Mill power', 'power', 'kW', 0)]},
	'packing': {'title': 'Packing & palletising', 'line': 0, 'signals': {
		'lvlA': (64.0, 5.0, 800.0), 'lvlB': (47.0, 6.0, 900.0), 'lvlC': (72.0, 4.0, 700.0),
		'sackWeight': (25.04, 0.03, 31.0), 'sacksMin': (4.2, 0.2, 47.0), 'weightB': (1003.0, 1.5, 29.0), 'packsB': (48.0, 1.5, 41.0),
		'weightC': (502.1, 0.9, 29.0), 'packsC': (62.0, 1.8, 43.0), 'rejects': (0.6, 0.15, 61.0), 'pallets': (11.5, 0.4, 97.0)},
		'tile': [('Rolled oats', 'packsC', 'packs/min', 0), ('Steel-cut oats', 'packsB', 'packs/min', 0), ('Pallets', 'pallets', '/h', 1)]},
	'utilities': {'title': 'Steam & compressed air', 'line': 0, 'signals': {
		'boilerPressure': (10.2, 0.12, 37.0), 'steamTemp': (184.0, 1.0, 61.0), 'steamFlow': (3.4, 0.15, 47.0), 'drumLevel': (52.0, 2.5, 53.0),
		'gasFlow': (265.0, 9.0, 47.0), 'headerPressure': (3.5, 0.05, 31.0), 'feedLevel': (68.0, 3.0, 301.0),
		'airPressure': (7.2, 0.08, 29.0), 'dewPoint': (-40.5, 0.8, 97.0), 'compAmps': (96.0, 4.0, 41.0)},
		'tile': [('Steam header', 'headerPressure', 'bar', 2), ('Boiler', 'boilerPressure', 'bar', 1), ('Compressed air', 'airPressure', 'bar', 1)]},
}
SCADA_LIVE = ('rate', 'temperature', 'moisture', 'pressure', 'power')


def _scadaWave(signal, spec, seconds):
	import math
	base, amplitude, period = spec
	phase = sum(ord(c) for c in signal) % 17
	return base + amplitude * math.sin(seconds / period + phase) + amplitude * 0.2 * math.sin(seconds / max(3.1, period / 40.0) + phase)


def _scadaArea(area):
	if area not in SCADA:
		raise ValueError('Unknown process area')
	return SCADA[area]


def scadaAreaTitle(area):
	return _scadaArea(area)['title']


def _scadaSimulate(area):
	spec = _scadaArea(area)
	seconds = system.date.toMillis(system.date.now()) / 1000.0
	data = dict((key, _scadaWave(key, value, seconds)) for key, value in spec['signals'].items())
	data['running'] = True
	data['state'] = 'Running'
	if spec['line']:
		row = None
		for candidate in live().get('lines', []):
			if int(candidate.get('lineNumber', 0)) == spec['line']:
				row = candidate
		if row:
			state = row.get('state') or 'Running'
			for key in SCADA_LIVE:
				if row.get(key) is not None:
					data[key] = float(row[key])
			data['state'] = state
			data['running'] = state not in ('Stopped', 'Changeover')
			if not data['running']:
				for key in spec.get('flows', ()):
					data[key] = 0.0
	return data


# The SCADA graphics are Perspective drawings (ia.shapes.svg). Size-dependent
# outlines are written as SVG markup and converted to drawing elements here.
_SVG_TAG = re.compile(r'<(/?)(\w+)([^>]*?)(/?)>')
_SVG_ATTR = re.compile(r'([\w:-]+)="([^"]*)"')
_SVG_STYLE = {'fill': ('fill', 'paint'), 'fill-opacity': ('fill', 'opacity'), 'stroke': ('stroke', 'paint'),
	'stroke-width': ('stroke', 'width'), 'stroke-dasharray': ('stroke', 'dasharray'),
	'stroke-linejoin': ('stroke', 'linejoin'), 'stroke-linecap': ('stroke', 'linecap')}


def scadaElements(markup):
	root = []
	stack = [root]
	for closing, name, attrs, selfClosing in _SVG_TAG.findall(markup):
		if name == 'svg':
			continue
		if closing:
			stack.pop()
			continue
		element = {'type': 'group' if name == 'g' else name, 'name': '{0}{1}'.format(name, len(stack[-1]))}
		for key, value in _SVG_ATTR.findall(attrs):
			if key in _SVG_STYLE:
				section, prop = _SVG_STYLE[key]
				element.setdefault(section, {})[prop] = value
			elif not key.startswith('font') and key not in ('text-anchor', 'paint-order', 'xmlns'):
				element[key] = value
		stack[-1].append(element)
		if name == 'g' and not selfClosing:
			element['elements'] = []
			stack.append(element['elements'])
	return root


def _scadaFormat(value, unit, decimals):
	text = u'{0:,.{1}f}'.format(float(value or 0), int(decimals))
	return text + (u' ' + unit if unit else u'')


def scadaSiloLevel(level):
	# Path of the product inside the silo outline (110 x 330 design units).
	level = max(0.0, min(100.0, float(level or 0)))
	top = 6 + 314 * (1 - level / 100.0)
	if top <= 240:
		return 'M3 {0:.1f} H107 V240 L64 326 H46 L3 240 Z'.format(top)
	t = (top - 240) / 86.0
	return 'M{0:.1f} {1:.1f} H{2:.1f} L64 326 H46 Z'.format(3 + 43 * t, top, 107 - 43 * t)


def scadaTrendElements(tagPath, colour, setpoint):
	found = _scadaInstance(tagPath)
	if not found:
		return []
	area, _kind, params = found
	signal = params.get('Signal')
	spec = _scadaArea(area)
	end = system.date.toMillis(system.date.now())
	values = []
	if spec['line'] and signal in SCADA_LIVE:
		result = history(end - 3600 * 1000, end, spec['line'], signal)
		values = [float(p['line' + str(spec['line'])]) for p in result.get('points', []) if p.get('line' + str(spec['line'])) is not None]
	if len(values) < 2 and signal in spec['signals']:
		values = [_scadaWave(signal, spec['signals'][signal], end / 1000.0 - 600 + i * 5) for i in range(121)]
	if len(values) < 2:
		return []
	low, high = min(values), max(values)
	if setpoint:
		low, high = min(low, float(setpoint)), max(high, float(setpoint))
	spread = max(high - low, abs(high) * 0.02, 0.01)
	low, high = low - spread * 0.25, high + spread * 0.25
	step = 274.0 / (len(values) - 1)
	points = [(3 + i * step, 65 - (value - low) / (high - low) * 60) for i, value in enumerate(values)]
	elements = []
	if setpoint:
		y = 65 - (float(setpoint) - low) / (high - low) * 60
		elements.append({'type': 'path', 'name': 'Setpoint', 'd': 'M3 {0:.2f} H277'.format(y),
			'fill': {'paint': 'none'}, 'stroke': {'paint': '#73c9d9', 'width': 1, 'dasharray': '4 4'}})
	elements.append({'type': 'polyline', 'name': 'Value', 'points': ' '.join('{0:.2f},{1:.2f}'.format(x, y) for x, y in points),
		'fill': {'paint': 'none'}, 'stroke': {'paint': colour, 'width': 1}})
	elements.append({'type': 'circle', 'name': 'Now', 'cx': 277, 'cy': round(points[-1][1], 2), 'r': 2.2, 'fill': {'paint': '#df8074'}})
	return elements


def openFaceplate(udt, tagPath):
	if udt not in ('AnalogInput', 'Motor', 'Valve', 'Silo') or not _scadaInstance(tagPath):
		raise ValueError('Unknown SCADA tag')
	system.perspective.openPopup('faceplate', 'Popups/Faceplates/' + udt, params={'tagPath': tagPath},
		title=tagPath.split('/')[-1], position={'width': 760, 'height': 640}, modal=False, draggable=True, resizable=True)


SCADA_TAGS = '[default]OatMill'
_scadaIndex = [0.0, {}]


def _parameter(value):
	# A ParameterValue holds a QualifiedValue; unwrap both to the plain value.
	while hasattr(value, 'getValue'):
		value = value.getValue()
	return unicode(value) if isinstance(value, basestring) else value


def _scadaTagIndex():
	# (UDT, path, parameters) per area folder, refreshed every minute so new
	# instances are picked up without a restart.
	if _scadaIndex[1] and time.time() - _scadaIndex[0] < 60:
		return _scadaIndex[1]
	index = {}
	for folder in system.tag.getConfiguration(SCADA_TAGS, True)[0]['tags']:
		entries = []
		for tag in folder['tags']:
			if str(tag['tagType']) != 'UdtInstance':
				continue
			params = dict((str(key), _parameter(value)) for key, value in dict(tag['parameters']).items())
			entries.append((str(tag['typeId']).split('/')[-1], '{0}/{1}/{2}'.format(SCADA_TAGS, folder['name'], tag['name']), params))
		index[str(folder['name']).lower()] = entries
	_scadaIndex[0], _scadaIndex[1] = time.time(), index
	return index


def _scadaInstance(tagPath):
	# (area, UDT, parameters) of an OatMill instance path, or None.
	for area, entries in _scadaTagIndex().items():
		for kind, path, params in entries:
			if path == tagPath:
				return area, kind, params
	return None


def _writeScadaTags():
	import math
	paths, values = [], []
	now = system.date.now()
	seconds = system.date.toMillis(now) / 1000.0
	index = _scadaTagIndex()
	# Operator settings written from the faceplates: Mode (Auto, Hand, Off) and the valve position in Hand.
	settings = [path + member for entries in index.values() for kind, path, params in entries if kind in ('Motor', 'Valve')
		for member in (('/Mode', '/PositionSP') if kind == 'Valve' else ('/Mode',))]
	operator = dict(zip(settings, [qv.value for qv in system.tag.readBlocking(settings)])) if settings else {}
	for area, entries in index.items():
		if area not in SCADA:
			continue
		data = _scadaSimulate(area)
		running = data['running']
		for kind, path, params in entries:
			signal = params.get('Signal')
			if kind == 'AnalogInput' and signal in data:
				paths.append(path + '/PV'); values.append(float(data[signal]))
			elif kind == 'Silo' and signal in data:
				paths.append(path + '/Level'); values.append(float(data[signal]))
			elif kind == 'Motor':
				mode = operator.get(path + '/Mode') or 'Auto'
				on = mode == 'Hand' or (mode == 'Auto' and running and params.get('Duty') != 'Standby')
				if signal in data and signal.endswith('Amps'):
					current = float(data[signal])
				else:
					current = float(params.get('RatedCurrent') or 10.0) * (0.82 + 0.04 * math.sin(seconds / 23.0 + len(path)))
				paths.extend([path + '/Running', path + '/Current']); values.extend([on, current if on else 0.0])
			elif kind == 'Valve':
				mode = operator.get(path + '/Mode') or 'Auto'
				control = params.get('Description') == 'Control valve'
				position = 42.0 + 6.0 * math.sin(seconds / 37.0 + len(path)) if control else 100.0
				if mode == 'Hand':
					position = float(operator.get(path + '/PositionSP') or 0.0)
				opened = mode == 'Hand' or (mode == 'Auto' and running)
				paths.extend([path + '/Open', path + '/Position']); values.extend([opened and position > 0, position if opened else 0.0])
			elif kind == 'ProcessArea':
				paths.extend([path + '/State', path + '/Running', path + '/LastUpdate']); values.extend([data['state'], running, now])
	if paths:
		qualities = system.tag.writeBlocking(paths, values)
		bad = [path for path, quality in zip(paths, qualities) if not quality.isGood()]
		if bad:
			raise ValueError('{0} SCADA tag writes failed, first {1}'.format(len(bad), bad[0]))


def scadaValues(area):
	keys, paths = [], []
	for kind, path, params in _scadaTagIndex().get(area, []):
		if kind in ('AnalogInput', 'Silo') and params.get('Signal') not in keys:
			keys.append(params['Signal']); paths.append(path + ('/PV' if kind == 'AnalogInput' else '/Level'))
		elif kind == 'ProcessArea':
			keys.extend(['state', 'running']); paths.extend([path + '/State', path + '/Running'])
	if not paths:
		return {}
	return dict(zip(keys, [qv.value if qv.quality.isGood() else None for qv in system.tag.readBlocking(paths)]))


def scadaEquipmentElements(body, width, height, padding):
	# Equipment templates draw their body from (0, 0); padding (left, top, right,
	# bottom) holds hoppers, heads and stacks, plus 2 px for the outline stroke.
	left, top = padding[0] + 2, padding[1] + 2
	return scadaElements(u'<g transform="translate({0} {1})" fill="#d7d9d8" stroke="#666a68" stroke-width="1.4">{2}</g>'.format(left, top, body))


def faceplateHistory(tagPath, hours):
	# Points for the faceplate chart: recorded line history where it exists,
	# otherwise the same deterministic model that drives the tag.
	import math
	found = _scadaInstance(tagPath)
	if not found:
		return {'points': [], 'unit': '', 'message': 'Unknown tag.'}
	area, kind, params = found
	spec = _scadaArea(area)
	signal = params.get('Signal') or ''
	hours = max(1, min(24, int(hours or 1)))
	end = system.date.toMillis(system.date.now())
	start = end - hours * 3600 * 1000
	times = [start + (end - start) * i / 239 for i in range(240)]
	unit = {'Motor': 'A', 'Valve': '%', 'Silo': '%'}.get(kind, params.get('Unit') or '')
	running = dict((t, True) for t in times)
	points, source = [], 'Simulated process model'
	if spec['line']:
		# A stopped line stops its drives: take the line state from recorded throughput.
		rate = history(start, end, spec['line'], 'rate').get('points', [])
		recorded = [(p['ts'], p.get('line' + str(spec['line']))) for p in rate if p.get('line' + str(spec['line'])) is not None]
		if recorded:
			for t in times:
				nearest = min(recorded, key=lambda point: abs(point[0] - t))
				running[t] = nearest[1] > 1
	if kind in ('AnalogInput', 'Silo') and spec['line'] and signal in SCADA_LIVE:
		result = history(start, end, spec['line'], signal)
		points = [{'ts': p['ts'], 'value': p.get('line' + str(spec['line']))} for p in result.get('points', []) if p.get('line' + str(spec['line'])) is not None]
		source = 'Recorded line history'
	elif kind in ('AnalogInput', 'Silo') and signal in spec['signals']:
		points = [{'ts': t, 'value': _scadaWave(signal, spec['signals'][signal], t / 1000.0)} for t in times]
	elif kind == 'Motor':
		amps = signal.endswith('Amps') and signal in spec['signals']
		rated = float(params.get('RatedCurrent') or 10.0)
		for t in times:
			on = running[t] and params.get('Duty') != 'Standby'
			value = _scadaWave(signal, spec['signals'][signal], t / 1000.0) if amps else rated * (0.82 + 0.04 * math.sin(t / 1000.0 / 23.0 + len(tagPath)))
			points.append({'ts': t, 'value': value if on else 0.0})
	elif kind == 'Valve':
		control = params.get('Description') == 'Control valve'
		for t in times:
			value = 42.0 + 6.0 * math.sin(t / 1000.0 / 37.0 + len(tagPath)) if control else 100.0
			points.append({'ts': t, 'value': value if running[t] else 0.0})
	if kind in ('AnalogInput', 'Silo') and points:
		low, high = [qv.value for qv in system.tag.readBlocking([tagPath + '/LowLimit', tagPath + '/HighLimit'])]
		# Signals without real limits carry +/-1e9 placeholders; leave those off the chart.
		for point in points:
			if low is not None and abs(low) < 1e8:
				point['low'] = low
			if high is not None and abs(high) < 1e8:
				point['high'] = high
	return {'points': points, 'unit': unit, 'message': u'{0}, last {1} h. Mode changes and limits apply from now on.'.format(source, hours)}


SCADA_PILLS = {'Stopped': ('#b23b34', '#ffffff'), 'Quality hold': ('#f6dca6', '#6b4a0c'), 'Recovering': ('#c9d9ea', '#24425f')}


def scadaTile(tagPath):
	area = tagPath.split('/')[-2].lower()
	spec = _scadaArea(area)
	data = scadaValues(area)
	state = data.get('state') or 'Starting'
	fill, text = SCADA_PILLS.get(state, ('#dfe3e6', '#4d555c'))
	rows = []
	for caption, signal, unit, decimals in spec['tile']:
		value = data.get(signal)
		rows.append({'caption': caption, 'value': _scadaFormat(value, unit, decimals) if value is not None else '--'})
	return {'title': spec['title'], 'state': state.upper(), 'pillFill': fill, 'pillText': text, 'rows': rows}


def completedOutputBatches():
	return _queryJson("""SELECT coalesce(jsonb_agg(to_jsonb(x)), '[]') FROM (
		SELECT b.reference,l.product,l.name AS line,
		to_char(b.ends AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') AS completed,
		EXISTS(SELECT 1 FROM oat_demo.batch_output o WHERE o.batch_reference=b.reference) AS recorded
		FROM oat_demo.plan_batches(now()-interval '90 days',now(),0) b
		JOIN oat_demo.line l ON l.id=b.line_id
		WHERE b.ends<=now()
		AND EXISTS(SELECT 1 FROM oat_demo.sample s WHERE s.line_id=b.line_id AND s.at>=b.starts AND s.at<b.ends)
		ORDER BY b.ends DESC LIMIT 200) x""")


def recentBatchOutputs():
	return _queryJson("""SELECT coalesce(jsonb_agg(to_jsonb(x)), '[]') FROM (
		SELECT o.batch_reference AS reference,o.product,l.name AS line,o.quantity_kg,o.bags,
		to_char(o.completed_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') AS completed,
		to_char(o.recorded_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') AS recorded
		FROM oat_demo.batch_output o JOIN oat_demo.line l ON l.id=o.line_id
		ORDER BY o.recorded_at DESC LIMIT 100) x""")


def validateBatchOutput(values):
	values = values or {}
	checks = {
		'quantity': common.validation.input.validateNumericInput(values.get('quantity'), negativeAllowed=False, decimalAllowed=True, required=True),
		'bags': common.validation.input.validateNumericInput(values.get('bags'), negativeAllowed=False, decimalAllowed=False, required=True)
	}
	errors = []
	if not values.get('reference'):
		errors.append('Select a completed batch.')
	quantity = checks['quantity']['validatedOutput']
	bags = checks['bags']['validatedOutput']
	if checks['quantity']['errorMessage'] or quantity is None or not 0 <= quantity <= 100000:
		errors.append('Enter a valid output quantity in kg, from 0 to 100,000.' if values.get('quantity') else 'Enter the actual output quantity.')
	if checks['bags']['errorMessage'] or bags is None or not 0 <= bags <= 10000:
		errors.append('Enter a whole bag count from 0 to 10,000.')
	return {'valid': not errors, 'message': ' '.join(errors),
		'values': {'reference': values.get('reference'), 'quantity': quantity, 'bags': bags}}


def recordBatchOutput(values, requestId):
	validation = validateBatchOutput(values)
	if not validation['valid']:
		raise ValueError(validation['message'])
	v = validation['values']
	result = _queryJson('SELECT oat_demo.record_batch_output(CAST(? AS uuid), ?, CAST(? AS numeric), CAST(? AS integer))',
		[str(UUID.fromString(str(requestId))),str(v['reference']),v['quantity'],v['bags']])
	return 'Output recorded for batch {0}.'.format(result['reference']) if result['created'] else 'Output was already recorded for batch {0}.'.format(result['reference'])
