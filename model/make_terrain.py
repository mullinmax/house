"""Real site terrain for the house model, from free public data (no Google data).

Downloads (cached in data/terrain/raw/) and converts into plan feet
(origin = outside NW slab corner, +x east, +y SOUTH, plan north = true north):
  * bare-earth DEM      USGS 3DEP 1 m (elevation.nationalmap.gov 3DEPElevation ImageServer)
  * orthophoto          USDA NAIP via USGS (imagery.nationalmap.gov USGSNAIPImagery ImageServer)
  * tree canopy height  USGS 3DEP lidar point cloud, Ohio statewide (usgs-lidar-public EPT on AWS):
                        highest non-ground, non-building return per cell minus the DEM
  * roads, buildings    OpenStreetMap via the Overpass API

Outputs in data/terrain/ (small, local):
  dem.npy        float32 [rows, cols] ground elevation, feet NAVD88; row 0 = north edge (smallest plan y)
  chm.npy        float32 canopy height above ground, feet, same grid
  ortho.jpg      orthophoto covering exactly the grid extent, top = north
  trees.json     [[x, y, height_ft, crown_radius_ft], ...] in plan feet
  osm.json       roads and buildings as plan-feet polylines/polygons
  terrain_10ft.json  downsampled DEM (10 ft grid) for sharing
  meta.json      grid extent, sources, dates, suggested slab-top elevation

Run (any Python 3.11+ with numpy, pyproj, tifffile, pillow, laspy[lazrs]):
  python make_terrain.py            # uses [terrain] in config.toml
  python make_terrain.py --refresh  # ignore the download cache
"""
import io, json, math, os, sys, tomllib, urllib.parse, urllib.request
import numpy as np
from pyproj import Transformer
import tifffile
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
F = 0.3048
C = tomllib.load(open(os.path.join(HERE, "config.toml"), "rb"))
TC = C["terrain"]
OUT = os.path.join(HERE, "data", "terrain")
RAW = os.path.join(OUT, "raw")
os.makedirs(RAW, exist_ok=True)
REFRESH = "--refresh" in sys.argv
UA = {"User-Agent": "house-model-terrain/1.0 (personal project)"}

# ------------------------------------------------------------------ plan <-> geographic
LAT, LON = TC["lat"], TC["lon"]
AX, AY = TC["anchor_plan_xy"]                 # plan point (ft) that sits at LAT/LON
LOCAL = f"+proj=aeqd +lat_0={LAT} +lon_0={LON} +datum=WGS84 +units=m +no_defs"   # true north up at the site
to_ll = Transformer.from_crs(LOCAL, 4326, always_xy=True)
ll_to_utm = Transformer.from_crs(4326, 32617, always_xy=True)
utm_to_ll = Transformer.from_crs(32617, 4326, always_xy=True)
ll_to_3857 = Transformer.from_crs(4326, 3857, always_xy=True)
ll_to_local = Transformer.from_crs(4326, LOCAL, always_xy=True)


def plan_to_ll(x, y):
    e, n = (np.asarray(x) - AX) * F, -(np.asarray(y) - AY) * F
    return to_ll.transform(e, n)


def ll_to_plan(lon, lat):
    e, n = ll_to_local.transform(lon, lat)
    return AX + np.asarray(e) / F, AY - np.asarray(n) / F


HALF = TC["area_ft"] / 2
CX, CY = TC.get("center_plan_xy", [C["house"]["width_x"] / 2, C["house"]["depth_y"] / 2])
STEP = TC["grid_ft"]
X0, X1, Y0, Y1 = CX - HALF, CX + HALF, CY - HALF, CY + HALF
xs = np.arange(X0, X1 + 1e-6, STEP); ys = np.arange(Y0, Y1 + 1e-6, STEP)
GX, GY = np.meshgrid(xs, ys)                  # row = plan y (north first), col = plan x
NDVI = None


