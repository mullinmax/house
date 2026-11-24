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
BD_WEB = 0.39 if G.WEB_T >= 0.25 else 0.30   # 3/16 in brackets (cost pass 11/24/2026): about 0.30 in, confirm in the SendCutSend preview
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


def round_outline(shp, r, bends=(), inner=0.0, keep=0.45):
    """round 7 (Maxwell 11/24/2026): round every convex outline corner to r (laser cut, costs nothing), except corners within keep of a
    bend line (bend reliefs and flange roots stay as drawn); inner > 0 also fills concave corners to that radius (flat plates only)."""
    from shapely.geometry import LineString
    if inner:
        shp = shp.buffer(inner, 64, join_style=1).buffer(-inner, 64, join_style=2).simplify(0.002)
    if r <= 0:
        return shp
    shp = shp.buffer(0)
    ext = list(shp.exterior.coords)[:-1]
    if Polygon(ext).exterior.is_ccw is False:
        ext = ext[::-1]
    bl = [LineString(b) for b in bends]
    out = []
    n = len(ext)
    for i, p in enumerate(ext):
        a, b = ext[i - 1], ext[(i + 1) % n]
        cross = (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0])
        near = any(l.distance(Point(p)) < keep for l in bl)
        la, lb = math.hypot(p[0] - a[0], p[1] - a[1]), math.hypot(b[0] - p[0], b[1] - p[1])
        if cross > 1e-9 and not near and min(la, lb) > 0.05:
            out += G._fillet([a, p, b], 1, r, n=8)
        else:
            out.append(p)
    return Polygon(out, [list(h.coords) for h in shp.interiors])


def part(file, name, qty, thick, outline, holes=(), bends=(), bend_text="none", notes="", mirror=False, rnd=0.0, inner=0.0):
    shp = round_outline(outline, rnd, bends, inner) if (rnd or inner) else outline
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
def bracket():
    """flat bracket for the OPEN (west / north) side, seen from its outside face: x = u along the flight, y = z, origin at the tread's
    underside over the web's front edge. Web on the stringer side, a seat tab folded off its top edge (under the tread) and, with the
    tread strips, a bolting flange folded off its front edge (to the strip). Round 8: the same part under every tread, the lower flight's
    first one included (the floor shoe took over the slab foot)."""
    A, B = (G.WEB0, 0.0), (G.TD + G.RT, 0.0)
    C = (G.WEB0, (G.WEB0 - (G.TD + G.RT)) * G.SL)
    f_, k_ = G.UPPER, 2                                         # round 6: corners rounded (the same outline on every tread)
    uk_, zk_ = f_.uk(k_), f_.z0 + k_ * G.RI - G.TT
    web = Polygon([(u - uk_, z - zk_) for u, z in G.bracket_web(f_, k_)])
    for f2, k2 in ((G.LOWER, 1), (G.UPPER, 1), (G.LOWER, 3)):
        w2 = Polygon([(u - f2.uk(k2), z - (f2.z0 + k2 * G.RI - G.TT)) for u, z in G.bracket_web(f2, k2)])
        assert w2.symmetric_difference(web).area < 1e-3, "bracket webs differ"
    seat = rect(G.SEAT_S, G.SEAT_E, 0, G.SEAT_TAB - BD_WEB / 2)   # round 10: the seat ends where the web's riser corner starts to round
    parts_ = [web, seat]
    cuts = []                                                   # the bend runs the web's whole straight top edge, so no reliefs
    bends = [((G.SEAT_S, 0), (G.SEAT_E, 0))]
    holes = []
    if G.STRIPS:
        fl_out = T + G.ARM_FL                                   # flange: outside dimension from the stringer face
        parts_.append(rect(G.WEB0 - (fl_out - BD / 2), G.WEB0, -G.ARM_D, 0))
        cuts += [rect(G.WEB0, G.WEB0 + 0.40, -G.ARM_D - 0.25, -G.ARM_D), rect(G.SEAT_S - 0.25, G.SEAT_S, -0.40, 0)]
        bends.append(((G.WEB0, -G.ARM_D), (G.WEB0, 0)))
        d_ = T + 0.95                                           # flange bolt, slotted along the flange to take up bend tolerance
        holes.append(slot(G.WEB0 - (d_ - BD / 2), -G.FLANGE_BOLT, H38, 0.70, vertical=False))
    else:                                                       # no strip option: lag holes through the seat (5/16 lags, 11/32 clearance)
        for u_ in G.seat_lags(0.0):
            holes.append(Point(u_, (G.SEAT_TAB / 2 + G.SEAT_LAG_V) - BD_WEB / 2).buffer(0.34375 / 2, 64))
    shp = unary_union(parts_)
    for s_ in (4.25, 8.25):                                     # two through bolts into the stringer
        ub, zb = G.WEB0 + s_ * CA + nx * G.BOLT_N, C[1] + s_ * SA + nz * G.BOLT_N
        holes.append(Point(ub, zb).buffer(H38 / 2, 64))
    for c in cuts:
        shp = shp.difference(c)
    return shp, holes, bends


