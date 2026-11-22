#!/usr/bin/env python3
"""Solid element check of the mono stringer tread support with the on edge cross ARM (ladder_cad.py, mono branch).

One mid flight tread (upper flight, tread 4), as one model:
  arm      flat plate on edge across the flight under the tread, x = WEB0 - t .. WEB0, top at the tread underside,
           ARM_D0 deep for |y| <= ARM_FLAT, tapering to ARM_D1 at its tips, which stop ARM_END inside the tread ends
           (the four small screw tabs folded off its top edge are left out)
  webs     two, one each side of the 4 x 4 tube (the 5 point web polygon of bracket_solid_fea.py), two 7/16 in holes each
  flanges  folded 90 degrees off each web's vertical front edge, ARM_FL wide past the web, ARM_D0 tall, inside bend radius t,
           lying against the arm's back face, joined to it by two 3/8 in bolts (0.9 and 2.7 in below the tread underside,
           0.95 in out from the web's outer face), each modelled as a tied patch 0.75 in across (washer footprint), the rest of
           the interface free (no contact: the parts may overlap a little there, and the web front edges touch the arm untied)
  seat tab SEAT_TAB wide, bent outward off each web's top edge from x = WEB0 + 0.6 to TD + RT, inside bend radius t
  tread    (case N only) oak 1.44 x 8.5, E 1.6e6 psi, isotropic, tied to the arm's top edge and to the seat tabs
Supports: web hole surfaces fully fixed (rigid bolts in a rigid tube). Steel E 29e6 psi, nu 0.29, Fy 36 ksi, limit 0.6 Fy.

Local coordinates, inches: x = u - uk along the flight from the tread's front edge, y = v - VC across it (open side negative),
z above the tread underside. CadQuery -> gmsh 10 node tets (separate meshes per part) -> CalculiX linear static, *TIE for
the bolt patches and the tread, *BUCKLE for case E. Tie forces: consistent internal nodal forces (sum over points of
w det(J) B^T sigma) at the tied nodes, checked against the hole reactions (the *SECTION PRINT SOF values also written to job.dat
were 3 to 30 percent off and are not used). SPOOLES is the only direct solver in this CalculiX build, so the plate mesh is held
at 0.125 in (1.5 elements through 3/16 in plate) and the refined run refines a box round the open side arm root only.

Cases (300 lb down): E = arm top edge, last 2 in at the open end tip; M = arm top edge, middle 8 in;
N = 2 x 2 in patch on the oak tread at the nosing at the open end (ties: full = whole tab tops, screws = 0.5 in patches at the
two screws in each tab, none = arm top only).
Run:  python arm_bracket_solid_fea.py [--out DIR] [--only t25:E t25:M ...] [--refine 0.7]
PRELIMINARY: for an engineer's review, not for construction.
"""
import argparse, json, math, os, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ladder_geom as G
import bracket_solid_fea as B                      # web outline, hole positions, C3D10 helpers, stress post

E_ST, NU_ST, FY, ALLOW, E_OAK, NU_OAK, P = B.E_ST, B.NU_ST, B.FY, B.ALLOW, B.E_OAK, B.NU_OAK, B.P
FLIGHT, K = B.FLIGHT, B.K
XA1 = G.WEB0                                       # arm back face = flange front face = web front edge
XS0, XS1 = G.WEB0 + 0.6, G.TD + G.RT               # seat tab
YF = G.TW / 2                                      # tube side face, |y|
YT = G.VC - G.ARM_END                              # arm tip, |y|
YEND = G.VC - 0.05                                 # tread end, |y|
ZB = (-0.9, -2.7)                                  # flange bolts, z
PATCH_R, SCREW_R = 0.375, 0.25
SCREWS = [(x, s * (YF + G.SEAT_TAB / 2 + 0.3)) for x in (6.3, 8.3) for s in (-1, 1)]
OPTIONS = {"t25": 0.25, "t188": 0.1875}
CASES = ("E", "M", "N_full", "N_screws", "N_none")
SOLVER = os.environ.get("FEA_SOLVER", "SPOOLES")      # the conda CalculiX here has no PARDISO or PaStiX
H_PLATE = 0.125
QA_TIE = "POSITION TOLERANCE=0.02,ADJUST=NO"


def yb(t):
    return YF + t + 0.95                           # flange bolt line, |y|


def bolts(t):
    return [(s, z) for s in (-1, 1) for z in ZB]   # (side sign, z); y = s * yb(t)


# ---------------------------------------------------------------- geometry
def bracket(t, side):
    """one web + flange + seat tab, open side (side = -1) built and mirrored for the wall side"""
    import cadquery as cq
    V = cq.Vector
    w = cq.Wire.makePolygon([V(x, -YF, z) for x, z in B.WEB], close=True)
    s = cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), V(0, -t, 0))
    s = s.fuse(cq.Solid.makeBox(t, t + G.ARM_FL, G.ARM_D0, V(XA1, -YF - t - G.ARM_FL, -G.ARM_D0)))          # flange
    s = s.fuse(cq.Solid.makeBox(XS1 - XS0, G.SEAT_TAB, t, V(XS0, -YF - G.SEAT_TAB, -t))).clean()           # seat tab
    ok = []
    for nm, test in (("fold", lambda p: abs(p.x - XA1 - t) < 1e-6 and abs(p.y + YF + t) < 1e-6),
                     ("tab", lambda p: abs(p.y + YF + t) < 1e-6 and abs(p.z + t) < 1e-6)):
        ed = [e for e in s.Edges() if e.geomType() == "LINE" and all(test(p) for p in (e.startPoint(), e.endPoint()))]
        try:
            s = s.fillet(t, ed)
            ok.append(nm)
        except Exception as ex:
            print(f"  {nm} fillet failed ({len(ed)} edges), sharp:", ex)
    for bx, bz in B.BOLTS:
        s = s.cut(cq.Solid.makeCylinder(B.HOLE_D / 2, t + 2, V(bx, -YF + 1, bz), V(0, -1, 0)))
    if side > 0:
        s = s.mirror("XZ")
    return s, ok


