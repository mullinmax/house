#!/usr/bin/env python3
"""Solid element stress analysis of one mono (single centre stringer) tread bracket of the loft ships ladder.

The bracket is the bent steel plate ladder_cad.py draws for the mono stringer: a web (the five point polygon A, C, C + n*LAP,
B + n*LAP, B) lying against the side face of the 4 x 4 tube, and a seat flange SEAT_W wide, t thick, from u = uk + 1 to
uk + TD + RT, bent outward from the web's top edge with an inside bend radius equal to t. Two 7/16 in bolt holes in the web,
4 in apart on a line parallel to the slope, BOLT_N below the tube's top face (square to the slope), centred on Flight.bolt_u(k).

Model: CadQuery solids -> gmsh 10 node tetrahedra (bonded, conformal steel / oak interface) -> CalculiX linear static.
Local coordinates, inches: x = u - uk (horizontal, along the flight, from the tread's front edge), y = v - VC (across the
flight, 0 on the stringer centreline, the open side negative), z = height above the tread underside (seat top = 0). Units lb, in, psi.

Variants (each with bolts only, and with bolts plus normal contact of the web's back face on the tube face):
  options  t25 = 1/4 in plate, t375 = 3/8 in plate, t25g = 1/4 in plate with one 1/4 in, 3 x 3 in triangular gusset
  loads    A_half  300 lb on a 2 x 2 in patch at the open end of the oak tread, the tread modelled from the open end to the
                   stringer centreline and free there (no help from the far bracket)
           A_cont  the same load, the tread continuous across the stringer onto the mirror bracket (both brackets modelled,
                   tube taken as rigid between them)
           B_seat  300 lb spread uniformly on the seat's top face (no tread)

Bolt holes: hole surfaces fully fixed (rigid bolts in a rigid tube). Contact: the web's back face below the tube top may bear on
a rigid, frictionless tube face, no tension; solved exactly on a model condensed by CalculiX (*SUBSTRUCTURE GENERATE) onto contact
points about 0.25 in apart, then the contact forces are applied in a final run. The tread is bonded to the seat (stands in for the
two screws). Stresses: integration point values extrapolated to corners and averaged over steel elements only. Sharp re-entrant
corners (web front edge and seat back end at the bend, the gusset's welded edges) and the fixed hole edges are singular and are
reported separately from the "away from singularities" peak.

Run:  python bracket_solid_fea.py [--out DIR]                      everything (slow: the contact runs take 3 to 70 min each)
      python bracket_solid_fea.py --only t25:A_half [t375:B_seat ...]  python bracket_solid_fea.py --fine t25 [--refine 0.7]
      python bracket_solid_fea.py --collect                         summary.json from the result files
Needs cadquery, gmsh, numpy, matplotlib and a CalculiX ccx executable (env CCX, --ccx, or on PATH). FEA_THREADS sets solver threads.
PRELIMINARY: for an engineer's review, not for construction.
"""
import argparse, json, math, os, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ladder_geom as G

assert G.MONO, "model/config.toml ladder_stringer must be 'mono'"

# ---------------------------------------------------------------- inputs
E_ST, NU_ST, FY = 29.0e6, 0.29, 36000.0          # A36
ALLOW = 0.6 * FY                                  # 21,600 psi
E_OAK, NU_OAK = 1.6e6, 0.3                        # white oak, taken isotropic
P = 300.0                                         # lb
HOLE_D, BOLT_SP = 7 / 16, 4.0
TG, GLEG = 0.25, 3.0                              # gusset plate thickness and leg length
PATCH = 2.0                                       # load patch, square
FLIGHT, K = G.UPPER, 4                            # a mid flight tread (every non foot tread has the same bracket)
OPTIONS = {"t25": (0.25, False), "t375": (0.375, False), "t25g": (0.25, True)}
LOADS = ("A_half", "A_cont", "B_seat")
SUPPORTS = ("bolts", "bolts+contact")

# Round 8 (Maxwell 11/24/2026): the no strip option. BRACKET_R8=1 uses the round 7 web (G.bracket_web, a hull round the bolts), a seat
# along the web's whole top edge (no flange to a strip), BRACKET_SEAT_W wide, under a BRACKET_TT thick tread.
R8 = os.environ.get("BRACKET_R8", "0") == "1"
if R8:
    G.SEAT_W = float(os.environ.get("BRACKET_SEAT_W", "1.5"))
    G.TT = float(os.environ.get("BRACKET_TT", "1.75"))
    OPTIONS["t25"], OPTIONS["t375"] = (0.25, False), (0.375, False)
CA, SA, SL = math.cos(G.ANG), math.sin(G.ANG), G.SL
XS0, XS1 = (G.WEB0 if R8 else 1.0), G.TD + G.RT   # seat, along x
XW = G.WEB0                                       # web front edge
YF = -G.TW / 2                                    # tube side face (open side)
ZL = lambda x: (x - G.TD - G.RT) * SL             # tube top line, relative to the tread underside
A_, B_ = (XW, 0.0), (XS1, 0.0)
C_ = (XW, ZL(XW))
NV = (SA, -CA)                                    # unit normal to the slope, pointing down into the tube side
WEB = [A_, C_, (C_[0] + NV[0] * G.LAP, C_[1] + NV[1] * G.LAP), (B_[0] + NV[0] * G.LAP, B_[1] + NV[1] * G.LAP), B_]
if R8:
    _uk, _zk = FLIGHT.uk(K), FLIGHT.z0 + K * G.RI - G.TT
    WEB = [(u - _uk, z - _zk) for u, z in G.bracket_web(FLIGHT, K)]
