"""Inspect web/*.glb: node counts, operable extras, spawns, Roof/Utilities, textures. Also rebuilds manifest parts.
   python web_check.py"""
import json, os, struct, glob

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
man = json.load(open(os.path.join(D, "manifest.json")))
order = ["site", "trees", "shell", "interior", "furniture_west", "furniture_east"]
man["parts"] = [{"file": f"{n}.glb", "name": n, "bytes": os.path.getsize(os.path.join(D, f"{n}.glb"))} for n in order if os.path.exists(os.path.join(D, f"{n}.glb"))]
json.dump(man, open(os.path.join(D, "manifest.json"), "w"), indent=1)
tot = 0
for p in man["parts"]:
    b = open(os.path.join(D, p["file"]), "rb").read()
    ln = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + ln])
    nodes = j.get("nodes", [])
    ops = [n for n in nodes if n.get("extras", {}).get("operable")]
    kinds = {}
    for n in ops:
        kinds[n["extras"]["operable"]] = kinds.get(n["extras"]["operable"], 0) + 1
    spawns = [n["name"] for n in nodes if n.get("name", "").startswith("Spawn_")]
    named = [n["name"] for n in nodes if n.get("name") in ("Roof", "Utilities")]
    inst = sum(1 for n in nodes if "EXT_mesh_gpu_instancing" in n.get("extensions", {}))
    mats = j.get("materials", [])
    tex_mats = sum(1 for m in mats if "baseColorTexture" in m.get("pbrMetallicRoughness", {}))
    tot += p["bytes"]
    print(f"{p['file']:22s} {p['bytes'] / 1e6:5.1f} MB  nodes {len(nodes):5d}  meshes {len(j.get('meshes', [])):4d}  "
          f"mats {len(mats):3d} (textured {tex_mats})  images {len(j.get('images', [])):3d}  ops {kinds}  "
          f"spawns {len(spawns)}  {named}  gpu-instanced {inst}  ext {j.get('extensionsUsed', [])}")
    if p["name"] == "interior":
        print("   sample door extras:", [(n["name"], n["extras"]) for n in ops[:3]])
        print("   spawns:", spawns)
    if p["name"] == "shell":
        print("   shell ops:", [(n["name"], n["extras"]) for n in ops][:12])
print(f"total {tot / 1e6:.1f} MB; manifest keys {list(man)}")
