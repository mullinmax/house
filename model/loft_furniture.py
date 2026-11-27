# Loft furniture (Maxwell 11/21/2026), run by make_house.py after the loft is built. [loft] furniture = "chest" | "sleeper" | "none";
# [loft] bed_open = true draws the bed down (LOFT_BED_OPEN for mockups).
# (LOFT_LAYOUT overrides it for mockups). Everything is ASSUMED placement, in the Belongings layer, heights from the loft floor.
def _loft_furniture():
    lay = os.environ.get("LOFT_LAYOUT") or LOFT.get("furniture", "none")
    if lay == "none":
        return
    FL = LOFT["floor_height"]
    X0, X1, Y0, Y1 = LX0 + 0.14, LX1 - 0.05, LY0 + 0.07, LY1 - 0.07          # clear floor inside the railing and the walls
    MATERIALS.setdefault("Galvanized Pipe", dict(color="#A9AEB1", rough=0.5, metal=0.75))
    MATERIALS.setdefault("Table Wood", dict(color="#A2513C", rough=0.5, map="white_oak.jpg", tile=0.8, grain="long"))   # stained the red brown of the concrete floor
    MATERIALS.setdefault("Piano Wood", dict(color="#8A5A3A", rough=0.45, map="white_oak.jpg", tile=0.8, grain="long"))
    OAK, PIPE, PW = "White Oak", "Galvanized Pipe", "Piano Wood"
    fab, fab2 = paint("#6F7F74"), paint("#5E6D63")

    def b(mat, x0, x1, y0, y1, z0, z1):
        box(mat, x0, x1, y0, y1, FL + z0, FL + z1)

    def piece(id_, name, model, specs, notes=None, links=None):
        info = dict(model=model, specs=specs, notes=(notes or []) + ["Placement ASSUMED, mockup 11/21/2026."])
        if links:
            info["links"] = links
        rec(f"furniture.loft_{id_}", "furniture", name, "furniture", room="Loft", info=info)

    def shelf_unit(x0, x1, y0, y1, h, n, face, stuff=()):
        """Open oak shelving: sides, back, n shelves; face = the open side (W or N or S). stuff = colours of boxes and books on it."""
        t = 0.06
        b(OAK, x0, x1, y0, y1, 0.0, 0.25); b(OAK, x0, x1, y0, y1, h - t, h)
        alongy = face == "W"
        if alongy:
            b(OAK, x0, x1, y0, y0 + t, 0.25, h - t); b(OAK, x0, x1, y1 - t, y1, 0.25, h - t); b(OAK, x1 - 0.03, x1, y0, y1, 0.25, h - t)
            for m in range(1, int((y1 - y0) / 3.0) + 1):
                ym = y0 + (y1 - y0) * m / (int((y1 - y0) / 3.0) + 1)
                b(OAK, x0, x1 - 0.03, ym - t / 2, ym + t / 2, 0.25, h - t)
        else:
            b(OAK, x0, x0 + t, y0, y1, 0.25, h - t); b(OAK, x1 - t, x1, y0, y1, 0.25, h - t)
            yb = (y1 - 0.03, y1) if face == "N" else (y0, y0 + 0.03)
            b(OAK, x0, x1, yb[0], yb[1], 0.25, h - t)
            for m in range(1, int((x1 - x0) / 3.0) + 1):
                xm = x0 + (x1 - x0) * m / (int((x1 - x0) / 3.0) + 1)
                b(OAK, xm - t / 2, xm + t / 2, y0, y1, 0.25, h - t)
        zs = [0.25 + (h - t - 0.25) * k / n for k in range(n)]
        for z in zs[1:]:
            b(OAK, x0 + t, x1 - t, y0 + (0 if alongy else 0), y1, z - t / 2, z + t / 2)
        if stuff:                                             # game boxes and books, a deterministic scatter
            L0, L1 = (y0 + 0.12, y1 - 0.12) if alongy else (x0 + 0.12, x1 - 0.12)
            gap = (h - t - 0.25) / n
            for k, z in enumerate(zs):
                u, i = L0, k * 3
                while u < L1 - 0.3:
                    w = 0.35 + 0.22 * ((i * 7 + k) % 4)
                    hh = min(gap - 0.12, 0.25 + 0.17 * ((i * 5 + 2 * k) % 4))
                    if (i + k) % 5 != 4:
                        m = paint(stuff[(i * 3 + k) % len(stuff)])
                        d0 = 0.12
                        if alongy:
                            b(m, x0 + d0, x1 - 0.08, u, min(u + w, L1), z + t / 2, z + t / 2 + hh)
                        elif face == "N":
                            b(m, u, min(u + w, L1), y0 + d0, y1 - 0.08, z + t / 2, z + t / 2 + hh)
                        else:
                            b(m, u, min(u + w, L1), y0 + 0.08, y1 - d0, z + t / 2, z + t / 2 + hh)
                    u += w + 0.04
                    i += 1

    def pipe_leg(cx, cy, h):
        cyl(PIPE, cx, cy, FL, FL + h, 0.08); cyl(PIPE, cx, cy, FL, FL + 0.03, 0.19); cyl(PIPE, cx, cy, FL + h - 0.03, FL + h, 0.19)

    GAMES = ["#B5483A", "#2F5D8A", "#E0B040", "#3F7F5F", "#6A4C93", "#D9D4C7", "#2B2B2B", "#C96F2E"]
    BOOKS = ["#7A3B2E", "#2F4858", "#C9B27C", "#4F6D5A", "#8C8C8C", "#B56B45", "#3A3A55"]
    OPEN = bool(os.environ.get("LOFT_BED_OPEN") or LOFT.get("bed_open"))
    TW, LIN, PIL = "Table Wood", paint("#E9E4DA"), paint("#F6F3EC")

    def piano(px0):
        """Compact console digital piano, back against the south wall, keys facing north."""
        px1 = px0 + 4.55
        D = lambda d: Y1 - d
        piece("piano", "Digital piano", "Compact console digital piano in a wood cabinet, 88 weighted keys (ASSUMED, model not picked)",
              [["Size", "54 1/2 in wide, 17 in deep, 36 in high"], ["Wall", "South wall (Maxwell 11/21/2026)"]],
              ["Similar to an upright in looks, about a third of the depth. Examples of the type: Yamaha Arius YDP, Kawai CN, Roland RP.", "Needs an outlet on the south wall; the loft has only its code required outlets so far."])
        b(PW, px0, px0 + 0.12, D(1.42), D(0), 0.0, 2.45); b(PW, px1 - 0.12, px1, D(1.42), D(0), 0.0, 2.45)
        b(PW, px0, px1, D(0.1), D(0), 0.5, 3.0); b(PW, px0, px1, D(0.75), D(0), 2.45, 3.0); b(PW, px0, px1, D(1.42), D(0), 2.0, 2.3)
        b(paint("#F4F1EA"), px0 + 0.14, px1 - 0.14, D(1.36), D(0.85), 2.3, 2.36)
        for k in range(36):
            if k % 7 in (2, 6):
                continue
            xk = px0 + 0.2 + (px1 - px0 - 0.4) * (k + 0.75) / 36
            b(paint("#161616"), xk - 0.03, xk + 0.03, D(1.17), D(0.85), 2.36, 2.4)
        b(PW, px0 + 1.5, px1 - 1.5, D(0.8), D(0.76), 2.5, 3.25); b(PW, px0 + 0.12, px1 - 0.12, D(0.18), D(0.1), 0.3, 0.75)
        for k in range(3):
            b(paint("#C8A85A"), (px0 + px1) / 2 - 0.3 + k * 0.25, (px0 + px1) / 2 - 0.22 + k * 0.25, D(0.6), D(0.18), 0.12, 0.17)
        return (px0 + px1) / 2

    def bench(bx, yc, name="Piano bench"):
        piece("piano_bench", name, "Wood bench with a padded top", [["Size", "30 in x 14 in x 19 in"]])
        b(PW, bx - 1.25, bx + 1.25, yc - 0.58, yc + 0.58, 1.35, 1.5); b(paint("#2A2A2A"), bx - 1.2, bx + 1.2, yc - 0.53, yc + 0.53, 1.5, 1.6)
        for sx in (-1.15, 1.03):
            for sy in (-0.5, 0.4):
                b(PW, bx + sx, bx + sx + 0.12, yc + sy, yc + sy + 0.1, 0.0, 1.35)

    def loveseat(x0, x1):
        """Small two seat couch, back on the north wall, facing south."""
        piece("loveseat", "Loveseat", "Two seat couch on the north wall", [["Size", f"{ftin(x1 - x0)} long, 2' 10\" deep"], ["Roof above", ftin(north_roof_z(Y0) - FL) + " at the wall"]])
        b(fab2, x0, x1, Y0, Y0 + 0.6, 0.35, 2.6); b(fab2, x0, x0 + 0.45, Y0 + 0.6, Y0 + 2.85, 0.35, 1.95); b(fab2, x1 - 0.45, x1, Y0 + 0.6, Y0 + 2.85, 0.35, 1.95)
        b(fab, x0 + 0.45, x1 - 0.45, Y0 + 0.6, Y0 + 2.85, 0.35, 1.45)
        half = (x1 - x0 - 0.9) / 2
        for k in range(2):
            b(fab, x0 + 0.48 + k * half, x0 + 0.42 + (k + 1) * half, Y0 + 0.6, Y0 + 0.95, 1.45, 2.45)
        for px_ in (x0 + 0.15, x1 - 0.15):
            for py_ in (Y0 + 0.15, Y0 + 2.7):
                cyl("Black Metal", px_, py_, FL, FL + 0.35, 0.05)

    def swivel(cx, cy, back, n=""):
        """Swivel armchair on a round base; back = the side its back is on now (N, S, E or W)."""
        piece("swivel" + n, "Swivel armchair", "Armchair on a swivel base: turns to the TV, the table or the room", [["Size", "about 30 in round"]])
        cyl("Black Metal", cx, cy, FL, FL + 0.06, 0.85); cyl("Black Metal", cx, cy, FL + 0.06, FL + 0.6, 0.12)
        cyl(fab, cx, cy, FL + 0.6, FL + 1.45, 1.2)
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[back]
        if dx:
            b(fab2, cx + dx * 0.75, cx + dx * 1.2, cy - 1.05, cy + 1.05, 1.45, 2.75)
            for sy in (-1, 1):
                b(fab2, cx - 0.8, cx + 0.8, cy + sy * 0.85, cy + sy * 1.15, 1.45, 2.05)
        else:
            b(fab2, cx - 1.05, cx + 1.05, cy + dy * 0.75, cy + dy * 1.2, 1.45, 2.75)
            for sx in (-1, 1):
                b(fab2, cx + sx * 0.85, cx + sx * 1.15, cy - 0.8, cy + 0.8, 1.45, 2.05)

    def bedding(x0, x1, y0, y1, z, head):
        """Mattress top dressing: sheet, folded blanket and two pillows; head = N, S, E or W end."""
        b(LIN, x0, x1, y0, y1, z, z + 0.04)
        if head in "EW":
            hx = (x1 - 1.9, x1 - 0.3) if head == "E" else (x0 + 0.3, x0 + 1.9)
            for k in range(2):
                ya = y0 + 0.2 + k * (y1 - y0 - 0.2) / 2
                b(PIL, hx[0], hx[1], ya, ya + (y1 - y0) / 2 - 0.4, z + 0.04, z + 0.4)
            fx = (x0, x0 + 2.2) if head == "E" else (x1 - 2.2, x1)
            b(paint("#6F7F74"), fx[0], fx[1], y0, y1, z + 0.04, z + 0.14)
        else:
            hy = (y1 - 1.9, y1 - 0.3) if head == "S" else (y0 + 0.3, y0 + 1.9)
            for k in range(2):
                xa = x0 + 0.2 + k * (x1 - x0 - 0.2) / 2
                b(PIL, xa, xa + (x1 - x0) / 2 - 0.4, hy[0], hy[1], z + 0.04, z + 0.4)
            fy = (y0, y0 + 2.2) if head == "S" else (y1 - 2.2, y1)
            b(paint("#6F7F74"), x0, x1, fy[0], fy[1], z + 0.04, z + 0.14)

    # Maxwell 11/21/2026: no big table. Loveseat on the north wall, piano on the south wall, a full size cabinet bed in the
    # south east corner, and bookshelves along the east wall that frame the window, deep enough to sit on under it.
    CW, CD, CH, CL = 58 / 12, 23 / 12, 39 / 12, 76 / 12        # Arason Creden-ZzZ full: 58 W x 23 D x 39 H in, opens to 76 in
    SILL = 13.67 - FL                                         # east window sill above the loft floor (A-21)
    WY0, WY1 = 26.71, 30.71                                   # east window rough opening
    if lay == "sleeper":
        # Mockup for Maxwell 11/21/2026: one sleeper sofa does the couch and the bed. IKEA FRIHETEN: 88 5/8 x 41 3/8 x 32 5/8 in,
        # the seat pulls forward into a 56 3/4 x 78 3/8 in bed that lies along the sofa, so it only comes 56 3/4 in off the wall.
        SW_, SD_, SH_, SO_ = 88.625 / 12, 41.375 / 12, 32.625 / 12, 56.75 / 12
        wc = (WY0 + WY1) / 2
        s0, s1 = wc - SW_ / 2, wc + SW_ / 2
        bx = piano(X0 + 0.5)   # round 17: 6 in off the loft edge, clear of the loft railing's south end post and its flange
        bench(bx, 32.0)
        piece("sleeper_sofa", "Sleeper sofa", "IKEA FRIHETEN sleeper sofa: the seat pulls forward into a bed that lies along the sofa",
              [["Closed", "88 5/8 in wide, 41 3/8 in deep, 32 5/8 in high"], ["Bed", "56 3/4 in x 78 3/8 in (a full is 54 x 75)"], ["Open", "56 3/4 in from the wall"],
               ["Packages", "Two, 105 lb and 125 lb"], ["Clear when open", f"{ftin(X1 - SO_ - (X0 + 0.05 + 4.55))} past the end of the piano"]],
              ["Under the east window facing the railing and the TV. The back stands about 10 in below the sill.",
               "You sleep on the seat and back cushions, there is no separate mattress: fine for guests, firmer than the cabinet bed's 6 in foam mattress. A topper helps.",
               "Bedding stores under the seat."],
              links=[["IKEA product page", "https://www.ikea.com/us/en/p/friheten-sleeper-sofa-faringe-light-gray-40551231/"]])
        b(fab2, X1 - 0.75, X1, s0, s1, 0.2, SH_)                                   # back
        b(fab2, X1 - SD_, X1 - 0.75, s0, s1, 0.2, 0.95)                            # base with the bedding box
        if OPEN:
            b(fab2, X1 - SO_, X1 - SD_, s0 + 0.05, s1 - 0.05, 0.2, 0.95)
            b(fab, X1 - SO_, X1 - 0.75, s0 + 0.05, s1 - 0.05, 0.95, 1.35)
            bedding(X1 - SO_ + 0.03, X1 - 0.78, s0 + 0.1, s1 - 0.1, 1.35, "N")
        else:
            b(fab, X1 - SD_, X1 - 0.75, s0 + 0.05, s1 - 0.05, 0.95, 1.35)
            for k in range(3):
                ya = s0 + 0.08 + k * (SW_ - 0.16) / 3
                b(fab, X1 - 1.2, X1 - 0.75, ya, ya + (SW_ - 0.16) / 3 - 0.06, 1.35, 2.5)
        bd = 23 / 12
        piece("bookcase", "Bookcase north of the window", "White oak bookcase from the floor to 6 ft, in the north east corner",
              [["Size", f"{ftin(s0 - 0.05 - Y0)} wide, 23 in deep, 6' high"]])
        shelf_unit(X1 - bd, X1, Y0, s0 - 0.05, 6.0, 5, "W", GAMES)
        piece("bookcase_s", "Bookcase south of the window", "White oak bookcase from the floor to 6 ft, in the south east corner",
              [["Size", f"{ftin(Y1 - (s1 + 0.05))} wide, 23 in deep, 6' high"]])
        shelf_unit(X1 - bd, X1, s1 + 0.05, Y1, 6.0, 5, "W", BOOKS)
        piece("low_shelf", "Low shelves on the north wall", "White oak shelves, 3 ft high", [["Size", "3' 6\" long, 14 in deep, 3' high"]])
        shelf_unit(X0 + 0.3, X0 + 3.8, Y0, Y0 + 1.17, 3.0, 2, "S", GAMES)
        swivel(36.0, 24.6, "N")
        return
    loveseat(31.6, 36.8)
    bx = piano(X0 + 0.5)   # round 17: 6 in off the loft edge, clear of the loft railing's south end post and its flange
    bench(bx, 32.0)
    cy1 = Y1 - 0.02
    cy0 = cy1 - CW
    piece("cabinet_bed", "Cabinet bed, full size", "Arason Creden-ZzZ full size cabinet bed: a free standing wood chest that unfolds into a bed",
          [["Closed", "58 in wide, 23 in deep, 39 in high"], ["Open", "76 in from the wall"], ["Mattress", "Full, 6 in two layer foam, stored inside"],
           ["Weight", "220 lb in its carton"], ["Clear when open", f"{ftin(X1 - CL - (X0 + 0.05 + 4.55))} to the piano, {ftin(cy0 - 28.75)} to the swivel chair"]],
          ["Free standing, no wall anchors. It ships as one 220 lb carton, so it has to be hoisted over the loft railing; it will not go up the ladder.",
           "Dimensions from Arason's Creden-ZzZ collection sheet. The queen is 64 x 23 x 43 in and opens to 81 in: it would touch the piano and stand as high as the window sill.",
           "A flat packed alternative: Night and Day Murphy Cube (queen 64.1 x 26.4 x 36.6 in, opens 80.3 in, 128 lb)."],
          links=[["Arason collection sheet with dimensions (PDF)", "https://cdn.shopify.com/s/files/1/0690/0226/4860/files/Creden-ZzZ-Cabinet-Bed-Collection.pdf"],
                               ["A retailer page, full size", "https://www.zfurniture.com/products/creden-zzz-full-pekoe-murphy-cabinet-bed"]])
    b(OAK, X1 - CD, X1, cy0, cy0 + 0.08, 0.0, CH); b(OAK, X1 - CD, X1, cy1 - 0.08, cy1, 0.0, CH); b(OAK, X1 - 0.06, X1, cy0, cy1, 0.0, CH)
    if OPEN:
        bx0 = X1 - CL
        b(OAK, X1 - CD, X1, cy0, cy1, 0.0, 0.9); b(OAK, bx0, X1 - CD, cy0 + 0.1, cy1 - 0.1, 0.75, 0.9)
        for k in range(2):
            b(OAK, bx0 + 0.1 + k * 2.2, bx0 + 0.25 + k * 2.2, cy0 + 0.1, cy1 - 0.1, 0.0, 0.75)
        b(PIL, bx0 + 0.05, X1 - 0.1, cy0 + 0.17, cy1 - 0.17, 0.9, 1.4)
        bedding(bx0 + 0.05, X1 - 0.1, cy0 + 0.17, cy1 - 0.17, 1.4, "E")
    else:
        b(OAK, X1 - CD, X1, cy0, cy1, CH - 0.1, CH); b(OAK, X1 - CD, X1 - CD + 0.08, cy0, cy1, 0.0, CH - 0.1)
        b(OAK, X1 - CD - 0.02, X1 - CD, cy0 + 0.08, cy1 - 0.08, 0.85, 0.89)
        for k in (-1, 1):
            b("Black Metal", X1 - CD - 0.08, X1 - CD - 0.02, (cy0 + cy1) / 2 + k * 1.1 - 0.25, (cy0 + cy1) / 2 + k * 1.1 + 0.25, 2.5, 2.56)
    swivel(38.3, 27.55, "E")
    # east wall shelving, the same 23 in depth as the cabinet bed so the fronts line up
    sx0 = X1 - CD
    seat_h = SILL - 0.17                                       # top 2 in under the sill
    piece("window_seat", "Window seat shelves", "White oak shelves under the east window, built to sit on",
          [["Size", f"{ftin(cy0 - 0.05 - (WY0 - 0.1))} long, 23 in deep, {ftin(seat_h)} high"], ["Top", "2 in under the window sill, with a seat pad"]],
          [f"At {ftin(seat_h)} the top is counter height: a perch more than a bench. The low shelf doubles as a step up."])
    shelf_unit(sx0, X1, WY0 - 0.1, cy0 - 0.05, seat_h, 3, "W", BOOKS)
    b(fab, sx0 + 0.05, X1 - 0.05, WY0, cy0 - 0.15, seat_h, seat_h + 0.17)
    piece("bookcase", "Bookcase north of the window", "White oak bookcase from the floor to 6 ft, in the north east corner",
          [["Size", f"{ftin(WY0 - 0.15 - Y0)} wide, 23 in deep, 6' high"], ["Behind it", "Solid north wall: the attic entrance moved west to clear it (Maxwell 11/21/2026)"], ["Roof above", ftin(north_roof_z(Y0) - FL) + " at the north wall"]])
    shelf_unit(sx0, X1, Y0, WY0 - 0.15, 6.0, 5, "W", GAMES)
    piece("wall_shelves", "Shelves south of the window", "Three white oak wall shelves over the cabinet bed, matching the bookcase across the window",
          [["Size", f"{ftin(cy1 - (WY1 + 0.15))} long, 10 in deep"], ["Heights", "4' 6\", 5' 6\" and 6' 6\""]])
    for z_ in (4.5, 5.5, 6.5):
        b(OAK, X1 - 0.85, X1, WY1 + 0.15, cy1, z_ - 0.1, z_)
        for k in range(7):
            if k % 4 != 3:
                ya = WY1 + 0.3 + k * 0.5
                b(paint(BOOKS[(k + int(z_)) % len(BOOKS)]), X1 - 0.75, X1 - 0.08, ya, ya + 0.3 + 0.05 * (k % 3), z_, z_ + 0.6 + 0.1 * (k % 2))


_loft_furniture()
