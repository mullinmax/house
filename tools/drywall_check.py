"""Drywall check (python3 tools/drywall_check.py from the repo root). The partitions A-11 draws as a bare 3 1/2 in stud are
built as a 2x4 plus 5/8 in drywall each side (make_house.py _grow_thin), so their faces sit 5/8 in further into the rooms
than the plan lines. Lists anything that still sits inside that added drywall: furniture, fixtures, cabinets and appliances
of house.json (make_house.py settle_off_drywall slides them out), and the wall devices and grilles of equipment.json.
Exit 1 if any."""
import runpy, io, contextlib, json, sys
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path("model/make_house.py")
slabs = g["drywall_slabs"]()
hits = []
for r in g["RECS"]:
    if r.get("kind") not in ("furniture", "fixture", "cabinet", "appliance"):
        continue
    for s in list(r.get("parts", [])) + [s for o in r.get("ops", []) for s in o["parts"]]:
        b = g["buried_in_drywall"](s, slabs)
        if b:
            hits.append((r["id"], s[1], b))
            break
eq = json.load(open("site/models/equipment.json"))
pts = [(it["id"], it["at"]) for it in eq["items"] if it.get("at") and it.get("layer") in ("electrical", "lowvolt")]
for d in eq["ducts"]:
    for gr in d.get("grilles", []):
        if gr.get("wall"):
            pts.append((d["id"] + " grille", gr["at"]))
for i, at in pts:
    for ax, sg, sl, a in slabs:
        if sl[0] + 0.002 < at[0] < sl[1] - 0.002 and sl[2] + 0.002 < at[1] < sl[3] - 0.002:
            hits.append((i, "point", [round(at[0], 3), round(at[1], 3), round(at[2], 2)]))
for h in hits:
    print(*h)
print(f"{len(slabs)} drywall slabs added, {len(hits)} things inside them")
sys.exit(1 if hits else 0)
