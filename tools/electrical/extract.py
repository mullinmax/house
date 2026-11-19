# Reads device symbols off the sealed utility plans (U-11, U-12). Run from this folder: python3 build.py, then python3 assemble.py.
# Needs pymupdf and the sealed PDF at the path in extract.py (it lives in the project files, not in this repo).
import fitz, json, math, sys
PDF='/mnt/project-files/HeilmanMullin-AppraisalPermit-06142026-SEALED (1).pdf'
d=fitz.open(PDF)
def ctr(r): return ((r.x0+r.x1)/2,(r.y0+r.y1)/2)
def extract(pg, box):
  p=d[pg]; out=[]
  dr=[g for g in p.get_drawings() if box[0]<g['rect'].x0<box[2] and box[1]<g['rect'].y0<box[3]]
  bars=[]
  for g in dr:
    for it in g['items']:
      if it[0]=='l':
        a,b=it[1],it[2]; L=math.hypot(a.x-b.x,a.y-b.y)
        if 18<L<19.6: bars.append(((a.x+b.x)/2,(a.y+b.y)/2,'v' if abs(a.x-b.x)<0.5 else ('h' if abs(a.y-b.y)<0.5 else 'd'),g['rect']))
  seen=set()
  for g in dr:
    r=g['rect']; k=''.join(i[0] for i in g['items']); c=ctr(r)
    key=(round(c[0]),round(c[1]),k,round(r.width))
    if key in seen: continue
    seen.add(key)
    if k=='cccc' and abs(r.width-11.2)<0.3 and g.get('fill')==(1.0,1.0,1.0):
      nb=[b for b in bars if math.hypot(b[0]-c[0],b[1]-c[1])<4]
      out.append(dict(kind='outlet',x=c[0],y=c[1],bars=len(nb),ori=''.join(sorted(set(b[2] for b in nb)))))
    elif k=='cccc' and abs(r.width-16.7)<0.3 and g.get('fill')==(1.0,1.0,1.0):
      out.append(dict(kind='smoke',x=c[0],y=c[1]))
    elif k=='lll' and g.get('fill')==(0.0,0.0,0.0) and 10<r.width<14 and 10<r.height<14:
      out.append(dict(kind='data',x=c[0],y=c[1],w=r.width,h=r.height))
    elif k=='ccccc' and g.get('fill') is None and 10<max(r.width,r.height)<15 and g.get('width',0)>1:
      out.append(dict(kind='switch',x=c[0],y=c[1]))
    elif k=='ccccc' and g.get('fill')==(1.0,1.0,1.0) and abs(r.width-6.2)<0.3:
      out.append(dict(kind='c62',x=c[0],y=c[1]))
    elif k=='cccc' and abs(r.width-9.1)<0.3:
      out.append(dict(kind='c91',x=c[0],y=c[1]))
    elif k=='cccc' and abs(r.width-6.5)<0.3:
      out.append(dict(kind='c65',x=c[0],y=c[1]))
  # dedupe by kind+pos
  res=[]
  for o in out:
    if not any(q['kind']==o['kind'] and math.hypot(q['x']-o['x'],q['y']-o['y'])<2 for q in res): res.append(o)
  return res, p
if __name__=='__main__':
  pg=int(sys.argv[1]); box=[float(v) for v in sys.argv[2].split(',')]
  res,p=extract(pg,box)
  import collections; print(collections.Counter((o['kind'],o.get('bars')) for o in res))
  json.dump(res,open(f'raw_{pg}.json','w'),indent=0)
  col={'outlet':(1,0,0),'smoke':(0,0.6,0),'data':(0,0,1),'switch':(1,0.5,0),'c62':(0.7,0,0.7),'c91':(0,0.7,0.7),'c65':(0.5,0.5,0)}
  sh=p.new_shape()
  for i,o in enumerate(res):
    sh.draw_rect(fitz.Rect(o['x']-10,o['y']-10,o['x']+10,o['y']+10)); sh.finish(color=col[o['kind']],width=2)
  sh.commit()
  for i,o in enumerate(res):
    p.insert_text((o['x']+10,o['y']-10),str(i),fontsize=7,color=col[o['kind']])
  p.get_pixmap(clip=fitz.Rect(*box),dpi=int(sys.argv[3]) if len(sys.argv)>3 else 60).save(f'ov_{pg}.png')
