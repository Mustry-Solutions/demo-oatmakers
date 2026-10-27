"""Build the OatMill UDTs and one tag instance per instrument, drive, valve and silo on the SCADA screens.

The gateway timer writes the simulated process values into these memory tags
every second (application.demo.tick); the screens bind to the tags.
"""
import ast,json,re,shutil
from view_primitives import ROOT

TAGS=ROOT/'services/config/resources/core/ignition'
CODE=ROOT/'projects/oatmakers/ignition/script-python/application/demo/code.py'
# Alarm limits for the measurements that the line telemetry drives; the
# simulated areas alarm outside four times their normal swing.
LIMITS={'temperature':(55.0,86.0),'moisture':(10.5,13.0)}


def model():
    source=CODE.read_text(encoding='utf-8')
    return ast.literal_eval(re.search(r'\nSCADA = (\{.*?\n\})\n',source,re.S).group(1))


def param(value):
    return {'dataType':{str:'String',int:'Int4',float:'Float8'}[type(value)],'value':value}


def member(name,dataType,**config):
    return dict({'name':name,'tagType':'AtomicTag','valueSource':'memory','dataType':dataType},**config)


def udt(name,params,tags):
    return {'name':name,'tagType':'UdtType','parameters':{k:param(v) for k,v in params.items()},'tags':tags}


UDTS=[
 udt('AnalogInput',{'Description':'','Signal':'','Unit':'','Decimals':1},[
  member('PV','Float8',engUnit='{Unit}',documentation='{Description}',formatString='#,##0.##'),
  member('LowLimit','Float8',engUnit='{Unit}',value=0.0),member('HighLimit','Float8',engUnit='{Unit}',value=100.0),
  member('Alarm','Boolean',valueSource='expr',expression='{[.]PV} < {[.]LowLimit} || {[.]PV} > {[.]HighLimit}')]),
 udt('Motor',{'Description':'','Signal':'','RatedCurrent':10.0,'Duty':'Duty'},[
  member('Running','Boolean'),member('Fault','Boolean'),member('Mode','String',value='Auto'),
  member('Current','Float8',engUnit='A',documentation='{Description} current')]),
 udt('Valve',{'Description':'','Signal':''},[
  member('Open','Boolean'),member('Position','Float8',engUnit='%',documentation='{Description} position')]),
 udt('Silo',{'Description':'','Signal':'','Product':'','Capacity':60},[
  member('Level','Float8',engUnit='%',documentation='{Description} level'),
  member('Content','Float8',valueSource='expr',engUnit='t',expression='{[.]Level} * {Capacity} / 100')]),
 udt('ProcessArea',{'Title':''},[
  member('State','String',value='Starting'),member('Running','Boolean'),member('LastUpdate','DateTime')]),
]


def folder(path,files,content=None):
    path.mkdir(parents=True,exist_ok=True)
    (path/'unary-resource.json').write_text(json.dumps({'scope':'G','version':1,'restricted':False,'overridable':True,
        'files':files,'attributes':{'config':{}}},indent=2))
    if content is not None:
        (path/files[0]).write_text(json.dumps(content,indent=2,ensure_ascii=False)+'\n')


def build_tags(area_tags):
    signals=model()
    folder(TAGS/'tag-type-definition/default/OatMill',['udts.json'],UDTS)
    root=TAGS/'tag-definition/default/OatMill'
    shutil.rmtree(root,ignore_errors=True)
    folder(root,[])
    for area,tags in area_tags.items():
        spec=signals[area]['signals']
        live=signals[area]['line']>0
        covered=set()
        for tag in tags.values():
            params=tag['parameters']
            if tag['typeId'] in ('OatMill/AnalogInput','OatMill/Silo'):
                signal=params['Signal']['value']
                assert signal in spec,(area,tag['name'],signal)
                covered.add(signal)
            if tag['typeId']=='OatMill/AnalogInput':
                base,amplitude,_period=spec[signal]
                low,high=LIMITS.get(signal) if live and signal in LIMITS else (base-4*amplitude,base+4*amplitude)
                if live and signal not in LIMITS:low,high=-1e9,1e9
                # Limits are per-instance member values, so an engineer can tune them on the tag.
                tag['tags']=[{'name':'HighLimit','tagType':'AtomicTag','value':float(round(high,3))},
                             {'name':'LowLimit','tagType':'AtomicTag','value':float(round(low,3))}]
        missing=set(spec)-covered
        assert not missing,(area,sorted(missing))
        folder(root/area.title(),['udts.json'],sorted(tags.values(),key=lambda t:t['name']))
