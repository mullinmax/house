"""Laser cut kit for the mono (centre stringer) ships ladder: one flat DXF per plate part for SendCutSend, a preview sheet and a parts list.

Run: python3 tools/ladder_drawings/export_mono_kit.py OUTDIR        (pip install ezdxf shapely matplotlib)

Every part is drawn FLAT in inches. Bent parts carry their bend lines as dashed lines on a layer named BEND (SendCutSend reads a
line at the centre of each bend; the 3D preview at checkout confirms the angle and direction). Flat lengths use a 90 degree bend
deduction for 1/4 in mild steel of BD = 0.39 in (SendCutSend's effective radius 0.150 in, K about 0.45): flat leg = outside leg - BD/2
on each side of a bend. Holes on short flanges near a bend are slotted where they must line up with another part.

Hole sizes: 7/16 in for 3/8 in bolts, 1/2 in for 3/8 in slab anchors, 13/32 in countersunk for 3/8 flat heads in the base plates.
No tapped threads, rivets or rivet nuts (round 5): every bolt into a tube is a through bolt with a steel crush sleeve.
Screw holes into the oak (tread tabs) are NOT cut: drill them at assembly through the tab into the tread (9/32 in, then the insert).
PRELIMINARY: dimensions follow ladder_geom.py (round 6: rounded brackets, shared head clips, saddle with cheeks and tabs; straight rails); for an engineer's review before ordering.
"""
import json, math, os, sys
import ezdxf
from shapely.geometry import Polygon, Point, box as sbox
from shapely.affinity import scale as sscale, translate
from shapely.ops import unary_union
import ladder_geom as G

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)
assert G.MONO, "kit is for the mono stringer"
T = G.BRKT_T
BD = 0.39                     # 90 degree bend deduction, 1/4 in mild steel
H38, HANC, CSK38 = 0.4375, 0.5, 0.40625
CA, SA = math.cos(G.ANG), math.sin(G.ANG)
nx, nz = SA, -CA              # unit normal pointing down and back from the tube top line, in a flight's (u, z)


def rect(x0, x1, y0, y1):
    return sbox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def slot(cx, cy, w, ln, vertical=True):
    """obround: w wide, ln long overall"""
    a = ln - w
    p = Point(cx, cy).buffer(w / 2, 64)
    q = Point(cx, cy + a if vertical else cy).buffer(w / 2, 64) if vertical else Point(cx + a, cy).buffer(w / 2, 64)
    s = unary_union([p, q]).convex_hull
    return translate(s, 0, -a / 2) if vertical else translate(s, -a / 2, 0)


PARTS = []                    # dict(file, name, qty, thick, material, bends, notes, shape, bends_xy, holes)


def part(file, name, qty, thick, outline, holes=(), bends=(), bend_text="none", notes="", mirror=False):
    shp = outline
    for h in holes:
        shp = shp.difference(h)
    if mirror:
        shp = sscale(shp, -1, 1, origin=(0, 0))
        bends = [((-x0, y0), (-x1, y1)) for (x0, y0), (x1, y1) in bends]
    minx, miny = shp.bounds[0], shp.bounds[1]
    shp = translate(shp, -minx, -miny)
    bends = [((x0 - minx, y0 - miny), (x1 - minx, y1 - miny)) for (x0, y0), (x1, y1) in bends]
    PARTS.append(dict(file=file, name=name, qty=qty, thick=thick, material="Mild steel A36 (hot rolled P&O)", bends=bend_text, notes=notes,
                      shape=shp, bend_lines=bends, size=[round(shp.bounds[2], 2), round(shp.bounds[3], 2)]))


