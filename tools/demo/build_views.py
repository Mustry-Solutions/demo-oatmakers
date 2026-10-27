"""Build the operational demo with Mustry UI controls and live SCADA."""
import base64,copy,json,shutil
from view_primitives import *
M='mustrysolutions.perspective.'
EMPTY_RANGE={'start':0,'end':0,'valid':False,'realtime':False}
EMPTY_HISTORY={'points':[],'count':0,'message':'Loading recorded history...'}
COLORS=['#39444f','#77889a','#aeb8c0']
THEME_COLORS={'hello-kitty':['#ac2454','#246b80','#857038']}
LINES=[(0,'All lines'),(1,'Rolling line 01'),(2,'Cutting line 02'),(3,'Milling line 03')]
METRICS={'rate':('Throughput','Throughput','kg/h'),'temperature':('Temperature','Temperature','°C'),'moisture':('Moisture','Moisture','%'),'pressure':('Pressure','Pressure','bar'),'power':('Power','Power','kW')}

def theme_series(n,colours):
    for i,colour in enumerate(colours):
        values={'standard':colour}|{t:c[i] for t,c in THEME_COLORS.items()}
        for key in ('stroke.color','fill.color'):n['propConfig'][f'props.series[{i}].line.appearance.{key}']=themed(values)
    return n

def bind_script(path,code):
    return {'binding':{'type':'property','config':{'path':path},'transforms':[{'type':'script','code':code}]}}
def struct_binding(values,code):
    return {'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':values},'transforms':[{'type':'script','code':code}]}}
def action(script):return {'component':{'onActionPerformed':{'type':'script','scope':'G','config':{'script':script}}}}
def select(name,options,path,width='200px'):
    n=node('ia.input.dropdown',name,{'options':[{'value':v,'label':l} for v,l in options],'value':options[0][0],'search':{'enabled':False},'style':{'classes':'Demo/Select','overflow':'visible'}},basis=width)
    n['propConfig']={'props.value':prop(path,True)};return n

def grid(name,source,columns,key='reference',height='350px',selectable=False):
    cols=[]
    for field,title,width in columns:
        col={'field':field,'header':title,'width':width}
        if field in ('produced_kg','target_kg','good_kg','quantity_kg','bags','minutes','lost_kg'):
            col.update({'type':'number','align':'right','decimals':1 if field.endswith('_kg') else 0})
        if field in ('status','quality','result'):
            col['cellStyles']=[{'equals':v,'color':c,'background':bg} for v,c,bg in [('Scheduled','#5d666e','#eef1f3'),('In production','#23282d','#e2e6e9'),('Completed','#5d666e','#f1f3f5'),('Quality review','#b57a17','#fdf3e0'),('Review required','#b57a17','#fdf3e0'),('Stopped','#b23b34','#fbeceb'),('Released','#3f4a54','#eef1f3'),('Within limits','#3f4a54','#eef1f3')]]
        cols.append(col)
    n=node(M+'input.datagrid',name,{'config':{'columns':cols,'idField':key,'rowHeight':44,'locale':'en-GB','rowSelect':'single' if selectable else 'none','showToolbar':True,'showExport':True,'editable':False,'emptyMessage':'No records for the selected range.'},'data':{'rows':[]},'state':{'selection':[]},'style':{'classes':'Demo/DataGrid'}},basis=height)
    n['propConfig']={'props.data.rows':prop(source)};return n

def picker(name='DateRange'):
    presets=[{'label':title,'type':'rolling','rolling':{'amount':amount,'unit':unit}} for title,amount,unit in [('Last 15 min',0.25,'hours'),('Last hour',1,'hours'),('Last 8 hours',8,'hours'),('Last 24 hours',24,'hours'),('Last 7 days',7,'days'),('Last 30 days',30,'days')]]
    n=node(M+'input.datetimerangepicker',name,{'config':{'display':'popover','layout':'twoMonths','granularity':'second','timezone':'Europe/Brussels','locale':'en-GB','disableDates':'future','spanDays':{'max':90},'showPresets':True,'showClear':False,'popover':{'placeholder':'Choose history range','closeOnSelect':True,'dateFormat':'DD/MM/YYYY'},'presets':presets,'realtime':{'enabled':True,'refreshSeconds':5}},'selection':{'rollingAmount':1,'rollingUnit':'hours'},'style':{'overflow':'visible','classes':'Demo/DateRange'}},basis='390px')
    n['props']['output']={'startDateTime':'','endDateTime':'','startEpochMs':0,'endEpochMs':0,'durationDays':0,'durationHours':0,'durationLabel':'','isValid':False,'isRealtime':False}
    n['propConfig']={'props.output':{'persistent':True},'props.config.dateBounds.earliest':{'binding':{'type':'expr','config':{'expression':'dateFormat(addDays(now(60000), -90), "yyyy-MM-dd")'}}}}
    return n

# Common visual components.
metric=flex('root',[bound_label('Title','view.params.title','Demo/Eyebrow'),flex('Reading',[bound_label('Value','view.params.value','Demo/MetricValue'),bound_label('Unit','view.params.unit','Demo/MetricUnit')],'row','Demo/MetricReading'),bound_label('Hint','view.params.hint','Demo/Muted')],classes='Demo/Metric')
view('Templates/Cards/Metric',metric,params={'title':'','value':'','unit':'','hint':''},height=135)

line_children=[flex('Heading',[bound_label('Name','view.params.name','Demo/SectionTitle'),bound_label('State','view.params.state','Demo/Badge')],'row','Demo/Spread'),bound_label('Product','view.params.product','Demo/Muted'),label('SpeedCaption','LIVE THROUGHPUT','Demo/Eyebrow')]
rate=bound_label('Rate','view.params.rate','Demo/LineValue');rate['propConfig']['props.text']=bind_script('view.params.rate','\treturn "{0:,.0f} kg/h".format(value or 0)');line_children.append(rate)
readings=[]
for key in ['temperature','moisture','pressure']:
    b=button(key.title(),'',script='\tapplication.demo.showHistory(self.view.params.lineNumber, '+json.dumps(key)+')',classes='Demo/ReadingButton')
    b['position']={'basis':'90px','grow':1,'shrink':1}
    b['propConfig']={'props.text':bind_script('view.params.'+key,'\treturn u"{0:.1f} {1}".format(value or 0, '+'u'+json.dumps(METRICS[key][2])+')')};readings.append(b)
