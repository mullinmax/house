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
               "Size and cutout from the Lowe's listing. Confirm against the Frigidaire installation guide before the cabinets are ordered.",
               "Erin's list (11/17/2026) has this at $2,199 as GCWD3067AD. The AD suffix is the black stainless finish ($2,799 at Lowe's); the AF modelled here is the stainless one the list's link points to."],
        links=[["Lowe's product page", "https://www.lowes.com/pd/Frigidaire-30-in-Self-cleaning-Air-Fry-Single-fan-European-Element-Double-Electric-Wall-Oven-Smudge-proof-Stainless-Steel/5013113761"]],
        placement="West wall oven tower, per the cabinet plan.")),
 dict(id="cooktop", name="LG smart induction cooktop", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="cooktop_induction", size=[30.69, 3.69, 21.06], at=[0.74, 47.0, 3.0], facing=90,
      cull=[dict(box=[0.5, 45.4, 3.05, 2.9, 48.6, 3.35], materials=["Black Glass"])],
      info=dict(model="LG CBIH3013BE, 30 in smart induction cooktop, 4 elements, black ceramic glass", price="$999 at LG on 11/17/2026 ($899 on Erin's list)",
        specs=[["Size", "30 11/16 W x 21 1/16 D x 3 11/16 H in"], ["Cutout", "28 1/2 W x 19 5/8 D in, 5 3/4 in deep"],
               ["Elements", "Centre 10 in 2,400 W (4,300 boost), left front 7 in 2,100 W (3,200 boost), left rear and right front 6 in 1,300 W (1,800 boost)"],
               ["Power", "240/208 V, 29.6 A at 240 V"], ["Weight", "35.7 lb"], ["Features", "ThinQ app, touch controls with a boost level on every element"]],
        notes=["From Erin's list (11/17/2026), replacing the KitchenAid KCIT730SBL.",
               "The cutout is 1 in narrower and about 0.8 in shallower than the KitchenAid's (29.5 x 20.44 in), so tell the countertop fabricator. Size, cutout and element ratings are from LG's spec sheet, which does not state a breaker size: confirm that with the installation guide."],
        links=[["LG product page", "https://www.lg.com/us/cooking-appliances/lg-cbih3013be"]],
        placement="West counter run, centred on the cooktop bay in the cabinet plan.")),
 dict(id="fridge", name="Frigidaire Gallery counter depth French door fridge", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="fridge_french_door", size=[36, 70, 30.8], at=[5.475, 35.2, 0], facing=180,
      cull=[dict(box=[3.96, 35.1, 0, 6.99, 37.75, 5.99], materials=["Stainless", "Black Glass", "Appliance Interior", "Brushed Nickel"])],
      info=dict(model="Frigidaire Gallery GRFC2353AF, 36 in counter depth French door, 22.6 cu ft", price="$2,899 at Lowe's on 11/17/2026 (list $3,299)",
        specs=[["Size", "36 W x 70 H x 30.8 D in with handles"], ["Depth", "28.5 in without handles, 23.6 in without doors"], ["Capacity", "22.6 cu ft"],
               ["Doors", "Two French doors over a bottom freezer drawer"], ["Dispenser", "Water and ice in the left door, dual ice maker"],
               ["Finish", "Fingerprint resistant stainless steel"], ["Weight", "334 lb"]],
        notes=["From Erin's list (11/17/2026), replacing the Whirlpool WRFC5036RZ. Size from the Lowe's listing.",
               "Erin's note prices the fridge at $1,699 as FRFC2323AS, which is the plain Frigidaire version of this fridge: same 36 x 70 x 30.8 in and 22.6 cu ft, also with a door dispenser, $1,899 at Lowe's on 11/17/2026. The link on the list points to the Gallery GRFC2353AF, so that is what is modelled. Either one fits the same bay.",
               "The fridge bay is 37.8 in wide with 3/4 in panels inside it, which leaves about 36.3 in clear, so this 36 in fridge has under 3/16 in each side. Check the opening width in the Frigidaire install guide with Carter Lumber. It is 1 in shallower than the Whirlpool, so the pantry door beside it has no less room than before."],
        links=[["Lowe's product page (GRFC2353AF)", "https://www.lowes.com/pd/Frigidaire-22-6-Cu-Ft-Counter-Depth-French-Door-Refrigerator/5013011561"],
               ["Lowe's product page (FRFC2323AS)", "https://www.lowes.com/pd/Frigidaire-22-6-cu-ft-Counter-depth-French-Door-Refrigerator-with-Ice-Maker-Stainless-Steel-ENERGY-STAR/5013990507"]],
        placement="North kitchen wall, in the panelled fridge bay.")),
 dict(id="dishwasher", name="Bosch 500 Series dishwasher", category="Kitchen appliance", system="kitchen", room="Kitchen", layer="appliances",
      builder="dishwasher", size=[23.56, 33.88, 23.75], at=[7.25, 51.458, 0.02], facing=0,
      cull=[dict(box=[6.2, 49.2, 0.3, 8.3, 51.46, 3.0], materials=["Stainless"])],
      info=dict(model="Bosch 500 Series SHP65DM5N, 24 in top control, pocket handle, stainless steel", price="$1,129 at Lowe's on 11/17/2026 (list $1,249)",
        specs=[["Size", "23.56 W x 33.88 H x 23.75 D in"], ["Cutout", "24 W x 33.88 H x 24 D in"], ["Noise", "44 dBA"], ["Capacity", "16 place settings"],
               ["Energy", "240 kWh per year"], ["Features", "AutoAir dry, third rack, Zone Wash, Home Connect"]],
        notes=["From Erin's list (11/17/2026). The model number is corrected from SHP65DP5N to SHP65DM5N. The size, energy and capacity figures were not shown on the Lowe's page, so they are carried over from the 500 Series pocket handle spec: confirm them with the Bosch install guide."],
        links=[["Lowe's product page", "https://www.lowes.com/pd/Bosch-500-Series-24-in-Top-Control-Built-In-Pocket-Handle-Dishwasher-in-Stainless-Steel/5016131451"]],
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
      info=dict(model="Hisense HBC164N6SS, 24 in beverage centre", price="$599 at Lowe's on 11/17/2026 (list $899)", specs=[["Size", "23.4 W x 33.9 H x 23.6 D in"], ["Capacity", "5.4 cu ft, about 164 cans"],
               ["Power", "115 V, 0.8 A"], ["Noise", "39 dB"], ["Install", "Built in or freestanding, reversible door"]],
        notes=["Confirmed against Erin's list (11/17/2026)."],
        links=[["Lowe's product page", "https://www.lowes.com/pd/Hisense-23-43-in-W-Smart-140-Can-Capacity-Stainless-Steel-Built-In-Freestanding-Beverage-Refrigerator-with-Glass-Door/5015197291"]],
        placement="Under the island, facing the dining room.")),
]

# ------------------------------------------------------------------ laundry
items += [
 dict(id="washer_dryer", name="GE Profile UltraFast Combo washer dryer", category="Laundry appliance", system="laundry", room="Laundry", layer="appliances",
      builder="front_load_laundry", size=[28, 46.7, 32], at=[27.45, 22.36, 0], facing=0, finish="graphite", kind_ring="dark", replaces_nodes=["washer", "dryer"],
      cull=[dict(box=[24.95, 19.7, 0.0, 29.95, 22.45, 3.3], materials=["Enamel White", "Plastic Grey", "Aluminum", "Black Glass", "Glass"])],   # the baked pair, merged into per material meshes
      info=dict(model="GE Profile PFQ97HSPVDS UltraFast Combo, 4.8 cu ft all in one washer dryer, Carbon Graphite", price="$2,099 at Lowe's on 11/17/2026 (list $2,999; $1,994.05 on Erin's list)",
        specs=[["Size", "28 W x 46 7/10 H x 32 D in"], ["Capacity", "4.8 cu ft, washes and dries in one drum"], ["Drying", "Ventless heat pump, no dryer vent"],
               ["Power", "120 V, 11 A, on its own 15 A circuit, outlet within 36 in of the cord entry"],
               ["Water", "Hot and cold valves 36 1/4 in above the floor, drain hose standpipe"], ["Clearance", "0 in sides and top, 1/2 in each side suggested"], ["Weight", "302 lb"]],
        notes=["One combo unit replaces the separate washer and dryer (Maxwell, 11/17/2026). Lowe's lists this listing as model PFQ97HSPVDS.",
               "Size from AJ Madison and the GE spec sheet. It is 7 1/2 in taller than a standard front loader, so check any counter or shelf planned above it."],
        links=[["Lowe's product page", "https://www.lowes.com/pd/GE-Profile-UltraFast-Combo-4-8-cu-ft-Ventless-All-In-One-Washer-Dryer-Combo-Carbon-Graphite/5014255941"]],
        placement="Laundry south wall, centred where the washer and dryer pair stood.")),
]

# Laundry sink and linen shelves (Maxwell, 11/20/2026: "a sink and shelves on the west wall", from the original drawings).
# A-11 draws the sink at the west end of the south wall, right against the hall closet, and 3'-0" x 2'-0" B&W cabinets on the
# west wall of the alcove north of that closet (inside x 16.664 to 20.039, y 15.491 to 18.574). The sheet's fixture schedule
# (item 9) names the sink: Steelton 36 in, 16 gauge stainless, one compartment utility sink #522US13621 with a 12 in swing spout
# faucet #190FW812. Maxwell asked for open shelves of linens there instead of cabinets.
LS_X0, LS_Y0, LS_Y1 = 16.664, 15.491, 18.574            # alcove west wall face, north wall face, closet north wall face
SINK_W, SINK_D, SINK_H = 40, 25.5, 44                    # overall, in (Steelton family size for the 36 x 21 x 14 bowl, ASSUMED)
SINK_GAP = 2.5 / 12                                      # stands 2 1/2 in off the wall: supplies and the vent riser go up behind it
SINK_X = 20.039 + (SINK_W / 2 + 0.5) / 12                # west leg 1/2 in off the hall closet wall
SINK_BACK = 22.408 - SINK_GAP                            # laundry south wall face is y 22.408
SUP_Y = 22.408 - 1.25 / 12                               # supplies 1 1/4 in off the wall
items += [
 dict(id="laundry_sink", name="Laundry utility sink", category="Plumbing fixture", system="plumbing", room="Laundry", layer="appliances",
      builder="utility_sink", size=[SINK_W, SINK_H, SINK_D], at=[round(SINK_X, 3), round(SINK_BACK, 4), 0], facing=0,
      info=dict(model="Steelton 522US13621 one compartment utility sink, 16 gauge stainless, 36 x 21 x 14 in bowl, with a 12 in swing spout faucet (190FW812)",
        specs=[["Bowl", "36 W x 21 front to back x 14 deep in"], ["Overall", "About 40 W x 25 1/2 D x 44 H in to the top of the 8 in backsplash (ASSUMED from the Steelton family)"],
               ["Rim", "36 in up"], ["Faucet", "8 in centres through the backsplash, 12 in swing spout over the bowl"],
               ["Water", "Hot and cold 1/2 in PEX up through the slab behind the sink, quarter turn stops about 18 in up"],
               ["Drain", "1 1/2 in trap into a 2 in riser behind the sink, air admittance valve on top of the riser"]],
        notes=["Drawn on A-11 at the west end of the laundry's south wall, against the hall closet, and named in the plumbing fixture schedule (item 9) "
               "of the sealed set. Added at Maxwell's request (11/20/2026).",
               "The hot and cold are assumed to come under the slab from the utility room, where the house hot and cold go down into the slab, about 20 ft. "
               "The drain ties into the building drain under the slab. The air admittance valve stands in for a vent through the wall; the plumber may run a real vent up the wall instead.",
               "The combo washer dryer's own valves and standpipe are not drawn yet; its drain can share this riser."],
        links=[["Steelton sink at WebstaurantStore", "https://www.webstaurantstore.com/steelton-36-16-gauge-stainless-steel-one-compartment-commercial-utility-sink-36-x-21-x-14-bowl/522US13621.html"]],
        placement="Laundry south wall at the west end, against the hall closet, where A-11 draws it. The faucet is on the backsplash, so nothing is in the wall the Dyson hangs on.")),
 dict(id="linen_shelves", name="Linen shelves", category="Storage", system="household", room="Laundry", layer="storage",
      builder="linen_shelves", size=[round((LS_Y1 - LS_Y0) * 12 - 0.1, 2), 90, 24], at=[LS_X0, round((LS_Y0 + LS_Y1) / 2, 4), 0], facing=90,
      shelves=[[7, 24, 0.75], [21, 24, 0.75], [37, 24, 1.25], [53, 15, 0.75], [68, 15, 0.75], [83, 15, 0.75]],
      info=dict(model="Open white oak shelves on cleats, wall to wall in the alcove (ASSUMED build)",
        specs=[["Width", "3 ft 1 in, wall to wall"], ["Shelves", "7, 21 and 37 in up at 24 in deep; 53, 68 and 83 in up at 15 in deep"],
               ["Folding shelf", "The 37 in shelf is 1 1/4 in thick and kept clear for folding; the U-11 outlet at 42 in sits just above it"],
               ["Stocked with", "Throws in baskets, folded blankets, bath and hand towels, sheet sets, spare pillows and a comforter, for scale"]],
        notes=["A-11 draws 3'-0\" x 2'-0\" B&W cabinets on this wall. Maxwell asked for shelves with towels, sheets and blankets instead (11/20/2026).",
               "The upper shelves are shallower so they do not catch your head while you work at the folding shelf."],
        placement="West wall of the laundry's alcove, north of the hall closet, left of the door as you come in from hall 2.")),
]
# ------------------------------------------------------------------ pantry: chest freezer and what is on the shelves
# Maxwell 11/20/2026: a chest freezer he owns at the back of the pantry, 24.5 in deep x 33 in tall x 21.5 in wide, the lid hinging
# up on a 24.5 in side. Its long side runs along the back (north) wall with the hinge at the wall, so it opens like any chest
# freezer from the aisle. The shelves are in the house (make_house.py); the food on them is in Belongings for scale.
PA = CFG["pantry"]
PX0, PX1, PY0, PY1 = PA["inside"]
FZ_W, FZ_H, FZ_D = PA["freezer_size"]
FZ_BACK = PY0 + PA["freezer_gap_in"] / 12
PL = PA["layouts"][PA["layout"]]
FZ_WHERE = {"right": "Back left corner of the pantry, 1 in off the left wall, front facing the doorway; the shelves are on the right and above it.",
            "u": "Back (north) wall of the pantry, centred between the shelves, front facing the doorway."}[PA["layout"]]
items += [
 dict(id="chest_freezer", name="Chest freezer", category="Kitchen appliance", system="kitchen", room="Pantry", layer="appliances",
      builder="chest_freezer", size=[FZ_W, FZ_H, FZ_D], at=[PL["freezer_x"], round(FZ_BACK, 4), 0], facing=180, lid_open=80,
      info=dict(model="Chest freezer Maxwell already owns (make and model not recorded yet)",
        specs=[["Size", f"{FZ_W} W x {FZ_H} H x {FZ_D} D in"], ["Lid", "Hinged along the 24.5 in back edge, lifts up toward the wall (E or a tap opens it)"],
               ["Clearance", f"{PA['freezer_gap_in']} in off the back wall for the hinges and the condenser"],
               ["Power", "Plugs into the U-11 outlet on the back wall, 41 3/4 in up at x 3.06"],
               ["Open lid", f"Top edge about {round(FZ_H + FZ_D * 0.985)} in up; the back wall shelves start at 64 in"]],
        notes=["Added at Maxwell's request (11/20/2026). The look is a generic white chest freezer; send the model number to get its real details."],
        placement=FZ_WHERE)),
 dict(id="pantry_goods", name="Pantry food and supplies", category="Storage", system="household", room="Pantry", layer="storage",
      builder="pantry_goods", size=[1, 1, 1], at=[PX0, PY0, 0], facing=180,
      shelves=[dict(wall=r["wall"], face=round({"W": PX0, "E": PX1, "N": PY0}[r["wall"]], 4), run=r["run"], depth=r["depth"], tops=r["tops"], kinds=r["kinds"])
               for r in PL["shelves"]],
      info=dict(model="Everyday pantry goods, for scale",
        specs=[["Stocked with", "25 lb flour and 20 lb rice bags, a case of water, a potato bin, 5 lb flour and 4 lb sugar bags, canned goods, jars of pasta, beans and grains, cereal and pasta boxes, a stand mixer, paper towels"]],
        notes=["Belongings only: they give the shelves a sense of scale (Maxwell, 11/20/2026)."],
        placement="On the pantry shelves.")),
]

# ------------------------------------------------------------------ garage: the cars and the charger
# Both cars park nose in (facing north). The Model Y takes the east bay: its charge port is at the left rear, so it
# ends up beside the Wall Connector on the pier between the doors. Rear bumpers sit 3 ft inside the doors. ASSUMED.
GA = CFG["garage"]
GX0, GY0, GX1, GY1 = GA["rect"]
G_IN = GY1 - 0.5                                   # inside face of the garage's south wall
G_FLOOR = -0.05                                    # garage slab top, an inch below the house slab
bay = [GX0 + s0 + w / 2 for s0, w in GA["overhead_doors"]]
pier = (GX0 + GA["overhead_doors"][0][0] + GA["overhead_doors"][0][1] + GX0 + GA["overhead_doors"][1][0]) / 2
REAR_Y = G_IN - 3.0
items += [
 dict(id="car_model_y", name="Tesla Model Y", category="Car", system="vehicles", room="Garage", layer="vehicles",
      builder="car", car="model_y", size=[75.6, 63.9, 187.0], at=[round(bay[1], 3), round(REAR_Y, 3), G_FLOOR], facing=0,
      info=dict(model="Tesla Model Y, 2020 to 2024, Solid Black",
        specs=[["Size", "187.0 L x 75.6 W x 63.9 H in (83.8 in wide with mirrors, 77.9 in folded)"], ["Wheelbase", "113.8 in"], ["Track", "64.4 in"],
               ["Ground clearance", "6.6 in"], ["Tyres", "255/45 R19 on 19 in Gemini wheels with aero covers"], ["Charge port", "Left rear"]],
        notes=["The original 2020 to 2024 body (Maxwell, 11/17/2026). Dimensions from the 2023 and 2024 Model Y Long Range listings on evspecifications.com and carexpert.co.nz. The body curves between those numbers are drawn from photos, so they are close but not surveyed.",
               "Parked nose in, in the east bay, so the charge port on the left rear lands about 2 ft from the Wall Connector."],
        placement=f"East garage bay, centred on the door, rear bumper 3 ft inside the door. ASSUMED.")),
 dict(id="car_insight", name="Honda Insight", category="Car", system="vehicles", room="Garage", layer="vehicles",
      builder="car", car="insight", size=[71.6, 55.6, 183.6], at=[round(bay[0], 3), round(REAR_Y, 3), G_FLOOR], facing=0,
      info=dict(model="Honda Insight, 2019 to 2022 hybrid sedan, Touring, Crystal Black Pearl",
        specs=[["Size", "183.6 L x 71.6 W x 55.6 H in"], ["Wheelbase", "106.3 in"], ["Track", "60.9 in front, 61.6 in rear"],
               ["Tyres", "215/50 R17 (Touring; the EX has 215/55 R16)"], ["Curb weight", "3,078 lb (Touring)"]],
        links=[["2022 Insight specifications", "https://www.hondainfocenter.com/2022/Insight/Feature-Guide/Specifications/"]],
        notes=["Dimensions from Honda's 2022 Insight specifications. The trim is ASSUMED to be the Touring, for its 17 in two tone wheels.",
               "The body curves between those numbers are drawn from photos, so they are close but not surveyed."],
        placement="West garage bay, centred on the door, rear bumper 3 ft inside the door. ASSUMED.")),
 dict(id="wall_connector", name="Tesla Universal Wall Connector", category="EV charger", system="electrical.ev", room="Garage", layer="appliances",
      builder="wall_connector", size=[6.1, 13.6, 5.9], at=[round(pier, 3), G_IN, 1.5], facing=0,
      info=dict(model="Tesla Universal Wall Connector, NACS handle with a built in J1772 adapter", price="$720 at the Tesla shop (out of stock on 11/17/2026)",
        specs=[["Size", "13.6 H x 6.1 W x 5.9 D in, about 13 lb"], ["Output", "12 to 48 A at 208 to 240 V, up to 11.5 kW"],
               ["Circuit", "48 A needs a 60 A breaker"], ["Cable", "24 ft"], ["Enclosure", "Type 3R, IP54, indoor or outdoor"], ["Network", "Wi-Fi 2.4 GHz"]],
        links=[["Tesla shop", "https://shop.tesla.com/product/universal-wall-connector"],
               ["Product specifications", "https://energylibrary.tesla.com/docs/Public/Charging/WallConnector/Gen3/Install/UniversalWC/en-us/GUID-4A3BDFAA-7DBB-48CB-852C-BF1473EC4945.html"]],
        notes=["Size, output and cable from Tesla's install manual. The 60 A breaker follows the usual 125 percent rule for a 48 A continuous load; confirm with the electrician.",
               "Tesla's shop notes that a Model Y draws at most 32 A (7.7 kW) from this unit.",
               "Unit face about 3'-7\" to 4'-7\" above the floor. The wall holster and cable hook are ASSUMED accessories."],
        placement="Inside face of the garage south wall, on the 3 ft pier between the two overhead doors.")),
]