def fetch(url, name, data=None):
    p = os.path.join(RAW, name)
    if os.path.exists(p) and not REFRESH:
        return open(p, "rb").read()
    req = urllib.request.Request(url, data=data, headers=UA)
    b = urllib.request.urlopen(req, timeout=300).read()
    open(p, "wb").write(b)
    return b


def utm_bbox(margin_m=40):
    cx = [X0, X1, X1, X0]; cy = [Y0, Y0, Y1, Y1]
    lon, lat = plan_to_ll(cx, cy)
    e, n = ll_to_utm.transform(lon, lat)
    return min(e) - margin_m, min(n) - margin_m, max(e) + margin_m, max(n) + margin_m


def bilinear(a, fx, fy):
    """sample array a at fractional pixel coords (fx = col, fy = row)."""
    h, w = a.shape[:2]
    fx = np.clip(fx, 0, w - 1.001); fy = np.clip(fy, 0, h - 1.001)
    x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int); dx = fx - x0; dy = fy - y0
    if a.ndim == 3:
        dx = dx[..., None]; dy = dy[..., None]
    return (a[y0, x0] * (1 - dx) * (1 - dy) + a[y0, x0 + 1] * dx * (1 - dy) +
            a[y0 + 1, x0] * (1 - dx) * dy + a[y0 + 1, x0 + 1] * dx * dy)


def plan_to_utm_px(px, py, bb, res):
    lon, lat = plan_to_ll(px, py)
    e, n = ll_to_utm.transform(lon, lat)
    return (e - bb[0]) / res - 0.5, (bb[3] - n) / res - 0.5


# ------------------------------------------------------------------ DEM (USGS 3DEP 1 m)
def get_dem():
    bb = utm_bbox(); res = 1.0
    w, h = int(round((bb[2] - bb[0]) / res)), int(round((bb[3] - bb[1]) / res))
    url = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?" +
           urllib.parse.urlencode(dict(bbox=",".join(f"{v:.2f}" for v in bb), bboxSR=32617, imageSR=32617,
                                       size=f"{w},{h}", format="tiff", pixelType="F32",
                                       interpolation="RSP_BilinearInterpolation", f="image")))
    a = tifffile.imread(io.BytesIO(fetch(url, "dem_utm.tif"))).astype(np.float32)
    if a.ndim == 3:
        a = a[..., 0]
    a[a < -1000] = np.nan
    fx, fy = plan_to_utm_px(GX, GY, bb, res)
    dem_m = bilinear(np.nan_to_num(a, nan=np.nanmedian(a)), fx, fy)
    return (dem_m / F).astype(np.float32)


# ------------------------------------------------------------------ orthophoto (NAIP)
def get_ortho():
    bb = utm_bbox(); res = 0.3
    w, h = int(round((bb[2] - bb[0]) / res)), int(round((bb[3] - bb[1]) / res))
    url = ("https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage?" +
           urllib.parse.urlencode(dict(bbox=",".join(f"{v:.2f}" for v in bb), bboxSR=32617, imageSR=32617,
                                       size=f"{w},{h}", format="png", bandIds="0,1,2", f="image")))
    img = np.asarray(Image.open(io.BytesIO(fetch(url, "naip_utm.png"))).convert("RGB")).astype(np.float32)
    n = TC.get("ortho_px", 2000)
    ox = np.linspace(X0, X1, n); oy = np.linspace(Y0, Y1, n)
    OX, OY = np.meshgrid(ox, oy)
    fx, fy = plan_to_utm_px(OX, OY, bb, res)
    out = bilinear(img, fx, fy)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(OUT, "ortho.jpg"), quality=90)
    # near infrared band -> NDVI on the DEM grid (tells real trees from wires, poles and roofs)
    url_nir = url.replace("bandIds=0%2C1%2C2", "bandIds=3")
    nir = np.asarray(Image.open(io.BytesIO(fetch(url_nir, "naip_nir_utm.png"))).convert("L")).astype(np.float32)
    fx, fy = plan_to_utm_px(GX, GY, bb, res)
    red, nr = bilinear(img[..., 0], fx, fy), bilinear(nir, fx, fy)
    global NDVI
    NDVI = (nr - red) / np.maximum(nr + red, 1.0)
    # acquisition date of the NAIP tile under the site
    q = ("https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/query?" +
         urllib.parse.urlencode(dict(geometry=f"{LON},{LAT}", geometryType="esriGeometryPoint", inSR=4326,
                                     spatialRel="esriSpatialRelIntersects", outFields="Name,Year,acquisition_date,State",
                                     returnGeometry="false", f="json")))
    tiles = [f["attributes"] for f in json.loads(fetch(q, "naip_query.json"))["features"] if f["attributes"].get("Year")]
    return tiles