# ---------------------------------------------------------------- tread brackets (one each side of the stringer under every tread)
def bracket(foot):
    """flat bracket for the OPEN (west / north) side, seen from its outside face: x = u along the flight, y = z, origin at the tread's
    underside over the web's front edge. Web on the stringer side, a bolting flange folded off its front edge (to the strip), a seat tab
    folded off its top edge (under the tread), and for the lower flight's first tread a foot flange folded off its bottom (slab)."""
    A, B = (G.WEB0, 0.0), (G.TD + G.RT, 0.0)
    C = (G.WEB0, (G.WEB0 - (G.TD + G.RT)) * G.SL)
    f_, k_ = (G.LOWER, 1) if foot else (G.UPPER, 2)            # round 6: corners rounded (the same outline on every tread)
    uk_, zk_ = f_.uk(k_), f_.z0 + k_ * G.RI - G.TT
    web = Polygon([(u - uk_, z - zk_) for u, z in G.bracket_web(f_, k_)])
    zf = -(G.RI - G.TT)                                         # slab, from the first tread's underside
    if foot:
        web = web.intersection(rect(-5, 20, zf, 1))
    fl_out = T + G.ARM_FL                                       # flange: outside dimension from the stringer face
    flange = rect(G.WEB0 - (fl_out - BD / 2), G.WEB0, -G.ARM_D, 0)
    seat = rect(G.SEAT_S, B[0], 0, G.SEAT_TAB - BD / 2)
    shp = unary_union([web, flange, seat])
    cuts = [rect(G.WEB0, G.WEB0 + 0.40, -G.ARM_D - 0.25, -G.ARM_D),      # bend reliefs at the bend ends
            rect(G.SEAT_S - 0.25, G.SEAT_S, -0.40, 0), rect(B[0], B[0] + 0.25, -0.40, 0)]
    bends = [((G.WEB0, -G.ARM_D), (G.WEB0, 0)), ((G.SEAT_S, 0), (B[0], 0))]
    holes = []
    for s_ in (4.25, 8.25):                                     # two through bolts into the stringer
        ub, zb = G.WEB0 + s_ * CA + nx * G.BOLT_N, C[1] + s_ * SA + nz * G.BOLT_N
        if not foot or zb > zf + T + 0.5:
            holes.append(Point(ub, zb).buffer(H38 / 2, 64))
    d_ = T + 0.95                                               # flange bolt, slotted along the flange to take up bend tolerance
    holes.append(slot(G.WEB0 - (d_ - BD / 2), -G.FLANGE_BOLT, H38, 0.70, vertical=False))
    if foot:
        xs = [x for x, y in web.exterior.coords if abs(y - zf) < 1e-6]
        x0, x1 = min(xs), max(xs)
        ft = rect(x0, x1, zf - (G.FOOT_W - BD / 2), zf)
        shp = unary_union([shp, ft])
        cuts.append(rect(G.WEB0, G.WEB0 + 0.0, zf, zf))
        bends.append(((x0, zf), (x1, zf)))
        for xa in (x0 + 0.8, x1 - 0.8):
            holes.append(Point(xa, zf - (2.35 - BD / 2)).buffer(HANC / 2, 64))
    for c in cuts:
        shp = shp.difference(c)
    return shp, holes, bends


for foot in (False, True):
    shp, holes, bends = bracket(foot)
    n = 1 if foot else (G.N_LO - 2) + (G.N_UP - 1)
    nm = "bracket_foot" if foot else "bracket"
    bt = ("3 bends, all 90 deg toward the outside face: flange off the front edge, seat tab off the top edge, foot off the bottom edge" if foot
          else "2 bends, both 90 deg toward the outside face: flange off the front edge, seat tab off the top edge")
    where = "lower flight first tread" if foot else f"every other tread ({G.N_LO - 2} lower + {G.N_UP - 1} upper)"
    part(f"{nm}_open_qty{n}.dxf", f"Tread bracket{' with slab foot' if foot else ''}, open side", n, 0.25, shp, holes, bends, bt,
         f"{where}; west side of the upper flight, north side of the lower flight. 2 x 7/16 bolt holes into the stringer, flange bolt slotted. Drill the seat tab screw holes at assembly.")
    part(f"{nm}_wall_qty{n}.dxf", f"Tread bracket{' with slab foot' if foot else ''}, wall side (mirror)", n, 0.25, shp, holes, bends, bt,
         f"mirror image of the open side part. {where}.", mirror=True)

# ---------------------------------------------------------------- tread strips (2 in strip on edge under each tread, across both brackets)
L_ = G.WN - 2 * G.ARM_END
TAB_OUT = 1.60                     # outside, from the strip's front face (CAD 1.50; lengthened so the flat tab clears SendCutSend's 1.15 in minimum)
shp = rect(0, L_, -G.ARM_D, 0)
bends, cuts = [], []
for vt in (G.STRIP_TAB, L_ - G.STRIP_TAB):
    shp = unary_union([shp, rect(vt - 0.9, vt + 0.9, 0, TAB_OUT - BD / 2)])
    cuts += [rect(vt - 0.9 - 0.25, vt - 0.9, -0.40, 0), rect(vt + 0.9, vt + 1.15, -0.40, 0)]
    bends.append(((vt - 0.9, 0), (vt + 0.9, 0)))