line_children += [flex('Readings',readings,'row','Demo/Wrap'),button('Scada','Open SCADA',script='\tsystem.perspective.navigate({1: "/scada/flaking", 2: "/scada/cutting", 3: "/scada/milling"}.get(int(self.view.params.lineNumber), "/scada"))',classes='Demo/QuietButton')]
line_root=flex('root',line_children,classes='Demo/Panel');line_root['children'][0]['children'][1]['propConfig']['props.style.color']=prop('view.params.colour')
view('Templates/Cards/LineCard',line_root,params={'lineNumber':1,'name':'','state':'','product':'','rate':0,'temperature':0,'moisture':0,'pressure':0,'colour':'#2d8962'},height=270)

# Shared history view: the Mustry picker output is the source of the query.
control=flex('Controls',[picker(),select('Line',LINES,'view.params.lineNumber'),select('Measurement',[(k,v[1]) for k,v in METRICS.items()],'view.params.metric')],'row','Demo/Filters')
control['children'][1]['propConfig']['position.display']=prop('view.params.showSelectors');control['children'][2]['propConfig']['position.display']=prop('view.params.showSelectors')
hchart=chart('HistoryPlot',[(f'line{i}',name,COLORS[i-1]) for i,name in LINES if i],source='view.custom.history.points',height='320px')
hchart['position']={'basis':'0px','grow':1,'shrink':1};hchart['props']['style'].update({'minHeight':'240px'})
for s in hchart['props']['series']:
    s['line']['appearance']['fill']['opacity']=0;s['line']['appearance']['stroke']['width']=2
hchart['props']['xAxes'][0]['date']['format']='dd MMM HH:mm';hchart['props']['xAxes'][0]['appearance']['grid']['minDistance']=110
hchart['props']['yAxes'][0]['value']['range']['min']=''
for i in range(3):
    hchart['propConfig'][f'props.series[{i}].visible']=expr('{view.params.lineNumber} = 0 || {view.params.lineNumber} = '+str(i+1))
    hchart['propConfig'][f'props.series[{i}].hiddenInLegend']=expr('{view.params.lineNumber} != 0 && {view.params.lineNumber} != '+str(i+1))
theme_series(hchart,COLORS)
hchart['propConfig']['props.yAxes[0].label.enabled']={'persistent':True};hchart['props']['yAxes'][0]['label']['enabled']=True
hchart['propConfig']['props.yAxes[0].label.text']=bind_script('view.params.metric','\treturn application.demo.METRICS.get(value or "rate", application.demo.METRICS["rate"])[2]')
history_root=flex('root',[control,hchart,bound_label('HistoryMessage','view.custom.history.message','Demo/Muted')],classes='Demo/HistoryRoot')
range_cfg={'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'start':'try({/root/Controls/DateRange.props.output.startEpochMs}, 0)','end':'try({/root/Controls/DateRange.props.output.endEpochMs}, 0)','valid':'try({/root/Controls/DateRange.props.output.isValid}, false)','realtime':'try({/root/Controls/DateRange.props.output.isRealtime}, false)'}}}}
view('Templates/Charts/HistoryChart',history_root,params={'lineNumber':0,'metric':'rate','showSelectors':True,'range':copy.deepcopy(EMPTY_RANGE)},custom={'range':copy.deepcopy(EMPTY_RANGE),'history':copy.deepcopy(EMPTY_HISTORY)},config={'custom.range':dict(range_cfg,persistent=True),'params.lineNumber':{'paramDirection':'inout','persistent':True},'params.metric':{'paramDirection':'inout','persistent':True},'params.range':dict(prop('view.custom.range'),paramDirection='output',persistent=True),'custom.history':struct_binding({'range':'{view.custom.range}','line':'{view.params.lineNumber}','metric':'{view.params.metric}','refresh':'now(5000)'},'\tvalue = value or {}\n\trange_value = value.get("range") or {}\n\tif not range_value.get("valid", False):\n\t\treturn {"points": [], "count": 0, "message": "Loading recorded history..."}\n\treturn application.demo.history(range_value.get("start", 0), range_value.get("end", 0), value.get("line", 0), value.get("metric", "rate"))')},height=430)

for path in ['Templates/Charts/HistoryChart']:
    file=V/path/'view.json';data=json.loads(file.read_text())
    data['propConfig']['custom.history']['persistent']=True
    write(file,data)

# Minimal fixed-height headers leave the operational content its space.
EMPTY_LIVE={'ready':False,'metrics':[],'lines':[],'trend':[],'updatedEpochMs':0,'updatedAt':'','shiftStart':''}
def page(name,title,subtitle,body,custom=None,config=None,live_header=True):
    header=flex('Header',[flex('Identity',[label('Eyebrow','OATMAKERS / LIVE OPERATIONS','Demo/Eyebrow'),label('Title',title,'Demo/PageTitle'),label('Subtitle',subtitle,'Demo/Subtitle')],grow=1),theme_badge(label('Mode','SIMULATED FACTORY','Demo/DemoBadge'))],'row','Demo/PageHeader')
    children=[header]
    if live_header:
        live_label=label('LiveStatus','','Demo/LiveStatus')
        live_label['propConfig']={'props.text':expr('if({view.custom.live.ready}, "Live · recorded at " + {view.custom.live.updatedAt} + " · updates every second", "Live telemetry is unavailable")'),'props.style.color':expr('if({view.custom.live.ready}, "#6d757c", "#b57a17")')}
        children.append(live_label)
    cfg={'custom.live':struct_binding({'tick':'now(1000)'},'\treturn application.demo.live()')} if live_header else {}
    cfg.update(config or {})
    return view(name,theme_root(flex('root',children+body,classes='Demo/Page')),custom=({'live':EMPTY_LIVE} if live_header else {})|(custom or {}),config=cfg)

def line_cards():
    return repeater('Lines','Templates/Cards/LineCard','view.custom.live.lines','auto')
def live_metrics():
    n=repeater('LiveMetrics','Templates/Cards/Metric','view.custom.live.metrics','auto');return n

live_plot=chart('LiveTrend',[('rate','Throughput (t/h)','#2d8962')],source='view.custom.live.trend',height='235px');live_plot['props']['legend']['enabled']=False;theme_series(live_plot,['#2d8962'])
page('Pages/Overview','What is happening now','Live production rates, shift output and process alerts.',[
 live_metrics(),line_cards(),panel('LiveTrendPanel','Factory throughput','The latest ten minutes of recorded one-second telemetry.',[live_plot,button('History','Choose a history range',page='/performance',classes='Demo/QuietButton')],grow=0)])

# The resource timeline owns its window; only visible batches are fetched.
resources=[{'id':str(i),'label':name,'group':'Oat processing','color':COLORS[i-1]} for i,name in LINES if i]
timeline=node(M+'display.resourcetimeline','Timeline',{'config':{'resources':resources,'rowHeight':76,'timezone':'Europe/Brussels','locale':'en-GB','showToolbar':True,'showMiniNav':True,'showLegend':True,'refreshSeconds':5,'editable':False,'selectable':False,'builtInEditor':False,'showExport':True,'categories':[{'id':k,'label':t,'color':c} for k,t,c in [('planned','Scheduled','#9aa3ab'),('running','In production','#4d5862'),('quality','Quality review','#b57a17'),('complete','Completed','#c3cad0'),('stop','Unplanned stop','#b23b34'),('changeover','Changeover / CIP','#7d8891')]],'shifts':[{'label':'Early','start':'06:00'},{'label':'Late','start':'14:00'},{'label':'Night','start':'22:00'}]},'data':{'events':[]},'state':{'zoom':'shift','followNow':True},'style':{'classes':'Demo/PlanningTimeline'}},basis='480px')
timeline['propConfig']={'props.data.events':prop('view.custom.events')}
timeline['events']={'component':{'onEventClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showBatch(event.id)'}}}}
page('Pages/Production','Production planning','Browse shifts, pan through the schedule and open a batch for details.',[
 timeline,label('PlanningHelp','Use Hour, Day, Shift or Week to change the scale. Click a batch to inspect its production and quality record.','Demo/Muted')],custom={'events':[]},config={'custom.events':struct_binding({'start':'{/root/Timeline.props.output.visibleStartMs}','end':'{/root/Timeline.props.output.visibleEndMs}','refresh':'now(5000)'},'\treturn application.demo.timeline(value["start"], value["end"])')})

