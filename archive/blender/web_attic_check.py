"""Re-import web parts and render the attic level (roof hidden, ceilings + attic deck shown) to look for wall gaps.
   blender --background --python web_attic_check.py"""
import bpy, os, math, json
from mathutils import Vector
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for p in json.load(open(os.path.join(D, "manifest.json")))["parts"]:
    if p["name"] in ("shell", "interior"):
        bpy.ops.import_scene.gltf(filepath=os.path.join(D, p["file"]))
roof = bpy.data.objects.get("Roof")
for o in [roof] + list(roof.children_recursive) if roof else []:
    o.hide_render = True
for o in bpy.data.objects:
    if "ceiling" in o.name.lower():
        o.hide_render = True
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1.0, 0.2, 0.6, 1)   # magenta sky: any gap shows pink
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sd = bpy.data.lights.new("sun", 'SUN'); sd.energy = 3.0; so = bpy.data.objects.new("sun", sd); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(30), 0, math.radians(20))
sc.render.engine = 'CYCLES'; sc.cycles.samples = 16; sc.cycles.use_denoising = True
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = True
    sc.cycles.device = 'GPU'
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
F = 0.3048
def shot(name, frm, to, lens=24, ortho=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 5000
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho * F
    c = bpy.data.objects.new(name, cd); sc.collection.objects.link(c)
    c.location = Vector(frm) * F
    c.rotation_euler = ((Vector(to) - Vector(frm)) * F).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = c; sc.render.filepath = os.path.join(D, "_attic_" + name + ".png"); bpy.ops.render.render(write_still=True)
shot("top", (21.5, -26, 120), (21.5, -26.01, 0), ortho=58)
shot("hall_from_attic", (5, -16, 13.5), (30, -15, 10.5), 20)
print("ATTIC CHECK OK")