shp, holes, bends = bracket()
n = (G.N_LO - 1) + (G.N_UP - 1)
bt = ("2 bends, both 90 deg toward the outside face: flange off the front edge, seat tab off the top edge" if G.STRIPS
      else "1 bend, 90 deg toward the outside face: seat tab off the top edge")
where = f"every tread ({G.N_LO - 1} lower + {G.N_UP - 1} upper)"
holes_txt = ("2 x 7/16 bolt holes into the stringer, flange bolt slotted. Drill the seat tab screw holes at assembly." if G.STRIPS
             else "2 x 7/16 bolt holes into the stringer, 3 x 11/32 holes in the seat for 5/16 x 1 1/2 lags up into the tread.")
part(f"bracket_open_qty{n}.dxf", "Tread bracket, open side", n, G.WEB_T, shp, holes, bends, bt,
     f"{where}; west side of the upper flight, north side of the lower flight. {holes_txt}", rnd=0.3)
part(f"bracket_wall_qty{n}.dxf", "Tread bracket, wall side (mirror)", n, G.WEB_T, shp, holes, bends, bt,
     f"mirror image of the open side part. {where}.", mirror=True, rnd=0.3)

# ---------------------------------------------------------------- tread strips (2 in strip on edge under each tread, across both brackets)
if G.STRIPS:
    L_ = G.WN - 2 * G.ARM_END
    TAB_OUT = 1.60                     # outside, from the strip's front face (CAD 1.50; lengthened so the flat tab clears SendCutSend's 1.15 in minimum)
    shp = Polygon([(v - G.ARM_END, z) for v, z in G.strip_outline(0.0)])     # round 7: bottom end corners rounded
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
         "one under every tread. 2 x 7/16 holes for the bracket flange bolts. Drill the tab screw holes at assembly. Tabs 1.6 in outside (CAD shows 1.5).", rnd=0.3)

# ---------------------------------------------------------------- floor shoe (round 10): base under the lower stringer's foot, a wall up
# its sloped top face at the west end (the pocket), its own through bolt. Flat: x along the flight from the toe's bend line (wall at x < 0),
# y across from the centreline. The bend is 118 deg (the wall leans back over the base at the tube's slope); with SendCutSend's 1/4 in
# inside radius the flat length works out within 0.03 in of the two inside lengths from the toe, so the wall is laid straight off the line.
f_ = G.LOWER
base = Polygon([(u - f_.u0, v - G.VC) for u, v in G.shoe_base()])
wall = Polygon([(-s_, w_) for s_, w_ in G.shoe_wall()])
shp = unary_union([base, wall, rect(-0.02, 0.02, -G.TW / 2, G.TW / 2)])
for sy in (-1, 1):                                               # bend reliefs where the wings run past the wall's edges
    shp = shp.difference(rect(-0.01, 0.45, *sorted((sy * G.TW / 2, sy * (G.TW / 2 + 0.25)))))
