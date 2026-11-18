#!/usr/bin/env python3
"""Duct and truss clash check (python3 tools/truss_clash.py from the repo root, after model/make_equipment.py).

Reads site/models/equipment.json and lays out the open web floor trusses the same way site/equipment.js does.
A duct in the truss space may:
  - run parallel to the trusses (north to south) or straight up and down, if it stays clear of every truss in a bay,
  - cross the trusses (any run that is not north to south) only if it is round and no bigger than MAX_CROSS in, through the web openings.
Prints every offender and exits 1 if there is one.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "site", "models", "equipment.json")))
T = D["trusses"]
MAX_CROSS = T.get("max_cross_in", 6.0)               # largest round duct that passes the web openings ([floor_trusses] in config.toml)
DEP, SP, Z0 = T["depth_in"] / 12, T["spacing_in"] / 12, T["z0"]
CW, E = 3.5 / 12, 0.05


def truss_xs(r):
    rx0, ry0, rx1, ry1 = r
    x0, x1 = rx0 + E, rx1 - E
    if T.get("grid_x0") is not None:               # one grid for the whole house: trusses run continuous over the walls
        g, sp = T["grid_x0"], SP
        k0 = int((x0 + CW / 2 - g) // sp) - 1
        return [g + k * sp for k in range(k0, k0 + 200) if x0 + CW / 2 - 1e-6 <= g + k * sp <= x1 - CW / 2 + 1e-6]
    n = max(1, round((x1 - x0) / SP))
    return [min(x1 - CW / 2, max(x0 + CW / 2, x0 + i * (x1 - x0) / n)) for i in range(n + 1)]


REG = [(r, truss_xs(r)) for r in T["regions"] + T.get("loft_regions", [])]
bad = []
for dc in D["ducts"]:
    rnd = dc.get("shape") == "round" or isinstance(dc["size"], (int, float))
    size = dc["size"] if isinstance(dc["size"], (int, float)) else dc["size"][0]
    hw = size / 24
    for a, b in zip(dc["points"], dc["points"][1:]):
        zlo, zhi = min(a[2], b[2]), max(a[2], b[2])
        if zhi < Z0 + 0.05 or zlo > Z0 + DEP - 0.05:
            continue                               # not in the truss space
        ns = abs(a[0] - b[0]) < 1e-3
        for (rx0, ry0, rx1, ry1), xs in REG:
            ylo, yhi = min(a[1], b[1]), max(a[1], b[1])
            xlo, xhi = min(a[0], b[0]), max(a[0], b[0])
            if yhi < ry0 or ylo > ry1 or xhi < rx0 or xlo > rx1:
                continue
            if ns:
                for x in xs:
                    if abs(a[0] - x) < hw + CW / 2 - 1e-3:
                        bad.append(f"{dc['id']}: {size} in run at x {a[0]:.2f} hits the truss at x {x:.2f} (y {ylo:.1f} to {yhi:.1f})")
            else:
                pad = hw if rnd else 0.0                # a rect run's width lies across its length
                crossed = [x for x in xs if xlo - pad - CW / 2 < x < xhi + pad + CW / 2]
                if crossed and (not rnd or size > MAX_CROSS):
                    bad.append(f"{dc['id']}: {'round ' if rnd else 'rect '}{dc['size']} crosses {len(crossed)} trusses at y {a[1]:.1f} (max {MAX_CROSS} in round)")
for b in bad:
    print(b)
print(f"{len(bad)} duct and truss clashes")
sys.exit(1 if bad else 0)
