# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Senga Sketch in one command. Written for AI agents; humans just ask their agent.

Install (once, permanent):
  blender -b --python senga_agent.py -- --install senga_sketch-x.y.z.zip
  (never add --factory-startup here: the install is saved into the user's preferences)

Sketch a .blend:
  blender -b scene.blend --python senga_agent.py -- --medium PENCIL --save scene_sketch.blend --render preview.png

Sketch a model file straight away (.glb .gltf .fbx .obj); a camera (and a key light, if needed) is added:
  blender -b --python senga_agent.py -- --model chair.glb --medium PEN --render preview.png

Options:
  --install ZIP         install + enable the extension from a zip (saved to user preferences)
  --model PATH          import this model into an empty scene first
  --medium NAME         technique: PEN PENCIL CHARCOAL BALLPOINT INK_WASH ENGRAVING SCREENTONE STIPPLE
  --paper NAME          paper & ink: SKETCHBOOK SEPIA KRAFT TONED_GREY NOTEBOOK BLUEPRINT CHALKBOARD WATERCOLOUR
  --variation N         re-roll hatch angle / spacing / wobble / breakup / edge fade / paper shade (0 = off)
  --shuffle             pick a random variation (printed, so it can be repeated with --variation N)
  --set KEY=VALUE       any look setting, repeatable, e.g. --set hatch_spacing=0.008 --set outline_enable=false
  --objects A,B         only these objects (default: every visible object)
  --frame-camera        add a "Senga Camera" aimed at the objects (the user's camera is left alone)
  --preview-size PCT    render size in % of the scene resolution, e.g. 50 for quick previews
  --save PATH           save the .blend here (default: do not save)
  --render PATH         render a PNG (adds a camera if the scene has none)
  --revert              take Senga Sketch out of the scene again
  --ui-language L       panel language AUTO EN JA ZH KO (saved to user preferences)
  --list                print media, papers and settings, then exit
Exit code 0 on success; the last line printed starts with "SENGA OK" or "SENGA ERROR".
"""

import math
import os
import random
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, flag=False):
    if name not in argv:
        return default
    if flag:
        return True
    i = argv.index(name)
    return argv[i + 1] if i + 1 < len(argv) else default


def args(name):
    return [argv[i + 1] for i, a in enumerate(argv) if a == name and i + 1 < len(argv)]


def fail(msg):
    print("SENGA ERROR", msg)
    sys.exit(1)


def installed():
    return "senga" in bpy.types.Scene.bl_rna.properties


def install(zip_path):
    zip_path = os.path.abspath(zip_path)
    if not os.path.isfile(zip_path):
        fail(f"zip not found: {zip_path}")
    if bpy.app.factory_startup:
        fail("do not use --factory-startup when installing; it would overwrite the user's preferences")
    bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    if not installed():
        import addon_utils
        addon_utils.enable("bl_ext.user_default.senga_sketch", default_set=True, persistent=True)
    bpy.ops.wm.save_userpref()
    if not installed():
        fail("install finished but the add-on did not load")
    print("Senga Sketch installed:", zip_path)


def import_model(path):
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        fail(f"model not found: {path}")
    for ob in list(bpy.context.scene.objects):
        if ob.type != "CAMERA":
            bpy.data.objects.remove(ob)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        fail(f"unsupported model type {ext} (use .glb .gltf .fbx .obj)")


def targets(scene, names):
    if names:
        objs = [scene.objects.get(n) for n in names]
        missing = [n for n, o in zip(names, objs) if o is None]
        if missing:
            fail(f"objects not found: {', '.join(missing)}")
        return objs
    return [o for o in scene.objects if o.type in {"MESH", "CURVE", "FONT", "SURFACE"} and o.visible_get()]


def aim_camera(scene, objs, name="Senga Camera"):
    cam = scene.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        scene.collection.objects.link(cam)
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box] or [Vector((0, 0, 0))]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr, size = (lo + hi) / 2, max(max(hi - lo), 1e-3)
    cam.data.lens = 50
    d = size * 2.3
    cam.location = ctr + Vector((d * 0.62, -d * 0.78, d * 0.38))
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = max(100.0, d * 20)
    scene.camera = cam
    return cam


def parse_value(prop, text):
    rna = bpy.types.Scene.bl_rna.properties["senga"].fixed_type.bl_rna.properties[prop]
    if rna.type == "BOOLEAN":
        return text.lower() in ("1", "true", "yes", "on")
    if rna.type == "INT":
        return int(float(text))
    if rna.type == "ENUM":
        return text.upper()
    if getattr(rna, "is_array", False):
        return tuple(float(x) for x in text.split(","))
    return float(text)


def main():
    zip_path = arg("--install")
    if zip_path and not installed():
        install(zip_path)
    elif zip_path:
        print("Senga Sketch already installed")
    if not installed():
        fail("Senga Sketch is not installed (run with --install senga_sketch-x.y.z.zip)")
    S = bpy.types.Scene.bl_rna.properties["senga"].fixed_type.bl_rna.properties

    lang = arg("--ui-language")
    if lang:
        lang = lang.upper()
        if lang not in ("AUTO", "EN", "JA", "ZH", "KO"):
            fail("--ui-language must be AUTO, EN, JA, ZH or KO")
        if bpy.app.factory_startup:
            fail("do not use --factory-startup with --ui-language; it is saved into the user's preferences")
        addon = next((a for k, a in bpy.context.preferences.addons.items() if k.endswith("senga_sketch")), None)
        if addon is None or addon.preferences is None:
            fail("Senga Sketch preferences not found")
        addon.preferences.ui_language = lang
        bpy.ops.wm.save_userpref()
        print("panel language:", lang)

    if arg("--list", flag=True):
        for key in ("medium", "paper", "pattern"):
            for it in S[key].enum_items:
                print(f"{key:7s} {it.identifier:12s} {it.name:20s} {it.description}")
        print("settings:", " ".join(k for k in S.keys() if k not in ("rna_type", "alive", "key_light", "pattern_id", "hatch_phase")))
        print("SENGA OK listed")
        return

    if arg("--model"):
        import_model(arg("--model"))
    scene = bpy.context.scene

    if arg("--revert", flag=True):
        scene.senga.only_selected = False
        bpy.ops.senga.revert()
        report = "reverted"
    else:
        job = ("--paper", "--medium", "--variation", "--shuffle", "--set", "--model", "--objects", "--save", "--render")
        if not any(a in argv for a in job):
            print("SENGA OK", "installed" if zip_path else "nothing to do")
            return
        names = arg("--objects")
        objs = targets(scene, names.split(",") if names else None)
        if not objs:
            fail("nothing to draw: the scene has no visible mesh, curve or text objects")
        if arg("--frame-camera", flag=True) or arg("--model") or scene.camera is None:
            aim_camera(scene, objs)
        if arg("--model") and scene.world and scene.world.node_tree:      # soft studio sky instead of Blender's dark grey (lights the tone evenly)
            bg = next((n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"), None)
            if bg and not bg.inputs["Color"].is_linked:
                bg.inputs["Color"].default_value = (0.55, 0.6, 0.72, 1.0)
                bg.inputs["Strength"].default_value = 0.8
        s = scene.senga
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        s.only_selected = bool(names)
        already = any(m.get("senga") for m in bpy.data.materials)
        if not already or arg("--model") or names:
            r = bpy.ops.senga.apply_all()
            if r != {"FINISHED"}:
                fail("Make It Senga did not finish")
        try:
            if arg("--paper"):
                s.paper = arg("--paper").upper()
            if arg("--medium"):
                s.medium = arg("--medium").upper()
            if arg("--shuffle", flag=True):
                s.variation = random.randint(1, 9999)
            elif arg("--variation") is not None:
                s.variation = int(arg("--variation"))
            for kv in args("--set"):
                k, _, v = kv.partition("=")
                if k not in S.keys():
                    fail(f"unknown setting {k!r} (see --list)")
                setattr(s, k, parse_value(k, v))
        except TypeError as err:
            fail(f"{err} (see --list for valid names)")
        report = f"medium {s.medium}, paper {s.paper}, variation {s.variation}, {len(objs)} object(s)"
    print(report)

    render = arg("--render")
    if render:
        if scene.camera is None:
            aim_camera(scene, targets(scene, None))
        if arg("--preview-size"):
            scene.render.resolution_percentage = int(float(arg("--preview-size")))
        scene.render.filepath = os.path.abspath(render)
        bpy.ops.render.render(write_still=True)
        print("preview:", scene.render.filepath)
    save = arg("--save")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save))
        print("saved:", os.path.abspath(save))
    print("SENGA OK", report)


main()