BU = FLIGHT.bolt_u(K) - FLIGHT.uk(K)              # bolt group centroid, x
BC = (C_[0] + 6.25 * CA + G.BOLT_N * SA, C_[1] + 6.25 * SA - G.BOLT_N * CA)
assert abs(BC[0] - BU) < 1e-9
BOLTS = [(BC[0] - s * BOLT_SP / 2 * CA, BC[1] - s * BOLT_SP / 2 * SA) for s in (1, -1)]   # lower hole first
XG = (XS0 + XS1) / 2                              # gusset at mid seat length
YEND = -(G.VC - 0.05)                             # tread's open end (the tread runs 0.05 in short of each side line)
PX = (G.TD / 2 - PATCH / 2, G.TD / 2 + PATCH / 2)  # load patch: centred on the tread depth, at the open end
PY = (YEND, YEND + PATCH)
LOAD_PT = (G.TD / 2, YEND + PATCH / 2, G.TT)


# ---------------------------------------------------------------- geometry
def bracket_solid(t, gusset):
    import cadquery as cq
    V = cq.Vector
    w = cq.Wire.makePolygon([V(x, YF, z) for x, z in WEB], close=True)
    web = cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), V(0, -t, 0))
    seat = cq.Solid.makeBox(XS1 - XS0, G.SEAT_W, t, V(XS0, YF - G.SEAT_W, -t))
    s = web.fuse(seat).clean()
    yc, zc = YF - t, -t                            # the inside corner of the bend
    edges = [e for e in s.Edges() if e.geomType() == "LINE" and
             all(abs(p.y - yc) < 1e-6 and abs(p.z - zc) < 1e-6 for p in (e.startPoint(), e.endPoint()))]
    filleted = False
    try:
        s = s.fillet(t, edges)                     # inside bend radius = t
        filleted = True
    except Exception as ex:                        # fall back to a sharp inside corner
        print("  fillet failed, sharp inside corner:", ex)
    for bx, bz in BOLTS:
        s = s.cut(cq.Solid.makeCylinder(HOLE_D / 2, t + 2, V(bx, YF + 1, bz), V(0, -1, 0)))
    if gusset:
        g = cq.Wire.makePolygon([V(XG - TG / 2, YF - t, -t), V(XG - TG / 2, YF - t - GLEG, -t), V(XG - TG / 2, YF - t, -t - GLEG)], close=True)
        s = s.fuse(cq.Solid.extrudeLinear(cq.Face.makeFromWires(g), V(TG, 0, 0))).clean()
    return s, filleted


def build_brep(opt, load, path):
    import cadquery as cq
    t, gus = OPTIONS[opt]
    br, filleted = bracket_solid(t, gus)
    solids = [br]
    if load == "A_cont":
        solids.append(br.mirror("XZ"))
    if load in ("A_half", "A_cont"):
        y1 = 0.0 if load == "A_half" else -YEND
        solids.append(cq.Solid.makeBox(G.TD, y1 - YEND, G.TT, cq.Vector(0, YEND, 0)))
        solids.append(cq.Solid.makeBox(PX[1] - PX[0], PY[1] - PY[0], G.TT, cq.Vector(PX[0], PY[0], 0)))   # splits off the patch
    cq.Compound.makeCompound(solids).exportBrep(path)
    return filleted