history=embed('History','Templates/Charts/HistoryChart',{'lineNumber':0,'metric':'rate','showSelectors':True,'range':copy.deepcopy(EMPTY_RANGE)},basis='460px')
page('Pages/Performance','Performance & history','Pick exact dates or a live preset. Every chart uses that recorded range.',[
 history,repeater('Metrics','Templates/Cards/Metric','view.custom.summary.metrics','auto'),
 grid('Losses','view.custom.summary.losses',[('reason','Loss reason',250),('minutes','Line minutes',140),('lost_kg','Lost output kg',160)],key='reason',height='250px')],custom={'summary':{'metrics':[],'losses':[]}},config={'custom.summary':struct_binding({'start':'try({/root/History.props.params.range.start}, 0)','end':'try({/root/History.props.params.range.end}, 0)','line':'{/root/History.props.params.lineNumber}','refresh':'now(10000)'},'\treturn application.demo.rangeSnapshot(value["start"], value["end"], value["line"])')},live_header=False)

# One modern record grid, with an explicit inspect action.
quality_picker=picker('QualityRange')
quality_picker['props']['selection']['rollingAmount']=24
quality_picker['props']['style']['height']='40px'
qgrid=grid('BatchGrid','view.custom.batches',[('reference','Batch',190),('product','Product',160),('line','Line',170),('good_kg','Good output kg',150),('quality','Quality decision',170)],height='480px',selectable=True)
inspect=button('InspectBatch','Inspect selected batch',script='\tapplication.demo.showBatch(self.view.custom.selected)',classes='Demo/Button');inspect['propConfig']={'props.enabled':expr('len({view.custom.selected}) > 0')}
inspect['position']={'basis':'auto','grow':0,'shrink':0}
inspect['props']['style'].update({'height':'40px','minWidth':'180px','whiteSpace':'nowrap'})
page('Pages/Quality','Quality & traceability','Find a production batch and inspect its measurements.',[
 flex('QualityFilters',[quality_picker,inspect],'row','Demo/Filters'),qgrid],custom={'batches':[],'selected':''},config={'custom.batches':struct_binding({'start':'{/root/QualityFilters/QualityRange.props.output.startEpochMs}','end':'{/root/QualityFilters/QualityRange.props.output.endEpochMs}','refresh':'now(10000)'},'\treturn application.demo.batches(value["start"], value["end"])'),'custom.selected':bind_script('/root/BatchGrid.props.state.selection','\treturn str(value[0]) if value else ""')},live_header=False)

# Detail popups have their own range-controlled history and compact measurements.
qc=button('Inspect','Record demo inspection',script='\ttry:\n\t\tself.view.custom.result = application.demo.recordInspection(self.view.params.reference)\n\t\tself.view.refreshBinding("custom.batch")\n\texcept (Exception, application.demo.JavaException):\n\t\tself.view.custom.result = "Inspection could not be recorded for this batch."')
qc['propConfig']={'props.enabled':expr('{view.custom.batch.available} && {view.custom.batch.status} != "Scheduled"')}
batch_cards=[]
for name,title,key,unit in [('Output','GOOD OUTPUT','good_kg','kg'),('Moisture','PEAK MOISTURE','peak_moisture','%'),('Temperature','AVERAGE TEMPERATURE','temperature','°C')]:
    card=embed(name,'Templates/Cards/Metric',{'title':title,'unit':unit,'hint':''},basis='240px',grow=1)
    card['propConfig']={'props.params.value':bind_script('view.custom.batch','\treturn value.get("'+key+'", "n/a")')};batch_cards.append(card)
batch_root=flex('root',[bound_label('BatchTitle','view.params.reference','Demo/SectionTitle'),bound_label('Product','view.custom.batch.product','Demo/Subtitle'),bound_label('Status','view.custom.batch.status','Demo/Badge'),flex('Measurements',batch_cards,'row','Demo/Wrap'),qc,bound_label('Result','view.custom.result','Demo/Muted')],classes='Demo/PopupRoot')
theme_root(batch_root)
view('Popups/BatchDetails',batch_root,params={'reference':''},custom={'batch':{'available':False,'product':'','status':'Loading'},'result':''},config={'custom.batch':bind_script('view.params.reference','\treturn application.demo.batchDetails(value)')},height=400)

