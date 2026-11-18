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
      builder="cooktop_induction", size=[30.69, 3.69, 21.06], at=[0.74, 47.0, 3.127], facing=90,
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
# Geothermal: the five loops come up through the slab in one sleeve at the north wall, about 2 ft east of the west wall
# (Maxwell, 11/18/2026), fan out to the manifolds on the west wall, and the flow center sits further south on the same wall,
# right under the heat pump's water connections in the attic.
CON_X, CON_Y = 2.5, UN + 0.32
MAN_Y, MAN_Z = 24.3, 2.5                           # manifold centre along the wall, and the bottom of its valve legs
MAN_XS, MAN_XR = 0.56 + 2.6 / 12, 0.56 + 5.4 / 12  # supply header on the wall, return header in front of it
MAN_ZS, MAN_ZR = MAN_Z + 26 / 12, MAN_Z + 14 / 12  # header heights
FC_Y, FC_Z = 27.15, 3.0
# Hot water: both tanks stand off the south wall with a 5 in pipe lane behind them. The preheat tank is as far west as the flow
# center allows, right under the heat pump's hot water connections, so the desuperheater lines drop straight down behind it
# (Maxwell, 11/18/2026). The water heater is next to it, and its two ducts rise in truss bay 5.7, just east of the return plenum.
WH_X, PH_D = 6.2, 22.0
TANK_Y = US - 0.42 + 2 / 12                        # the tanks' back point (the builders put each tank 2 in in front of it)
PH_X = WH_X - ((24.25 + 4) / 24 + 0.25 + (PH_D + 4) / 24)   # preheat tank just west, drain pans 3 in apart
WH_DUCT_X = WH_X
# Heat pump: on the attic deck with its length north to south. Supply leaves the north end, the water, desuperheater and
# electrical connections are on the south end, the return and filter are on the east side, and the service panels face a
# 2 ft aisle along the west wall (exactly 2 ft from the wall face to the cabinet). Seen from the connection end the return is on the right: a right hand return unit.
HP_X, HP_Y = 4.31, 25.235                          # centre of the unit's east (return) face
HP_Z = DECK + 5.5 / 12
HP_AT = [HP_X, HP_Y, HP_Z]
HP_S, HP_N = HP_Y + 28 / 12, HP_Y - 28 / 12        # south (connection) end and north (supply) end
HP_CX = HP_X - 21.7 / 24                           # centreline of the cabinet
HP_PX = HP_X - 21.7 * 0.3 / 12                     # x of the water connections on the south end
items += [
 dict(id="geo_manifold", name="Geothermal loop manifolds", category="Geothermal", system="geothermal.loop", room="Utility", layer="mechanical",
      builder="pe_manifold", size=[30, 30, 8], at=[0.56, MAN_Y, MAN_Z], facing=90, mirror=True,
      info=dict(model="Geo-Hydro MPE532PS PE manifold set", price="$802.90 (quote MMUL8476-5, special order)",
        specs=[["Mains", "1-1/4 in PE"], ["Circuits", "5 x 3/4 in, each with a 1 in ball valve"], ["Piping", "Reverse return. Greg's summary has supply and return in separate 4 in sweeps with a 36 in radius"],
               ["Loop entry", "One sleeve through the slab at the north wall, about 2 ft east of the west wall. The ten pipes fan out from it to the valves"],
               ["Loop field", "5 loops of 3/4 in x 600 ft PE, 103.8 gal system volume"], ["Fluid", "20% propylene glycol (Fernox Alphi-11 with F1 inhibitor)"]],
        notes=["Layout on the wall is ASSUMED. Greg's summary gives the parts and the piping scheme, not a wall elevation.",
               "Raised so the valves sit about 2-1/2 ft off the floor and the loop pipes have room to bend up from the sleeve for fusing (Maxwell, 11/18/2026; Greg asked for the same).",
               "Ten 3/4 in PE pipes are 1.05 in across each, so they need about a 6 in sleeve. A 2 in conduit holds one. Shown as one 6 in sleeve until the size in the slab is confirmed."],
        placement="Northwest corner of the utility room, on the west wall (Maxwell, 11/15/2026).")),
 dict(id="flow_center", name="Geo-Flo flow center", category="Geothermal", system="geothermal.loop", room="Utility", layer="mechanical",
      builder="flow_center", size=[13, 22, 11], at=[0.56, FC_Y, FC_Z], facing=90,
      info=dict(model="Geo-Flo GF-1272 NP2, non pressurized, 2 pumps", price="$1,367.52 (quote MMUL8476-5)",
        specs=[["Pumps", "Two circulators"], ["Connections", "GF-2911 Flo-Link fusion set, 1-1/4 in"], ["Location", "First floor, per Greg's design summary"]],
        notes=[APPROX, "Kept on the west wall, which is an outside wall, so pump hum does not pass into bedroom 3 behind the north wall. "
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
        placement="South wall of the utility room (Maxwell, 11/15/2026), 5 in off the wall so the piping runs behind it. Its two ducts rise in one truss bay and come out on the attic deck just east of the return plenum.")),
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
        placement="South wall of the utility room, as far west as the flow center allows and directly under the heat pump's hot water connections.")),
]
# ---- geothermal piping. Loop entry sleeve, the ten loop pipes fanning out to the valve legs, the two mains to the flow
# center, then insulated 1-1/4 in lines straight up through the ceiling and deck and a short way across the attic.
runs.append(dict(id="geo_conduit", name="Loop entry sleeve", category="Geothermal", system="geothermal.loop", dia=6.6, mat="condensate",
    points=[[CON_X, CON_Y, 0.0], [CON_X, CON_Y, 0.5]],
    info=dict(model="PVC sleeve through the slab, shown at 6 in",
              specs=[["Carries", "All five loops: ten 3/4 in PE pipes, 1.05 in across each"], ["Where", "North wall, about 2 ft east of the west wall (Maxwell, 11/18/2026)"]],
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

# ---- domestic water. Everything runs in the lane behind the tanks or in the gap between them; nothing touches the wall line.
WR = 24.25 / 24                                    # water heater radius, ft
WH_CY, PH_Y = TANK_Y - (WR * 12 + 2) / 12, TANK_Y - (PH_D / 2 + 2) / 12     # tank centres
WCX = WH_X - (WR * 12 + 2.2) / 12                  # the water heater's side connections face the preheat tank
WC_Y, WHOT_Y = WH_CY + 1.6 / 12, WH_CY - 1.6 / 12  # cold in (low) and hot out (high)
WHOT_Z = (74.2 - 15.5 - 4) / 12
PH_TOP = 59.0 / 12 + 3 / 12                        # top of the preheat tank's brass nipples
GAP_X = WCX - 0.03                                 # the vertical pipes in the gap between the tanks
Y_COLD, Y_WALL = US - 0.39, US - 0.19              # cold line behind the preheat tank; recirculation return on the wall
Z_COLD = 6.9
X_SVC = PH_X - 0.74                                # cold service riser, behind the preheat tank's west side
HOT, HOT_R = 1.9, 1.5                              # 3/4 in and 1/2 in copper with pipe insulation, outside diameter
def dhw(id, name, dia, mat, points, model, notes, specs=None, info_of=None):
    r = dict(id=id, name=name, category="Hot water", system="plumbing.dhw", dia=dia, mat=mat, points=points)
    if info_of: r["info_of"] = info_of; r.pop("name")
    else: r["info"] = dict(model=model, specs=specs or [], notes=notes)
    runs.append(r)
dhw("dhw_cold", "Cold water to the preheat tank", 1.1, "copper",
    [[X_SVC, Y_COLD, 0.2], [X_SVC, Y_COLD, Z_COLD], [PH_X - 0.3, Y_COLD, Z_COLD], [PH_X - 0.3, PH_Y, Z_COLD], [PH_X - 0.3, PH_Y, PH_TOP]],
    "3/4 in copper", ["Cold service comes up through the slab behind the preheat tank, rises, and drops into the tank's cold inlet, about 9 ft of pipe. "
                      "The desuperheater return tees into the drop. Service entry point and valves ASSUMED."],
    specs=[["Valves", "Main shutoff at the riser, shutoff and union at the tank"], ["Expansion tank", "Hangs from a short stub off this line, as U-11 shows"]])
dhw("dhw_cold_house", None, 1.1, "copper", [[X_SVC, Y_COLD, Z_COLD], [X_SVC, Y_COLD, CEIL]], None, None, info_of="dhw_cold")
dhw("dhw_cold_stub", None, 1.1, "copper", [[X_SVC, Y_COLD, Z_COLD], [X_SVC - 0.6, Y_COLD, Z_COLD]], None, None, info_of="dhw_cold")
dhw("dhw_preheat", "Preheated water to the heat pump water heater", HOT, "foam",
    [[PH_X + 0.3, PH_Y, PH_TOP], [PH_X + 0.3, PH_Y, 5.5], [GAP_X, WC_Y, 5.5], [GAP_X, WC_Y, 0.75], [WCX, WC_Y, 0.75]],
    "3/4 in copper, insulated", ["Preheat tank hot outlet, across the gap between the tanks and down to the heat pump water heater's low side cold inlet, about 6 ft of pipe. "
                                 "The recirculation return tees in near the bottom. Bypass valves so either tank can be isolated are ASSUMED."])
dhw("dhw_hot", "Hot water to the house", HOT, "foam",
    [[WCX, WHOT_Y, WHOT_Z], [GAP_X, WHOT_Y, WHOT_Z], [GAP_X, WHOT_Y, CEIL]],
    "3/4 in copper, insulated", ["Heat pump water heater high side hot outlet, straight up through a thermostatic mixing valve into the ceiling and on to the fixtures."])
X_RC = PH_X + 0.76                                 # between the desuperheater drop and the gap between the tanks
dhw("dhw_recirc", "Hot water recirculation return", HOT_R, "foam",
    [[X_RC, Y_WALL, CEIL], [X_RC, Y_WALL, 1.2], [GAP_X, Y_WALL, 1.2], [GAP_X, WC_Y, 1.2]],
    "1/2 in copper, insulated", ["Return from the far end of the hot main (U-11 shows a recirculation pump). Comes down the south wall between the two tanks, through the pump at "
                                 "chest height, and tees into the water heater's cold inlet pipe. A check valve and a timer or demand control are ASSUMED.",
                                 "Insulated like the hot line: a recirculation loop is hot whenever it runs, so bare pipe would give that heat away all day."])
items += [
 dict(id="recirc_pump", name="Hot water recirculation pump", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="circ_pump", size=[5, 5, 5], at=[X_RC, Y_WALL, 3.9], facing=90,
      info=dict(model="Small inline circulator, bronze or stainless body (U-11)", specs=[["On", "The recirculation return where it comes down the south wall, about 4 ft off the floor"]],
                notes=["Model not picked. A timer or a push button demand control keeps it from running all day.", APPROX])),
 dict(id="expansion_tank", name="Thermal expansion tank", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="expansion_tank", size=[8, 11], at=[X_SVC - 0.5, Y_COLD, Z_COLD], facing=0,
      info=dict(model="2 gal potable thermal expansion tank (U-11 detail)", specs=[["On", "The cold line, after the main shutoff and any check valve"]], notes=[APPROX])),
 dict(id="mixing_valve", name="Thermostatic mixing valve", category="Hot water", system="plumbing.dhw", room="Utility", layer="mechanical",
      builder="mixing_valve", size=[3, 3, 3], at=[GAP_X, WHOT_Y, 6.3], facing=0,
      info=dict(model="3/4 in thermostatic mixing valve", specs=[["Why", "Lets both tanks store water hotter for more capacity while the taps get a safe 120 F"]],
                notes=["Its cold side tees off the cold line; that small tee is not drawn.", APPROX])),
]
# Desuperheater (Maxwell, 11/18/2026). The preheat tank stands right under the heat pump's hot water connections, so the two
# insulated 3/4 in lines step sideways off the ports and drop straight through the deck into the lane behind the tank.
# One goes to the tank's drain port (water to the geo), the other tees into the cold drop above the tank (water back).
DSH_Y = US - 0.29
PH_DRAIN = [PH_X + (PH_D / 2 + 1.7) / 12, TANK_Y - (PH_D / 2 + 2 - 4.8) / 12, 5.4 / 12]
for k in range(2):
    z = HP_Z + (9.6, 13.6)[k] / 12
    x = HP_PX + (0.27, -0.27)[k]
    start = [[HP_PX, HP_S + 0.07, z], [HP_PX, HP_S + 0.18, z], [x, HP_S + 0.18, z], [x, DSH_Y, z]]
    if k == 0: pts = start + [[x, DSH_Y, PH_DRAIN[2]], [PH_DRAIN[0], DSH_Y, PH_DRAIN[2]], PH_DRAIN]
    else: pts = start + [[x, DSH_Y, 6.15], [PH_X - 0.3, DSH_Y, 6.15], [PH_X - 0.3, PH_Y, 6.15]]
    runs.append(dict(id=f"dsh_{k}", name="Desuperheater lines", category="Hot water", system="plumbing.dhw", dia=1.6, mat="foam",
        info_of=None if k == 0 else "dsh_0", points=pts,
        info=dict(model="3/4 in copper or PEX with pipe insulation, to and from the geo's built in desuperheater pump",
                  specs=[["Supply to the geo", "From the preheat tank's bottom drain port"], ["Return from the geo", "Tees into the cold drop just above the preheat tank"],
                         ["Length", "About 5 ft and 10 ft: straight down from the heat pump's connections to the tank"]],
                  notes=["The preheat tank stands directly under the heat pump's hot water connections, so the lines drop straight through the attic deck into the lane behind the tank (Maxwell, 11/18/2026). "
                         "Route is ASSUMED. Line size and the maximum run come from the GZT installation manual."])))

# ------------------------------------------------------------------ attic: heat pump, ERV
# ERV: raised to the height of the heat pump's top, in line with it and just south of its piping, so its two room side ducts run
# straight over the top of the heat pump with no bends (Maxwell, 11/18/2026: it can go up, and the ducts should stay off the floor).
ERV_Z = HP_Z + 21.2 / 12 + 0.4                    # centre of the ERV's duct adapters, and of the two ducts over the heat pump
ERV_N = HP_S + 1.45                               # its room (north) end
ERV_S = ERV_N + 26.6 / 12                         # its outdoor (south) end
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
               "Turned 90 degrees (Maxwell, 11/18/2026): supply out the north end toward the trunk, water and desuperheater connections on the south end right above the flow center, "
               "return and filter on the east side, service panels facing a 2 ft aisle along the west wall."],
        placement="On the attic deck over the utility room, where Andy drew HP-01, lengthwise north to south.")),
 dict(id="erv", name="Energy recovery ventilator", category="HVAC", system="hvac.ventilation", room="Attic", layer="mechanical",
      builder="erv", size=[19.9, 11.4, 26.6], at=[HP_CX, ERV_N, ERV_Z - 5.7 / 12], facing=180, stand=round((ERV_Z - 5.7 / 12 - DECK) * 12, 1),
      info=dict(model="Panasonic Intelli-Balance 100 (ERV-01 on M-10)", specs=[["Airflow", "50 to 100 CFM balanced, boost from a bath timer switch"], ["Ducts", "Intake and exhaust through the west wall"],
               ["Stale air from", "Bath 1, bath 2 and powder exhaust grilles, 20 CFM each continuous, about 50 CFM on boost"], ["Fresh air to", "The supply plenum at the heat pump, so it reaches every room through the supply registers"], ["Mounting", "On a stand or hung on chains, about 2 ft above the deck"]],
        notes=["Greg's alternative: RenewAire EV Premium M, about $1,800.", APPROX,
               "The bathrooms exhaust through this unit instead of separate fans (Maxwell, 11/17/2026). The code allows it because the ERV sends that air outdoors; "
               "it has to run continuously at 20 CFM or more per bathroom (IRC table M1505.4.4).",
               "Fresh air goes into the supply plenum, not the attic (Maxwell, 11/18/2026). Panasonic's instructions say the furnace blower should run whenever the ERV runs when it is tied into "
               "the ductwork, and Building Science Corp. calls for an interlock and a motorized damper on a supply side connection. The heat pump's ECM blower can idle at low speed for this. "
               "Andy should confirm the ERV can push against the supply plenum's pressure; the fallback is the return plenum, which the code also counts as supply ventilation (IRC M1505.4.1).",
               "One fan pulls from all three bathrooms, so the whole exhaust duct is under suction and air cannot be pushed from one bathroom into another. Backdraft dampers are for "
               "separate fans that share a duct. Each branch gets a balancing damper to set its airflow.",
               "Panasonic: separate outdoor hoods go at least 10 ft apart, each duct connection wants 2 to 3 ft of straight run, and the unit must sit in conditioned space above 50 F. "
               "The two wall ducts are drawn 7 in apart here, so they need a combined hood made for the purpose or one of them moved. Open item. Three baths plus whole house ventilation (about 75 CFM for this size and bedroom count) "
               "is near the top of a 100 CFM unit, so Andy should confirm the size. The range hood cannot connect here, it has its own duct outdoors."],
        placement="In line with the heat pump, just south of it and raised to the height of its top. Andy drew it west of HP-01.")),
]