# ------------------------------------------------------------------ utility room: geothermal and hot water
# The utility room's walls as traced from A-11 (the room list rounds the south one to 29.03, which is really the powder room side).
UW, UN, US, UE = 0.497, 22.866, 28.241, 11.664    # inside faces: west, north, south, east
# Geothermal: the five loops come up through the slab in one sleeve at the north wall, about 1-1/2 ft east of the west wall
# (Maxwell, 11/19/2026, measured on site; it was drawn at 2 ft), fan out to the manifolds on the west wall, and the flow center sits further south on the same wall,
# right under the heat pump's water connections in the attic.
CON_X, CON_Y = UW + 1.5, UN + 0.32
MAN_Y, MAN_Z = 24.3, 2.5                           # manifold centre along the wall, and the bottom of its valve legs
MAN_XS, MAN_XR = 0.56 + 2.6 / 12, 0.56 + 5.4 / 12  # supply header on the wall, return header in front of it
MAN_ZS, MAN_ZR = MAN_Z + 26 / 12, MAN_Z + 14 / 12  # header heights
FC_Y, FC_Z = 27.15, 3.0
# Hot water: both tanks stand off the south wall with a 5 in pipe lane behind them. The preheat tank is as far west as it can
# go while leaving 2 ft of working room in front of the flow center (pump swaps, flush hoses, topping up), so the desuperheater
# lines drop down the wall just west of it (Maxwell, 11/18/2026). The water heater is 16 in east of it so the valves, pump and
# mixing valve between the tanks can be reached, and its two ducts rise in the middle of truss bay 7.7.
WH_X, PH_D = 7.7, 22.0
TANK_Y = US - 0.42 + 2 / 12                        # the tanks' back point (the builders put each tank 2 in in front of it)
PH_X = WH_X - ((24.25 + 4) / 24 + 1.0 + (PH_D + 4) / 24)    # preheat tank to the west, drain pans 12 in apart: a 16 in service gap between the tanks
WH_DUCT_X = WH_X
# Heat pump: on the attic deck with its length north to south. Supply leaves the north end, the water, desuperheater and
# electrical connections are on the south end, the return and filter are on the east side, and the service panels face a
# 2 ft aisle along the west wall (exactly 2 ft from the wall face to the cabinet). Seen from the connection end the return is on the right: a right hand return unit.
HP_X, HP_Y = 4.31, 25.235                          # centre of the unit's east (return) face
HP_Z = DECK + 6.5 / 12                             # on a pad: the EZ-Trap on the condensate drain needs 6-1/2 in of height (GZT manual p.35)
HP_AT = [HP_X, HP_Y, HP_Z]
HP_S, HP_N = HP_Y + 28 / 12, HP_Y - 28 / 12        # south (connection) end and north (supply) end
HP_CX = HP_X - 21.7 / 24                           # centreline of the cabinet
HP_PX = HP_X - 21.7 * 0.3 / 12                     # x of the water connections on the south end
items += [
 dict(id="geo_manifold", name="Geothermal loop manifolds", category="Geothermal", system="geothermal.loop", room="Utility", layer="mechanical",
      builder="pe_manifold", size=[30, 30, 8], at=[0.56, MAN_Y, MAN_Z], facing=90, mirror=True,
      info=dict(model="Geo-Hydro MPE532PS PE manifold set", price="$802.90 (quote MMUL8476-5, special order)",
        specs=[["Mains", "1-1/4 in PE"], ["Circuits", "5 x 3/4 in, each with a 1 in ball valve"], ["Piping", "Reverse return. Greg's summary has supply and return in separate 4 in sweeps with a 36 in radius"],
               ["Loop entry", "One sleeve through the slab at the north wall, about 1-1/2 ft east of the west wall. The ten pipes fan out from it to the valves"],
               ["Loop field", "5 loops of 3/4 in x 600 ft PE, 103.8 gal system volume"], ["Fluid", "20% propylene glycol (Fernox Alphi-11 with F1 inhibitor)"]],
        notes=["Layout on the wall is ASSUMED. Greg's summary gives the parts and the piping scheme, not a wall elevation.",
               "Raised so the valves sit about 2-1/2 ft off the floor and the loop pipes have room to bend up from the sleeve for fusing (Maxwell, 11/18/2026; Greg asked for the same).",
               "Ten 3/4 in PE pipes are 1.05 in across each, so they need about a 6 in sleeve. A 2 in conduit holds one. Shown as one 6 in sleeve until the size in the slab is confirmed."],
        placement="Northwest corner of the utility room, on the west wall (Maxwell, 11/15/2026).")),
 dict(id="flow_center", name="Geo-Flo flow center", category="Geothermal", system="geothermal.loop", room="Utility", layer="mechanical",
      builder="flow_center", size=[13, 22, 11], at=[0.56, FC_Y, FC_Z], facing=90,
      info=dict(model="Geo-Flo GF-1272 NP2, non pressurized, 2 pumps", price="$1,367.52 (quote MMUL8476-5)",
        specs=[["Pumps", "Two circulators"], ["Connections", "GF-2911 Flo-Link fusion set, 1-1/4 in"], ["Location", "First floor, per Greg's design summary"]],
        notes=[APPROX, "Service: 2 ft of open floor in front for swapping a pump or hooking up flush hoses, and its fill cap on top is about 5 ft off the floor with nothing over it. "
                      "Geo-Flo gives no clearance numbers; it says only to check the fluid level in the canister, mostly in the first days after a fill. "
                      "OPEN QUESTION for Greg: a non pressurized flow center normally sits level with or above the heat pump, and here the heat pump is about 9 ft above it.",
               "Kept on the west wall, which is an outside wall, so pump hum does not pass into bedroom 3 behind the north wall. "
                      "It sits under the heat pump's water connections, so the insulated lines go straight up and only cross about 3 ft of attic."],
        placement="Utility room west wall, south of the manifolds. 1-1/4 in insulated pipes run from here straight up through the ceiling to the heat pump.")),
 dict(id="water_heater", name="Heat pump water heater", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="hpwh", size=[24.25, 74.2], at=[WH_X, TANK_Y, 0], facing=0, flip=True,
      info=dict(model="Rheem ProTerra 80 gal hybrid with LeakGuard (PROPH80 T2 RH400-SO)", price="$3,467 at US Supply (pickup only, 11/18/2026); check Lowe's and Home Depot",
        specs=[["Tank", "80 gal, 87 gal first hour rating"], ["Efficiency", "UEF 4.07"], ["Size", "24-1/4 in diameter x 74-3/16 in tall, 6 in clear above for the filter"],
               ["Power", "240 V, 30 A, 10 AWG"], ["Air", "Intake and exhaust both ducted to the attic, so the solid utility door needs no louvers"],
               ["Fed by", "The 50 gal desuperheater preheat tank next to it"]],
        links=[["Spec sheet", "https://files.rheem.com/blobazrheem/wp-content/uploads/sites/2/Hybrid-Electric-HPWH-with-LeakGuard-Spec-Sheet.pdf"],
               ["US Supply", "https://www.ussupply.com/80-gal-professional-prestige-proterra-hybrid-electric-heat-pump-4-5kw-amp-ef4-07-2047131.html"],
               ["Research doc", "https://claude.ai/artifact/49L6BApM9Yqx434FQv1fWF"]],
        notes=["Maxwell (11/18/2026): plan for 4 people and err on the big side, keep the utility door solid so the hall stays quiet, use two tanks, and keep a heat pump unit because the house is meant to go off grid.",
               "Sheet U-11 names a Rheem Performance Platinum 50 gal hybrid with a recirculation pump; this is the same family, one size up.",
               "Runner up: A.O. Smith Signature 900 HPS10-80H45DV (45 dBA published, 69 in tall).",
               "Shown with the U-11 details: 2 in drain pan, expansion tank, recirculation pump.", APPROX],
        placement="South wall of the utility room (Maxwell, 11/15/2026), 5 in off the wall so the piping runs behind it. It stands 16 in east of the preheat tank so the valves, the recirculation pump and the mixing valve between the tanks can be reached. Its two ducts rise in one truss bay and come out on the attic deck east of the return plenum.")),
 dict(id="preheat_tank", name="Desuperheater preheat tank", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="storage_tank", size=[PH_D, 59.0], at=[PH_X, TANK_Y, 0], facing=0,
      info=dict(model="Rheem Professional Classic 50 gal electric (PROE50 T2 RH95), elements left unwired", price="$744 at HVACDirect (11/18/2026)",
        specs=[["Tank", "50 gal, no power: only the geothermal desuperheater heats it"], ["Piping", "Cold supply in, preheated water out to the heat pump water heater's cold inlet"],
               ["Desuperheater", "The geo's built in pump pulls from the bottom drain port and returns through a tee at the cold inlet"],
               ["Bypass", "Valves so the heat pump water heater can run on its own"]],
        links=[["HVACDirect", "https://hvacdirect.com/rheem-professional-classic-electric-water-heater-50-gal-tall-240-vac-4500-watt-proe50-t2-rh95.html"]],
        notes=["Two tanks because a desuperheater works best on cold water, and a heat pump tank also heats from the bottom, so in one tank they compete. "
               "Enertech's install guidance says a preheat tank gets the most out of the desuperheater.",
               "The GeoComfort GZT048J11LM1CCS has hot water code 1: desuperheater with a factory installed pump.",
               "Size is ASSUMED (about 22 in x 59 in for a 50 gal tall tank)."],
        placement="South wall of the utility room, as far west as it can go while leaving 2 ft of working room in front of the flow center. The desuperheater lines come down the wall just west of it.")),
]
# ---- geothermal piping. Loop entry sleeve, the ten loop pipes fanning out to the valve legs, the two mains to the flow
# center, then insulated 1-1/4 in lines straight up through the ceiling and deck and a short way across the attic.
runs.append(dict(id="geo_conduit", name="Loop entry sleeve", category="Geothermal", system="geothermal.loop", dia=6.6, mat="condensate",
    points=[[CON_X, CON_Y, 0.0], [CON_X, CON_Y, 0.5]],
    info=dict(model="PVC sleeve through the slab, shown at 6 in",
              specs=[["Carries", "All five loops: ten 3/4 in PE pipes, 1.05 in across each"], ["Where", "North wall, about 1-1/2 ft east of the west wall (Maxwell, 11/19/2026, as built)"]],
              notes=["Size to confirm. Ten of these pipes need about a 6 in sleeve, five fit in a 4 in, and a 2 in conduit holds only one. "
                     "Greg's design summary called for two 4 in sweeps, one for the supplies and one for the returns."])))
for k in range(5):
    xc = CON_X + (k - 2) * 0.1                     # legs further south land further east in the sleeve, so no two pipes cross
    for row, (xl, dy, zt, yc) in enumerate([(MAN_XS, 0.0, 1.35, CON_Y - 0.06), (MAN_XR, 1.4 / 12, 0.9, CON_Y + 0.06)]):
        y = MAN_Y + (-12 + 6 * k) / 12 + dy
        runs.append(dict(id=f"geo_loop_{'sr'[row]}{k + 1}", info_of="geo_manifold", dia=1.05, mat="pe",
                         points=[[xl, y, MAN_Z], [xl, y, zt], [xc, y, zt], [xc, yc, zt], [xc, yc, 0.3]]))
FC_N = FC_Y - 6.9 / 12                             # the loop ports on the flow center's north side line up with the two headers
for k, (x, z) in enumerate([(MAN_XS, MAN_ZS), (MAN_XR, MAN_ZR)]):
    runs.append(dict(id=f"geo_main_{k}", info_of="geo_manifold", dia=1.66, mat="pe", points=[[x, MAN_Y + 1.75, z], [x, FC_N, z]]))
GEO_Y = HP_S + 1.23                                # the lines cross the attic just south of the hose kit
FC_PZ, GX = FC_Z + 19.6 / 12, 1.0                  # flow center's top ports; the risers hug the west wall, west of the supply main in the truss bay
for k, (zc, dy, jog) in enumerate([(17.6, 3.2 / 12, []), (5.6, -3.2 / 12, [1.3])]):
    z, y = HP_Z + zc / 12, FC_Y + dy
    runs.append(dict(id=f"geo_riser_{k}", name="Heat pump source piping", category="Geothermal", system="geothermal.loop", dia=2.4, mat="foam",
        info_of=None if k == 0 else "geo_riser_0",
        points=[[1.5, y, FC_PZ], [1.68, y, FC_PZ], [1.68, y, FC_Z + 2.2], [GX, y, FC_Z + 2.2], [GX, y, z]] + [[x, y, z] for x in jog] +
               [[jog[0] if jog else GX, GEO_Y, z], [HP_PX, GEO_Y, z], [HP_PX, HP_S + 0.97, z]],
        info=dict(model="1-1/4 in PE with Aeroflex elastomeric insulation", specs=[["From", "Flow center in the utility room"], ["To", "Heat pump in the attic, through 1 in ball valves and the GF-1366 rubber hose kit"],
                                                                                    ["Length", "About 6 ft up and 5 ft across the attic, each"], ["Beside them", "The desuperheater lines drop through the deck 3 ft away, at the heat pump's connection end"]],
                  notes=["Straight up the west wall from the flow center, through the ceiling and the attic deck, then across to the heat pump's connection end (Maxwell, 11/18/2026). "
                         "The heat pump was turned so its connections sit right above the flow center. Exact route is set on site."])))

# ---- domestic water. Slab penetrations as built (Maxwell, 11/19/2026): the well line comes up at the south wall about 1-1/2 ft
# off the west wall, right below the loop sleeve on the north wall, and the house hot water lines and the drain come up about
# 1 ft further east on the same wall. Those all land in the open corner west of the preheat tank, so the tanks stay put.
# The well line crosses the room overhead to the pressure tank and the filters on the north wall (the south wall is full of
# tanks, and the flow center needs its 2 ft of floor), and treated cold comes back overhead to the preheat tank and the house.
WR = 24.25 / 24                                    # water heater radius, ft
WH_CY, PH_Y = TANK_Y - (WR * 12 + 2) / 12, TANK_Y - (PH_D / 2 + 2) / 12     # tank centres
WCX = WH_X - (WR * 12 + 2.2) / 12                  # the water heater's side connections face the preheat tank
WC_Y, WHOT_Y = WH_CY + 1.6 / 12, WH_CY - 1.6 / 12  # cold in (low) and hot out (high)
WHOT_Z = (74.2 - 15.5 - 4) / 12
PH_TOP = 59.0 / 12 + 3 / 12                        # top of the preheat tank's brass nipples
GAP_X = WCX - 0.03                                 # the vertical pipes in the gap between the tanks
Y_COLD, Y_WALL = US - 0.39, US - 0.19              # cold line behind the preheat tank; hot and recirculation lines on the wall
Z_COLD, Z_HOT, Z_RC, Z_WELL = 7.4, 7.0, 7.2, 7.9   # overhead levels, all under the 9 ft ceiling and clear of a 6 ft 6 in head
WELL_X = UW + 1.5                                  # well line up through the slab, south wall (Maxwell, 11/19/2026)
HL_X = UW + 2.5                                    # house hot water lines and the drain, 1 ft further east (Maxwell, 11/19/2026)
X_HC, X_HH, X_HR = HL_X - 0.22, HL_X - 0.03, HL_X + 0.15                       # house cold, house hot, recirculation back
X_DR, Y_DR = HL_X + 0.3, US - 0.54                 # floor drain, just in front of the lines
HOT, HOT_R = 1.9, 1.5                              # 3/4 in and 1/2 in copper with pipe insulation, outside diameter
# Well water treatment on the north wall, west to east: UV, carbon, sediment, spin down screen, tank tee, pressure tank.
LN = UN + 0.33                                     # pipe lane on the north wall, through the filter heads
HEAD_Z = 4.4                                       # filter heads (ports) about 4-1/2 ft up, easy to reach for cartridge changes
UV_X, CB_X, SD_X, SP_X = 2.78, 3.5, 4.2, 4.8
TT_X = 5.11                                        # tank tee
PT_D, PT_H = 16.0, 62.0                            # pressure tank, in: a slim tall one keeps the walkway past the tanks about 22 in wide
PT_X = 5.95
PT_CY = UN + (1 + PT_D / 2) / 12
UV_Z, UV_H = 2.55, 42.0
# Stick vacuum (Maxwell, 11/19/2026): moved from the utility room to the hall closet off hall 2 (inside x 16.664 to 19.747, y 18.866 to 22.408,
# door on its west side). It hangs on the closet's back (east) wall, straight across from the door.
VAC_WALL, VAC_Y = 19.747, 20.64                    # back wall inside face, and the dock's centre along it (the door's centre line)
def dhw(id, name, dia, mat, points, model, notes, specs=None, info_of=None, system="plumbing.dhw", category="Hot water"):
    r = dict(id=id, name=name, category=category, system=system, dia=dia, mat=mat, points=points)
    if info_of: r["info_of"] = info_of; r.pop("name")
    else: r["info"] = dict(model=model, specs=specs or [], notes=notes)
    runs.append(r)
def well(id, name, dia, mat, points, model=None, notes=None, specs=None, info_of=None):
    dhw(id, name, dia, mat, points, model, notes, specs, info_of, system="plumbing.well", category="Well water")
# well line: up at the south wall, overhead north, along the north wall and down into the tank tee
well("well_line", "Well water line", 1.32, "pe",
     [[WELL_X, Y_WALL, 0.0], [WELL_X, Y_WALL, Z_WELL], [WELL_X, LN + 0.2, Z_WELL], [TT_X + 0.04, LN + 0.2, Z_WELL], [TT_X + 0.04, LN + 0.2, 1.0]],
     "1 in polyethylene from the submersible pump (Crabtree Drilling)",
     ["Comes up through the slab at the south wall about 1-1/2 ft off the west wall (Maxwell, 11/19/2026). It rises in the corner, crosses the room overhead "
      "at about 8 ft and drops to the tank tee next to the pressure tank, about 17 ft of pipe. Line size is ASSUMED; Crabtree's quote says pipe, wire and fittings are included."],
     specs=[["From", "6 in PVC cased well, estimated 100 ft deep, 1/2 HP submersible pump (Crabtree estimate 2479)"], ["To", "Tank tee at the pressure tank"]])
well("well_tank", None, 1.32, "pe", [[TT_X, LN + 0.1, 1.0], [TT_X, LN + 0.1, 0.25], [TT_X, PT_CY, 0.25], [PT_X - 0.45, PT_CY, 0.25]], info_of="well_line")
well("well_to_filters", "Well water to the filters", 1.1, "copper",
     [[TT_X - 0.04, LN, 1.0], [TT_X - 0.04, LN, HEAD_Z], [SP_X, LN, HEAD_Z]],
     "1 in copper or PEX with full port ball valves",
     ["From the tank tee up the wall into the filter row. A bypass around the filters (three valves) is ASSUMED so water keeps flowing during a cartridge change."])
well("well_f1", None, 1.1, "copper", [[SP_X, LN, HEAD_Z], [SD_X, LN, HEAD_Z]], info_of="well_to_filters")
well("well_f2", None, 1.1, "copper", [[SD_X, LN, HEAD_Z], [CB_X, LN, HEAD_Z]], info_of="well_to_filters")
well("well_f3", None, 1.1, "copper", [[CB_X, LN, HEAD_Z], [CB_X - 0.38, LN, HEAD_Z], [CB_X - 0.38, LN, UV_Z + 4.5 / 12], [UV_X + 0.2, LN, UV_Z + 4.5 / 12]], info_of="well_to_filters")
UV_TOP = UV_Z + UV_H / 12
dhw("dhw_cold", "Treated cold water", 1.1, "copper",
    [[UV_X, LN, UV_TOP - 0.1], [UV_X, LN, Z_COLD], [UV_X, Y_COLD, Z_COLD], [PH_X - 0.3, Y_COLD, Z_COLD], [PH_X - 0.3, PH_Y, Z_COLD], [PH_X - 0.3, PH_Y, PH_TOP]],
    "3/4 in copper", ["Out of the UV sterilizer, up and back across the room overhead to the south wall. One branch goes down through the slab as the house cold supply, "
                      "the other drops into the preheat tank's cold inlet. The desuperheater return tees into that drop. Valves ASSUMED."],
    specs=[["Valves", "Shutoff after the UV, shutoff and union at the preheat tank"], ["Expansion tank", "Hangs from a short stub near the north wall, as U-11 shows"]])
dhw("dhw_cold_house", "Cold water to the house", 1.1, "copper", [[UV_X, Y_COLD, Z_COLD], [X_HC, Y_COLD, Z_COLD], [X_HC, Y_COLD, 0.0]],
    "3/4 in copper to PEX under the slab",
    ["Drops through the slab with the hot lines, about 2-1/2 ft off the west wall. ASSUMED: Maxwell said the hot water lines and the drain come up there; the house cold is "
     "drawn with them until the plumber confirms where it goes."])
dhw("dhw_cold_stub", None, 1.1, "copper", [[UV_X, LN, 6.75], [UV_X + 0.75, LN, 6.75]], None, None, info_of="dhw_cold")
dhw("dhw_preheat", "Preheated water to the heat pump water heater", HOT, "foam",
    [[PH_X + 0.3, PH_Y, PH_TOP], [PH_X + 0.3, PH_Y, 5.5], [GAP_X, WC_Y, 5.5], [GAP_X, WC_Y, 0.75], [WCX, WC_Y, 0.75]],
    "3/4 in copper, insulated", ["Preheat tank hot outlet, across the gap between the tanks and down to the heat pump water heater's low side cold inlet, about 6 ft of pipe. "
                                 "The recirculation return tees in near the bottom. Bypass valves so either tank can be isolated are ASSUMED."])