# ------------------------------------------------------------------ lidar canopy (USGS EPT)
EPT = TC.get("lidar_ept", "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/OH_StatewideP3_5_B21/")


def get_lidar_points():
    import laspy
    meta = json.loads(fetch(EPT + "ept.json", "ept.json"))
    b = meta["bounds"]
    lon, lat = plan_to_ll([X0, X1, X1, X0], [Y0, Y0, Y1, Y1])
    mx, my = ll_to_3857.transform(lon, lat)
    qx0, qx1, qy0, qy1 = min(mx) - 5, max(mx) + 5, min(my) - 5, max(my) + 5
    keys = []

    def hit(key):
        d, X, Y, Z = map(int, key.split("-"))
        s = (b[3] - b[0]) / 2 ** d
        nx0, ny0 = b[0] + X * s, b[1] + Y * s
        return nx0 < qx1 and nx0 + s > qx0 and ny0 < qy1 and ny0 + s > qy0

    def walk(hkey):
        h = json.loads(fetch(EPT + f"ept-hierarchy/{hkey}.json", f"ept_h_{hkey}.json"))
        for k, cnt in h.items():
            if not hit(k):
                continue
            if cnt == -1:
                if k != hkey:
                    walk(k)
            elif cnt > 0:
                keys.append(k)
    walk("0-0-0-0")
    print(f"lidar: {len(keys)} EPT nodes intersect the site")
    pts = []
    for k in keys:
        las = laspy.read(io.BytesIO(fetch(EPT + f"ept-data/{k}.laz", f"ept_{k}.laz")))
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x > qx0) & (x < qx1) & (y > qy0) & (y < qy1)
        if m.any():
            pts.append(np.stack([x[m], y[m], np.asarray(las.z)[m], np.asarray(las.classification)[m],
                                 np.asarray(las.return_number)[m]], 1))
    P = np.concatenate(pts)
    lon, lat = Transformer.from_crs(3857, 4326, always_xy=True).transform(P[:, 0], P[:, 1])
    px, py = ll_to_plan(lon, lat)
    return px, py, P[:, 2] / F, P[:, 3].astype(int)


def grid_index(px, py):
    c = np.round((px - X0) / STEP).astype(int); r = np.round((py - Y0) / STEP).astype(int)
    ok = (c >= 0) & (c < len(xs)) & (r >= 0) & (r < len(ys))
    return r, c, ok


def get_canopy(dem):
    px, py, z, cls = get_lidar_points()
    print(f"lidar: {len(z):,} points in area, classes {sorted(set(cls.tolist()))}")
    r, c, ok = grid_index(px, py)
    # vertical datum check: ground returns vs the 3DEP DEM
    g = ok & (cls == 2)
    off = float(np.median(z[g] - dem[r[g], c[g]])) if g.sum() > 100 else 0.0
    print(f"lidar ground minus DEM median offset: {off:.2f} ft (removed)")
    z = z - off
    veg = ok & ~np.isin(cls, (2, 6, 7, 9, 17, 18))      # drop ground, building, noise, water, bridge
    dsm = np.full(dem.shape, -1e9, np.float32)
    np.maximum.at(dsm, (r[veg], c[veg]), z[veg].astype(np.float32))
    chm = np.where(dsm > -1e8, dsm - dem, 0).astype(np.float32)
    chm = np.clip(chm, 0, 150)
    bld = ok & (cls == 6)
    return chm, off, int(len(z)), int(bld.sum())