# Record actual output against an existing completed batch.
reference=node('ia.input.dropdown','Reference',{'options':[],'value':'','placeholder':'Select a completed batch','search':{'enabled':True},'style':{'classes':'Demo/Select'}},basis='42px')
reference['propConfig']={'props.options':bind_script('view.custom.batches','\toptions = []\n\tfor row in value or []:\n\t\tlabel = row["reference"] + " | " + row["product"]\n\t\tif row["recorded"]:\n\t\t\tlabel += " (recorded)"\n\t\toptions.append({"label": label, "value": row["reference"]})\n\treturn options')}
context=label('BatchContext','','Demo/Muted')
context['propConfig']={'props.text':bind_script('view.custom.selected','\tif not value or not value.get("reference"):\n\t\treturn ""\n\treturn value["product"] + " | " + value["line"] + " | Completed " + value["completed"]')}
fields=[label('BatchLabel','Completed batch','Demo/Body'),reference,context]
for name,title,initial,decimal in [('Quantity','Output quantity (kg)','',True),('Bags','Number of bags','0',False)]:
    fields.append(label(name+'Label',title,'Demo/Body'))
    field=node('ia.input.text-field',name,{'text':initial,'deferUpdates':False,'placeholder':'Enter actual quantity' if decimal else '0 for bulk output','style':{'classes':'Demo/Select','padding':'8px'}},basis='42px')
    fields.append(field)
fields.append(label('BulkHint','For bulk output, enter 0 bags.','Demo/Muted'))
notice=label('RecordedNotice','','Demo/Status');notice['propConfig']={'props.text':expr('if({view.custom.selected.recorded} && !{view.custom.saved}, "Output has already been recorded for this batch.", "")')}
submit=button('Submit','Record output',script='\tif self.view.custom.busy:\n\t\treturn\n\tself.view.custom.busy = True\n\ttry:\n\t\tif not self.view.custom.requestId:\n\t\t\tself.view.custom.requestId = application.demo.newRequestId()\n\t\tself.view.custom.result = application.demo.recordBatchOutput(dict(self.view.custom.values),self.view.custom.requestId)\n\t\tself.view.custom.saved = True\n\t\tself.view.refreshBinding("custom.records")\n\t\tself.view.refreshBinding("custom.batches")\n\texcept (Exception, application.demo.JavaException):\n\t\tself.view.custom.result = "Output could not be recorded. Verify the batch and quantities, then try again."\n\tfinally:\n\t\tself.view.custom.busy = False')
submit['propConfig']={'props.enabled':expr('{view.custom.validation.valid} && !{view.custom.busy} && !{view.custom.saved} && !{view.custom.selected.recorded}')}
form=panel('Form','Record batch output','',fields+[notice,bound_label('Validation','view.custom.validation.message','Demo/Muted'),submit,bound_label('Result','view.custom.result','Demo/Status')],basis='450px',grow=0)
form['props']['style'].update({'overflow':'visible','alignSelf':'flex-start'})
output_grid=grid('Outputs','view.custom.records',[('reference','Batch',190),('product','Product',150),('line','Line',150),('quantity_kg','Output (kg)',130),('bags','Bags',80),('recorded','Recorded at',140)],height='0px')
output_grid['props']['config']['emptyMessage']='No batch output recorded yet.'
output_grid['position']={'basis':'0px','grow':1,'shrink':1}
output_panel=panel('OutputList','Recorded output','',[output_grid],basis='560px',grow=1)
output_panel['props']['style'].update({'height':'calc(100vh - 215px)','minHeight':'400px','overflow':'hidden'})
workspace=flex('Workspace',[form,output_panel],'row','Demo/Workspace')
page('Pages/Operator','Batch output','Record actual production for a completed batch.',[workspace],custom={'values':{},'validation':{'valid':False,'message':'Select a completed batch and enter its output.'},'requestId':'','busy':False,'saved':False,'result':'','batches':[],'records':[],'selected':{'reference':'','product':'','line':'','completed':'','recorded':False}},config={
 'custom.values':dict(struct_binding({'reference':'{/root/Workspace/Form/Reference.props.value}','quantity':'{/root/Workspace/Form/Quantity.props.text}','bags':'{/root/Workspace/Form/Bags.props.text}'},'\treturn value'),onChange={'enabled':True,'script':'\tself.custom.requestId = ""\n\tself.custom.saved = False\n\tself.custom.result = ""'}),
 'custom.validation':bind_script('view.custom.values','\treturn application.demo.validateBatchOutput(value)'),
 'custom.batches':struct_binding({'refresh':'now(10000)'},'\treturn application.demo.completedOutputBatches()'),
 'custom.records':struct_binding({'refresh':'now(5000)'},'\treturn application.demo.recentBatchOutputs()'),
 'custom.selected':struct_binding({'reference':'try({/root/Workspace/Form/Reference.props.value}, "")','batches':'{view.custom.batches}'},'\tfor row in value["batches"] or []:\n\t\tif row["reference"] == value["reference"]:\n\t\t\treturn row\n\treturn {"reference": "", "product": "", "line": "", "completed": "", "recorded": False}')})
operator_file=V/'Pages/Operator/view.json'
operator=json.loads(operator_file.read_text())
def trim_empty_captions(component):
    if 'children' in component:
        component['children']=[c for c in component['children'] if not (c.get('type')=='ia.display.label' and c.get('props',{}).get('text')=='' and not c.get('propConfig'))]
        for child in component['children']:trim_empty_captions(child)
trim_empty_captions(operator['root'])
for key in ('custom.batches','custom.records','custom.selected'):
    operator['propConfig'][key]['persistent']=True
write(operator_file,operator)

from build_scada import build_scada, SCADA_CSS, AREAS
scada_routes=build_scada()

