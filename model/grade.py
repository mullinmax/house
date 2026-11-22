"""Floor levels and finished grade around the house, the breezeway and the garage ([grade] in config.toml).

The walkthrough's terrain (Terrain in site/models/site.glb) was baked with the house slab set 8 in over the lidar
ground. [terrain] slab_top_elev_ft now puts the slab higher (11/22/2026), and the garage and the breezeway sit lower
than the house, so the ground near the buildings has to change. This module works out the new ground on a 2 ft grid
as a patch of heights. site/app.js cuts the baked Terrain triangles under the patch and draws the patch instead
(house.json meta.grade); make_equipment.py stands the trees, transformer and drive on the same ground.

Run it on its own for the check:  python model/grade.py
"""
import array, ast, json, math, os, statistics, struct

import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.toml"), "rb") as _f:
    C = tomllib.load(_f)
G = C["grade"]
TC = C["terrain"]
OLD_ELEV = 1034.93                     # the slab top elevation the baked site.glb terrain was made with

PATIO_Z = -G["patio_drop_in"] / 12     # top of the breezeway brick
GARAGE_Z = -G["garage_drop_in"] / 12   # top of the garage slab
HW, HD = C["house"]["width_x"], C["house"]["depth_y"]
GARAGE = C["garage"]["rect"]
PORCH = C["porch"]["rect"]


class _Grid:
    """a 2D float32 .npy read without numpy (CI has none): g[r, c]"""
    def __init__(self, data, ncols):
        self.a, self.n = data, ncols

    def __getitem__(self, rc):
        return self.a[rc[0] * self.n + rc[1]]


def _npy(path):
    with open(path, "rb") as f:
        assert f.read(6) == b"\x93NUMPY"
        major = f.read(2)[0]
        hl = struct.unpack("<H" if major == 1 else "<I", f.read(2 if major == 1 else 4))[0]
        hdr = ast.literal_eval(f.read(hl).decode("latin1"))
        assert hdr["descr"] == "<f4" and not hdr["fortran_order"]
        a = array.array("f"); a.frombytes(f.read())
    return _Grid(a, hdr["shape"][1])


def linspace(a, b, n):
    return [a + (b - a) * k / (n - 1) for k in range(n)]


def _load():
    d = os.path.join(HERE, "data", "terrain")
    meta = json.load(open(os.path.join(d, "meta.json")))
    dem = _npy(os.path.join(d, "dem.npy"))
    web = json.load(open(os.path.join(d, "web_ground.json")))
    return meta, dem, web


META, DEM, WEB = _load()


def natural(x, y, elev=None):
    """lidar ground, feet above the slab top (slab at elev, default the config value)"""
    X0, Y0 = META["extent_plan_ft"][:2]; S = META["grid_ft"]
    c, r = (x - X0) / S, (y - Y0) / S
    c0, r0 = int(math.floor(c)), int(math.floor(r)); fc, fr = c - c0, r - r0
    z = (DEM[r0, c0] * (1 - fc) * (1 - fr) + DEM[r0, c0 + 1] * fc * (1 - fr)
         + DEM[r0 + 1, c0] * (1 - fc) * fr + DEM[r0 + 1, c0 + 1] * fc * fr)
    return float(z) - (TC["slab_top_elev_ft"] if elev is None else elev)


def web(x, y):
    """the baked web terrain, feet above the slab top (tools/ground_grid.mjs)"""
    fx = (x - WEB["x0"]) / WEB["step"]; fy = (y - WEB["y0"]) / WEB["step"]
    i = max(0, min(WEB["nx"] - 2, int(fx))); j = max(0, min(WEB["ny"] - 2, int(fy)))
    tx, ty = min(1, max(0, fx - i)), min(1, max(0, fy - j)); z = WEB["z"]
    return (z[j][i] * (1 - tx) + z[j][i + 1] * tx) * (1 - ty) + (z[j + 1][i] * (1 - tx) + z[j + 1][i + 1] * tx) * ty


def _dist(r, x, y):
    dx = max(r[0] - x, 0, x - r[2]); dy = max(r[1] - y, 0, y - r[3])
    return math.hypot(dx, dy)


PADS = [((0, 0, HW, HD), -G["house_grade_in"] / 12),
        (tuple(PORCH), PATIO_Z - G["patio_grade_in"] / 12),
        (tuple(GARAGE), GARAGE_Z - G["garage_grade_in"] / 12)]


def smooth(t):
    t = min(1.0, max(0.0, t)); return t * t * (3 - 2 * t)


