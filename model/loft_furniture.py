# Loft furniture (Maxwell 11/21/2026), run by make_house.py after the loft is built. [loft] furniture = "lounge" | "table" | "none"
# (LOFT_LAYOUT overrides it for mockups). Everything is ASSUMED placement, in the Belongings layer, heights from the loft floor.
def _loft_furniture():
    lay = os.environ.get("LOFT_LAYOUT") or LOFT.get("furniture", "none")
    if lay == "none":
        return
    FL = LOFT["floor_height"]
    X0, X1, Y0, Y1 = LX0 + 0.14, LX1 - 0.05, LY0 + 0.07, LY1 - 0.07          # clear floor inside the railing and the walls
    MATERIALS.setdefault("Galvanized Pipe", dict(color="#A9AEB1", rough=0.5, metal=0.75))
    MATERIALS.setdefault("Piano Wood", dict(color="#8A5A3A", rough=0.45, map="white_oak.jpg", tile=0.8, grain="long"))
    OAK, PIPE, PW = "White Oak", "Galvanized Pipe", "Piano Wood"
    fab, fab2 = paint("#6F7F74"), paint("#5E6D63")

    def b(mat, x0, x1, y0, y1, z0, z1):
        box(mat, x0, x1, y0, y1, FL + z0, FL + z1)

    def piece(id_, name, model, specs, notes=None):
        rec(f"furniture.loft_{id_}", "furniture", name, "furniture", room="Loft", info=dict(model=model, specs=specs, notes=(notes or []) + ["Placement ASSUMED, mockup 11/21/2026."]))

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
    if lay == "lounge":
        # couch facing the railing and the living room TV (west wall, y 30.65)
        cx0, cx1, cy0, cy1 = X0 + 2.6, X0 + 5.7, 28.05, 34.45
        piece("couch", "Loft couch", "Three seat couch facing the railing", [["Size", "6' 5\" long, 3' 1\" deep"], ["Faces", "West, over the railing to the living room TV"], ["Walkway", f"{ftin(cx0 - X0)} between the railing and the seat"]])
        b(fab, cx0, cx1 - 0.7, cy0 + 0.5, cy1 - 0.5, 0.35, 1.45); b(fab2, cx1 - 0.7, cx1, cy0, cy1, 0.35, 2.75)
        b(fab2, cx0, cx1 - 0.7, cy0, cy0 + 0.5, 0.35, 2.0); b(fab2, cx0, cx1 - 0.7, cy1 - 0.5, cy1, 0.35, 2.0)
        for k in range(3):
            ya = cy0 + 0.55 + k * (cy1 - cy0 - 1.1) / 3
            b(fab, cx1 - 1.05, cx1 - 0.7, ya, ya + (cy1 - cy0 - 1.1) / 3 - 0.06, 1.45, 2.55)
        for px, py in ((cx0 + 0.15, cy0 + 0.15), (cx0 + 0.15, cy1 - 0.15), (cx1 - 0.15, cy0 + 0.15), (cx1 - 0.15, cy1 - 0.15)):
            cyl("Black Metal", px, py, FL, FL + 0.35, 0.05)
        # compact console digital piano on the north wall, by the loft outlets
        px0, px1, py0 = X0 + 1.9, X0 + 1.9 + 4.55, Y0
        piece("piano", "Digital piano", "Compact console digital piano in a wood cabinet, 88 weighted keys (ASSUMED, model not picked)",
              [["Size", "54 1/2 in wide, 17 in deep, 36 in high"], ["Wall", "North wall, next to the loft outlets"], ["Roof above", ftin(north_roof_z(Y0 + 1.4) - FL) + " at the player's side"]],
              ["Similar to an upright in looks, about a third of the depth. Examples of the type: Yamaha Arius YDP, Kawai CN, Roland RP."])
        b(PW, px0, px0 + 0.12, py0, py0 + 1.42, 0.0, 2.45); b(PW, px1 - 0.12, px1, py0, py0 + 1.42, 0.0, 2.45)       # cheeks
        b(PW, px0, px1, py0, py0 + 0.1, 0.5, 3.0)                                                                     # back panel
        b(PW, px0, px1, py0, py0 + 0.75, 2.45, 3.0)                                                                   # top box
        b(PW, px0, px1, py0, py0 + 1.42, 2.0, 2.3)                                                                    # key bed
        b(paint("#F4F1EA"), px0 + 0.14, px1 - 0.14, py0 + 0.85, py0 + 1.36, 2.3, 2.36)                                # white keys
        for k in range(36):
            if k % 7 in (2, 6):
                continue
            xk = px0 + 0.2 + (px1 - px0 - 0.4) * (k + 0.75) / 36
            b(paint("#161616"), xk - 0.03, xk + 0.03, py0 + 0.85, py0 + 1.17, 2.36, 2.4)
        b(PW, px0 + 1.5, px1 - 1.5, py0 + 0.76, py0 + 0.8, 2.5, 3.25)                                                 # music rest
        b(PW, px0 + 0.12, px1 - 0.12, py0 + 0.1, py0 + 0.18, 0.3, 0.75)                                               # pedal rail
        for k in range(3):
            b(paint("#C8A85A"), (px0 + px1) / 2 - 0.3 + k * 0.25, (px0 + px1) / 2 - 0.22 + k * 0.25, py0 + 0.18, py0 + 0.6, 0.12, 0.17)
        piece("piano_bench", "Piano bench", "Wood bench with a padded top", [["Size", "30 in x 14 in x 19 in"]])
        bx = (px0 + px1) / 2
        b(PW, bx - 1.25, bx + 1.25, py0 + 1.9, py0 + 3.05, 1.35, 1.5); b(paint("#2A2A2A"), bx - 1.2, bx + 1.2, py0 + 1.95, py0 + 3.0, 1.5, 1.6)
        for sx in (-1.15, 1.03):
            for sy in (1.95, 2.9):
                b(PW, bx + sx, bx + sx + 0.12, py0 + sy, py0 + sy + 0.1, 0.0, 1.35)
        # shelving: a tall bookcase on the south wall behind the couch, a low run under the east window
        piece("bookcase", "Tall bookcase", "Open white oak bookcase, 7 ft high", [["Size", "4' 6\" wide, 12 in deep, 7' high"], ["Wall", "South wall (the clerestory wall), 10 ft of headroom there"]])
        shelf_unit(cx1 + 0.15, cx1 + 4.65, Y1 - 1.0, Y1, 7.0, 6, "N", BOOKS)
        piece("low_shelf", "Low shelf under the window", "Open white oak shelf, 3' 3\" high, top just under the window sill", [["Size", "7' 6\" long, 12 in deep"], ["Wall", "East wall, under the loft window (sill 3' 7\")"]])
        shelf_unit(X1 - 1.0, X1, 25.6, 33.1, 3.25, 3, "W", BOOKS)
    elif lay == "table":
        tx0, ty0 = X0 + 2.05, (Y0 + Y1) / 2 - 3.0
        tx1, ty1 = tx0 + 6.0, ty0 + 6.0
        piece("game_table", "Game table, 6 ft square", "White oak top on galvanized steel pipe legs",
              [["Top", "6' x 6', 1 3/4 in thick, white oak like the loft floor"], ["Height", "30 in"], ["Legs", "1 1/2 in galvanized pipe with floor flanges, pipe stretchers"],
               ["Clear around it", f"{ftin(tx0 - X0)} to the railing, {ftin(X1 - 1.0 - tx1)} to the shelves, {ftin(ty0 - Y0)} north and south"]])
        b(OAK, tx0, tx1, ty0, ty1, 2.354, 2.5)
        for lx_, ly_ in ((tx0 + 0.6, ty0 + 0.6), (tx1 - 0.6, ty0 + 0.6), (tx0 + 0.6, ty1 - 0.6), (tx1 - 0.6, ty1 - 0.6)):
            pipe_leg(lx_, ly_, 2.354)
        for ly_ in (ty0 + 0.6, ty1 - 0.6):
            b(PIPE, tx0 + 0.6, tx1 - 0.6, ly_ - 0.07, ly_ + 0.07, 0.5, 0.64)
        b(PIPE, (tx0 + tx1) / 2 - 0.07, (tx0 + tx1) / 2 + 0.07, ty0 + 0.6, ty1 - 0.6, 0.5, 0.64)
        for nm, ya in (("north", ty0 - 1.55), ("south", ty1 + 0.35)):
            piece(f"bench_{nm}", "Bench", "White oak bench on galvanized pipe legs", [["Size", "5' x 14 in x 18 in"]])
            b(OAK, tx0 + 0.5, tx1 - 0.5, ya, ya + 1.2, 1.37, 1.5)
            for lx_ in (tx0 + 1.0, tx1 - 1.0):
                for ly_ in (ya + 0.25, ya + 0.95):
                    pipe_leg(lx_, ly_, 1.37)
        piece("game_shelves", "Game shelves", "Open white oak shelves for board games: low under the window, tall to its south",
              [["Low run", "4' 6\" long, 3' 3\" high, under the window"], ["Tall unit", "3' 6\" wide, 7' high"], ["Depth", "12 in (most game boxes are 11 to 12 in)"]])
        shelf_unit(X1 - 1.0, X1, 26.45, 30.95, 3.25, 3, "W", GAMES)
        shelf_unit(X1 - 1.0, X1, 31.0, 34.5, 7.0, 6, "W", GAMES)


_loft_furniture()