popup_history=embed('History','Templates/Charts/HistoryChart',{'showSelectors':False},basis='0px',grow=1);popup_history['position']['shrink']=1;popup_history['propConfig']={'props.params.lineNumber':prop('view.params.lineNumber'),'props.params.metric':prop('view.params.metric')}
view('Popups/TagHistory',theme_root(flex('root',[bound_label('Title','view.params.title','Demo/SectionTitle'),bound_label('Tag','view.params.tagPath','Demo/Muted'),popup_history],classes='Demo/PopupRoot')),params={'lineNumber':1,'metric':'temperature','title':'Temperature','tagPath':''},height=560)

health_cards=[]
for name,title,key,unit,hint in [('Age','LIVE DATA AGE','liveAgeSeconds','sec','One-second recorded telemetry'),('History','HISTORY','coverageDays','days','Minute history, capped at three months'),('Lines','LINES','lineCount','','Three simulated production lines')]:
    card=embed(name,'Templates/Cards/Metric',{'title':title,'unit':unit,'hint':hint},basis='240px',grow=1);card['propConfig']={'props.params.value':prop('view.custom.health.'+key)};health_cards.append(card)
page('Pages/Health','Demo health','Data freshness and automatic retention.',[flex('Metrics',health_cards,'row','Demo/Wrap'),label('Policy','One-second telemetry is retained for 6 hours. Minute history, recorded batch output and inspections are retained for at most 90 days or three calendar months.','Demo/Body')],custom={'health':{'liveAgeSeconds':'n/a','coverageDays':'n/a','lineCount':'n/a'}},config={'custom.health':struct_binding({'refresh':'now(5000)'},'\treturn application.demo.health()')})

# Session settings: the theme applies to every page, popup and the navigation.
theme_picker=select('Theme',THEMES,'session.custom.theme',width='40px');theme_picker['props']['style']['maxWidth']='320px'
page('Pages/Settings','Settings','Choose how the demo looks for this session.',[
 panel('Appearance','Theme','Standard follows high-performance HMI practice. Hello Kitty is the pink edition.',[theme_picker],grow=0)],live_header=False)

routes=[('/','Factory overview','Pages/Overview'),('/scada','SCADA','Pages/Scada/Overview'),('/production','Production planning','Pages/Production'),('/performance','Performance','Pages/Performance'),('/quality','Quality & traceability','Pages/Quality'),('/operator','Batch output','Pages/Operator')]
logo=base64.b64encode((ROOT/'tools/demo/scada-assets/oatmakers-logo.svg').read_bytes()).decode()
kitty=base64.b64encode((ROOT/'tools/demo/scada-assets/hello-kitty.png').read_bytes()).decode()
brand=node('ia.display.image','Brand',{'source':'data:image/svg+xml;base64,'+logo,'altText':'Oatmakers','fit':{'mode':'contain'},'style':{'classes':'Demo/BrandLogo'}},basis='74px')
kitty_brand=node('ia.display.image','KittyBrand',{'source':'data:image/png;base64,'+kitty,'altText':'Hello Kitty with her red bow','fit':{'mode':'contain'},'style':{'classes':'Demo/BrandLogo'}},basis='130px')
brand['propConfig']={'position.display':themed({'standard':True,'hello-kitty':False})};kitty_brand['propConfig']={'position.display':themed({'standard':False,'hello-kitty':True})}
detail=label('BrandDetail','CONNECTED OPERATIONS','Demo/NavEyebrow');detail['propConfig']={'props.text':themed({'standard':'CONNECTED OPERATIONS','hello-kitty':'Hello Kitty operations'})}
nav=[brand,kitty_brand,detail,label('DemoLabel','LIVE SIMULATION','Demo/NavBadge')]
# The SCADA entry drills down into process groups and their area screens.
def item(title,target='',icon='',children=None):
    return {'target':target,'items':children or [],'navIcon':{'path':'material/chevron_right' if children else ''},'label':{'text':title,'icon':{'path':icon}},'visible':True,'enabled':True,'showHeader':True,'resetOnClick':False,'backActionText':'','style':{'classes':''}}
groups={}
for route,title,_ in scada_routes:groups.setdefault(next(a[3] for a in AREAS if a[1]==route),[]).append(item(title,route))
scada_menu=[item('Plant overview','/scada','material/dashboard')]+[item(g,icon=i,children=children) for (g,children),i in zip(groups.items(),['material/local_shipping','material/grain','material/layers','material/archive','material/build'])]
menu_items=[item('Factory overview','/','material/home'),item('SCADA',icon='material/device_hub',children=scada_menu)]+[item(t,r,i) for (r,t,_),i in zip(routes[2:],['material/event','material/timeline','material/verified_user','material/assignment'])]
menu=node('ia.navigation.menutree','Menu',{'items':menu_items,'layoutAlignment':'left','backActionText':'Back','style':{'classes':'Demo/Menu'}},basis='auto',grow=1)
menu['propConfig']={'props.items':bind_script('page.props.path','\titems = system.util.jsonDecode('+json.dumps(json.dumps(menu_items))+')\n\tdef mark(nodes):\n\t\tfound = False\n\t\tfor n in nodes:\n\t\t\tchild = mark(n["items"])\n\t\t\tactive = n["target"] == value\n\t\t\tn["style"]["classes"] = "Demo/MenuActive" if active else ("Demo/MenuTrail" if child else "")\n\t\t\tfound = found or active or child\n\t\treturn found\n\tmark(items)\n\treturn items')}
nav.append(menu)
NAV_ICONS={'/settings':'settings','/demo/health':'favorite'}
def nav_icon(b,path):
    b['props']['image']={'icon':{'path':'material/'+NAV_ICONS[path],'color':'#d5dade','style':{}},'position':'left','width':18,'height':18}
    b.setdefault('propConfig',{})['props.image.icon.color']=themed({'standard':'#d5dade','hello-kitty':'#ac2454'});return b