# ------------------------------------------------------------------ ducts
def supply(id, room, cfm, dia, points, grille=None, note=None, name=None):
    d = dict(id=id, name=name or f"Supply to {room}", category="HVAC supply duct", system="hvac.supply", room=room, type="supply", shape="round", size=dia, points=points,
             info=dict(model=f'{dia} in round, {cfm} CFM', specs=[["Airflow", f"{cfm} CFM (M-10)"], ["Duct", f"{dia} in round"]], notes=[note] if note else []))
    if grille: d["grilles"] = [grille]
    ducts.append(d)

XW, YN, YE, XJ = HP_CX, 12.0, 16.1, 27.07        # west leg x, north leg y, east leg y, jog x (against bedroom 1's west wall, x 28.12)
TRUNK_NOTE = ("Rerouted from M-10. Andy drew this trunk down the middle of the attic at y about 21.6 ft. Maxwell asked for it along the north wall of the attic, "
              "so it runs straight north from the heat pump with no turn (Maxwell, 11/18/2026), then along the north attic wall all the way to bedroom 1's west wall, follows that wall south, then runs east along bedroom 1's south wall (Maxwell, 11/17/2026: keep the middle of the attic free for storage). Size is Andy's 18 x 16 throughout, no reductions modelled.")
ducts.append(dict(id="supply_trunk", name="Supply trunk", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[18, 16],
    points=[[XW, HP_N - 2.0, ZTR], [XW, YN, ZTR], [XJ, YN, ZTR], [XJ, YE, ZTR], [41.2, YE, ZTR]],
    info=dict(model="18 x 16 in main trunk, 1,368 CFM", specs=[["Airflow", "1,368 CFM total"], ["Location", "On the attic deck against the north attic wall"]], notes=[TRUNK_NOTE])))
