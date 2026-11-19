import fitz, json, math, sys
sys.path.insert(0,'.')
from extract import extract, d
OX,OY,S=251.2,198.35,18.0
def ft(x,y): return ((x-OX)/S,(y-OY)/S)
T=json.load(open('../../model/data/traced_geometry.json'))
polys=T['interior_walls_from_plan_A11']
W=43.0833; H=52.0; E=0.5417
def pip(pt,poly):
  x,y=pt; c=False
  for i in range(len(poly)):
    (x1,y1),(x2,y2)=poly[i],poly[i-1]
    if (y1>y)!=(y2>y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
  return c
def inwall(pt):
  x,y=pt
  if -0.6<x<W+0.6 and -0.6<y<H+0.6 and (x<E or x>W-E or y<E or y>H-E): return True
  return any(pip(pt,p) for p in polys)
res,p=extract(17,[200,150,1350,1600])
# bars again for wall direction
import extract as X
bars=[]
for g in p.get_drawings():
  for it in g['items']:
    if it[0]=='l':
      a,b=it[1],it[2]; L=math.hypot(a.x-b.x,a.y-b.y)
      if 18<L<19.6: bars.append((a,b))
words=[w for w in p.get_text('words') if 200<w[0]<1350 and 150<w[1]<1600]
out=[]
for o in res:
  if o['kind'] not in ('outlet','switch','data','smoke'): continue
  c=(o['x'],o['y'])
  near=[w[4] for w in words if math.hypot((w[0]+w[2])/2-c[0],(w[1]+w[3])/2-c[1])<28]
  rec=dict(kind=o['kind'],pt=[round(o['x'],1),round(o['y'],1)],ft=[round(v,3) for v in ft(*c)],near=near,bars=o.get('bars'))
  if o['kind']!='smoke':
    cand=[(a,b) for a,b in bars if math.hypot((a.x+b.x)/2-c[0],(a.y+b.y)/2-c[1])<(4 if o['kind']=='outlet' else 14)]
    best=None
    for a,b in cand:
      for e,f in ((a,b),(b,a)):
        dx,dy=(e.x-f.x)/18.8,(e.y-f.y)/18.8
        probe=ft(e.x+dx*3,e.y+dy*3)
        if inwall(probe):
          dist=math.hypot(e.x-c[0],e.y-c[1])
          if best is None or dist<best[0]: best=(dist,e,dx,dy)
    if best:
      _,e,dx,dy=best
      rec['wall']=[round(v,3) for v in ft(e.x,e.y)]; rec['facing']=round(math.degrees(math.atan2(-dx,dy)))%360  # into room = -d
    else: rec['wall']=None
  out.append(rec)
json.dump(out,open('main.json','w'),indent=0)
for i,r in enumerate(out): print(i,r['kind'],r['ft'],r.get('wall'),r.get('facing'),r['bars'],' '.join(r['near']))
