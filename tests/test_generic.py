"""Headless test: Senga Sketch on a scene it was never tuned for.
blender -b --factory-startup --python tests/test_generic.py -- <out_dir>"""
import bpy, sys, os, math
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
import senga_sketch as S
from senga_sketch import i18n
S.register()
sc = bpy.context.scene
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    bpy.data.images.remove(im)
    return a


def render(name):
    sc.render.filepath = f"{OUT}/{name}.png"
    bpy.ops.render.render(write_still=True)
    return load(sc.render.filepath)


# default startup: Cube (material), Light (point 1000 W), Camera
cube = bpy.data.objects["Cube"]; cube.location = (-2.2, 0, 0)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(0, 0, 0)); sph = bpy.context.active_object
bpy.ops.object.shade_smooth(); sph.color = (0.9, 0.35, 0.3, 1)
bpy.ops.object.text_add(location=(-1.5, -1.6, -0.9)); txt = bpy.context.active_object
txt.data.body = "Senga"; txt.data.extrude = 0.08; txt.rotation_euler = (math.radians(90), 0, 0)
bpy.ops.curve.primitive_bezier_circle_add(radius=0.6, location=(2.2, 0, 0)); crv = bpy.context.active_object
crv.data.bevel_depth = 0.15; crv.rotation_euler = (math.radians(70), 0, 0)
bpy.ops.mesh.primitive_monkey_add(size=1.2, location=(0, 2.2, 0.2)); mk = bpy.context.active_object
ca = mk.data.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
for i, d in enumerate(ca.data):
    d.color = (0.2 + 0.6 * (i % 7) / 7, 0.5, 0.9 - 0.6 * (i % 5) / 5, 1)
mk.data.color_attributes.active_color = ca
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1.2, location=(2.2, 2.2, 0)); cyl = bpy.context.active_object
m = bpy.data.materials.new("DiffuseImg"); nt = m.node_tree; nt.nodes.clear()
img = bpy.data.images.new("chk", 256, 256); img.generated_type = "COLOR_GRID"
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = img
df = nt.nodes.new("ShaderNodeBsdfDiffuse"); out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(ti.outputs[0], df.inputs["Color"]); nt.links.new(df.outputs[0], out.inputs["Surface"])
cyl.data.materials.append(m)
bpy.ops.mesh.primitive_ico_sphere_add(radius=0.35, location=(-2.2, 2.2, 0)); ico = bpy.context.active_object
me = bpy.data.materials.new("EmitOnly"); nt = me.node_tree; nt.nodes.clear()
em = nt.nodes.new("ShaderNodeEmission"); em.inputs[0].default_value = (1, 0.6, 0.2, 1); em.inputs[1].default_value = 3
o2 = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], o2.inputs["Surface"]); ico.data.materials.append(me)
# glass stays glass
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(1.1, -1.2, -0.6)); gls = bpy.context.active_object
mg = bpy.data.materials.new("Glass"); bs = next(n for n in mg.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bs.inputs["Transmission Weight"].default_value = 1.0; gls.data.materials.append(mg)
col = bpy.data.collections.new("Asset")
bpy.ops.mesh.primitive_cone_add(radius1=0.4, depth=0.9, location=(0, 0, 0)); cone = bpy.context.active_object
for c in cone.users_collection:
    c.objects.unlink(cone)
col.objects.link(cone)
inst = bpy.data.objects.new("ConeInstance", None); inst.instance_type = "COLLECTION"; inst.instance_collection = col
inst.location = (0, -2.2, -0.5); sc.collection.objects.link(inst)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -1)); gnd = bpy.context.active_object
cam = bpy.data.objects["Camera"]; cam.location = (0, -10.5, 5.5); cam.rotation_euler = (math.radians(63), 0, 0)
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1280, 720, 50
bpy.ops.object.select_all(action="DESELECT")
prev_view = sc.view_settings.view_transform
prev_film = sc.render.film_transparent

r = bpy.ops.senga.apply_all()
check(r == {"FINISHED"}, "apply_all finished")
s = sc.senga
key = s.key_light
check(key is not None and key.name == "Light" and bpy.data.objects.get("Senga Key Sun") is None,
      "existing point light used as key (no extra Sun)")