# ---------------------------------------------------------------- mesh
def mesh(opt, load, ref, work):
    import gmsh
    t, gus = OPTIONS[opt]
    brep = os.path.join(work, "geom.brep")
    # CadQuery's and gmsh's OpenCASCADE builds clash in one process: make the solids in a child process
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--brep", opt, load, brep], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("geometry failed: " + r.stdout + r.stderr)
    filleted = "FILLETED" in r.stdout
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", int(os.environ.get("GMSH_VERBOSE", "0")))
    gmsh.option.setNumber("General.NumThreads", os.cpu_count() or 4)
    gmsh.model.add("bracket")
    vols = gmsh.model.occ.importShapes(brep)
    vols = [d for d in vols if d[0] == 3]
    gmsh.model.occ.fragment(vols[:1], vols[1:])
    gmsh.model.occ.synchronize()
    steel, oak = [], []
    for _, v in gmsh.model.getEntities(3):
        (steel if gmsh.model.occ.getCenterOfMass(3, v)[2] < 0 else oak).append(v)
    h0, hs, ho = ref * t / 3, ref * t / 2, ref * 0.40       # bend and holes, rest of the plate, oak
    F = gmsh.model.mesh.field
    fl = []
    f = F.add("MathEval")                                     # inside bend corner, both sides
    F.setString(f, "F", f"{h0} + 0.45*Sqrt((Abs(y)-{-YF + t})^2 + (z+{t})^2)")
    fl.append(f)
    for bx, bz in BOLTS:
        f = F.add("MathEval")
        F.setString(f, "F", f"{h0} + 0.45*Abs(Sqrt((x{-bx:+.6f})^2 + (z{-bz:+.6f})^2) - {HOLE_D / 2})")
        fl.append(f)
    f = F.add("MathEval")                                     # web front edge corner at the seat underside
    F.setString(f, "F", f"{h0} + 0.45*Sqrt((x{-XW:+.6f})^2 + (z+{t})^2)")
    fl.append(f)
    if gus:
        f = F.add("MathEval")
        F.setString(f, "F", f"{h0} + 0.45*Sqrt((Abs(x{-XG:+.6f})-{TG / 2})^2 + ((Abs(y)-{-YF + t})*(z+{t}))^2)")
        fl.append(f)
    for vl, hv in ((steel, hs), (oak, ho)):
        if vl:
            f = F.add("Constant")
            F.setNumbers(f, "VolumesList", vl)
            F.setNumber(f, "VIn", hv)
            F.setNumber(f, "VOut", 1e3)
            fl.append(f)
    fm = F.add("Min")
    F.setNumbers(fm, "FieldsList", fl)
    F.setAsBackgroundMesh(fm)
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
    for grp, vl in (("STEEL", steel), ("OAK", oak)):
        cs = []
        for v in vl:
            et, _, en = gmsh.model.mesh.getElements(3, v)
            for ty, nn in zip(et, en):
                assert ty == 11, "expected 10 node tetrahedra"
                cs.append(nn.reshape(-1, 10).astype(int))
        els[grp] = np.vstack(cs) if cs else np.zeros((0, 10), int)
    steel_nodes = np.unique(els["STEEL"])
    holes, patch_tris, seat_tris, back_tris = {}, [], [], []
    for _, s in gmsh.model.getEntities(2):
        bb = gmsh.model.getBoundingBox(2, s)
        cx, cy, cz = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2
        typ = gmsh.model.getType(2, s)
        if typ == "Cylinder":
            for i, (bx, bz) in enumerate(BOLTS):
                if abs(cx - bx) < 0.3 and abs(cz - bz) < 0.3 and bb[3] - bb[0] < HOLE_D + 0.01:
                    side = "open" if cy < 0 else "wall"
                    nt, _, _ = gmsh.model.mesh.getNodes(2, s, includeBoundary=True)
                    holes.setdefault(f"{side}_hole{i + 1}", set()).update(nt.astype(int).tolist())
        if abs(bb[2] - bb[5]) < 1e-5:
            et, _, en = gmsh.model.mesh.getElements(2, s)
            tri = np.vstack([nn.reshape(-1, 6).astype(int) for ty, nn in zip(et, en) if ty == 9]) if len(et) else np.zeros((0, 6), int)
            if abs(cz - G.TT) < 1e-4 and PX[0] - 1e-4 <= bb[0] and bb[3] <= PX[1] + 1e-4 and PY[0] - 1e-4 <= bb[1] and bb[4] <= PY[1] + 1e-4:
                patch_tris.append(tri)
            if abs(cz) < 1e-4 and load == "B_seat":
                seat_tris.append(tri)
        if abs(bb[1] - bb[4]) < 1e-5 and abs(abs(cy) + YF) < 1e-4:          # web back faces, on the tube side faces
            et, _, en = gmsh.model.mesh.getElements(2, s)
            back_tris += [nn.reshape(-1, 6).astype(int) for ty, nn in zip(et, en) if ty == 9]
    gmsh.finalize()
    m = dict(X=X, els=els, steel_nodes=steel_nodes, holes={k: np.array(sorted(v)) for k, v in holes.items()},
             load_tris=np.vstack(patch_tris if load != "B_seat" else seat_tris), t=t, gusset=gus, filleted=filleted,
             load=load, sizes=dict(bend_and_holes=h0, plate=hs, oak=ho, refine=ref))
    assert len(m["holes"]) == (4 if load == "A_cont" else 2), m["holes"].keys()
    m["hole_nodes"] = np.concatenate(list(m["holes"].values()))
    c = ccx_elements(X, els["STEEL"])                       # contact candidates: web back face below the tube top line
    face = lambda p: (np.abs(np.abs(p[..., 1]) + YF) < 1e-6).all(axis=1)
    below = lambda p: p[:, :, 2].mean(axis=1) < ZL(p[:, :, 0].mean(axis=1))
    m["ccx_STEEL"] = c
    fl = plane_faces(X, c, lambda p: face(p) & below(p))
    m["cont_tris"] = np.array([c[i][list(FACES[k - 1]) + [EDGE6[k - 1][0], EDGE6[k - 1][1], EDGE6[k - 1][2]]] for i, k in fl])
    return m


FACES = [(0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)]   # CalculiX / Abaqus C3D10 faces S1..S4, corner nodes
EDGE6 = [(4, 5, 6), (7, 8, 4), (8, 9, 5), (9, 7, 6)]   # and their midside nodes


def plane_faces(X, c, test):
    """(element index, face number) of the faces of elements c (CalculiX order) whose three corners pass test(points)"""
    out = []
    for j, f in enumerate(FACES):
        p = X[c[:, list(f)]]
        ok = test(p)
        out += [(int(i), j + 1) for i in np.where(ok)[0]]
    return out


def tri6_loads(X, tris, total):
    """consistent nodal loads of a uniform pressure on flat 6 node triangles: corners 0, each midside node a third of the triangle"""
    a = 0.5 * np.linalg.norm(np.cross(X[tris[:, 1]] - X[tris[:, 0]], X[tris[:, 2]] - X[tris[:, 0]]), axis=1)
    f = {}
    q = total / a.sum()
    for tr, ai in zip(tris, a):
        for n in tr[3:]:
            f[int(n)] = f.get(int(n), 0.0) + q * ai / 3
    return f, float(a.sum())


# ---------------------------------------------------------------- CalculiX
PERM = [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]             # gmsh -> CalculiX C3D10 node order
FLIP = [0, 2, 1, 3, 6, 5, 4, 7, 9, 8]


