"""List exported objects whose world position falls outside the house footprint (sanity check for stray furniture).
   blender --background --python web_bounds.py"""
import bpy, os
from mathutils import Vector
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
F = 0.3048
bpy.ops.wm.read_factory_settings(use_empty=True)
for f in ("furniture_west.glb", "furniture_east.glb", "interior.glb"):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(D, f))
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    bad = []
    for o in new:
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        cx = sum(p.x for p in pts) / 8 / F; cy = -sum(p.y for p in pts) / 8 / F; cz = sum(p.z for p in pts) / 8 / F
        if not (-0.5 <= cx <= 43.6 and -0.5 <= cy <= 52.5) or cz < -1 or cz > 25:
            bad.append((o.name, round(cx, 1), round(cy, 1), round(cz, 1), o.parent.name if o.parent else None))
    print(f"{f}: {len(new)} meshes, {len(bad)} outside the house:")
    for b in bad[:40]:
        print("   ", b)