holes = [Point(u - f_.u0, v - G.VC).buffer(HANC / 2, 64) for u, v in G.shoe_anchors()]
holes += [Point(-G.SHOE_BOLT_S, 0).buffer(H38 / 2, 64)]
part("floor_shoe_qty1.dxf", "Floor shoe under the lower stringer (a pocket)", 1, 0.25, shp, holes,
     [((0, -G.TW / 2), (0, G.TW / 2))],
     f"1 bend, {180 - math.degrees(G.ANG):.0f} deg: the wall folds up and back over the base to lie on the stringer's sloped top face ({math.degrees(G.ANG):.1f} deg pocket)",
     "the lower stringer's level foot stands on the base and its toe sits in the bend; the wall lies on the tube's top face. One 3/8 through bolt "
     "square through the wall and the tube (about 4 3/4 in, crush sleeve inside, nut on the tube's underside). Three 3/8 slab anchors (1/2 in "
     "holes): two in the wings beside the tube at the west end, one in the east tab. Nothing shares a bracket bolt.", rnd=0.3)

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
         "one through bolt across the stringer (crush sleeve inside). Other leg bolts through the beam.", mirror=mir, rnd=0.4)
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
tab = Polygon([(cx(z), yb - (w / G.TAB_W) * ((G.TAB_W + T) - BD / 2)) for w, z in G.tab_outline()])   # round 10: full height, outer corners rounded
half = unary_union([cheek, tab])
shp = unary_union([rect(-xs, xs, -ys, ys), rect(-1.5, 1.5, -ys - (leg_out - BD / 2), ys + (leg_out - BD / 2)),
                   half, sscale(half, -1, 1, origin=(0, 0))])
for sy in (-1, 1):                                               # bend reliefs where the seat meets the 3 in legs
    for sx in (-1, 1):
        shp = shp.difference(rect(sx * 1.5, sx * 1.75, sy * (ys - 0.001), sy * (ys + 0.40)))
yh = ys + (T + 2.0) - BD / 2                                     # leg bolt, 2 in below the post top
holes = [Point(0, sy * yh).buffer(H38 / 2, 64) for sy in (-1, 1)]
holes += [Point(sx * cx(G.SAD_BOLT[1]), cy(G.SAD_BOLT[0])).buffer(H38 / 2, 64) for sx in (-1, 1)]
holes += [Point(sx * cx(G.TAB_BOLT_Z), yb - ((1.05 + T) - BD / 2)).buffer(H38 / 2, 64) for sx in (-1, 1)]
bends = [((-1.5, -ys), (1.5, -ys)), ((-1.5, ys), (1.5, ys))]
bends += [((sx * xs, cy(G.CHEEK[0][0])), (sx * xs, cy(G.CHEEK[-1][0]))) for sx in (-1, 1)]
bends += [((sx * cx(G.TAB_Z[0]), yb), (sx * cx(G.TAB_Z[1]), yb)) for sx in (-1, 1)]
SAD_INFO = dict(seat=(seat_v, seat_u), cheek_h=G.Z_SEAT + 2.0 - zpt, tab=(G.TAB_W + T, G.TAB_Z[1] - G.TAB_Z[0]))
part("upper_post_saddle_qty1.dxf", "Upper stringer post saddle (seat, legs down the post, cheeks up the stringer, tabs to the landing beam)", 1, 0.25, shp, holes,
     bends, "6 bends, all 90 deg: the 2 legs DOWN (a U over the post top), the 2 cheeks UP (a U round the stringer), and a tab off each cheek's "
     "south edge bent OUT, away from the stringer (bend the tabs before the cheeks)",
     f"seat {seat_v:.2f} x {seat_u:.2f} in outside; legs 3 in wide, {leg_out:.2f} in outside, one 3/8 through bolt across the post; cheeks "
     f"{SAD_INFO['cheek_h']:.2f} in tall outside, one 3/8 through bolt across the stringer (crush sleeve inside); tabs {SAD_INFO['tab'][0]:.2f} in out x "
     f"{SAD_INFO['tab'][1]:.2f} in tall, one 3/8 bolt each through the landing's north beam. Replaces round 5's foot clips.", rnd=0.3)