def ccx_elements(X, conn):
    c = conn[:, PERM]
    v = np.einsum("ij,ij->i", np.cross(X[c[:, 1]] - X[c[:, 0]], X[c[:, 2]] - X[c[:, 0]]), X[c[:, 3]] - X[c[:, 0]])
    c[v < 0] = c[v < 0][:, FLIP]
    return c


def write_inp(path, m, loads, cont, fy=None, retained=None):
    X, els = m["X"], m["els"]
    grps = ("STEEL", "OAK")
    used = np.unique(np.concatenate([els[g].ravel() for g in grps]))
    L = ["*NODE"] + [f"{n},{X[n, 0]:.9g},{X[n, 1]:.9g},{X[n, 2]:.9g}" for n in used]
    eid = 1
    m["eid0"] = {}
    for grp in grps:
        c = m.setdefault("ccx_" + grp, ccx_elements(X, els[grp]))
        if not len(c):
            continue
        m["eid0"][grp] = eid
        L.append(f"*ELEMENT,TYPE=C3D10,ELSET=E{grp}")
        L += [f"{eid + i}," + ",".join(map(str, r)) for i, r in enumerate(c)]
        eid += len(c)

    def nset(name, nodes):
        L.append(f"*NSET,NSET={name}")
        nodes = list(map(int, nodes))
        L.extend(",".join(map(str, nodes[i:i + 12])) for i in range(0, len(nodes), 12))
    nset("NODES", used)
    if len(cont):
        nset("CONT", cont)
    for k, v in m["holes"].items():
        nset(k.upper(), v)
    L += ["*MATERIAL,NAME=STEEL", "*ELASTIC", f"{E_ST},{NU_ST}", "*SOLID SECTION,ELSET=ESTEEL,MATERIAL=STEEL"]
    if len(els["OAK"]):
        L += ["*MATERIAL,NAME=OAK", "*ELASTIC", f"{E_OAK},{NU_OAK}", "*SOLID SECTION,ELSET=EOAK,MATERIAL=OAK"]
    if retained is not None:                    # condensed stiffness of the y freedoms of the retained nodes, bolts held
        nset("RET", retained)
        L += ["*STEP", "*SUBSTRUCTURE GENERATE,SOLVER=SPOOLES", "*BOUNDARY"] + [f"{k.upper()},1,3" for k in m["holes"]]
        L += ["*RETAINED NODAL DOFS", "RET,2,2", "*SUBSTRUCTURE MATRIX OUTPUT,STIFFNESS=YES,OUTPUT FILE=USER DEFINED,FILE NAME=kred", "*END STEP"]
        open(path, "w").write("\n".join(L) + "\n")
        return
    L += ["*STEP", "*STATIC,SOLVER=SPOOLES", "*BOUNDARY"]
    L += [f"{k.upper()},1,3" for k in m["holes"]]
    if len(cont):
        L.append("CONT,2,2")
    L.append("*CLOAD")
    L += [f"{n},3,{-f:.9g}" for n, f in loads.items()]
    if fy is not None:
        L += [f"{n},2,{f:.9g}" for n, f in fy.items()]
    L += ["*NODE PRINT,NSET=NODES", "U"]
    for k in m["holes"]:
        L += [f"*NODE PRINT,NSET={k.upper()},TOTALS=ONLY", "RF"]
    if len(cont):
        L += ["*NODE PRINT,NSET=CONT", "RF"]
    L += ["*EL PRINT,ELSET=ESTEEL", "S", "*END STEP"]
    open(path, "w").write("\n".join(L) + "\n")


def parse_dat(path):
    blocks, cur, buf = {}, None, []

    def flush():
        if cur and buf:
            blocks[cur] = np.array(" ".join(buf).split(), float)
    for line in open(path):
        if " for set " in line:
            flush()
            kind = line.split("(")[0].strip()
            cur, buf = (kind, line.split(" for set ")[1].split()[0]), []
        elif cur and line.strip():
            buf.append(line)
    flush()
    return blocks


def run_ccx(ccx, work, m, loads, cont, fy=None, retained=None):
    write_inp(os.path.join(work, "job.inp"), m, loads, cont, fy, retained)
    nc = os.environ.get("FEA_THREADS") or str(os.cpu_count() or 4)
    d = os.path.dirname(os.path.abspath(ccx))                # conda layout: the solver's DLLs sit beside ccx.exe and in the env root
    extra = [d, os.path.dirname(d), os.path.dirname(os.path.dirname(d)), os.path.join(os.path.dirname(d), "mingw-w64", "bin")]
    env = dict(os.environ, OMP_NUM_THREADS=nc, CCX_NPROC_EQUATION_SOLVER=nc, PATH=os.pathsep.join(extra + [os.environ.get("PATH", "")]))
    r = subprocess.run([ccx, "-i", "job"], cwd=work, env=env, capture_output=True, text=True)
    if r.returncode != 0 or "*ERROR" in r.stdout:
        raise RuntimeError("ccx failed:\n" + r.stdout[-3000:] + r.stderr[-2000:])
    if retained is not None:
        return read_mtx(os.path.join(work, "kred.mtx"))
    b = parse_dat(os.path.join(work, "job.dat"))
    U = np.zeros_like(m["X"])
    u = b[("displacements", "NODES")].reshape(-1, 4)
    U[u[:, 0].astype(int)] = u[:, 1:]
    R = {k: b[("total force", k.upper())][-3:] for k in m["holes"]}
    rc = b[("forces", "CONT")].reshape(-1, 4) if len(cont) else np.zeros((0, 4))
    S = b[("stresses", "ESTEEL")].reshape(-1, 8)
    return U, R, rc, S