check(0.3 < s.light_scale < 5, f"point-light Light Scale is irradiance at the subject ({s.light_scale:.2f})")
check(sph.data.materials and sph.data.materials[0].get("senga"), "material-less sphere got a sketch material")
check(mk.data.materials and any(n.type == "VERTEX_COLOR" for n in mk.data.materials[0].node_tree.nodes), "vertex colours kept")
check(txt.data.materials and txt.data.materials[0].get("senga"), "text object sketched")
check(crv.data.materials and crv.data.materials[0].get("senga"), "curve object sketched")
grp = next(n for n in m.node_tree.nodes if n.type == "GROUP")
check(grp.inputs["Base Color"].is_linked and grp.inputs["Base Color"].links[0].from_node.type == "TEX_IMAGE",
      "diffuse+image base colour linked")
ge = next(n for n in me.node_tree.nodes if n.type == "GROUP")
check(tuple(round(x, 2) for x in ge.inputs["Base Color"].default_value[:3]) == (1.0, 0.6, 0.2), "emission colour used as base")
check(not mg.get("senga") and mg.get("senga_glass"), "glass material left alone")
check(cone.data.materials and cone.data.materials[0].get("senga"), "collection-instance object sketched")
check(cone.modifiers.get(S.OUTLINE_MOD) is not None, "collection-instance object outlined")
check(gnd.modifiers.get(S.OUTLINE_MOD) is None, "ground plane skipped by outline")
check(sc.render.film_transparent and sc.render.engine.startswith("BLENDER_EEVEE"), "EEVEE + transparent film")
aovs = {a.name for a in sc.view_layers[0].aovs}
check({"senga_ink", "senga_wash", "senga_hi", "senga_n"} <= aovs, "AOVs registered")
print("FIT ref", round(s.outline_ref_distance, 2))
a = render("generic_sketch")
paper = np.array(s.paper_color)
dark = (a.mean(axis=2) < 0.25).mean()
check(0.01 < dark < 0.5, f"ink drawn ({dark * 100:.1f} % dark pixels)")
corner = a[-10:, -10:].reshape(-1, 3).mean(axis=0)
check(float(corner.min()) > 0.6 and float(np.abs(corner - corner.mean()).max()) < 0.1,
      f"paper fills the background (corner {np.round(corner, 3).tolist()})")

# ink coverage reaches the compositor (value AOVs came through empty once)
ng = sc.compositing_node_group
rl = next(n for n in ng.nodes if n.type == "R_LAYERS")
go = next(n for n in ng.nodes if n.type == "GROUP_OUTPUT")
keep = go.inputs[0].links[0].from_socket
ng.links.new(next(o for o in rl.outputs if o.name == "senga_ink"), go.inputs[0])
cov = render("aov_ink")
ng.links.new(keep, go.inputs[0])
check(cov[:, :, 0].max() > 0.9 and cov[:, :, 1].max() > 0.9, "ink AOV carries coverage (R) and hull flag (G)")

# a static shot must not flicker with defaults (only outlines boil)
def frame(f):
    sc.frame_set(f)
    return render(f"flicker_{f}")
fr = [frame(f) for f in (1, 2, 3)]
chg = max(float((np.abs(fr[i] - fr[i - 1]).max(axis=2) > 8 / 255).mean() * 100) for i in (1, 2))
check(not s.hatch_boil and chg < 3.0, f"static shot does not flicker ({chg:.1f} % of pixels change)")
sc.frame_set(1)

# tiny-scene fit: everything x0.05 -> reference distance ~1/20 (line width stays the same on screen)
f0 = s.outline_ref_distance
for o in (cube, sph, txt, crv, mk, cyl, ico, gls, inst, gnd):
    o.scale = tuple(x * 0.05 for x in o.scale); o.location = tuple(x * 0.05 for x in o.location)
cam.location = tuple(x * 0.05 for x in cam.location)
bpy.context.view_layer.update()
bpy.ops.senga.fit_scene()
check(15 < f0 / s.outline_ref_distance < 25, f"fit_to_scene follows a tiny scene ({f0 / s.outline_ref_distance:.1f}x closer)")
mod = cube.modifiers.get(S.OUTLINE_MOD)
th = next(getattr(mod.properties.inputs, it.identifier).value for it in mod.node_group.interface.items_tree
          if getattr(it, "in_out", None) == "INPUT" and it.name == "Thickness")
check(abs(th - 0.0058 / 6 * 1.6 * s.line_width * s.outline_ref_distance) < 1e-7, f"outline width follows the fit ({th:.5f})")
render("generic_tiny")

