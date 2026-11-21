#!/usr/bin/env python3
"""HVAC bill of materials: ducts, fittings, grilles and the ERV, generated from the model.

    python3 model/make_bom.py            writes site/models/bom.json, docs/hvac-bom.md and docs/hvac-bom.csv
    python3 model/make_bom.py --check    exits 1 if those files are out of date with site/models/equipment.json

Run it after model/make_equipment.py. The Pages deploy runs it too, so the list in the walkthrough (More, Bill of
materials) always matches the ducts in the deployed model.

What comes from the model: every duct run in equipment.json (size, length, bends, where it starts, the grilles on it),
counted into round pipe, flex, elbows, takeoffs, boots, registers and grilles, plus hangers and sealing estimated from
those counts. What is written here by hand: Greg's equipment quote, and the ventilation equipment the model only shows
as a box (ERV, wall hoods, controls, range hood parts). Those hand entries only show up when their item is in the model,
so a part that leaves the model leaves the list.

Rules of thumb used for the estimates (change them below if the installer prefers others):
  - round pipe comes in 5 ft joints, flex in 25 ft boxes, 10 percent extra on both
  - a bend over 60 degrees is a 90, 20 to 60 degrees is a 45; flex bends are not counted (flex makes its own)
  - rigid round is hung every 5 ft, flex every 4 ft (ADC flex guide), rectangular duct every 4 ft
  - each joint gets 3 screws, mastic and foil tape; about 40 joints per gallon of mastic, 25 per roll of tape
"""
import csv, io, json, math, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
EQ = os.path.join(ROOT, "site", "models", "equipment.json")
OUT_JSON = os.path.join(ROOT, "site", "models", "bom.json")
OUT_MD = os.path.join(ROOT, "docs", "hvac-bom.md")
OUT_CSV = os.path.join(ROOT, "docs", "hvac-bom.csv")

D = json.load(open(EQ))
DUCTS = D["ducts"]
BY = {d["id"]: d for d in DUCTS}
ITEMS = {i["id"]: i for i in D["items"]}
T = D["trusses"]
MAX_CROSS = T.get("max_cross_in", 6.0)

WASTE = 1.10
JOINT_FT, FLEX_BOX_FT = 5, 25

# ------------------------------------------------------------------ hand entries
# Greg Beach, Geo-Hydro Supply, quote MMUL8476-8 (11/19/2026, right hand return). Prices held through 12/31/2026,
# about 2 weeks from order to shipping, freight is an estimate.
QUOTE = dict(ref="MMUL8476-8", date="11/19/2026", total="$11,904.57", vendor="Geo-Hydro Supply (Greg Beach)",
             terms="Prices held through 12/31/2026. About 2 weeks from order to shipping. Freight $550 is an estimate, not a firm rate. Tax 6.75%.")
ORDER = [
    ("GZT048J11RM1CCS", "GeoComfort 4 ton two stage compact horizontal, right hand return, multi position discharge, R-454B, desuperheater (hot water generator), copper coax, EPIC controls, 208-230 V", 1, "$9,979.20", ""),
    ("WD-RES1-1000", "10 year parts only warranty (deducts $499.80, no labor allowance)", 1, "-$499.80", ""),
    ("AXCH151MB", "15 kW external close coupled electric heater for ZT042 to 048, single point wiring", 1, "$514.20", "It bolts onto the discharge: confirm it fits the end discharge this layout uses (the quote calls the package side discharge)."),
    ("AFR1836A", "Galvanized filter rack 18 x 36", 1, "$132.00", ""),
    ("AHEF1836C", "MERV 13 2 in pleated filter 18 x 36", 2, "$87.84 each", ""),
    ("ACDT1A", "EZ-Trap 3/4 in condensate trap kit", 1, "$29.34", "Needs 6-1/2 in under the unit, so the unit sits on a 6-1/2 in pad."),
    ("ATSWE42D", "Emerson Sensi Touch Wi-Fi thermostat, black", 1, "$271.20", ""),
    ("LTL freight", "Delivered to the house (estimate)", 1, "$550.00", "A regional freight terminal pickup is cheaper."),
]
ORDER_GAPS = [
    ("Hose kit (heat pump to loop)", "Rubber hose kit with the right fittings for the GZT048, the model assumes a Geo-Flo GF-1366", 1,
     "Not on MMUL8476-8. The July loop quote MMUL8476-5 listed a GF-1366 1 in hose kit ($201), but Greg suggested holding it until the heat pump was picked. Check the barn box from the 7/31 pickup and ask Greg whether it fits the right hand GZT048.", "Ask Greg"),
    ("Flow center placement", "Non pressurized flow center about 9 ft below the heat pump", 1,
     "Asked Greg on 11/18, not answered yet. Confirm before ordering, or move it to the attic.", "Ask Greg"),
]