def read_mtx(path):
    """CalculiX substructure stiffness (*USER ELEMENT ... *MATRIX, lower triangle by rows) -> node list, dense matrix"""
    txt = open(path).read()
    head, mat = txt.split("*MATRIX,TYPE=STIFFNESS")
    nodes = []
    for ln in head.split("** ELEMENT NODES")[1].splitlines()[1:]:
        if not ln.startswith("**"):
            break
        nodes += [int(v) for v in ln[2:].replace(",", " ").split()]
    v = np.array(mat.replace(",", " ").split(), float)
    n = len(nodes)
    assert len(v) == n * (n + 1) // 2, (len(v), n)
    Kc = np.zeros((n, n))
    Kc[np.tril_indices(n)] = v
    return np.array(nodes), Kc + np.tril(Kc, -1).T


def lcp(D, g0):
    """lam >= 0, g = g0 + D lam >= 0, lam . g = 0, D symmetric positive definite: active set iteration"""
    A = g0 < 0
    lam = np.zeros(len(g0))
    for it in range(500):
        lam[:] = 0
        if A.any():
            lam[A] = np.linalg.solve(D[np.ix_(A, A)], -g0[A])
        g = g0 + D @ lam
        neg = A & (lam < 0)
        pen = ~A & (g < -1e-9)
        if not neg.any() and not pen.any():
            return lam, g, it
        A = (A & ~neg) | pen
    raise RuntimeError("contact LCP did not converge")


CGRID = 0.25                                       # contact point spacing, in


def solve(ccx, work, m, loads, contact):
    """Bolts fixed. With contact, the web's back face below the tube top may also bear on the tube face (rigid tube,
    frictionless, no tension), enforced at corner nodes of the face mesh, thinned to about one per CGRID square: CalculiX condenses the model onto those
    nodes' y freedoms (*SUBSTRUCTURE GENERATE), the contact problem is solved exactly on that small matrix, and the
    contact forces found are applied with the tread load in a final CalculiX run."""
    U, R, rc, S = run_ccx(ccx, work, m, loads, np.zeros(0, int))
    if not contact:
        return U, R, rc, S, dict()
    X = m["X"]
    # pre-select: hold the whole candidate face once (bilateral), keep the faces that bear in compression and a 0.6 in margin
    tris = m["cont_tris"]
    allc = np.setdiff1d(np.unique(tris), m["hole_nodes"])
    _, _, rb, _ = run_ccx(ccx, work, m, loads, allc)
    fyb = np.zeros(X.shape[0])
    fyb[rb[:, 0].astype(int)] = rb[:, 2]
    share = np.zeros(X.shape[0])
    np.add.at(share, tris.ravel(), 1)
    sgt = np.where(X[tris[:, 0], 1] < 0, -1.0, 1.0)
    ff = (fyb[tris] / np.maximum(share[tris], 1)).sum(axis=1) * sgt
    cc = X[tris[:, :3]].mean(axis=1)
    pc = cc[ff > 0]
    keep = np.zeros(len(tris), bool)
    for i in range(0, len(cc), 2000):
        d = np.linalg.norm(cc[i:i + 2000, None, ::2] - pc[None, :, ::2], axis=2).min(axis=1) if len(pc) else np.full(len(cc[i:i + 2000]), 9e9)
        keep[i:i + 2000] = d < 0.6
    cn = np.setdiff1d(np.unique(tris[keep][:, :3]), m["hole_nodes"])
    gi = np.floor(X[cn][:, [0, 2]] / CGRID).astype(int)                   # thin to one contact point per CGRID square
    _, first = np.unique(gi[:, 0] * 100003 + gi[:, 1] + (X[cn, 1] > 0) * 7, return_index=True)
    cn = cn[np.sort(first)]
    nodes, Kc = run_ccx(ccx, work, m, loads, np.zeros(0, int), retained=cn)
    sg = np.where(X[nodes, 1] < 0, -1.0, 1.0)     # from the tube into the bracket
    D = sg[:, None] * np.linalg.inv(Kc) * sg[None, :]
    g0 = sg * U[nodes, 1]                          # < 0 would be into the tube
    lam, g, its = lcp(D, g0)
    fy = {int(n): float(s_ * l_) for n, s_, l_ in zip(nodes, sg, lam) if l_ > 0}
    U, R, rc, S = run_ccx(ccx, work, m, loads, np.zeros(0, int), fy=fy)
    pen_any = float((np.where(X[allc, 1] < 0, -1, 1) * U[allc, 1]).min())
    on = nodes[lam > 0]
    info = dict(contact="web back face below the tube top bears on a rigid tube face: frictionless, no tension, enforced at face corner nodes thinned to one per 0.25 in square (penetration between them reported)",
                contact_candidate_nodes=len(nodes), contact_nodes_bearing=int((lam > 0).sum()), contact_force_lb=round(float(lam.sum()), 1),
                contact_active_set_iterations=its, max_penetration_any_face_node_in=round(min(pen_any, 0.0), 7),
                bearing_zone_bbox_x_z=[round(float(X[on, 0].min()), 2), round(float(X[on, 0].max()), 2),
                                       round(float(X[on, 2].min()), 2), round(float(X[on, 2].max()), 2)] if len(on) else None)
    return U, R, np.zeros((0, 4)), S, info