for c in cuts:
    shp = shp.difference(c)
holes = [Point(v - G.ARM_END, -G.FLANGE_BOLT).buffer(H38 / 2, 64) for v in (G.VC - G.TW / 2 - T - 0.95, G.VC + G.TW / 2 + T + 0.95)]
nstrip = (G.N_LO - 1) + (G.N_UP - 1)
part(f"tread_strip_qty{nstrip}.dxf", "Tread strip (2 in on edge, closes the riser)", nstrip, 0.25, shp, holes, bends,
     "2 bends, 90 deg: a screw tab at each end folds toward the back of the tread",
     "one under every tread. 2 x 7/16 holes for the bracket flange bolts. Drill the tab screw holes at assembly. Tabs 1.6 in outside (CAD shows 1.5).")

# ---------------------------------------------------------------- stringer head clips (round 6: the same part at both stringer tops)
def clip_flat(f):
    hc = G.head_clip(f)
    ub, (zb0, zt0) = hc["ub"], hc["beam"]
    X = lambda u: (ub - u) - BD / 2                              # tube leg, measured away from the bend at the beam's face
    leg = Polygon([(X(u) if u < ub - T else 0.0, z - zt0) for u, z in hc["leg"]])
    shp = unary_union([leg, rect(-(2.25 - BD / 2), 0, zb0 - zt0, 0)])
    holes = [slot(X(hc["tube_bolt"][0]), hc["tube_bolt"][1] - zt0, H38, 1.0, vertical=True), Point(-(1.3 - BD / 2), hc["beam_bolt_z"] - zt0).buffer(H38 / 2, 64)]
    return shp, holes, [((0, zb0 - zt0), (0, 0))]
shp, holes, bl = clip_flat(G.UPPER)
s2, h2, _ = clip_flat(G.LOWER)
assert s2.symmetric_difference(shp).area < 1e-3, "head clips differ between flights"
for side, mir in (("west", False), ("east", True)):
    part(f"head_clip_{side}_qty2.dxf", f"Stringer top clip, {side} side (both flights)", 2, 0.25, shp, holes, bl,
         "1 bend, 90 deg (west and east are mirror images)",
         "one pair at each stringer top (upper on the balcony head beam, lower on the landing header). Tube leg hole is a 1 in VERTICAL SLOT: "
         "one through bolt across the stringer (crush sleeve inside). Other leg bolts through the beam.", mirror=mir)
# saddle (round 6): level seat under the stringer's level foot cut; legs DOWN the post's south and north faces (one bolt through the post);
# cheeks UP both sides of the stringer (one bolt through the stringer); a tab off each cheek's south edge onto the landing's north beam.
# Flat: x across the flight (west +), y along the flight (north +), origin at the seat's centre.
u0, u1 = G.SAD_U0, G.SAD_U1
seat_u, seat_v = u1 - u0, G.TW + 2 * T                          # outside
um, zpt = (u0 + u1) / 2, G.Z_SEAT - T
leg_out = T + G.SAD_LEG                                          # seat top to leg bottom, outside
ys = seat_u / 2 - BD / 2                                         # leg bend lines at y = +-ys
xs = seat_v / 2 - BD / 2                                         # cheek bend lines at x = +-xs
yb = (u0 - um) + BD / 2                                          # tab bend line on each cheek's south edge
cx = lambda z: xs + max((z - zpt) - BD / 2, 0.0)                 # cheek: flat x of a point at height z (outside from the seat's underside)
cy = lambda u: max(u - um, yb)
cheek = Polygon([(cx(z), cy(u)) for u, z in G.CHEEK])
tab = rect(cx(G.TAB_Z[0]), cx(G.TAB_Z[1]), yb, yb - ((G.TAB_W + T) - BD / 2))
half = unary_union([cheek, tab])
shp = unary_union([rect(-xs, xs, -ys, ys), rect(-1.5, 1.5, -ys - (leg_out - BD / 2), ys + (leg_out - BD / 2)),
                   half, sscale(half, -1, 1, origin=(0, 0))])
for sy in (-1, 1):                                               # bend reliefs where the seat meets the 3 in legs
    for sx in (-1, 1):
        shp = shp.difference(rect(sx * 1.5, sx * 1.75, sy * (ys - 0.001), sy * (ys + 0.40)))
