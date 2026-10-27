"""Build the oat mill SCADA: a plant overview and drill-down process area screens."""
import base64,json
from html import escape
from view_primitives import *

W,H=1740,910
INK='#565957'
STEAM='#c9a54e'
AIR='#8f9599'
WATER='#93bcd1'
GAS='#b3a4c9'
METAL='#d7d9d8'
EDGE='#666a68'
ON='#a7dfa5'
OFF='#b3b3b3'
HMI='Demo/Hmi/'

# Process order drives the previous/next buttons and the menu.
AREAS=[
 ('intake','/scada/intake','Intake & raw oat silos','Receiving','Truck intake, pre-cleaning and four raw oat silos.'),
 ('cleaning','/scada/cleaning','Cleaning','Receiving','Sieving, aspiration, destoning, length grading and optical sorting.'),
 ('dehulling','/scada/dehulling','Dehulling','Groat processing','Impact hulling, hull aspiration and groat separation.'),
 ('kiln','/scada/kiln','Kilning & stabilisation','Groat processing','Steam and heat inactivate the lipase enzyme, then the groats are cooled and graded.'),
 ('flaking','/scada/flaking','Line 01 · Steaming & flaking','Production lines','Rolled oats: steaming, flaking rolls, drying and cooling.'),
 ('cutting','/scada/cutting','Line 02 · Groat cutting','Production lines','Steel-cut oats: conditioning, granulators and size grading.'),
 ('milling','/scada/milling','Line 03 · Oat flour milling','Production lines','Oat flour and bran: heat treatment, hammer mill and plansifter.'),
 ('packing','/scada/packing','Packing & palletising','Finished goods','Retail packs and 25 kg sacks, checkweighing, metal detection and palletising.'),
 ('utilities','/scada/utilities','Steam & compressed air','Utilities','Boiler house, steam distribution and compressed air.'),
]
ROUTE={k:r for k,r,*_ in AREAS}
TITLE={k:t for k,_,t,*_ in AREAS}

def b64(markup):return 'data:image/svg+xml;base64,'+base64.b64encode(markup.encode()).decode()
def svg(body,w,h):return '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">%s</svg>'%(w,h,w,h,body)
def image(name,source,alt):
    return node('ia.display.image',name,{'source':source,'altText':alt,'fit':{'mode':'fill'},'style':{'pointerEvents':'none'}})
def at(n,x,y,w,h):
    n['position']={'x':x,'y':y,'width':w,'height':h};return n
def bind(path):return {'binding':{'type':'property','config':{'path':path}}}
def script_expr(expression,code):return {'binding':{'type':'expr','config':{'expression':expression},'transforms':[{'type':'script','code':code}]}}
def click(script):return {'dom':{'onClick':{'type':'script','scope':'G','config':{'script':script}}}}
def clickable(children,script,cursor='pointer'):
    root=node('ia.container.coord','root',{'mode':'percent','style':{'cursor':cursor}},children);root['events']=click(script);return root
def full(n):
    n['position']={'x':0,'y':0,'width':1,'height':1};return n

# Valves and pumps share the separator's flow axis (y=48 in an 88 high box).
# Compact symbols (motors, fans, rotary valves) are centred on (20,30) with
# their tag to the right, so they sit on a pipe in either direction.
def symbol(kind,active,tag,w=78,h=88):
    fill=ON if active else OFF
    body=''
    if kind in ('block','control','pump'):
        cx,cy=w/2.0,48.0
        if kind=='pump':
            body+='<circle cx="%s" cy="%s" r="21" fill="#c0dfb8" stroke="#555" stroke-width="2"/>'%(cx,cy) if active else '<circle cx="%s" cy="%s" r="21" fill="%s" stroke="#555" stroke-width="2"/>'%(cx,cy,OFF)
            for r in (0,90,180,270):
                body+='<path d="M%s %s q-22 -20 -9 -19 q15 -3 13 14 Z" transform="rotate(%d %s %s)" fill="%s"/>'%(cx,cy,r,cx,cy,'#548455' if active else '#7c7f7d')
            body+='<circle cx="%s" cy="%s" r="5" fill="#555"/><text x="%s" y="17" font-size="12">M</text>'%(cx,cy,w-15)
        else:
            body+='<path d="M%s %s L%s %s V%s L%s %s Z" fill="%s" stroke="#555" stroke-width="1.6"/>'%(cx-15,cy-8,cx+15,cy+8,cy-8,cx-15,cy+8,fill)
            body+='<path d="M%s %s V%s" stroke="#555" stroke-width="1.4"/>'%(cx,cy-22,cy)
            if kind=='control':
                body+='<path d="M%s %s a14 12 0 0 1 28 0 Z" fill="%s" stroke="#555" stroke-width="1.4"/><text x="%s" y="%s" font-size="12">A</text>'%(cx-14,cy-22,fill,cx+20,cy-23)
            else:
                body+='<rect x="%s" y="%s" width="20" height="12" fill="%s" stroke="#555" stroke-width="1.4"/><path d="M%s %s h20 M%s %s v12" stroke="#555"/>'%(cx-10,cy-34,fill,cx-10,cy-28,cx,cy-34)
        body+='<text x="%s" y="%s" text-anchor="middle" font-size="12" font-weight="600">%s</text>'%(cx,h-5,escape(tag))
    else:
        cx,cy=20,30
        if kind=='motor':
            body+='<circle cx="%s" cy="%s" r="15" fill="%s" stroke="#555" stroke-width="1.6"/><text x="%s" y="%s" text-anchor="middle" font-size="13" font-weight="700">M</text>'%(cx,cy,fill,cx,cy+5)
        elif kind=='fan':
            body+='<circle cx="%s" cy="%s" r="17" fill="%s" stroke="#555" stroke-width="1.6"/>'%(cx,cy,fill)
            for r in (0,120,240):
                body+='<path d="M%s %s q-3 -12 7 -13 q4 6 -7 13 Z" transform="rotate(%d %s %s)" fill="#555"/>'%(cx,cy,r,cx,cy)
        else:
            body+='<circle cx="%s" cy="%s" r="14" fill="%s" stroke="#555" stroke-width="1.6"/><path d="M%s %s h28 M%s %s v28 M%s %s l20 20 M%s %s l-20 20" stroke="#555" stroke-width="1"/>'%(cx,cy,fill,cx-14,cy,cx,cy-14,cx-10,cy-10,cx+10,cy-10)
        body+='<text x="42" y="34" font-size="12" font-weight="600">%s</text>'%escape(tag)
    return svg('<g font-family="Arial" fill="#555">'+body+'</g>',w,h)

def stream_svg(text,w,target):
    fill='#3f5a73' if target else '#595c5a'
    body='<path d="M0 0 H%s a14 14 0 0 1 0 28 H0 Z" fill="%s"/>'%(w-14,fill)
    body+='<circle cx="%s" cy="14" r="9" fill="#cdd0cd"/><path d="M%s 8 l7 6 -7 6 Z" fill="#60645f"/>'%(w-14,w-17)
    body+='<text x="%s" y="18" text-anchor="middle" font-family="Arial" font-size="10.5" fill="white">%s</text>'%((w-25)/2,escape(text))
    return svg(body,w,28)