ducts.append(dict(id="supply_plenum", info_of="supply_trunk", type="supply", shape="rect", size=[26, 24], points=[[HP_CX, HP_N - 0.75, DECK + 1.0], [HP_CX, HP_N - 2.05, DECK + 1.0]]))
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
XB3 = bay(3.7)                                    # bottom takeoff under the trunk, in the truss bay below it
supply("s_bed3", "Bedroom 3", 127, 7, [[XB3, 14.5, DECK + 0.3], [XB3, 14.5, ZT], [bay(5.7), 14.5, ZT]], dict(at=[bay(5.7), 14.5, CEIL - 0.02], size=[12, 8]),
       "Bottom takeoff from the trunk into the truss bay below it, then crosses one truss to a ceiling register in the next bay west of the bedroom 3 return.")
# south main: drops from the west side of the supply plenum into the first truss bay at the west wall and runs south in it. Each kitchen and powder
# register then gets its own round branch through the truss webs (a rectangular main cannot cross the trusses).
XM = bay(1.7) + 0.2                               # east of centre in the bay, so the geo risers pass on its west side
SMAIN_END = 34.3
ducts.append(dict(id="supply_south_main", name="South supply main", category="HVAC supply duct", system="hvac.supply", type="supply", shape="rect", size=[14, 8],
    points=[[XM, HP_N - 1.4, DECK + 0.2], [XM, HP_N - 1.4, ZT], [XM, SMAIN_END, ZT]],
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

RY = 24.8                                          # the main return's centreline: above the utility room door, in line with the heat pump's filter side
ret("return_main", "Main return (M-10)", [34, 10], [[11.95, RY, ZT], [10.95, RY, ZT]],
    grilles=[dict(at=[12.15, RY, ZT], size=[34, 10], wall="E")])
ducts[-1]["info"] = dict(model="34 x 10 in grille and trunk, 1,368 CFM system (M-10)",
    specs=[["Serves", "Living, kitchen, dining, family and the halls, plus any room on transfer grilles"], ["Grille", "34 x 10 in, hall 1 (M-10)"],
           ["Boot", "34 x 10 in box in one truss bay over the utility room, parallel to the trusses"], ["Trunk", "34 x 10 in on the attic deck (M-10)"]],
    notes=["Andy's M-10 return: one 34 x 10 grille in hall 1 and a 34 x 10 return trunk over the utility, pantry and powder rooms to HP-01. "
           "Moved about 6 ft north along the same hall 1 wall (Maxwell, 11/18/2026), so the trunk runs straight west into the heat pump's return plenum with no turns: about 5 ft of trunk instead of 11. "
           "The grille sits high on the hall 1 wall above the utility room door. Behind it a boot box sits inside one truss bay, so nothing crosses the trusses, "
           "and rises straight up through the deck. The trunk runs on the deck from there to the return plenum. Route on the deck is ASSUMED to suit the heat pump position in this model."])
XMR = 11.45
RP_S, RP_N = HP_Y + 2.215, HP_Y - 2.035            # the plenum box covers the 36 in filter rack
RP_E = HP_X + 0.22 + 14 / 12                       # its east face, where the trunk comes in
RPX = bay(7.7)                                     # the bedroom flex runs come up into the bottom of the trunk in this truss bay
ret("return_main_riser", None, [14, 30], [[XMR, RY, ZT], [XMR, RY, DK]], info_of="return_main")
ret("return_main_deck", None, [34, 10], [[XMR, RY, DK], [RP_E, RY, DK]], info_of="return_main")
ret("return_plenum", "Return plenum box", [14, 24], [[RP_E - 7 / 12, RP_S, PZ], [RP_E - 7 / 12, RP_N, PZ]],
    model="14 x 24 in return plenum box on the deck, along the heat pump's filter rack",
    note="The return trunk comes straight into its east face. The bedroom flex runs come up through collars in the bottom of the trunk just east of it. "
         "The box sits on the deck along the AFR1836A filter rack on the heat pump's east side. Size ASSUMED.")

# Bedrooms 2 and 3 (Maxwell, 11/17/2026): bedroom 3's grille moved from beside the bed to its north wall. Both grilles are in
# the wall the two rooms share, in neighbouring stud bays, and both stacks rise into the trusses over bedroom 3, where they join.
XR3, XR2 = bay(7.7), bay(9.7)
r = ret("return_bed23", "Bedrooms 2 and 3 return", 10, bend([[XR3, 10.85, ZT], [XR3, RY - 0.7, ZT], [XR3, RY - 0.7, DECK + 0.2]]), flex=True,
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
        bend([[XSB, 10.85, ZT], [XSB - 0.35, 11.4, ZT], [XSB - 0.35, YSW, ZT], [XR2, YSW, ZT], [XR2, RY + 0.5, ZT], [RPX, RY + 0.5, ZT], [RPX, RY + 0.5, DECK + 0.2]]), flex=True,
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
                                  [bay(11.7) - 0.2, RY - 1.3, ZT]]), flex=True,
    grilles=[dict(at=[XB1R, 15.01, LOW], size=[14, 8], wall=N)], info_of="return_study")
