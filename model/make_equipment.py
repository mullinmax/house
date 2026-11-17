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
OVEN_Z = CFG["kitchen"].get("oven_face_bottom", 1.22)            # bottom of the wall oven's face, ft
OVEN_H = CFG["kitchen"].get("oven_face_height_in", 50.75)

items, runs, ducts = [], [], []
APPROX = "Dimensions are approximate: the maker's spec sheet was not reachable, so the size comes from the product class."

# ------------------------------------------------------------------ kitchen
items += [
 dict(id="oven", name="Frigidaire Gallery double wall oven", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="wall_oven_double", size=[29.87, OVEN_H, 25.19], at=[0.5417, 43.1, OVEN_Z], facing=90,
      cull=[dict(box=[0.5, 41.7, 0.9, 2.9, 44.5, 5.5], materials=["Stainless", "Black Glass", "Appliance Interior"])],
      info=dict(model="Frigidaire Gallery GCWD3067AF, 30 in double electric wall oven with air fry", price="$2,099 at Lowe's on 11/17/2026 (list $3,599)",
        specs=[["Size", "29.87 W x 50.75 H x 25.19 D in"], ["Cutout", "28.5 W x 48.875 H x 23.5 D in"], ["Capacity", "10.6 cu ft (5.3 + 5.3)"],
               ["Power", "240 V, 40 A"], ["Features", "Air fry, steam cook, single fan convection with a European element, self clean and steam clean"],
               ["Finish", "Fingerprint resistant stainless steel"]],
        notes=["Maxwell's pick (11/17/2026), replacing the LG WDEP9423F.",
               f"The oven tower is changed to suit it: the face starts {OVEN_Z * 12:.1f} in above the floor over one drawer, and the doors above start at {OVEN_Z * 12 + OVEN_H + 0.25:.1f} in. "
               "The Carter Lumber drawing shows a 39 in tall opening, so the tower's drawer and door split has to change in the cabinet order. The tower is 33.6 in wide, which leaves about 2.5 in of stile each side of the 28.5 in cutout.",
               "Size and cutout from the Lowe's listing. Confirm against the Frigidaire installation guide before the cabinets are ordered."],
        placement="West wall oven tower, per the cabinet plan.")),
 dict(id="cooktop", name="KitchenAid induction cooktop", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="cooktop_induction", size=[30.8, 3.7, 21.3], at=[0.74, 47.0, 3.127], facing=90,
      cull=[dict(box=[0.5, 45.4, 3.05, 2.9, 48.6, 3.35], materials=["Black Glass"])],
      info=dict(model="KitchenAid KCIT730SBL, 30 in, 5 zones", price="About $1,899",
        specs=[["Size", "30.8 W x 21.3 D x 3.7 H in"], ["Cutout", "29.5 W x 20.44 D in"], ["Zones", "Centre 10 in 2,600 W (3,700 boost), four more from 1,500 to 2,500 W"],
               ["Power", "240 V, 50 A circuit"], ["Features", "Temp Cook, Even-Heat bridge"]],
        placement="West counter run, centred on the cooktop bay in the cabinet plan.")),
 dict(id="fridge", name="Whirlpool counter depth French door fridge", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="fridge_french_door", size=[35.75, 70, 31.8], at=[5.475, 35.2, 0], facing=180,
      cull=[dict(box=[3.96, 35.1, 0, 6.99, 37.75, 5.99], materials=["Stainless", "Black Glass", "Appliance Interior", "Brushed Nickel"])],
      info=dict(model="Whirlpool WRFC5036RZ, 36 in true counter depth, 3 door French door, 23.4 cu ft",
        specs=[["Size", "35 3/4 W x 70 H x 31 4/5 D in"], ["Capacity", "23.4 cu ft"], ["Doors", "Two French doors over a bottom freezer drawer"],
               ["Dispenser", "Water and ice in the left door"], ["Finish", "Fingerprint resistant stainless"]],
        notes=["Size from the dimensioned product photo Maxwell sent (11/17/2026).",
               "The fridge bay was 36.6 in wide with 3/4 in panels inside it, which left only about 35.1 in clear. It is widened to 37.8 in here (about 36.3 in clear) so this fridge fits. Check the exact cutout and door clearance with Carter Lumber and the Whirlpool install guide."],
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
      builder="beverage_center", size=[23.4, 33.9, 25.0], at=[11.81, 44.95, 0.02], facing=90,   # 1/8 in off the island back, which it was flush with
      cull=[dict(box=[13.6, 43.95, 0.2, 14.1, 45.95, 3.0], materials=["Stainless", "Black Glass", "Brushed Nickel"])],
      info=dict(model="Hisense HBC164N6SS, 24 in beverage centre", specs=[["Size", "23.4 W x 33.9 H x 23.6 D in"], ["Capacity", "5.4 cu ft, about 164 cans"],
               ["Power", "115 V, 0.8 A"], ["Noise", "39 dB"], ["Install", "Built in or freestanding, reversible door"]],
        placement="Under the island, facing the dining room.")),
]

# ------------------------------------------------------------------ laundry
items += [
 dict(id="washer_dryer", name="GE Profile UltraFast Combo washer dryer", category="Laundry appliance", system="laundry", room="Laundry", layer="appliances",
      builder="front_load_laundry", size=[28, 46.7, 32], at=[27.45, 22.36, 0], facing=0, finish="graphite", kind_ring="dark", replaces_nodes=["washer", "dryer"],
      cull=[dict(box=[24.95, 19.7, 0.0, 29.95, 22.45, 3.3], materials=["Enamel White", "Plastic Grey", "Aluminum", "Black Glass", "Glass"])],   # the baked pair, merged into per material meshes
      info=dict(model="GE Profile PFQ97HSPVDS UltraFast Combo, 4.8 cu ft all in one washer dryer, Carbon Graphite", price="$2,199 at Lowe's",
        specs=[["Size", "28 W x 46 7/10 H x 32 D in"], ["Capacity", "4.8 cu ft, washes and dries in one drum"], ["Drying", "Ventless heat pump, no dryer vent"],
               ["Power", "120 V, 11 A, on its own 15 A circuit, outlet within 36 in of the cord entry"],
               ["Water", "Hot and cold valves 36 1/4 in above the floor, drain hose standpipe"], ["Clearance", "0 in sides and top, 1/2 in each side suggested"], ["Weight", "302 lb"]],
        notes=["One combo unit replaces the separate washer and dryer (Maxwell, 11/17/2026). Lowe's lists this listing as model PFQ97HSPVDS.",
               "Size from AJ Madison and the GE spec sheet. It is 7 1/2 in taller than a standard front loader, so check any counter or shelf planned above it."],
        placement="Laundry south wall, centred where the washer and dryer pair stood.")),
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
      builder="erv", size=[19.9, 11.4, 26.6], at=[0.75, 28.9, DECK + 0.05], facing=90,
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

XW, YN, YE, XJ = 1.654, 12.0, 16.1, 27.07     # west leg x, north leg y, east leg y, jog x (against bedroom 1's west wall, x 28.12)
TRUNK_NOTE = ("Rerouted from M-10. Andy drew this trunk down the middle of the attic at y about 21.6 ft. Maxwell asked for it along the north wall of the attic, "
              "so it now hugs the west wall and the north attic wall all the way to bedroom 1's west wall, follows that wall south, then runs east along bedroom 1's south wall (Maxwell, 11/17/2026: keep the middle of the attic free for storage). Size is Andy's 18 x 16 throughout, no reductions modelled.")
ducts.append(dict(id="supply_trunk", name="Supply trunk", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[18, 16],
    points=[[XW, 23.0, ZTR], [XW, YN, ZTR], [XJ, YN, ZTR], [XJ, YE, ZTR], [41.2, YE, ZTR]],
    info=dict(model="18 x 16 in main trunk, 1,368 CFM", specs=[["Airflow", "1,368 CFM total"], ["Location", "On the attic deck against the north attic wall"]], notes=[TRUNK_NOTE])))
ducts.append(dict(id="supply_plenum", info_of="supply_trunk", type="supply", shape="rect", size=[26, 24], points=[[2.52, 24.0, DECK + 1.0], [0.85, 24.0, DECK + 1.0]]))
def drop(x, y0, ys, zt=ZT):      # leave the trunk's side, drop into the truss space, run to ys
    return [[x, y0, DECK + 0.45], [x, y0 + (0.25 if ys > y0 else -0.25), zt], [x, ys, zt]]

# The floor trusses sit on one 24 in grid across the house (they run continuous over the interior walls), so every
# truss bay lines up from room to room: trusses at x = TG + 2k, bays centred on TG + 1 + 2k (1.7, 3.7, 5.7, ...).
# A duct may run north to south inside a bay at any size that fits, but anything crossing the trusses goes through
# the web openings, so it is round and 7 in or less (tools/truss_clash.py checks both).
TG = CFG["floor_trusses"].get("grid_x0", 0.7)
def bay(x):                       # centre of the truss bay nearest x
    return round(TG + 1 + 2 * round((x - TG - 1) / 2), 3)

S = "S"; N = "N"
# north wall trunk: high sidewall registers straight through the attic wall into the vaulted north rooms
supply("s_closet3", "Closet 3", 26, 6, [[3.3, YN - 0.6, 11.0], [3.3, 10.6, 11.0]], dict(at=[3.3, 10.62, 11.0], size=[10, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_closet2", "Closet 2", 32, 6, [[4.7, YN - 0.6, 11.0], [4.7, 10.3, 11.0], [4.7, 5.5, 10.25]], dict(at=[4.7, 5.44, 10.25], size=[10, 6], wall=N), "Runs exposed along the ceiling of closet 3 to reach closet 2. ASSUMED.")
supply("s_bed2", "Bedroom 2", 78, 6, [[8.5, YN - 0.6, 11.0], [8.5, 10.6, 11.0]], dict(at=[8.5, 10.62, 11.0], size=[12, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_bath2", "Bath 2", 37, 6, [[19.0, YN - 0.6, 11.0], [19.0, 10.6, 11.0]], dict(at=[19.0, 10.62, 11.0], size=[10, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_study", "Bedroom 4 / study", 104, 7, [[26.9, YN - 0.6, 11.0], [26.9, 10.6, 11.0]], dict(at=[26.9, 10.62, 11.0], size=[12, 6], wall=N),
       "High sidewall register through the attic wall.")
supply("s_hall2a", "Hall 2", 15, 6, drop(bay(14.4), YN + 0.75, 17.8), dict(at=[bay(14.4), 17.8, CEIL - 0.02], size=[8, 6]))
supply("s_hall2b", "Hall 2", 16, 6, drop(bay(20.5), YN + 0.75, 13.8), dict(at=[bay(20.5), 13.8, CEIL - 0.02], size=[8, 6]))
# west leg
XB3 = bay(1.7) + 0.55                             # bottom takeoff under the trunk, in the first truss bay
supply("s_bed3", "Bedroom 3", 127, 7, [[XB3, 14.5, DECK + 0.3], [XB3, 14.5, ZT], [bay(5.7), 14.5, ZT]], dict(at=[bay(5.7), 14.5, CEIL - 0.02], size=[12, 8]),
       "Bottom takeoff from the trunk into the first truss bay, then crosses two trusses to a ceiling register in the next bay west of the bedroom 3 return.")
# south main: drops from the plenum into the first truss bay at the west wall and runs south in it. Each kitchen and powder
# register then gets its own round branch through the truss webs (a rectangular main cannot cross the trusses).
XM = bay(1.7)
SMAIN_END = 34.3
ducts.append(dict(id="supply_south_main", name="South supply main", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[14, 8],
    points=[[XM, 24.6, DECK + 0.2], [XM, 24.6, ZT], [XM, SMAIN_END, ZT]],
    grilles=[dict(at=[XM, 31.0, CEIL - 0.02], size=[10, 6])],
    info=dict(model="14 x 8 in in the first truss bay, then 6 and 7 in round branches", specs=[["Serves", "Kitchen and dining 3 x 127 CFM, pantry 22, powder 15, utility 18"]],
      notes=["New. On M-10 these rooms were fed by branches crossing the attic floor. Here the main runs south in the truss bay along the west wall, "
             "which is parallel to the trusses so a rectangular duct fits, and each register gets its own round branch through the truss webs. Sizes are schematic."])))
supply("s_utility", "Utility", 18, 6, [[XM, 26.5, ZT], [3.1, 26.5, ZT]], dict(at=[3.1, 26.5, CEIL - 0.02], size=[8, 6]), "Extra capacity for the utility room computers is on Maxwell's wish list and not sized yet.")
supply("s_powder", "Powder", 15, 6, [[XM, 32.2, ZT], [9.1, 32.2, ZT]], dict(at=[9.1, 32.2, CEIL - 0.02], size=[8, 6]), "Round branch off the south main through the pantry trusses.")
for k, (x, yb) in enumerate([(bay(3.0), 34.15), (bay(7.0), 33.5), (bay(11.0), 32.85)]):
    supply(f"s_kitchen{k+1}", "Kitchen / dining", 127, 7, [[XM, yb, ZT], [x, yb, ZT], [x, 35.0, ZT]], dict(at=[x, 35.1, ZT], size=[14, 6], wall=S),
           "High sidewall register in the clerestory wall, on its own 7 in round branch through the pantry and powder trusses. M-10 had the third one at x about 17 ft, reached by a duct across the open living room, so it moved west.")
# east leg
YS = YE + 0.75
XL = bay(27.6)                                     # laundry and living 1 share one bay, side by side
supply("s_laundry", "Laundry", 40, 6, drop(XL - 0.35, YS, 19.0), dict(at=[XL - 0.35, 19.0, CEIL - 0.02], size=[10, 6]))
supply("s_living1", "Living", 70, 7, drop(XL + 0.35, YS, 21.4) + [[bay(23.7), 21.4, ZT], [bay(23.7), 22.62, ZT]], dict(at=[bay(23.7), 22.9, ZT], size=[10, 6], wall=S),
       "Drops in the laundry bay, then crosses the trusses west under the study and bedroom 1 returns to keep the register near where M-10 has it.")
supply("s_living2", "Living", 70, 7, drop(bay(29.7), YS, 22.62), dict(at=[bay(29.7), 22.9, ZT], size=[12, 6], wall=S),
       "Hall 1 has no supply of its own (Maxwell, 11/17/2026): one 3 ft from the main return would short circuit into it. Its 48 CFM from M-10 is split between the two living registers, which open onto the hall through the 8 ft wide cased opening.")
supply("s_closet1", "Closet 1", 33, 6, drop(bay(33.4), YS, 18.9), dict(at=[bay(33.4), 18.9, CEIL - 0.02], size=[10, 6]))
XB1 = bay(35.7)                                    # bath 1 and the loft share one bay
supply("s_bath1", "Bath 1", 49, 6, drop(XB1 - 0.35, YS, 27.6), dict(at=[XB1 - 0.35, 27.6, CEIL - 0.02], size=[10, 6]), "Runs in the loft floor.")
supply("s_loft", "Loft", 88, 6, drop(XB1 + 0.35, YS, 24.6) + [[XB1 + 0.35, 24.6, DECK + 0.01]], dict(at=[XB1 + 0.35, 24.6, DECK + 0.01], size=[12, 4]), "Floor register in the loft.")
for k, x in enumerate([31.7, 37.7]):
    supply(f"s_family{k+1}", "Entry / family", 112, 7, drop(bay(x), YS, 35.0), dict(at=[bay(x), 35.1, ZT], size=[14, 6], wall=S), "Runs in the loft floor to a high sidewall register.")
supply("s_bed1", "Bedroom 1", 138, 8, [[40.4, YE - 0.6, 11.0], [40.4, 14.95, 11.0]], dict(at=[40.4, 14.97, 11.0], size=[14, 8], wall=N), "High sidewall register through the attic wall.")

# ------------------------------------------------------------------ returns
# Main: Andy's M-10 return, a 34 x 10 grille high on the hall 1 west wall. Behind it a boot box sits in one truss bay
# (parallel to the trusses, so it fits), rises straight up through the deck, and a 34 x 10 trunk on the deck runs to the
# return plenum at the heat pump.
# Bedrooms: low grilles with a stack up the stud bay into the trusses, then round flex. Flex runs north to south in a bay
# where it can, and crosses the trusses only at 7 in or less, through the web openings. Every run ends at the return
# plenum box on the deck at the heat pump.
DK = DECK + 5 / 12                                # centre of a 10 in tall duct lying on the deck
LOW = 1.0                                         # centre of a low return grille, 8 in tall, its bottom 8 in above the floor
STK = [14, 2.5]                                   # wall stack: 14 x 2-1/2 in, kept inside a 3-1/2 in stud bay (w runs along plan x)
YP = 25.5                                         # where the bedroom flex rises into the return plenum box
PZ = DECK + 1.0                                   # centre of the 24 in tall plenum box on the deck
def ret(id, name, size, points, grilles=None, note=None, info_of=None, model=None, flex=False):
    d = dict(id=id, name=name, category="HVAC return duct", system="hvac.return", type="return", points=points)
    if isinstance(size, (int, float)):
        d.update(shape="round", size=size)
        if flex: d["flex"] = True
    else: d.update(shape="rect", size=size)
    if info_of: d["info_of"] = info_of
    else: d["info"] = dict(model=model or (f"{size} in round flex" if flex else f"{size[0]} x {size[1]} in"), notes=[note] if note else [])
    if grilles: d["grilles"] = grilles
    ducts.append(d)
    return d

def stack(id, x, y, info_of, size=STK):           # a return stack from a low grille up the stud bay into the truss space
    ret(id, None, size, [[x, y, LOW - 0.33], [x, y, ZT]], info_of=info_of)

def bend(pts, r=0.55):
    """Flex duct does not turn sharp corners: round every corner off with a short arc of radius about r ft."""
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u = [b[i] - a[i] for i in range(3)]; v = [c[i] - b[i] for i in range(3)]
        lu = sum(t * t for t in u) ** 0.5; lv = sum(t * t for t in v) ** 0.5
        if lu < 1e-6 or lv < 1e-6:
            continue
        k = min(r, lu / 2, lv / 2)
        p0 = [b[i] - u[i] / lu * k for i in range(3)]; p2 = [b[i] + v[i] / lv * k for i in range(3)]
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):            # quadratic Bezier through the corner
            out.append([round((1 - t) ** 2 * p0[i] + 2 * (1 - t) * t * b[i] + t * t * p2[i], 3) for i in range(3)])
    out.append(pts[-1])
    return out

RFLEX = ("Round flex duct: a rectangular duct cannot pass through open web floor trusses, and 11-7/8 in trusses leave about 8-7/8 in between the chords. "
         "Runs that go north to south lie in one truss bay, parallel to the trusses, where a bigger round fits. Runs that cross the trusses go through "
         "the web openings at 7 in or less. For reference, SBCA's floor truss guidance lists about 5-5/8 in round through the end panel of a 12 in deep "
         "truss and 7 to 8 in through the larger interior panels, so the truss maker should confirm the opening sizes on the truss drawings, or build a "
         "duct chase where these runs cross. Flex is fine for returns inside the conditioned envelope if it is pulled tight with gentle bends. Sizes are ASSUMED "
         "until Andy or the HVAC installer sizes them.")

ret("return_main", "Main return (M-10)", [34, 10], [[11.95, 30.6, ZT], [10.95, 30.6, ZT]],
    grilles=[dict(at=[12.15, 30.6, ZT], size=[34, 10], wall="E")])
ducts[-1]["info"] = dict(model="34 x 10 in grille and trunk, 1,368 CFM system (M-10)",
    specs=[["Serves", "Living, kitchen, dining, family and the halls, plus any room on transfer grilles"], ["Grille", "34 x 10 in, hall 1 (M-10)"],
           ["Boot", "34 x 10 in box in one truss bay over the powder room, parallel to the trusses"], ["Trunk", "34 x 10 in on the attic deck (M-10)"]],
    notes=["Andy's M-10 return: one 34 x 10 grille in hall 1 and a 34 x 10 return trunk over the utility, pantry and powder rooms to HP-01. "
           "The grille sits high on the hall 1 wall above the powder room door. Behind it a boot box sits inside one truss bay, so nothing crosses the trusses, "
           "and rises straight up through the deck. The trunk runs on the deck from there to the return plenum. Route on the deck is ASSUMED to suit the heat pump position in this model."])
XMR = 11.45
ret("return_main_riser", None, [14, 30], [[XMR, 30.6, ZT], [XMR, 30.6, DK]], info_of="return_main")
ret("return_main_deck", None, [34, 10], [[XMR, 30.6, DK], [5.2, 30.6, DK], [5.2, 26.0, DK]], info_of="return_main")
ret("return_plenum", "Return plenum box", [14, 24], [[3.62, 25.51, PZ], [11.85, 25.51, PZ]],
    model="14 x 24 in return plenum box on the deck, against the heat pump's filter rack",
    note="Every return lands here: the M-10 trunk from the south, and the bedroom flex runs from below, each through its own collar in the bottom of the box. "
         "The box sits on the deck against the AFR1836A filter rack on the heat pump's return side. Size ASSUMED.")

# Bedrooms 2 and 3 (Maxwell, 11/17/2026): bedroom 3's grille moved from beside the bed to its north wall. Both grilles are in
# the wall the two rooms share, in neighbouring stud bays, and both stacks rise into the trusses over bedroom 3, where they join.
XR3, XR2 = bay(7.7), bay(9.7)
r = ret("return_bed23", "Bedrooms 2 and 3 return", 10, bend([[XR3, 10.85, ZT], [XR3, YP, ZT], [XR3, YP, DECK + 0.2]]), flex=True,
        grilles=[dict(at=[XR3, 11.02, LOW], size=[14, 8], wall=S)])
r["info"]["specs"] = [["Serves", "Bedroom 3 (low grille on its north wall) and bedroom 2 (low grille on its south wall)"],
                      ["Duct", "14 x 2-1/2 in wall stacks, 7 in flex from bedroom 2 through one truss, 10 in flex south in one truss bay to the plenum"],
                      ["Crosses", "One truss, at 7 in. No supply runs"]]
r["info"]["notes"] = ["Bedroom 3's grille moved from its south wall, next to the bed, to its north wall (Maxwell, 11/17/2026). It shares that wall with bedroom 2, "
                      "so the two stacks rise side by side into the trusses over bedroom 3 and join there: bedroom 2's 7 in flex crosses one truss into bedroom 3's bay and "
                      "tees into a 10 in flex that runs south in that bay, parallel to the trusses, to the return plenum box at the heat pump.", RFLEX]
stack("return_bed3_stack", XR3, 10.8, "return_bed23")
ret("return_bed2", None, 7, bend([[XR2, 10.85, ZT], [XR2, 11.9, ZT], [XR3 + 0.3, 12.7, ZT], [XR3, 13.2, ZT]], 0.4), flex=True,
    grilles=[dict(at=[XR2, 10.64, LOW], size=[14, 8], wall=N)], info_of="return_bed23")
stack("return_bed2_stack", XR2, 10.8, "return_bed23")

# Study and bedroom 1: one 7 in flex home run each. They come down side by side in one hall 2 bay, cross the laundry and
# linen trusses west (the study's run first, further north, so the two never cross), and drop south in their own bays to the plenum.
XSB, XB1R = bay(25.7), bay(29.7)
YSW, YBW = 19.6, 20.3
r = ret("return_study", "Study and bedroom 1 returns", 7,
        bend([[XSB, 10.85, ZT], [XSB - 0.35, 11.4, ZT], [XSB - 0.35, YSW, ZT], [XR2, YSW, ZT], [XR2, YP, ZT], [XR2, YP, DECK + 0.2]]), flex=True,
        grilles=[dict(at=[XSB, 10.64, LOW], size=[14, 8], wall=N)])
r["info"]["specs"] = [["Serves", "Study (low grille on its south wall) and bedroom 1 (low grille on its south wall, beside the door)"],
                      ["Duct", "14 x 2-1/2 in wall stacks, one 7 in flex home run per room to the return plenum box"],
                      ["Crosses", "The laundry, linen and bedroom 3 trusses at 7 in. No supply runs, and they stay in the trusses, off the tall south part of the attic"]]
r["info"]["notes"] = ["The study and bedroom 1 have low grilles (Maxwell, 11/17/2026) with a stack up the stud bay into the trusses. Each room gets its own 7 in flex "
                      "back to the plenum, because one duct big enough for both would not fit through the truss webs.",
                      "A 7 in flex carries roughly 90 to 100 CFM at return duct friction, a little under bedroom 1's 138 CFM supply. Andy may want a second run "
                      "or a bigger chase for bedroom 1.", RFLEX]
stack("return_study_stack", XSB, 10.8, "return_study")
ret("return_bed1", None, 7, bend([[XB1R, 15.3, ZT], [XB1R, 15.75, ZT], [XSB + 0.35, 15.75, ZT], [XSB + 0.35, YBW, ZT], [bay(11.7) - 0.2, YBW, ZT],
                                  [bay(11.7) - 0.2, YP, ZT], [bay(11.7) - 0.2, YP, DECK + 0.2]]), flex=True,
    grilles=[dict(at=[XB1R, 15.01, LOW], size=[14, 8], wall=N)], info_of="return_study")
stack("return_bed1_stack", XB1R, 15.26, "return_study")

# Bath exhaust (Maxwell, 11/17/2026): ceiling or high wall grilles in bath 1, bath 2 and the powder room, ducted to the ERV's stale air inlet
# instead of separate fans. The run hugs the supply trunk's south side on the deck so it stays in the low, north part of the attic.
ERV_Z = DECK + 0.05 + 5.7 / 12                    # centre of the ERV's duct adapters
ERV_F = 0.75 + 26.6 / 12                          # the ERV's room end
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
XE1 = bay(39.7)
exhaust("ex_bath1", "Bath 1 exhaust", 4, [[XE1, 30.0, ZT], [XE1, 17.8, ZT], [XE1, 17.8, EX]], room="Bath 1",
        grilles=[dict(at=[XE1, 30.0, CEIL - 0.02], size=[10, 10])], note=ENOTE + " Runs north in one loft floor truss bay, east of the family supply drop, then up onto the deck.")
exhaust("ex_bath2", "Bath 2 exhaust", 4, [[19.8, 10.62, 11.7], [19.8, 13.5, 11.7], [19.8, 13.5, EX]], room="Bath 2",
        grilles=[dict(at=[19.8, 10.6, 11.7], size=[10, 6], wall=N)], note=ENOTE + " High on the bath 2 wall through the attic wall, over the supply trunk.")
exhaust("ex_powder", "Powder exhaust", 4, [[10.2, 31.3, ZT], [3.3, 31.3, ZT], [3.3, 31.3, EX], [3.3, 29.32, EX]], room="Powder",
        grilles=[dict(at=[10.2, 31.3, CEIL - 0.02], size=[8, 8])], note=ENOTE + " Runs west through the pantry truss webs, then up to the ERV.")
exhaust("ex_main", "Bath exhaust main", 6, [[XE1, 17.8, EX], [25.6, 17.8, EX], [25.6, 13.5, EX], [3.3, 13.5, EX], [3.3, 29.32, EX], [ERV_F, 29.32, ERV_Z]],
        note="Collects the three bathroom exhausts on the attic deck along the south side of the supply trunk and down the west side to the ERV stale air inlet. ASSUMED route and size.")
# Range hood (Maxwell, 11/17/2026): quiet inside, so the fan is as far from the kitchen as it can be, on the roof, and a
# silencer sits in the duct between the hood and the fan. The hood is a liner or insert with no blower of its own. The duct
# rises inside the chimney cover, through the 10-1/4 in SIP roof, to a low profile exterior blower on a curb, so nothing sticks
# out of the west wall. IRC M1503: its own duct to the outdoors, smooth metal, a backdraft damper. 400 CFM or less is assumed,
# because more needs makeup air (M1503.6).
RF = CFG["roof"]
def roof_top(y):                                   # top of the low (south) roof, standing seam included, at y
    return RF["south_wall_height"] + (CFG["house"]["depth_y"] - y) * RF["south_pitch"] / 12 + RF["panel_thickness"] * (1 + (RF["south_pitch"] / 12) ** 2) ** 0.5 + 0.08
HX, HY = CFG["house"]["ext_wall_thickness"] + 0.6, 47.0   # centre of the hood chimney (14-3/8 in deep off the west wall)
HOOD_TOP, SIL_Z0, SIL_L = 6.35, 7.4, 36
RT = roof_top(HY)
HNOTE = ("Hood not picked yet. It needs to be a liner or insert sold for a remote blower (no fan inside the hood), 400 CFM or less ASSUMED so no makeup air is "
         "required. The chimney cover is drawn 14-3/8 in square so the silencer fits inside it; a stock chimney is usually narrower, so it may need to be a custom "
         "or extended cover.")
exhaust("ex_hood", "Range hood duct", 8, [[HX, HY, HOOD_TOP + 0.02], [HX, HY, RT + 0.15]], room="Kitchen",
        note="8 in smooth galvanized duct straight up inside the hood's chimney cover, through the roof to the roof mounted blower. One straight run with no elbows "
             "is the quietest and moves the most air. A range hood may not connect to the ERV or the return: IRC M1503 (adopted in the Ohio residential code) requires "
             "its own duct to the outdoors. The blower's own gravity damper closes it when off; an insulated backdraft damper at the hood is worth adding in a house this tight. " + HNOTE)
ducts[-1]["info"]["specs"] = [["Duct", "8 in round, smooth galvanized"], ["Fan", "Exterior roof blower, about 11 ft above the cooktop"], ["Silencer", "In the chimney cover, between the hood and the fan"]]
items += [
 dict(id="hood_silencer", name="Range hood duct silencer", category="Ventilation", system="hvac.exhaust", room="Kitchen", layer="mechanical",
      builder="silencer", size=[12, SIL_L], at=[HX, HY, SIL_Z0], facing=90,
      info=dict(model="Fantech LD 8 round duct silencer, or similar (ASSUMED)",
        specs=[["Duct", "8 in, galvanized, perforated liner with about 2 in of acoustic lining"], ["Size", "About 12 in outside, 3 ft long (approximate)"]],
        notes=["A duct muffler: it soaks up fan noise travelling down the duct with very little added resistance. Fantech's kitchen guidance puts it between the hood and the fan, "
               "in any orientation, and puts the fan as far from the hood as possible.",
               "Hidden inside the hood's chimney cover. Use no clip or the slice slider to see it.", HNOTE],
        placement="Inside the hood's chimney cover, above the hood.")),
 dict(id="hood_blower", name="Range hood roof blower", category="Ventilation", system="hvac.exhaust", room="Roof", layer="mechanical",
      builder="roof_blower", size=[22, 13, 22], at=[HX, HY, RT], facing=0,
      info=dict(model="Low profile exterior roof blower for range hoods, about 400 CFM (ASSUMED), for example Fantech's RE series or the hood maker's own roof blower",
        specs=[["Size", "About 22 x 22 in on its curb, about 13 in tall above the roof (approximate)"], ["Duct", "8 in"], ["Damper", "Built in gravity backdraft damper"],
               ["Control", "Speed from the hood's controls"]],
        notes=["The fan sits outside on the roof, the furthest point from the kitchen, so most of its noise stays outdoors (Maxwell, 11/17/2026). "
               "Replaces the wall cap on the west wall, which stuck out about 9 in.",
               "On a curb flashed into the standing seam roof, just in from the west eave. The roofer and the SIP maker should agree on the curb and the 8 in hole through the panel.", HNOTE],
        placement="Low roof, about 1 ft in from the west wall, straight above the cooktop.")),
]

# ERV ducts. The Intelli-Balance 100 has two 6 in adapters on each end: outdoor air and exhaust air on the wall end,
# stale air in and fresh air out on the room end. The unit lies with its long side east-west so the wall end meets the west wall.
for k, (y, nm) in enumerate([(28.9 - 0.415, "outdoor air in"), (28.9 + 0.415, "exhaust air out")]):
    ducts.append(dict(id=f"erv_wall_{k}", info_of="erv", type="erv", shape="round", size=6, points=[[0.75, y, ERV_Z], [-0.05, y, ERV_Z]]))
ducts.append(dict(id="erv_to_return", info_of="erv", type="erv", shape="round", size=6,
                  points=[[ERV_F, 28.485, ERV_Z], [3.1, 28.485, DECK + 0.85], [3.6, 28.485, DECK + 0.85], [3.95, 28.485, ERV_Z]]))

trusses = dict(id="floor_trusses", name="Open web floor trusses", category="Structure", system="structure.floor", regions=FLAT, loft_regions=[LOFT],
    z0=CEIL, depth_in=TRUSS_IN, spacing_in=CFG["floor_trusses"]["spacing_in"], deck_in=DECK_IN, grid_x0=TG,
    info=dict(model="11-7/8 in open web floor trusses",
      specs=[["Depth", "11-7/8 in (Maxwell, 11/16/2026)"], ["Clear for ducts", "About 8-7/8 in between the chords"], ["Floor top", f"{DECK:.2f} ft above the slab with 3/4 in decking"],
             ["Spacing", "24 in on centre on one grid across the house, ASSUMED"], ["Span", "North to south, continuous over the interior walls, ASSUMED"]],
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