dhw("dhw_hot", "Hot water to the house", HOT, "foam",
    [[WCX, WHOT_Y, WHOT_Z], [GAP_X, WHOT_Y, WHOT_Z], [GAP_X, WHOT_Y, Z_HOT], [GAP_X, Y_COLD - 0.15, Z_HOT], [X_HH, Y_COLD - 0.15, Z_HOT], [X_HH, Y_WALL, Z_HOT], [X_HH, Y_WALL, 0.0]],
    "3/4 in copper, insulated, to PEX under the slab",
    ["Heat pump water heater high side hot outlet, up through the thermostatic mixing valve, west above the preheat tank and down through the slab "
     "about 2-1/2 ft off the west wall (Maxwell, 11/19/2026), where the lines to the rest of the house run."])
X_RC = PH_X + 0.76                                 # between the desuperheater drop and the gap between the tanks
dhw("dhw_recirc", "Hot water recirculation return", HOT_R, "foam",
    [[X_HR, Y_WALL, 0.0], [X_HR, Y_WALL, Z_RC], [X_HR, Y_COLD - 0.3, Z_RC], [X_RC, Y_COLD - 0.3, Z_RC], [X_RC, Y_WALL, Z_RC], [X_RC, Y_WALL, 1.2], [GAP_X, Y_WALL, 1.2], [GAP_X, WC_Y, 1.2]],
    "1/2 in copper, insulated", ["Return from the far end of the hot main (U-11 shows a recirculation pump). Comes up through the slab next to the hot line, crosses above the preheat tank, "
                                 "comes down the south wall between the two tanks through the pump at chest height, and tees into the water heater's cold inlet pipe. "
                                 "Which of the lines in the slab is the return is ASSUMED. A check valve and a timer or demand control are ASSUMED.",
                                 "Insulated like the hot line: a recirculation loop is hot whenever it runs, so bare pipe would give that heat away all day."])
# Pan drains (Maxwell, 11/19/2026: the drain is a floor drain for the water heater's pan). Both tanks' pans drain to it and end
# an inch above the grate so there is an air gap. The water heater's line runs behind the preheat tank, under the desuperheater pipe.
PAN_Z = 0.1
WH_PAN = WH_X - (WR * 12 + 2) / 12
dhw("pan_drain_wh", "Drain pan lines", 1.32, "pvc",
    [[WH_PAN + 0.02, WH_CY + 0.3, PAN_Z], [WH_PAN - 0.1, WH_CY + 0.3, PAN_Z], [WH_PAN - 0.1, US - 0.12, PAN_Z], [X_DR + 0.1, US - 0.12, PAN_Z], [X_DR + 0.1, Y_DR, PAN_Z], [X_DR + 0.06, Y_DR, PAN_Z + 0.04]],
    "1 in PVC from each tank's drain pan",
    ["The water heater's pan drains behind the preheat tank to the floor drain, about 6 ft. The preheat tank's pan drains straight to it. Both end above the grate for an air gap. "
     "The relief valves (T&P) on both tanks can discharge here too. Route ASSUMED."])
dhw("pan_drain_ph", None, 1.32, "pvc", [[PH_X - 0.83, PH_Y + 0.62, PAN_Z], [X_DR - 0.12, PH_Y + 0.62, PAN_Z], [X_DR - 0.12, Y_DR, PAN_Z + 0.04]], None, None, info_of="pan_drain_wh")
items += [
 dict(id="recirc_pump", name="Hot water recirculation pump", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="circ_pump", size=[5, 5, 5], at=[X_RC, Y_WALL, 3.9], facing=90,
      info=dict(model="Small inline circulator, bronze or stainless body (U-11)", specs=[["On", "The recirculation return where it comes down the south wall, about 4 ft off the floor"]],
                notes=["Model not picked. A timer or a push button demand control keeps it from running all day.", APPROX])),
 dict(id="expansion_tank", name="Thermal expansion tank", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="expansion_tank", size=[8, 11], at=[UV_X + 0.75, LN, 6.75], facing=180,
      info=dict(model="2 gal potable thermal expansion tank (U-11 detail)", specs=[["On", "The treated cold line, after the main shutoff and any check valve"]], notes=[APPROX])),
 dict(id="mixing_valve", name="Thermostatic mixing valve", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="mixing_valve", size=[3, 3, 3], at=[GAP_X, WHOT_Y, 6.3], facing=0,
      info=dict(model="3/4 in thermostatic mixing valve", specs=[["Why", "Lets both tanks store water hotter for more capacity while the taps get a safe 120 F"]],
                notes=["Its cold side tees off the cold line; that small tee is not drawn.", APPROX])),
 dict(id="floor_drain", name="Floor drain", category="Hot water", system="plumbing.drain", room="Utility", layer="mechanical",
      builder="floor_drain", size=[6, 0.5, 6], at=[X_DR, Y_DR + 0.25, 0], facing=0,
      info=dict(model="Floor drain with a round grate, about 4 in", specs=[["Where", "South wall, about 2-1/2 ft off the west wall, beside the house hot lines (Maxwell, 11/19/2026)"],
                                                                         ["Takes", "Both tanks' drain pans and relief valves, the spin down flush, a softener's backwash if one goes in"]],
                notes=["Maxwell (11/19/2026): the drain line coming up here will become a floor drain and pan drain for the water heater. Trap primer, size and exact spot are the plumber's.", APPROX])),
 # ---- well water: pressure tank and treatment, north wall
 dict(id="pressure_tank", name="Well pressure tank", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="pressure_tank", size=[PT_D, PT_H], at=[PT_X, UN + 0.02, 0], facing=180,
      info=dict(model="Slim diaphragm well tank, about 44 gal (generic tall model)", price="Included in Crabtree's $4,900 pump system (estimate 2479, approved 3/11/2026)",
        specs=[["Pump", "1/2 HP submersible with a pressure switch (Crabtree estimate 2479)"], ["Size", "About 16 in across and 62 in tall"],
               ["Pressure", "Usually a 40/60 PSI switch with the tank pre-charged to 38 PSI"], ["Connection", "1 in at the bottom, through the tank tee"]],
        links=[["Crabtree Drilling", "https://www.crabtreedrilling.com"]],
        notes=["Crabtree's approved estimate lists a 1/2 HP submersible pump system 'including a pressure tank, pipe, wire, fittings, ditch digging and labor' but not the tank model or size. "
               "The size here is ASSUMED: a 44 gal tank is a common match for a 1/2 HP pump and gives about 12 gal between pump starts. "
               "A slim, tall tank was picked over the usual 22 in one so the walkway past the water tanks stays about 22 in wide (Maxwell, 11/19/2026: slimmer is fine, there is height to use). "
               "The quote also offered a 1 HP constant pressure system for $5,800 as an alternate; the approved total ($10,919) has the 1/2 HP system.",
               "Well (same estimate): 6 in PVC casing, estimated 100 ft, $43/ft past that.", APPROX],
        placement="North wall of the utility room, east of the filters. The pump is down the well, so the only noise here is the pressure switch clicking.")),
 dict(id="tank_tee", name="Tank tee and pressure switch", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="tank_tee", size=[10, 4, 3], at=[TT_X, LN + 0.1, 1.0], facing=180,
      info=dict(model="1 in brass tank tee with pressure switch, gauge, relief valve and drain", specs=[["Switch", "40/60 PSI, ASSUMED"]],
                notes=["Part of Crabtree's pump system. Layout ASSUMED.", APPROX])),
 dict(id="spin_down", name="Spin down sediment screen", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="spin_down", size=[6, 13, 6], at=[SP_X, UN, HEAD_Z - 11.5 / 12], facing=180,
      info=dict(model="Flushable spin down screen, 1 in, about 100 micron (generic)", specs=[["Service", "Open the flush valve at the bottom to rinse sand out, no cartridge"]],
                notes=["Not in Crabtree's quote. The whole filter row is a placeholder until the water test comes back (Maxwell, 11/19/2026: approximate is fine).", APPROX])),
 dict(id="filter_sediment", name="Sediment filter", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="big_blue", size=[8, 25, 9], at=[SD_X, UN, HEAD_Z - 23.3 / 12], facing=180,
      info=dict(model="20 in x 4.5 in whole house housing, 5 micron pleated sediment cartridge (generic)", specs=[["Flow", "About 15 to 20 gpm"], ["Cartridge", "Change every 3 to 6 months"]],
                notes=["Generic placeholder, not in Crabtree's quote.", APPROX])),
 dict(id="filter_carbon", name="Carbon filter", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="big_blue", size=[8, 25, 9], at=[CB_X, UN, HEAD_Z - 23.3 / 12], facing=180, sump="grey",
      info=dict(model="20 in x 4.5 in whole house housing, carbon block cartridge (generic)", specs=[["Takes out", "Taste, odor and some chemicals"], ["Cartridge", "Change every 6 to 12 months"]],
                notes=["Generic placeholder. If the water test shows iron or sulfur, an iron filter or a softener usually goes here instead, and those need floor space and the drain.", APPROX])),
 dict(id="uv_sterilizer", name="UV sterilizer", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="uv_system", size=[8, UV_H, 6], at=[UV_X, UN, UV_Z], facing=180,
      info=dict(model="Whole house UV sterilizer, about 12 gpm (Viqua VH410 class, generic)", specs=[["Power", "120 V outlet nearby"], ["Lamp", "Change once a year"], ["Order", "Last, after the filters, so the water it sees is clear"]],
                notes=["Generic placeholder, not in Crabtree's quote. Common on private wells to kill bacteria; the county may want a bacteria test either way.", APPROX])),
 dict(id="softener_space", name="Water softener (space reserved)", category="Well water", system="plumbing.well", room="Utility", layer="mechanical",
      builder="softener_cabinet", size=[14, 44, 17.5], at=[UE - 0.62, US - 0.02, 0], facing=0,
      info=dict(model="Space for a cabinet softener, about 14 W x 17-1/2 D x 44 H in (generic, not decided)",
        specs=[["Status", "Not decided. Space kept so one can go in later (Maxwell, 11/19/2026)"], ["Needs", "120 V outlet, the floor drain for backwash (about 8 ft of 1/2 in tubing), and the treated cold line"],
               ["Would sit", "After the filters, before the preheat tank, with a bypass valve"]],
        notes=["Southeast corner, south of the hall door, so the door still opens fully. A cabinet unit (resin and salt in one box) fits; a twin tank one does not.",
               "Whether it is needed depends on the water test (hardness and iron). Piping to it is not drawn.", APPROX])),
 # ---- cleaning (Maxwell, 11/19/2026): the stick vacuum lives in the hall closet on its wall charging dock
 dict(id="stick_vacuum", name="Dyson V8 stick vacuum on its wall dock", category="Cleaning", system="household", room="Hall closet", layer="appliances",
      builder="stick_vacuum", size=[9.8, 49.1, 8.8], at=[VAC_WALL - 0.01, VAC_Y, 0], facing=270,
      info=dict(model="Dyson V8 cordless stick vacuum (clear bin, long wand) with its wall docking station and charger",
        specs=[["Size", "About 9.8 W x 49 H x 8.8 D in hanging on the dock, floor head about 1 in off the floor"],
               ["Dock", "Screws to the wall with its top about 4 ft up, charges the vacuum while it hangs and holds two tools"],
               ["Power", "One 120 V duplex outlet about 18 in up, just north of the vacuum, for the charger"],
               ["Run time", "Up to about 40 min on low, roughly 5 h to recharge"]],
        notes=["Placeholder for where the vacuum is kept (Maxwell, 11/19/2026). Exact V8 variant not picked, so the size is from the V8 class.",
               "The charger outlet is not on Andy's U-11: it is in the Electrical layer as an added outlet, so tell the electrician it is wanted here. U-11 shows no outlet in this closet.", APPROX],
        placement="Hall closet off hall 2, on the back (east) wall straight across from the door (Maxwell, 11/19/2026: moved here from the utility room). It sticks out about 9 in into the 3 ft deep closet, which leaves about 2 ft 3 in in front of it.")),
 dict(id="ro_system", name="Reverse osmosis drinking water", category="Kitchen appliance", system="plumbing.well", room="Kitchen", layer="appliances",
      builder="ro_unit", size=[5.7, 18, 17.6], at=[10.85, 51.42, 0.34], facing=0,
      info=dict(model="Tankless under sink reverse osmosis with its own faucet (generic, Waterdrop G3 class)",
        specs=[["Size", "About 5.7 W x 18 H x 17.6 D in, stands beside the disposal"], ["Needs", "Cold line tee, a drain saddle on the sink drain, and an outlet for the pump"],
               ["Faucet", "Small RO faucet in a hole beside the main faucet"]],
        notes=["Under the kitchen sink rather than whole house: the utility room has no room left, and you only need RO water for drinking and cooking (Maxwell, 11/19/2026: under the sink is fine).",
               "Not picked yet.", APPROX],
        placement="Inside the sink base, right side, behind the right door.")),
]
# Laundry sink water and drain (see laundry_sink). Everything rises out of the slab in the 2 1/2 in gap behind the sink, so
# nothing goes in the wall the hall closet's Dyson hangs on, and no pipe runs inside a wall.
SH_X, SC_X, FAU_Z = SINK_X - 4 / 12, SINK_X + 4 / 12, 40.5 / 12           # hot on the left (west), cold on the right, faucet shanks
TRAP_Y = SINK_BACK - 13 / 12                                               # under the bowl's drain
dhw("sink_hot", "Laundry sink supplies", 0.625, "pex_hot", [[round(SH_X, 3), round(SUP_Y, 4), 0], [round(SH_X, 3), round(SUP_Y, 4), FAU_Z]],
    "1/2 in PEX, hot (red) and cold (blue)", ["Up through the slab behind the sink to quarter turn stops about 18 in up, then to the faucet shanks. "
    "Assumed to run under the slab from the utility room, where the house hot and cold go down, about 20 ft."],
    system="plumbing.laundry", category="Laundry sink plumbing")
dhw("sink_cold", None, 0.625, "pex_cold", [[round(SC_X, 3), round(SUP_Y, 4), 0], [round(SC_X, 3), round(SUP_Y, 4), FAU_Z]], None, None,
    info_of="sink_hot", system="plumbing.laundry", category="Laundry sink plumbing")
dhw("sink_trap", "Laundry sink drain", 1.9, "pvc",
    [[round(SINK_X, 3), round(TRAP_Y, 4), 17 / 12], [round(SINK_X, 3), round(TRAP_Y, 4), 1.0], [round(SINK_X, 3), round(TRAP_Y + 0.13, 4), 0.9],
     [round(SINK_X, 3), round(TRAP_Y + 0.28, 4), 1.0], [round(SINK_X, 3), round(TRAP_Y + 0.28, 4), 1.16], [round(SINK_X, 3), round(SINK_BACK, 4), 1.14]],
    "1 1/2 in PVC P trap, 2 in PVC riser, air admittance valve", ["The tailpiece drops into a 1 1/2 in P trap, the trap arm runs back to a 2 in riser that comes up "
    "out of the slab behind the sink, and an air admittance valve on top of the riser vents it (about 10 in above the trap weir). "
    "The riser drains to the building drain under the slab. The combo washer dryer can share it."],
    system="plumbing.laundry", category="Laundry sink plumbing")
dhw("sink_riser", None, 2.375, "pvc", [[round(SINK_X, 3), round(SINK_BACK, 4), 0], [round(SINK_X, 3), round(SINK_BACK, 4), 2.0]], None, None,
    info_of="sink_trap", system="plumbing.laundry", category="Laundry sink plumbing")

# Desuperheater (Maxwell, 11/18/2026). The preheat tank stands just east of the heat pump's hot water connections, so the two
# insulated 3/4 in lines step sideways off the ports and drop straight through the deck into the lane behind the tank.
# One goes to the tank's drain port (water to the geo), the other tees into the cold drop above the tank (water back).
DSH_Y = US - 0.24
PH_DRAIN = [PH_X + (PH_D / 2 + 1.7) / 12, TANK_Y - (PH_D / 2 + 2 - 4.8) / 12, 5.4 / 12]
for k in range(2):
    z = HP_Z + (9.6, 13.6)[k] / 12
    x = HP_PX + (-0.27, 0.27)[k]
    start = [[HP_PX, HP_S + 0.07, z], [HP_PX, HP_S + 0.18, z], [x, HP_S + 0.18, z], [x, DSH_Y, z]]
    if k == 0: pts = start + [[x, DSH_Y, PH_DRAIN[2]], [PH_DRAIN[0], DSH_Y, PH_DRAIN[2]], PH_DRAIN]
    else: pts = start + [[x, DSH_Y, 6.15], [PH_X - 0.3, DSH_Y, 6.15], [PH_X - 0.3, PH_Y, 6.15]]
    runs.append(dict(id=f"dsh_{k}", name="Desuperheater lines", category="Hot water", system="plumbing.dhw", dia=1.6, mat="foam",
        info_of=None if k == 0 else "dsh_0", points=pts,
        info=dict(model="3/4 in copper or PEX with pipe insulation, to and from the geo's built in desuperheater pump",
                  specs=[["Supply to the geo", "From the preheat tank's bottom drain port"], ["Return from the geo", "Tees into the cold drop just above the preheat tank"],
                         ["Length", "About 5 ft and 10 ft: straight down from the heat pump's connections to the tank"]],
                  notes=["The lines drop straight through the attic deck from the heat pump's hot water connections and down the wall just west of the preheat tank (Maxwell, 11/18/2026). "
                         "Service parts from the GZT manual (p.39): a shutoff valve on each line at the tank, an air vent at the high point, which here is at the heat pump in the attic, "
                         "and drain valves for flushing and purging the circuit. Copper only, 5/8 in OD or larger, 50 ft at most, 3/8 in wall insulation. "
                         "Route is ASSUMED. Line size and the maximum run come from the GZT installation manual."])))