stack("return_bed1_stack", XB1R, 15.26, "return_study")

# Bath exhaust (Maxwell, 11/17/2026): ceiling or high wall grilles in bath 1, bath 2 and the powder room, ducted to the ERV's stale air inlet
# instead of separate fans. The run hugs the supply trunk's south side on the deck so it stays in the low, north part of the attic.
ZTOP = ZTR + 8 / 12 + 0.27                        # centre of a 6 in round lying on top of the 18 x 16 supply trunk
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
exhaust("ex_bath2", "Bath 2 exhaust", 4, [[19.8, 10.62, ZTOP], [19.8, YN, ZTOP]], room="Bath 2",
        grilles=[dict(at=[19.8, 10.6, ZTOP], size=[10, 6], wall=N)], note=ENOTE + " High on the bath 2 wall through the attic wall, over the supply trunk.")
PWX, PWY = 10.2, 31.3                              # powder room exhaust grille
exhaust("ex_powder", "Powder exhaust", 4, [[PWX, PWY, ZT], [PWX, PWY, EX - 0.08], [4.9, PWY, EX - 0.08], [4.9, HP_S + 1.0, EX - 0.08], [4.9, HP_S + 1.0, ERV_Z], [ERV_XS + 0.1, HP_S + 1.0, ERV_Z]], room="Powder",
        grilles=[dict(at=[PWX, PWY, CEIL - 0.02], size=[8, 8])], note=ENOTE + " Comes up through the deck, runs along it and rises into the main just before the ERV.")
