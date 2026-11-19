#!/usr/bin/env python3
"""Duct balance estimate, Manual D style (python3 tools/duct_balance.py from the repo root, after model/make_equipment.py).

Reads site/models/equipment.json and answers three questions about the ducts as modelled:
  - supplies: with every damper open, how much of its share does each register get, and what plenum pressure
    does it take to bring every register to its target once the easy runs are throttled,
  - returns: how much of each closed bedroom's supply comes back through its own return and how much leaves
    under the door,
  - total external static against the blower.

It is an estimate for ranking rooms and spotting undersized runs, not a design: the fitting allowances, the flex
factor, the register, grille and filter drops below are typical values, not this job's parts. The designer's
Manual D replaces it. It reports and always exits 0, so it is not a CI gate.

What it reads from each duct: size, points, type, and the fields model/make_equipment.py adds for it:
  parent  the duct this one is fed from (supply) or empties into (return); None for the two plenums
  cfm     a supply register's design airflow (M-10)
  el      extra equivalent length in ft for fittings the points do not show
  k       extra loss in velocity heads (return boot and turns)
  n       this piece stands for n equal runs side by side;  calc False: drawn only, counted through another piece's n
  room, intake   a return piece that starts at a grille, and the room it serves

Options:  --flex 1.5   --filter 0.28   --system 1368   --set <id>.<field>=<value> (try a size without editing the model)
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "site", "models", "equipment.json")))
OPT = dict(flex=1.5, filter=0.28, system=1368.0)
SETS = []
a = sys.argv[1:]
while a:
    o = a.pop(0)
    if o == "--set": SETS.append(a.pop(0))
    else: OPT[o.lstrip("-")] = float(a.pop(0))
FLEX, FILTER, SYSTEM = OPT["flex"], OPT["filter"], OPT["system"]
EL_TAKEOFF, EL_TURN, EL_TURN_RECT, EL_BOOT_WALL, EL_BOOT_CEIL = 35, 10, 20, 30, 35     # ft, typical Manual D values
REGISTER = 0.03                                    # in w.c. across a register or grille at its design airflow
UNDERCUT_SQFT = 0.25                               # 1 in under a 36 in door (M-10 note 4)

DUCTS = {d["id"]: d for d in D["ducts"]}
for st in SETS:
    key, val = st.split("="); i, f = key.split(".")
    DUCTS[i][f] = json.loads(val)


def fr(q, dia): return 0.109136 * abs(q) ** 1.9 / dia ** 5.02            # in w.c. per 100 ft, galvanized round
def deq(d): return d["size"] if isinstance(d["size"], (int, float)) else 1.30 * (d["size"][0] * d["size"][1]) ** 0.625 / (d["size"][0] + d["size"][1]) ** 0.25
def area(d): return math.pi * (d["size"] / 24) ** 2 if isinstance(d["size"], (int, float)) else d["size"][0] * d["size"][1] / 144
def is_round(d): return isinstance(d["size"], (int, float))
def mult(d): return FLEX if is_round(d) and (d.get("flex") or d["type"] == "supply") else 1.0   # round supply branches are taken as flex


def stations(p):                                   # running length at each point, and at each corner the turn in quarter turns
    s, out, turns = 0.0, [0.0], []
    for a, b in zip(p, p[1:]):
        s += math.dist(a, b); out.append(s)
    for i in range(1, len(p) - 1):
        u = [p[i][k] - p[i - 1][k] for k in range(3)]; v = [p[i + 1][k] - p[i][k] for k in range(3)]
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu > 1e-6 and lv > 1e-6:
            turns.append((out[i], math.degrees(math.acos(max(-1, min(1, sum(u[k] * v[k] for k in range(3)) / lu / lv)))) / 90))
    return out, turns


def project(p, pt):                                # station on polyline p nearest to pt
    best, s0 = (1e9, 0.0), 0.0
    for a, b in zip(p, p[1:]):
        L = math.dist(a, b)
        if L < 1e-9: continue
        t = max(0.0, min(1.0, sum((pt[k] - a[k]) * (b[k] - a[k]) for k in range(3)) / L / L))
        q = [a[k] + (b[k] - a[k]) * t for k in range(3)]
        if math.dist(q, pt) < best[0]: best = (math.dist(q, pt), s0 + t * L)
        s0 += L
    return best[1]


def bisect(f, target, hi=3000.0):                  # largest q with f(q) <= target, f rising
    lo = 0.0
    for _ in range(26):
        m = (lo + hi) / 2
        if f(m) > target: hi = m
        else: lo = m
    return lo


# ------------------------------------------------------------------ supplies
SUP = {i: d for i, d in DUCTS.items() if d["type"] == "supply" and "parent" in d}
TERM = [i for i, d in SUP.items() if d.get("cfm")]
SCALE = SYSTEM / sum(SUP[i]["cfm"] for i in TERM)
TARGET = {i: SUP[i]["cfm"] * SCALE for i in TERM}
KIDS = {i: [] for i in SUP}
for i, d in SUP.items():
    if d["parent"]: KIDS[d["parent"]].append(i)
GEO = {i: stations(d["points"]) for i, d in SUP.items()}
AT = {i: project(SUP[d["parent"]]["points"], d["points"][0]) for i, d in SUP.items() if d["parent"]}


def sub_flow(i, q): return q[i] if i in q else sum(sub_flow(c, q) for c in KIDS[i])


def along(i, s, q):                                # drop inside trunk piece i from its start to station s
    d = SUP[i]; ks = sorted(KIDS[i], key=lambda c: AT[c]); flow = sub_flow(i, q)
    dp = fr(flow, deq(d)) * mult(d) * d.get("el", 0) / 100
    cuts = [(AT[c], sub_flow(c, q)) for c in ks]
    pos = 0.0
    for at, qc in cuts + [(1e9, 0.0)]:
        end = min(at, s)
        if end > pos:
            el = sum(t * (EL_TURN if is_round(d) else EL_TURN_RECT) for st, t in GEO[i][1] if pos < st <= end)
            dp += fr(flow, deq(d)) * mult(d) * (end - pos + el) / 100
            pos = end
        if at >= s: break
        flow -= qc
    return dp


def node(i, q):                                    # drop from the supply plenum to the start of piece i
    p = SUP[i]["parent"]
    return 0.0 if not p else node(p, q) + along(p, AT[i], q)


def branch(i, qi):                                 # a register's own run: takeoff, duct, turns, boot and register
    d = SUP[i]; g = (d.get("grilles") or [{}])[0]
    L = GEO[i][0][-1]; el = EL_TAKEOFF + (EL_BOOT_WALL if g.get("wall") else EL_BOOT_CEIL) + EL_TURN * sum(t for _, t in GEO[i][1]) + d.get("el", 0)
    return fr(qi, deq(d)) * mult(d) * (L + el) / 100 + REGISTER * (qi / TARGET[i]) ** 2


def open_dampers(p0):
    q = dict(TARGET)
    for _ in range(30):
        nd = {i: node(i, q) for i in TERM}
        q = {i: 0.5 * q[i] + 0.5 * bisect(lambda x, i=i: branch(i, x), max(0.0, p0 - nd[i])) for i in TERM}
    return q


lo, hi = 0.0, 2.0
for _ in range(22):
    m = (lo + hi) / 2
    if sum(open_dampers(m).values()) > SYSTEM: hi = m
    else: lo = m
P_OPEN = lo; Q_OPEN = open_dampers(P_OPEN)
NEED = {i: node(i, TARGET) + branch(i, TARGET[i]) for i in TERM}
P_BAL = max(NEED.values())

print(f"Duct balance estimate. Flex factor {FLEX}, filter {FILTER} in w.c., system {SYSTEM:.0f} CFM.")
print(f"M-10 registers add up to {sum(SUP[i]['cfm'] for i in TERM)} CFM, so every target below is the M-10 number times {SCALE:.3f}.\n")
print("SUPPLIES, every damper open")
print(f"  {'run':14s} {'room':18s} {'size':>7s} {'ft':>5s} {'target':>6s} {'gets':>5s} {'share':>6s} {'fpm':>5s}  needs")
for i in sorted(TERM, key=lambda i: Q_OPEN[i] / TARGET[i]):
    d = SUP[i]; sz = f"{d['size']} in" if is_round(d) else f"{d['size'][0]}x{d['size'][1]}"
    print(f"  {i:14s} {d['room'][:18]:18s} {sz:>7s} {GEO[i][0][-1]:5.1f} {TARGET[i]:6.0f} {Q_OPEN[i]:5.0f} {Q_OPEN[i] / TARGET[i] * 100:5.0f}% {TARGET[i] / area(d):5.0f}  {NEED[i]:.3f}")
worst = max(NEED, key=NEED.get)
print(f"  Supply plenum pressure with every damper open: {P_OPEN:.3f} in w.c.")
print(f"  Supply plenum pressure once balanced (every register at target, the rest throttled): {P_BAL:.3f} in w.c., set by {worst}\n")

# ------------------------------------------------------------------ returns
RET = {i: d for i, d in DUCTS.items() if d["type"] == "return" and "parent" in d and d.get("calc", True)}
INT = [i for i, d in RET.items() if d.get("intake")]
ROOMS = sorted({RET[i]["room"] for i in INT if RET[i].get("room")})
ROOM_SUP = {r: sum(TARGET[i] for i in TERM if SUP[i]["room"] == r) for r in ROOMS}
REST = SYSTEM - sum(ROOM_SUP.values())
RGEO = {i: stations(d["points"]) for i, d in RET.items()}


def path(i):
    out = []
    while i and RET[i]["parent"]:
        out.append(i); i = RET[i]["parent"]
    return out


PATH = {i: path(i) for i in INT}
DESIGN = {i: (ROOM_SUP[RET[i]["room"]] / sum(1 for j in INT if RET[j].get("room") == RET[i]["room"])) if RET[i].get("room") else REST for i in INT}


def piece(i, q):
    d = RET[i]; qe = q / d.get("n", 1)
    el = RGEO[i][0][-1] + EL_TURN * sum(t for _, t in RGEO[i][1]) + d.get("el", 0)
    return fr(qe, deq(d)) * mult(d) * el / 100 + d.get("k", 0) * (qe / area(d) / 4005) ** 2


def path_dp(i, qi, q):                             # drop from intake i to the return plenum, other intakes' flows held
    dp = REGISTER * (qi / DESIGN[i]) ** 2
    for pc in PATH[i]:
        dp += piece(pc, qi + sum(q[j] for j in INT if j != i and pc in PATH[j]))
    return dp


def undercut(p): return 0.6 * 4005 * UNDERCUT_SQFT * math.sqrt(max(p, 0.0))


def returns(suction):
    q = {i: DESIGN[i] * 0.7 for i in INT}; pr = {r: 0.0 for r in ROOMS}
    for _ in range(10):
        for r in ROOMS:
            mine = [i for i in INT if RET[i].get("room") == r]
            lo, hi = 0.0, 0.3
            for _ in range(18):
                p = (lo + hi) / 2
                for i in mine: q[i] = bisect(lambda x, i=i: path_dp(i, x, q), suction + p, 600.0)
                if sum(q[i] for i in mine) + undercut(p) > ROOM_SUP[r]: hi = p
                else: lo = p
            pr[r] = (lo + hi) / 2
        for i in INT:
            if not RET[i].get("room"): q[i] = bisect(lambda x, i=i: path_dp(i, x, q), suction)
    return q, pr


lo, hi = 0.0, 1.0
for _ in range(16):
    m = (lo + hi) / 2
    q, pr = returns(m)
    if sum(q.values()) > SYSTEM: hi = m           # what does not come back through a bedroom's duct reaches the hall grille under its door
    else: lo = m
S_OPEN = (lo + hi) / 2; RQ, RP = returns(S_OPEN)
print("RETURNS, doors shut, 1 in door undercuts")
print(f"  {'room':18s} {'supply':>6s} {'ducted':>6s} {'share':>6s} {'under door':>10s} {'room Pa':>8s}  suction for 100%")
S_FULL = {}
for r in ROOMS:
    mine = [i for i in INT if RET[i].get("room") == r]; got = sum(RQ[i] for i in mine)
    full = {i: DESIGN[i] for i in INT}
    S_FULL[r] = max(path_dp(i, DESIGN[i], full) for i in mine)
    print(f"  {r[:18]:18s} {ROOM_SUP[r]:6.0f} {got:6.0f} {got / ROOM_SUP[r] * 100:5.0f}% {ROOM_SUP[r] - got:10.0f} {RP[r] * 249:8.1f}  {S_FULL[r]:.3f}")
main = [i for i in INT if not RET[i].get("room")]
print(f"  Open rooms through {', '.join(main)}: {sum(RQ[i] for i in main):.0f} CFM")
print(f"  Return plenum suction as drawn: {S_OPEN:.3f} in w.c. Every bedroom returning all its own air would take {max(S_FULL.values()):.3f}.\n")

print("TOTAL EXTERNAL STATIC, in w.c. (the coil is taken as inside the heat pump's blower rating)")
print(f"  {'':34s} {'filter':>7s} {'supply':>7s} {'return':>7s} {'total':>7s}")
print(f"  {'Dampers open, nothing balanced':34s} {FILTER:7.2f} {P_OPEN:7.2f} {S_OPEN:7.2f} {FILTER + P_OPEN + S_OPEN:7.2f}")
print(f"  {'Supplies balanced, returns as drawn':34s} {FILTER:7.2f} {P_BAL:7.2f} {S_OPEN:7.2f} {FILTER + P_BAL + S_OPEN:7.2f}")
print(f"  {'Supplies and returns balanced':34s} {FILTER:7.2f} {P_BAL:7.2f} {max(S_FULL.values()):7.2f} {FILTER + P_BAL + max(S_FULL.values()):7.2f}")