# Things the model does not draw but the install needs.
SEPARATE_EQUIP = [
    ("heat_pump", "Secondary drain pan with float switch", "Under the heat pump, about 30 x 60 in, galvanized or plastic, with a float switch wired to stop the unit", 1, "", "Usual code answer for equipment over a finished ceiling (IRC M1411.3). Not drawn yet."),
    ("heat_pump", "Vibration isolation pad", "Under the heat pump, on the 6-1/2 in pad", 1, "", "Keeps compressor hum out of the trusses."),
    ("heat_pump", "Condensate line", "3/4 in PVC from the EZ-Trap to a drain, sloped 1/4 in per ft, plus a pump if gravity cannot reach", 1, "", "Route not drawn yet."),
    ("heat_pump", "Spare MERV 13 filters 18 x 36 x 2", "Two come with the order", 4, "", ""),
    ("heat_pump", "Flexible duct connectors (canvas)", "Supply and return collars at the heat pump, stops vibration carrying into the ducts", 2, "", ""),
]
ERV_PARTS = [
    ("erv", "Broan AI Series 210 ERV, side ports (B210E75RS)", "65 to 210 CFM", 1, "About $1,580 to $1,790", ""),
    ("erv", "Broan VBATHW 20/40/60 minute boost control", "One per bathroom: bath 1, bath 2, powder", 3, "About $34 each", ""),
    ("erv", "8 in wall hood with screen, for ERV intake and exhaust", "Two hoods on the west wall, more than 10 ft apart", 2, "", "Match the maker's hood or an insulated hood."),
    ("erv", "6 to 8 in increaser", "At the ERV's four 6 in ports (ducts are 8 in)", 4, "", "Port size ASSUMED from the side port model; check Broan's drawing."),
    ("erv", "8 in backdraft damper", "In the fresh air duct to the supply plenum", 1, "", ""),
    ("erv", "Hanging chains or straps with vibration isolators (set)", "The ERV hangs level from the roof framing", 1, "", ""),
    ("erv", "Blower interlock wire", "ERV to heat pump, so the blower runs with the ERV", 1, "", ""),
]
# Range hood and litter box parts are listed only when the model has them (two threads are still settling these).
OTHER_VENT = [
    ("litter_flow_limiter", "4 in constant airflow regulator, 20 CFM (for example Aldes CAR-II)", "Litter box exhaust, holds 20 CFM on boost too", 1, "About $30 to $50", ""),
    ("litter_damper", "4 in manual balancing damper with locking quadrant", "Litter box exhaust", 1, "About $10 to $20", ""),
    ("hood_insert", "Range hood power pack insert", "", 1, "", ""),
    ("hood_cap", "8 in range hood wall cap with damper", "West wall", 1, "", ""),
    ("hood_blower", "Range hood roof blower, about 400 CFM", "Roof, over the cooktop", 1, "", ""),
    ("hood_silencer", "8 in round duct silencer (Fantech LD 8 or similar)", "In the hood chimney", 1, "", ""),
    ("ex_hood", "8 in insulated backdraft damper for the hood duct", "At the hood", 1, "", "Worth it in a house this tight."),
]