nav += [nav_icon(button('Settings','Settings',page='/settings',classes='Demo/NavButton'),'/settings'),nav_icon(button('Health','Demo health',page='/demo/health',classes='Demo/NavButton'),'/demo/health'),label('Footer','Mustry Solutions','Demo/NavFooter')]
view('Docks/Sidenav',theme_root(flex('root',nav,classes='Demo/Navigation')),height=900)
config=json.loads((P/'page-config/config.json').read_text());config['pages'].pop('/components',None)
for route,title,path in routes+scada_routes:config['pages'][route]={'title':title,'viewPath':path}
config['pages']['/process']={'title':'SCADA','viewPath':'Pages/Scada/Overview'};config['pages']['/demo/health']={'title':'Demo health','viewPath':'Pages/Health'};config['pages']['/settings']={'title':'Settings','viewPath':'Pages/Settings'}
config['pages']['/observatory']['viewPath']='Pages/Observatory';config['pages']['/makeramaigreatagain']['viewPath']='Pages/MakeRamaiGreatAgain'
config['pages']['/oee']={'title':'Performance','viewPath':'Pages/Performance'};config['pages']['/demo/input-fields']={'title':'Batch output','viewPath':'Pages/Operator'}
nav_docks=config.get('sharedDocks', {})
if not nav_docks.get('left'):
    nav_docks=next((p.get('docks') for p in config['pages'].values() if p.get('docks',{}).get('left')), {})
for route,definition in config['pages'].items():
    definition.pop('docks', None)
config['sharedDocks']=copy.deepcopy(nav_docks)
for dock in config['sharedDocks'].get('left',[]):
    if dock.get('id')=='sidenav':dock['viewPath']='Docks/Sidenav'
# A slim header dock on every page: where you are, and the session-wide label switch.
titles={route:definition.get('title','') for route,definition in config['pages'].items()}
where=label('Where','','Hmi/HeaderWhere');where['position']['grow']=1;where['propConfig']={'props.text':bind_script('page.props.path','\ttitles = system.util.jsonDecode('+json.dumps(json.dumps(titles))+')\n\treturn "OATMAKERS / " + titles.get(value, "").upper()')}
switch=node('ia.input.toggle-switch','LabelSwitch',{'selected':True})
switch['propConfig']={'props.selected':{'binding':{'type':'property','config':{'path':'session.custom.showLabels','bidirectional':True}}}}
view('Docks/Header',theme_root(flex('root',[where,flex('Labels',[label('Caption','Labels','Demo/Muted'),switch],'row','Hmi/LabelToggle')],'row','Hmi/HeaderDock')),height=40)
config['sharedDocks']['top']=[{'anchor':'fixed','autoBreakpoint':0,'content':'push','handle':'hide','iconUrl':'','id':'header','modal':False,'resizable':False,'show':'visible','size':40,'viewParams':{},'viewPath':'Docks/Header'}]
write(P/'page-config/config.json',config)
write(P/'session-props/props.json',{'custom':{'showLabels':True,'demo':{'scadaLine':1,'scadaArea':'peeling','scadaMetric':'temperature'},'theme':'standard'},'props':{'theme':'light'}});resource(P/'session-props',['props.json'])
# Views live in Pages (one per route), Templates (embedded), Popups and Docks.
# The generator used to write everything under Demo/; remove what is left of it.
for old in ['Demo','Sidenav']:
    if (V/old).exists():shutil.rmtree(V/old)