# ------------------------------------------------------------------ attic: heat pump, ERV
# ERV: raised to the height of the heat pump's top, in line with it and just south of its piping, so its two room side ducts run
# straight over the top of the heat pump with no bends (Maxwell, 11/18/2026: it can go up, and the ducts should stay off the floor).
ERV_Z = HP_Z + 21.2 / 12 + 0.4                    # centre of the ERV's duct adapters, and of the two ducts over the heat pump
ERV_N = HP_S + 1.45                               # its room (north) end
ERV_S = ERV_N + 24.8 / 12                         # its outdoor (south) end
ERV_XF, ERV_XS = HP_CX - 0.415, HP_CX + 0.415     # fresh air adapter (west) and stale air adapter (east)
items += [
 dict(id="heat_pump", name="Geothermal heat pump", category="HVAC", system="hvac.air", room="Attic", layer="mechanical",
      builder="geo_horizontal", size=[21.7, 21.2, 56], at=HP_AT, facing=270, mirror=True,
      info=dict(model="GeoComfort GZT048, 4 ton two stage, horizontal, shown with a right hand return", price="$9,979.20, or $11,797.82 for the whole quote MMUL8476-4",
        specs=[["Cabinet", "21.7 W x 21.2 H x 56.0 L in"], ["Supply opening", "11.6 x 12.5 in"], ["Full load", "48,700 Btuh cooling at EER 17.3, 36,900 Btuh heating at COP 3.6"],
               ["Part load", "38,000 Btuh at EER 24.4, 29,300 Btuh at COP 4.1"], ["Airflow", "1,368 CFM design (M-10)"], ["Load", "Manual J: 35,394 Btuh heating, 41,028 Btuh cooling"],
               ["With it", "AXCH151MB 15 kW heater $514.20, AFR1836A filter rack $132, two MERV 13 18 x 36 filters $175.68, EZ-Trap, Sensi Touch thermostat $271.20"]],
        notes=["Andy's plan names a ClimateMaster Tranquility 30 as the basis of design and assumes a downflow unit. This is the unit Greg quoted and Maxwell sent Andy on 8/14/2026.",
               "Greg's quote MMUL8476-4 is for GZT048J11LM1CCS, which is a left hand return. This layout needs the right hand return version: standing at the "
               "water connection end, the return and filter are on the right. The unit is not ordered yet, so ask Greg to quote the right hand model and confirm which side the service panels are on.",
               "Service access from the GZT manual (p.17): 2 ft clear in front of the controls and compressor panel, which is the south (connection) end; 2 ft beside the blower door, "
               "which with end discharge is on the west side at the north end; working room for the reversing valve and heat exchanger on the west side and for the TXV and filter drier "
               "on the east side, both near the south end. The west aisle is 2 ft, the return plenum stops at the coil so the TXV corner is open, and the ERV intake duct runs along the west wall "
               "just above the cabinet's height, so the aisle is clear up to about 2-1/2 ft over the deck. STILL SHORT: the ERV hangs 17 in in front of the controls end and has to move.",
               "Condensate: the drain is at the north end, the EZ-Trap needs 6-1/2 in of height so the unit sits on a 6-1/2 in pad, and the unit tilts 1/4 to 1/2 in toward the drain (p.19, p.35). "
               "Over a finished ceiling a secondary drain pan under the unit is the usual code answer; the manual shows it as optional.",
               "Turned 90 degrees (Maxwell, 11/18/2026): supply out the north end toward the trunk, water and desuperheater connections on the south end right above the flow center, "
               "return and filter on the east side, service panels facing a 2 ft aisle along the west wall."],
        placement="On the attic deck over the utility room, where Andy drew HP-01, lengthwise north to south.")),
 dict(id="erv", name="Energy recovery ventilator", category="HVAC", system="hvac.ventilation", room="Attic", layer="mechanical",
      builder="erv", size=[21.0, 20.8, 24.8], at=[HP_CX, ERV_N, ERV_Z - 10.4 / 12], facing=180, hang=round((CFG["roof"]["north_wall_height"] + (ERV_N + 1.1) * CFG["roof"]["north_pitch"] / 12 - 0.9 - (ERV_Z + 10.4 / 12)) * 12, 1),
      info=dict(model="Broan AI Series 210 ERV, side ports (B210E75RS). Replaces the Panasonic Intelli-Balance 100 that is ERV-01 on M-10", price="About $1,580 to $1,790 (11/19/2026)",
        specs=[["Airflow", "65 to 210 CFM, self balancing. Low all the time, boost from a bathroom timer"], ["Size", "About 24.8 x 21 x 20.8 in, 47 lb, four 6 in ports"],
               ["Ducts", "Exhaust through the west wall beside the unit, intake through the west wall 10 ft further north, both 8 in"],
               ["Stale air from", "Bath 1, bath 2 and powder exhaust grilles: 20 CFM each all the time, about 80 CFM from each shower room and 30 from the powder room on boost. Plus 20 CFM from the litter box in the utility room"],
               ["Fresh air to", "The supply plenum at the heat pump, so it reaches every room through the supply registers"], ["Mounting", "Hung level from the roof framing, its underside about 22 in above the deck"],
               ["Controls", "Runs continuously on low; a 20/40/60 minute wall control (Broan VBATHW, about $34) in each bathroom boosts it; blower interlock wire to the heat pump"]],
        links=[["Broan B210E75RS", "https://broan-nutone.com/en-us/product/freshairsystems/b210e75rs"]],
        notes=["Maxwell, 11/19/2026: a larger ERV so the bathrooms need no fans of their own. This one unit does all the bath exhaust; the two shower fans, their ducts and their wall hoods are gone. "
               "Alternatives: Panasonic Intelli-Balance 200 (about $2,730 to $3,135), RenewAire EV Premium L (30 to 280 CFM).", APPROX,
               "What to expect: an ERV core hands some moisture back to the incoming air, so it clears a steamy mirror slower than a fan blowing straight outdoors, and boost pulls from all three "
               "bathrooms at once. If the bath 1 wet room proves too steamy, a fan on its own duct to the east wall can still be added there. The unit has to run all the time so damp air does not sit in the ducts. "
               "The port layout is ASSUMED from the side port model; check Broan's drawing before hanging it.",
               "The bathrooms exhaust through this unit instead of separate fans (Maxwell, 11/17/2026). The code allows it because the ERV sends that air outdoors; "
               "it has to run continuously at 20 CFM or more per bathroom (Ohio 4101:8-15-01, table 1505.4.4), so no bath fan is required.",
               "Fresh air goes into the supply plenum, not the attic (Maxwell, 11/18/2026). ERV makers' instructions say the furnace blower should run whenever the ERV runs when it is tied into "
               "the ductwork, and Building Science Corp. calls for an interlock and a motorized damper on a supply side connection. The heat pump's ECM blower can idle at low speed for this. "
               "Andy should confirm the ERV can push against the supply plenum's pressure; the fallback is the return plenum, which the code also counts as supply ventilation (IRC M1505.4.1).",
               "One fan pulls from all three bathrooms, so the whole exhaust duct is under suction and air cannot be pushed from one bathroom into another. Backdraft dampers are for "
               "separate fans that share a duct. Each branch gets a balancing damper to set its airflow.",
               "Set out to the Panasonic installation instructions the first unit came with (Maxwell, 11/18/2026); check them against Broan's: the two outdoor hoods are more than 10 ft apart, every duct connection has 2 ft or more of straight run "
               "before its first elbow, the outdoor ducts are insulated, the unit hangs level on chains inside the conditioned attic, and the intake is well over 6 ft from the dryer and range hood outlets.",
               "A backdraft damper in the fresh air duct stops the heat pump's blower from pushing supply air backward through the ERV. With the blower off, the ERV's own fan still sends the fresh air "
               "down the supply trunk to every register, so it works without the heat pump running. Whole house ventilation is about 75 CFM for this size and bedroom count, "
               "and a full boost is about 190 CFM, inside this unit's 210. Andy should confirm the size. The range hood cannot connect here, it has its own duct outdoors.",
               "Litter box exhaust (Maxwell, 11/20/2026): a fourth pickup, 20 CFM from a low grille behind the litter box in the utility room. The bath grilles keep their 20 each, "
               "so the continuous setting goes from about 65 to 80 CFM (fresh air rises with it, the unit stays balanced). With a 20 CFM constant airflow insert on that branch, boost is unchanged; "
               "with only a hand damper the litter branch would take about 50 of the 210 on boost."],
        placement="In line with the heat pump, just south of it, hung at the height of its top. Andy drew it west of HP-01.")),
]

# ------------------------------------------------------------------ ducts
DAMPER = "Manual volume damper at the takeoff, set when the system is air balanced (M-10 general notes)"
def supply(id, room, cfm, dia, points, grille=None, note=None, name=None, parent="supply_trunk", el=0):
    # cfm, parent (the duct this run is fed from) and el (extra equivalent length, ft) are read by tools/duct_balance.py
    d = dict(id=id, name=name or f"Supply to {room}", category="HVAC supply duct", system="hvac.supply", room=room, type="supply", shape="round", size=dia, points=points,
             cfm=cfm, parent=parent, damper=True,
             info=dict(model=f'{dia} in round, {cfm} CFM', specs=[["Airflow", f"{cfm} CFM (M-10)"], ["Duct", f"{dia} in round"], ["Damper", DAMPER]], notes=[note] if note else []))
    if el: d["el"] = el
    if grille: d["grilles"] = [grille]
    ducts.append(d)

XW, YN, YE, XJ = HP_CX, 12.0, 16.1, 29.2         # west leg x, north leg y, east leg y, jog x: against bedroom 1's door wall (west face x 30.25), the attic's east wall there (Maxwell, 11/19/2026; it had stayed at 27.07 when that wall moved east from 28.12)
TRUNK_NOTE = ("Rerouted from M-10. Andy drew this trunk down the middle of the attic at y about 21.6 ft. Maxwell asked for it along the north wall of the attic, "
              "so it runs straight north from the heat pump with no turn (Maxwell, 11/18/2026), then along the north attic wall all the way to bedroom 1's west wall, follows that wall south, then runs east along bedroom 1's south wall (Maxwell, 11/17/2026: keep the middle of the attic free for storage). Size is Andy's 18 x 16 throughout, no reductions modelled.")
ducts.append(dict(id="supply_trunk", name="Supply trunk", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[18, 16], parent="supply_plenum", el=20,
    points=[[XW, HP_N - 2.0, ZTR], [XW, YN, ZTR], [XJ, YN, ZTR], [XJ, YE, ZTR], [41.2, YE, ZTR]],
    info=dict(model="18 x 16 in main trunk, 1,368 CFM", specs=[["Airflow", "1,368 CFM total"], ["Location", "On the attic deck against the north attic wall"]], notes=[TRUNK_NOTE])))
ducts.append(dict(id="supply_plenum", info_of="supply_trunk", type="supply", shape="rect", size=[26, 24], parent=None, points=[[HP_CX, HP_N - 0.75, DECK + 1.0], [HP_CX, HP_N - 2.05, DECK + 1.0]]))
def drop(x, y0, ys, zt=ZT):      # leave the trunk's side, drop into the truss space, run to ys
    return [[x, y0, DECK + 0.45], [x, y0 + (0.25 if ys > y0 else -0.25), zt], [x, ys, zt]]

# The floor trusses sit on one 24 in grid across the house (they run continuous over the interior walls), so every
# truss bay lines up from room to room: trusses at x = TG + 2k, bays centred on TG + 1 + 2k (1.7, 3.7, 5.7, ...).
# A duct may run north to south inside a bay at any size that fits, but anything crossing the trusses goes through
# the web openings, so it is round and 6 in or less (tools/truss_clash.py checks both).
TG = CFG["floor_trusses"].get("grid_x0", 0.7)
def bay(x):                       # centre of the truss bay nearest x
    return round(TG + 1 + 2 * round((x - TG - 1) / 2), 3)

S = "S"; N = "N"
# A wall register's back sits about 1/10 in behind the drywall face and its front stands about 0.6 in proud, so it shows
# from the room and its faces are never flush with the wall (tools/grille_reach.mjs checks every grille).
YC2 = CFG["roof"]["clerestory_wall_y"] + CFG["house"]["ext_wall_thickness"]   # south (kitchen side) face of the clerestory wall
YREG_S = round(YC2 + 0.25 / 12, 3)                # centre of a register on that face, 0.7 in thick
# north wall trunk: high sidewall registers straight through the attic wall into the vaulted north rooms
supply("s_closet3", "Closet 3", 26, 6, [[3.3, YN - 0.6, 11.0], [3.3, 10.6, 11.0]], dict(at=[3.3, 10.62, 11.0], size=[10, 6], wall=N), "High sidewall register through the attic wall.")
supply("s_closet2", "Closet 2", 32, 6, [[4.7, YN - 0.6, 11.0], [4.7, 10.3, 11.0], [4.7, 5.5, 10.25]], dict(at=[4.7, 5.44, 10.25], size=[10, 6], wall=N), "Runs exposed along the ceiling of closet 3 to reach closet 2. ASSUMED.")
supply("s_bed2", "Bedroom 2", 78, 6, [[8.5, YN - 0.6, 11.0], [8.5, 10.6, 11.0]], dict(at=[8.5, 10.62, 11.0], size=[12, 6], wall=N), "High sidewall register through the attic wall.")
# Study (Maxwell, 11/18/2026): it is one of the most used rooms, has computers in it (about 1 kW, Maxwell 11/19/2026) and needs good
# circulation with the door shut. 1 kW of computers, screens and a person is about 3,400 Btu/h; in cooling the supply is about 20 F
# below the room, so it takes about 160 CFM (CFM = Btu/h / (1.08 x dT)) against M-10's 104.
# Maxwell, 11/19/2026 (picked on a card after bedroom 1's door wall moved): no exposed duct along the ceiling, no booster fan and no
# motorized damper. Two 8 in high sidewall registers in the door wall, east of the high return. Later the same day he had the trunk's
# elbow moved east against bedroom 1's door wall, so the trunk passes right behind both registers and each is a stub about 8 in long
# straight off its north face, like bedroom 2's. tools/duct_balance.py: each gets about 110% of its 80 CFM with every damper open,
# and with the door shut the high return and the two low stacks bring back about 84% at about 0.5 Pa. cfm 98 each is in M-10's
# units: the tool scales every register to the 1,368 CFM system, which makes these 80 each.
XS1, XS2 = 27.9, 29.5                             # register centres; the trunk's north leg now ends at x 29.95 and the deck at bedroom 1's door wall, x 30.25
STUDY_NOTE = ("Two of these, side by side, replace the exposed duct, booster fan and motorized damper (Maxwell, 11/19/2026). Sized for about 1 kW of computers, "
              "screens and a person: about 160 CFM in cooling, against M-10's 104. The supply trunk runs right behind this wall (its elbow moved east to bedroom 1's "
              "door wall for this, Maxwell 11/19/2026), so each register is a stub about 8 in long straight off the trunk. Nothing passes through a floor truss.")
STUDY_REG = ("Registers: long throw, bar type with adjustable blades, aimed along the sloped ceiling at the window about 10 ft away, so the air crosses the "
             "desk before it comes back. The supply and the returns are all in this wall, and a short throw register would let part of the air slip "
             "straight into the high return beside it.")
STUDY_FIXED = ("The airflow is fixed. The hand damper on each run is reached from the attic: open in summer, part closed in winter, when the computers "
               "already heat the room. An outlet on the attic side of this wall would let a motorized damper replace the hand ones later. The rest of the "
               "house gives up about 5% of its air for this unless the blower is set near 1,440 CFM instead of 1,368.")
for _k, _x in enumerate([XS1, XS2]):
    supply("s_study" if _k == 0 else "s_study2", "Bedroom 4 / study", 98, 8, [[_x, YN - 0.6, 11.0], [_x, 10.6, 11.0]],
           dict(at=[_x, 10.62, 11.0], size=[14, 6], wall=N), STUDY_NOTE, name=f"Supply to Bedroom 4 / study, {'west' if _k == 0 else 'east'} register")
    ducts[-1]["info"]["model"] = "8 in round, about 80 CFM, one of two"
    ducts[-1]["info"]["specs"] = [["Airflow", "About 80 CFM each, 160 for the room (M-10 has 104 for the room)"], ["Duct", "8 in round stub straight off the trunk"],
                                  ["Register", "14 x 6 in high sidewall, long throw"], ["Damper", "Manual volume damper at the takeoff, reached from the attic"]]
    ducts[-1]["info"]["notes"] += [STUDY_REG, STUDY_FIXED]
supply("s_hall2a", "Hall 2", 15, 6, drop(bay(14.4), YN + 0.75, 17.8), dict(at=[bay(14.4), 17.8, CEIL - 0.02], size=[8, 6]))
supply("s_hall2b", "Hall 2", 16, 6, drop(bay(20.5), YN + 0.75, 13.8), dict(at=[bay(20.5), 13.8, CEIL - 0.02], size=[8, 6]))
# west leg
XB3 = bay(3.7)                                    # bottom takeoff under the trunk, in the truss bay below it
supply("s_bed3", "Bedroom 3", 127, 8, [[XB3, 13.4, DECK + 0.3], [XB3, 13.4, ZT], [XB3, 16.6, ZT]], dict(at=[XB3, 16.6, CEIL - 0.02], size=[14, 8]),
       "Bottom takeoff from the trunk into the truss bay below it, then about 3 ft south in that same bay to a ceiling register. It crosses no truss, so it can be 8 in: "
       "the 6 in run that crossed one truss carried only about three quarters of this room's air (duct balance check, 11/18/2026).")
# south main: drops from the west side of the supply plenum into the first truss bay at the west wall and runs south in it. Each kitchen and powder
# register then gets its own round branch through the truss webs (a rectangular main cannot cross the trusses).
XM = bay(1.7) + 0.2                               # east of centre in the bay, so the geo risers pass on its west side
KY = CFG["roof"]["clerestory_wall_y"] - 0.02 - 7 / 12   # centreline of the kitchen duct on the deck, tight against the attic side of the clerestory wall
KZ = DECK + 4 / 12 + 0.02                         # centre of an 8 in tall duct lying on the deck
SMAIN_END = KY
ducts.append(dict(id="supply_south_main", name="South supply main", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[14, 8],
    points=[[XM, HP_N - 1.4, DECK + 0.2], [XM, HP_N - 1.4, ZT], [XM, SMAIN_END, ZT]], parent="supply_plenum", el=50,
    info=dict(model="14 x 8 in in the first truss bay, then up onto the deck for the kitchen", specs=[["Serves", "Kitchen and dining 3 x 127 CFM, pantry 22, powder 15, utility 18"]],
      notes=["New. On M-10 these rooms were fed by branches crossing the attic floor. Here the main runs south in the truss bay along the west wall, "
             "which is parallel to the trusses so a rectangular duct fits. The small utility and powder branches cross the trusses at 6 in. "
             "At the clerestory wall the main comes up through the deck and feeds the kitchen duct, so the big kitchen runs never pass through a truss (Maxwell, 11/18/2026). Sizes are schematic."])))
ducts.append(dict(id="s_pantry", name="Supply to Pantry", category="HVAC supply duct", system="hvac.supply", room="Pantry", type="supply", shape="rect", size=[10, 6],
    points=[[XM, 31.0, ZT], [XM, 31.0, CEIL + 0.05]], cfm=22, parent="supply_south_main", damper=True, grilles=[dict(at=[XM, 31.0, CEIL - 0.02], size=[10, 6])],
    info=dict(model="10 x 6 in ceiling register on the bottom of the south main, 22 CFM", specs=[["Airflow", "22 CFM (M-10)"], ["Damper", "Opposed blade damper in the register"]], notes=[])))
supply("s_utility", "Utility", 18, 6, [[XM, 26.5, ZT], [3.1, 26.5, ZT]], dict(at=[3.1, 26.5, CEIL - 0.02], size=[8, 6]), parent="supply_south_main", note="Extra capacity for the utility room computers is on Maxwell's wish list and not sized yet.")
supply("s_powder", "Powder", 15, 6, [[XM, 29.2, ZT], [9.5, 29.2, ZT]], dict(at=[9.5, 29.2, CEIL - 0.02], size=[8, 6]), parent="supply_south_main", note=
       "Round branch off the south main through the pantry trusses. Ceiling register in the northeast corner by the door, about 4 ft from the "
       "exhaust over the toilet (Maxwell, 11/18/2026: move them apart; the 9 ft flat ceiling leaves no way to bring this one in low).")
# Kitchen (Maxwell, 11/18/2026): run it higher, out of the floor, so it can be bigger. The main rises through the deck at the clerestory
# wall and a 14 x 8 duct lies on the deck tight against that wall, over the pantry and powder room. Each register is a short 8 in stub
# straight through the wall, like the bedroom registers on the north trunk. Nothing here crosses a truss.
KX = [bay(3.0), bay(7.0), bay(11.0)]
ducts.append(dict(id="supply_kitchen_riser", info_of="supply_kitchen_main", type="supply", shape="rect", size=[14, 8], parent="supply_south_main", el=30,
    points=[[XM, KY, ZT], [XM, KY, KZ]]))
ducts.append(dict(id="supply_kitchen_main", name="Kitchen supply duct", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[14, 8], parent="supply_kitchen_riser",
    points=[[XM, KY, KZ], [KX[-1] + 0.6, KY, KZ]],
    info=dict(model="14 x 8 in on the attic deck along the clerestory wall, 381 CFM", specs=[["Serves", "Kitchen and dining, 3 x 127 CFM"], ["Location", "On the deck over the pantry and powder room, against the kitchen wall"]],
      notes=["Replaces three 6 in branches through the pantry and powder trusses, which carried only about 70% of the kitchen's air (duct balance check, 11/18/2026). "
             "Maxwell, 11/18/2026: run the kitchen ducts higher so they are not in the floor and can be larger. It takes a strip of deck 14 in wide along the wall. ASSUMED size."])))
for k, x in enumerate(KX):
    supply(f"s_kitchen{k+1}", "Kitchen / dining", 127, 8, [[x, KY + 0.55, KZ], [x, YC2 - 0.03, KZ]], dict(at=[x, YREG_S, KZ], size=[14, 6], wall=S), parent="supply_kitchen_main", note=
           "High sidewall register in the clerestory wall, about 11 in higher than before, on a short 8 in stub from the kitchen duct on the attic deck. M-10 had the third one at x about 17 ft, reached by a duct across the open living room, so it moved west.")
# east leg
YS = YE + 0.75
XL = bay(27.6)                                     # laundry and living 1 share one bay, side by side
# The elbow moved east of this bay (Maxwell, 11/19/2026), so these two leave the west face of the trunk's north to south leg, run about
# a foot west on the deck and then drop into the bay as before.
def drop_w(x, y0, ys):
    return [[XJ - 0.6, y0, DECK + 0.45], [x, y0, DECK + 0.45], [x, y0 + 0.25, ZT], [x, ys, ZT]]
supply("s_laundry", "Laundry", 40, 6, drop_w(XL - 0.35, 15.9, 19.0), dict(at=[XL - 0.35, 19.0, CEIL - 0.02], size=[10, 6]))
supply("s_living1", "Living", 70, 7, drop_w(XL + 0.35, 15.2, 21.4) + [[bay(23.7), 21.4, ZT], [bay(23.7), 22.62, ZT]], dict(at=[bay(23.7), 22.9, ZT], size=[10, 6], wall=S),
       "Drops in the laundry bay, then crosses the trusses west under the study returns to keep the register near where M-10 has it. "
       "7 in (Maxwell, 11/18/2026): at 6 in this was the weakest supply in the house. The builder is only sure 6 in passes the truss webs, so check the fit at these two trusses before ordering.")
ducts[-1]["cross_ok"] = 7                          # tools/truss_clash.py: this run may cross the trusses at 7 in
supply("s_living2", "Living", 70, 7, drop(bay(29.7), YS, 22.62), dict(at=[bay(29.7), 22.9, ZT], size=[12, 6], wall=S),
       "Hall 1 has no supply of its own (Maxwell, 11/17/2026): one 3 ft from the main return would short circuit into it. Its 48 CFM from M-10 is split between the two living registers, which open onto the hall through the 8 ft wide cased opening.")
supply("s_closet1", "Closet 1", 33, 6, drop(bay(33.4), YS, 18.9), dict(at=[bay(33.4), 18.9, CEIL - 0.02], size=[10, 6]))
XB1 = bay(35.7)                                    # bath 1 and the loft share one bay
supply("s_bath1", "Bath 1", 49, 6, drop(XB1 - 0.4, YS, 27.6), dict(at=[XB1 - 0.4, 27.6, CEIL - 0.02], size=[10, 6]), "Runs in the loft floor.")
supply("s_loft", "Loft", 88, 8, drop(XB1 + 0.4, YS, 24.6) + [[XB1 + 0.4, 24.6, DECK + 0.01]], dict(at=[XB1 + 0.4, 24.6, DECK + 0.01], size=[12, 4]),
       "Floor register in the loft. 8 in, up from 6 in: the run stays in one truss bay, so the 6 in limit on crossing trusses does not apply (duct balance check, 11/18/2026).")
for k, x in enumerate([31.7, 37.7]):
    supply(f"s_family{k+1}", "Entry / family", 112, 8, drop(bay(x), YS, YC2 - 0.03), dict(at=[bay(x), YREG_S, ZT], size=[14, 6], wall=S), "Runs in the loft floor to a high sidewall register. 8 in, up from 7 in: 19 ft long but all in one truss bay, so it can be the full size the trusses allow (duct balance check, 11/18/2026).")