def find_trees(chm):
    """local maxima of the smoothed canopy height = tree tops."""
    minh = TC.get("min_tree_height_ft", 12.0)
    k = max(1, int(round(TC.get("tree_min_spacing_ft", 14.0) / STEP / 2)))
    # light 3x3 smoothing
    s = chm.copy()
    s[1:-1, 1:-1] = sum(chm[1 + dy:chm.shape[0] - 1 + dy, 1 + dx:chm.shape[1] - 1 + dx]
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.pad(s, k, constant_values=0)
    mx = sliding_window_view(pad, (2 * k + 1, 2 * k + 1)).max(axis=(2, 3))
    peaks = np.argwhere((s >= mx - 1e-6) & (s >= minh))
    trees = []
    rr = int(round(30 / STEP))
    ndvi_min = TC.get("tree_ndvi_min", 0.15)
    for (r, c) in peaks:
        h = float(chm[r, c])
        if NDVI is not None and NDVI[max(0, r - 1):r + 2, max(0, c - 1):c + 2].max() < ndvi_min:
            continue          # not vegetation in the photo: wire, pole or structure
        if np.mean(chm[max(0, r - 2):r + 3, max(0, c - 2):c + 3] > minh * 0.5) < 0.35:
            continue          # a lone 1-cell spike (wire sag, bird, pole) not a crown
        win = chm[max(0, r - rr):r + rr + 1, max(0, c - rr):c + rr + 1]
        # crown radius: distance to where canopy drops below half the tree height (crude)
        area = (win > h * 0.5).sum() * STEP * STEP
        rad = float(np.clip(math.sqrt(area / math.pi), 0.18 * h, 0.4 * h))
        trees.append([round(float(xs[c]), 1), round(float(ys[r]), 1), round(h, 1), round(min(rad, 25.0), 1)])
    return clean_trees(trees)


def clean_trees(trees):
    """plausible heights: heights at the 150 ft clip are lidar outliers (birds, wires, noise) and take the median of
    their neighbors within 40 ft; everything is capped at max_tree_height_ft; anything under min_tree_height_ft is dropped."""
    minh, maxh = TC.get("min_tree_height_ft", 12.0), TC.get("max_tree_height_ft", 95.0)
    clip = 149.0
    ok = [t for t in trees if minh <= t[2] < clip]
    out = []
    for t in trees:
        x, y, h, r = t
        if h >= clip:
            nb = [o[2] for o in ok if math.hypot(o[0] - x, o[1] - y) <= 40.0]
            if not nb:
                continue
            h = float(np.median(nb))
        if h < minh:
            continue
        h = min(h, maxh)
        r = min(r, 0.4 * h)
        out.append([x, y, round(h, 1), round(r, 1)])
    return out


# ------------------------------------------------------------------ OpenStreetMap
def get_osm():
    FA = TC.get("far_area_ft")
    ex = (CX - FA / 2, CX + FA / 2, CY - FA / 2, CY + FA / 2) if FA else (X0, X1, Y0, Y1)
    lon, lat = plan_to_ll([ex[0], ex[1], ex[1], ex[0]], [ex[2], ex[2], ex[3], ex[3]])
    s, w, n, e = min(lat), min(lon), max(lat), max(lon)
    q = f"""[out:json][timeout:60];
(way["highway"]({s},{w},{n},{e}); way["building"]({s},{w},{n},{e}););
out geom tags;"""
    for ep in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            j = json.loads(fetch(ep, "osm_far.json" if FA else "osm.json", data=urllib.parse.urlencode({"data": q}).encode()))
            break
        except Exception as ex:
            print("overpass", ep, ex)
    else:
        raise RuntimeError("Overpass unavailable")
    roads, blds = [], []
    for el in j.get("elements", []):
        g = el.get("geometry")
        if not g:
            continue
        x, y = ll_to_plan([p["lon"] for p in g], [p["lat"] for p in g])
        pts = [[round(float(a), 1), round(float(b), 1)] for a, b in zip(x, y)]
        t = el.get("tags", {})
        if "building" in t:
            lv = t.get("building:levels"); hgt = t.get("height")
            h = float(hgt) / F if hgt and hgt.replace(".", "").isdigit() else (float(lv) * 10 + 6 if lv and lv.isdigit() else 18.0)
            blds.append({"id": el["id"], "type": t.get("building"), "height_ft": round(h, 1), "pts": pts})
        else:
            hw = t.get("highway")
            width = {"primary": 24, "secondary": 22, "tertiary": 20, "residential": 18, "unclassified": 18,
                     "service": 12, "track": 9}.get(hw, 10)
            roads.append({"id": el["id"], "highway": hw, "name": t.get("name") or t.get("ref"), "width_ft": width,
                          "surface": t.get("surface"), "pts": pts})
    return roads, blds


# ------------------------------------------------------------------ far ring (out to the horizon): coarse DEM, photo, trees
def get_far():
    """coarse terrain + photo + tree tops for a far square around the site (default 6000 ft). Tree tops come from the
    shallow (sparse) levels of the same lidar point cloud, so woodlots out to the horizon are where they really are."""
    import laspy
    FA = TC.get("far_area_ft", 6000.0); FS = TC.get("far_grid_ft", 20.0)
    fx0, fx1, fy0, fy1 = CX - FA / 2, CX + FA / 2, CY - FA / 2, CY + FA / 2
    fxs = np.arange(fx0, fx1 + 1e-6, FS); fys = np.arange(fy0, fy1 + 1e-6, FS)
    FGX, FGY = np.meshgrid(fxs, fys)
    lon, lat = plan_to_ll([fx0, fx1, fx1, fx0], [fy0, fy0, fy1, fy1])
    e, n = ll_to_utm.transform(lon, lat)
    bb = (min(e) - 50, min(n) - 50, max(e) + 50, max(n) + 50)
    res = 5.0
    w, h = int((bb[2] - bb[0]) / res), int((bb[3] - bb[1]) / res)
    url = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?" +
           urllib.parse.urlencode(dict(bbox=",".join(f"{v:.2f}" for v in bb), bboxSR=32617, imageSR=32617, size=f"{w},{h}",
                                       format="tiff", pixelType="F32", interpolation="RSP_BilinearInterpolation", f="image")))
    a = tifffile.imread(io.BytesIO(fetch(url, "far_dem_utm.tif"))).astype(np.float32)
    if a.ndim == 3:
        a = a[..., 0]
    a[a < -1000] = np.nan; a = np.nan_to_num(a, nan=np.nanmedian(a))
    fxp, fyp = plan_to_utm_px(FGX, FGY, bb, res)
    fdem = (bilinear(a, fxp, fyp) / F).astype(np.float32)
    np.save(os.path.join(OUT, "far_dem.npy"), fdem)
    # photo, ~1.2 m/px, plus NIR for a vegetation check
    pres = 1.2; pw, ph = int((bb[2] - bb[0]) / pres), int((bb[3] - bb[1]) / pres)
    q = dict(bbox=",".join(f"{v:.2f}" for v in bb), bboxSR=32617, imageSR=32617, size=f"{pw},{ph}", format="jpg", f="image")
    base = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage?"
    img = np.asarray(Image.open(io.BytesIO(fetch(base + urllib.parse.urlencode({**q, "bandIds": "0,1,2"}), "far_naip.jpg"))).convert("RGB")).astype(np.float32)
    nir = np.asarray(Image.open(io.BytesIO(fetch(base + urllib.parse.urlencode({**q, "bandIds": "3"}), "far_naip_nir.jpg"))).convert("L")).astype(np.float32)
    npx = TC.get("far_ortho_px", 3000)
    ox = np.linspace(fx0, fx1, npx); oy = np.linspace(fy0, fy1, npx); OX, OY = np.meshgrid(ox, oy)
    pxx, pyy = plan_to_utm_px(OX, OY, bb, pres)
    Image.fromarray(np.clip(bilinear(img, pxx, pyy), 0, 255).astype(np.uint8)).save(os.path.join(OUT, "far_ortho.jpg"), quality=88)
    # sparse lidar: EPT nodes down to far_lidar_depth only
    meta = json.loads(fetch(EPT + "ept.json", "ept.json")); b = meta["bounds"]
    mx, my = ll_to_3857.transform(lon, lat)
    qx0, qx1, qy0, qy1 = min(mx), max(mx), min(my), max(my)
    maxd = TC.get("far_lidar_depth", 10)
    keys = []

    def hit(key):
        d, X, Y, Z = map(int, key.split("-")); s = (b[3] - b[0]) / 2 ** d
        return b[0] + X * s < qx1 and b[0] + (X + 1) * s > qx0 and b[1] + Y * s < qy1 and b[1] + (Y + 1) * s > qy0

    def walk(hkey):
        hh = json.loads(fetch(EPT + f"ept-hierarchy/{hkey}.json", f"ept_h_{hkey}.json"))
        for k, cnt in hh.items():
            if not hit(k) or int(k.split("-")[0]) > maxd:
                continue
            if cnt == -1:
                if k != hkey:
                    walk(k)
            elif cnt > 0:
                keys.append(k)
    walk("0-0-0-0")
    print(f"far lidar: {len(keys)} EPT nodes (depth <= {maxd})")
    tf = Transformer.from_crs(3857, 4326, always_xy=True)
    cell = TC.get("far_tree_cell_ft", 10.0)
    gx = np.arange(fx0, fx1 + 1e-6, cell); gy = np.arange(fy0, fy1 + 1e-6, cell)
    dsm = np.full((len(gy), len(gx)), -1e9, np.float32)
    npts = 0
    for k in keys:
        las = laspy.read(io.BytesIO(fetch(EPT + f"ept-data/{k}.laz", f"ept_{k}.laz")))
        cls = np.asarray(las.classification)
        m = ~np.isin(cls, (2, 6, 7, 9, 17, 18))
        if not m.any():
            continue
        lo_, la_ = tf.transform(np.asarray(las.x)[m], np.asarray(las.y)[m])
        px_, py_ = ll_to_plan(lo_, la_)
        c = np.round((px_ - fx0) / cell).astype(int); r = np.round((py_ - fy0) / cell).astype(int)
        ok = (c >= 0) & (c < len(gx)) & (r >= 0) & (r < len(gy))
        np.maximum.at(dsm, (r[ok], c[ok]), (np.asarray(las.z)[m][ok] / F).astype(np.float32))
        npts += int(ok.sum())
    GXc, GYc = np.meshgrid(gx, gy)
    ground = bilinear(fdem, (GXc - fx0) / FS, (GYc - fy0) / FS)
    chm = np.where(dsm > -1e8, dsm - ground, 0)
    # vegetation check from the photo
    pxx, pyy = plan_to_utm_px(GXc, GYc, bb, pres)
    red, nr = bilinear(img[..., 0], pxx, pyy), bilinear(nir, pxx, pyy)
    ndvi = (nr - red) / np.maximum(nr + red, 1)
    from numpy.lib.stride_tricks import sliding_window_view
    kk = max(1, int(round(TC.get("far_tree_spacing_ft", 26.0) / cell / 2)))
    mxw = sliding_window_view(np.pad(chm, kk), (2 * kk + 1, 2 * kk + 1)).max(axis=(2, 3))
    minh, maxh = TC.get("min_tree_height_ft", 12.0), TC.get("max_tree_height_ft", 95.0)
    pk = np.argwhere((chm >= mxw - 1e-6) & (chm >= minh) & (ndvi > TC.get("tree_ndvi_min", 0.15)))
    trees = []
    for (r, c) in pk:
        x, y = float(gx[c]), float(gy[r])
        if X0 - 5 < x < X1 + 5 and Y0 - 5 < y < Y1 + 5:
            continue              # inside the detailed square: those come from the full-density lidar
        h = float(min(chm[r, c], maxh))
        trees.append([round(x, 1), round(y, 1), round(h, 1), round(max(0.22 * h, 6.0), 1)])
    json.dump(trees, open(os.path.join(OUT, "far_trees.json"), "w"))
    json.dump({"extent_plan_ft": [fx0, fy0, fx1, fy1], "grid_ft": FS, "shape": list(fdem.shape), "lidar_points": npts,
               "lidar_depth": maxd, "trees": len(trees)}, open(os.path.join(OUT, "far_meta.json"), "w"), indent=1)
    print(f"far ring: dem {fdem.shape}, {npts:,} sparse lidar points, {len(trees)} trees")


