"""Download the CC0 assets listed in [assets] of config.toml into assets/ and write assets/SOURCES.md.

  Poly Haven (https://polyhaven.com, CC0): furniture/prop models as glTF, sky HDRI
  ambientCG  (https://ambientcg.com, CC0): PBR material sets (color, roughness, normal, ...)

Run:  python fetch_assets.py          (skips files already downloaded)
"""
import io, json, os, sys, tomllib, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
C = tomllib.load(open(os.path.join(HERE, "config.toml"), "rb"))
A = C["assets"]
OUT = os.path.join(HERE, A.get("dir", "assets"))
UA = {"User-Agent": "house-model-assets/1.0 (personal project)"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()


def save(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return os.path.getsize(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    b = get(url)
    open(path, "wb").write(b)
    return len(b)


rows = []
total = 0
# ---- Poly Haven models (glTF + bin + textures)
for mid in A["polyhaven_models"]:
    files = json.loads(get(f"https://api.polyhaven.com/files/{mid}"))
    res = A.get("model_res", "1k")
    if "gltf" not in files:
        print("skip (no glTF):", mid); continue
    g = files["gltf"].get(res) or files["gltf"][sorted(files["gltf"])[0]]
    gl = g["gltf"]
    d = os.path.join(OUT, "polyhaven", mid)
    total += save(gl["url"], os.path.join(d, os.path.basename(gl["url"])))
    for rel, inc in gl.get("include", {}).items():
        total += save(inc["url"], os.path.join(d, rel))
    rows.append((f"polyhaven/{mid}", "Poly Haven model", f"https://polyhaven.com/a/{mid}", "CC0 1.0"))
    print("model", mid)
# ---- Poly Haven HDRI
hid, hres = A["hdri"], A.get("hdri_res", "2k")
hf = json.loads(get(f"https://api.polyhaven.com/files/{hid}"))
u = hf["hdri"][hres]["hdr"]["url"]
total += save(u, os.path.join(OUT, "polyhaven", "hdri", os.path.basename(u)))
rows.append((f"polyhaven/hdri/{os.path.basename(u)}", "Poly Haven HDRI", f"https://polyhaven.com/a/{hid}", "CC0 1.0"))
print("hdri", hid)
# ---- Poly Haven textures (2k: diffuse, normal GL, roughness); real-world size recorded for correct mapping scale
sizes = {}
for role, tid in A.get("polyhaven_textures", {}).items():
    files = json.loads(get(f"https://api.polyhaven.com/files/{tid}"))
    info = json.loads(get(f"https://api.polyhaven.com/info/{tid}"))
    res = A.get("ph_texture_res", "2k")
    d = os.path.join(OUT, "polyhaven_tex", tid)
    for key, suffix in (("Diffuse", "Color"), ("nor_gl", "NormalGL"), ("Rough", "Roughness")):
        if key in files:
            u = files[key][res]["jpg"]["url"]
            total += save(u, os.path.join(d, f"{tid}_{suffix}.jpg"))
    sizes[tid] = [x / 1000 for x in info.get("dimensions", [1000, 1000])]
    rows.append((f"polyhaven_tex/{tid}", f"Poly Haven texture ({role}), {sizes[tid][0]:.2f} m tile", f"https://polyhaven.com/a/{tid}", "CC0 1.0"))
    print("texture", role, tid, sizes[tid])
json.dump(sizes, open(os.path.join(OUT, "polyhaven_tex", "sizes.json"), "w"))
# ---- ambientCG materials
tres = A.get("texture_res", "1K")
for role, aid in A["ambientcg"].items():
    d = os.path.join(OUT, "ambientcg", aid)
    if not (os.path.isdir(d) and os.listdir(d)):
        r_ = "2K" if aid.startswith(("LeafSet", "Bark")) else tres
        z = zipfile.ZipFile(io.BytesIO(get(f"https://ambientcg.com/get?file={aid}_{r_}-JPG.zip")))
        os.makedirs(d, exist_ok=True)
        for n in z.namelist():
            if n.lower().endswith((".jpg", ".png")) and "preview" not in n.lower():
                open(os.path.join(d, os.path.basename(n)), "wb").write(z.read(n))
    total += sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
    rows.append((f"ambientcg/{aid}", f"ambientCG material ({role})", f"https://ambientcg.com/view?id={aid}", "CC0 1.0"))
    print("material", role, aid)

# ---- original abstract prints for the picture frames (the Poly Haven frames ship a grey placeholder card)
try:
    import numpy as np
    from PIL import Image, ImageFilter
    ad = os.path.join(OUT, "art"); os.makedirs(ad, exist_ok=True)
    palettes = [["#56614A", "#C9B68E", "#E9E2D3", "#2B2D2F", "#9A6B4A"], ["#7D8A6C", "#D9CBA8", "#3E4A3A", "#B98B5A", "#EEEAE3"],
                ["#1E2022", "#A7B88F", "#D6C7A1", "#6B4E3A", "#F1EEE8"]]
    for k, pal in enumerate(palettes):
        rng = np.random.default_rng(40 + k)
        W, H = 768, 1024
        img = Image.new("RGB", (W, H), pal[-1])
        arr = np.asarray(img).astype(float)
        yy, xx = np.mgrid[0:H, 0:W]
        for j in range(6):   # soft-edged color fields
            c = np.array([int(pal[j % (len(pal) - 1)][i:i + 2], 16) for i in (1, 3, 5)], float)
            cx, cy = rng.uniform(0.15, 0.85) * W, rng.uniform(0.1, 0.9) * H
            rx, ry = rng.uniform(0.18, 0.45) * W, rng.uniform(0.08, 0.25) * H
            m = np.clip(1.2 - (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) ** 0.5, 0, 1) ** 1.5
            arr = arr * (1 - m[..., None] * 0.85) + c * (m[..., None] * 0.85)
        arr += rng.normal(0, 4, arr.shape)                  # paper grain
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)).save(os.path.join(ad, f"art_{k + 1}.jpg"), quality=90)
    rows.append(("art/art_1..3.jpg", "Original abstract prints generated by fetch_assets.py", "(this project)", "CC0 1.0"))
except Exception as ex:
    print("art generation skipped:", ex)

with open(os.path.join(OUT, "SOURCES.md"), "w", encoding="utf-8") as fh:
    fh.write("# Asset sources\n\nEvery asset here is CC0 1.0 (public domain dedication); no attribution required, credited anyway.\n\n")
    fh.write("| Local path | What | Source | License |\n|---|---|---|---|\n")
    for r in rows:
        fh.write("| " + " | ".join(r) + " |\n")
    fh.write("\nProcedural (modeled in build_house.py, no download): beds and bedding, toilets, vanities and sinks, mirrors, "
             "shower and tub, curtains and shades, towels, rugs, washer/dryer, baseboards, casings, interior doors and hardware, "
             "gutters and downspouts, fascia and soffit, outlets, hose bibs, thresholds, stoops, study desk.\n")
print(f"ASSETS OK  {total / 1e6:.1f} MB in {OUT}")