# Bedroom 1's supply sits high over the middle of its pocket door's header (Maxwell, 11/20/2026: good mixing with both returns
# east of the header). Nudged 6 in east of the header's centre (x 34.8) to clear the attic outlet in the same wall at x 34.5.
XB1S = 35.3
supply("s_bed1", "Bedroom 1", 138, 8, [[XB1S, YE - 0.6, 11.0], [XB1S, 14.95, 11.0]], dict(at=[XB1S, 15.01, 11.0], size=[14, 8], wall=N),
       "High sidewall register through the attic wall, over the closet 1 pocket door's header (Maxwell, 11/20/2026). The header and its "
       "flat 2x and cripples stop at the 9' 1\" top plates, so the register and its boot sit in the wall above them.")

# ------------------------------------------------------------------ returns
# Main: Andy's M-10 return, a 34 x 10 grille high on the hall 1 west wall. Behind it a boot box sits in one truss bay
# (parallel to the trusses, so it fits), rises straight up through the deck, and a 34 x 10 trunk on the deck runs to the
# return plenum at the heat pump.
# Bedrooms: low grilles with a stack up the stud bay into the trusses, then round flex. Flex runs north to south in a bay
# where it can, and crosses the trusses only at 6 in or less, through the web openings. Every run ends at the return
# plenum box on the deck at the heat pump.
DK = DECK + 5 / 12                                # centre of a 10 in tall duct lying on the deck
LOW = 1.0                                         # centre of a low return grille, 8 in tall, its bottom 8 in above the floor
STK = [14, 2.5]                                   # wall stack: 14 x 2-1/2 in, kept inside a 3-1/2 in stud bay (w runs along plan x)
PZ = DECK + 1.0                                   # centre of the 24 in tall plenum box on the deck
def ret(id, name, size, points, grilles=None, note=None, info_of=None, model=None, flex=False, parent="return_plenum", el=0, **calc):
    # parent (the duct this one empties into), el (extra equivalent length, ft) and calc (k, n, room, intake, calc) are read by tools/duct_balance.py
    d = dict(id=id, name=name, category="HVAC return duct", system="hvac.return", type="return", points=points, parent=parent, **calc)
    if el: d["el"] = el
    if isinstance(size, (int, float)):
        d.update(shape="round", size=size)
        if flex: d["flex"] = True
    else: d.update(shape="rect", size=size)
    if info_of: d["info_of"] = info_of
    else: d["info"] = dict(model=model or (f"{size} in round flex" if flex else f"{size[0]} x {size[1]} in"), notes=[note] if note else [])
    if grilles: d["grilles"] = grilles
    ducts.append(d)
    return d

def stack(id, x, y, info_of, parent, room, size=STK, top=ZT):   # a return stack from a low grille up the stud bay into the truss space
    ret(id, None, size, [[x, y, LOW - 0.33], [x, y, top]], info_of=info_of, parent=parent, room=room, intake=True, el=75)

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
         "the web openings at 6 in or less. For reference, SBCA's floor truss guidance lists about 5-5/8 in round through the end panel of a 12 in deep "
         "truss and 7 to 8 in through the larger interior panels, so the truss maker should confirm the opening sizes on the truss drawings, or build a "
         "duct chase where these runs cross. Flex is fine for returns inside the conditioned envelope if it is pulled tight with gentle bends. Sizes are ASSUMED "
         "until Andy or the HVAC installer sizes them.")

RY = 24.8                                          # the main return's centreline: above the utility room door, in line with the heat pump's filter side
# Quiet main return (Maxwell, 11/18/2026: do everything we can to cut the noise at this grille). About 1,030 CFM comes back here.
# The grille is twice as tall and sits higher on the hall 1 wall, above the attic deck, so it opens into a lined box on the deck
# instead of a boot in the trusses. The air turns down inside the box, turns again into a taller lined trunk, and turns a third
# time into the filter, so there is no straight line for blower noise from the heat pump to the hall.
RG_H = 20                                          # grille height, in
RG_Z = DECK + 14 / 12 + RG_H / 24 + 0.1            # grille centre: its bottom edge just above the top of the trunk behind the wall
RT_H = 14                                          # lined trunk height, in
DKM = DECK + RT_H / 24                             # centre of the trunk lying on the deck
ret("return_main", "Main return (M-10)", [34, RG_H], [[11.64, RY, RG_Z], [11.06, RY, RG_Z]], parent="return_main_riser", intake=True, k=1.0,
    grilles=[dict(at=[12.15, RY, RG_Z], size=[34, RG_H], wall="E")])
ducts[-1]["info"] = dict(model=f"34 x {RG_H} in grille, lined drop box and 34 x {RT_H} in lined trunk, 1,368 CFM system (M-10)",
    specs=[["Serves", "Living, kitchen, dining, family and the halls, plus what leaves the bedrooms under their doors"], ["Grille", f"34 x {RG_H} in, high on the hall 1 wall. About 220 fpm at the face, down from about 440 fpm at 34 x 10"],
           ["Drop box", f"14 x 36 in, on the deck behind the grille, 1 in acoustic duct liner"], ["Trunk", f"34 x {RT_H} in on the attic deck, 1 in acoustic duct liner, about 6 ft"],
           ["Turns", "Three between the grille and the filter: down in the box, into the trunk, and into the return plenum"]],
    notes=["Andy's M-10 return is one 34 x 10 grille in hall 1 and a 34 x 10 return trunk to HP-01. Maxwell, 11/18/2026: make it as quiet as possible, with a larger grille and "
           "an elbow or two so the sound bounces before it reaches the hall. The grille is 34 x 20 and sits above the attic deck on the same wall, over the utility room door. "
           "It opens into a lined box that turns the air down to the deck, then a lined trunk runs west into the return plenum. Nothing is in the floor trusses any more.",
           "To go further: a deeper filter grille style frame with a sound attenuating liner, flexible connectors at the heat pump, and a turning vane free square elbow (lined) all help. "
           "Liner takes 1 in off each inside face, so the trunk is drawn 4 in taller than M-10's. Sizes and route ASSUMED."])
RP_N = HP_Y - 2.035                                # the plenum box covers the 36 in filter rack on the coil (north) half of the unit
RP_S = RP_N + 3.2                                  # and stops there, so the TXV and filter drier access south of it stays open (GZT manual p.17, area A-2)
RP_E = HP_X + 0.22 + 14 / 12                       # its east face, where the trunk comes in
RPX = bay(7.7)                                     # the bedroom flex runs come up into the bottom of the trunk in this truss bay
XMR = 11.06                                        # the drop box, tight against the attic side of the hall 1 wall
ret("return_main_riser", None, [14, 36], [[XMR, RY, RG_Z + RG_H / 24], [XMR, RY, DECK + 0.02]], info_of="return_main", parent="return_main_deck", k=1.0)
ret("return_main_deck", None, [34, RT_H], [[XMR - 7 / 12, RY, DKM], [RP_E, RY, DKM]], info_of="return_main", k=1.0)
# Utility room (Maxwell, 11/18/2026): the door is solid, so the room gets a transfer grille straight up into the attic.
UTX, UTY = bay(9.7), 27.3
ret("transfer_utility", "Utility room transfer grille", [12, 12], [[UTX, UTY, CEIL], [UTX, UTY, DECK - 0.03]], parent=None, calc=False,
    grilles=[dict(at=[UTX, UTY, CEIL - 0.02], size=[12, 12]), dict(at=[UTX, UTY, DECK + 0.02], size=[12, 12])],
    model="12 x 12 in ceiling grille and lined sleeve up through the trusses to a grille in the attic deck",
    note="The utility room has a solid door (to keep equipment noise out of the hall), a supply register and no return, so the air it is given had no way out. "
         "Maxwell, 11/18/2026: give it a transfer grille to the attic. The sleeve sits in one truss bay between the water heater and the door. "
         "Lining the sleeve keeps light and tank noise from carrying. The attic is inside the SIP roof and has no return opening of its own, so Andy should confirm "
         "how air gets from the attic back to the heat pump. ASSUMED size and position. "
         "Since the litter box exhaust (11/20/2026) pulls 20 CFM from the room against its 18 CFM supply, air now comes DOWN this grille, a little, instead of going up, so the litter smell does not reach the attic.")
ret("return_plenum", "Return plenum box", [14, 24], [[RP_E - 7 / 12, RP_S, PZ], [RP_E - 7 / 12, RP_N, PZ]], parent=None,
    model="14 x 24 in return plenum box on the deck, along the heat pump's filter rack",
    note="The return trunk comes straight into its east face. The bedroom flex runs come up through collars in the bottom of the trunk just east of it. "
         "The box sits on the deck along the AFR1836A filter rack on the heat pump's east side. Size ASSUMED.")

# Bedrooms 2 and 3 (Maxwell, 11/17/2026): bedroom 3's grille moved from beside the bed to its north wall. Both grilles are in
# the wall the two rooms share, in neighbouring stud bays, and both stacks rise into the trusses over bedroom 3, where they join.
# Bedroom 3 has a second grille and stack one bay west (duct balance check, 11/18/2026): one 14 x 2-1/2 in stack chokes 127 CFM.
XR3, XR2, XR3B = bay(7.7), bay(9.7), bay(5.7)
r = ret("return_bed23", "Bedrooms 2 and 3 return", 10, bend([[XR3, 10.85, ZT], [XR3, RY - 0.7, ZT], [XR3, RY - 0.7, DECK + 0.2]]), flex=True, el=25,
        grilles=[dict(at=[XR3, 10.97, LOW], size=[14, 8], wall=S), dict(at=[XR3B, 10.97, LOW], size=[14, 8], wall=S)])
r["info"]["specs"] = [["Serves", "Bedroom 3 (two low grilles on its north wall) and bedroom 2 (low grille on its south wall)"],
                      ["Duct", "14 x 2-1/2 in wall stacks, 6 in flex from bedroom 2 and from bedroom 3's second stack through one truss each, 10 in flex south in one truss bay to the plenum"],
                      ["Crosses", "One truss from each side, at 6 in. No supply runs"]]
r["info"]["notes"] = ["Bedroom 3's grille moved from its south wall, next to the bed, to its north wall (Maxwell, 11/17/2026). It shares that wall with bedroom 2, "
                      "so the stacks rise side by side into the trusses over bedroom 3 and join there: bedroom 2's 6 in flex crosses one truss into bedroom 3's bay and "
                      "tees into a 10 in flex that runs south in that bay, parallel to the trusses, to the return plenum box at the heat pump.",
                      "Bedroom 3 has two grilles and two stacks (duct balance check, 11/18/2026): a 14 x 2-1/2 in stack is all a 2x4 wall holds, and one of them alone "
                      "passed only about three quarters of the room's 127 CFM.", RFLEX]
stack("return_bed3_stack", XR3, 10.8, "return_bed23", "return_bed23", "Bedroom 3")
stack("return_bed3_stack2", XR3B, 10.8, "return_bed23", "return_bed3b", "Bedroom 3")
ret("return_bed3b", None, 6, bend([[XR3B, 10.85, ZT], [XR3B, 12.6, ZT], [XR3 - 0.3, 13.4, ZT], [XR3, 13.9, ZT]], 0.4), flex=True, info_of="return_bed23", parent="return_bed23", el=30)
ret("return_bed2", None, 6, bend([[XR2, 10.85, ZT], [XR2, 11.9, ZT], [XR3 + 0.3, 12.7, ZT], [XR3, 13.2, ZT]], 0.4), flex=True, parent="return_bed23", el=30,
    grilles=[dict(at=[XR2, 10.64, LOW], size=[14, 8], wall=N)], info_of="return_bed23")
stack("return_bed2_stack", XR2, 10.8, "return_bed23", "return_bed2", "Bedroom 2")

# Study: two 6 in flex home runs from its one stack (duct balance check, 11/18/2026: one 6 in returned about 60% of the room's air).
# They come down in one hall 2 bay, cross the laundry and linen trusses west a little apart, and drop south in their own bays.
# The second run uses the route bedroom 1's return had before it moved up onto the supply trunk.
XSB, XSB2 = bay(27.7), bay(29.7) - 0.2           # the study's two low grilles east of its door (x 23.37-26.00 with casing to 26.29), Maxwell 11/18/2026
# bedroom 1's grilles: both east of the closet 1 pocket door's header (Maxwell, 11/20/2026). The as-built header and its
# double jacks run from x 31.59 to 38.01 ([framing] in config.toml, 71 in clear measured 11/20/2026); at x 32.0 and 33.3 the stacks ran through the
# pocket. The second stack skips the bay with the bedroom outlet at x 39.6.
XB1R = 38.7
XSR = bay(25.7)                                   # both runs go south in the 25.7 bay: the laundry and living 1 supplies fill bay 27.7
YSW, YBW = 19.6, 20.3
r = ret("return_study", "Study return", 6,
        bend([[XSB - 0.3, 10.85, ZT], [XSB - 0.3, 11.4, ZT], [XSR - 0.35, 11.4, ZT], [XSR - 0.35, YSW, ZT], [XR2, YSW, ZT], [XR2, RY + 0.5, ZT], [RPX, RY + 0.5, ZT], [RPX, RY + 0.5, DECK + 0.2]]), flex=True,
        el=25, grilles=[dict(at=[XSB, 10.64, LOW], size=[14, 8], wall=N), dict(at=[XSB2, 10.64, LOW], size=[14, 8], wall=N)])
r["info"]["model"] = "Two low grilles, each with its own stack and 6 in round flex run"
r["info"]["specs"] = [["Serves", "Study (low grille on its south wall, east of the door; a separate high grille over the door carries most of the air)"],
                      ["Duct", "Two 14 x 2-1/2 in wall stacks in neighbouring truss bays, each with a 6 in flex home run to the heat pump's return"],
                      ["Crosses", "The laundry, linen and bedroom 3 trusses at 6 in. No supply runs, and they stay in the trusses, off the tall south part of the attic"]]
r["info"]["notes"] = ["The study has a low grille (Maxwell, 11/17/2026) with a stack up the stud bay into the trusses. Two 6 in runs because one big duct "
                      "would not fit through the truss webs and a single 6 in returned only about 60% of the room's 104 CFM (duct balance check, 11/18/2026). "
                      "If the builder confirms 7 in fits the webs, one 7 in run does nearly the same job.",
                      "Second grille and stack (Maxwell, 11/19/2026): the builder can move bedroom 1's door wall east, so it moved 2 ft 1 1/2 in, just far enough that the study's south wall has two stud bays for stacks, each under its own floor truss bay (27.7 and 29.7). The 24 in truss layout is ASSUMED: if the real trusses sit differently over this wall, the move needed changes, and with a truss right over the stud between the two bays it could be as little as about 8 in. Confirm on site.", RFLEX]
stack("return_study_stack", XSB, 10.8, "return_study", "return_study", "Bedroom 4 / study")
stack("return_study_stack2", XSB2, 10.8, "return_study", "return_study2", "Bedroom 4 / study")
ret("return_study2", None, 6, bend([[XSB2, 10.85, ZT], [XSB2, 12.0, ZT], [XSR + 0.35, 12.0, ZT], [XSR + 0.35, YBW, ZT], [bay(11.7) - 0.2, YBW, ZT],
                                    [bay(11.7) - 0.2, RY - 1.3, ZT]]), flex=True, info_of="return_study", el=25)

# Bedroom 1 (duct balance check, 11/18/2026): its 138 CFM is too much for anything that fits through the truss webs, so its return
# stays out of the trusses. Two stacks rise side by side in bedroom 1's south wall to a header above the supply trunk, which lies
# against the attic side of that wall. One 10 in round then rides on top of the trunk, beside the bath exhaust main, round to the
# north attic wall, comes down onto the deck east of the trunk's west leg and runs south to the return plenum.
ZR = ZTR + 8 / 12 + 5 / 12 + 0.02                  # centre of a 10 in round lying on top of the 18 x 16 supply trunk
ZH = ZTR + 8 / 12 + 0.54 + 5 / 12 + 0.04           # centre of the header, clear above the 6 in exhaust main on the trunk
XB1B = 40.6                                        # the second stack, one stud bay further east: the outlet at x 39.6 sits between them
XBH = (XB1R + XB1B) / 2
HBW = round((XB1B - XB1R) * 12 + 14 + 4)           # header box width (in): over both stacks
Y_RL, X_RL, Y_RN = YE + 0.31, XJ - 0.31, YN + 0.31 # the return's lane on the trunk top: south side of the east leg, west side of the jog, south side of the north leg
XRD = RP_E - 7 / 12                                # where it comes down and runs south, in line with the return plenum box
r = ret("return_bed1", "Bedroom 1 return", 10,
        [[XBH, 15.95, ZH], [XBH, Y_RL, ZH], [XBH, Y_RL, ZR], [X_RL, Y_RL, ZR], [X_RL, Y_RN, ZR], [XRD, Y_RN, ZR], [XRD, YN + 1.3, ZR], [XRD, YN + 2.3, DK], [XRD, RP_N, DK]],
        el=25, model="10 in round on top of the supply trunk",
        grilles=[dict(at=[XB1R, 15.01, LOW], size=[14, 8], wall=N), dict(at=[XB1B, 15.01, LOW], size=[14, 8], wall=N)])
r["info"]["specs"] = [["Serves", "Bedroom 1 (two low grilles on its south wall, east of the closet 1 pocket door)"],
                      ["Duct", "Two 14 x 2-1/2 in wall stacks to a header box, then one 10 in round, about 45 ft"],
                      ["Route", "On top of the supply trunk beside the bath exhaust main, then on the deck beside the trunk to the return plenum"],
                      ["Crosses", "No trusses"]]
r["info"]["notes"] = ["Replaces a 6 in flex through the laundry and linen trusses, which returned only about half of bedroom 1's 138 CFM (duct balance check, 11/18/2026). "
                      "A duct big enough for this room cannot pass the truss webs, so it goes over the top instead: it uses no deck along the trunk, "
                      "and a strip about 10 in wide beside the trunk's west leg over bedroom 3.",
                      "Clearance under the roof is tightest along the north attic wall, about 5 in above the duct in this model. Confirm on site. ASSUMED size and route."]
stack("return_bed1_stack", XB1R, 15.26, "return_bed1", "return_bed1_head", "Bedroom 1", top=ZH)
stack("return_bed1_stack2", XB1B, 15.26, "return_bed1", "return_bed1_head", "Bedroom 1", top=ZH)
ret("return_bed1_head", None, [HBW, 10], [[XBH, 15.3, ZH], [XBH, 15.95, ZH]], info_of="return_bed1", parent="return_bed1", el=25)

# Bath 2 supply comes in LOW and the exhaust stays HIGH (Maxwell, 11/18/2026), so the boost exhaust does not pull the fresh
# supply air straight back out. A bottom takeoff from the trunk drops into hall 2's trusses, runs north in one truss bay to the
# bath 2 / hall 2 wall (an interior stud wall, not a SIP), and goes down that stud bay to a low register just east of the door.
XS2 = 20.1                                        # inside bay 19.7, east of the door casing (door opening x 16.58 to 19.21)
supply("s_bath2", "Bath 2", 37, 6, [[XS2, YN, DECK + 0.3], [XS2, YN, ZT], [XS2, 10.85, ZT]], dict(at=[XS2, 10.64, LOW], size=[10, 6], wall=N), el=60, note=
       "Low sidewall register on the south wall (Maxwell, 11/18/2026): supply low, exhaust high on the other end of the same wall, so fresh air "
       "sweeps across the room before the exhaust takes it. Bottom takeoff from the trunk, 6 in round north in one hall 2 truss bay, then a "
       "12 x 2-1/2 in stack down the stud bay of the interior wall. The register sits east of the door and west of the vanity. ASSUMED sizes.")
ducts.append(dict(id="s_bath2_stack", info_of="s_bath2", type="supply", shape="rect", size=[12, 2.5], points=[[XS2, 10.8, LOW - 0.25], [XS2, 10.8, ZT]]))

# Bath exhaust (Maxwell, 11/17/2026): ceiling or high wall grilles in bath 1, bath 2 and the powder room, ducted to the ERV's stale air inlet
# instead of separate fans. The run hugs the supply trunk's south side on the deck so it stays in the low, north part of the attic.
ZTOP = ZTR + 8 / 12 + 0.27                        # centre of a 6 in round lying on top of the 18 x 16 supply trunk
EX = DECK + 0.25                                  # centre of a 6 in round lying on the deck
ENOTE = ("ERV pickup grille: the ERV pulls 20 CFM from it continuously and more on boost, from a timer by the door. There is no separate bath fan (Maxwell, 11/19/2026). "
         "Allowed by the Ohio residential code (4101:8-15-01, sections 1501.1 and 1505.4.4) because the ERV discharges outdoors. Duct sizes and route are ASSUMED.")
def exhaust(id, name, dia, points, grilles=None, note=None, info_of=None, room=None):
    d = dict(id=id, category="Ventilation", system="hvac.exhaust", type="exhaust", shape="round", size=dia, points=points)
    if info_of: d["info_of"] = info_of
    else:
        d.update(name=name, room=room, info=dict(model=f"{dia} in round exhaust", notes=[note] if note else []))
    if grilles: d["grilles"] = grilles
    ducts.append(d)
XE1 = bay(39.7)
Y_EL, X_EL, Y_EN = YE - 0.48, XJ + 0.48, YN - 0.48  # the exhaust main's lane on the trunk top: the other side from the bedroom 1 return
exhaust("ex_bath1", "Bath 1 exhaust", 6, [[XE1, 30.0, ZT], [XE1, 17.8, ZT], [XE1, 17.8, EX]], room="Bath 1",
        grilles=[dict(at=[XE1, 30.0, CEIL - 0.02], size=[10, 10])], note=ENOTE + " Runs north in one loft floor truss bay, east of the family supply drop, then up onto the deck.")
