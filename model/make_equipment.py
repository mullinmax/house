#!/usr/bin/env python3
"""Writes site/models/equipment.json: appliances, mechanical equipment, piping, HVAC ducts and floor trusses.

Plain Python, no Blender. The walkthrough builds all of this in the browser (site/equipment.js), so a change
here only needs:  python model/make_equipment.py

Conventions: positions are plan feet (x east, y south from the outside NW slab corner, z up from the slab).
Sizes are inches. An item's "at" is the centre of its back face at its base, "facing" is the compass
direction of its front (0 north, 90 east, 180 south, 270 west).

Sources: Andy Roehl's mechanical plan M-10 (07/30/2026, preliminary), sealed plan sheet U-11, Geo-Hydro Supply
quotes MMUL8476-4 and MMUL8476-5 with Greg Beach's 2/26/2026 design summary, Maxwell's appliance shortlist and
his 8/14/2026 notes to Andy. Anything marked ASSUMED is a placeholder until the real document exists.
"""
import json, os

import tomllib
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml"), "rb") as _f:
    CFG = tomllib.load(_f)
CEIL = CFG["ceilings"]["flat_height"]             # flat ceilings (A-11)
TRUSS_IN = CFG["floor_trusses"]["depth_in"]       # 11-7/8 in open web floor trusses (Maxwell, 11/16/2026)
DECK_IN = CFG["floor_trusses"]["deck_in"]
DECK = CEIL + (TRUSS_IN + DECK_IN) / 12           # top of the attic deck and the loft subfloor
ZT = CEIL + TRUSS_IN / 24                         # duct centreline inside the truss space
RH = 8                                            # tallest duct that passes between the 2x4 chords (8-7/8 in clear)
ZTR = DECK + 8.0 / 12 + 0.02                      # centre of the 18 x 16 supply trunk sitting on the deck
FLAT = CFG["ceilings"]["flat_rooms"]
LOFT = CFG["loft"]["rect"]

items, runs, ducts = [], [], []
APPROX = "Dimensions are approximate: the maker's spec sheet was not reachable, so the size comes from the product class."

# ------------------------------------------------------------------ kitchen
items += [
 dict(id="oven", name="LG double wall oven", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="wall_oven_double", size=[29.75, 52.06, 25.0], at=[0.5417, 43.1, 0.95], facing=90,
      cull=[dict(box=[0.5, 41.7, 0.9, 2.9, 44.5, 5.5], materials=["Stainless", "Black Glass", "Appliance Interior"])],
      info=dict(model="LG WDEP9423F, 30 in smart double wall oven", price="About $2,095 to $2,199",
        specs=[["Size", "29.75 W x 52.06 H x 23.38 D in"], ["Cutout", "28.5 W x 51.81 H x 24 D in"], ["Capacity", "9.4 cu ft (4.7 + 4.7)"],
               ["Power", "240 V, 40 A"], ["Features", "EasyClean, air fry, ThinQ"]],
        notes=["The oven tower in the Carter Lumber drawing is 33.6 in wide with a 39 in tall opening. This oven needs a 51.81 in tall cutout, so the tower's drawer and door split has to change."],
        placement="West wall oven tower, per the cabinet plan.")),
 dict(id="cooktop", name="KitchenAid induction cooktop", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="cooktop_induction", size=[30.8, 3.7, 21.3], at=[0.74, 47.0, 3.127], facing=90,
      cull=[dict(box=[0.5, 45.4, 3.05, 2.9, 48.6, 3.35], materials=["Black Glass"])],
      info=dict(model="KitchenAid KCIT730SBL, 30 in, 5 zones", price="About $1,899",
        specs=[["Size", "30.8 W x 21.3 D x 3.7 H in"], ["Cutout", "29.5 W x 20.44 D in"], ["Zones", "Centre 10 in 2,600 W (3,700 boost), four more from 1,500 to 2,500 W"],
               ["Power", "240 V, 50 A circuit"], ["Features", "Temp Cook, Even-Heat bridge"]],
        placement="West counter run, centred on the cooktop bay in the cabinet plan.")),
 dict(id="fridge", name="Frigidaire Gallery bottom freezer fridge", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="fridge_bottom_freezer", size=[29.9, 69.9, 33.5], at=[5.425, 35.2, 0], facing=180,
      cull=[dict(box=[3.96, 35.1, 0, 6.89, 37.75, 5.99], materials=["Stainless", "Black Glass", "Appliance Interior", "Brushed Nickel"])],
      info=dict(model="Frigidaire Gallery GRBN2012AF, 20.3 cu ft", price="$1,399.99",
        specs=[["Size", "About 30 W x 70 H x 33.5 D in"], ["Capacity", "20.3 cu ft, bottom freezer"]],
        notes=[APPROX, "The fridge bay in the cabinet plan is about 36.6 in wide. This 30 in fridge leaves roughly 3 in on each side, so the bay or the side panels should be resized with Carter Lumber."],
        placement="North kitchen wall, in the panelled fridge bay.")),
 dict(id="dishwasher", name="Bosch 500 Series dishwasher", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="dishwasher", size=[23.56, 33.88, 23.75], at=[7.25, 51.458, 0.02], facing=0,
      cull=[dict(box=[6.2, 49.2, 0.3, 8.3, 51.46, 3.0], materials=["Stainless"])],
      info=dict(model="Bosch SHP65DP5N, 24 in pocket handle", price="$1,129 to $1,249",
        specs=[["Size", "23.56 W x 33.88 H x 23.75 D in"], ["Cutout", "24 W x 33.88 H x 24 D in"], ["Noise", "44 dBA"], ["Capacity", "16 place settings"],
               ["Energy", "240 kWh per year"], ["Features", "AutoAir dry, Home Connect"]],
        placement="South counter run, left of the sink.")),
 dict(id="disposal", name="InSinkErator Septic Assist disposal", category="Kitchen appliance", system="plumbing.waste", room="Kitchen", layer="appliances",
      builder="disposal", size=[9, 12.63], at=[9.8, 50.83, 1.15], facing=0,
      info=dict(model="InSinkErator Evolution Septic Assist, 3/4 HP", specs=[["Size", "About 9 in diameter x 12.63 in tall"], ["Power", "120 V"], ["Warranty", "4 years in home"],
               ["Septic", "Bio-Charge enzyme injection for septic systems"]],
        notes=["One retailer (AJ Madison) lists this model as no longer available. Worth checking stock or the current replacement before the plumbing rough-in."],
        placement="Under the kitchen sink, inside the sink base cabinet. Use no clip or the slice slider to see it.")),
 dict(id="beverage", name="Hisense beverage fridge", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="beverage_center", size=[23.4, 33.9, 25.0], at=[11.8, 44.95, 0.02], facing=90,
      cull=[dict(box=[13.6, 43.95, 0.2, 14.1, 45.95, 3.0], materials=["Stainless", "Black Glass", "Brushed Nickel"])],
      info=dict(model="Hisense HBC164N6SS, 24 in beverage centre", specs=[["Size", "23.4 W x 33.9 H x 23.6 D in"], ["Capacity", "5.4 cu ft, about 164 cans"],
               ["Power", "115 V, 0.8 A"], ["Noise", "39 dB"], ["Install", "Built in or freestanding, reversible door"]],
        placement="Under the island, facing the dining room.")),
]