yh = ys + (T + 2.0) - BD / 2                                     # leg bolt, 2 in below the post top
holes = [Point(0, sy * yh).buffer(H38 / 2, 64) for sy in (-1, 1)]
holes += [Point(sx * cx(G.SAD_BOLT[1]), cy(G.SAD_BOLT[0])).buffer(H38 / 2, 64) for sx in (-1, 1)]
holes += [Point(sx * (cx(G.TAB_Z[0]) + cx(G.TAB_Z[1])) / 2, yb - ((1.05 + T) - BD / 2)).buffer(H38 / 2, 64) for sx in (-1, 1)]
bends = [((-1.5, -ys), (1.5, -ys)), ((-1.5, ys), (1.5, ys))]
bends += [((sx * xs, cy(G.CHEEK[0][0])), (sx * xs, cy(G.CHEEK[-1][0]))) for sx in (-1, 1)]
bends += [((sx * cx(G.TAB_Z[0]), yb), (sx * cx(G.TAB_Z[1]), yb)) for sx in (-1, 1)]
SAD_INFO = dict(seat=(seat_v, seat_u), cheek_h=G.Z_SEAT + 2.0 - zpt, tab=(G.TAB_W + T, G.TAB_Z[1] - G.TAB_Z[0]))
part("upper_post_saddle_qty1.dxf", "Upper stringer post saddle (seat, legs down the post, cheeks up the stringer, tabs to the landing beam)", 1, 0.25, shp, holes,
     bends, "6 bends, all 90 deg: the 2 legs DOWN (a U over the post top), the 2 cheeks UP (a U round the stringer), and a tab off each cheek's "
     "south edge bent OUT, away from the stringer (bend the tabs before the cheeks)",
     f"seat {seat_v:.2f} x {seat_u:.2f} in outside; legs 3 in wide, {leg_out:.2f} in outside, one 3/8 through bolt across the post; cheeks "
     f"{SAD_INFO['cheek_h']:.2f} in tall outside, one 3/8 through bolt across the stringer (crush sleeve inside); tabs {SAD_INFO['tab'][0]:.2f} in out x "
     f"{SAD_INFO['tab'][1]:.2f} in tall, one 3/8 bolt each through the landing's north beam. Replaces round 5's foot clips.")

# ---------------------------------------------------------------- base plates, 3/8 in
def base_plate(w, post, through, file, name, qty, notes):
    shp = rect(-w / 2, w / 2, -w / 2, w / 2)
    if through:
        shp = shp.difference(rect(-post / 2 - 0.03, post / 2 + 0.03, -post / 2 - 0.03, post / 2 + 0.03))
    off = post / 2 + 1.2 if post > 2 else 2.3
    holes = [Point(sx * off, sy * off).buffer(HANC / 2, 64) for sx in (-1, 1) for sy in (-1, 1)]
    holes += [Point(sx * (post / 2 + 1.1), 0).buffer(CSK38 / 2, 64) for sx in (-1, 1)]
    part(file, name, qty, 0.375, shp, holes, (), "none", notes + " COUNTERSINK the two 13/32 in holes from the BOTTOM face (82 deg, 3/8 flat head): flat head screws up through the plate into the post clips, nuts on top (no tapped threads). Four 1/2 in holes for 3/8 in slab anchors.")


base_plate(6.0, 2.0, True, "foot_post_base_plate_qty1.dxf", "Foot post base plate, 6 x 6 (post passes through)", 1, "lower flight foot post; the 2 x 2 post stands through the square hole on the slab.")
base_plate(6.0, 2.0, False, "corner_newel_base_plate_qty1.dxf", "Corner newel base plate, 6 x 6", 1, "corner newel stands on it.")
base_plate(7.0, 3.0, False, "upper_post_base_plate_qty1.dxf", "Upper stringer post base plate, 7 x 7", 1, "3 x 3 post under the upper stringer's foot.")

# ---------------------------------------------------------------- balcony post L plates, 3/8 in
x0 = G.XL - 8
shp = unary_union([rect(0, 10, 0, G.TK - G.TT), rect(8, 10, G.TK - G.TT - 0.01, G.TK + 3.5)])
holes = [Point(G.XL - 7 - x0, 1.5).buffer(H38 / 2, 64), Point(G.XL - 2.5 - x0, 1.5).buffer(H38 / 2, 64),
         Point(9, 1.2).buffer(H38 / 2, 64), Point(9, G.TK + 2.6).buffer(H38 / 2, 64)]
part("balcony_post_L_plate_qty2.dxf", "Balcony post L plate (south west newel and north west post)", 2, 0.375, shp, holes, (), "none",
     "flat; the long leg bolts to the end beam of the balcony frame, the short leg up the post. Same part both posts (flip one).")