XE2 = 21.9                                        # east end of the south wall, over the toilet and vanity, away from the low supply
exhaust("ex_bath2", "Bath 2 exhaust", 6, [[XE2, 10.62, ZTOP], [XE2, Y_EN, ZTOP]], room="Bath 2",
        grilles=[dict(at=[XE2, 10.64, ZTOP], size=[10, 6], wall=N)], note=ENOTE + " High on the east end of the bath 2 south wall, through the attic wall and into the main on top of the supply trunk. "
        "It was right beside the supply; the supply now comes in low at the west end of the same wall (Maxwell, 11/18/2026).")
PWX, PWY = 7.2, 32.2                               # powder room exhaust grille, over the toilet, about 4 ft from the supply by the door (Maxwell, 11/18/2026)
exhaust("ex_powder", "Powder exhaust", 4, [[PWX, PWY, ZT], [PWX, PWY, EX - 0.08], [4.9, PWY, EX - 0.08], [4.9, HP_S + 1.0, EX - 0.08], [4.9, HP_S + 1.0, ERV_Z], [ERV_XS + 0.1, HP_S + 1.0, ERV_Z]], room="Powder",
        grilles=[dict(at=[PWX, PWY, CEIL - 0.02], size=[8, 8])], note=ENOTE + " Comes up through the deck, runs along it and rises into the main just before the ERV. "
        "The litter box exhaust from the utility room tees into its riser.")
# Litter box exhaust (Maxwell, 11/20/2026): the cat's litter box lives in the utility room, so a small duct off the ERV's stale air side pulls
# a slow, steady 20 CFM from a low grille right behind it, and the smell goes outdoors instead of through the transfer grille into the attic
# (and from there back into the return). The box sits against the north wall east of the pressure tank, clear of the hall door. The
# pickup is a 10 x 4 in grille just above the box's back rim in the stud bay x 8.63 to 9.84 (typical 16 in layout until measured); a
# 6 x 2-1/2 in stack runs up that bay. In the floor trusses a 4 in round steps 6 in south, between the truss at x 8.7 and the study
# return in bay 9.7, out from under the server rack's pad, rises through the deck north of the main return trunk, crosses over the
# trunk 1-1/2 ft up, runs south to the line of the powder exhaust's riser and west into that riser just before the ERV.
LX = 9.15                                          # in the stud bay and in the truss space between the 8.7 truss and the study return
LWY = (UN + 22.408) / 2                            # centre of the utility room's north wall (bedroom 3 side face 22.408)
LGZ = 15 / 12                                      # pickup grille centre, its bottom about 1 in above a 12 in tall box's rim
LRY = 23.15                                        # riser through the deck: south of the rack pad (y 22.94), north of the return trunk (23.38)
LZ = 11.6                                          # over the 14 in main return trunk (top 11.22) and the water heater intake elbow (top 11.38)
LTY = HP_S + 1.0                                   # the powder exhaust riser's line
LIT_CFM = 20
LNOTE = (f"A slow, steady {LIT_CFM} CFM pulled from right behind the litter box, all the time, so the smell is taken at the box and goes outdoors with the bath air "
         "(Maxwell, 11/20/2026, after a video where a small ERV pickup at a litter box kept the room from ever smelling). "
         "The utility room is given about 18 CFM of supply (M-10) and has a solid door, so pulling 20 out keeps it slightly under suction: a little air comes in "
         "through the transfer grille and under the door and none leaves the room any other way. Before this the room's air, litter smell and all, went up "
         "the transfer grille into the attic and from there back into the return.")
ducts.append(dict(id="ex_litter_stack", info_of="ex_litter", type="exhaust", shape="rect", size=[6, 2.5], points=[[LX, LWY, LGZ - 0.2], [LX, LWY, ZT]],
                  grilles=[dict(at=[LX, UN + 0.021, LGZ], size=[10, 4], wall=S)]))
exhaust("ex_litter", "Litter box exhaust", 4, [[LX, LWY, ZT], [LX, LRY, ZT], [LX, LRY, LZ], [LX, LTY, LZ], [4.9 + 0.17, LTY, LZ]], room="Utility", note=LNOTE)
_lx = ducts[-1]
_lx["cfm"] = LIT_CFM
_lx["info"].update(model=f"4 in round exhaust, {LIT_CFM} CFM continuous, from a 10 x 4 in low filter grille behind the litter box", specs=[
    ["Airflow", f"{LIT_CFM} CFM all the time, set with the hand damper in the attic. On boost it rises with the bath grilles unless a constant airflow insert is used (notes)"],
    ["Pickup", "10 x 4 in filter grille in the north wall, centre 15 in off the floor, just above the box's back rim. A washable filter behind it keeps litter dust out of the ERV"],
    ["Duct", "6 x 2-1/2 in stack up the stud bay, then 4 in round: 6 in south in the floor trusses, up through the deck, over the main return trunk, south and west into the powder exhaust riser"],
    ["Into", "The ERV's stale air side, through the powder exhaust riser, about 1 ft before the unit"],
    ["Damper", "Hand balancing damper on the attic run, about 1-1/2 ft before the tee"]])
_lx["info"]["notes"] += [
    "Sizing: the video's pickup was about 5 CFM, a computer fan's worth. 20 CFM is used here so the room stays under suction against its supply; turn the damper down "
    "toward 10 if the room's supply is cut back. At 20 CFM a 4 in duct is quiet (about 230 ft per minute) and the stack in the wall moves the air at under 200.",
    "ERV balance: the three bath grilles keep their 20 CFM each (the code minimum), so the ERV's continuous setting goes up from about 65 to 80 CFM, which "
    "also brings in 80 CFM of fresh air (about 75 is the house's ventilation need). No bath grille needs trimming. "
    "On boost every branch rises together, so with only a hand damper this one would take roughly 50 of the unit's 210 CFM and the bathrooms about 160 instead of 190. "
    "A 4 in constant airflow regulator set to 20 CFM (a drop in insert, Aldes makes them, about $30 to $50) holds this branch at 20 whatever the fan does, "
    "so the boost stays in the bathrooms. Recommended in place of, or with, the hand damper.",
    "An ERV core hands some moisture back to the incoming air and a trace of odour can ride along with it. At 20 CFM out of 80, diluted with the bath air, that should not be noticeable. "
    "If it ever is, this branch can be split off to its own small fan and wall cap.",
    "Clash checks: the stack is in one stud bay (no studs, wall junctions or the door header), the 4 in round is between a truss and the study return in the floor trusses, "
    "and it crosses no trusses. Stud positions are the typical layout until the wall is measured. ASSUMED route and position."]
_lx["info"]["placement"] = "Utility room north wall, behind the litter box, up into the attic over the utility room."
LD_X = 4.9 + 0.17 + 1.5                           # hand damper on the attic run, 1-1/2 ft before the tee: reached from the heat pump's east side
items.append(dict(id="litter_damper", name="Litter box exhaust damper", category="Ventilation", system="hvac.exhaust", room="Attic", layer="ducts",
    builder="hand_damper", size=[4, 7], at=[LD_X, LTY, LZ - 2 / 12 - 0.15 / 12], facing=90,
    info=dict(model="4 in round manual balancing damper with a locking quadrant handle", price="About $10 to $20",
        specs=[["Set to", f"{LIT_CFM} CFM at the litter grille, with the ERV on its continuous setting"], ["Reach", "From the attic deck east of the heat pump, about 1-1/2 ft up"],
               ["Upgrade", "A 20 CFM constant airflow regulator in the duct holds the flow on boost too, so the bathrooms keep their boost air"]],
        notes=["Balancing damper for the litter box exhaust (Maxwell, 11/20/2026). Set once at commissioning, then locked. ASSUMED position."],
        placement="Attic, on the litter box exhaust just east of the powder exhaust riser.")))
LB = [24, 12, 18]                                  # a large open high sided litter box, W x H x D in (generic, for scale)
items.append(dict(id="litter_box", name="Cat litter box", category="Pets", system="household", room="Utility", layer="storage",
    builder="litter_box", size=LB, at=[LX, UN + 2 / 12, 0], facing=180, mat=[26, 16],
    info=dict(model="Large open litter box with high sides, about 24 x 18 x 12 in, on a litter mat (generic, for scale)",
        specs=[["Where", "Utility room north wall, east of the pressure tank, 2 in off the wall, about 2-1/2 ft west of the hall door"],
               ["Exhaust", f"The 10 x 4 in exhaust grille is right behind it, just above the back rim, pulling {LIT_CFM} CFM to the ERV"]],
        notes=["Placeholder for where the cat's litter box goes (Maxwell, 11/20/2026). The spot keeps it out of the walkway from the door to the tanks and the manifolds, "
               "away from the water heater's noise and clear of the hall door, which swings out into the hall. Any box works as long as its back sits against the grille."],
        placement="Utility room, against the north wall, centred on the exhaust grille.")))
ZTOP8 = ZTR + 8 / 12 + 4 / 12 + 0.02              # centre of an 8 in round lying on top of the trunk
MNOTE = ("Collects the three bathroom exhausts. It rides on top of the supply trunk all the way from bath 1's riser, on the side away from the bedroom 1 return, "
         "down to the heat pump, crosses over the heat pump's top and goes straight into the ERV's stale air inlet, so it takes no floor space (Maxwell, 11/18/2026). "
         "It is 6 in as far as bath 2, where it carries bath 1 alone, and 8 in from there to the ERV for the boost airflow (Maxwell, 11/19/2026: larger ERV, no bath fans). "
         "It crosses no trusses. It reduces to the ERV's 6 in port at the unit. ASSUMED route and size.")
exhaust("ex_main", "Bath exhaust main", 6, [[XE1, 17.8, EX], [XE1, 17.3, EX], [XE1, 17.3, ZTOP], [XE1, Y_EL, ZTOP], [X_EL, Y_EL, ZTOP], [X_EL, Y_EN, ZTOP], [XE2 + 0.6, Y_EN, ZTOP]], note=MNOTE)
exhaust("ex_main_w", None, 8, [[XE2 + 0.6, Y_EN, ZTOP], [XE2 + 0.25, Y_EN, ZTOP8], [ERV_XS, Y_EN, ZTOP8], [ERV_XS, HP_N - 2.5, ZTOP8], [ERV_XS, HP_N - 2.5, ERV_Z], [ERV_XS, ERV_N, ERV_Z]], info_of="ex_main")
# Heat pump water heater air (Maxwell, 11/18/2026): the utility door stays solid, so the water heater's intake and exhaust are both
# ducted up into the attic, which is inside the SIP roof. Rheem allows any size room when both are ducted and says never to tie
# the unit into other ductwork. Both rise straight up in truss bay 7.7, north to south of each other, and come out on open deck
# in the corner between the return plenum and the return trunk. Each ends in an elbow, pointing apart (Maxwell, 11/18/2026).
HPWH_TOP = 74.2 / 12
for k, (nm, yy, tail) in enumerate([("intake", WH_CY - 0.15, [[WH_DUCT_X, WH_CY - 0.15, DECK + 1.0], [WH_DUCT_X + 0.8, WH_CY - 0.15, DECK + 1.0]]),
                                   ("exhaust", WH_CY + 0.62, [[WH_DUCT_X, WH_CY + 0.62, DECK + 0.4], [WH_DUCT_X, WH_CY + 3.6, DECK + 0.4]])]):
    ducts.append(dict(id=f"hpwh_{nm}", name=f"Water heater {nm} duct" if k == 0 else None, category="Hot water", system="plumbing.dhw.air", type="exhaust",
        shape="round", size=8, flex=True, room="Utility",
        points=[[WH_DUCT_X, yy, HPWH_TOP + 0.05]] + tail,
        **({"info": dict(model="8 in insulated flex, Rheem duct kit (SP20889 flex, SP20890 elbows, SP17829 outlet adaptor)",
                         specs=[["Intake", "Top of the water heater up through the deck to an elbow facing east, 1 ft up"], ["Exhaust", "Up through the deck, then an elbow and 3 ft along the deck, so the cold air leaves about 4 ft from the intake and points away from it"],
                                ["Limit", "125 ft equivalent, intake plus exhaust; each elbow counts 5 ft"]],
                         notes=["Rheem: 'DO NOT connect this water heater to existing duct work; it must be ducted separately from other appliances.'",
                                "Insulated because the exhaust air is cold and would sweat. The newest Rheem manual uses a 10 in exhaust collar; 8 in shown. Route ASSUMED."])}
           if k == 0 else {"info_of": "hpwh_intake"})))
for d in ducts:
    if d.get("name", 1) is None: d.pop("name")

# Study high return (Maxwell, 11/18/2026: good circulation with the door shut). Bedroom 1's return rides the trunk top about a foot
# behind the study's door wall, so a high grille in that wall and a short flat boot over the bath exhaust main land straight on it.
XSH = 25.6
ZSH = ZTOP + 3 / 12 + 0.02 + 2 / 12               # centre of a 4 in tall boot, clear above the 6 in exhaust main
ret("return_study_high", "Study high return", [20, 4], [[XSH, 10.6, ZSH], [XSH, Y_RN - 0.3, ZSH]], parent="return_bed1", room="Bedroom 4 / study", intake=True, el=65,
    grilles=[dict(at=[XSH, 10.62, ZSH], size=[22, 4.5], wall=N)], model="22 x 4-1/2 in grille and flat boot into the bedroom 1 return",
    note="A high grille at the top of the study's door wall. A flat 20 x 4 in boot behind the grille about 1 ft long passes over the bath exhaust main and into the side of the 10 in "
         "bedroom 1 return on top of the supply trunk. No trusses and no stud bay, so it carries most of the study's air; the low grille and its two 6 in runs stay. "
         "Warm air from the computers collects under the high side of the ceiling, right where this grille is. The roof is about 1 in above the boot in this model: "
         "if it does not fit, drop the exhaust main down the trunk's north face for 2 ft here. An outlet in the attic beside it would make an inline fan easy to add later. ASSUMED.")

# Range hood (Maxwell, 11/20/2026): out the side of the house, high, tucked under the roof, and designed to the advice in the
# video he picked (https://www.youtube.com/watch?v=Qs4wis82NAE). The hood itself (make_house.py, [kitchen.hood]) is a wide, deep,
# low white oak box hemmed in by the oven tower and a south cheek. A power pack insert with a heat sensor sits at the top of it
# and turns itself on whenever the cooktop is hot, so it gets used every time. 8 in duct up the chimney enclosure, one elbow just
# under the ceiling, straight out the west SIP wall to a wall cap under the 12 in rake overhang.
# Code (Ohio Residential Code 4101:8-15-01, eff. 7/1/2019): 1503.3 its own duct to the outdoors, smooth, air tight, backdraft
# damper, never into an attic or soffit (also 1501.1); 1503.4 galvanized, stainless or copper; 1504.3 opening 3 ft from operable
# windows and doors, 10 ft from mechanical intakes. 1503.6 makeup air above 400 CFM applies only with a fuel burning appliance
# that is not direct vent inside the house, and this house is all electric.
RF = CFG["roof"]; KH = CFG["kitchen"].get("hood", {})
def roof_under_s(y):                               # underside of the low (south) roof SIP at y; on the west wall this is also the underside of the rake overhang
    return RF["south_wall_height"] + (CFG["house"]["depth_y"] - y) * RF["south_pitch"] / 12
def ftin_(v): return f"{int(v)} ft {round((v - int(v)) * 12)} in"
WALL_X = CFG["house"]["ext_wall_thickness"]
HX, HY = WALL_X + 0.6, 47.0                        # duct centre: in the chimney enclosure (14-3/8 in deep off the west wall), over the cooktop's centre
HOOD_TOP = 3.0 + KH.get("above_counter_in", 27) / 12 + KH.get("box_height_in", 24) / 12 - 0.06 - 0.02   # underside of the hood's stainless top
PP = [21.375, 10.5625, 11.4375]                    # Broan PM600SSV power pack, W x H x D in
HZ = 10.95                                         # centre of the duct through the wall: its top is about 6 in under the roof, clear of the SIP top plate
CAP = [12, 12, 7]                                  # 8 in wall cap with a damper, W x H x D in (ASSUMED)
CAP_Z = HZ - CAP[1] / 24
assert CAP_Z + CAP[1] / 12 < roof_under_s(HY + CAP[0] / 24) - 1 / 12, "wall cap hits the rake overhang"
VIDEO = ["Video Maxwell picked: kitchen hood design", "https://www.youtube.com/watch?v=Qs4wis82NAE"]
exhaust("ex_hood", "Range hood duct", 8, [[HX, HY, HOOD_TOP], [HX, HY, HZ], [-0.06, HY, HZ]], room="Kitchen",
        note="8 in smooth galvanized duct from the top of the power pack, up the chimney enclosure, one elbow just under the ceiling, then straight west through the "
             "SIP wall to the wall cap under the rake overhang. 8 in, not 6 in: the video's point that a 6 in duct chokes the real airflow, and the PM600SSV only "
             "reaches its top speed on 8 in. A range hood may not connect to the ERV or the return: the Ohio residential code (1503.3) requires its own smooth, "
             "air tight metal duct to the outdoors with a backdraft damper, and never into an attic or soffit. Where it passes the wall: a galvanized sleeve "
             "through the SIP, the foam cut back and sealed with the SIP maker's sealant and tape, the hole clear of the top plate and panel splines, and the "
             "sleeve flashed into the rain screen wrap behind the siding. Insulspan should confirm the hole and its spot.")
ducts[-1]["info"]["specs"] = [["Duct", "8 in round, smooth galvanized, one elbow, about 6 ft"], ["Wall", f"West wall, centre {ftin_(HZ)} up, through the 6-1/2 in SIP"],
                              ["Outside", "8 in wall cap with a damper, under the rake overhang"]]
ducts[-1]["info"]["links"] = [VIDEO]
items += [
 dict(id="hood_insert", name="Range hood power pack", category="Ventilation", system="hvac.exhaust", room="Kitchen", layer="appliances",
      builder="power_pack", size=PP, at=[WALL_X + 0.12, HY, round(HOOD_TOP - PP[1] / 12, 3)], facing=90,
      info=dict(model="Broan Elite PM600SSV power pack insert with SmartSense (suggested, not bought)", price="$789 list (Broan, 11/20/2026)",
        specs=[["Airflow", "HVI certified, up to about 600 CFM on 8 in duct (650 max blower), 4 speeds"], ["Noise", "0.5 sone on normal speed"],
               ["Auto", "SmartSense: an infrared sensor watches the cooktop, turns the fan on, sets its speed and turns it off"],
               ["Filter", "Hybrid baffle, dishwasher safe"], ["Duct", "8 in round up (also 6 in, or 3-1/4 x 10)"], ["Height", "24 in minimum over the cooktop"],
               ["Size", "21-3/8 W x 10-9/16 H x 11-7/16 D in"]],
        links=[["Broan PM600SSV", "https://broan-nutone.com/en-us/product/rangehoods/pm600ssv"],
               ["Spec sheet", "https://www.broan-nutone.com/getmedia/1c978a98-1157-487e-b676-739b3a1f9407/Spec_Sheet_PM600SSV_en_fr_2.pdf"], VIDEO],
        notes=["Picked to the video's advice (Maxwell, 11/20/2026): the SmartSense unit the video shows, so the hood runs every single time someone cooks; "
               "HVI certified airflow and noise, not 'equivalent CFM'; very quiet on normal. The video's catch: high speed is loud because 600 CFM squeezes through "
               "a small screened grille. The big hood box around it is the fix: it holds the smoke so normal speed has time to catch it.",
               "The fan sits inside the hood, so the duct ends at a plain wall cap outside. A remote exterior blower would be quieter on high, but it loses the "
               "heat sensor that makes the hood run on its own.",
               "Ohio only requires makeup air over 400 CFM when a fuel burning appliance is inside, and this house is all electric. Still, this house is very tight, "
               "so on high crack the kitchen window, or add a makeup air damper later.",
               "Other HVI listed choices: Broan PM400SSV (450 CFM, 0.5 to 1 sone, 10 minute delay off, 6 in duct only, $564) or Broan PMA400SS (400 CFM, 1 sone, Energy Star)."],
        placement="At the top of the hood box, centred over the cooktop, its outlet straight under the chimney.")),
 dict(id="hood_cap", name="Range hood wall cap", category="Ventilation", system="hvac.exhaust", room="Exterior", layer="mechanical",
      builder="wall_cap", size=CAP, at=[-0.07, HY, round(CAP_Z, 3)], facing=270,
      info=dict(model="8 in wall cap with a spring or gravity damper, black, for range hoods (ASSUMED)",
        specs=[["Height", f"Centre {ftin_(HZ)} up, top about {round((roof_under_s(HY) - CAP_Z - CAP[1] / 12) * 12)} in under the roof"], ["Duct", "8 in"],
               ["Damper", "Built in, closes when the fan is off"]],
        notes=["Out the side of the house instead of through the roof (Maxwell, 11/20/2026), high on the west wall and tucked under the 12 in rake overhang, straight out from the hood.",
               "Code check (Ohio residential code 4101:8-15-01): the roof is an unvented SIP roof with no soffit vents, so nothing can draw the exhaust back in at the eave, "
               "and 1501.1 only bars discharging INTO an attic, soffit or ridge vent; a wall opening under an overhang is fine. It is about 6 ft from the kitchen door "
               "(3 ft required from operable doors and windows), about 8-1/2 ft from the kitchen window round the corner, and about 24 ft from the ERV's outdoor air "
               "intake on the same wall (10 ft required). It blows down, away from the path to the kitchen door (303.5.2: not onto walkways).",
               "Expect some grease film on the siding and the underside of the overhang over the years; the black trim hides it. Pick one whose louvre can be cleaned "
               "(303.6 wants 1/4 to 1/2 in openings on exhaust outlets). A cap with a fine bug screen would clog with grease."],
        placement="West wall, high, under the rake overhang, straight out from the cooktop.")),
]