# ---------------------------------------------------------------- post base plate (round 11): one part under all three slab posts
pb_ = G.post_base(-1.0, 1.0, -1.0, 1.0, "a")
h_ = G.BP_W / 2
shp = Polygon([(a + h_, b + h_) for a, b in pb_["plate"]])
holes = [Point(a + h_, b + h_).buffer(HANC / 2, 64) for a, b in pb_["anchors"]]
holes += [Point(a + h_, b + h_).buffer(CSK38 / 2, 64) for a, b in pb_["screws"]]
part("post_base_plate_qty3.dxf", "Post base plate (foot post, corner newel, upper stringer post)", 3, G.BP_T, shp, holes, (), "none",
     f"{G.BP_W:g} x {G.BP_W:g} in, corners R {G.BP_R:g}. Four 1/2 in holes at the corners for 3/8 wedge anchors. COUNTERSINK the two 13/32 in "
     f"holes ({G.BP_SCREW:g} in each side of centre) from the BOTTOM face (82 deg, 3/8 flat head): the screws go up through the plate into the "
     f"two clip angles (cut from stock L 2 x 2 x 3/8, {G.BC_L:g} in long), nuts on top; put them in before the plate is anchored. The same plate "
     "fits the 2 x 2 and the 3 x 3 posts: only the hole in the clip's flat leg moves (1.45 in from the heel for 2 x 2, 0.95 in for 3 x 3).")

# ---------------------------------------------------------------- balcony corner plates (round 10), 3/8 in: replace the round 3 L plates
# Flat in the plate's own plane: x = a (inches west of the bath 1 wall), y = z (height), the flange unfolded below the band's bend line.
BD38 = 0.60                                                      # 90 degree bend deduction taken for 3/8 in, CHECK in SendCutSend's preview
out_, (fa0, fa1, fw), pbolts, fbolts = G.corner_plate(-1)
zu_ = G.FL - G.TK
yb_ = zu_ - G.CP_T + BD38 / 2                                    # bend line
plate = Polygon(out_).difference(rect(fa0 - 1, fa1, zu_ - 1, yb_))   # the band's bottom edge becomes the bend line (the post leg keeps its length)
flange = rect(fa0, fa1, yb_ - (fw - BD38 / 2), yb_)
shp = unary_union([plate, flange])
shp = translate(shp, -(G.XL - G.CP_BAND), -(zu_ - G.CP_DROP))
holes = [Point(a - (G.XL - G.CP_BAND), z - (zu_ - G.CP_DROP)).buffer(H38 / 2, 64) for a, z in pbolts]
holes += [Point(a - (G.XL - G.CP_BAND), yb_ - ((1.0 + G.CP_T) - BD38 / 2) - (zu_ - G.CP_DROP)).buffer(H38 / 2, 64) for a in fbolts]
part("balcony_corner_plate_qty2.dxf", "Balcony corner plate (south west newel and north west post)", 2, 0.375, shp, holes,
     [((fa0 - (G.XL - G.CP_BAND), yb_ - (zu_ - G.CP_DROP)), (fa1 - (G.XL - G.CP_BAND), yb_ - (zu_ - G.CP_DROP)))],
     "1 bend, 90 deg: the flange folds under the end beam. The two are mirror images: bend ONE UP and ONE DOWN (same flat)",
     "on the inside face of the post and the end beam (south west: the south beam's north face; north west: the north arm's south face). "
     "Two 3/8 grade 5 through bolts across the post (crush sleeve inside); two 3/8 bolts up through the flange and the beam (crush sleeves), "
     "nuts in counterbores on the underside of the oak. Replaces the round 3 L plates: nothing on the stair side.", rnd=0.5, inner=0.5)