# ------------------------------------------------------------------ main
def main():
    if "--far-only" in sys.argv:
        get_far(); return
    dem = get_dem()
    print(f"DEM: {dem.shape}, {np.nanmin(dem):.1f} to {np.nanmax(dem):.1f} ft NAVD88")
    np.save(os.path.join(OUT, "dem.npy"), dem)
    naip = get_ortho()
    print("NAIP tiles:", naip)
    lidar_info = {}
    try:
        chm, off, npts, nbld = get_canopy(dem)
        trees = find_trees(chm)
        lidar_info = {"points": npts, "building_points": nbld, "ground_minus_dem_ft": round(off, 2)}
    except Exception as ex:
        print("lidar canopy failed:", ex)
        chm = np.zeros_like(dem); trees = []
    np.save(os.path.join(OUT, "chm.npy"), chm.astype(np.float32))
    json.dump(trees, open(os.path.join(OUT, "trees.json"), "w"))
    print(f"trees: {len(trees)}")
    try:
        roads, blds = get_osm()
    except Exception as ex:
        print("OSM failed:", ex); roads, blds = [], []
    json.dump({"roads": roads, "buildings": blds}, open(os.path.join(OUT, "osm.json"), "w"), indent=0)
    print(f"OSM: {len(roads)} roads, {len(blds)} buildings")
    # suggested slab top: perimeter grade + reveal
    HW, HD = C["house"]["width_x"], C["house"]["depth_y"]
    per = []
    for t in np.linspace(0, 1, 40):
        for (x, y) in ((t * HW, -3), (t * HW, HD + 3), (-3, t * HD), (HW + 3, t * HD)):
            per.append(bilinear(dem, np.array((x - X0) / STEP), np.array((y - Y0) / STEP)))
    per = np.array(per, float)
    reveal = TC.get("slab_reveal_ft", 0.67)
    sug = float(np.median(per) + reveal)
    # 10 ft downsample for sharing
    k = max(1, int(round(10 / STEP)))
    small = dem[::k, ::k]
    json.dump({"x0": X0, "y0": Y0, "step_ft": STEP * k, "units": "ft NAVD88", "rows_north_to_south": True,
               "elev": np.round(small, 2).tolist()}, open(os.path.join(OUT, "terrain_10ft.json"), "w"))
    meta = {"extent_plan_ft": [X0, Y0, X1, Y1], "grid_ft": STEP, "shape": list(dem.shape),
            "anchor": {"lat": LAT, "lon": LON, "plan_xy": [AX, AY]},
            "perimeter_grade_ft": {"min": round(per.min(), 2), "median": round(float(np.median(per)), 2), "max": round(per.max(), 2)},
            "suggested_slab_top_elev_ft": round(sug, 2), "slab_reveal_ft": reveal,
            "sources": {"dem": "USGS 3DEP 1 m bare earth, elevation.nationalmap.gov 3DEPElevation ImageServer",
                        "ortho": {"service": "USDA NAIP via imagery.nationalmap.gov USGSNAIPImagery", "tiles": naip},
                        "lidar": {"ept": EPT, **lidar_info},
                        "osm": "OpenStreetMap contributors (ODbL), Overpass API"}}
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    print(f"perimeter grade {per.min():.2f}..{per.max():.2f} ft, suggested slab_top_elev_ft = {sug:.2f}")
    if TC.get("far_area_ft"):
        get_far()
    print("TERRAIN OK")


if __name__ == "__main__":
    main()