# ERV ducts. The unit is drawn with two 6 in ports on each end (the Broan side port layout, ASSUMED): outdoor air and exhaust air on the wall end,
# stale air in and fresh air out on the room end. The unit lies with its long side east-west so the wall end meets the west wall.
# Outdoor side (Panasonic: 2 to 3 ft straight off each adapter, insulated ducts, separate hoods at least 10 ft apart).
# The exhaust runs 2.6 ft straight south, then turns west and out through the wall. The intake turns west as soon as it
# leaves the unit, meets the wall and runs level north along it, at the ERV's own height, to a hood 10 ft 10 in north of the
# exhaust hood (Maxwell, 11/18/2026: no more climbing to the roof and following it back down). It passes just over the
# geothermal risers and sits against the wall above the heat pump cabinet's height, so the floor of the service aisle stays open.
OA_Y = ERV_S + 2.6 - 10.8
OA_X = 0.85                                       # centre of the run along the west wall
assert HY - OA_Y >= 10, "ERV intake within 10 ft of the range hood outlet (4101:8-15-01 1504.3)"
ducts.append(dict(id="erv_wall_0", info_of="erv", type="erv", shape="round", size=8,
                  points=[[ERV_XF, ERV_S, ERV_Z], [ERV_XF, ERV_S + 0.6, ERV_Z], [OA_X, ERV_S + 0.6, ERV_Z], [OA_X, OA_Y, ERV_Z], [-0.05, OA_Y, ERV_Z]]))
ducts.append(dict(id="erv_wall_1", info_of="erv", type="erv", shape="round", size=8,
                  points=[[ERV_XS, ERV_S, ERV_Z], [ERV_XS, ERV_S + 2.6, ERV_Z], [-0.05, ERV_S + 2.6, ERV_Z]]))
# Fresh air leaves the room end, runs over the top of the heat pump beside the exhaust main, and drops into the supply plenum
# through a backdraft damper.
ducts.append(dict(id="erv_to_supply", info_of="erv", type="erv", shape="round", size=8,
                  points=[[ERV_XF, ERV_N, ERV_Z], [ERV_XF, HP_N - 1.4, ERV_Z], [ERV_XF, HP_N - 1.4, DECK + 1.9]]))

# ------------------------------------------------------------------ attic storage
# Black and yellow 27 gal hardware store totes on the attic deck, for a sense of scale (Maxwell, 11/19/2026). One row along the
# north side of the open deck the ducts leave north of the laundry and hall, two high where the roof is low. The walkway is
# everything south of the row, the tallest part of the attic, so it is comfortable to walk through (Maxwell, 11/19/2026: north row
# only for now, a second row may come later). Nothing sits on a duct or in the heat pump's service space.
TOTE = [20.1, 14.4, 30.4]                         # W x H x L in, lid on (HDX / Commander 27 gal tough tote, about 30 x 20 x 14 in)
TOTE_GAP = 4.0 / 12                               # between stacks, so each one can be pulled out
def roof_under(y): return CFG["roof"]["north_wall_height"] + y * CFG["roof"]["north_pitch"] / 12 - 0.9   # underside of the north roof SIP
def tote_row(x0, x1, y_back, facing, count):
    w = TOTE[0] / 12; n = int((x1 - x0 + TOTE_GAP) // (w + TOTE_GAP)); pitch = w + TOTE_GAP
    xs = [(x0 + x1) / 2 + (k - (n - 1) / 2) * pitch for k in range(n)]
    return [[round(x, 3), y_back, facing, count] for x in xs]
TOTE_N_BACK = 14.3                                # back edge: south of the trunk, the bed 1 return and the hall takeoffs (y 13.25)
STACKS = tote_row(5.8, 26.07, TOTE_N_BACK, 180, 2)
TOTE_CX, TOTE_CY = 16.0, TOTE_N_BACK
for x, y, f, k in STACKS:                         # every stack clears the underside of the roof at its low (north) edge
    assert roof_under(y) - DECK - k * TOTE[1] / 12 > 1.5 / 12, (x, y, k)
N_TOTES = sum(s[3] for s in STACKS)
WALK_N = TOTE_N_BACK + TOTE[2] / 12               # front of the row
WALK_S = CFG["ceilings"]["flat_rooms"][4][3]      # attic wall over the living room
CLR_N = min(roof_under(s[1]) - DECK - s[3] * TOTE[1] / 12 for s in STACKS) * 12
def ftin(v): return f"{int(v)} ft {round((v - int(v)) * 12)} in"
items.append(dict(id="attic_totes", name="Storage totes", category="Storage", system="storage", room="Attic", layer="storage",
    builder="tote_stacks", size=TOTE, at=[TOTE_CX, TOTE_CY, DECK], facing=180,
    stacks=[[round(x - TOTE_CX, 3), round(y - TOTE_CY, 3), f, k] for x, y, f, k in STACKS],
    info=dict(model=f"{N_TOTES} black and yellow 27 gal tough totes, for scale", price="About $15 each at a hardware store",
        specs=[["Tote", "About 30 x 20 x 14-1/2 in with the lid on, 27 gal"],
               ["Row", f"{len(STACKS)} stacks, 2 high, clearing the roof by about {CLR_N:.0f} in at the back"],
               ["Walkway", f"About {ftin(WALK_S - WALK_N)} wide south of the row, {ftin(roof_under(WALK_N) - DECK)} of headroom at the totes rising to {ftin(roof_under(WALK_S) - DECK)} at the south wall"],
               ["Spacing", "4 in between stacks so any one can be pulled out"]],
        notes=["Shows how much fits along the north side of the open deck north of the laundry that the ducts leave free (Maxwell, 11/19/2026). Not packed tight. "
               "The row is held to 2 high because the roof comes down to about 2-1/2 ft over the deck there.",
               "North row only for now, so the walkway takes the south side, the tallest part of the attic (Maxwell, 11/19/2026). A second row may be added later.",
               "The walkway runs east to west and opens at the west end by the heat pump, so the totes never block its service aisle or a duct. "
               "Getting from the walkway to the heat pump's west side still means stepping over the bedroom 1 return, which lies on the deck there.",
               "Weight: a full tote of household things is roughly 30 to 50 lb. The deck is on 24 in open web trusses; ask the truss maker for the attic storage load they were designed for."],
        placement="On the attic deck over hall 2 and the laundry, against the supply trunk along the north side.")))

# ------------------------------------------------------------------ server rack (Maxwell, 11/20/2026: a 19 in rack in the attic, floor standing, about half height)
# A 22U four post open frame rack (half of a full 42U) on casters, standing on a plywood pad at the west end of the attic walkway, its back
# to the main return's deck duct and its front facing north into the walkway. RACK_SPOT picks one of the spots looked at, for renders.
RACK = [23.6, 46.5, 31.5]                         # W x H x D in: 600 x 800 mm frame, 22U of rails, about 43-1/2 in of frame on 3 in casters
RACK_PAD = [38.0, 0.75, 36.0]                     # 3/4 in plywood pad under it, W x T x D in
RACK_SPOTS = {
    "west_walkway": dict(at=[10.0, 22.75], facing=0, room="Attic, west end of the walkway",
        where="At the west end of the attic walkway, over the bedroom 3 and utility room wall, back to the main return duct, front facing north into the walkway."),
    "utility_attic": dict(at=[10.3, 32.7], facing=0, room="Attic over the utility room",
        where="In the tall attic over the utility room and pantry, east of the water heater ducts, front facing north."),
}
_rs = RACK_SPOTS[os.environ.get("RACK_SPOT", "west_walkway")]
RACK_X, RACK_YB = _rs["at"]
RACK_YF = RACK_YB - RACK[2] / 12 if _rs["facing"] == 0 else RACK_YB + RACK[2] / 12
_rack_top = RACK_PAD[1] + RACK[1]
RACK_HEAD = min(roof_under(RACK_YB), roof_under(RACK_YF)) - DECK - _rack_top / 12      # clearance over the top at its low edge
assert RACK_HEAD > 4 / 12, RACK_HEAD
items.append(dict(id="server_rack", name="Server rack", category="Network", system="lowvolt.network", room=_rs["room"].split(",")[0], layer="mechanical",
    builder="server_rack", size=RACK, pad=RACK_PAD, at=[RACK_X, RACK_YB, DECK], facing=_rs["facing"], units=22,
    gear=[[22, 1, "patch", "24 port Cat 6 patch panel"], [21, 1, "switch", "24 port network switch"], [20, 1, "manager", "Cable manager"],
          [18, 1, "router", "Router or firewall"], [16, 1, "shelf", "Shelf: modem or ONT, mini PCs"], [13, 2, "server", "2U server"],
          [10, 4, "nas", "4U storage server"], [2, 2, "ups", "2U UPS"]],
    info=dict(model="22U four post open frame rack on casters, 19 in rails, about 24 W x 32 D x 46-1/2 H in (ASSUMED, any 12U to 22U fits here)",
        price="About $150 to $350 for the rack, $20 for the plywood pad",
        specs=[["Size", "22U, half of a full 42U rack. Rails adjust for gear 22 to 40 in deep"],
               ["Headroom", f"About {RACK_HEAD * 12:.0f} in over the top at its low (north) edge, {(roof_under(RACK_YB) - DECK) * 12 - _rack_top:.0f} in at the back"],
               ["Service", "About 3 ft clear in front (the walkway); casters let it roll out to reach the back"],
               ["Power", "Its own 20 A circuit to a receptacle on the wall beside it, through a 2U UPS"],
               ["Cables", "Home runs drop straight down into the wall under its back, then to every data jack"],
               ["Gear shown", "Example only, for scale: patch panel, switch, router, servers, shelf, UPS"]],
        notes=["Why here: it is the tallest part of the walkway's floor that nothing else needs, so it blocks no path (the heat pump aisle is about 4 ft west of it) and "
               "the walkway in front of it is its service space. You reach it from the loft access by walking the length of the walkway, never stepping over a duct.",
               "Cables: the wall between bedroom 3 and the utility room runs right under its back edge, so the home runs go down through that wall's top plate "
               "(a 2 in grommet or a short sleeve) and the utility room, where the internet service and the electrical panel are most likely to land, is one wall away. "
               "Leave a pull string and a spare sleeve for later.",
               "Heat: a small home rack gives off roughly 200 to 600 W all the time. The attic is inside the conditioned envelope but has no return of its own, so "
               "that heat mostly sits up here. The heat pump water heater's intake is about 4 ft south, over the return duct, and it pulls attic air whenever it "
               "runs, which turns some of the rack's heat into hot water. If the gear grows, the easy fix is a small return grille in the side of the main return's "
               "drop box right behind the rack (a question for Andy, it changes the duct balance).",
               "Weight: a loaded 22U rack can reach 300 to 500 lb on about 4 sq ft. The plywood pad spreads it across the trusses at x 8.7 and 10.7; ask the truss maker "
               "what concentrated load the attic deck takes before loading it heavily.",
               "Headroom is crouching height (about 4-1/2 ft at the front rising to 5-1/2 ft at the back), fine for a rack you work on kneeling. The other spot looked at, "
               "over the utility room, has standing room but means climbing over the 14 in tall main return duct to reach it.",
               "For Home Assistant later: a UPS with a network card or USB reports power and runtime, and a temperature sensor on the rack shows how warm the attic gets."],
        placement=_rs["where"])))
items.append(dict(id="server_rack_outlet", name="Rack receptacle", category="Outlet", system="electrical", room="Attic", layer="electrical",
    builder="wall_box", size=[2.75, 4.5, 0.3], at=[11.64, 23.1, DECK + 1.5], facing=270,
    info=dict(model="20 A duplex receptacle on its own circuit (ASSUMED)",
        specs=[["Height", "18 in above the attic deck"], ["Circuit", "Dedicated 20 A, 120 V"]],
        notes=["Not on U-12: added for the server rack (Maxwell, 11/20/2026). On the attic side of the wall east of the rack, just north of the main return grille. "
               "The UPS plugs in here and everything in the rack plugs into the UPS."],
        placement="Attic, wall east of the server rack.")))

# ------------------------------------------------------------------ ceiling fans (Maxwell, 11/19/2026): every bedroom, the study and the family room
# Each bedroom fan has an LED light kit and takes the place of that room's ceiling light: one fan rated box per room, which
# is what a vaulted SIP ceiling wants. The baked light fixture goes (meta replace_nodes) and its night light moves to the kit.
# The family room keeps its recessed cans, so its fan has no light. Blades sit about 8 1/2 ft up in the vaulted rooms, at
# least a foot below the ceiling on the low side; in bedroom 3 under the flat 9 ft ceiling the fan hangs on a short rod.
# A fan's "at" is its canopy on the ceiling; size = [blade sweep, canopy to blade plane, both in], slope = ceiling rise per
# foot going north (the north roof falls toward the north wall, the south roof rises toward the clerestory).
_R = CFG["roof"]
_PN, _PS = _R["north_pitch"] / 12, _R["south_pitch"] / 12
_HD = CFG["house"]["depth_y"]
def ceiling_at(x, y):
    if any(a <= x <= c and b <= y <= d for a, b, c, d in FLAT):
        return CEIL, 0.0
    if y <= YC2:
        return _R["north_wall_height"] + y * _PN, -_PN
    return _R["south_wall_height"] + (_HD - y) * _PS, _PS
FAN_META = dict(replace_nodes=[], lights_moved={})
SLOPE_NOTE = ("On the sloped ceiling the fan needs a fan rated box fixed to the roof panel and a canopy that takes the slope (about 18 degrees under the "
              "3.82:12 north roof; most fans allow 30). In a SIP roof the box and the wire chase to it have to be planned with the panel maker before the "
              "panels are cut, because there is no stud cavity to fish a cable through later. ASSUMED until the electrician and the SIP maker agree.")
HA_NOTE = ("For Home Assistant later: a DC fan with a local network control, or a radio remote fan run through a bridge such as Bond, so speed, "
           "direction and the light can be automated. Model ASSUMED.")
def fan(id, room, x, y, sweep, blade_z, light, notes, light_name=None, blades=3):
    c, slope = ceiling_at(x, y)
    drop = round((c - blade_z) * 12, 1)
    rod = max(0.0, drop - 9.0)                               # canopy, ball and motor take about 9 in
    low = c - sweep / 24 * abs(slope) - blade_z              # blade tip to the ceiling on the low side
    specs = [["Size", f"{sweep} in, {blades} blades"], ["Blades", f"{blade_z * 12 // 12:.0f} ft {blade_z * 12 % 12:.0f} in above the floor, {low * 12:.0f} in below the ceiling at the low side"],
             ["Downrod", f"About {rod:.0f} in" if rod > 3 else "Close mount on a short rod"], ["Motor", "DC, 6 speeds and reverse, wall control or remote"]]
    if light:
        specs.append(["Light", "Dimmable LED light kit, about 1,600 lumens, the room's ceiling light"])
    if slope:
        specs.append(["Mount", f"Sloped ceiling, {abs(slope) * 12:.2f}:12"])
    items.append(dict(id=id, name="Ceiling fan" + (" with light" if light else ""), category="Ceiling fan", system="electrical.fans", room=room, layer="fans",
        builder="ceiling_fan", size=[sweep, drop], at=[x, y, round(c, 3)], facing=0, slope=round(slope, 4), blades=blades, light=bool(light),
        info=dict(model=f"{sweep} in DC ceiling fan, matte black with light oak blades" + (", LED light kit" if light else "") + " (ASSUMED)",
                  specs=specs, notes=notes + ([SLOPE_NOTE] if slope else []) + [HA_NOTE],
                  placement=f"Ceiling of {room}, x {x:.1f} ft, y {y:.1f} ft.")))
    if light_name:
        FAN_META["replace_nodes"] += [f"{light_name} base".replace(" ", "_"), f"{light_name} lens".replace(" ", "_")]   # three.js names, spaces as _
        FAN_META["lights_moved"][light_name] = [x, y, round(blade_z - 0.45, 2)]

fan("fan_bed1", "Bedroom 1", 37.6, 6.6, 52, 8.5, True, ["Over the middle of the bed, so on a warm night the downdraft reaches the bed without the light kit in your eyes from the pillows."], "Light Bed1 10")
fan("fan_bed2", "Bedroom 2", 11.0, 5.6, 44, 8.5, True, ["Where the ceiling light was, just off the foot of the bed. 44 in suits a room of about 100 sq ft."], "Light Bed2 11")
fan("fan_bed3", "Bedroom 3", 8.7, 17.0, 48, 8.15, True, ["On a fan rated pancake box screwed to the bottom chord of the truss at x 8.7. The bay beside it (x 7.7) "
    "carries the 10 in bedroom 2 and 3 return right on top of the drywall, so a deeper box cannot go there. Moved about 2 ft east of the old light so the blade tips "
    "stay about 2 1/2 ft clear of the ceiling supply register at x 3.7: blades passing through a register's jet push its air back up and make it sound louder."], "Light Bed3 12")
fan("fan_study", "Bedroom 4 / study", 27.4, 5.6, 42, 8.5, True, [
    "A smaller fan, over the desk chair, in place of the ceiling light. It hangs about 5 ft out from the door wall, where the two supply registers and the "
    "returns are, and the blades are about 2 1/2 ft lower than the registers.",
    "How it helps the air: the supply comes in high at the door wall and throws along the sloped ceiling toward the window, and the returns are in the same wall. "
    "In cooling, forward (downdraft) pulls that supply air down over the chair and the computers before it comes back, and the breeze lets the thermostat sit a "
    "degree or two warmer. In heating, warm air stays up under the high side of the ceiling by the high return; the fan on low in reverse (updraft) turns the "
    "air over the whole room.",
    "Warm air from the computers rises toward the high side, where the high return is. The fan mixes; it does not move air out of the room. The supply and "
    "returns still do that, so this is a companion to the ducts, not a fix for an undersized one."], "Light Study 13")
fan("fan_living", "Living", 23.89, 28.75, 60, 10.0, False, ["Trial fan (Maxwell, 11/19/2026: try one, it may come out later). Centred over the living room "
    "itself, x 16.66 to 31.12 and y 22.87 to 34.62, leaving out the loft side (Maxwell, 11/20/2026). The blade tips pass about 5 in from the flush ceiling "
    "light at x 21.0 in plan, though 8 ft below it; if the light flickers through the blades, move that light toward the west wall. The ceiling here is about 18 ft, so it hangs on a long "
    "rod with the blades about 10 ft up. In winter, on low in reverse, it pushes the warm air that collects up under this tall ceiling back down to the seating."])
fan("fan_family", "Entry / family", 36.5, 42.5, 60, 9.0, False, ["Between the entry and the family cans (both about 4 ft away), so the blades never pass under a light and flicker it. "
    "60 in for the open family and entry area; the high wall registers on the clerestory wall blow south toward it from about 5 ft beyond the blade tips."])

# ------------------------------------------------------------------ ceiling lights (Maxwell, 11/20/2026)
# The baked ceiling lights sat level under ceilings that mostly slope, so one edge hung below the drywall, and the old
# flush mounts were domes. Every one is now a slim flat LED wafer (a canless recessed light: a thin trim ring and a flat
# lens), seated on its own ceiling and tilted to it. tools/electrical/ceiling.mjs finds each ceiling's height and slope
# (model/data/ceiling_lights.json); the baked fixture goes (meta replace_nodes) and its night light moves to the wafer.
# The bath 1 lights were baked up in the loft from before the loft went in over the bath; they now sit on its 9 ft ceiling.
_CL_P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ceiling_lights.json")
_CL = json.load(open(_CL_P)) if os.path.exists(_CL_P) else {}
_CL_ROOM = {"Bath1": "Bath 1", "Bath1 shower": "Bath 1 shower", "Bath1 toilet": "Bath 1 toilet", "Bath2": "Bath 2"}
_n_cl = 0
for _L in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "manifest.json"))).get("lights", []):
    _nm = _L["name"]
    if not _nm.startswith("Light ") or _nm in FAN_META["lights_moved"] or _nm not in _CL:
        continue
    _x, _y = round(_L["pos"][0] / 0.3048, 3), round(-_L["pos"][1] / 0.3048, 3)
    _z, _sl = _CL[_nm]
    _big = _L.get("intensity_lm", 800) >= 1200                  # the old flush mounts: an 8 in wafer, the cans 6 in
    _n_cl += 1
    _rm = _CL_ROOM.get(_L["room"], _L["room"])
    _specs = [["Size", "8 in" if _big else "6 in"], ["Light", f"About {_L.get('intensity_lm', 800):,} lumens, warm white, dimmable"],
              ["Ceiling", f"{_z:.2f} ft" + (f", sloped {abs(_sl) * 12:.2f}:12" if abs(_sl) > 0.001 else ", flat")]]
    items.append(dict(id=f"can_light_{_n_cl:02d}", name=("Recessed light, 8 in" if _big else "Recessed light, 6 in"), category="Lighting",
        system="electrical.lighting", room=_rm, layer="electrical", builder="can_light", size=[7.9 if _big else 6.7, 0.5],
        at=[_x, _y, _z], facing=0, slope=_sl,
        info=dict(model="Slim canless LED wafer downlight with a flat lens, junction box beside it (ASSUMED)", specs=_specs,
            notes=["Positions are ASSUMED (the model's lighting plan, not on U-11). Flush with the ceiling and tilted to it. A wafer light needs only about "
                   "1 in of depth, which suits the SIP roof panels where a can would not fit; its wiring and box still have to be planned with the panel maker."],
            placement=f"Ceiling of {_rm}, x {_x:.1f} ft, y {_y:.1f} ft.")))
    FAN_META["replace_nodes"] += [f"{_nm} {p_}".replace(" ", "_") for p_ in ("base", "lens", "trim")]
    FAN_META["lights_moved"][_nm] = [_x, _y, round(_z - 0.3, 2)]