# media + papers: every medium sets the same keys (lossless), papers never touch technique keys
eq = lambda a_, b_: a_ == b_ if isinstance(b_, str) else (abs(a_ - b_) < 1e-5 if not hasattr(b_, "__len__")
                                                          else max(abs(x - y) for x, y in zip(a_, b_)) < 1e-5)
keysets = {k: set(v) for k, v in S.MEDIA.items()}
check(len({frozenset(v) for v in keysets.values()}) == 1, "every medium sets the same key set")
check(not (set().union(*[set(p) for p in S.PAPERS.values()]) & keysets["PEN"]), "paper keys and medium keys are disjoint")
fit_ref = s.outline_ref_distance
for med in S.MEDIA:
    s.medium = med
    if med in ("PENCIL", "ENGRAVING", "STIPPLE"):
        render(f"medium_{med.lower()}")
check(s.outline_ref_distance == fit_ref, "media keep fitted distances")
s.medium = "PEN"
check(all(eq(getattr(s, k), v) for k, v in S.MEDIA["PEN"].items()), "switching media back to pen is lossless")
for pap in S.PAPERS:
    s.paper = pap
    if pap in ("CHALKBOARD", "KRAFT"):
        render(f"paper_{pap.lower()}")
check(s.tone_invert == 0.0 and s.wash_amount > 0, "paper sets its keys")
s.paper = "SKETCHBOOK"
check(s.pattern_id == 0.0, "pattern id synced")
s.medium = "SCREENTONE"
check(s.pattern_id == 1.0, "screentone pattern id synced")
s.medium = "PEN"

# variation
before = {k: (tuple(getattr(s, k)) if k in ("paper_color", "ink_color") else getattr(s, k)) for k in S.VARY_KEYS}
bpy.ops.senga.shuffle(); v1 = s.variation; a1 = s.hatch_angle
bpy.ops.senga.shuffle(); bpy.ops.senga.shuffle()
s.variation = v1
check(v1 > 0 and abs(s.hatch_angle - a1) < 1e-6, "variation is reproducible from its number")
s.medium = "CHARCOAL"; s.medium = "PEN"
check(abs(s.hatch_angle - a1) < 1e-6, "variation survives a medium round trip")
s.variation = 0
after = {k: (tuple(getattr(s, k)) if k in ("paper_color", "ink_color") else getattr(s, k)) for k in S.VARY_KEYS}
check(all(eq(after[k], before[k]) for k in S.VARY_KEYS), "variation 0 restores the base look")

# object override
cube.senga_obj.use_override = True
check(abs(cube.senga_obj.hatch_amount - s.hatch_amount) < 1e-6, "override starts from scene values")
cube.senga_obj.hatch_amount = 0.0
cube.senga_obj.use_override = False

# translations: label, operator, tooltip, enum item, report, in every language
import bpy.app.translations as T
view = bpy.context.preferences.view
view.use_translate_interface = view.use_translate_tooltips = True
for loc, exp_label, exp_op, exp_enum in (("ja_JP", "画材", "線画にする", "鉛筆デッサン"),
                                         ("zh_HANS", "画材", "变成线画", "铅笔素描"),
                                         ("ko_KR", "재료", "선화로 만들기", "연필 소묘")):
    view.language = loc
    ok = (T.pgettext_iface("Drawing Medium") == exp_label and T.pgettext_iface("Make It Senga", "Operator") == exp_op
          and T.pgettext_iface("Graphite Pencil") == exp_enum and i18n.t("Drawing Medium") == exp_label
          and T.pgettext_tip("Soft grey shading under the lines") != "Soft grey shading under the lines"
          and i18n.report("Sketch look on 3 object(s)") != "Sketch look on 3 object(s)")
    check(ok, f"translations work in {loc}")
view.language = "en_US"
check(i18n.t("Drawing Medium") == "Drawing Medium", "English is the source")

# revert
r = bpy.ops.senga.revert()
check(sc.compositing_node_group is None, "revert restored compositor")
check(sc.view_settings.view_transform == prev_view and sc.render.film_transparent == prev_film,
      "revert restored view transform and film")
check(len(sph.data.materials) == 0, "revert removed auto material")
check(not m.get("senga") and m.node_tree.nodes["Diffuse BSDF"].outputs[0].links[0].to_node.type == "OUTPUT_MATERIAL",
      "revert restored diffuse material")
check(all(o.modifiers.get(S.OUTLINE_MOD) is None for o in (cube, sph, mk, cyl, cone)), "revert removed outlines")
S.unregister()
check(not hasattr(bpy.types.Scene, "senga"), "unregister clean")
print("RESULT", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