def components():
    graphic=full(image('Graphic','','Instrument'))
    graphic['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tag':'{view.params.tag}','kind':'{view.params.kind}','value':'{view.params.value}','colour':'{view.params.colour}'}},'transforms':[{'type':'script','code':'\treturn application.demo.scadaInstrumentSvg(value["tag"], value["kind"], value["value"], value["colour"])'}]}}}
    detail='\tp = self.view.params\n\tif p.signal:\n\t\tapplication.demo.showScadaDetail(p.area, p.tag, p.signal, p.unit, p.decimals)'
    view(HMI+'Instrument',clickable([graphic],detail),params={'area':'intake','tag':'TI101','kind':'TI','signal':'','unit':'','decimals':1,'value':'--','colour':'#f7f7f7'},height=51)
    device=full(image('Graphic','','Equipment'))
    device['propConfig']={'props.source':{'binding':{'type':'expr','config':{'expression':'if({view.params.running}, {view.params.on}, {view.params.off})'}}}}
    root=clickable([device],'\tp = self.view.params\n\tif p.signal:\n\t\tapplication.demo.showScadaDetail(p.area, p.tag, p.signal, p.unit, p.decimals)')
    view(HMI+'Device',root,params={'area':'intake','tag':'M101','signal':'','unit':'','decimals':1,'running':True,'on':'','off':''},height=88)
    # Connected streams navigate to the area that supplies or receives them.
    link=full(image('Graphic','','Stream'));link['propConfig']={'props.source':bind('view.params.source')}
    root=clickable([link],'\tif self.view.params.target:\n\t\tsystem.perspective.navigate(self.view.params.target)')
    root['propConfig']={'props.style.cursor':{'binding':{'type':'expr','config':{'expression':'if(len({view.params.target}) > 0, "pointer", "default")'}}}}
    view(HMI+'Stream',root,params={'source':'','target':''},height=28)
    trend=full(image('Plot','','Trend'))
    trend['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(2000)','area':'{view.params.area}','signal':'{view.params.signal}','colour':'{view.params.colour}','sp':'{view.params.sp}'}},'transforms':[{'type':'script','code':'\treturn application.demo.scadaTrendSvg(value["area"], value["signal"], value["colour"], value["sp"])'}]}}}
    view(HMI+'Trend',node('ia.container.coord','root',{'mode':'percent'},[trend]),params={'area':'intake','signal':'','colour':'#626b75','sp':0},height=70)
    silo=full(image('Graphic','','Silo'))
    silo['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'level':'{view.params.level}','product':'{view.params.product}'}},'transforms':[{'type':'script','code':'\treturn application.demo.scadaSiloSvg(value["level"], value["product"])'}]}}}
    view(HMI+'Silo',clickable([silo],'\tp = self.view.params\n\tapplication.demo.showScadaDetail(p.area, p.tag, p.signal, "%", 0)'),params={'area':'intake','tag':'SI101','signal':'','level':0,'product':''},height=330)
    tile=full(image('Graphic','','Process area'))
    tile['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(2000)','area':'{view.params.area}'}},'transforms':[{'type':'script','code':'\treturn application.demo.scadaTileSvg(value["area"])'}]}}}
    view(HMI+'Tile',clickable([tile],'\tsystem.perspective.navigate(self.view.params.route)'),params={'area':'intake','route':'/scada/intake'},height=170)
    value=label('Value','','Hmi/DetailValue')
    value['propConfig']={'props.text':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(1000)','area':'{view.params.area}','signal':'{view.params.signal}','unit':'{view.params.unit}','decimals':'{view.params.decimals}'}},'transforms':[{'type':'script','code':'\treturn application.demo.scadaDetailValue(value["area"], value["signal"], value["unit"], value["decimals"])'}]}}}
    plot=embed('Trend',HMI+'Trend',{'colour':'#626b75','sp':0},basis='160px')
    plot['propConfig']={'props.params.area':bind('view.params.area'),'props.params.signal':bind('view.params.signal')}
    caption=label('Caption','','Demo/Muted');caption['propConfig']={'props.text':script_expr('{view.params.area}','\treturn application.demo.scadaAreaTitle(value) + " | recent trend"')}
    view(HMI+'Detail',flex('root',[bound_label('Title','view.params.tag','Demo/SectionTitle'),label('Mode','Read-only process simulation','Demo/Muted'),value,plot,caption],classes='Demo/PopupRoot'),params={'area':'intake','tag':'','signal':'','unit':'','decimals':1},height=300)


class Scene:
    """One process drawing in fixed design coordinates: static vector layers with live views between them."""
    def __init__(self,area):
        self.area=area;self.under=[];self.parts=[];self.over=[]
    def pipe(self,d,colour=INK,width=1.8,dash=None):
        self.under.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round"%s/>'%(d,colour,width,(' stroke-dasharray="%s"'%dash) if dash else ''))
    def steam(self,d):self.pipe(d,STEAM,1.7)
    def air(self,d):self.pipe(d,AIR,1,'4 3')
    def text(self,x,y,t,size=12,weight=400,anchor='middle',fill='#555',layer=None):
        halo=' stroke="#e6e6e6" stroke-width="4" paint-order="stroke"' if layer is self.over else ''
        (self.under if layer is None else layer).append('<text x="%s" y="%s" font-family="Arial" font-size="%s" font-weight="%s" text-anchor="%s" fill="%s"%s>%s</text>'%(x,y,size,weight,anchor,fill,halo,escape(t)))
    def name(self,x,y,tag,title):
        if tag:self.text(x,y,tag,12,600,layer=self.over)
        if title:self.text(x,y+14,title,10.5,400,fill='#777',layer=self.over)
    def shape(self,body):self.under.append('<g fill="%s" stroke="%s" stroke-width="1.4">%s</g>'%(METAL,EDGE,body))
    # Static equipment outlines, ISA-101 greyscale.
    def bin(self,x,y,w,h,tag,title):
        b=y+h*0.7
        self.shape('<path d="M%s %s H%s V%s L%s %s H%s L%s %s Z"/>'%(x,y,x+w,b,x+w/2+10,y+h,x+w/2-10,x,b))
        self.name(x+w/2,y+h*0.42,tag,title)
    def conveyor(self,x,y,w,tag,title,kind='chain'):
        inner=''.join('<path d="M%s %s l6 12 l6 -12" fill="none" stroke-width="1"/>'%(x+14+i*12,y+4) for i in range(int((w-28)/12))) if kind=='screw' else '<circle cx="%s" cy="%s" r="7"/><circle cx="%s" cy="%s" r="7"/>'%(x+11,y+10,x+w-11,y+10)
        self.shape('<rect x="%s" y="%s" width="%s" height="20" rx="10"/>%s'%(x,y,w,inner))
        self.name(x+w/2,y+36,tag,title)
    def elevator(self,x,top,bottom,tag,title):
        self.shape('<rect x="%s" y="%s" width="30" height="%s"/><path d="M%s %s h50 v34 h-50 Z"/><path d="M%s %s h46 v26 h-46 Z"/>'%(x,top+34,bottom-top-60,x-10,top,x-8,bottom-26))
        self.shape('<path d="M%s %s V%s M%s %s V%s" stroke-dasharray="6 5" fill="none" stroke-width="1"/>'%(x+9,top+40,bottom-30,x+21,top+40,bottom-30))
        self.name(x-46,(top+bottom)/2,tag,title)
    def sieve(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="4"/>'%(x,y,w,h)+''.join('<path d="M%s %s L%s %s" fill="none" stroke-dasharray="5 3" stroke-width="1"/>'%(x+10,y+h*f,x+w-10,y+h*f+16) for f in (0.25,0.5,0.75)))
        self.name(x+w/2,y+h+18,tag,title)
    def aspirator(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="4"/><path d="M%s %s l%s 20 l-%s 20 l%s 20 l-%s 20" fill="none" stroke-width="1"/><path d="M%s %s v-36 m-6 8 l6 -8 l6 8" fill="none" stroke-width="1.2"/>'%(x,y,w,h,x+w*0.3,y+h*0.3,w*0.4,w*0.4,w*0.4,w*0.4,x+w*0.75,y+h*0.55))
        self.name(x+w/2,y+h+18,tag,title)
    def deck(self,x,y,w,h,tag,title):
        self.shape('<path d="M%s %s L%s %s V%s L%s %s Z"/><path d="M%s %s V%s M%s %s V%s" fill="none"/>'%(x,y+h*0.2,x+w,y,y+h*0.45,x,y+h*0.65,x+20,y+h*0.62,y+h,x+w-20,y+h*0.42,y+h))
        self.name(x+w/2,y+h+18,tag,title)
    def drum(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="%s"/><path d="M%s %s H%s" fill="none" stroke-dasharray="3 4" stroke-width="1"/>'%(x,y,w,h,h/2,x+h/2,y+h/2,x+w-h/2))
        self.name(x+w/2,y+h+18,tag,title)
    def huller(self,cx,cy,r,tag,title):
        self.shape('<circle cx="%s" cy="%s" r="%s"/><circle cx="%s" cy="%s" r="%s" fill="#c9cbca"/>'%(cx,cy,r,cx,cy,r*0.55)+''.join('<path d="M%s %s l%s 0" transform="rotate(%d %s %s)" fill="none" stroke-width="3"/>'%(cx,cy,r*0.55,a,cx,cy) for a in range(0,360,45)))
        self.name(cx,cy+r+18,tag,title)
    def cyclone(self,x,y,w,h,tag,title):
        b=y+h*0.4
        self.shape('<path d="M%s %s H%s V%s L%s %s H%s L%s %s Z"/>'%(x,y,x+w,b,x+w/2+9,y+h,x+w/2-9,x,b))
        self.name(x+w+40,y+h*0.35,tag,title)
    def filter(self,x,y,w,h,tag,title):
        b=y+h*0.72
        self.shape('<path d="M%s %s H%s V%s L%s %s H%s L%s %s Z"/>'%(x,y,x+w,b,x+w/2+10,y+h,x+w/2-10,x,b)+''.join('<path d="M%s %s V%s" fill="none" stroke-width="1"/>'%(x+w*f,y+10,b-12) for f in (0.2,0.4,0.6,0.8)))
        self.name(x+w/2,y+h+18,tag,title)
    def column(self,x,y,w,h,tag,title):
        self.shape('<path d="M%s %s Q%s %s %s %s V%s L%s %s H%s L%s %s Z"/>'%(x,y+20,x+w/2,y-14,x+w,y+20,y+h-40,x+w/2+12,y+h,x+w/2-12,x,y+h-40)+''.join('<path d="M%s %s h%s" fill="none" stroke="%s" stroke-width="2.5"/>'%(x+3,y+h*f,w-6,STEAM) for f in (0.3,0.5,0.7)))
    def cooler(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="4"/>'%(x,y,w,h)+''.join('<path d="M%s %s l14 -10" fill="none" stroke-width="1"/>'%(x+12+i*22,y+h*f) for f in (0.3,0.55,0.8) for i in range(int((w-30)/22))))
        self.name(x+w/2,y+h+18,tag,title)
    def steamer(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="%s"/>'%(x,y,w,h,w/2))
        self.name(x+w/2,y+h/2,tag,title)
    def rollmill(self,x,y,w,h,tag,title):
        self.shape('<path d="M%s %s h40 l-12 18 h-16 Z"/><rect x="%s" y="%s" width="%s" height="%s" rx="4"/><circle cx="%s" cy="%s" r="%s" fill="#c9cbca"/><circle cx="%s" cy="%s" r="%s" fill="#c9cbca"/>'%(x+w/2-20,y-18,x,y,w,h,x+w/2-h*0.24,y+h*0.45,h*0.23,x+w/2+h*0.24,y+h*0.45,h*0.23))
        self.name(x+w/2,y+h+18,tag,title)
    def hammermill(self,x,y,w,h,tag,title):
        cx,cy=x+w/2,y+h/2
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="6"/><circle cx="%s" cy="%s" r="%s" fill="#c9cbca"/>'%(x,y,w,h,cx,cy,h*0.32)+''.join('<rect x="%s" y="%s" width="8" height="%s" transform="rotate(%d %s %s)" fill="#999"/>'%(cx-4,cy-h*0.3,h*0.14,a,cx,cy) for a in range(0,360,60)))
        self.name(cx,y+h+18,tag,title)
    def plansifter(self,x,y,w,h,tag,title):
        self.shape(''.join('<rect x="%s" y="%s" width="%s" height="%s"/>'%(x,y+i*h/6,w,h/6) for i in range(6)))
        self.name(x+w/2,y+h+18,tag,title)
    def beltdryer(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="4"/>'%(x,y,w,h)+''.join('<path d="M%s %s H%s" fill="none" stroke-width="2"/>'%(x+12,y+h*f,x+w-12) for f in (0.3,0.55,0.8))+''.join('<path d="M%s %s v-12 h24 v12" fill="none"/>'%(x+w*f,y) for f in (0.2,0.5,0.8)))
        self.name(x+w/2,y+h+18,tag,title)
    def weigher(self,cx,y,tag,title):
        self.shape('<path d="M%s %s L%s %s H%s Z"/><path d="M%s %s h80 l-10 30 h-60 Z"/>'%(cx,y,cx+40,y+30,cx-40,cx-40,y+34))
        self.name(cx+80,y+30,tag,title)
    def bagger(self,cx,y,tag,title):
        self.shape('<rect x="%s" y="%s" width="90" height="70" rx="4"/><circle cx="%s" cy="%s" r="14" fill="#c9cbca"/><path d="M%s %s h30 l6 34 h-42 Z" fill="#ecebe5"/>'%(cx-45,y,cx-26,y+22,cx-15,y+76))
        self.name(cx+90,y+30,tag,title)
    def boiler(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="%s"/><rect x="%s" y="%s" width="40" height="%s"/><rect x="%s" y="%s" width="22" height="60"/>'%(x,y,w,h,h/2,x-40,y+h*0.25,h*0.5,x+w-70,y-60))
        self.name(x+w/2,y+h/2+4,tag,title)
    def vessel(self,x,y,w,h,tag,title):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="%s"/>'%(x,y,w,h,min(w,h)/2))
        self.name(x+w/2,y+h+18,tag,title)
    def box(self,x,y,w,h,tag,title,inner=''):
        self.shape('<rect x="%s" y="%s" width="%s" height="%s" rx="4"/>%s'%(x,y,w,h,inner))
        self.name(x+w/2,y+h+18,tag,title)
    def frame(self,x,y,w,h,caption):
        self.under.append('<rect x="%s" y="%s" width="%s" height="%s" fill="#eeeeee" stroke="#c2c5c3"/>'%(x-4,y-4,w+8,h+8))
        self.text(x,y-10,caption,11,600,'start','#6d7270')
    # Live elements.
    def instrument(self,tag,kind,signal,unit,dec,x,y,lead=None,colour=None):
        n=embed(tag,HMI+'Instrument',{'area':self.area,'tag':tag,'kind':kind,'signal':signal,'unit':unit,'decimals':dec,'colour':colour or '#f7f7f7','value':'--'})
        fmt='\treturn u"{0:,.'+str(dec)+'f} '+unit+'".format(value or 0)' if unit else '\treturn u"{0:,.'+str(dec)+'f}".format(value or 0)'
        n['propConfig']={'props.params.value':script_expr('try({view.custom.data.'+signal+'}, 0)',fmt)}
        if lead is not None:
            self.pipe('M%s %s V%s'%(x+10,y+42 if lead>y else y+22,lead),INK,1)
        self.parts.append(at(n,x,y,130,51))
    def state(self,x,y,tag):
        n=embed('LineState',HMI+'Instrument',{'area':self.area,'tag':tag,'kind':'ST','signal':'','unit':'','decimals':0,'value':'--','colour':'#f7f7f7'})
        n['propConfig']={'props.params.value':bind('view.custom.data.state'),'props.params.colour':{'binding':{'type':'expr','config':{'expression':'case({view.custom.data.state}, "Stopped", "#f2b8b3", "Quality hold", "#f6dca6", "Recovering", "#c9d9ea", "#f7f7f7")'}}}}
        self.parts.append(at(n,x,y,130,51))
    def device(self,tag,kind,cx,cy,signal='',unit='',dec=1,running=True):
        compact=kind in ('motor','fan','rotary')
        w,h=(110,60) if compact else (78,88)
        n=embed(tag.replace('-',''),HMI+'Device',{'area':self.area,'tag':tag,'signal':signal,'unit':unit,'decimals':dec,'running':running is not False,'on':b64(symbol(kind,True,tag,w,h)),'off':b64(symbol(kind,False,tag,w,h))})
        if running=='line':n['propConfig']={'props.params.running':bind('view.custom.data.running')}
        self.parts.append(at(n,cx-20 if compact else cx-39,cy-30 if compact else cy-48,w,h))
    def silo(self,tag,signal,product,x,y,w=110,h=330):
        n=embed(tag,HMI+'Silo',{'area':self.area,'tag':tag,'signal':signal,'product':product,'level':0})
        n['propConfig']={'props.params.level':bind('view.custom.data.'+signal)}
        self.parts.append(at(n,x,y,w,h))
        self.text(x+w/2+6,y-8,tag,12,600,'start',layer=self.over)
    def stream(self,text,x,y,w=170,target=None):
        n=embed(''.join(c for c in text.title() if c.isalnum())+'Link',HMI+'Stream',{'target':ROUTE.get(target,''),'source':b64(stream_svg(text,w,target))})
        self.parts.append(at(n,x,y,w,28))
    def trend(self,signal,x,y,w,h,caption,colour='#626b75',sp=0):
        self.frame(x,y,w,h,caption)
        self.parts.append(at(embed('Trend'+signal[0].upper()+signal[1:],HMI+'Trend',{'area':self.area,'signal':signal,'colour':colour,'sp':sp}),x,y,w,h))

    def build(self,title):
        self.text(40,890,title,22,600,'start','#5a5e5c',self.over)
        self.text(1700,890,'SIMULATION',10,400,'end','#777',self.over)
        canvas=[at(image('Piping',b64(svg(''.join(self.under),W,H)),title+' piping'),0,0,W,H)]+self.parts
        canvas.append(at(image('Labels',b64(svg(''.join(self.over),W,H)),title+' labels'),0,0,W,H))
        scene=node('ia.container.coord','root',{'mode':'fixed','style':{'backgroundColor':'transparent','overflow':'visible'}},canvas);scene.pop('position',None)
        d=view(HMI+'Drawing/'+self.area.title(),scene,custom={'data':{'running':True,'state':''}},config={'custom.data':dict(script_expr('now(1000)','\treturn application.demo.scadaData('+json.dumps(self.area)+')'),persistent=True)},height=H)
        d['props']['defaultSize']['width']=W
        write(V/HMI/'Drawing'/self.area.title()/'view.json',d)


def intake():
    s=Scene('intake')
    s.stream('Raw oats by truck',38,596,160)
    s.pipe('M198 610 H280 V620');s.bin(210,620,140,110,'IP101','Intake pit')
    s.pipe('M280 730 V746');s.conveyor(250,746,250,'CV101','Intake chain conveyor');s.device('M-CV101','motor',230,810)
    s.pipe('M500 756 H520');s.elevator(520,100,800,'EL101','Bucket elevator');s.device('M-EL101','motor',540,70,'elevAmps','A',1)
    s.pipe('M570 135 H640');s.drum(640,100,170,70,'PC101','Drum pre-cleaner');s.device('M-PC101','motor',705,60)
    s.pipe('M725 170 V300 H760',INK,1.2);s.stream('To screenings bin',760,286,150)
    s.pipe('M810 135 H850 V230');s.conveyor(840,230,690,'','','chain');s.name(1185,206,'CV102','Silo fill conveyor')
    s.device('M-CV102','motor',1560,240)
    for i,(x,lvl,tg) in enumerate([(880,'lvl1','tg1'),(1040,'lvl2','tg2'),(1200,'lvl3','tg3'),(1360,'lvl4','tg4')]):
        cx=x+55
        s.pipe('M%s 250 V360'%cx)
        s.silo('SI10%d'%(i+1),lvl,'Raw oats',x,360,110,330)
        s.instrument('TI10%d'%(i+1),'TI',tg,'°C',1,cx+8,286,lead=None)
        s.pipe('M%s 690 V800'%cx);s.device('RV10%d'%(i+1),'rotary',cx,735)
    s.conveyor(900,800,620,'','');s.name(1210,846,'CV103','Silo reclaim conveyor');s.device('M-CV103','motor',880,850)
    s.pipe('M1520 810 H1540');s.stream('To cleaning',1540,796,160,'cleaning')
    s.filter(200,140,110,180,'F101','Dust filter');s.device('FN101','fan',255,90)
    s.air('M255 140 V112');s.air('M280 620 V560 H240 V320');s.air('M510 117 H460 V230 H310')
    s.instrument('WT101','WI','intake','t/h',1,370,600)
    s.instrument('MI101','MI','moistIn','%',1,380,680,lead=746)
    s.instrument('PDI101','PDI','filterDp','mbar',1,320,250)
    s.instrument('II101','II','elevAmps','A',1,570,330)
    s.trend('intake',600,450,240,70,'Intake rate (t/h)','#626b75',32)
    s.build('Intake & raw oat silos')

def cleaning():
    s=Scene('cleaning')
    s.stream('From raw oat silos',38,96,170,'intake');s.pipe('M208 110 H260 V140')
    s.bin(200,140,120,160,'BN201','Cleaning feed bin');s.pipe('M260 300 V430 H330')
    s.device('FC201','rotary',260,335,'feed','t/h',1)
    s.box(240,375,40,26,'','',inner='<text x="260" y="393" font-size="10" text-anchor="middle" stroke="none" fill="#555">MAG</text>');s.text(300,393,'MG201',11,600,'start')
    s.sieve(330,410,220,110,'SP201','Separator sieve');s.device('M-SP201','motor',440,370,'sieveAmps','A',1)
    s.pipe('M550 470 H610');s.aspirator(610,380,130,170,'AS201','Aspirator')
    s.air('M675 380 V290');s.cyclone(630,110,100,180,'CY201','Dust cyclone');s.air('M680 110 V80 H800');s.device('FN201','fan',820,80);s.text(940,85,'Exhaust',11,fill='#777')
    s.pipe('M740 500 H800');s.deck(800,420,200,110,'DS201','Destoner');s.device('M-DS201','motor',900,385,'stonerAmps','A',1)
    s.pipe('M1000 470 H1060');s.drum(1060,430,220,80,'TR201','Indented cylinder');s.device('M-TR201','motor',1170,395,'trieurSpeed','rpm',0)
    s.pipe('M1280 470 H1330');s.box(1330,380,120,190,'CS201','Optical sorter',inner='<path d="M1345 420 l20 12 l-20 12 Z M1435 420 l-20 12 l20 12 Z" fill="#999"/>')
    s.pipe('M1450 470 H1540');s.stream('To dehulling',1540,456,160,'dehulling')
    for x,y in [(350,520),(950,540),(1110,510),(1350,570),(725,550)]:s.pipe('M%s %s V800'%(x,y),INK,1.2)
    s.conveyor(360,800,1150,'','');s.name(935,846,'CV205','Screenings conveyor');s.device('M-CV205','motor',340,850)
    s.pipe('M1510 810 H1540');s.stream('Screenings to by-products',1540,796,190)
    s.instrument('FT201','FI','feed','t/h',1,60,320)
    s.instrument('II201','II','sieveAmps','A',1,420,580)
    s.instrument('PDI201','PDI','aspDp','mbar',1,480,190)
    s.instrument('FI201','FI','airFlow','m³/h',0,900,140)
    s.instrument('II202','II','stonerAmps','A',1,860,600)
    s.instrument('SI201','SI','trieurSpeed','rpm',0,1060,590)
    s.instrument('QI201','QI','rejects','%',2,1240,620)
    s.instrument('QI202','QI','purity','%',2,1470,370,lead=470)
    s.trend('feed',1000,180,260,70,'Cleaning feed (t/h)','#626b75',18)
    s.trend('rejects',1320,180,260,70,'Sorter rejects (%)','#626b75',0)
    s.build('Cleaning')

def dehulling():
    s=Scene('dehulling')
    s.stream('From cleaning',38,96,160,'cleaning');s.pipe('M198 110 H260 V140')
    s.bin(200,140,120,150,'BN301','Huller feed bin');s.pipe('M260 290 V400 H420 V375')
    s.device('VF301','rotary',260,335,'feed','t/h',1)
    s.huller(460,440,62,'HU301','Impact huller');s.shape('<path d="M440 360 h40 l-8 18 h-24 Z"/>');s.device('M-HU301','motor',380,560,'hullerAmps','A',1)
    s.pipe('M522 440 H600');s.aspirator(600,360,130,170,'AS301','Hull aspirator')
    s.air('M665 360 V300 H730 V170 H760');s.cyclone(760,110,100,170,'CY301','Hull cyclone');s.air('M810 110 V80 H900');s.device('FN301','fan',920,80);s.text(1040,85,'Exhaust',11,fill='#777')
    s.pipe('M810 280 V330 H1000',INK,1.6);s.device('RV301','rotary',810,305)
    s.hammermill(1000,270,130,110,'HG301','Hull grinder');s.pipe('M1130 325 H1540',INK,1.6);s.stream('Hulls to pellet press',1540,311,180)
    s.pipe('M730 470 H820');s.deck(820,400,220,130,'GS301','Groat separator');s.device('M-GS301','motor',860,385)
    s.pipe('M1040 450 H1540');s.stream('To kilning',1540,436,160,'kiln')
    s.pipe('M990 530 V650 H330 V440 H398');s.text(630,642,'Unhulled oats return to huller',11,fill='#777')
    s.pipe('M715 530 V780 H1540',INK,1.2);s.stream('Groat fines to Line 03',1540,766,180,'milling')
    s.instrument('FT301','FI','feed','t/h',1,60,330)
    s.instrument('SI301','SI','rotorSpeed','rpm',0,150,500)
    s.instrument('II301','II','hullerAmps','A',1,150,570)
    s.instrument('PDI301','PDI','aspDp','mbar',1,560,250)
    s.instrument('FT303','FI','hulls','t/h',1,1200,230,lead=325)
    s.instrument('QI301','QI','efficiency','%',1,1160,355,lead=450)
    s.instrument('QI302','QI','broken','%',1,1320,355,lead=450)
    s.instrument('FT302','FI','groats','t/h',1,1450,500,lead=450)
    s.trend('efficiency',1060,580,240,70,'Hulling efficiency (%)','#626b75',92)
    s.trend('rotorSpeed',1320,580,240,70,'Huller rotor speed (rpm)','#626b75',1480)
    s.build('Dehulling')

def kiln():
    s=Scene('kiln')
    s.stream('From dehulling',38,96,170,'dehulling');s.pipe('M208 110 H260 V140')
    s.bin(200,140,120,150,'BN401','Groat buffer bin');s.pipe('M260 290 V380');s.device('RV401','rotary',260,330)
    s.conveyor(230,382,240,'SC401','Steam conditioner','screw');s.pipe('M470 392 H520 V100 H600 V130')
    s.stream('Steam from boiler house',38,640,200,'utilities')
    s.steam('M238 654 H420 V402');s.steam('M420 654 H540 V400 H562');s.device('FCV401','control',300,654,'steamFlow','kg/h',0)
    s.column(560,130,140,330,'KL401','Kiln');s.name(630,252,'KL401','Kiln')
    s.air('M670 120 V80 H760');s.device('FN402','fan',780,80);s.text(900,85,'Kiln exhaust',11,fill='#777')
    s.pipe('M630 460 V560');s.device('RV402','rotary',630,510)
    s.cooler(560,560,140,190,'','');s.name(490,600,'CL401','Counterflow cooler');s.air('M700 640 H740');s.device('FN401','fan',760,640)
    s.pipe('M630 750 V790 H920');s.plansifter(920,740,170,90,'GR401','Groat grader')
    s.pipe('M1090 785 H1200 V200 H1540');s.pipe('M1200 330 H1540');s.pipe('M1200 460 H1540')
    for y,tag,target,text in [(200,'SDV411','flaking','Groats to Line 01'),(330,'SDV412','cutting','Groats to Line 02'),(460,'SDV413','milling','Groats to Line 03')]:
        s.device(tag,'block',1400,y);s.stream(text,1540,y-14,180,target)
    s.instrument('PI401','PI','steamPressure','bar',2,90,560)
    s.instrument('FIC401','FI','steamFlow','kg/h',0,330,560,colour='#ffe044')
    s.instrument('TIC401','TI','kilnTop','°C',1,720,180,colour='#ffe044')
    s.instrument('TI402','TI','kilnMid','°C',1,720,260)
    s.instrument('TI403','TI','kilnBottom','°C',1,720,340)
    s.instrument('MI401','MI','moisture','%',1,760,690)
    s.instrument('TI404','TI','coolerOut','°C',1,420,700)
    s.instrument('FT401','FI','feed','t/h',1,60,330)
    s.trend('kilnMid',900,180,260,70,'Kiln temperature (°C)','#626b75',98)
    s.trend('moisture',900,330,260,70,'Groat moisture after cooler (%)','#626b75',9.6)
    s.trend('coolerOut',900,480,260,70,'Cooler outlet (°C)','#626b75',25)
    s.build('Kilning & stabilisation')

def line_scene(area,number):
    s=Scene(area)
    s.state(1380,40,'LINE 0%d'%number)
    return s

def flaking():
    s=line_scene('flaking',1)
    s.stream('Groats from kiln',38,96,170,'kiln');s.pipe('M208 110 H260 V140')
    s.bin(200,140,120,150,'BN501','Groat bin');s.pipe('M260 290 V380 H380 V110 H475 V150');s.device('RV501','rotary',260,330,'rate','kg/h',0,'line')
    s.steamer(420,150,110,300,'ST501','Steamer')
    s.stream('Steam from boiler house',38,640,200,'utilities');s.steam('M238 654 H350 V400 H420');s.device('PCV501','control',300,654,'pressure','bar',2,'line')
    s.pipe('M475 450 V500');s.rollmill(420,500,170,150,'FM501','Flaking mill');s.device('M-FM501','motor',620,520,'power','kW',1,'line')
    s.pipe('M560 650 V715 H640');s.beltdryer(640,660,300,110,'DR501','Flake dryer')
    s.pipe('M940 715 H990');s.cooler(990,640,150,150,'CL501','Flake cooler')
    s.pipe('M1140 715 H1200');s.plansifter(1200,670,170,100,'SF501','Fines sifter')
    s.pipe('M1370 720 H1540');s.stream('Rolled oats to packing',1540,706,190,'packing')
    s.pipe('M1340 770 V820 H1540',INK,1.2);s.stream('Fines to Line 03',1540,806,190,'milling')
    s.instrument('TIC501','TI','temperature','°C',1,560,190,colour='#ffe044')
    s.instrument('PI501','PI','pressure','bar',2,90,560)
    s.instrument('SI501','SI','rollSpeed','rpm',0,620,360)
    s.instrument('ZI501','ZI','rollGap','mm',2,620,430)
    s.instrument('JI501','JI','power','kW',1,640,580)
    s.instrument('TI502','TI','dryerTemp','°C',1,760,580)
    s.instrument('TI503','TI','coolerOut','°C',1,1000,560)
    s.instrument('MI501','MI','moisture','%',2,1150,580)
    s.instrument('FT501','FI','rate','kg/h',0,1390,610,lead=720)
    s.trend('rate',820,190,300,75,'Throughput (kg/h)','#626b75',1920)
    s.trend('moisture',1180,190,300,75,'Flake moisture (%)','#626b75',11.4)
    s.trend('temperature',820,380,300,75,'Steamer temperature (°C)','#626b75',82)
    s.trend('pressure',1180,380,300,75,'Steam pressure (bar)','#626b75',2.4)
    s.build('Line 01 · Steaming & flaking')

def cutting():
    s=line_scene('cutting',2)
    s.stream('Groats from kiln',38,96,170,'kiln');s.pipe('M208 110 H260 V140')
    s.bin(200,140,120,150,'BN601','Groat bin');s.pipe('M260 290 V380');s.device('RV601','rotary',260,330,'rate','kg/h',0,'line')
    s.conveyor(230,382,240,'SC601','Steam conditioner','screw')
    s.stream('Steam from boiler house',38,640,200,'utilities');s.steam('M238 654 H420 V402');s.device('PCV601','control',300,654,'pressure','bar',2,'line')
    s.pipe('M470 392 H520 V345 H560');s.pipe('M520 392 V515 H560')
    s.drum(560,305,200,80,'GC601','Granulator 1');s.drum(560,475,200,80,'GC602','Granulator 2')
    s.device('M-GC601','motor',640,270,'drum1','rpm',0,'line');s.device('M-GC602','motor',800,600,'drum2','rpm',0,'line')
    s.pipe('M760 345 H820 V430 H880');s.pipe('M760 515 H820 V430')
    s.aspirator(880,350,130,170,'AS601','Aspirator');s.air('M945 350 V300 H1000');s.text(1010,304,'To dust filter',11,anchor='start',fill='#777')
    s.pipe('M1010 470 H1080');s.sieve(1080,400,180,120,'SF601','Grading sifter')
    s.pipe('M1260 440 H1540');s.stream('Steel-cut oats to packing',1540,426,190,'packing')
    s.pipe('M1100 520 V700 H520 V515');s.text(840,692,'Oversize return to granulators',11,fill='#777')
    s.pipe('M1230 520 V780 H1540',INK,1.2);s.stream('Fines to Line 03',1540,766,190,'milling')
    s.instrument('TIC601','TI','temperature','°C',1,60,250,colour='#ffe044')
    s.instrument('PI601','PI','pressure','bar',2,90,560)
    s.instrument('SI601','SI','drum1','rpm',0,800,220)
    s.instrument('SI602','SI','drum2','rpm',0,560,600)
    s.instrument('JI601','JI','power','kW',1,1080,220)
    s.instrument('QI601','QI','uniformity','%',1,1080,560)
    s.instrument('QI602','QI','oversize','%',1,1250,560)
    s.instrument('MI601','MI','moisture','%',2,1300,340,lead=440)
    s.instrument('FT601','FI','rate','kg/h',0,1450,340,lead=440)
    s.trend('rate',1250,170,260,70,'Throughput (kg/h)','#626b75',1500)
    s.trend('moisture',1290,670,220,60,'Moisture (%)','#626b75',11.4)
    s.build('Line 02 · Groat cutting')

def milling():
    s=line_scene('milling',3)
    s.stream('Groats from kiln',38,96,170,'kiln');s.pipe('M208 110 H300 V140')
    s.stream('Fines from Line 01',38,166,170,'flaking');s.pipe('M208 180 H240')
    s.stream('Fines from Line 02',38,236,170,'cutting');s.pipe('M208 250 H240')
    s.bin(240,140,120,180,'BN701','Mill feed bin');s.pipe('M300 320 V400');s.device('RV701','rotary',300,360,'rate','kg/h',0,'line')
    s.conveyor(270,402,240,'HT701','Heat treatment screw','screw')
    s.stream('Steam from boiler house',38,640,200,'utilities');s.steam('M238 654 H470 V422');s.device('PCV701','control',300,654,'pressure','bar',2,'line')
    s.pipe('M510 412 H560');s.hammermill(560,360,150,140,'HM701','Hammer mill');s.device('M-HM701','motor',635,320,'millSpeed','rpm',0,'line')
    s.pipe('M710 430 H760 V140 H800');s.cyclone(800,110,110,190,'CY701','Product cyclone')
    s.air('M855 110 V80 H1000');s.device('FN701','fan',1020,80,'pneuDp','mbar',0,'line');s.text(1150,85,'To dust filter',11,fill='#777')
    s.pipe('M855 300 V390');s.device('RV702','rotary',855,345)
    s.plansifter(780,390,160,180,'PS701','Plansifter')
    s.pipe('M940 440 H1540');s.stream('Oat flour to packing',1540,426,190,'packing')
    s.pipe('M940 520 H1050');s.drum(1050,480,170,80,'BF701','Bran finisher');s.pipe('M1220 520 H1540');s.stream('Oat bran to packing',1540,506,190,'packing')
    s.pipe('M800 570 V650 H520 V470 H560');s.text(690,642,'Overs return to mill',11,fill='#777')
    s.instrument('TIC701','TI','temperature','°C',1,370,300,colour='#ffe044')
    s.instrument('PI701','PI','pressure','bar',2,90,560)
    s.instrument('SI701','SI','millSpeed','rpm',0,560,230)
    s.instrument('JI701','JI','power','kW',1,560,540)
    s.instrument('PDI701','PDI','pneuDp','mbar',0,960,215)
    s.instrument('QI701','QI','fineness','µm',0,990,340,lead=440)
    s.instrument('MI701','MI','moisture','%',2,1160,340,lead=440)
    s.instrument('FT701','FI','rate','kg/h',0,1330,340,lead=440)
    s.instrument('QI702','QI','branYield','%',1,1300,560,lead=520)
    s.trend('rate',1000,680,240,70,'Throughput (kg/h)','#626b75',1260)
    s.trend('power',1290,680,240,70,'Mill power (kW)','#626b75',0)
    s.build('Line 03 · Oat flour milling')

def packing():
    s=Scene('packing')
    lanes=[('Rolled oats from Line 01','flaking',96,940,'BN803','lvlC','Rolled oats','MW803','BG803','500 g packs','weightC','g','packsC'),
           ('Steel-cut oats from Line 02','cutting',166,620,'BN802','lvlB','Steel-cut oats','MW802','BG802','1 kg packs','weightB','g','packsB'),
           ('Oat flour from Line 03','milling',236,300,'BN801','lvlA','Oat flour','AF801','BG801','25 kg sacks','sackWeight','kg','sacksMin')]
    for text,src,y,x,bin_,lvl,product,weigher,bagger,size,weight,unit,speed in lanes:
        cx=x+55
        s.stream(text,38,y,210,src);s.pipe('M248 %s H%s V300'%(y+14,cx))
        s.silo(bin_,lvl,product,x,300,110,220)
        s.pipe('M%s 520 V560'%cx);s.weigher(cx,560,weigher,'Weigher' if weigher.startswith('MW') else 'Auger filler')
        s.pipe('M%s 594 V630'%cx);s.bagger(cx,630,bagger,size)
        s.pipe('M%s 740 V800'%cx)
        s.instrument(bagger.replace('BG','WI'),'WI',weight,unit,2 if unit=='kg' else 1,x+130,380)
        s.instrument(bagger.replace('BG','SI'),'SI',speed,'/min',1,x+130,440)
    s.conveyor(330,800,800,'','');s.name(730,846,'CV804','Pack collection conveyor');s.device('M-CV804','motor',310,850)
    s.pipe('M1130 810 H1160');s.box(1160,790,110,30,'CW801','Checkweigher')
    s.pipe('M1270 805 H1300');s.box(1300,770,70,60,'MD801','Metal detector',inner='<path d="M1312 830 V782 H1358 V830" fill="none" stroke-width="3"/>')
    s.pipe('M1370 805 H1420');s.box(1420,700,130,120,'PL801','Palletiser',inner='<rect x="1440" y="790" width="90" height="10" fill="#b9a27a"/><rect x="1445" y="740" width="80" height="48" fill="#ecebe5"/>')
    s.pipe('M1550 760 H1570');s.stream('To warehouse',1570,746,140)
    s.instrument('QI801','QI','rejects','%',2,1160,700)
    s.instrument('FQ801','FQ','pallets','/h',1,1560,640)
    s.trend('packsC',1240,180,280,70,'Rolled oats line (packs/min)','#626b75',62)
    s.trend('weightC',1240,320,280,70,'Rolled oats pack weight (g)','#626b75',500)
    s.trend('rejects',1240,460,280,70,'Checkweigher rejects (%)','#626b75',0)
    s.build('Packing & palletising')

def utilities():
    s=Scene('utilities')
    s.stream('Town water',38,96,150);s.pipe('M188 110 H230',WATER,1.7)
    s.vessel(230,80,70,120,'WT901','Softener');s.pipe('M300 140 H360',WATER,1.7)
    s.vessel(360,100,220,90,'FW901','Feedwater tank');s.pipe('M580 145 H600 V290 H700',WATER,1.7)
    s.device('P901','pump',640,290,'drumLevel','%',0)
    s.boiler(740,180,300,150,'B901','Steam boiler');s.stream('Natural gas',38,330,150);s.pipe('M188 344 H700 V295',GAS,1.7);s.device('FCV901','control',460,344,'gasFlow','Nm³/h',0)
    s.steam('M970 180 V130 H1400');s.device('PCV901','control',1180,130,'headerPressure','bar',2)
    s.steam('M1400 130 V340')
    for y,text,target in [(130,'Steam to kilning','kiln'),(200,'Steam to Line 01','flaking'),(270,'Steam to Line 02','cutting'),(340,'Steam to Line 03','milling')]:
        s.steam('M1400 %s H1540'%y);s.stream(text,1540,y-14,170,target)
    s.instrument('LI902','LI','feedLevel','%',0,420,235)
    s.instrument('PI901','PI','boilerPressure','bar',1,1060,190)
    s.instrument('TI901','TI','steamTemp','°C',1,1060,260)
    s.instrument('LIC901','LI','drumLevel','%',1,820,360,colour='#a7eef0')
    s.instrument('FI902','FI','gasFlow','Nm³/h',0,300,380)
    s.instrument('FI901','FI','steamFlow','t/h',2,1250,160)
    s.instrument('PIC902','PI','headerPressure','bar',2,1250,230,colour='#ffe044')
    s.text(40,480,'COMPRESSED AIR',11,700,'start','#6d7270')
    for y,tag,run in [(520,'AC901',True),(720,'AC902',False)]:
        s.box(200,y,140,90,tag,'Compressor (duty)' if run else 'Compressor (standby)')
        s.device('M-'+tag,'motor',270,y-35,'compAmps' if run else '','A',1,run)
        s.pipe('M340 %s H420'%(y+45),AIR,1.7)
    s.pipe('M420 565 V765',AIR,1.7);s.pipe('M420 640 H520',AIR,1.7)
    s.vessel(520,520,80,220,'AR901','Air receiver');s.pipe('M600 640 H700',AIR,1.7)
    s.box(700,580,120,120,'AD901','Adsorption dryer');s.pipe('M820 640 H1540',AIR,1.7);s.stream('Compressed air to plant',1540,626,190)
    s.instrument('II901','II','compAmps','A',1,450,470)
    s.instrument('PI903','PI','airPressure','bar',2,1000,540,lead=640)
    s.instrument('TI903','TI','dewPoint','°C',1,860,720)
    s.trend('headerPressure',980,400,240,70,'Steam header (bar)','#626b75',3.5)
    s.trend('airPressure',1270,400,240,70,'Compressed air (bar)','#626b75',7.2)
    s.build('Steam & compressed air')

def overview():
    s=Scene('overview')
    cols=[90+i*270 for i in range(6)]
    place={'intake':(cols[0],360),'cleaning':(cols[1],360),'dehulling':(cols[2],360),'kiln':(cols[3],360),
           'flaking':(cols[4],130),'cutting':(cols[4],360),'milling':(cols[4],590),'packing':(cols[5],360),'utilities':(cols[2],640)}
    def arrow(d,x,y,colour=INK):
        s.pipe(d,colour,2.2);s.under.append('<path d="M%s %s l-10 -6 v12 Z" fill="%s"/>'%(x,y,colour))
    for a,b in [(0,1),(1,2),(2,3)]:arrow('M%s 445 H%s'%(cols[a]+230,cols[b]),cols[b],445)
    k=cols[3]+230
    for y in (215,445,675):arrow('M%s 445 H%s V%s H%s'%(k,k+20,y,cols[4]),cols[4],y)
    l=cols[4]+230
    for y in (215,445,675):arrow('M%s %s H%s V445 H%s'%(l,y,l+20,cols[5]),cols[5],445)
    s.steam('M%s 725 H%s V530'%(cols[2]+230,cols[3]+115));s.under.append('<path d="M%s 530 l-6 10 h12 Z" fill="%s"/>'%(cols[3]+115,STEAM))
    s.text(cols[0],330,'RECEIVING',10,700,'start','#6d7270');s.text(cols[2],330,'GROAT PROCESSING',10,700,'start','#6d7270')
    s.text(cols[4],100,'PRODUCTION LINES',10,700,'start','#6d7270');s.text(cols[5],330,'FINISHED GOODS',10,700,'start','#6d7270');s.text(cols[2],620,'UTILITIES',10,700,'start','#6d7270')
    s.text(cols[0],130,'Click a process area to open its SCADA screen.',14,400,'start','#5a5e5c')
    s.pipe('M%s 170 h40'%cols[0],INK,2.2);s.text(cols[0]+50,174,'Product flow',12,anchor='start')
    s.steam('M%s 200 h40'%cols[0]);s.text(cols[0]+50,204,'Steam',12,anchor='start')
    for key,(x,y) in place.items():
        s.parts.append(at(embed(key.title()+'Tile',HMI+'Tile',{'area':key,'route':ROUTE[key]}),x,y,230,170))
    s.build('Oatmakers plant overview')


def page(name,title,subtitle,drawing,area=None):
    nav=[]
    if area:
        keys=[a[0] for a in AREAS];i=keys.index(area)
        nav.append(button('Overview','‹ Plant overview',page='/scada',classes='Demo/QuietButton'))
        if i>0:nav.append(button('Previous','‹ '+TITLE[keys[i-1]],page=ROUTE[keys[i-1]],classes='Demo/QuietButton'))
        if i<len(keys)-1:nav.append(button('Next',TITLE[keys[i+1]]+' ›',page=ROUTE[keys[i+1]],classes='Demo/QuietButton'))
    group=next((a[3] for a in AREAS if a[0]==area),'')
    for b in nav:b['props'].setdefault('style',{})['classes']='Demo/QuietButton Hmi/NavButton'
    header=flex('Header',[flex('Identity',[label('Eyebrow','OATMAKERS / SCADA'+(' / '+group.upper() if group else ''),'Demo/Eyebrow'),label('Title',title,'Demo/PageTitle'),label('Subtitle',subtitle+' Drag to pan, scroll to zoom.','Demo/Subtitle')],grow=1),flex('Navigation',nav,'row','Hmi/Navigation'),label('Mode','SIMULATED FACTORY','Demo/DemoBadge')],'row','Demo/PageHeader')
    pan=node('mustrysolutions.perspective.display.panzoomview','ProcessViewport',{
        'config':{'viewPath':drawing,'viewParams':[],'contentWidth':W,'contentHeight':H,'minZoom':0.2,'maxZoom':4,
                  'zoomStep':1.25,'wheelZoom':True,'doubleClickZoom':True,'showControls':True,'showMinimap':True,'showPoiList':False,
                  'flyToMs':250,'home':{'x':-1,'y':-1,'zoom':0}},
        'state':{'zoom':0,'center':{'x':0,'y':0},'target':''},'data':{'pois':[]},'style':{'classes':'Hmi/PanZoom','minHeight':'0px'}},basis='0px',grow=1)
    pan['position']['shrink']=1
    view(name,flex('root',[header,pan],classes='Demo/Page Hmi/Page'),height=939)

def build_scada():
    components()
    for fn in (overview,intake,cleaning,dehulling,kiln,flaking,cutting,milling,packing,utilities):fn()
    page('Demo/SCADA','Plant overview','From truck intake to pallet: live status of every process area.',HMI+'Drawing/Overview')
    for key,route,title,group,subtitle in AREAS:
        page(HMI+'Screen/'+key.title(),title,subtitle,HMI+'Drawing/'+key.title(),key)
    return [(route,title,HMI+'Screen/'+key.title()) for key,route,title,*_ in AREAS]


SCADA_CSS='''
.psc-Hmi\\/Page { background:#e6e6e6; color:#565957; overflow:hidden; width:100%; height:100%; font-family:Arial,sans-serif; }
.psc-Hmi\\/Navigation { gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
.psc-Hmi\\/Navigation { flex:0 1 auto !important; }
.psc-Hmi\\/NavButton { flex:0 0 auto !important; height:34px; padding:6px 12px; font-size:12px; white-space:nowrap; }
.psc-Hmi\\/PanZoom.mustry-panzoom { border:0; border-radius:0; --pz-canvas:#e6e6e6; --pz-bg:#e6e6e6; --pz-accent:#565957; }
.psc-Hmi\\/PanZoom .mustry-pz-content { background:transparent; box-shadow:none; border:0; }
.psc-Hmi\\/DetailValue { font-size:28px; color:#444; }
.psc-Demo\\/Menu { background:transparent; color:#d5dade; font-size:12px; }
.psc-Demo\\/Menu .menu-wrapper,.psc-Demo\\/Menu .wrapper-submenu { background:#2b3238 !important; height:100%; }
.psc-Demo\\/Menu .ia_menuTreeComponent__item { background:transparent; color:#d5dade; border:0; border-radius:4px; min-height:42px; padding:0 10px; margin-bottom:4px; cursor:pointer; }
.psc-Demo\\/Menu .ia_menuTreeComponent__item:hover { background:#3d474f; }
.psc-Demo\\/Menu .ia_menuTreeComponent__item__text { color:#d5dade; font-size:12px; }
.psc-Demo\\/Menu .ia_menuTreeComponent__item__icon,.psc-Demo\\/Menu .ia_menuTreeComponent__item__navIcon { fill:#a6aeb4; color:#a6aeb4; }
.psc-Demo\\/Menu .ia_menuTreeComponent__header { background:transparent; color:#f2f4f5; font-size:12px; font-weight:700; letter-spacing:0.6px; border:0; border-bottom:1px solid #3d474f; padding:8px 10px; }
.psc-Demo\\/Menu .ia_menuTreeComponent__backAction { background:transparent; color:#a6aeb4; font-size:11px; border:0; padding:8px 10px; cursor:pointer; }
.psc-Demo\\/Menu .ia_menuTreeComponent__backAction:hover { color:#f2f4f5; }
.psc-Demo\\/Menu .ia_menuTreeComponent__header__icon,.psc-Demo\\/Menu .ia_menuTreeComponent__backAction svg { fill:#a6aeb4; }
.psc-Demo\\/Menu .psc-Demo\\/MenuActive { background:#3d474f; }
.psc-Demo\\/Menu .psc-Demo\\/MenuActive .ia_menuTreeComponent__item__text { color:#fff; font-weight:700; }
.psc-Demo\\/Menu .psc-Demo\\/MenuTrail .ia_menuTreeComponent__item__text { color:#fff; font-weight:700; }
'''