# ------------------------------------------------------------------ laundry
items += [
 dict(id="washer", name="LG front load washer", category="Laundry appliance", system="laundry", room="Laundry", layer="appliances",
      builder="front_load_laundry", size=[27, 39, 30.25], at=[26.15, 22.36, 0], facing=0, replaces_nodes=["washer"],
      info=dict(model="LG WM5500HWA, 4.5 cu ft (matching white washer)", price="About $799",
        specs=[["Size", "About 27 W x 39 H x 30.25 D in"], ["Capacity", "4.5 cu ft"]],
        notes=[APPROX, "The shortlist only names the dryer. This is the matching white washer. The 5.0 cu ft WM6500HWA (about $1,199) is the step up."],
        placement="Laundry south wall, left of the dryer.")),
 dict(id="dryer", name="LG heat pump dryer", category="Laundry appliance", system="laundry", room="Laundry", layer="appliances",
      builder="front_load_laundry", size=[27, 39, 32.25], at=[28.75, 22.36, 0], facing=0, label="dryer", replaces_nodes=["dryer"],
      info=dict(model="LG DLHC5502W, 7.8 cu ft ventless heat pump dryer", price="$1,345 to $1,349",
        specs=[["Size", "27 W x 39 H x 32.25 D in (52.75 in with the door open)"], ["Capacity", "7.8 cu ft"], ["Power", "240 V, 15 A"],
               ["Venting", "None. It needs a condensate drain instead of a duct."]],
        placement="Laundry south wall, right of the washer.")),
]