def load_node(m):
    lp = (XG, YF - G.SEAT_W, 0.0) if m["load"] == "B_seat" else LOAD_PT
    ln = np.unique(m["load_tris"])
    return ln[int(np.argmin(np.linalg.norm(m["X"][ln] - lp, axis=1)))]


# ---------------------------------------------------------------- post
QA, QB = 0.5854101966249685, 0.1381966011250105     # 4 point tetrahedron rule: point i lies near corner i


def nodal_stress(m, S):
    """extrapolate each element's 4 integration point stresses linearly to its corners, average over steel elements only"""
    c = m["ccx_STEEL"]
    ne = len(c)
    s = S[:, 2:].reshape(ne, 4, 6)
    F = s.sum(axis=1, keepdims=True)
    cor = (s - QB * F) / (QA - QB)                 # (ne, 4 corners, 6)
    edges = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]
    val = np.concatenate([cor, np.stack([(cor[:, a] + cor[:, b]) / 2 for a, b in edges], axis=1)], axis=1)
    nn = m["X"].shape[0]
    acc, cnt = np.zeros((nn, 6)), np.zeros(nn)
    np.add.at(acc, c.ravel(), val.reshape(-1, 6))
    np.add.at(cnt, c.ravel(), 1)
    ok = cnt > 0
    acc[ok] /= cnt[ok, None]
    vm = np.zeros(nn)
    vm[ok] = von_mises(acc[ok])
    ipvm = von_mises(S[:, 2:]).reshape(ne, 4)
    return vm, ok, ipvm


def von_mises(s):
    sx, sy, sz, sxy, sxz, syz = s.T
    return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3 * (sxy ** 2 + sxz ** 2 + syz ** 2))


def zones(m, P_):
    """masks over points P_ (n, 3) in the open side (or mirrored) bracket"""
    t = m["t"]
    x, ya, z = P_[:, 0], np.abs(P_[:, 1]), P_[:, 2]
    dh = np.min([np.hypot(x - bx, z - bz) for bx, bz in BOLTS], axis=0) - HOLE_D / 2
    near_hole = dh < 0.30
    near_front = np.hypot(x - XW, z + t) < 0.35       # sharp corner where the web's front edge meets the seat underside
    near_back = np.hypot(x - XS1, z + t) < 0.35       # and where the seat's back end meets the web, which runs on below it
    near_gus = (np.abs(x - XG) < TG / 2 + 0.35) & (z < 0.01) if m["gusset"] else np.zeros(len(x), bool)
    bend = (ya - (-YF) <= 2.5 * t) & (z >= -2.5 * t) & (x > XW + 0.5) & (x < XS1 - 0.3) & ~near_gus
    return dict(near_hole=near_hole, near_front=near_front, near_back=near_back, near_gus=near_gus, bend=bend,
                away=~near_hole & ~near_front & ~near_back & ~near_gus)


def where(p, m):
    x, y, z = p
    t, ya = m["t"], abs(y)
    side = "open side bracket" if y < 0 else "wall side bracket"
    dh = [math.hypot(x - bx, z - bz) - HOLE_D / 2 for bx, bz in BOLTS]
    if min(dh) < 0.3:
        i = int(np.argmin(dh))
        return f"{side}: edge of {'lower' if i == 0 else 'upper'} bolt hole (fixed bolt, singular)"
    if m["gusset"] and abs(x - XG) < TG / 2 + 0.35 and z < 0.01:
        return f"{side}: gusset to plate junction (sharp weld corner, singular)"
    if math.hypot(x - XW, z + t) < 0.35:
        return f"{side}: web front edge where it meets the seat underside (sharp re-entrant corner)"
    if math.hypot(x - XS1, z + t) < 0.35:
        return f"{side}: seat back end where it meets the web (sharp re-entrant corner, end of the bend)"
    if ya + YF <= 2.5 * t and z >= -2.5 * t:
        face = "inside (fillet) face" if ya + YF > 0.5 * t and z < -0.5 * t else ("top / back outer corner" if ya + YF < 0.5 * t and z > -0.5 * t else "bend")
        return f"{side}: bend, {face}, x = {x:.2f} in"
    if z > -t - 1e-6:
        return f"{side}: seat, {('top' if z > -t / 2 else 'underside')}, x = {x:.2f}, {ya + YF:.2f} in out from the tube face"
    return f"{side}: web, x = {x:.2f}, z = {z:.2f}"