# ---------------------------------------------------------------- placeholder clips for joints the CAD does not detail yet
def clip(w, leg, file, name, qty, notes):
    shp = rect(0, w, -(leg - BD / 2), leg - BD / 2)
    holes = [Point(w / 2, s * (leg * 0.63 - BD / 2)).buffer(H38 / 2 if w > 1.5 else 0.28 / 2, 64) for s in (-1, 1)]
    part(file, name, qty, 0.25, shp, holes, [((0, 0), (w, 0))], "1 bend, 90 deg", "PLACEHOLDER for an engineer: " + notes, rnd=0.25)


clip(2.0, 1.75, "clip_angle_2in_qty18.dxf", "Clip angle 2 in wide, 1 3/4 legs", 18,
     "at the landing and balcony frame corners, including the ledger and north arm ends on the north east post. Round 7: the knee braces use gusset plates instead. Round 10: the post bases use stock angle instead.")

# ---------------------------------------------------------------- knee frame gussets (round 7): brace top, brace foot, post top
# round 10: the north knee frame's wall post is the north east guard post in one piece, so its corner gusset is gone; its brace runs to the
# north west post, so its top gusset is a new shape. The foot gusset is the same part on both frames.
for j_, what, qty, shape, bolts_ in (("top", "south frame: brace top to the head beam (2 bolts in the beam, 1 in the brace)", 1, G.gusset("top"), G.KG["top"]),
                                     ("foot", "both frames: brace foot to the wall post (2 in the post, 1 in the brace); a triangle whose lower edge follows the post's 45 deg foot cut", 2, G.gusset("foot"), G.KG["foot"]),
                                     ("corner", "south frame: wall post top to the head beam's end, an L plate (2 bolts in the post, 2 in the beam, so it cannot pivot)", 1, G.gusset("corner"), G.KG["corner"]),
                                     ("north_top", "north frame: brace top to the north arm's west end and the north west post (the post's 2 bolts are the corner plate's, 1 in the brace)", 1, G.nk_gusset("top"), G.NKG["top"])):
    a0_, z0_ = min(a for a, _ in shape), min(z for _, z in shape)
    shp = Polygon([(a - a0_, z - z0_) for a, z in shape])
    holes = [Point(a - a0_, z - z0_).buffer(H38 / 2, 64) for a, z in bolts_]
    part(f"knee_gusset_{j_}_qty{qty}.dxf", f"Knee frame gusset, {j_.replace('_', ' ')}", qty, 0.25, shp, holes, (), "none",
         f"flat: {what}. South frame: on the brace's north face; north frame: on the north face. 3/8 through bolts with crush sleeves.")
clip(1.25, 1.5, "rail_clip_1-25in_qty10.dxf", "Rail end clip 1 1/4 in wide, 1 1/2 legs", 10,
     "straight rail ends into post faces, the north guard rail into the west one, the north guard rail at the bath 1 wall, and the four guard bottom rail ends. 9/32 in holes for 1/4-20.")

shp = rect(0, 1.25, 0, 4.5)
holes = [Point(0.625, y).buffer(0.28 / 2, 64) for y in (1.0, 3.5)]
part("rail_post_strap_qty3.dxf", "Rail to post strap 1 1/4 x 4 1/2", 3, 0.25, shp, holes, (), "none",
     "PLACEHOLDER for an engineer: flat strap on the side where a rail runs over a post top (lower rail on the foot post, guard top rails on the north west and north east posts); 1/4 in spacer behind it on the rail, which sits 1/4 in in from the post face.", rnd=0.6)

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