# ------------------------------------------------------------------ utility room: geothermal and hot water
MAN_Y, FC_Y = 24.4, 26.9
items += [
 dict(id="geo_manifold", name="Geothermal loop manifolds", category="Geothermal", system="geothermal.loop", room="Utility", layer="mechanical",
      builder="pe_manifold", size=[30, 48, 8], at=[0.56, MAN_Y, 0], facing=90, mirror=True,
      info=dict(model="Geo-Hydro MPE532PS PE manifold set", price="$802.90 (quote MMUL8476-5, special order)",
        specs=[["Mains", "1-1/4 in PE"], ["Circuits", "5 x 3/4 in, each with a 1 in ball valve"], ["Piping", "Reverse return, supply and return in separate 4 in sweeps with a 36 in radius"],
               ["Loop field", "5 loops of 3/4 in x 600 ft PE, 103.8 gal system volume"], ["Fluid", "20% propylene glycol (Fernox Alphi-11 with F1 inhibitor)"]],
        notes=["Layout on the wall is ASSUMED. Greg's summary gives the parts and the piping scheme, not a wall elevation."],
        placement="Northwest corner of the utility room, on the west wall (Maxwell, 11/15/2026).")),
 dict(id="flow_center", name="Geo-Flo flow center", category="Geothermal", system="geothermal.loop", room="Utility", layer="mechanical",
      builder="flow_center", size=[13, 22, 11], at=[0.56, FC_Y, 2.9], facing=90,
      info=dict(model="Geo-Flo GF-1272 NP2, non pressurized, 2 pumps", price="$1,367.52 (quote MMUL8476-5)",
        specs=[["Pumps", "Two circulators"], ["Connections", "GF-2911 Flo-Link fusion set, 1-1/4 in"], ["Location", "First floor, per Greg's design summary"]],
        notes=[APPROX], placement="Utility room west wall, just south of the manifolds. 1-1/4 in insulated pipes run from here up through the ceiling to the heat pump.")),
 dict(id="water_heater", name="Heat pump water heater", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="hpwh", size=[22.25, 61.4], at=[4.5, 28.22, 0], facing=0,
      info=dict(model="Rheem ProTerra 50 gal hybrid (PROPH50 T2 RH375-30)", price="Not priced yet",
        specs=[["Tank", "50 gal"], ["Efficiency", "UEF 3.88"], ["Size", "About 22.25 in diameter x 61.4 in tall"], ["Power", "240 V, 30 A"], ["Setpoint", "37 to 145 F"]],
        notes=["Picked because sheet U-11 names the Rheem Performance Platinum 50 gal hybrid with a recirculation pump as the basis of design, and this is the same family.",
               "Alternative: A.O. Smith Signature 900 HPS10-50H45DV, 50 gal, UEF 3.80, 63 H x 22 W in, 45 dBA, built in leak detection. It wants 450 cu ft of room air. The utility room is about 540 cu ft.",
               "Shown with the U-11 details: 2 in drain pan, expansion tank, recirculation pump.", APPROX],
        placement="South wall of the utility room (Maxwell, 11/15/2026), near the floor drain on U-11.")),
]
# manifold mains to the flow center, then insulated 1-1/4 in lines up through the ceiling to the heat pump's water connections
HP_AT = [5.535, 24.9, DECK + 5.5 / 12]            # back (return side) centre of the unit base
HP_E = HP_AT[0] + 56 / 24                          # east (front, water connection) end
for k, (dz, dy) in enumerate([(3.67, -0.12), (2.67, 0.12)]):
    runs.append(dict(id=f"geo_main_{k}", info_of="geo_manifold", dia=1.66, mat="pe",
                     points=[[0.9, MAN_Y + 1.5, dz], [0.9, FC_Y - 0.75 + k * 0.4, dz], [0.9, FC_Y - 0.3 + k * 0.6, 2.6]]))
for k, (zc, off) in enumerate([(5.6, 0.0), (17.6, 0.35)]):
    z = HP_AT[2] + zc / 12
    runs.append(dict(id=f"geo_riser_{k}", name="Heat pump source piping", category="Geothermal", system="geothermal.loop", dia=2.4, mat="foam",
        info_of=None if k == 0 else "geo_riser_0",
        points=[[0.95, FC_Y - 0.2 + off, 4.75], [0.95, FC_Y - 0.2 + off, 8.55 - off], [8.9 + off, FC_Y - 0.2 + off, 8.55 - off], [8.9 + off, 24.36, 8.55 - off],
                [8.9 + off, 24.36, z], [HP_E + 0.95, 24.36, z]],
        info=dict(model="1-1/4 in PE with Aeroflex elastomeric insulation", specs=[["From", "Flow center in the utility room"], ["To", "Heat pump in the attic, through 1 in ball valves and the GF-1366 rubber hose kit"]],
                  notes=["Route is ASSUMED. Greg's summary only says the piping goes up through the ceiling to the unit."])))
for r in runs:
    if r.get("info_of") is None: r.pop("info_of", None)