# ---------------------------------------------------------------- placeholder clips for joints the CAD does not detail yet
def clip(w, leg, file, name, qty, notes):
    shp = rect(0, w, -(leg - BD / 2), leg - BD / 2)
    holes = [Point(w / 2, s * (leg * 0.63 - BD / 2)).buffer(H38 / 2 if w > 1.5 else 0.28 / 2, 64) for s in (-1, 1)]
    part(file, name, qty, 0.25, shp, holes, [((0, 0), (w, 0))], "1 bend, 90 deg", "PLACEHOLDER for an engineer: " + notes)


clip(2.0, 1.75, "clip_angle_2in_qty30.dxf", "Clip angle 2 in wide, 1 3/4 legs", 30,
     "16 at the landing and balcony frame corners, 6 at the three post bases (2 each, flat heads up through the base plates), 8 at the two knee braces' ends (the south brace's wall end needs a bracket rated about 750 lb: engineer).")
clip(1.25, 1.5, "rail_clip_1-25in_qty10.dxf", "Rail end clip 1 1/4 in wide, 1 1/2 legs", 10,
     "straight rail ends into post faces, the north guard rail into the west one, the north guard rail at the bath 1 wall, and the four guard bottom rail ends. 9/32 in holes for 1/4-20.")

shp = rect(0, 1.25, 0, 4.5)
holes = [Point(0.625, y).buffer(0.28 / 2, 64) for y in (1.0, 3.5)]
part("rail_post_strap_qty3.dxf", "Rail to post strap 1 1/4 x 4 1/2", 3, 0.25, shp, holes, (), "none",
     "PLACEHOLDER for an engineer: flat strap on the side where a rail runs over a post top (lower rail on the foot post, guard top rails on the north west and north east posts); 1/4 in spacer behind it on the rail, which sits 1/4 in in from the post face.")

# ---------------------------------------------------------------- write
for p in PARTS:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 1
    doc.header["$MEASUREMENT"] = 0
    doc.layers.add("BEND", color=1, linetype="DASHED")
    msp = doc.modelspace()
    shp = p["shape"]
    geoms = getattr(shp, "geoms", [shp])
    for g in geoms:
        for ring in [g.exterior, *g.interiors]:
            pts = list(ring.coords)
            # holes that are circles go out as true circles
            poly = Polygon(pts)
            c = poly.centroid
            r = [math.hypot(x - c.x, y - c.y) for x, y in pts]
            if len(pts) > 40 and max(r) - min(r) < 1e-3:
                msp.add_circle((c.x, c.y), sum(r) / len(r))
            else:
                msp.add_lwpolyline(pts[:-1], close=True)
    for (x0, y0), (x1, y1) in p["bend_lines"]:
        msp.add_line((x0, y0), (x1, y1), dxfattribs=dict(layer="BEND", linetype="DASHED"))
    doc.saveas(os.path.join(OUT, p["file"]))

rows = [{k: v for k, v in p.items() if k not in ("shape", "bend_lines")} for p in PARTS]
json.dump(dict(bend_deduction_in=BD, parts=rows), open(os.path.join(OUT, "kit_parts.json"), "w"), indent=1)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
n = len(PARTS)
cols = 4
rows_ = math.ceil(n / cols)
fig, axs = plt.subplots(rows_, cols, figsize=(cols * 4, rows_ * 4))
for ax, p in zip(axs.flat, PARTS):
    for g in getattr(p["shape"], "geoms", [p["shape"]]):
        for ring in [g.exterior, *g.interiors]:
            xs, ys = ring.xy
            ax.plot(xs, ys, "k-", lw=0.8)
    for (x0, y0), (x1, y1) in p["bend_lines"]:
        ax.plot([x0, x1], [y0, y1], "r--", lw=0.8)
    ax.set_aspect("equal")
    ax.set_title(f"{p['file']}\n{p['thick']} in, {p['size'][0]} x {p['size'][1]} in", fontsize=8)
    ax.tick_params(labelsize=6)
for ax in list(axs.flat)[n:]:
    ax.axis("off")
fig.suptitle("Loft ships ladder: SendCutSend flat parts (inches; red dashed = bend line). PRELIMINARY", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "kit_preview.png"), dpi=110)
for p in rows:
    print(f"{p['qty']:3d}  {p['thick']:.3f}  {p['size']}  {p['file']}")
