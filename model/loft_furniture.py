# Loft furniture (Maxwell 11/21/2026), run by make_house.py after the loft is built. [loft] furniture = "chest" | "murphy" | "table" | "none";
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

    if lay == "table":
        tx0, ty0 = 34.2, 25.0
        tx1, ty1 = tx0 + 6.0, ty0 + 6.0
        piece("game_table", "Game table, 6 ft square", "Wood top stained the red brown of the concrete floor, on galvanized steel pipe legs",
              [["Top", "6' x 6', 1 3/4 in thick"], ["Colour", "Red brown stain to match the stained concrete (Maxwell 11/21/2026)"], ["Height", "30 in"],
               ["Legs", "1 1/2 in galvanized pipe with floor flanges, pipe stretchers"],
               ["Clear around it", f"{ftin(tx0 - X0)} to the railing, {ftin(X1 - tx1)} to the east wall, {ftin(ty0 - Y0)} north, {ftin(Y1 - 1.42 - ty1)} to the piano"]],
              ["A bed cannot open with the table in place. One idea: a twin mattress on a rolling platform that stores under the table."])
        b(TW, tx0, tx1, ty0, ty1, 2.354, 2.5)
        for lx_, ly_ in ((tx0 + 0.6, ty0 + 0.6), (tx1 - 0.6, ty0 + 0.6), (tx0 + 0.6, ty1 - 0.6), (tx1 - 0.6, ty1 - 0.6)):
            pipe_leg(lx_, ly_, 2.354)
        for ly_ in (ty0 + 0.6, ty1 - 0.6):
            b(PIPE, tx0 + 0.6, tx1 - 0.6, ly_ - 0.07, ly_ + 0.07, 0.5, 0.64)
        b(PIPE, (tx0 + tx1) / 2 - 0.07, (tx0 + tx1) / 2 + 0.07, ty0 + 0.6, ty1 - 0.6, 0.5, 0.64)
        bx = piano(33.2)
        bench(bx, 32.0, "Bench, shared by the piano and the table")
        for i_, (sx_, sy_) in enumerate(((tx0 - 0.9, ty0 + 1.6), (tx0 - 0.9, ty1 - 1.6), (tx1 + 0.9, ty0 + 1.6), (tx1 + 0.9, ty1 - 1.6), (tx0 + 1.6, ty0 - 0.9), (tx1 - 1.6, ty0 - 0.9))):
            piece(f"stool_{i_}", "Stool", "Round wood seat on a galvanized pipe post", [["Height", "18 in"]])
            cyl(TW, sx_, sy_, FL + 1.38, FL + 1.5, 0.55); pipe_leg(sx_, sy_, 1.38)
        piece("game_shelves", "Game shelves", "Open white oak shelves for board games, 7 ft high", [["Size", "4' 4\" wide, 12 in deep"], ["Wall", "South wall, east of the piano"]])
        shelf_unit(38.05, 42.4, Y1 - 1.0, Y1, 7.0, 6, "N", GAMES)
    else:
        loveseat(32.0, 37.2)
        if lay == "murphy":
            bx = piano(31.95)
            bench(bx, 32.0)
            mx0, mx1, md, mh = 36.85, 42.4, 1.4, 7.5
            piece("murphy", "Murphy bed", "Queen wall bed in a white oak cabinet, folds up against the south wall",
                  [["Cabinet", f"{ftin(mx1 - mx0)} wide, 16 3/4 in deep, 7' 6\" high"], ["Open", "reaches 7' 2\" from the wall"], ["Wall", "South wall, 10 ft of headroom there"]],
                  ["Must be anchored to the wall framing. The swivel chair moves aside when the bed comes down."])
            b(OAK, mx0, mx0 + 0.08, Y1 - md, Y1, 0.0, mh); b(OAK, mx1 - 0.08, mx1, Y1 - md, Y1, 0.0, mh); b(OAK, mx0, mx1, Y1 - md, Y1, mh - 0.08, mh); b(OAK, mx0, mx1, Y1 - 0.05, Y1, 0.0, mh)
            if OPEN:
                by0 = Y1 - 0.25 - 6.9
                b(OAK, mx0 + 0.15, mx1 - 0.15, by0, Y1 - 0.25, 1.05, 1.2); b(OAK, mx0 + 0.15, mx1 - 0.15, by0 - 0.06, by0, 0.0, 1.2)
                b(PIL, mx0 + 0.27, mx1 - 0.27, by0 + 0.05, Y1 - 0.35, 1.2, 2.0)
                bedding(mx0 + 0.27, mx1 - 0.27, by0 + 0.05, Y1 - 0.35, 2.0, "S")
                swivel(34.6, 29.2, "E")
            else:
                b(OAK, mx0 + 0.08, mx1 - 0.08, Y1 - md, Y1 - md + 0.08, 0.1, mh - 0.08)
                for k in (1, 2):
                    b(OAK, mx0 + (mx1 - mx0) * k / 3 - 0.02, mx0 + (mx1 - mx0) * k / 3 + 0.02, Y1 - md - 0.02, Y1 - md, 0.1, mh - 0.08)
                b("Black Metal", mx0 + 1.5, mx1 - 1.5, Y1 - md - 0.1, Y1 - md - 0.05, 5.3, 5.38)
                swivel(39.6, 29.4, "E")
            piece("wall_shelves", "Shelves over the piano", "Two white oak wall shelves", [["Size", "4' 6\" long, 10 in deep"]])
            for z_ in (4.4, 5.8):
                b(OAK, 31.95, 36.5, Y1 - 0.85, Y1, z_, z_ + 0.12)
                for k in range(9):
                    if k % 4 != 3:
                        b(paint(BOOKS[k % len(BOOKS)]), 32.1 + k * 0.47, 32.1 + k * 0.47 + 0.3 + 0.05 * (k % 3), Y1 - 0.75, Y1 - 0.08, z_ + 0.12, z_ + 0.75 + 0.1 * (k % 2))
        else:                                                    # chest: a cabinet bed under the east window
            bx = piano(34.1)
            bench(bx, 32.0)
            swivel(32.65, 32.7, "E")
            piece("bookcase", "Tall bookcase", "Open white oak bookcase, 7 ft high", [["Size", "3' 5\" wide, 12 in deep"], ["Wall", "South wall, east of the piano"]])
            shelf_unit(38.95, 42.4, Y1 - 1.0, Y1, 7.0, 6, "N", BOOKS)
            cy0, cy1, cd, ch = 26.0, 31.4, 2.05, 3.4
            piece("cabinet_bed", "Cabinet bed", "Queen cabinet bed (chest bed): a free standing wood chest that unfolds into a bed",
                  [["Closed", "64 in wide, 24 1/2 in deep, 41 in high: under the window sill"], ["Open", "reaches 6' 8\" from the wall"], ["Mattress", "Queen, 6 in tri fold foam"]],
                  ["Free standing: no wall anchors, and it can come up the ladder in pieces. Examples of the type: Night and Day Murphy Cube, Arason Creden-ZzZ.", "Closed, its top is a shelf under the window."])
            b(OAK, X1 - cd, X1, cy0, cy0 + 0.08, 0.0, ch); b(OAK, X1 - cd, X1, cy1 - 0.08, cy1, 0.0, ch); b(OAK, X1 - 0.06, X1, cy0, cy1, 0.0, ch)
            if OPEN:
                bx0 = X1 - 6.7
                b(OAK, X1 - cd, X1, cy0, cy1, 0.0, 0.9); b(OAK, bx0, X1 - cd, cy0 + 0.1, cy1 - 0.1, 0.75, 0.9)
                for k in range(2):
                    b(OAK, bx0 + 0.1 + k * 2.2, bx0 + 0.25 + k * 2.2, cy0 + 0.1, cy1 - 0.1, 0.0, 0.75)
                b(PIL, bx0 + 0.05, X1 - 0.1, cy0 + 0.2, cy1 - 0.2, 0.9, 1.4)
                bedding(bx0 + 0.05, X1 - 0.1, cy0 + 0.2, cy1 - 0.2, 1.4, "E")
            else:
                b(OAK, X1 - cd, X1, cy0, cy1, ch - 0.1, ch); b(OAK, X1 - cd, X1 - cd + 0.08, cy0, cy1, 0.0, ch - 0.1)
                b(OAK, X1 - cd - 0.02, X1 - cd, cy0 + 0.08, cy1 - 0.08, 0.85, 0.89)
                for k in (-1, 1):
                    b("Black Metal", X1 - cd - 0.08, X1 - cd - 0.02, (cy0 + cy1) / 2 + k * 1.2 - 0.25, (cy0 + cy1) / 2 + k * 1.2 + 0.25, 2.5, 2.56)


_loft_furniture()