def build_brep(t, case, path):
    import cadquery as cq
    V = cq.Vector
    t = float(t)
    pts = [(-YT, 0), (YT, 0), (YT, -G.ARM_D1), (G.ARM_FLAT, -G.ARM_D0), (-G.ARM_FLAT, -G.ARM_D0), (-YT, -G.ARM_D1)]
    arm = cq.Solid.extrudeLinear(cq.Face.makeFromWires(cq.Wire.makePolygon([V(XA1 - t, y, z) for y, z in pts], close=True)), V(t, 0, 0))
    bo, ok = bracket(t, -1)
    bw, _ = bracket(t, 1)
    sol = [arm, bo, bw]
    if case.startswith("N"):
        sol.append(cq.Solid.makeBox(G.TD, 2 * YEND, G.TT, V(0, -YEND, 0)))
        sol.append(cq.Solid.makeBox(B.PATCH, B.PATCH, G.TT, V(0, -YEND, 0)))
    cq.Compound.makeCompound(sol).exportBrep(path)
    print("FILLETS", ",".join(ok))


# ---------------------------------------------------------------- mesh
def mesh(t, case, ref, work, py):
    import gmsh
    brep = os.path.join(work, "geom.brep")
    r = subprocess.run([py, os.path.abspath(__file__), "--brep", str(t), case, brep], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("geometry failed: " + r.stdout + r.stderr)
    fil = [ln.split()[1] if len(ln.split()) > 1 else "" for ln in r.stdout.splitlines() if ln.startswith("FILLETS")][0]
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", int(os.environ.get("GMSH_VERBOSE", "0")))
    gmsh.option.setNumber("General.NumThreads", os.cpu_count() or 4)
    gmsh.model.add("arm")
    vols = [d for d in gmsh.model.occ.importShapes(brep) if d[0] == 3]
    oakv = [d for d in vols if gmsh.model.occ.getCenterOfMass(*d)[2] > 0]
    if len(oakv) > 1:
        gmsh.model.occ.fragment(oakv[:1], oakv[1:])              # imprint the load patch on the tread (oak only: steel parts stay separate)
    gmsh.model.occ.synchronize()
    part = {}
    for _, v in gmsh.model.getEntities(3):
        cx, cy, cz = gmsh.model.occ.getCenterOfMass(3, v)
        part[v] = "OAK" if cz > 0 else ("ARM" if cx < XA1 else ("BRO" if cy < 0 else "BRW"))
    # plate: 0.125 in everywhere (t/2 for 1/4 in, 1.5 elements through 3/16 in: SPOOLES, the only solver in this CalculiX
    # build, runs out of memory past about 250k nodes here); bends, holes, tie patches t/3. A refined run (ref < 1) scales the
    # feature sizes and the plate size inside a box round the open side arm root, flange and fold, where the peaks are.
    h0, hs, ho = ref * t / 3, H_PLATE, 0.40
    Fd = gmsh.model.mesh.field
    fl = []

    def me(expr):
        f = Fd.add("MathEval")
        Fd.setString(f, "F", expr)
        fl.append(f)
    ay = f"(Abs(y)-{YF + t})"
    outz = lambda a, b: f"((Abs(z-({(a + b) / 2}))-{abs(b - a) / 2}+Abs(Abs(z-({(a + b) / 2}))-{abs(b - a) / 2}))/2)"
    outx = lambda a, b: f"((Abs(x-({(a + b) / 2}))-{abs(b - a) / 2}+Abs(Abs(x-({(a + b) / 2}))-{abs(b - a) / 2}))/2)"
    me(f"{h0} + 0.45*Sqrt((x-{XA1 + t})^2 + {ay}^2) + 0.45*{outz(-G.ARM_D0, 0)}")                  # flange fold, inside corner
    me(f"{h0} + 0.45*Sqrt({ay}^2 + (z+{t})^2) + 0.45*{outx(XS0, XS1)}")                           # seat tab bend
    me(f"{h0} + 0.45*Sqrt({ay}^2 + (z+{G.ARM_D0})^2) + 0.45*{outx(XA1, XA1 + t)}")                 # flange bottom corner
    for xe in (XS0, XS1):
        me(f"{h0} + 0.45*Sqrt((x-{xe})^2 + (z+{t})^2 + {ay}^2)")                                   # tab ends
    for bx, bz in B.BOLTS:
        me(f"{h0} + 0.45*Abs(Sqrt((x-({bx}))^2 + (z-({bz}))^2) - {B.HOLE_D / 2}) + 0.45*Abs(Abs(y)-{YF})")
    for zb in ZB:
        me(f"{h0} + 0.35*((Sqrt((Abs(y)-{yb(t)})^2 + (z-({zb}))^2)-{PATCH_R})+Abs(Sqrt((Abs(y)-{yb(t)})^2 + (z-({zb}))^2)-{PATCH_R}))/2 + 0.45*Abs(x-{XA1})")
    if case == "N_screws":
        for sx, sy in SCREWS:
            me(f"{h0} + 0.35*Sqrt((x-{sx})^2 + (y-({sy}))^2) + 0.45*Abs(z)")
    for grp, hv in (("steel", hs), ("OAK", ho)):
        vl = [v for v, p in part.items() if (p == "OAK") == (grp == "OAK")]
        if vl:
            f = Fd.add("Constant")
            Fd.setNumbers(f, "VolumesList", vl)
            Fd.setNumber(f, "VIn", hv)
            Fd.setNumber(f, "VOut", 1e3)
            fl.append(f)
    if ref < 1:
        f = Fd.add("Box")
        for k_, v_ in (("VIn", ref * H_PLATE), ("VOut", 1e3), ("XMin", 3.5), ("XMax", 6.5), ("YMin", -5.5), ("YMax", -1.5), ("ZMin", -4.5), ("ZMax", 0.5)):
            Fd.setNumber(f, k_, v_)
        fl.append(f)
    fm = Fd.add("Min")
    Fd.setNumbers(fm, "FieldsList", fl)
    Fd.setAsBackgroundMesh(fm)
    for k_, v_ in (("Mesh.MeshSizeExtendFromBoundary", 0), ("Mesh.MeshSizeFromPoints", 0), ("Mesh.MeshSizeFromCurvature", 0),
                   ("Mesh.Algorithm3D", 10), ("Mesh.Optimize", 1), ("Mesh.ElementOrder", 2), ("Mesh.SecondOrderLinear", 0),
                   ("Mesh.MeshSizeMax", 0.6), ("Mesh.HighOrderOptimize", 2)):
        gmsh.option.setNumber(k_, v_)
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(2)
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    X = np.zeros((int(tags.max()) + 1, 3))
    X[tags.astype(int)] = xyz.reshape(-1, 3)
    els = {}
    for grp in ("ARM", "BRO", "BRW", "OAK"):
        cs = []
        for v, p in part.items():
            if p != grp:
                continue
            et, _, en = gmsh.model.mesh.getElements(3, v)
            for ty, nn in zip(et, en):
                assert ty == 11
                cs.append(nn.reshape(-1, 10).astype(int))
        els[grp] = np.vstack(cs) if cs else np.zeros((0, 10), int)
    holes = {}
    for v, p in part.items():
        if not p.startswith("BR"):
            continue
        for _, s in gmsh.model.getBoundary([(3, v)], oriented=False):
            if gmsh.model.getType(2, s) != "Cylinder":
                continue
            bb = gmsh.model.getBoundingBox(2, s)
            cx, cz = (bb[0] + bb[3]) / 2, (bb[2] + bb[5]) / 2
            for i, (bx, bz) in enumerate(B.BOLTS):
                if abs(cx - bx) < 0.3 and abs(cz - bz) < 0.3 and bb[3] - bb[0] < B.HOLE_D + 0.01:
                    nt, _, _ = gmsh.model.mesh.getNodes(2, s, includeBoundary=True)
                    holes.setdefault(f"{'open' if p == 'BRO' else 'wall'}_hole{i + 1}", set()).update(nt.astype(int).tolist())
    gmsh.finalize()
    assert len(holes) == 4, holes.keys()
    m = dict(X=X, els=els, t=t, case=case, fillets=fil, holes={k: np.array(sorted(v)) for k, v in holes.items()},
             sizes=dict(fine=h0, plate=hs, oak=ho, refine=ref))
    m["c"] = {g: B.ccx_elements(X, e) for g, e in els.items() if len(e)}
    m["ccx_STEEL"] = np.vstack([m["c"][g] for g in ("ARM", "BRO", "BRW")])
    m["arm_nodes"] = np.unique(els["ARM"])
    m["br_nodes"] = np.unique(np.concatenate([els["BRO"].ravel(), els["BRW"].ravel()]))
    return m


def faces(m, grp, test):
    """element faces (global element id, face no) of group grp whose corner points pass test, and their 6 node triangles"""
    c = m["c"][grp]
    out, tris = [], []
    for i, k in B.plane_faces(m["X"], c, test):
        out.append((m["eid0"][grp] + i, k))
        tris.append(c[i][list(B.FACES[k - 1]) + list(B.EDGE6[k - 1])])
    return out, np.array(tris)


# ---------------------------------------------------------------- CalculiX
def write_inp(path, m, buckle=False):
    X, t, case = m["X"], m["t"], m["case"]
    grps = [g for g in ("ARM", "BRO", "BRW", "OAK") if g in m["c"]]
    used = np.unique(np.concatenate([m["c"][g].ravel() for g in grps]))
    L = ["*NODE"] + [f"{n},{X[n, 0]:.9g},{X[n, 1]:.9g},{X[n, 2]:.9g}" for n in used]
    eid, m["eid0"] = 1, {}
    for g in grps:
        m["eid0"][g] = eid
        L.append(f"*ELEMENT,TYPE=C3D10,ELSET=E{g}")
        L += [f"{eid + i}," + ",".join(map(str, r)) for i, r in enumerate(m["c"][g])]
        eid += len(m["c"][g])
    L += ["*ELSET,ELSET=ESTEEL", "EARM,EBRO,EBRW"]

    def nset(name, nodes, surf=False):
        L.append(f"*SURFACE,NAME={name},TYPE=NODE" if surf else f"*NSET,NSET={name}")
        nodes = list(map(int, nodes))
        if surf:
            L.extend(map(str, nodes))
        else:
            L.extend(",".join(map(str, nodes[i:i + 12])) for i in range(0, len(nodes), 12))

    def esurf(name, fc):
        L.append(f"*SURFACE,NAME={name},TYPE=ELEMENT")
        L.extend(f"{e},S{k}" for e, k in fc)
    nset("NODES", used)
    for k, v in m["holes"].items():
        nset(k.upper(), v)
    tie, sec = [], []
    bn = m["br_nodes"]
    for i, (s, zb) in enumerate(bolts(t)):                     # flange to arm bolts: flange nodes in the washer disc -> arm back face
        r = np.hypot(X[bn, 1] - s * yb(t), X[bn, 2] - zb)
        sl = bn[(np.abs(X[bn, 0] - XA1) < 1e-6) & (r <= PATCH_R + 1e-6)]
        fc, _ = faces(m, "ARM", lambda p, s=s, zb=zb: (np.abs(p[..., 0] - XA1) < 1e-6).all(axis=1) &
                      (np.hypot(p[..., 1].mean(axis=1) - s * yb(t), p[..., 2].mean(axis=1) - zb) < PATCH_R + 0.3))
        nm = f"B{i + 1}"
        nset(f"S{nm}", sl, True)
        esurf(f"M{nm}", fc)
        tie.append(nm)
        sec.append(f"M{nm}")
        m.setdefault("patch_nodes", {})[nm] = len(sl)
    if case.startswith("N"):
        an = m["arm_nodes"]
        nset("SARMTOP", an[np.abs(X[an, 2]) < 1e-6], True)
        if case != "N_none":
            top = (np.abs(X[bn, 2]) < 1e-6) & (X[bn, 0] > XS0 - 1e-6)
            if case == "N_screws":
                top &= np.min([np.hypot(X[bn, 0] - sx, X[bn, 1] - sy) for sx, sy in SCREWS], axis=0) <= SCREW_R + 1e-6
            nset("STABTOP", bn[top], True)
        fc, _ = faces(m, "OAK", lambda p: (np.abs(p[..., 2]) < 1e-6).all(axis=1))
        esurf("MOAKBOT", fc)
        fa, _ = faces(m, "ARM", lambda p: (np.abs(p[..., 2]) < 1e-6).all(axis=1))
        esurf("FARMTOP", fa)
        sec.append("FARMTOP")
        for g, nm in (("BRO", "FTABO"), ("BRW", "FTABW")):
            ft, _ = faces(m, g, lambda p: (np.abs(p[..., 2]) < 1e-6).all(axis=1) & (p[..., 0].min(axis=1) > XS0 - 1e-6))
            esurf(nm, ft)
            sec.append(nm)
    L += ["*MATERIAL,NAME=STEEL", "*ELASTIC", f"{E_ST},{NU_ST}", "*SOLID SECTION,ELSET=ESTEEL,MATERIAL=STEEL"]
    if "OAK" in m["c"]:
        L += ["*MATERIAL,NAME=OAK", "*ELASTIC", f"{E_OAK},{NU_OAK}", "*SOLID SECTION,ELSET=EOAK,MATERIAL=OAK"]
    for nm in tie:
        L += [f"*TIE,NAME=T{nm},{QA_TIE}", f"S{nm},M{nm}"]
    if case.startswith("N"):
        L += [f"*TIE,NAME=TARM,{QA_TIE}", "SARMTOP,MOAKBOT"]
        if case != "N_none":
            L += [f"*TIE,NAME=TTAB,{QA_TIE}", "STABTOP,MOAKBOT"]
    L += ["*STEP", f"*BUCKLE,SOLVER={SOLVER}", "2"] if buckle else ["*STEP", f"*STATIC,SOLVER={SOLVER}"]
    L += ["*BOUNDARY"] + [f"{k.upper()},1,3" for k in m["holes"]]
    L.append("*CLOAD")
    L += [f"{n},3,{-f:.9g}" for n, f in m["loads"].items()]
    if buckle:
        L +=["*NODE PRINT,NSET=NODES", "U", "*END STEP"]
    else:
        L += ["*NODE PRINT,NSET=NODES", "U"]
        for k in m["holes"]:
            L += [f"*NODE PRINT,NSET={k.upper()},TOTALS=ONLY", "RF"]
        for s in sec:
            L += [f"*SECTION PRINT,SURFACE={s},NAME=P{s}", "SOF"]
        L += ["*EL PRINT,ELSET=ESTEEL", "S", "*END STEP"]
    open(path, "w").write("\n".join(L) + "\n")


def ccx_run(ccx, work, name):
    nc = os.environ.get("FEA_THREADS") or str(os.cpu_count() or 4)
    d = os.path.dirname(os.path.abspath(ccx))
    extra = [d, os.path.dirname(d), os.path.dirname(os.path.dirname(d)), os.path.join(os.path.dirname(d), "mingw-w64", "bin")]
    env = dict(os.environ, OMP_NUM_THREADS=nc, CCX_NPROC_EQUATION_SOLVER=nc, PATH=os.pathsep.join(extra + [os.environ.get("PATH", "")]))
    r = subprocess.run([ccx, "-i", name], cwd=work, env=env, capture_output=True, text=True)
    open(os.path.join(work, name + ".log"), "w").write(r.stdout + r.stderr)
    if r.returncode != 0 or "*ERROR" in r.stdout:
        raise RuntimeError("ccx failed:\n" + r.stdout[-3000:] + r.stderr[-2000:])
    return r.stdout


def parse_sof(path):
    """*SECTION PRINT SOF: {surface: (Fx, Fy, Fz) force of the rest of the model on the part through that surface}"""
    out, cur, want = {}, None, False
    for ln in open(path):
        if "statistics for surface set" in ln:
            cur = ln.split("surface set")[1].split()[0]
        elif cur and "total surface force" in ln:
            want = True
        elif want and ln.strip():
            out[cur] = [float(v) for v in ln.split()[:3]]
            want = False
    return out


def parse_buckle(path):
    fac, on = [], False
    for ln in open(path):
        if "B U C K L I N G" in ln:
            on = True
        elif on:
            p = ln.split()
            if len(p) == 2 and p[0].isdigit():
                fac.append(float(p[1]))
            elif fac and not p:
                break
    return fac


def first_disp(path, n):
    """mode 1 shape: the first displacement block after the buckling factors (the one before them is the static preload)"""
    U, on, cnt, past = np.zeros((n, 3)), False, 0, False
    for ln in open(path):
        if "B U C K L I N G" in ln:
            past = True
        if past and "displacements (vx,vy,vz)" in ln:
            if on:
                break
            on = True
            continue
        if on:
            p = ln.split()
            if len(p) == 4:
                U[int(p[0])] = [float(v) for v in p[1:]]
                cnt += 1
            elif cnt and not p:
                pass
    return U


# ---------------------------------------------------------------- post
def zones(m, P_, is_arm):
    t = m["t"]
    x, ya, z = P_[:, 0], np.abs(P_[:, 1]), P_[:, 2]
    br = ~is_arm
    dh = np.min([np.hypot(x - bx, z - bz) for bx, bz in B.BOLTS], axis=0) - B.HOLE_D / 2
    near_hole = br & (dh < 0.30) & (ya < YF + t + 0.01)
    dp = np.min([np.hypot(ya - yb(t), z - zb) for zb in ZB], axis=0)
    near_patch = (np.abs(dp - PATCH_R) < 0.25) & (np.abs(x - XA1) < 0.1)      # tie patch edges, both parts (surface layer)
    near_fcorner = br & (np.hypot(ya - YF - t, z + G.ARM_D0) < 0.35) & (x < XA1 + t + 0.35)
    near_tabend = br & (np.min([np.hypot(x - xe, z + t) for xe in (XS0, XS1)], axis=0) < 0.35) & (ya < YF + t + 0.35)
    near_screw = np.zeros(len(x), bool)
    if m["case"] == "N_screws":
        near_screw = br & (np.min([np.hypot(x - sx, np.abs(P_[:, 1]) - abs(sy)) for sx, sy in SCREWS], axis=0) < SCREW_R + 0.25) & (z > -2 * t)
    near_tread = np.zeros(len(x), bool)
    if m["case"].startswith("N"):                  # tread bonded on the arm's top edge (and the tab tops): 90 degree bonded corners, singular
        near_tread = is_arm & (z > -0.3)
        if m["case"] == "N_full":
            near_tread |= br & (z > -0.3) & (x > XS0 - 0.3) & ((ya > YF + G.SEAT_TAB - 0.3) | (x < XS0 + 0.3) | (x > XS1 - 0.3))
    sing = near_hole | near_patch | near_fcorner | near_tabend | near_screw | near_tread
    fold = br & (x <= XA1 + 4 * t) & (ya <= YF + 4 * t) & (z >= -G.ARM_D0) & ~near_fcorner & ~near_tabend
    flange = br & (x <= XA1 + t + 1e-4) & (ya > YF + 4 * t)
    tab = br & (z > -t - 1e-4) & (ya > YF + t + 1e-4) & ~fold
    web = br & ~fold & ~flange & ~tab
    root = is_arm & (ya >= YF - 0.25) & (ya <= YF + t + G.ARM_FL + 0.5)
    return dict(sing=sing, near_hole=near_hole, near_patch=near_patch, near_fcorner=near_fcorner, near_tabend=near_tabend,
                near_tread=near_tread, near_screw=near_screw, fold=fold, flange=flange, tab=tab, web=web, root=root, arm=is_arm, away=~sing)


def where(p, m, is_arm):
    x, y, z = p
    t, ya = m["t"], abs(p[1])
    side = "open side" if y < 0 else "wall side"
    Z = {k: v[0] for k, v in zones(m, np.array([p]), np.array([is_arm])).items()}
    if Z["near_hole"]:
        return f"{side} web: edge of a fixed bolt hole (singular)"
    if Z["near_patch"]:
        return f"{side} {'arm' if is_arm else 'flange'}: edge of a tied bolt patch (singular), z = {z:.2f}"
    if Z["near_fcorner"]:
        return f"{side}: sharp re-entrant corner at the bottom of the flange fold (no relief, singular)"
    if Z["near_tabend"]:
        return f"{side}: sharp corner at an end of the seat tab bend (singular)"
    if Z["near_tread"] or Z["near_screw"]:
        return f"{side} {'arm top edge' if is_arm else 'seat tab'}: edge of the bonded tread tie (singular), y = {y:.2f}"
    if is_arm:
        return f"arm, {'over the flanges (root)' if Z['root'] else ('between the webs' if ya < YF else 'cantilever')}, y = {y:.2f}, z = {z:.2f}, {'back' if x > XA1 - t / 2 else 'front'} face side"
    for k in ("fold", "flange", "tab", "web"):
        if Z[k]:
            return f"{side} {k}, x = {x:.2f}, |y| = {ya:.2f}, z = {z:.2f}"
    return f"{side} bracket x = {x:.2f}, z = {z:.2f}"


GP = (0.1381966011250105, 0.5854101966249685)


def c3d10_dN():
    """shape function derivatives (4 integration points, 10 nodes, 3 natural directions) of the CalculiX C3D10, 4 point rule"""
    b, a = GP
    pts = [(b, b, b), (a, b, b), (b, a, b), (b, b, a)]
    out = np.zeros((4, 10, 3))
    for i, (xi, et, ze) in enumerate(pts):
        L = [1 - xi - et - ze, xi, et, ze]
        dL = np.array([[-1, -1, -1], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
        for k in range(4):
            out[i, k] = (4 * L[k] - 1) * dL[k]
        for j, (p, q) in enumerate(((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))):
            out[i, 4 + j] = 4 * (L[p] * dL[q] + L[q] * dL[p])
    return out


def internal_forces(m, S):
    """consistent nodal forces of the steel elements' stresses, f = sum over points of w det(J) B^T sigma (lb): at a node with
    no load and no support this is the force the ties put into the part there"""
    c = m["ccx_STEEL"]
    X = m["X"]
    dN = c3d10_dN()
    xe = X[c]                                          # (ne, 10, 3)
    s = S[:, 2:].reshape(len(c), 4, 6)
    sig = np.zeros((len(c), 4, 3, 3))
    for (i, j), k in (((0, 0), 0), ((1, 1), 1), ((2, 2), 2), ((0, 1), 3), ((0, 2), 4), ((1, 2), 5)):
        sig[..., i, j] = sig[..., j, i] = s[..., k]
    f = np.zeros((X.shape[0], 3))
    for g in range(4):
        J = np.einsum("ekd,kn->end", xe, dN[g])        # J[e, n, d] = dx_d / d natural_n
        Ji = np.linalg.inv(J)
        dX = np.einsum("kn,edn->ekd", dN[g], Ji)       # dN_k / dx_d
        w = np.abs(np.linalg.det(J)) / 24.0
        fe = np.einsum("e,ekd,edj->ekj", w, dX, sig[:, g])
        np.add.at(f, c.ravel(), fe.reshape(-1, 3))
    return f


def contour_png(path, m, vm, title, peak_p):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    c = m["ccx_STEEL"][:, :4]
    fcs = np.vstack([c[:, [0, 1, 2]], c[:, [0, 1, 3]], c[:, [1, 2, 3]], c[:, [0, 2, 3]]])
    _, inv, cnt = np.unique(np.sort(fcs, axis=1), axis=0, return_inverse=True, return_counts=True)
    bf = fcs[cnt[inv.ravel()] == 1]
    X = m["X"]
    val = vm[bf].mean(axis=1)
    cmap = plt.get_cmap("turbo")
    fig = plt.figure(figsize=(15, 6.5))
    for i, (el, az, lab) in enumerate(((5, 180, "from the front (looking back along the flight at the arm)"), (25, -35, "from the open side, behind and above"))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(X[bf], facecolors=cmap(np.clip(val / FY, 0, 1)), edgecolors="none"))
        lo, hi = X[bf].reshape(-1, 3).min(axis=0), X[bf].reshape(-1, 3).max(axis=0)
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(hi - lo)
        ax.view_init(elev=el, azim=az)
        ax.plot([peak_p[0]], [peak_p[1]], [peak_p[2]], "k*", ms=14, mec="w")
        ax.set_xlabel("x along flight"); ax.set_ylabel("y across (open side -)"); ax.set_zlabel("z")
        ax.set_title(lab, fontsize=9)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, FY))
    cb = fig.colorbar(sm, ax=fig.axes, shrink=0.7, label="von Mises (psi), capped at 36,000 (Fy); line at 0.6 Fy = 21,600")
    cb.ax.axhline(ALLOW, color="k", lw=2)
    fig.suptitle(title, fontsize=10)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def set_loads(m):
    X, t, case = m["X"], m["t"], m["case"]
    if case.startswith("N"):
        _, tr = faces(m, "OAK", lambda p: (np.abs(p[..., 2] - G.TT) < 1e-6).all(axis=1) & (p[..., 0].max(axis=1) <= B.PATCH + 1e-6) &
                      (p[..., 1].max(axis=1) <= -YEND + B.PATCH + 1e-6))
        lp = (B.PATCH / 2, -YEND + B.PATCH / 2, G.TT)
    else:
        rng = (-YT, -YT + 2.0) if case == "E" else (-4.0, 4.0)
        _, tr = faces(m, "ARM", lambda p: (np.abs(p[..., 2]) < 1e-6).all(axis=1) & (p[..., 1].mean(axis=1) >= rng[0]) & (p[..., 1].mean(axis=1) <= rng[1]))
        lp = (XA1 - t / 2, -YT if case == "E" else 0.0, 0.0)
    m["loads"], area = B.tri6_loads(X, tr, P)
    ln = np.unique(tr)
    m["load_node"] = int(ln[np.argmin(np.linalg.norm(X[ln] - lp, axis=1))])
    an = m["arm_nodes"]
    m["tip_node"] = int(an[np.argmin(np.linalg.norm(X[an] - (XA1 - t / 2, -YT, 0.0), axis=1))])
    return area


def analyse(ccx, opt, case, ref, out, work, py, tag="", buckle=False):
    t0 = time.time()
    os.makedirs(work, exist_ok=True)
    t = OPTIONS[opt]
    m = mesh(t, case, ref, work, py)
    X = m["X"]
    m["eid0"] = {}
    e = 1
    for g in ("ARM", "BRO", "BRW", "OAK"):
        if g in m["c"]:
            m["eid0"][g] = e
            e += len(m["c"][g])
    area = set_loads(m)
    ne = len(m["ccx_STEEL"])
    print(f"  mesh {opt} {case} ref {ref}: {ne} steel + {len(m['els']['OAK'])} oak tets, fillets [{m['fillets']}] ({time.time() - t0:.0f} s)", flush=True)
    write_inp(os.path.join(work, "job.inp"), m)
    t1 = time.time()
    ccx_run(ccx, work, "job")
    with open(os.path.join(work, "job.dat")) as fi, open(os.path.join(work, "job_nosof.dat"), "w") as fo:
        skip = False                                       # parse_dat does not know *SECTION PRINT blocks
        for ln in fi:
            if "statistics for surface set" in ln:
                skip = True
            elif " for set " in ln:
                skip = False
            if not skip:
                fo.write(ln)
    b = B.parse_dat(os.path.join(work, "job_nosof.dat"))
    U = np.zeros_like(X)
    u = b[("displacements", "NODES")].reshape(-1, 4)
    U[u[:, 0].astype(int)] = u[:, 1:]
    R = {k: b[("total force", k.upper())][-3:] for k in m["holes"]}
    S = b[("stresses", "ESTEEL")].reshape(-1, 8)
    sof = parse_sof(os.path.join(work, "job.dat"))
    vm, ok, ipvm = B.nodal_stress(m, S)
    sn = np.where(ok)[0]
    is_arm = np.isin(sn, m["arm_nodes"])
    Z = zones(m, X[sn], is_arm)
    v = vm[sn]

    def pk(mask):
        if not mask.any():
            return None
        j = int(np.argmax(np.where(mask, v, -1)))
        return dict(von_mises_psi=round(float(v[j]), 0), at_xyz_in=[round(float(a), 3) for a in X[sn[j]]], where=where(X[sn[j]], m, bool(is_arm[j])))
    away = Z["away"]
    tips = {"arm_tip_open_end": m["tip_node"], "load_point": m["load_node"]}
    fint = internal_forces(m, S)
    for k_, nds in m["holes"].items():                 # check: internal forces at the fixed hole nodes = the reactions
        assert np.allclose(fint[nds].sum(axis=0), R[k_], atol=0.02 * P), (k_, fint[nds].sum(axis=0), R[k_])
    an = m["arm_nodes"]
    bf = {}
    for i, (s, zb) in enumerate(bolts(t)):
        sel = an[(np.abs(X[an, 0] - XA1) < 1e-6) & (np.hypot(X[an, 1] - s * yb(t), X[an, 2] - zb) < PATCH_R + 0.3)]
        f = fint[sel].sum(axis=0)
        bf[f"{'open' if s < 0 else 'wall'}_{'upper' if zb == ZB[0] else 'lower'}_bolt"] = dict(
            Fx_axial=round(f[0], 1), Fy=round(f[1], 1), Fz=round(f[2], 1), shear=round(math.hypot(f[1], f[2]), 1), at_y_z=[round(s * yb(t), 3), zb])
    d = dict(variant=f"{opt}_{case}{tag}", plate_t_in=t, case=case, refine=ref,
             inside_bend_radius_in=dict(flange_fold=t if "fold" in m["fillets"] else 0.0, seat_tab=t if "tab" in m["fillets"] else 0.0),
             mesh=dict(steel_tets=ne, oak_tets=len(m["els"]["OAK"]), element="C3D10", **m["sizes"], tie_patch_slave_nodes=m["patch_nodes"]),
             load_lb=P, load_area_in2=round(area, 3),
             peak_von_mises=pk(np.ones(len(v), bool)),
             peak_away_from_singular_spots=pk(away),
             arm_root_away=pk(Z["root"] & away), arm_root_incl_patch_edges=pk(Z["root"]),
             arm_peak_away=pk(Z["arm"] & away),
             flange_fold=pk(Z["fold"] & away), flange_outside_fold=pk(Z["flange"] & away),
             web=pk(Z["web"] & away), seat_tab=pk(Z["tab"] & away),
             singular_zone_peaks=dict(bolt_holes=pk(Z["near_hole"]), tie_patch_edges=pk(Z["near_patch"]),
                                      flange_fold_bottom_corner=pk(Z["near_fcorner"]), tab_ends=pk(Z["near_tabend"]), tread_tie_edges=pk(Z["near_tread"] | Z["near_screw"])),
             integration_point_peak_away_psi=None,
             deflection_in={k: dict(at=[round(float(a), 3) for a in X[n]], uz=round(float(U[n, 2]), 5), ux=round(float(U[n, 0]), 5))
                            for k, n in tips.items()},
             max_abs_uz_steel_in=round(float(np.abs(U[m["ccx_STEEL"].ravel(), 2]).max()), 5),
             flange_bolt_forces_lb=bf,
             note_bolt_forces="force from the flange on the arm through each tied patch (consistent internal nodal forces of the arm at its patch nodes, checked against the hole reactions); Fx is along the bolt axis (+ pulls the arm off the flange toward the front)",
             web_hole_reactions_lb={k: dict(Fx=round(float(r[0]), 1), Fy=round(float(r[1]), 1), Fz=round(float(r[2]), 1)) for k, r in sorted(R.items())},
             sum_hole_reactions_z_lb=round(float(sum(r[2] for r in R.values())), 2),
             solve_s=round(time.time() - t1, 1))
    cen = X[m["ccx_STEEL"][:, :4]].mean(axis=1)
    Ze = zones(m, cen, np.arange(len(cen)) < len(m["c"]["ARM"]))
    d["integration_point_peak_away_psi"] = round(float(ipvm.max(axis=1)[Ze["away"]].max()), 0)
    if case.startswith("N"):
        bn = m["br_nodes"]
        top_a = an[np.abs(X[an, 2]) < 1e-6]
        d["tread_tie_forces_lb"] = {"note": "force of the tread on each part (consistent nodal forces at the tied nodes), z + up",
                                    "arm_top": [round(float(v_), 1) for v_ in fint[top_a].sum(axis=0)]}
        for nm, sg in (("open_tab", -1), ("wall_tab", 1)):
            sel = bn[(np.abs(X[bn, 2]) < 1e-6) & (X[bn, 0] > XS0 - 1e-6) & (np.sign(X[bn, 1]) == sg)]
            d["tread_tie_forces_lb"][nm] = [round(float(v_), 1) for v_ in fint[sel].sum(axis=0)]
    d["under_0p6Fy_away_from_singular_spots"] = bool(d["peak_away_from_singular_spots"]["von_mises_psi"] <= ALLOW)
    if buckle:
        tb = time.time()
        try:
            write_inp(os.path.join(work, "buck.inp"), m, buckle=True)
            ccx_run(ccx, work, "buck")
            fac = parse_buckle(os.path.join(work, "buck.dat"))
            Ub = first_disp(os.path.join(work, "buck.dat"), X.shape[0])
            an = m["arm_nodes"]
            j = an[np.argmax(np.linalg.norm(Ub[an], axis=1))]
            jj = int(np.argmax(np.linalg.norm(Ub, axis=1)))
            d["buckling"] = dict(factors=[round(f_, 2) for f_ in fac], mode1_max_disp_at=[round(float(a), 2) for a in X[jj]],
                                 mode1_in_arm=dict(at=[round(float(a), 2) for a in X[j]], direction=[round(float(a), 3) for a in Ub[j] / np.linalg.norm(Ub[j])]),
                                 solve_s=round(time.time() - tb, 1), ran_cleanly=bool(fac))
        except Exception as ex:
            d["buckling"] = dict(ran_cleanly=False, error=str(ex)[-800:])
    json.dump(d, open(os.path.join(out, d["variant"] + ".json"), "w"), indent=1)
    if not tag:
        pa = d["peak_away_from_singular_spots"]
        contour_png(os.path.join(out, d["variant"] + ".png"), m, vm,
                    f"{d['variant']}: t = {t} in, case {case}, 300 lb. Peak away from singular spots {pa['von_mises_psi']:,.0f} psi (star: {pa['where']}); "
                    f"arm tip uz {d['deflection_in']['arm_tip_open_end']['uz']:.3f} in", pa["at_xyz_in"])
    print(f"    peak {d['peak_von_mises']['von_mises_psi']:.0f} ({d['peak_von_mises']['where']}); away {d['peak_away_from_singular_spots']['von_mises_psi']:.0f} "
          f"({d['peak_away_from_singular_spots']['where']}); tip uz {d['deflection_in']['arm_tip_open_end']['uz']:.4f}; "
          f"bolts {[v_['shear'] for v_ in bf.values()]}; sum Rz {d['sum_hole_reactions_z_lb']} ({time.time() - t1:.0f} s)"
          + (f"; buckling {d['buckling']}" if buckle else ""), flush=True)
    return d


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--brep":
        build_brep(*sys.argv[2:])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "..", "ladder-fea-results", "arm"))
    ap.add_argument("--only", nargs="*", help="opt:case[:ref] e.g. t25:E t188:E t25:E:0.7")
    ap.add_argument("--ccx", default=os.environ.get("CCX") or shutil.which("ccx") or "ccx")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    jobs = a.only or ["t25:E", "t25:M", "t25:N_full", "t25:N_screws", "t25:N_none", "t188:E", "t25:E:0.7"]
    for j in jobs:
        p = j.split(":")
        ref = float(p[2]) if len(p) > 2 else 1.0
        tag = f"_ref{p[2]}" if len(p) > 2 else ""
        analyse(a.ccx, p[0], p[1], ref, out, os.path.join(out, f"_work_{p[0]}_{p[1]}{tag}"), sys.executable, tag, buckle=(p[1] == "E" and not tag))


if __name__ == "__main__":
    main()