css='''
/* High-performance HMI (ISA-101): a low-contrast grey canvas, process content in
   greyscale, and colour spent only where it means something is abnormal. The
   accent below is for interaction affordances, never for a healthy process. */
:root {
  --demo-ink:#23282d; --demo-muted:#6d757c; --demo-bg:#e9ecee; --demo-line:#d3d8dc;
  --demo-surface:#f6f7f8; --demo-accent:#3f5a73;
  --demo-alarm:#b23b34; --demo-warn:#b57a17; --demo-info:#4a6f96;
}
.psc-Demo\\/Page { container-type:inline-size; container-name:demo; background:var(--demo-bg); color:var(--demo-ink); padding:24px 30px; gap:18px; overflow:auto; font-family:Arial,sans-serif; }
.psc-Demo\\/PageHeader { align-items:center; justify-content:space-between; gap:20px; overflow:visible; }
.psc-Demo\\/PageTitle { font-size:28px; font-weight:700; line-height:1.3; padding:4px 0; white-space:normal; }
.psc-Demo\\/Eyebrow { font-size:10px; font-weight:700; letter-spacing:1.3px; color:var(--demo-muted); }
.psc-Demo\\/Subtitle { font-size:13px; color:var(--demo-muted); line-height:1.5; white-space:normal; }
.psc-Demo\\/SectionTitle { font-size:17px; font-weight:700; white-space:normal; }
.psc-Demo\\/Body { font-size:14px; line-height:1.5; white-space:normal; }
.psc-Demo\\/Muted { font-size:12px; color:var(--demo-muted); line-height:1.5; white-space:normal; }
.psc-Demo\\/Panel { background:var(--demo-surface); border:1px solid var(--demo-line); border-radius:6px; padding:20px; gap:12px; min-width:0; overflow:visible; }
.psc-Demo\\/Metric { background:var(--demo-surface); border:1px solid var(--demo-line); border-radius:6px; padding:18px 20px; gap:10px; height:100%; box-sizing:border-box; }
.psc-Demo\\/MetricReading { align-items:baseline; gap:8px; }
/* The reading is the loudest thing on a high-performance screen -- by contrast,
   not by hue. */
.psc-Demo\\/MetricValue { font-size:32px; font-weight:700; font-variant-numeric:tabular-nums; color:var(--demo-ink); }
.psc-Demo\\/MetricUnit { font-size:14px; color:var(--demo-muted); }
.psc-Demo\\/Repeater { gap:14px; overflow:visible; }
.psc-Demo\\/Wrap,.psc-Demo\\/Workspace { gap:18px; align-items:stretch; overflow:visible; }
.psc-Demo\\/Filters { gap:10px; align-items:center; min-height:44px; overflow:visible !important; position:relative; z-index:4; }
.psc-Demo\\/Select { height:40px; min-height:40px; border-radius:4px; border-color:var(--demo-line); background:#fff; font-size:13px; overflow:visible; }
.psc-Demo\\/DateRange { min-height:40px; overflow:visible !important; --dtrp-accent:var(--demo-accent); --dtrp-bg:#fff; }
.psc-Demo\\/HistoryRoot { overflow:visible; gap:10px; min-height:0; }
.psc-Demo\\/PopupRoot { overflow:visible !important; background:var(--demo-surface); padding:20px; gap:14px; min-height:0; }
.psc-Demo\\/DemoBadge { padding:7px 12px; border-radius:4px; background:#dfe3e6; color:#4d555c; font-size:10px; letter-spacing:1px; }
.psc-Demo\\/LiveStatus { font-size:12px; color:var(--demo-muted); }
.psc-Demo\\/Status { padding:10px; border-radius:4px; font-size:12px; color:var(--demo-ink); white-space:normal; }
.psc-Demo\\/Button { background:var(--demo-accent); color:#fff; border:1px solid var(--demo-accent); border-radius:4px; padding:8px 16px; font-weight:600; }
.psc-Demo\\/Button:disabled { background:#d7dbde; border-color:#d7dbde; color:#8b9198; }
.psc-Demo\\/QuietButton,.psc-Demo\\/ReadingButton { background:#fff; color:var(--demo-ink); border:1px solid var(--demo-line); border-radius:4px; padding:8px 12px; font-size:12px; }
.psc-Demo\\/ReadingButton { font-variant-numeric:tabular-nums; }
.psc-Demo\\/Badge { padding:5px 8px; border-radius:3px; background:#dfe3e6; font-size:11px; font-weight:700; }
.psc-Demo\\/Spread { justify-content:space-between; align-items:center; gap:8px; }
.psc-Demo\\/LineValue { font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; color:var(--demo-ink); }
.psc-Demo\\/Chart { font-size:11px; min-width:0; }
.psc-Demo\\/DataGrid { --dg-accent:var(--demo-accent); --dg-bg:#fff; --dg-header-bg:#eceff1; --dg-border:var(--demo-line); --dg-text:var(--demo-ink); --dg-muted:var(--demo-muted); border:1px solid var(--demo-line); border-radius:4px; min-height:180px; }
.psc-Demo\\/PlanningTimeline { --tml-accent:var(--demo-accent); --tml-bg:#fff; --tml-group-bg:#eceff1; --tml-border:var(--demo-line); --tml-line:#e4e8ea; --tml-text:var(--demo-ink); border:1px solid var(--demo-line); border-radius:6px; background:#fff; }
.psc-Demo\\/ScadaPage { overflow:hidden; background:#c5c7c9; }
.psc-Demo\\/ScadaWorkspace { gap:12px; min-height:0; align-items:stretch; }
.psc-Demo\\/ScadaMap.mustry-panzoom { border:0; border-radius:0; --pz-canvas:#c5c7c9; --pz-bg:#c5c7c9; --pz-accent:#343b40; --pz-alert:var(--demo-alarm); }
.psc-Demo\\/ScadaMap .mustry-pz-content { background:transparent; box-shadow:none; border:0; }
.psc-Demo\\/ScadaTrendPanel { gap:4px; padding:8px 0 0; border-top:1px solid #a8aeb3; min-width:0; min-height:250px; }
.psc-Demo\\/ScadaState { font-size:12px; font-weight:700; margin-left:auto; }
.psc-Demo\\/TagFace { background:transparent; border:0; border-radius:0; padding:3px 6px; gap:2px; cursor:pointer; box-sizing:border-box; overflow:visible; }
.psc-Demo\\/TagFace:hover { outline:1px solid #8d979f; outline-offset:2px; }
.psc-Demo\\/TagName { font-size:15px; font-weight:600; color:#434b51; }
.psc-Demo\\/TagValue { font-size:26px; font-weight:700; font-variant-numeric:tabular-nums; color:#333399; }
.psc-Demo\\/PvLabel { font-size:12px; font-weight:700; color:#333399; }
.psc-Demo\\/SpLabel,.psc-Demo\\/SpValue { font-size:15px; color:#006400; font-variant-numeric:tabular-nums; }
.psc-Demo\\/TagUnit { font-size:13px; color:#515b63; }
.psc-Demo\\/TagCondition { font-size:12px; font-weight:700; color:#865900; }
.psc-Demo\\/BrandLogo { background:#f2f3f1; padding:8px; margin-bottom:8px; }
@container demo (max-width:1000px) { .psc-Demo\\/ScadaPage { overflow:auto; } .psc-Demo\\/ScadaWorkspace { flex-wrap:wrap !important; flex-shrink:0 !important; } .psc-Demo\\/ScadaMap { flex-basis:100% !important; min-height:500px !important; } .psc-Demo\\/ScadaTrendPanel { flex-basis:300px !important; min-height:300px; } }
.psc-Demo\\/Navigation { background:#2b3238; padding:28px 16px 20px; gap:9px; color:#dde1e4; height:100%; box-sizing:border-box; font-family:Arial,sans-serif; }
.psc-Demo\\/Brand { font-size:24px; font-weight:800; letter-spacing:1.2px; color:#f2f4f5; padding:0 9px; }
.psc-Demo\\/NavEyebrow { font-size:9px; letter-spacing:1.3px; color:#a6aeb4; padding:0 9px; }
.psc-Demo\\/NavBadge { font-size:9px; color:#c8ced3; background:#3a434a; padding:9px; border-radius:3px; margin:15px 0; }
.psc-Demo\\/NavButton { background:transparent; color:#d5dade; border:0; border-radius:4px; padding:10px 12px; font-size:12px; text-align:left; }
/* The button centres its icon and text inline; menu items read better left-aligned. */
.psc-Demo\\/NavButton > div { width:100%; justify-content:flex-start !important; gap:10px; }
.psc-Demo\\/NavButton .text { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.psc-Demo\\/NavButton:hover { background:#3d474f; }
.psc-Demo\\/NavFooter { font-size:10px; color:#98a1a8; padding:4px 9px; }
@container demo (max-width:900px) { .psc-Demo\\/Workspace { flex-wrap:wrap !important; } .psc-Demo\\/Workspace > * { flex-basis:100% !important; } .psc-Demo\\/PageHeader { flex-wrap:wrap !important; } }
@media(max-width:650px) { .psc-Demo\\/Page { padding:14px; } .psc-Demo\\/PageTitle { font-size:24px; } .psc-Demo\\/Filters { flex-wrap:wrap !important; } }

/* Hello Kitty theme: the root of every page, popup and the navigation carries
   Theme/HelloKitty when the session chooses it on the settings page. */
.psc-Theme\\/HelloKitty {
  --demo-ink:#3b3038; --demo-muted:#75606d; --demo-bg:#fff5f8;
  --demo-line:#edc9d6; --demo-surface:#fff; --demo-accent:#ac2454;
  --demo-alarm:#b23b34; --demo-warn:#956000; --demo-info:#246b80;
  font-family:"Trebuchet MS","Verdana",sans-serif; letter-spacing:0;
}
.psc-Theme\\/HelloKitty.psc-Demo\\/Page {
  background-color:var(--demo-bg);
  background-image:repeating-linear-gradient(0deg,transparent,transparent 31px,#f9e6ed 31px,#f9e6ed 32px);
  padding:24px 28px; gap:18px; font-family:"Trebuchet MS","Verdana",sans-serif;
}
.psc-Theme\\/HelloKitty .psc-Demo\\/PageHeader { border-bottom:2px solid #edb3c8; padding-bottom:16px; gap:16px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/PageTitle { font-size:27px; color:#8d2149; line-height:1.3; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Eyebrow,.psc-Theme\\/HelloKitty .psc-Demo\\/NavEyebrow,.psc-Theme\\/HelloKitty .psc-Demo\\/NavBadge,
.psc-Theme\\/HelloKitty .psc-Demo\\/DemoBadge,.psc-Theme\\/HelloKitty .psc-Demo\\/Brand { letter-spacing:0; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Eyebrow { color:#8d3655; font-size:11px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/SectionTitle { color:#713048; font-size:17px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Metric { border-radius:8px; border-top:3px solid #dc779b; padding:18px; background:#fff; box-shadow:0 2px 0 #f4dce6; }
.psc-Theme\\/HelloKitty .psc-Demo\\/MetricValue { font-size:32px; color:#70203f; }
.psc-Theme\\/HelloKitty .psc-Demo\\/MetricUnit { color:#75606d; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Panel { border:0; border-top:1px solid var(--demo-line); border-radius:0; padding:18px 0; background:transparent; box-shadow:none; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Repeater .psc-Demo\\/Panel { background:#fff; border:1px solid var(--demo-line); border-radius:8px; border-top:3px solid #d990ac; padding:18px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/LineValue { color:#70203f; font-size:28px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/DemoBadge,.psc-Theme\\/HelloKitty .psc-Demo\\/Badge { background:#fbe2ec; color:#772343; border-radius:4px; white-space:normal; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Button { background:#ac2454; border-color:#ac2454; border-radius:6px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Button:hover:enabled { background:#8d2149; }
.psc-Theme\\/HelloKitty .psc-Demo\\/QuietButton,.psc-Theme\\/HelloKitty .psc-Demo\\/ReadingButton { border-color:#e4b7c8; color:#713048; background:#fff; border-radius:6px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/QuietButton:hover,.psc-Theme\\/HelloKitty .psc-Demo\\/ReadingButton:hover { background:#fce5ee; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Button:focus-visible,.psc-Theme\\/HelloKitty .psc-Demo\\/NavButton:focus-visible,
.psc-Theme\\/HelloKitty .psc-Demo\\/QuietButton:focus-visible,.psc-Theme\\/HelloKitty .psc-Demo\\/ReadingButton:focus-visible { outline:3px solid #246b80; outline-offset:2px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Select { border-color:#ddb0c2; border-radius:6px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/DataGrid { --dg-header-bg:#fbe8ef; border-radius:6px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/PlanningTimeline { --tml-group-bg:#fbe8ef; border-radius:6px; }
.psc-Theme\\/HelloKitty.psc-Demo\\/Navigation { background:#fff; color:#713048; border-right:1px solid #edc9d6; padding:20px 14px; gap:8px; font-family:"Trebuchet MS","Verdana",sans-serif; }
.psc-Theme\\/HelloKitty .psc-Demo\\/BrandLogo { background:transparent; padding:0; margin:0; }
.psc-Theme\\/HelloKitty .psc-Demo\\/NavEyebrow { color:#75606d; font-size:11px; padding:0 10px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/NavBadge { color:#8d2149; background:#fce5ee; margin:8px 0; padding:9px 10px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/NavButton { color:#713048; border-radius:6px; font-size:13px; padding:10px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/NavButton:hover { background:#fce5ee !important; }
.psc-Theme\\/HelloKitty .psc-Demo\\/NavFooter { color:#75606d; white-space:normal; }
.psc-Theme\\/HelloKitty.psc-Demo\\/PopupRoot { background:#fff5f8; }
.psc-Theme\\/HelloKitty .psc-Hmi\\/PanZoom.mustry-panzoom { --pz-bg:#fff5f8; --pz-accent:#ac2454; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu { color:#713048; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .menu-wrapper,.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .wrapper-submenu { background:#fff !important; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__item { border-radius:6px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__item:hover { background:#fce5ee; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__item__text { color:#713048; font-size:13px; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__item__icon,.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__item__navIcon,
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__header__icon,.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__backAction svg { fill:#ac2454; color:#ac2454; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__header { color:#8d2149; border-bottom-color:#edc9d6; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__backAction { color:#75606d; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .ia_menuTreeComponent__backAction:hover { color:#8d2149; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .psc-Demo\\/MenuActive { background:#f9d7e5; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .psc-Demo\\/MenuActive .ia_menuTreeComponent__item__text,.psc-Theme\\/HelloKitty .psc-Demo\\/Menu .psc-Demo\\/MenuTrail .ia_menuTreeComponent__item__text { color:#70203f; }
.psc-Theme\\/HelloKitty .psc-Demo\\/PageHeader > * { min-width:0; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Filters { flex-wrap:wrap !important; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Filters > *,.psc-Theme\\/HelloKitty .psc-Demo\\/Workspace > * { max-width:100%; min-width:0; }
.psc-Theme\\/HelloKitty .psc-Demo\\/Workspace { flex-wrap:wrap; }
@media(max-width:650px) { .psc-Theme\\/HelloKitty.psc-Demo\\/Page { padding:14px; } .psc-Theme\\/HelloKitty .psc-Demo\\/PageTitle { font-size:23px; } .psc-Theme\\/HelloKitty .psc-Demo\\/DemoBadge { font-size:10px; } }
'''
p=P/'stylesheet';(p/'stylesheet.css').write_text(css+SCADA_CSS);resource(p,['stylesheet.css'])
print('Built operational screens with Mustry UI, drill-down SCADA and range-controlled history.')