# ------------------------------------------------------------------ study temperature sensor
# The booster fan, motorized damper and their outlet box were removed (Maxwell, 11/19/2026): two wall registers carry the load on
# their own. The sensor spot stays, because it shows whether the fixed airflow is right and is what a later motorized damper would use.
items += [
 dict(id="study_temp_sensor", name="Study temperature sensor spot", category="Controls", system="controls", room="Bedroom 4 / study", layer="mechanical",
      builder="wall_box", size=[2.75, 2.75, 0.9], at=[23.04, 8.6, 4.9], facing=90, sensor=True,
      info=dict(model="Wall temperature sensor for Home Assistant, battery or low voltage (ASSUMED)",
        specs=[["Height", "About 5 ft, the thermostat height"], ["Where", "West wall by the door, away from the desk, the window and the supply jets"]],
        notes=["A low voltage cable or a box here at rough in keeps the option of a wired sensor. A battery Zigbee or Thread sensor works with no wiring.",
               "For Home Assistant later: it shows how far the study runs from the thermostat's reading with the computers on, which says how to set the two hand "
               "dampers each season, and it is the input a motorized damper would need if one is added in the attic."])),
]

# ------------------------------------------------------------------ electrical and low voltage (sealed sheets U-11 and U-12)
# Device positions were read from the vector symbols on Andy's sealed utility plans (06/14/2026) by tools/extract_electrical.py,
# into model/data/electrical_plan.json. Plain outlets sit at 16 in per the U-11 legend (Maxwell, 11/19/2026); the labelled
# ones (44 in GFI, 24 in GFI, 72 in TV) keep their own heights. Switches 44 in per the legend.
_EP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "electrical_plan.json")))
_SNAP_P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "electrical_snap.json")
_SNAP = json.load(open(_SNAP_P)) if os.path.exists(_SNAP_P) else {}   # tools/electrical/snap.mjs: ft to move each wall device onto the finished wall
_ROOMS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "house.json")))["meta"]["rooms"]
LOFT_FLOOR = next(r.get("floor") for r in _ROOMS if r["name"] == "Loft")
def _room(x, y, level):
    if level == "upper":
        a, b, c, d = LOFT
        return "Loft" if a <= x <= c and b <= y <= d else "Attic"
    if 0.5 <= x <= 12.12 and 28.241 < y <= 29.03:   # the utility room really ends at 28.241 (traced A-11); the strip south of it is the pantry and powder
        return "Pantry" if x < 5.6 else "Powder"
    if 30.25 <= x <= 31.12 and 10.7 <= y <= 15.03:   # bedroom 1's L, west of its main rectangle (A-11; door wall moved to x 30.25, Maxwell 11/19/2026)
        return "Bedroom 1"
    for r in _ROOMS:
        a, b, c, d = r["rect"]
        if not r.get("upper") and a <= x <= c and b <= y <= d and not r.get("outside"):
            return r["name"]
    return "Outside"
def _roof_under(y):
    return (_R["north_wall_height"] + y * _PN) if y <= YC2 else (_R["south_wall_height"] + (_HD - y) * _PS)
_SHEET = "Andy Roehl's sealed utility plans, 06/14/2026: "
_FIELD = "The sheet says outlet locations get confirmed with the owner in the field, so the electrician's rough in wins over this."
_FACE = {0: "north", 90: "east", 180: "south", 270: "west"}
_n = {}
def _eid(kind):
    _n[kind] = _n.get(kind, 0) + 1
    return f"elec_{kind}_{_n[kind]:02d}"
# The stick vacuum's charger outlet (PR 40) is not on U-11: it is added here so the Electrical layer has every outlet,
# and the vacuum builder only draws the charger plugged into it.
VAC_OY = VAC_Y - 7 / 12
_EP["devices"].append(dict(kind="outlet", x=VAC_WALL, y=round(VAC_OY, 3), z_in=18, facing=270, level="main", src="added #vacuum",
    note="Not on U-11. Added for the stick vacuum's charger in the hall closet, just north of its dock (Maxwell, 11/19/2026: the vacuum moved here from the utility room)."))
_tagq = []
def _tag(n0=None, src=None):                    # every electrical item carries its sheet symbol, for the snap tool
    if _tagq:
        a, sr = _tagq.pop()
        for it_ in items[a:]:
            it_["src"] = sr
    if n0 is not None:
        _tagq.append((n0, src))
for dv in _EP["devices"]:
    _tag(len(items), dv["src"])
    k, x, y, lvl = dv["kind"], dv["x"], dv["y"], dv["level"]
    _s = _SNAP.get(dv["src"], 0.0)
    if _s and dv.get("facing") in (0, 90, 180, 270):
        _ux, _uy = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}[dv["facing"]]
        x, y = round(x + _ux * _s, 3), round(y + _uy * _s, 3)
    _f = dv.get("facing")                         # look up the room just in front of a wall device, not in the wall
    _dx, _dy = {0: (0, -0.4), 90: (0.4, 0), 180: (0, 0.4), 270: (-0.4, 0)}.get(_f, (0, 0)) if k not in ("smoke", "floor_box") else (0, 0)
    room = "Outside" if dv.get("wp") else _room(x + _dx, y + _dy, lvl)
    floor = 0.0 if lvl == "main" else (LOFT_FLOOR if room == "Loft" else DECK)
    sheet = "U-11 main level" if lvl == "main" else "U-12 upper level"
    notes = ([dv["note"]] if dv.get("note") else []) + ([_SHEET + sheet + f" utility plan (symbol {dv['src'].split('#')[1]}).", _FIELD] if dv["src"].startswith("U-") else [])
    wall = f"{_FACE.get(dv.get('facing'), '')} facing".strip()
    if k == "smoke":
        c = ceiling_at(x, y)[0] if lvl == "main" else _roof_under(y)
        items.append(dict(id=_eid("smoke"), name="Smoke and CO alarm", category="Electrical", system="electrical.life_safety", room=room, layer="electrical",
            builder="smoke_alarm", size=[5.5, 1.8, 5.5], at=[x, y, round(c, 3)], facing=0,
            info=dict(model="120 V combination smoke and carbon monoxide alarm, battery backup, interconnected (NFPA 72)",
                specs=[["Where", "Ceiling" if lvl == "main" or room == "Loft" else "Underside of the roof in the attic"], ["Power", "Hard wired, battery backup, interconnected"]],
                notes=notes + ["U-11 note 7: within 12 in of the ceiling, and keep it 3 ft from supply and return grilles."])))
        continue
    z_in = dv["z_in"]
    if k == "floor_box":
        items.append(dict(id=_eid("floor"), name="Floor outlet", category="Electrical", system="electrical.power", room=room, layer="electrical",
            builder="floor_box", size=[4.6, 0.15, 4.6], at=[x, y, 0.0], facing=0,
            info=dict(model="Flush floor box with a brass cover, 120 V duplex", specs=[["Where", "In the slab, dining room"]], notes=notes)))
        continue
    if k in ("outlet", "special"):
        volts = dv.get("volts", 240 if k == "special" else 120)
        kind = "Special outlet" if k == "special" else ("Outdoor outlet" if dv.get("wp") else ("240 V outlet" if volts == 240 else "Outlet"))
        tags = (" GFI" if dv.get("gfi") and not dv.get("wp") else "") + (" by the TV" if z_in == 72 else "")
        model = ("Weatherproof GFCI receptacle with an in use cover" if dv.get("wp") else
                 "240 V receptacle" if volts == 240 and k != "special" else
                 "Dedicated circuit for the equipment, sized to its nameplate, disconnect if it needs one" if k == "special" else
                 "Duplex receptacle, GFCI" if dv.get("gfi") else "Duplex receptacle, 120 V, tamper resistant")
        items.append(dict(id=_eid("outlet"), name=f"{kind}{tags}, {z_in} in", category="Electrical", system="electrical.power", room=room, layer="electrical",
            builder="outlet", size=[2.75, 4.5, 0.3], at=[x, y, round(floor + (z_in - 2.25) / 12, 3)], facing=dv["facing"],
            gfi=bool(dv.get("gfi")), wp=bool(dv.get("wp")), volts=volts,
            info=dict(model=model, specs=[["Height", f"{z_in} in to the centre" + (" (U-11 legend)" if z_in == 16 else "")], ["On", f"The {wall} wall" if wall else "Wall"]],
                notes=notes)))
        continue
    if k == "switch":
        gangs = dv.get("gangs", 1)
        items.append(dict(id=_eid("switch"), name=f"{gangs} gang light switch, 44 in" if gangs > 1 else "Light switch, 44 in", category="Electrical", system="electrical.lighting", room=room, layer="electrical",
            builder="switch_plate", size=[2.75 + 1.81 * (gangs - 1), 4.5, 0.3], gangs=gangs, at=[x, y, round(floor + (44 - 2.25) / 12, 3)], facing=dv["facing"],
            info=dict(model=(f"{gangs} gang plate of rocker switches with dimmers" if gangs > 1 else "Wall switch with a dimmer (U-11 legend)"), specs=[["Height", "44 in to the centre"], ["On", f"The {wall} wall"]],
                notes=notes + ["U-11 marks some of these 3-way or 4-way. Which ones switch which lights is on the sheet's dashed lines, not modelled here."])))
        continue
    if k in ("data", "tv_data"):
        items.append(dict(id=_eid("data"), name=("TV network outlet, 72 in" if k == "tv_data" else f"Network outlet, {z_in} in"), category="Low voltage",
            system="low_voltage", room=room, layer="lowvolt", builder="data_jack", size=[2.75, 4.5, 0.3], at=[x, y, round(floor + (z_in - 2.25) / 12, 3)], facing=dv["facing"],
            info=dict(model="Two port network outlet, CAT-6 (U-11 draws cable TV and CAT-5; CAT-6 costs about the same now)",
                specs=[["Height", f"{z_in} in to the centre"], ["Jacks", "Two network jacks, no coax"]],
                notes=notes + ["No coax anywhere in the house (Maxwell, 11/19/2026): each U-11 cable TV and CAT-5 outlet becomes two network jacks, each with its own cable back to the network spot.", "Every network cable runs back to one spot. U-11 does not say where; the utility room or the mechanical platform by the electric panel are the usual choices."])))
        if k == "tv_data":
            tv = dv.get("tv", False)
            ty = 30.65 if tv else y                    # the living room TV centres between its outlet and data jack
            items.append(dict(id=_eid("tv"), name="65 in TV on its wall mount" if tv else "TV mount", category="Low voltage", system="low_voltage", room=room, layer="lowvolt",
                builder="tv_mount", size=[24, 16, 1.6], tv=[57.1, 32.7, 1.1] if tv else None, at=[x, ty, round(floor + 72 / 12 - 8 / 12, 3)], facing=dv["facing"],
                info=dict(model="Flat screen TV mount at 72 in, wall blocking behind it, 2 in sleeve down to a single gang box (U-11 legend)",
                    specs=[["Height", "72 in to the TV centre, confirm with the owner"], ["Blocking", "Needed in the wall before drywall"]],
                    notes=notes + ["The bracket is drawn generic: the TV and its mount are not picked yet. A recessed power and cable box behind the TV hides the cords."]
                        + (["The TV is a generic 65 in set (about 57 x 33 in), the size Andy's site plan furniture shows. Its centre is at 72 in as U-11 draws it, which is high for watching from the couch; 42 to 48 in is more usual, so confirm before the blocking goes in."] if tv else []))))


# ------------------------------------------------------------------ site: planted trees, transformer, gravel drive
# Positions from [site_plantings] (traced from the 10/29/2026 drone photo). Each stands on the web terrain: heights come
# from model/data/terrain/web_ground.json, sampled off site.glb by tools/ground_grid.mjs.
SP = CFG.get("site_plantings")
if SP:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "terrain", "web_ground.json")) as _f:
        GG = json.load(_f)
    def ground(x, y):
        fx = (x - GG["x0"]) / GG["step"]; fy = (y - GG["y0"]) / GG["step"]
        i = max(0, min(GG["nx"] - 2, int(fx))); j = max(0, min(GG["ny"] - 2, int(fy)))
        tx, ty = min(1, max(0, fx - i)), min(1, max(0, fy - j)); z = GG["z"]
        return (z[j][i] * (1 - tx) + z[j][i + 1] * tx) * (1 - ty) + (z[j + 1][i] * (1 - tx) + z[j + 1][i + 1] * tx) * ty
    PHOTO = "Traced from Maxwell's drone photo of 10/29/2026 (DJI_0218), lined up on the four slab corners, so the spot is good to about a foot."
    def tree(id, name, kind, xy, h_ft, model, notes, seed):
        x, y = xy
        items.append(dict(id=id, name=name, category="Planted tree" if kind != "taxus" else "Planted shrub", system="site.plantings", room="Yard",
            layer="plantings", builder="conifer", kind=kind, seed=seed, size=[round(h_ft * 12 * (0.62 if kind == "spruce" else 0.7 if kind == "pine" else 1.25), 1), round(h_ft * 12, 1), 0],
            at=[round(x, 2), round(y, 2), round(ground(x, y), 3)], facing=(seed * 47) % 360,
            info=dict(model=model, specs=[["Height now", f"About {h_ft:g} ft, ASSUMED from the photo"]],
                      notes=notes + [PHOTO], placement=f"{round(x)} ft east and {round(-y)} ft north of the slab's NW corner.")))
    SPRUCE = "Norway spruce (Picea abies)"
    SPRUCE_NOTES = ["Grows about 1 to 2 ft a year once settled, to 40 to 60 ft tall and 25 to 30 ft wide. Drawn at planting size."]
    tree("tree_white_pine", "White pine", "pine", SP["white_pine"], SP["pine_height_ft"], "Eastern white pine (Pinus strobus)",
         ["West end of the line of five north of the house (Maxwell, 11/19/2026).", "Grows fast, to 50 to 80 ft tall and 20 to 40 ft wide. Drawn at planting size.",
          "Found in the photo by its long morning shadow, about 70 ft west of the first spruce, as Maxwell described."], 1)
    for k, xy in enumerate(SP["north_spruces"]):
        tree(f"tree_spruce_n{k + 1}", f"Norway spruce {k + 1} of the north row", "spruce", xy, SP["spruce_height_ft"], SPRUCE,
             ["One of four Norway spruces east of the white pine in the line north of the house (Maxwell, 11/19/2026)."] + SPRUCE_NOTES, 2 + k)
    for k, xy in enumerate(SP["east_spruces"]):
        tree(f"tree_spruce_e{k + 1}", f"Norway spruce {k + 1} by the woods", "spruce", xy, SP["spruce_height_ft"] * 1.1, SPRUCE,
             ["One of two Norway spruces east of the drive, by the woods (Maxwell, 11/19/2026)."] + SPRUCE_NOTES, 7 + k)
    for k, xy in enumerate(SP["taxus"]):
        tree(f"taxus_{k + 1}", f"Taxus {k + 1} of 7", "taxus", xy, SP["taxus_height_ft"], "Taxus (also sold as yew), variety not known",
             ["Seven taxus in a line along the woods edge, north to south (Maxwell, 11/19/2026).",
              "Every part of a taxus but the red flesh of the berry is poisonous to people, dogs and horses. Keep clippings away from animals."], 11 + k)
    tx, ty = SP["transformer"]
    items.append(dict(id="pad_transformer", name="Pad mounted transformer", category="Electric service", system="electrical.service", room="Yard",
        layer="site", builder="pad_transformer", size=[38, 34, 42], at=[tx, ty, round(ground(tx, ty), 3)], facing=SP.get("transformer_facing", 270),
        info=dict(model="Single phase pad mounted utility transformer, green, on a pad. Owned by the utility",
          specs=[["Size drawn", "About 38 W x 42 D x 34 H in on a 48 x 52 in pad, typical of 25 to 50 kVA units. ASSUMED"],
                 ["Clearances", "Utilities usually want about 10 ft clear in front of the doors and 3 ft at the sides and back. Check with the utility before planting closer."]],
          notes=["The green box at the south end of the taxus line (Maxwell, 11/19/2026). It feeds the house service underground.", PHOTO],
          placement=f"{round(tx)} ft east and {round(ty)} ft south of the slab's NW corner, doors toward the drive (ASSUMED).")))
    # gravel drive: a smooth centreline, cross sections every 2 ft laid on the ground with a shallow crown and shoulders
    cl = SP["drive_centerline"]; W = SP["drive_width_ft"]
    def cr(p0, p1, p2, p3, t):
        return tuple(0.5 * (2 * p1[i] + (-p0[i] + p2[i]) * t + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t * t + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t ** 3) for i in (0, 1))
    P = [cl[0]] + cl + [cl[-1]]
    dense = []
    for k in range(1, len(P) - 2):
        seg = ((P[k + 1][0] - P[k][0]) ** 2 + (P[k + 1][1] - P[k][1]) ** 2) ** 0.5
        n = max(1, int(seg / 1.0))
        dense += [cr(P[k - 1], P[k], P[k + 1], P[k + 2], t / n) for t in range(n)]
    dense.append(tuple(cl[-1]))
    st, acc, last = [dense[0]], 0.0, dense[0]           # resample about every 2 ft
    for q in dense[1:]:
        acc += ((q[0] - last[0]) ** 2 + (q[1] - last[1]) ** 2) ** 0.5; last = q
        if acc >= 2.0: st.append(q); acc = 0.0
    if st[-1] != dense[-1]: st.append(dense[-1])
    OFF = [(-W / 2 - 0.7, -0.06), (-W / 2, 0.12), (-W / 4, 0.14), (0, 0.15), (W / 4, 0.14), (W / 2, 0.12), (W / 2 + 0.7, -0.06)]   # (across ft, height above ground ft)
    rows, length = [], 0.0
    for k, (x, y) in enumerate(st):
        a, b = st[max(0, k - 1)], st[min(len(st) - 1, k + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]; L = (dx * dx + dy * dy) ** 0.5 or 1
        nx, ny = -dy / L, dx / L
        if k: length += ((x - st[k - 1][0]) ** 2 + (y - st[k - 1][1]) ** 2) ** 0.5
        rows.append([[round(x + nx * o, 2), round(y + ny * o, 2), round(ground(x + nx * o, y + ny * o) + h, 3)] for o, h in OFF])
    x0, y0, x1, y1 = SP["old_drive_cull"]
    items.append(dict(id="gravel_drive", name="Gravel drive", category="Site", system="site.drive", room="Yard", layer="site",
        builder="drive", size=[W * 12, 2, round(length * 12)], at=[0, 0, 0], facing=180, rows=rows,
        cull=[dict(box=[x0, y0, -30, x1, y1, 30], materials=["Gravel"])],
        info=dict(model="Gravel drive as built",
          specs=[["Width", f"About {W:g} ft"], ["Length", f"About {round(length / 10) * 10:.0f} ft from the road to the garage pad"],
                 ["Shape", "Straight south from the road, parallel to the woods, then a J loop round south of the garage and back north into the garage pad"]],
          notes=[PHOTO + " North of the photo it is drawn straight on to the road on the same heading.",
                 "It sits about 40 ft further west than the first model guessed, which put it 10 ft off the tree line."])))

_tag()
trusses = dict(id="floor_trusses", name="Open web floor trusses", category="Structure", system="structure.floor", regions=FLAT, loft_regions=[LOFT],
    z0=CEIL, depth_in=TRUSS_IN, spacing_in=CFG["floor_trusses"]["spacing_in"], deck_in=DECK_IN, grid_x0=TG, max_cross_in=CFG["floor_trusses"]["max_round_duct_in"],
    info=dict(model="11-7/8 in open web floor trusses",
      specs=[["Depth", "11-7/8 in (Maxwell, 11/16/2026)"], ["Clear for ducts", "About 8-7/8 in between the chords"], ["Floor top", f"{DECK:.2f} ft above the slab with 3/4 in decking"],
             ["Spacing", "24 in on centre on one grid across the house, ASSUMED"], ["Span", "North to south, continuous over the interior walls, ASSUMED"]],
      notes=["The attic deck and the loft floor sit on these, about 3 in higher in the attic and 2 in higher in the loft than the sealed plans.",
             "The loft railing, pony wall, ladder and furniture come from the last Blender export and still sit at the old height, about 2 in low, until the next export."]))

out = dict(
    meta=dict(units="plan feet for positions, inches for sizes", generated_by="model/make_equipment.py",
              sources=["M-10 mechanical plan 07/30/2026 (preliminary)", "U-11 and U-12 sealed utility plans", "Geo-Hydro quotes MMUL8476-4 and MMUL8476-5", "Appliance shortlist 11/15/2026"],
              **FAN_META),
    levels=[dict(id="main", name="Main floor", cut_ft=8.85), dict(id="truss", name="Floor trusses", cut_ft=round(CEIL + TRUSS_IN / 12 - 0.03, 2)),
            dict(id="upper", name="Loft and attic", cut_ft=16.0), dict(id="all", name="Whole house", cut_ft=None)],
    items=items, runs=runs, ducts=ducts, trusses=trusses)
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "equipment.json")
with open(path, "w") as f:
    json.dump(out, f, indent=1)
print(f"wrote {os.path.normpath(path)}: {len(items)} items, {len(runs)} pipe runs, {len(ducts)} ducts")