def target(x, y):
    """finished ground: a flat pad at each slab, blended back to the lidar ground, then faded into the old web mesh"""
    ds = [_dist(r, x, y) for r, _ in PADS]
    w = [1 / (d + 0.5) ** 3 for d in ds]
    pad = sum(wi * lv for wi, (_, lv) in zip(w, PADS)) / sum(w)
    dmin = min(ds)
    z = pad + (natural(x, y) - pad) * smooth((dmin - G["buffer_ft"]) / G["blend_ft"])
    f0, f1 = G["fade_ft"]
    return z + (web(x, y) - z) * smooth((dmin - f0) / (f1 - f0))


def grid(step=2.0, pad=None):
    """the regraded ground as a patch: absolute heights (ft above the slab top) on a plan grid round the buildings,
    inside the web_ground.json extent. Its edge matches the baked mesh (dz fades to 0 there), dropped 0.03 ft so the
    baked triangles that straddle the edge draw over it rather than flicker."""
    pad = G["fade_ft"][1] if pad is None else pad
    wx1 = WEB["x0"] + (WEB["nx"] - 1) * WEB["step"]; wy1 = WEB["y0"] + (WEB["ny"] - 1) * WEB["step"]
    x0 = max(math.floor((-pad) / step) * step, WEB["x0"]); x1 = min(math.ceil((GARAGE[2] + pad) / step) * step, wx1)
    y0 = max(math.floor((-pad) / step) * step, WEB["y0"]); y1 = min(math.ceil((HD + pad) / step) * step, wy1)
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    z = []
    for j in range(ny):
        row = []
        for i in range(nx):
            x, y = x0 + i * step, y0 + j * step
            edge = min(i, j, nx - 1 - i, ny - 1 - j)
            row.append(round(target(x, y) - (0.03 if edge <= 2 else 0.0), 2))
        z.append(row)
    return dict(x0=x0, y0=y0, step=step, nx=nx, ny=ny, z=z)


_GRID = None


def ground(x, y):
    """the ground the walkthrough draws after the regrade, feet above the slab top"""
    global _GRID
    if _GRID is None:
        _GRID = grid()
    g = _GRID
    fx = (x - g["x0"]) / g["step"]; fy = (y - g["y0"]) / g["step"]
    if fx < 0 or fy < 0 or fx > g["nx"] - 1 or fy > g["ny"] - 1:
        return web(x, y)
    i = min(g["nx"] - 2, int(fx)); j = min(g["ny"] - 2, int(fy)); tx, ty = fx - i, fy - j; d = g["z"]
    return (d[j][i] * (1 - tx) + d[j][i + 1] * tx) * (1 - ty) + (d[j + 1][i] * (1 - tx) + d[j + 1][i + 1] * tx) * ty


def check():
    """the garage slab against the lidar ground just outside it, and what slab elevation that asks for"""
    gx0, gy0, gx1, gy1 = GARAGE; b = G["buffer_ft"]
    pts = [(gx0 - b + (gx1 - gx0 + 2 * b) * t, y) for t in linspace(0, 1, 41) for y in (gy0 - b, gy1 + b)] + \
          [(x, gy0 - b + (gy1 - gy0 + 2 * b) * t) for t in linspace(0, 1, 41) for x in (gx0 - b, gx1 + b)]
    nat_old = [natural(x, y, OLD_ELEV) for x, y in pts]
    need = max(nat_old) + G["garage_min_above_natural_in"] / 12 - GARAGE_Z      # house slab rise over the old guess, ft
    house_pts = [(t * HW, -b) for t in linspace(0, 1, 21)] + [(t * HW, HD + b) for t in linspace(0, 1, 21)] + \
                [(-b, t * HD) for t in linspace(0, 1, 21)] + [(HW + b, t * HD) for t in linspace(0, 1, 21)]
    return dict(garage_natural_old_ft=[round(min(nat_old), 2), round(max(nat_old), 2)], rise_needed_ft=round(need, 2),
                slab_elev_needed=round(OLD_ELEV + need, 2), slab_elev_now=TC["slab_top_elev_ft"],
                garage_clear_in=round((GARAGE_Z - max(natural(x, y) for x, y in pts)) * 12, 1),
                house_reveal_over_natural_in=round(-float(statistics.median([natural(x, y) for x, y in house_pts])) * 12, 1))


if __name__ == "__main__":
    print(json.dumps(check(), indent=1))
    g = grid(); a = [v for row in g["z"] for v in row]
    print("patch", g["nx"], "x", g["ny"], "from", g["x0"], g["y0"], "min %.2f max %.2f" % (min(a), max(a)))