def contour_png(path, m, vm, title, peak_p):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    c = m["ccx_STEEL"][:, :4]
    faces = np.vstack([c[:, [0, 1, 2]], c[:, [0, 1, 3]], c[:, [1, 2, 3]], c[:, [0, 2, 3]]])
    key = np.sort(faces, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    bf = faces[cnt[inv.ravel()] == 1]
    X = m["X"]
    if (X[bf, 1] > 0).any():                       # two brackets: plot the loaded (open side) one
        bf = bf[(X[bf, 1] < 0).all(axis=1)]
    val = vm[bf].mean(axis=1)
    cmap = plt.get_cmap("turbo")
    vmax = 36000.0
    fig = plt.figure(figsize=(13, 6.2))
    for i, (el, az, lab) in enumerate(((8, -90, "from the open side (outside face of the web)"), (-35, -125, "from below, front"))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        pc = Poly3DCollection(X[bf], facecolors=cmap(np.clip(val / vmax, 0, 1)), edgecolors="none")
        ax.add_collection3d(pc)
        lo, hi = X[bf].reshape(-1, 3).min(axis=0), X[bf].reshape(-1, 3).max(axis=0)
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(hi - lo)
        ax.view_init(elev=el, azim=az)
        ax.plot([peak_p[0]], [peak_p[1]], [peak_p[2]], "k*", ms=14, mec="w")
        ax.set_xlabel("x along flight (in)"); ax.set_ylabel("y across (in)"); ax.set_zlabel("z (in)")
        ax.set_title(lab, fontsize=9)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax))
    cb = fig.colorbar(sm, ax=fig.axes, shrink=0.7, label="von Mises (psi), capped at 36,000 (Fy); 0.6 Fy = 21,600")
    cb.ax.axhline(ALLOW, color="k", lw=2)
    fig.suptitle(title, fontsize=10)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def analyse(ccx, opt, load, ref, out, work, contours=True, supports=SUPPORTS, tag=""):
    t0 = time.time()
    os.makedirs(work, exist_ok=True)
    m = mesh(opt, load, ref, work)
    ns, ne = len(m["steel_nodes"]), len(m["els"]["STEEL"])
    nall = len(np.unique(np.concatenate([m["els"]["STEEL"].ravel(), m["els"]["OAK"].ravel()])))
    loads, area = tri6_loads(m["X"], m["load_tris"], P)
    print(f"  mesh {opt} {load} ref {ref}: {ne} steel + {len(m['els']['OAK'])} oak tets, {nall} nodes, load area {area:.3f} in2 ({time.time() - t0:.0f} s)")
    res = []
    for sup in supports:
        t1 = time.time()
        U, R, rc, S, info = solve(ccx, work, m, loads, sup != "bolts")
        vm, ok, ipvm = nodal_stress(m, S)
        X = m["X"]
        sn = np.where(ok)[0]
        loaded = sn[X[sn, 1] < 0]                  # the loaded (open side) bracket
        Z = zones(m, X[loaded])
        v = vm[loaded]

        def pk(mask):
            if not mask.any():
                return None
            i = loaded[mask][np.argmax(v[mask])]
            return dict(von_mises_psi=round(float(vm[i]), 0), at_xyz_in=[round(float(a), 3) for a in X[i]], where=where(X[i], m))
        ipeak = int(np.argmax(v))
        peak_p = X[loaded[ipeak]]
        # integration point peaks (not extrapolated), same zones, by element centroid
        cen = X[m["ccx_STEEL"][:, :4]].mean(axis=1)
        eo = cen[:, 1] < 0
        Ze = zones(m, cen[eo])
        ipm = ipvm.max(axis=1)[eo]
        if load == "B_seat":
            lp = (XG, YF - G.SEAT_W, 0.0)
        else:
            lp = LOAD_PT
        il = int(np.argmin(np.linalg.norm(X[np.unique(m["load_tris"])] - lp, axis=1)))
        nl = np.unique(m["load_tris"])[il]
        d = dict(variant=f"{opt}_{load}_{sup.replace('+', '_')}{tag}", option=opt, plate_t_in=m["t"], gusset=m["gusset"], load_case=load,
                 support=sup, refine=ref, inside_bend_radius_in=m["t"] if m["filleted"] else 0.0,
                 mesh=dict(steel_tets=ne, oak_tets=len(m["els"]["OAK"]), nodes=nall, element="C3D10 (10 node tetrahedron)", **m["sizes"],
                           approx_elements_through_t_at_bend=round(m["t"] / m["sizes"]["bend_and_holes"], 1)),
                 load_lb=P, load_area_in2=round(area, 3),
                 peak_von_mises=pk(np.ones(len(v), bool)),
                 peak_away_from_singularities=pk(Z["away"]),
                 bend_peak_away_from_holes=pk(Z["bend"]),
                 hole_zone_peak=pk(Z["near_hole"]),
                 front_corner_zone_peak=pk(Z["near_front"]),
                 back_corner_zone_peak=pk(Z["near_back"]),
                 gusset_zone_peak=pk(Z["near_gus"]) if m["gusset"] else None,
                 integration_point_peaks_psi=dict(all=round(float(ipm.max()), 0), away=round(float(ipm[Ze["away"]].max()), 0),
                                                  bend=round(float(ipm[Ze["bend"]].max()), 0) if Ze["bend"].any() else None),
                 deflection_in=dict(at=[round(float(a), 3) for a in X[nl]], point="load patch centre, tread top" if load != "B_seat" else "seat outer edge, mid length",
                                    uz=round(float(U[nl, 2]), 5), max_abs_uz_steel=round(float(np.abs(U[m["steel_nodes"], 2]).max()), 5)),
                 bolt_reactions_lb={k: dict(Fx=round(float(r[0]), 1), Fy_normal_to_tube_face=round(float(r[1]), 1), Fz=round(float(r[2]), 1),
                                            shear_in_plane=round(float(math.hypot(r[0], r[2])), 1)) for k, r in sorted(R.items())},
                 sum_reactions_z_lb=round(float(sum(r[2] for r in R.values()) + 0), 2),
                 under_0p6Fy_away_from_singularities=None, solve_s=round(time.time() - t1, 1), **info)
        d["under_0p6Fy_away_from_singularities"] = bool(d["peak_away_from_singularities"]["von_mises_psi"] <= ALLOW)
        res.append(d)
        if out:
            json.dump(d, open(os.path.join(out, d["variant"] + ".json"), "w"), indent=1)
            if contours:
                contour_png(os.path.join(out, d["variant"] + ".png"), m, vm,
                            f"{d['variant']}: t = {m['t']} in{' + gusset' if m['gusset'] else ''}, {load}, {sup}. Peak {d['peak_von_mises']['von_mises_psi']:,.0f} psi (star), "
                            f"away from singularities {d['peak_away_from_singularities']['von_mises_psi']:,.0f}, bend {d['bend_peak_away_from_holes']['von_mises_psi']:,.0f}", peak_p)
        print(f"    {sup}: peak {d['peak_von_mises']['von_mises_psi']:.0f} ({d['peak_von_mises']['where']}); away {d['peak_away_from_singularities']['von_mises_psi']:.0f} "
              f"({d['peak_away_from_singularities']['where']}); bend {d['bend_peak_away_from_holes']['von_mises_psi']:.0f}; uz {d['deflection_in']['uz']:.4f} ({time.time() - t1:.0f} s)")
    return res


