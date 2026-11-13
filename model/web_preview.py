"""Re-import web/*.glb into an empty scene and render check views (roof hidden):
   blender --background --python web_preview.py"""
import bpy, os, math, json
from mathutils import Vector
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for p in json.load(open(os.path.join(D, "manifest.json")))["parts"]:
    bpy.ops.import_scene.gltf(filepath=os.path.join(D, p["file"]))
roof = bpy.data.objects.get("Roof")
if roof:
    for o in [roof] + list(roof.children_recursive):
        o.hide_render = True
for o in bpy.data.objects:
    if "ceiling" in o.name.lower():
        o.hide_render = True
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.7, 0.8, 1.0, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.2
sd = bpy.data.lights.new("sun", 'SUN'); sd.energy = 3.5; so = bpy.data.objects.new("sun", sd); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(45), 0, math.radians(30))
sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.use_denoising = True
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = True
    sc.cycles.device = 'GPU'
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
F = 0.3048
def shot(name, frm, to, lens=24):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 5000
    c = bpy.data.objects.new(name, cd); sc.collection.objects.link(c)
    c.location = Vector(frm) * F
    c.rotation_euler = ((Vector(to) - Vector(frm)) * F).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = c; sc.render.filepath = os.path.join(D, "_preview_" + name + ".png"); bpy.ops.render.render(write_still=True)
# Blender coords (ft, plan y negated): house spans x 0..43, y 0..-52
shot("dollhouse", (-25, -95, 55), (22, -27, 0))
shot("site", (-140, -260, 90), (40, -30, 5), 24)
shot("kitchen", (12, -47.5, 5.3), (2, -42, 4), 18)
print("PREVIEW OK")