# ------------------------------------------------------------------ attic: heat pump, ERV
items += [
 dict(id="heat_pump", name="Geothermal heat pump", category="HVAC", system="hvac.air", room="Attic", layer="mechanical",
      builder="geo_horizontal", size=[21.7, 21.2, 56], at=HP_AT, facing=0,
      info=dict(model="GeoComfort GZT048J11LM1CCS, 4 ton two stage, horizontal, left hand return", price="$9,979.20, or $11,797.82 for the whole quote MMUL8476-4",
        specs=[["Cabinet", "21.7 W x 21.2 H x 56.0 L in"], ["Supply opening", "11.6 x 12.5 in"], ["Full load", "48,700 Btuh cooling at EER 17.3, 36,900 Btuh heating at COP 3.6"],
               ["Part load", "38,000 Btuh at EER 24.4, 29,300 Btuh at COP 4.1"], ["Airflow", "1,368 CFM design (M-10)"], ["Load", "Manual J: 35,394 Btuh heating, 41,028 Btuh cooling"],
               ["With it", "AXCH151MB 15 kW heater $514.20, AFR1836A filter rack $132, two MERV 13 18 x 36 filters $175.68, EZ-Trap, Sensi Touch thermostat $271.20"]],
        notes=["Andy's plan names a ClimateMaster Tranquility 30 as the basis of design and assumes a downflow unit. This is the unit Greg quoted and Maxwell sent Andy on 8/14/2026.",
               "Turned so the supply leaves the west end and heads straight for the north wall trunk, with the return on the south side. Orientation is ASSUMED."],
        placement="On the attic deck over the utility room, where Andy drew HP-01, directly above the manifolds and flow center.")),
 dict(id="erv", name="Energy recovery ventilator", category="HVAC", system="hvac.ventilation", room="Attic", layer="mechanical",
      builder="erv", size=[26.6, 11.4, 19.9], at=[0.75, 28.9, DECK + 0.05], facing=90,
      info=dict(model="Panasonic Intelli-Balance 100 (ERV-01 on M-10)", specs=[["Airflow", "50 to 100 CFM balanced, boost from a bath timer switch"], ["Ducts", "Intake and exhaust through the west wall"],
               ["Stale air from", "Bath 1, bath 2 and powder exhaust grilles, 20 CFM each continuous, about 50 CFM on boost"], ["Fresh air to", "The heat pump return"]],
        notes=["Greg's alternative: RenewAire EV Premium M, about $1,800.", APPROX,
               "The bathrooms exhaust through this unit instead of separate fans (Maxwell, 11/17/2026). The code allows it because the ERV sends that air outdoors; "
               "it has to run continuously at 20 CFM or more per bathroom. Three baths plus whole house ventilation (about 75 CFM for this size and bedroom count) "
               "is near the top of a 100 CFM unit, so Andy should confirm the size. The range hood cannot connect here, it has its own duct outdoors."],
        placement="Attic deck at the west wall, south of the heat pump. Andy drew it west of HP-01.")),
]

# ------------------------------------------------------------------ ducts
def supply(id, room, cfm, dia, points, grille=None, note=None, name=None):
    d = dict(id=id, name=name or f"Supply to {room}", category="HVAC supply duct", system="hvac.supply", room=room, type="supply", shape="round", size=dia, points=points,
             info=dict(model=f'{dia} in round, {cfm} CFM', specs=[["Airflow", f"{cfm} CFM (M-10)"], ["Duct", f"{dia} in round"]], notes=[note] if note else []))
    if grille: d["grilles"] = [grille]
    ducts.append(d)

def ret(id, name, size, points, grilles=None, note=None, info_of=None):
    d = dict(id=id, name=name, category="HVAC return duct", system="hvac.return", type="return", shape="rect", size=size, points=points)
    if info_of: d["info_of"] = info_of
    else: d["info"] = dict(model=f"{size[0]} x {size[1]} in, in the floor truss space", notes=[note] if note else [])
    if grilles: d["grilles"] = grilles
    ducts.append(d)

XW, YN, YE, XJ = 1.654, 12.0, 16.1, 27.07     # west leg x, north leg y, east leg y, jog x (against bedroom 1's west wall, x 28.12)
TRUNK_NOTE = ("Rerouted from M-10. Andy drew this trunk down the middle of the attic at y about 21.6 ft. Maxwell asked for it along the north wall of the attic, "
              "so it now hugs the west wall and the north attic wall all the way to bedroom 1's west wall, follows that wall south, then runs east along bedroom 1's south wall (Maxwell, 11/17/2026: keep the middle of the attic free for storage). Size is Andy's 18 x 16 throughout, no reductions modelled.")
ducts.append(dict(id="supply_trunk", name="Supply trunk", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[18, 16],
    points=[[XW, 23.0, ZTR], [XW, YN, ZTR], [XJ, YN, ZTR], [XJ, YE, ZTR], [41.2, YE, ZTR]],
    info=dict(model="18 x 16 in main trunk, 1,368 CFM", specs=[["Airflow", "1,368 CFM total"], ["Location", "On the attic deck against the north attic wall"]], notes=[TRUNK_NOTE])))