def collect(out, refine):
    rs = {}
    for f in sorted(os.listdir(out)):
        if f.endswith(".json") and f != "summary.json":
            r = json.load(open(os.path.join(out, f)))
            rs[r["variant"]] = r
    conv = []
    for v, r in rs.items():
        if v.endswith("_fine"):
            r1 = rs.get(v[:-5])
            if r1:
                conv.append(dict(variant=r1["variant"], refine=r["refine"], steel_tets=[r1["mesh"]["steel_tets"], r["mesh"]["steel_tets"]],
                                 bend_size_in=[round(r1["mesh"]["bend_and_holes"], 4), round(r["mesh"]["bend_and_holes"], 4)],
                                 **{k: [r1[k]["von_mises_psi"], r[k]["von_mises_psi"]] for k in ("peak_von_mises", "peak_away_from_singularities", "bend_peak_away_from_holes", "hole_zone_peak")},
                                 uz=[r1["deflection_in"]["uz"], r["deflection_in"]["uz"]]))
    summary = dict(note="PRELIMINARY, for an engineer's review. Linear elastic, small displacement. See bracket_solid_fea.py docstring.",
                   inputs=dict(E_steel=E_ST, nu_steel=NU_ST, Fy=FY, allowable_0p6Fy=ALLOW, E_oak=E_OAK, nu_oak=NU_OAK, load_lb=P,
                               hole_d=HOLE_D, bolt_spacing=BOLT_SP, bolt_n=G.BOLT_N, seat_w=G.SEAT_W, web0=G.WEB0, lap=G.LAP,
                               tread_depth=G.TD, tread_t=G.TT, riser_lip=G.RT, slope_deg=round(math.degrees(G.ANG), 3),
                               tread_overhang_past_seat_in=round(-YEND + YF - G.SEAT_W, 3), load_patch_x=PX, load_patch_y=PY,
                               bolts_xz=BOLTS, flight=FLIGHT.name, tread=K, bolt_u_from_tread_front=round(BU, 4)),
                   results=[{k: r.get(k) for k in ("variant", "peak_von_mises", "peak_away_from_singularities", "bend_peak_away_from_holes",
                                                    "hole_zone_peak", "front_corner_zone_peak", "back_corner_zone_peak", "gusset_zone_peak", "deflection_in", "bolt_reactions_lb",
                                                    "contact_force_lb", "under_0p6Fy_away_from_singularities")} for v, r in rs.items() if not v.endswith("_fine")],
                   convergence=conv)
    json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=1)
    return summary


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--brep":
        print("FILLETED" if build_brep(*sys.argv[2:]) else "SHARP")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "..", "ladder-fea-results"))
    ap.add_argument("--only", nargs="*", help="option:load pairs, e.g. t25:A_half (runs just these, no convergence or summary)")
    ap.add_argument("--fine", nargs="*", help="convergence runs only: options to rerun (A_half, bolts) with the --refine mesh size factor")
    ap.add_argument("--collect", action="store_true", help="only write summary.json from the result files in --out")
    ap.add_argument("--refine", type=float, default=0.7, help="mesh size factor for the convergence runs")
    ap.add_argument("--ccx", default=os.environ.get("CCX") or shutil.which("ccx") or "ccx")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    work = os.path.join(out, "_work")
    print(f"bracket: {FLIGHT.name} flight tread {K}; tread end overhang past the seat edge {-(YEND) - (-YF) - G.SEAT_W:.3f} in; "
          f"bolts at x, z = {[(round(x, 3), round(z, 3)) for x, z in BOLTS]}; slope {math.degrees(G.ANG):.2f} deg")
    if a.collect:
        print(json.dumps(collect(out, a.refine)["convergence"], indent=1))
        return
    everything = not a.only and a.fine is None
    jobs = [tuple(s.split(":")) for s in a.only] if a.only else ([(o, l) for o in OPTIONS for l in LOADS] if everything else [])
    for o, l in jobs:
        analyse(a.ccx, o, l, 1.0, out, f"{work}_{o}_{l}")
    for o in (a.fine if a.fine is not None else (("t25", "t25g") if everything else ())):
        analyse(a.ccx, o, "A_half", a.refine, out, f"{work}_{o}_fine", contours=False, supports=("bolts",), tag="_fine")
    if everything:
        print(json.dumps(collect(out, a.refine)["convergence"], indent=1))


if __name__ == "__main__":
    main()