exhaust("ex_main", "Bath exhaust main", 6, [[XE1, 17.8, EX], [25.6, 17.8, EX], [25.6, 13.3, EX], [25.6, 13.3, ZTOP], [25.6, YN, ZTOP], [ERV_XS, YN, ZTOP], [ERV_XS, HP_N - 2.5, ZTOP],
                                           [ERV_XS, HP_N - 2.5, ERV_Z], [ERV_XS, ERV_N, ERV_Z]],
        note="Collects the three bathroom exhausts. It rides on top of the supply trunk along the north attic wall and down to the heat pump, crosses over the heat pump's top "
             "and goes straight into the ERV's stale air inlet, so it takes no floor space (Maxwell, 11/18/2026). ASSUMED route and size.")
# Heat pump water heater air (Maxwell, 11/18/2026): the utility door stays solid, so the water heater's intake and exhaust are both
# ducted up into the attic, which is inside the SIP roof. Rheem allows any size room when both are ducted and says never to tie
# the unit into other ductwork. Both rise straight up in truss bay 5.7, north to south of each other, and come out on open deck
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
for k, (x, y) in enumerate([(ERV_XF, ERV_S + 0.6), (ERV_XS, ERV_S + 1.2)]):
    ducts.append(dict(id=f"erv_wall_{k}", info_of="erv", type="erv", shape="round", size=6, points=[[x, ERV_S, ERV_Z], [x, y, ERV_Z], [-0.05, y, ERV_Z]]))
# Fresh air leaves the room end, runs over the top of the heat pump beside the exhaust main, and drops into the supply plenum.
ducts.append(dict(id="erv_to_supply", info_of="erv", type="erv", shape="round", size=6,
                  points=[[ERV_XF, ERV_N, ERV_Z], [ERV_XF, HP_N - 1.4, ERV_Z], [ERV_XF, HP_N - 1.4, DECK + 1.9]]))

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
