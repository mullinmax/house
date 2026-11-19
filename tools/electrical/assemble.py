import json, math
M=json.load(open('main.json'))
U=json.load(open('raw_18.json'))
DIR={0:(0,-1),90:(1,0),180:(0,1),270:(-1,0)}
GFI44={46,48,49,50,51,54,55,56,57,58,59,60,61,76,77,78}
GFI24={52,53}; WP={104,105,106,107}
TVOUT={13,15}; TVDATA={12,14}
NOTE={45:"Marked RANGE on U-11. The kitchen now has the LG induction cooktop on this wall and the Frigidaire wall oven in the tower, both 240 V, so this circuit and a second one for the oven get set by the cabinet layout.",
      47:"Marked M/W on U-11, for a microwave. The microwave is now the Breville on the fridge wall counter (or a cubby), so this one may move.",
      72:"Floor outlet, U-11 says to confirm with the owner.",
      13:"Behind the living room TV. U-11: 72 in to the TV, confirm with the owner.",
      15:"Behind the entry and family room TV. U-11: 72 in to the TV, confirm with the owner.",
      108:"U-11's utility room outlet, beside the pressure tank: handy for the UV sterilizer and well controls. The stick vacuum has its own added outlet by its dock in the northeast corner."}
dev=[]
def add(**k): dev.append(k)
SKIP={8,9,10,11}   # the four switches U-11 puts behind the loft ladder: one 4 gang plate west of it instead (Maxwell, 11/19/2026)
add(kind='switch',gangs=4,x=27.0,y=34.583,z_in=44,facing=0,level='main',src="U-11 #8-11",note="U-11 draws four switches (two of them 3-way, for the loft) side by side on this wall, right where the ships ladder now stands. Combined into one 4 gang plate just west of the ladder (Maxwell, 11/19/2026).")
MOVE={12:(16.709,30.9,90),13:(16.709,30.4,90)}   # living room TV: west wall, not east (Maxwell, 11/19/2026)
NOTE[13]="Behind the living room TV. U-11 draws it on the east wall; moved to the west wall facing the couch (Maxwell, 11/19/2026). U-11: 72 in to the TV, confirm with the owner."
for i,r in enumerate(M):
  x,y=r['ft']; k=r['kind']
  if i in SKIP: continue
  if i in MOVE:
    X,Y,f=MOVE[i]
    add(kind='tv_data' if i==12 else 'outlet',x=X,y=Y,z_in=72,facing=f,level='main',src=f"U-11 #{i}",tv=(i==12),**({'note':NOTE[13]} if i==13 else {}))
    continue
  if k=='smoke': add(kind='smoke',x=x,y=y,level='main',src=f"U-11 #{i}"); continue
  f=r.get('facing')
  if i in (52,53):   # island ends
    if i==53: add(kind='outlet',x=6.0,y=44.11,z_in=24,facing=270,gfi=True,level='main',src=f"U-11 #{i}",note="24 in GFI on the island's west end, per U-11.")
    else: add(kind='outlet',x=13.9,y=46.085,z_in=24,facing=90,gfi=True,level='main',src=f"U-11 #{i}",note="U-11 puts a 24 in GFI on the island's east end. The beverage fridge now fills most of that end, so it is shown on the narrow end panel beside it. Move it to a side of the island if the panel is too narrow.")
    continue
  if i==72: add(kind='floor_box',x=x,y=y,z_in=0,facing=0,level='main',src=f"U-11 #{i}",note=NOTE[i]); continue
  wx,wy=r['wall']
  if f in (0,180): X,Y=x,wy
  else: X,Y=wx,y
  z=16; e={}
  if i in GFI44: z=44; e['gfi']=True
  if i in GFI24: z=24; e['gfi']=True
  if i in WP: e['wp']=True; e['gfi']=True
  if i==47: z=44
  if i in TVOUT or i in TVDATA: z=72
  if k=='switch': z=44
  if k=='outlet' and r['bars']==3: e['volts']=240
  kind={'outlet':'outlet','switch':'switch','data':'data'}[k]
  if i in TVDATA: kind='tv_data'
  if i==14: e['tv']=False
  add(kind=kind,x=X,y=Y,z_in=z,facing=f,level='main',src=f"U-11 #{i}",**e,**({'note':NOTE[i]} if i in NOTE else {}))
# upper (U-12): facing set by hand from the sheet (see the thread)
UF={4:90,5:180,6:270,7:0,8:180,9:0,10:0,11:180,16:180,17:270,2:0,12:0,3:90}
for i,o in enumerate(U):
  x=(o['x']-251.2)/18; y=(o['y']-198.35)/18; k=o['kind']
  if k=='smoke': add(kind='smoke',x=x,y=y,level='upper',src=f"U-12 #{i}"); continue
  if k=='c91':   # special receptacles for the HVAC unit and ERV, on the deck against the wall south of them
    add(kind='special',x=x,y=22.37,z_in=16,facing=0,level='upper',src=f"U-12 #{i}",note=("For the heat pump" if i==0 else "For the ERV")+" in the attic, per U-12. The equipment itself sits elsewhere in the attic now, so this moves to suit it.")
    continue
  f=UF[i]; dx,dy=DIR[f]
  X,Y=x-dx*0.522,y-dy*0.522
  if i in (3,4): X=31.29
  if i==5: X=39.0   # U-12 draws it at x 35.6, where the model has no wall above the 9 ft plate yet; moved east onto the loft's north wall
  add(kind={'outlet':'outlet','switch':'switch','data':'data'}[k],x=X,y=Y,z_in=44 if k=='switch' else 16,facing=f,level='upper',src=f"U-12 #{i}",**({'note':"U-12 shows a 36 in pony wall along the loft's west edge here. The model has an open railing, so this needs a short pony wall, a post mounted box or a floor box."} if i in (3,4) else {}))
for d_ in dev:
  d_['x']=round(d_['x'],3); d_['y']=round(d_['y'],3)
json.dump(dict(source="Sealed plan set 06/14/2026 (Moonlight Architecture), sheets U-11 main level and U-12 upper level utility plans. Positions read from the PDF's vector symbols at 1/4 in = 1 ft, plan feet from the outside NW slab corner. facing = compass direction the device faces. z_in = inches above that level's floor to the centre.",
  heights=dict(outlet_default_in=16, note="Plain outlets 16 in per the U-11 legend (Maxwell's pick 11/19/2026). U-11 note 27 says 24 in and the G sheet notes say 18 in."),
  devices=dev),open('../../model/data/electrical_plan.json','w'),indent=1)
import collections; print(collections.Counter((d_['kind'],d_['level']) for d_ in dev))
