"""Wall junction audit (python3 tools/wall_audit.py from the repo root): on a 1 inch grid, every wall cell next to a room must
reach that room's ceiling with no holes. A narrow enclosed void in the study (x 22.1 to 22.6 at the north wall) is a known false positive."""
import runpy,io,contextlib,math
with contextlib.redirect_stdout(io.StringIO()):
    g=runpy.run_path("model/make_house.py")
T,HW,HD,YC,YC2=g["T"],g["HW"],g["HD"],g["YC"],g["YC2"]
FH,FT,DK=g["FH"],g["FLOOR_T"],g["DECK_T"]; LX0,LY0,LX1,LY1=g["LX0"],g["LY0"],g["LX1"],g["LY1"]
L=g["LOFT"]["floor_height"]
S=1/12; nx,ny=int(HW/S)+1,int(HD/S)+1
cov={}  # cell -> list of (z0,z1)
def add(x0,x1,y0,y1,z0,top):
    for i in range(max(0,int(x0/S)),min(nx,int(math.ceil(x1/S)))):
        cx=(i+.5)*S
        if not (x0<cx<x1): continue
        for j in range(max(0,int(y0/S)),min(ny,int(math.ceil(y1/S)))):
            cy=(j+.5)*S
            if y0<cy<y1: cov.setdefault((i,j),[]).append((z0,top(cx,cy) if callable(top) else top))
for (r,top) in g["WALL_PIECES"]: add(*r,0,top)
for f in g["FIXES"]:
    if f[0]=="sliver": add(*f[1:5],f[6],f[5])
    else: add(*f[1:5],f[6],f[5])
for d in g["DOOR_GAPS"]:   # door openings: open below the head by design
    _,a,b,c,e,h=d
    if _=="x": add(a,b,c,e,0,h)
    else: add(c,e,a,b,0,h)   # ('y', y0,y1,x0,x1)
for da in g["FU"].get("door_add", []):
    if da["axis"]=="y": add(da["t0"],da["t1"],da["g0"],da["g1"],da.get("head",6.67),FH+FT-DK)
    else: add(da["g0"],da["g1"],da["t0"],da["t1"],da.get("head",6.67),FH+FT-DK)
add(-1,T,-1,HD+1,0,99); add(HW-T,HW+1,-1,HD+1,0,99); add(-1,HW+1,-1,T,0,99); add(-1,HW+1,HD-T,HD+1,0,99)
add(-1,HW+1,YC,YC2,0,99)
def ceiling(x,y):
    if LX0<=x<=LX1 and LY0<=y<=LY1: return L-FT
    if any(a0<=x<=a1 and b0<=y<=b1 for a0,b0,a1,b1 in g["C"]["ceilings"]["flat_rooms"]): return FH+FT-DK
    return g["roof_under"](y)
def reach(iv):
    iv=sorted(iv); z=iv[0][0] if iv[0][0]<=8.1 else 0   # door openings and open passages: covered from the head up
    for a,b in iv:
        if a>z+0.02: break
        z=max(z,b)
    return z
bad={}
for (i,j),iv in cov.items():
    cx,cy=(i+.5)*S,(j+.5)*S
    if LX0-0.7<cx<LX0+0.7 and LY0-0.3<cy<LY1+0.3: continue   # open loft edge (railing)
    z=reach(iv)
    for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
        n=(i+di,j+dj)
        if n in cov or not(0<=n[0]<nx and 0<=n[1]<ny): continue
        need=ceiling((n[0]+.5)*S,(n[1]+.5)*S)
        if z<need-0.15: bad.setdefault((round(cx,1),round(cy,1)),(round(z,2),round(need,2)))
# narrow uncovered slits
for i in range(nx):
    for j in range(ny):
        if (i,j) in cov: continue
        for di,dj in ((1,0),(0,1)):
            k1=next((k for k in range(1,8) if (i+di*k,j+dj*k) in cov),None); k2=next((k for k in range(1,8) if (i-di*k,j-dj*k) in cov),None)
            if k1 and k2 and k1+k2-1<=6: bad.setdefault((round((i+.5)*S,1),round((j+.5)*S,1)),("slit",""))
# cluster
pts=sorted(bad); cl=[]
for p in pts:
    for c in cl:
        if any(abs(p[0]-q[0])<=0.25 and abs(p[1]-q[1])<=0.25 for q in c): c.append(p); break
    else: cl.append([p])
for c in cl:
    xs=[p[0] for p in c]; ys=[p[1] for p in c]
    print(f"x {min(xs):.2f}-{max(xs):.2f} y {min(ys):.2f}-{max(ys):.2f} n={len(c)} wall/need {bad[c[0]]} room {g['room_at'](c[0][0]+0.7,c[0][1]+0.7)}")
print(len(cl),"problem spots")