ducts.append(dict(id="supply_plenum", info_of="supply_trunk", type="supply", shape="rect", size=[26, 24], points=[[2.52, 24.0, DECK + 1.0], [0.85, 24.0, DECK + 1.0]]))
# south main: drops from the plenum into the truss space, west wall then along the clerestory wall
ducts.append(dict(id="supply_south_main", name="South supply main", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[14, 8],
    points=[[XW, 24.6, DECK + 0.2], [XW, 24.6, ZT], [XW, 33.9, ZT], [11.0, 33.9, ZT]],
    grilles=[dict(at=[XW, 31.0, CEIL - 0.02], size=[10, 6])],
    info=dict(model="14 x 8 in, in the truss space", specs=[["Serves", "Kitchen and dining 3 x 127 CFM, pantry 22, powder 15, utility 18"]],
      notes=["New. On M-10 these rooms were fed by branches crossing the attic floor. Here one main runs in the floor trusses so nothing sits on the deck. Sizes are schematic."])))

def drop(x, y0, ys, zt=ZT):      # leave the trunk's side, drop into the truss space, run to ys
    return [[x, y0, DECK + 0.45], [x, y0 + (0.25 if ys > y0 else -0.25), zt], [x, ys, zt]]

S = "S"; N = "N"
# north wall trunk: high sidewall registers straight through the attic wall into the vaulted north rooms
supply("s_closet3", "Closet 3", 26, 6, [[3.3, YN - 0.6, 11.0], [3.3, 10.6, 11.0]], dict(at=[3.3, 10.62, 11.0], size=[10, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_closet2", "Closet 2", 32, 6, [[4.7, YN - 0.6, 11.0], [4.7, 10.3, 11.0], [4.7, 5.5, 10.25]], dict(at=[4.7, 5.44, 10.25], size=[10, 6], wall=N), "Runs exposed along the ceiling of closet 3 to reach closet 2. ASSUMED.")
supply("s_bed2", "Bedroom 2", 78, 6, [[8.5, YN - 0.6, 11.0], [8.5, 10.6, 11.0]], dict(at=[8.5, 10.62, 11.0], size=[12, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_bath2", "Bath 2", 37, 6, [[19.0, YN - 0.6, 11.0], [19.0, 10.6, 11.0]], dict(at=[19.0, 10.62, 11.0], size=[10, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_study", "Bedroom 4 / study", 104, 7, [[26.9, YN - 0.6, 11.0], [26.9, 10.6, 11.0]], dict(at=[26.9, 10.62, 11.0], size=[12, 6], wall=N),
       "High sidewall register through the attic wall.")
supply("s_hall2a", "Hall 2", 15, 6, drop(14.4, YN + 0.75, 17.8), dict(at=[14.4, 17.8, CEIL - 0.02], size=[8, 6]))
supply("s_hall2b", "Hall 2", 16, 6, drop(20.5, YN + 0.75, 13.8), dict(at=[20.5, 13.8, CEIL - 0.02], size=[8, 6]))
# west leg
supply("s_bed3", "Bedroom 3", 127, 7, [[XW + 0.75, 14.5, DECK + 0.45], [XW + 1.0, 14.5, ZT], [6.3, 14.5, ZT]], dict(at=[6.3, 14.5, CEIL - 0.02], size=[12, 8]),
       "Ceiling register moved west from x 8.5 to 6.3 ft so this run stops short of the secondary return's truss bay.")
supply("s_utility", "Utility", 18, 6, [[XW, 26.5, ZT], [3.1, 26.5, ZT]], dict(at=[3.1, 26.5, CEIL - 0.02], size=[8, 6]), "Extra capacity for the utility room computers is on Maxwell's wish list and not sized yet.")
supply("s_powder", "Powder", 15, 6, [[8.5, 33.9, ZT], [8.5, 32.4, ZT]], dict(at=[8.5, 32.4, CEIL - 0.02], size=[8, 6]))
for k, x in enumerate([3.0, 7.0, 11.0]):
    supply(f"s_kitchen{k+1}", "Kitchen / dining", 127, 7, [[x, 33.9, ZT], [x, 35.0, ZT]], dict(at=[x, 35.1, ZT], size=[14, 6], wall=S),
           "High sidewall register in the clerestory wall. M-10 had the third one at x about 17 ft, reached by a duct across the open living room, so it moved west.")
# east leg
YS = YE + 0.75
supply("s_living1", "Living", 70, 7, drop(26.6, YS, 20.6) + [[24.5, 20.6, ZT], [24.5, 22.62, ZT]], dict(at=[24.5, 22.9, ZT], size=[10, 6], wall=S),
       "Leaves the trunk corner, then jogs west in the trusses to keep the register where M-10 has it.")
supply("s_living2", "Living", 70, 7, drop(28.5, YS, 22.62), dict(at=[28.5, 22.9, ZT], size=[12, 6], wall=S),
       "Hall 1 has no supply of its own (Maxwell, 11/17/2026): one 3 ft from the main return would short circuit into it. Its 48 CFM from M-10 is split between the two living registers, which open onto the hall through the 8 ft wide cased opening.")
supply("s_laundry", "Laundry", 40, 6, drop(27.6, YS, 19.0), dict(at=[27.6, 19.0, CEIL - 0.02], size=[10, 6]))
supply("s_closet1", "Closet 1", 33, 6, drop(33.4, YS, 18.9), dict(at=[33.4, 18.9, CEIL - 0.02], size=[10, 6]))
supply("s_bath1", "Bath 1", 49, 6, drop(34.6, YS, 27.6), dict(at=[34.6, 27.6, CEIL - 0.02], size=[10, 6]), "Runs in the loft floor.")
supply("s_loft", "Loft", 88, 6, drop(36.0, YS, 24.6), dict(at=[36.0, 24.6, DECK + 0.01], size=[12, 4]), "Floor register in the loft.")
for k, x in enumerate([32.3, 38.0]):
    supply(f"s_family{k+1}", "Entry / family", 112, 7, drop(x, YS, 35.0), dict(at=[x, 35.1, ZT], size=[14, 6], wall=S), "Runs in the loft floor to a high sidewall register.")
supply("s_bed1", "Bedroom 1", 138, 8, [[40.4, YE - 0.6, 11.0], [40.4, 14.95, 11.0]], dict(at=[40.4, 14.97, 11.0], size=[14, 8], wall=N), "High sidewall register through the attic wall.")

# returns. Main: Andy's M-10 return, a 34 x 10 grille high on the hall 1 west wall and a 34 x 10 trunk on the attic deck back to the heat pump.
# Secondary: a spine in the open web floor trusses for bedrooms 2 and 3 (Maxwell, 11/17/2026), kept clear of every supply run.
DK = DECK + 5 / 12                                # centre of a 10 in tall duct lying on the deck
ret("return_main", "Main return (M-10)", [34, 10],
    [[11.95, 30.6, ZT], [10.6, 30.6, ZT], [10.6, 30.6, DK], [10.6, 27.6, DK], [5.2, 27.6, DK], [5.2, 26.4, DK]],
    grilles=[dict(at=[12.15, 30.6, ZT], size=[34, 10], wall="E")],
    note="Andy's M-10 return: one 34 x 10 grille in hall 1 and a 34 x 10 return trunk over the utility, pantry and powder rooms to HP-01. "
         "The grille sits high on the hall 1 wall above the powder room door and opens into the truss bay over the powder ceiling, then the trunk "
         "rises onto the attic deck. Route on the deck is ASSUMED to suit the heat pump position in this model.")
ducts[-1]["info"]["model"] = "34 x 10 in grille and trunk, 1,368 CFM system (M-10)"
ducts[-1]["info"]["specs"] = [["Serves", "Living, kitchen, dining, family and the halls, plus any room on transfer grilles"], ["Grille", "34 x 10 in, hall 1 (M-10)"], ["Trunk", "34 x 10 in on the attic deck (M-10)"]]
RNOTE = ("New, in addition to Andy's main return. Each bedroom has a low grille near the floor (Maxwell, 11/17/2026) with a wall stack up the stud bay into the trusses. The builder plans open web floor trusses, so bedrooms 2 and 3 get a ducted return in the truss space "
         "instead of relying only on transfer grilles. It runs north to south in one truss bay at x 7.5 ft, parallel to the trusses, so it never crosses a "
         "supply run: every supply drop in the trusses leaves the trunk south side further east, and the bedroom 3 supply stops short of this bay. "
         "Trusses are 11-7/8 in deep with about 8-7/8 in clear between the chords, so the duct is 8 in tall. Size, truss direction and bay are ASSUMED until "
         "Andy or the HVAC installer sizes them.")
XR = 9.5
LOW = 1.0                                         # centre of a low return grille, 8 in tall, its bottom 8 in above the floor
STK = [14, 3.25]                                  # wall stack: 14 x 3-1/4 in in a 2x4 stud bay (w runs along plan x)
def stack(id, x, y, info_of, size=STK):           # a return stack from a low grille up the stud bay into the truss space
    ret(id, None, size, [[x, y, LOW - 0.33], [x, y, ZT]], info_of=info_of)
ret("return_truss", "Secondary return (floor trusses)", [14, RH], [[XR, 10.8, ZT], [XR, 21.9 - 0.85, ZT]],
    grilles=[dict(at=[XR, 10.64, LOW], size=[14, 8], wall=N)], note=RNOTE)
ducts[-1]["info"]["specs"] = [["Serves", "Bedrooms 2 and 3, low wall grilles"], ["Duct", "14 x 3-1/4 in wall stacks, 14 x 8 in in one truss bay"], ["Crosses", "No supply runs"]]
stack("return_bed2_stack", XR, 10.8, "return_truss")
stack("return_bed3_stack", XR, 22.64, "return_truss")
# Study and bedroom 1 (Maxwell, 11/17/2026). Both vaulted rooms back onto the hall 2 east leg, so each gets a return into that truss
# space through a low grille and a stud bay stack. A spine runs south in one bay at x 23.6, crossing under the trunk once, turns west in the laundry, linen and bedroom 3 trusses at
# y 21.9 behind every supply drop and joins the bedroom 2 and 3 spine at x 7.5. Nothing sits on the attic deck (Maxwell: keep the tall south
# part of the attic clear). The hall 1 supply that used to cross this path now comes from the south main instead.
XS, YW = 23.6, 21.9
SNOTE = ("New, in addition to Andy's main return. The study and bedroom 1 have low grilles (Maxwell, 11/17/2026) on walls that back onto "
         "the floor trusses, with a stack up the stud bay. The duct stays in the trusses the whole way: it crosses under the supply trunk once at a right "
         "angle, runs west behind every supply drop and joins the bedroom 2 and 3 return at x 7.5, which grows to 20 x 8 from there to the riser. "
         "Sizes are ASSUMED until Andy or the HVAC installer sizes them.")
ret("return_east", "Study and bedroom 1 return", [12, RH], [[XS, 11.2, ZT], [XS, YW, ZT], [XR + 0.85, YW, ZT]], note=SNOTE)
ducts[-1]["info"]["specs"] = [["Serves", "Study and bedroom 1, low wall grilles (bedroom 1's is on its south wall, beside the door)"], ["Duct", "14 x 3-1/4 in wall stacks, 10 x 8 in branches, 12 x 8 in spine, all in the floor trusses"],
                              ["Crosses", "Under the supply trunk once, no supply runs"]]
ret("return_study", None, [10, RH], [[26.9, 10.8, ZT], [26.9, 11.2, ZT], [XS, 11.2, ZT]], grilles=[dict(at=[26.9, 10.64, LOW], size=[14, 8], wall=N)], info_of="return_east")
stack("return_study_stack", 26.9, 10.8, "return_east")
ret("return_bed1", None, [10, RH], [[28.9, 15.26, ZT], [XS, 15.26, ZT]], grilles=[dict(at=[28.9, 15.01, LOW], size=[14, 8], wall=N)], info_of="return_east")
stack("return_bed1_stack", 28.9, 15.26, "return_east")
ret("return_truss_s", None, [20, RH], [[XR, 21.9 - 0.85, ZT], [XR, 25.6, ZT], [5.2, 25.6, ZT]], grilles=[dict(at=[XR, 22.39, LOW], size=[14, 8], wall=N)], info_of="return_truss")
ret("return_riser", None, [30, RH], [[5.2, 25.6, ZT], [5.2, 25.6, DECK + 0.6]], info_of="return_truss")
ret("return_plenum", None, [36, 20], [[5.2, 24.92, DECK + 5.5 / 12 + 10.6 / 12], [5.2, 26.4, DECK + 5.5 / 12 + 10.6 / 12]], info_of="return_main")

# Bath exhaust (Maxwell, 11/17/2026): ceiling or high wall grilles in bath 1, bath 2 and the powder room, ducted to the ERV's stale air inlet
# instead of separate fans. The run hugs the supply trunk's south side on the deck so it stays in the low, north part of the attic.
EX = DECK + 0.25                                  # centre of a 6 in round lying on the deck
ENOTE = ("Exhaust grille, no fan of its own: the ERV pulls 20 CFM continuously and boosts when the bath timer switch is pressed. "
         "Allowed by the Ohio residential code (IRC M1501.1, M1505.4.4) because the ERV discharges outdoors. Duct sizes and route are ASSUMED.")
def exhaust(id, name, dia, points, grilles=None, note=None, info_of=None, room=None):
    d = dict(id=id, category="Ventilation", system="hvac.exhaust", type="exhaust", shape="round", size=dia, points=points)
    if info_of: d["info_of"] = info_of
    else:
        d.update(name=name, room=room, info=dict(model=f"{dia} in round exhaust", notes=[note] if note else []))
    if grilles: d["grilles"] = grilles
    ducts.append(d)
exhaust("ex_bath1", "Bath 1 exhaust", 4, [[37.2, 30.0, ZT], [37.2, 17.8, ZT], [37.2, 17.8, EX]], room="Bath 1",
        grilles=[dict(at=[37.2, 30.0, CEIL - 0.02], size=[10, 10])], note=ENOTE + " Runs north in the loft floor trusses between the loft and family supply drops, then up onto the deck.")
exhaust("ex_bath2", "Bath 2 exhaust", 4, [[19.8, 10.62, 11.7], [19.8, 13.5, 11.7], [19.8, 13.5, EX]], room="Bath 2",
        grilles=[dict(at=[19.8, 10.6, 11.7], size=[10, 6], wall=N)], note=ENOTE + " High on the bath 2 wall through the attic wall, over the supply trunk.")
exhaust("ex_powder", "Powder exhaust", 4, [[10.2, 32.8, ZT], [10.2, 31.8, ZT], [3.3, 31.8, ZT], [3.3, 31.8, EX], [3.3, 29.6, EX]], room="Powder",
        grilles=[dict(at=[10.2, 32.8, CEIL - 0.02], size=[8, 8])], note=ENOTE + " Runs west in the pantry trusses, then up to the ERV.")
exhaust("ex_main", "Bath exhaust main", 6, [[37.2, 17.8, EX], [25.6, 17.8, EX], [25.6, 13.5, EX], [3.3, 13.5, EX], [3.3, 29.6, EX], [2.45, 29.6, EX]],
        note="Collects the three bathroom exhausts on the attic deck along the south side of the supply trunk and down the west side to the ERV stale air inlet. ASSUMED route and size.")
# Range hood: its own duct straight out the west wall. IRC M1503: range hood ducts discharge outdoors, independent of every other exhaust system,
# smooth metal with a backdraft damper. A hood over 400 CFM also needs makeup air (M1503.6), so 400 CFM or less is assumed.
exhaust("ex_hood", "Range hood duct", 6, [[0.99, 47.0, 7.2], [-0.75, 47.0, 7.2]], room="Kitchen",
        grilles=[dict(at=[-0.78, 47.0, 7.2], size=[10, 10], wall="W")],
        note="Straight out through the west wall behind the hood's chimney cover to a wall cap with a backdraft damper. A range hood may not connect to the ERV or the return: "
             "IRC M1503 (adopted in the Ohio residential code) requires its own duct to the outdoors. Hood not picked yet, 400 CFM or less ASSUMED so no makeup air is required.")

# ERV ducts
for k, (y, nm) in enumerate([(28.2, "outdoor air in"), (29.6, "exhaust air out")]):
    ducts.append(dict(id=f"erv_wall_{k}", info_of="erv", type="erv", shape="round", size=6, points=[[0.75, y, DECK + 1.15], [-0.05, y, DECK + 1.15]]))
ducts.append(dict(id="erv_to_return", info_of="erv", type="erv", shape="round", size=6, points=[[2.95, 28.9, DECK + 1.15], [4.4, 28.9, DECK + 1.15], [4.4, 26.4, DECK + 1.15]]))

trusses = dict(id="floor_trusses", name="Open web floor trusses", category="Structure", system="structure.floor", regions=FLAT, loft_regions=[LOFT],
    z0=CEIL, depth_in=TRUSS_IN, spacing_in=CFG["floor_trusses"]["spacing_in"], deck_in=DECK_IN,
    info=dict(model="11-7/8 in open web floor trusses",
      specs=[["Depth", "11-7/8 in (Maxwell, 11/16/2026)"], ["Clear for ducts", "About 8-7/8 in between the chords"], ["Floor top", f"{DECK:.2f} ft above the slab with 3/4 in decking"],
             ["Spacing", "24 in on centre, ASSUMED"], ["Span", "North to south, ASSUMED"]],
      notes=["The attic deck and the loft floor sit on these, about 3 in higher in the attic and 2 in higher in the loft than the sealed plans.",
             "The loft railing, pony wall, ladder and furniture come from the last Blender export and still sit at the old height, about 2 in low, until the next export."]))

out = dict(
    meta=dict(units="plan feet for positions, inches for sizes", generated_by="model/make_equipment.py",
              sources=["M-10 mechanical plan 07/30/2026 (preliminary)", "U-11 sealed plan", "Geo-Hydro quotes MMUL8476-4 and MMUL8476-5", "Appliance shortlist 11/15/2026"]),
    levels=[dict(id="main", name="Main floor", cut_ft=8.85), dict(id="truss", name="Floor trusses", cut_ft=round(CEIL + TRUSS_IN / 12 - 0.03, 2)),
            dict(id="upper", name="Loft and attic", cut_ft=16.0), dict(id="all", name="Whole house", cut_ft=None)],
    items=items, runs=runs, ducts=ducts, trusses=trusses)
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "equipment.json")
with open(path, "w") as f:
    json.dump(out, f, indent=1)
print(f"wrote {os.path.normpath(path)}: {len(items)} items, {len(runs)} pipe runs, {len(ducts)} ducts")