# ------------------------------------------------------------------ geometry helpers
def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def bends(pts):
    n90 = n45 = 0
    segs = [(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-3]
    for (a, b), (c, e) in zip(segs, segs[1:]):
        u = [b[i] - a[i] for i in range(3)]
        v = [e[i] - c[i] for i in range(3)]
        cos = sum(x * y for x, y in zip(u, v)) / (math.hypot(*u) * math.hypot(*v))
        ang = math.degrees(math.acos(max(-1, min(1, cos))))
        if ang > 60:
            n90 += 1
        elif ang > 20:
            n45 += 1
    return n90, n45


def dist_to_seg(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    L2 = sum(x * x for x in ab)
    t = 0 if L2 == 0 else max(0, min(1, sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2))
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)])


def truss_xs(r):
    CW, E, SP = T.get("chord_w_in", 3.5) / 12, 0.05, T["spacing_in"] / 12
    x0, x1 = r[0] + E, r[2] - E
    g = T.get("grid_x0", 0.0)
    k0 = int((x0 + CW / 2 - g) // SP) - 1
    return [g + k * SP for k in range(k0, k0 + 200) if x0 + CW / 2 - 1e-6 <= g + k * SP <= x1 - CW / 2 + 1e-6]


REG = [(r, T["xs"][i] if "xs" in T else truss_xs(r)) for i, r in enumerate(T["regions"] + T.get("loft_regions", []))]
Z0, DEP = T["z0"], T["depth_in"] / 12


def truss_crossings(dc):
    n = 0
    for a, b in zip(dc["points"], dc["points"][1:]):
        if max(a[2], b[2]) < Z0 + 0.05 or min(a[2], b[2]) > Z0 + DEP - 0.05 or abs(a[0] - b[0]) < 1e-3:
            continue
        for (rx0, ry0, rx1, ry1), xs in REG:
            if max(a[1], b[1]) < ry0 or min(a[1], b[1]) > ry1:
                continue
            n += sum(1 for x in xs if min(a[0], b[0]) < x < max(a[0], b[0]))
    return n


def rnd(dc):
    return dc.get("shape") == "round" or isinstance(dc["size"], (int, float))


def size_txt(dc):
    return f'{dc["size"]} in round' if rnd(dc) else f'{fmt(dc["size"][0])} x {fmt(dc["size"][1])} in'


def fmt(x):
    if abs(x - round(x)) < 1e-6:
        return str(int(round(x)))
    w, f = int(x), x - int(x)
    frac = {0.25: "1/4", 0.5: "1/2", 0.75: "3/4"}.get(round(f, 2))
    return f"{w}-{frac}" if frac and w else (frac or f"{x:g}")


def family(dc):
    return dc.get("info_of") or dc["id"]


SYS_NAME = {"supply": "Supply", "return": "Return", "exhaust": "Exhaust", "erv": "ERV"}


def system_of(dc):
    fam = BY.get(family(dc), dc)
    if family(dc) == "erv":
        return "ERV"
    s = (fam.get("system") or "")
    if s.startswith("plumbing.dhw"):
        return "Water heater air"
    if fam["id"] == "ex_hood":
        return "Range hood"
    return SYS_NAME.get(dc.get("type"), dc.get("type", "Other"))


# ------------------------------------------------------------------ count the ducts
round_ft = Counter()        # (system group, size) -> rigid ft
flex_ft = Counter()         # (insulated?, size) -> flex ft
elbow90, elbow45 = Counter(), Counter()
takeoffs, tees, dampers = Counter(), Counter(), Counter()
rect_rows, run_rows, stack_rows = [], [], []
boots, registers = Counter(), Counter()
rigid_joints = flex_ends = 0
hang_rigid = hang_flex = hang_rect = 0.0
crossing_notes = []

fam_has_stack = defaultdict(bool)
for dc in DUCTS:
    if not rnd(dc) and min(dc["size"]) <= 3:
        fam_has_stack[family(dc)] = True

INSULATED_FAMS = {"hpwh_intake"}                 # the Rheem kit is insulated flex
ERV_OUTDOOR = {"erv_wall_0", "erv_wall_1"}       # outdoor side of the ERV: insulated with a vapor jacket

HEADS = [dc for dc in DUCTS if dc.get("stack_head")]
for dc in DUCTS:
    if dc.get("stack_head"):                      # counted below as a stack head per stack, not a made to measure piece
        continue
    pts, L = dc["points"], length(dc["points"])
    fam = family(dc)
    grp = system_of(dc)
    n90, n45 = bends(pts)
    is_stack = not rnd(dc) and min(dc["size"]) <= 3
    if rnd(dc):
        s = dc["size"]
        if dc.get("flex"):
            flex_ft[(fam in INSULATED_FAMS, s)] += L
            flex_ends += 2
            hang_flex += L / 4
        else:
            key = (grp + (" outdoor side, insulated" if dc["id"] in ERV_OUTDOOR else ""), s)
            round_ft[key] += L
            elbow90[s] += n90
            elbow45[s] += n45
            rigid_joints += math.ceil(L / JOINT_FT) + 2 * (n90 + n45)
            hang_rigid += L / 5
        cr = truss_crossings(dc)
        if cr:
            lim = dc.get("cross_ok", MAX_CROSS)
            crossing_notes.append((dc["id"], s, cr, s > MAX_CROSS))
    elif is_stack:
        stack_rows.append(dc)
    else:
        rect_rows.append(dict(id=dc["id"], name=BY.get(fam, dc).get("name", dc["id"]), size=size_txt(dc), ft=L, bends=n90 + n45,
                              part=("part of " + BY[fam]["name"]) if fam != dc["id"] and fam in BY else "",
                              lined=("lined" in json.dumps(BY.get(fam, dc).get("info", {})).lower() and dc.get("type") == "return")))
        hang_rect += L / 4
    # where it starts
    par = BY.get(dc.get("parent"))
    if par and rnd(dc) and not is_stack:
        if rnd(par):
            tees[f'{par["size"]} x {dc["size"]} in'] += 1
        else:
            takeoffs[(dc["size"], bool(dc.get("damper")))] += 1
            if dc.get("damper"):
                dampers[dc["size"]] += 0      # the damper comes in the takeoff
    elif not par and rnd(dc) and dc.get("type") == "exhaust" and not dc.get("info_of") and not dc.get("flex") and dc["id"] != "ex_hood":
        # exhaust branches carry no parent field: find the duct their far end lands on
        end = pts[-1]
        for o in DUCTS:
            if o is dc or not rnd(o) or family(o) == dc["id"]:
                continue
            if any(dist_to_seg(end, a, b) < 0.5 for a, b in zip(o["points"], o["points"][1:])):
                tees[f'{o["size"]} x {dc["size"]} in wye'] += 1
                if not any(k in ITEMS for k in ("litter_flow_limiter", "litter_damper")) or dc["id"] != "ex_litter":
                    dampers[dc["size"]] += 1        # the litter branch has its own damper or flow limiter, listed above
                break
    # grilles and boots
    for g in dc.get("grilles", []):
        gs = f'{fmt(g["size"][0])} x {fmt(g["size"][1])}'
        kind = "sidewall" if g.get("wall") else "ceiling"
        t = dc.get("type")
        word = {"supply": "supply register", "return": "return grille", "exhaust": "exhaust grille"}.get(t, "grille")
        if dc["id"] == "transfer_utility":
            word = "transfer grille"
        if dc["id"] == "ex_litter_stack":
            word = "filter grille (litter box pickup)"
        registers[(f"{gs} in {kind} {word}", grp)] += 1
        if fam_has_stack[fam] and g["at"][2] < 3:
            boots[f"Wall stack boot for a {gs} in grille"] += 1
        elif rnd(dc):
            boots[f'{gs} in {kind} boot x {dc["size"]} in round'] += 1
    if not is_stack and not dc.get("info_of"):
        run_rows.append(dict(id=dc["id"], name=dc.get("name", dc["id"]), system=grp, room=dc.get("room", ""), size=size_txt(dc),
                             ft=sum(length(o["points"]) for o in DUCTS if family(o) == dc["id"] and not (not rnd(o) and min(o["size"]) <= 3)),
                             cfm=dc.get("cfm"), flex=bool(dc.get("flex")),
                             crosses=sum(truss_crossings(o) for o in DUCTS if family(o) == dc["id"] and rnd(o)),
                             stacks=sum(1 for o in DUCTS if family(o) == dc["id"] and not rnd(o) and min(o["size"]) <= 3)))

stack_ct = Counter()
stack_ft = Counter()
for s in stack_rows:
    k = f'{fmt(s["size"][0])} x {fmt(s["size"][1])} in'
    stack_ct[k] += 1
    stack_ft[k] += length(s["points"])


def joints_for(ft):
    return math.ceil(ft * WASTE / JOINT_FT)


# ------------------------------------------------------------------ build sections
def row(item, spec="", qty="", unit="", where="", note="", price="", status=""):
    return dict(item=item, spec=spec, qty=qty, unit=unit, where=where, note=note, price=price, status=status)


sections = []

sections.append(dict(id="order", title=f"In the equipment order ({QUOTE['ref']})", buy="Geo-Hydro Supply",
                     note=f"{QUOTE['vendor']}, quote {QUOTE['ref']} of {QUOTE['date']}, total {QUOTE['total']}. {QUOTE['terms']}",
                     rows=[row(c, d, q, "ea", "", n, p, "On the quote") for c, d, q, p, n in ORDER]
                     + [row(c, d, q, "", "", n, "", s) for c, d, q, n, s in ORDER_GAPS]))

sections.append(dict(id="equipment", title="Buy separately: heat pump install parts", buy="Separately",
                     note="Not on Greg's quote and not drawn in the model yet.",
                     rows=[row(n, s, q, "ea", "", note, p) for key, n, s, q, p, note in SEPARATE_EQUIP if key in ITEMS]))

vent = [row(n, s, q, "ea", "", note, p) for key, n, s, q, p, note in ERV_PARTS if key in ITEMS]
vent += [row(n, s, q, "ea", "", note, p) for key, n, s, q, p, note in OTHER_VENT if key in ITEMS or key in BY]
if "hpwh_intake" in BY:
    vent.append(row("Rheem water heater duct kit", "8 in insulated flex SP20889, elbows SP20890, outlet adaptor SP17829", 1, "kit", "Water heater intake and exhaust to the attic",
                    "Must not tie into any other duct (Rheem)."))
sections.append(dict(id="vent", title="Buy separately: ERV and ventilation equipment", buy="Separately",
                     note="Listed from the parts in the model. The range hood rows follow whichever hood design is in the model.",
                     rows=vent))

rows = []
for (grp, s), ft in sorted(round_ft.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    j = joints_for(ft)
    rows.append(row(f"{s} in round pipe, 30 ga snap lock", grp, j, f"x {JOINT_FT} ft", f"{ft:.0f} ft in the model",
                    "Insulate with R-8 wrap or use insulated duct, vapor jacket outside" if "insulated" in grp else ""))
for (ins, s), ft in sorted(flex_ft.items(), key=lambda kv: kv[0][1]):
    if ins:
        continue                                       # the Rheem kit covers it
    rows.append(row(f"{s} in flex duct, R-6 insulated", "Return runs through the trusses", math.ceil(ft * WASTE / FLEX_BOX_FT), f"x {FLEX_BOX_FT} ft box",
                    f"{ft:.0f} ft in the model", "Pull it tight, no sags; support every 4 ft"))
for s in sorted(set(elbow90) | set(elbow45)):
    if elbow90[s]:
        rows.append(row(f"{s} in adjustable 90 elbow", "", elbow90[s], "ea", "Counted from the bends in the model"))
    if elbow45[s]:
        rows.append(row(f"{s} in adjustable 45 elbow", "", elbow45[s], "ea", "Counted from the bends in the model"))
for (s, dmp), n in sorted(takeoffs.items()):
    rows.append(row(f"{s} in round takeoff (starting collar){' with volume damper' if dmp else ''}", "Off a rectangular trunk, main or plenum", n, "ea",
                    "", "Supply branches get a manual damper to set at air balancing (M-10)" if dmp else ""))
for k, n in sorted(tees.items()):
    rows.append(row(f"{k} {'tee or wye' if 'wye' not in k else ''}".strip(), "Branch into a round main", n, "ea"))
for s, n in sorted(dampers.items()):
    if n:
        rows.append(row(f"{s} in manual balancing damper", "One per ERV exhaust branch", n, "ea", "", "Set each bathroom to 20 CFM continuous"))
sections.append(dict(id="round", title="Buy separately: round duct, flex and fittings", buy="Separately",
                     note=f"Counted from the model with {round((WASTE - 1) * 100)} percent extra. Anything that crosses the floor trusses must be {fmt(MAX_CROSS)} in round or smaller (7 in only if the builder confirms the web openings).",
                     rows=rows))

rows = []
PART_NAME = {"supply_plenum": "supply plenum at the heat pump", "supply_kitchen_riser": "kitchen riser", "return_main": "main return grille collar",
             "return_main_riser": "main return drop box", "return_main_deck": "main return trunk", "return_bed1_head": "bedroom 1 return header box",
             "transfer_utility": "utility room transfer sleeve", "return_study_high": "study high return boot"}
for r in rect_rows:
    label = PART_NAME.get(r["id"], r["name"][0].lower() + r["name"][1:])
    rows.append(row(f"{r['size']} {label}", r["part"] or "Fabricated", 1, "piece", f"{r['ft']:.1f} ft, {r['bends']} turns",
                    "1 in acoustic liner" if r["lined"] else ""))
for k in stack_ct:
    rows.append(row(f"Wall stack {k}", "In a 2x4 stud bay (stock 3-1/4 in deep stacks also fit)", stack_ct[k], "ea", f"{stack_ft[k]:.0f} ft total",
                    "Plus one stack head per stack, or a header box"))
if HEADS:
    rows.append(row("Stack head, wall stack to side round collar", "Sits on the top plate in the truss bay over the stack; the round collar is on its "
                    f"south face, so the round runs straight off it with no elbow beside the wall. About 12 x 4 in, 8 to 11 in tall",
                    len(HEADS), "ea", "", "The stud bay and the truss bay over it are about 2 in apart: the head is as wide as the part they share"))
sections.append(dict(id="rect", title="Buy separately: rectangular duct, plenums and stacks", buy="Sheet metal shop",
                     note="Trunks, plenums and boxes are usually made to measure by a sheet metal shop once the equipment is set. Sizes and lengths are from the model.",
                     rows=rows))

rows = [row(k, "", n, "ea") for k, n in sorted(boots.items())]
for (k, grp), n in sorted(registers.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    rows.append(row(k[0].upper() + k[1:], grp, n, "ea"))
sections.append(dict(id="grilles", title="Buy separately: boots, registers and grilles", buy="Separately",
                     note="Sidewall supply registers in the door walls should be long throw types aimed across the room. Grille sizes are the duct openings.",
                     rows=rows))

joints = rigid_joints + 2 * len(rect_rows) + 2 * sum(stack_ct.values())
hangers = math.ceil(hang_rigid + hang_flex + hang_rect)
rows = [
    row("Duct mastic, water based, UL 181", "", max(1, math.ceil(joints / 40)), "gal", f"About {joints} joints"),
    row("Foil tape, UL 181A-P / 181B-FX", "", max(1, math.ceil(joints / 25)), "roll"),
    row("#8 x 1/2 in self drilling sheet metal screws", "3 per joint", math.ceil(joints * 3 / 100) * 100, "ea"),
    row("Flex duct clamps or nylon duct ties", "2 per flex connection", flex_ends * 2, "ea"),
    row("Hanger strap, 1 in galvanized or 1-1/2 in flex saddle strap", "Rigid every 5 ft, flex every 4 ft, rect every 4 ft", hangers, "hangers", "About 3 ft of strap each"),
    row("Acoustic duct liner, 1 in", "Main return box and trunk", 1, "roll", "", "Often supplied by the sheet metal shop"),
    row("Duct insulation wrap, R-8 with vapor jacket", "ERV outdoor ducts", math.ceil(sum(ft for (g, s), ft in round_ft.items() if "insulated" in g) * WASTE), "ft", "",
        "Supply and return ducts sit inside the SIP envelope, so they do not need insulation by code"),
]
sections.append(dict(id="supplies", title="Buy separately: sealing, hanging and insulation", buy="Separately",
                     note="Estimated from the joint and length counts above.", rows=rows))

runs = sorted(run_rows, key=lambda r: (r["system"], r["id"]))
over = [c for c in crossing_notes if c[3]]
meta = dict(generated_from="site/models/equipment.json", by="model/make_bom.py",
            truss_rule=f"Ducts through the open web floor trusses: {fmt(MAX_CROSS)} in round max (7 in only if verified). Use more runs, not bigger ones.",
            over_limit=[f"{BY[i].get('name', i)} ({BY[i].get('info', {}).get('model', '').split(',')[0] or str(s) + ' in round'}) crosses {n} trusses. Allowed in the model, still needs the builder's OK on the web openings." for i, s, n, _ in over],
            quote=QUOTE)
BOM = dict(meta=meta, sections=sections, runs=runs)


# ------------------------------------------------------------------ write
def md():
    o = ["# HVAC duct and ERV bill of materials", "",
         "Generated by `model/make_bom.py` from `site/models/equipment.json`. Do not edit by hand: change the model and rerun it. "
         "The same list is in the walkthrough under More, Bill of materials.", "",
         f"**Truss rule:** {meta['truss_rule']}", ""]
    for n in meta["over_limit"]:
        o.append(f"- {n}")
    if meta["over_limit"]:
        o.append("")
    for s in sections:
        o += [f"## {s['title']}", "", s["note"], "", "| Item | Spec | Qty | Unit | Where | Notes |", "|---|---|---|---|---|---|"]
        for r in s["rows"]:
            note = " ".join(x for x in (r["price"], r["status"], r["note"]) if x)
            o.append(f"| {r['item']} | {r['spec']} | {r['qty']} | {r['unit']} | {r['where']} | {note} |".replace("\n", " "))
        o.append("")
    o += ["## Every run in the model", "", "| Run | System | Room | Size | Length ft | CFM | Flex | Truss crossings | Wall stacks |", "|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        o.append(f"| {r['name']} | {r['system']} | {r['room']} | {r['size']} | {r['ft']:.1f} | {r['cfm'] or ''} | {'yes' if r['flex'] else ''} | {r['crosses'] or ''} | {r['stacks'] or ''} |")
    return "\n".join(o) + "\n"


def csvtxt():
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(["Section", "Buy from", "Item", "Spec", "Qty", "Unit", "Where", "Price", "Status", "Notes"])
    for s in sections:
        for r in s["rows"]:
            w.writerow([s["title"], s["buy"], r["item"], r["spec"], r["qty"], r["unit"], r["where"], r["price"], r["status"], r["note"]])
    return b.getvalue()


outs = {OUT_JSON: json.dumps(BOM, indent=1) + "\n", OUT_MD: md(), OUT_CSV: csvtxt()}
if "--check" in sys.argv:
    stale = [p for p, t in outs.items() if not os.path.exists(p) or open(p).read() != t]
    for p in stale:
        print(f"out of date: {os.path.relpath(p, ROOT)} (run python3 model/make_bom.py)")
    sys.exit(1 if stale else 0)
os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
for p, t in outs.items():
    open(p, "w").write(t)
print(f"wrote {len(sections)} sections, {sum(len(s['rows']) for s in sections)} rows, {len(runs)} runs")
