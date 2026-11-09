# SPDX-License-Identifier: GPL-3.0-or-later
"""Hand-inked inverted-hull outline (Geometry Nodes): constant screen width, broken
pen pressure, boil on twos, and heavier lines on the side turned away from the light
(the classic inker's trick that makes a drawing feel lit)."""
import bpy
from .util import (TAG, OUTLINE_GROUP, OUTLINE_MAT, OUTLINE_MOD, AOV_COVER, AOV_WASH, AOV_NORMAL,
                   sock, new, iface, math, vmath)

INK_VER = 4
GROUP_VER = 6
LINE_ANG = 0.0058 / 6.0 * 1.6


def build_outline_material():
    """Emission ink + AOVs (coverage 1, no wash) so the compositor treats it as ink."""
    mat = bpy.data.materials.get(OUTLINE_MAT) or bpy.data.materials.new(OUTLINE_MAT)
    if hasattr(mat, "use_nodes") and not mat.node_tree:
        mat.use_nodes = True
    mat.use_backface_culling = True
    if hasattr(mat, "use_backface_culling_shadow"):
        mat.use_backface_culling_shadow = True
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = new(N, "ShaderNodeOutputMaterial", (500, 0))
    ink = new(N, "ShaderNodeAttribute", (-700, 100), "Ink Colour")
    ink.attribute_type = "VIEW_LAYER"; ink.attribute_name = "senga.ink_color"
    alive = new(N, "ShaderNodeAttribute", (-700, -100), "Alive")
    alive.attribute_type = "VIEW_LAYER"; alive.attribute_name = "senga.alive"
    fb = new(N, "ShaderNodeRGB", (-700, 250), "Senga Fallback ink_color")
    fb["senga_prop"] = "ink_color"
    fb.outputs[0].default_value = (0.02, 0.02, 0.025, 1.0)
    mx = new(N, "ShaderNodeMix", (-400, 100), "Ink Mix"); mx.data_type = "RGBA"
    L.new(alive.outputs["Factor"], sock(mx.inputs, "Factor", "VALUE"))
    L.new(fb.outputs[0], sock(mx.inputs, "A", "RGBA"))
    L.new(ink.outputs["Color"], sock(mx.inputs, "B", "RGBA"))
    em = new(N, "ShaderNodeEmission", (0, 80), "Ink")
    L.new(sock(mx.outputs, "Result", "RGBA"), em.inputs["Color"])
    lp = new(N, "ShaderNodeLightPath", (0, 300))
    tr = new(N, "ShaderNodeBsdfTransparent", (0, -80))
    ms = new(N, "ShaderNodeMixShader", (250, 0))
    L.new(lp.outputs["Is Shadow Ray"], ms.inputs[0])
    L.new(em.outputs[0], ms.inputs[1]); L.new(tr.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], out.inputs["Surface"])
    a1 = new(N, "ShaderNodeOutputAOV", (500, -200), "Senga AOV Ink"); a1.aov_name = AOV_COVER
    a1.inputs["Color"].default_value = (1.0, 1.0, 0.0, 1.0)     # R coverage, G = "this is the outline hull"
    a2 = new(N, "ShaderNodeOutputAOV", (500, -350), "Senga AOV Wash"); a2.aov_name = AOV_WASH
    a2.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    a3 = new(N, "ShaderNodeOutputAOV", (500, -500), "Senga AOV Normal"); a3.aov_name = AOV_NORMAL
    a3.inputs["Color"].default_value = (0.5, 0.5, 1.0, 1.0)
    mat[TAG + "_ver"] = INK_VER
    return mat


def build_outline_group(rebuild=False):
    ng = bpy.data.node_groups.get(OUTLINE_GROUP)
    if ng and not rebuild and ng.get(TAG + "_ver") == GROUP_VER:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(OUTLINE_GROUP, "GeometryNodeTree")
    ng.is_modifier = True
    ng.nodes.clear()
    ng.interface.clear()
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Thickness", "INPUT", "NodeSocketFloat", 0.008, 0.0, 1.0)
    iface(ng, "Screen Space", "INPUT", "NodeSocketFloat", 1.0, 0.0, 1.0)
    iface(ng, "Reference Distance", "INPUT", "NodeSocketFloat", 6.0, 0.01, 1000.0)
    iface(ng, "Fade Distance", "INPUT", "NodeSocketFloat", 30.0, 0.01, 10000.0)
    iface(ng, "Fade Min", "INPUT", "NodeSocketFloat", 0.35, 0.0, 1.0)
    iface(ng, "Jitter", "INPUT", "NodeSocketFloat", 0.7, 0.0, 1.0)
    iface(ng, "Jitter Scale", "INPUT", "NodeSocketFloat", 6.0, 0.0, 100.0)
    iface(ng, "Boil", "INPUT", "NodeSocketFloat", 1.0, 0.0, 1.0)
    iface(ng, "Boil Rate", "INPUT", "NodeSocketFloat", 2.0, 1.0, 24.0)
    iface(ng, "Camera Push", "INPUT", "NodeSocketFloat", 3.0, 0.0, 10.0)
    iface(ng, "Weld Seams", "INPUT", "NodeSocketBool", True)
    iface(ng, "Light", "INPUT", "NodeSocketObject")
    iface(ng, "Light Is Sun", "INPUT", "NodeSocketBool", True)
    iface(ng, "Light Weight", "INPUT", "NodeSocketFloat", 0.6, 0.0, 1.0)
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    ng[TAG + "_ver"] = GROUP_VER
    N, L = ng.nodes, ng.links
    gi = new(N, "NodeGroupInput", (-1800, 0))
    go = new(N, "NodeGroupOutput", (1200, 0))
    I = lambda n: gi.outputs[n]

    merge = new(N, "GeometryNodeMergeByDistance", (-1300, -150))
    merge.inputs["Distance"].default_value = 0.0005
    L.new(I("Geometry"), merge.inputs["Geometry"])
    weld = new(N, "GeometryNodeSwitch", (-1150, -150), "Weld Switch")
    weld.input_type = "GEOMETRY"
    L.new(I("Weld Seams"), weld.inputs["Switch"])
    L.new(I("Geometry"), weld.inputs["False"])
    L.new(merge.outputs[0], weld.inputs["True"])

    pos = new(N, "GeometryNodeInputPosition", (-1400, -400))
    nrm = new(N, "GeometryNodeInputNormal", (-1400, -300))
    cam = new(N, "GeometryNodeInputActiveCamera", (-1600, -600))
    oi = new(N, "GeometryNodeObjectInfo", (-1400, -600))
    oi.transform_space = "RELATIVE"
    L.new(cam.outputs[0], oi.inputs["Object"])
    rel = vmath(N, (-1200, -500), "SUBTRACT")
    L.new(pos.outputs[0], rel.inputs[0]); L.new(oi.outputs["Location"], rel.inputs[1])
    selfo = new(N, "GeometryNodeSelfObject", (-1800, -800))
    soi = new(N, "GeometryNodeObjectInfo", (-1600, -800))
    soi.transform_space = "ORIGINAL"
    L.new(selfo.outputs[0], soi.inputs["Object"])
    sab = vmath(N, (-1450, -800), "ABSOLUTE"); L.new(soi.outputs["Scale"], sab.inputs[0])
    sdot = vmath(N, (-1300, -800), "DOT_PRODUCT"); L.new(sab.outputs[0], sdot.inputs[0])
    sdot.inputs[1].default_value = (1 / 3, 1 / 3, 1 / 3)
    wsc = math(N, (-1150, -800), "MAXIMUM", b=1e-8, label="World Scale"); L.new(sdot.outputs["Value"], wsc.inputs[0])
    WS = wsc.outputs[0]
    dl = vmath(N, (-1050, -650), "LENGTH"); L.new(rel.outputs[0], dl.inputs[0])
    dist = math(N, (-950, -600), "MULTIPLY", label="World Distance")
    L.new(dl.outputs["Value"], dist.inputs[0]); L.new(WS, dist.inputs[1])
    away = vmath(N, (-1050, -450), "NORMALIZE"); L.new(rel.outputs[0], away.inputs[0])

    dr = math(N, (-900, -650), "DIVIDE"); L.new(dist.outputs[0], dr.inputs[0]); L.new(I("Reference Distance"), dr.inputs[1])
    ss = new(N, "ShaderNodeMix", (-750, -650)); ss.data_type = "FLOAT"
    L.new(I("Screen Space"), sock(ss.inputs, "Factor", "VALUE"))
    sock(ss.inputs, "A", "VALUE").default_value = 1.0
    L.new(dr.outputs[0], sock(ss.inputs, "B", "VALUE"))
    fade = new(N, "ShaderNodeMapRange", (-750, -850), "Distance Fade")
    fade.clamp = True
    L.new(dist.outputs[0], fade.inputs["Value"])
    L.new(I("Reference Distance"), fade.inputs["From Min"])
    L.new(I("Fade Distance"), fade.inputs["From Max"])
    fade.inputs["To Min"].default_value = 1.0
    L.new(I("Fade Min"), fade.inputs["To Max"])

    # boil on twos
    st = new(N, "GeometryNodeInputSceneTime", (-1400, -1100))
    fr = math(N, (-1250, -1100), "DIVIDE"); L.new(st.outputs["Frame"], fr.inputs[0]); L.new(I("Boil Rate"), fr.inputs[1])
    fl = math(N, (-1100, -1100), "FLOOR"); L.new(fr.outputs[0], fl.inputs[0])
    fw = math(N, (-950, -1100), "MULTIPLY", b=1.37); L.new(fl.outputs[0], fw.inputs[0])
    fb = math(N, (-800, -1100), "MULTIPLY"); L.new(fw.outputs[0], fb.inputs[0]); L.new(I("Boil"), fb.inputs[1])
    nz = new(N, "ShaderNodeTexNoise", (-650, -1050), "Line Noise")
    nz.noise_dimensions = "4D"
    nz.inputs["Detail"].default_value = 1.5
    # pressure noise measured in object sizes, so a ring and a building get the same rhythm
    bb = new(N, "GeometryNodeBoundBox", (-1300, -1250)); L.new(I("Geometry"), bb.inputs[0])
    bbd = vmath(N, (-1150, -1250), "SUBTRACT"); L.new(bb.outputs["Max"], bbd.inputs[0]); L.new(bb.outputs["Min"], bbd.inputs[1])
    bbl = vmath(N, (-1000, -1250), "LENGTH"); L.new(bbd.outputs[0], bbl.inputs[0])
    bbs = math(N, (-900, -1250), "MAXIMUM", b=1e-6); L.new(bbl.outputs["Value"], bbs.inputs[0])
    wpos = vmath(N, (-800, -1000), "DIVIDE"); L.new(pos.outputs[0], wpos.inputs[0])
    bbv = new(N, "ShaderNodeCombineXYZ", (-800, -1150))
    for i in range(3):
        L.new(bbs.outputs[0], bbv.inputs[i])
    L.new(bbv.outputs[0], wpos.inputs[1])
    L.new(wpos.outputs[0], nz.inputs["Vector"])
    L.new(fb.outputs[0], nz.inputs["W"])
    L.new(I("Jitter Scale"), nz.inputs["Scale"])
    nr = new(N, "ShaderNodeMapRange", (-450, -1050), "Line Breakup")
    nr.clamp = True
    nr.inputs["From Min"].default_value = 0.33
    nr.inputs["From Max"].default_value = 0.64
    nr.inputs["To Min"].default_value = 0.45     # a steady nib that swells and thins, never vanishes
    nr.inputs["To Max"].default_value = 1.15
    L.new(nz.outputs[0], nr.inputs["Value"])
    jm = new(N, "ShaderNodeMix", (-300, -1000)); jm.data_type = "FLOAT"
    L.new(I("Jitter"), sock(jm.inputs, "Factor", "VALUE"))
    sock(jm.inputs, "A", "VALUE").default_value = 1.0
    L.new(nr.outputs["Result"], sock(jm.inputs, "B", "VALUE"))

    # light weight: heavier line on the side turned away from the key light
    lio = new(N, "GeometryNodeObjectInfo", (-1400, -1400), "Light Info")
    lio.transform_space = "RELATIVE"
    L.new(I("Light"), lio.inputs["Object"])
    rv = new(N, "FunctionNodeRotateVector", (-1200, -1400))
    rv.inputs["Vector"].default_value = (0.0, 0.0, 1.0)
    L.new(lio.outputs["Rotation"], rv.inputs["Rotation"])
    tol = vmath(N, (-1200, -1550), "SUBTRACT"); L.new(lio.outputs["Location"], tol.inputs[0]); L.new(pos.outputs[0], tol.inputs[1])
    ldir = new(N, "GeometryNodeSwitch", (-1000, -1450), "Light Direction"); ldir.input_type = "VECTOR"
    L.new(I("Light Is Sun"), ldir.inputs["Switch"])
    L.new(tol.outputs[0], ldir.inputs["False"]); L.new(rv.outputs[0], ldir.inputs["True"])
    ln = vmath(N, (-850, -1450), "NORMALIZE"); L.new(ldir.outputs[0], ln.inputs[0])
    ldot = vmath(N, (-700, -1400), "DOT_PRODUCT"); L.new(nrm.outputs[0], ldot.inputs[0]); L.new(ln.outputs[0], ldot.inputs[1])
    # dot 1 (lit) -> 0.75, dot -1 (dark side) -> 1.8
    lw = new(N, "ShaderNodeMapRange", (-550, -1400), "Light Weight Curve")
    lw.clamp = True; lw.interpolation_type = "SMOOTHSTEP"
    lw.inputs["From Min"].default_value = -0.6; lw.inputs["From Max"].default_value = 0.8
    lw.inputs["To Min"].default_value = 1.8; lw.inputs["To Max"].default_value = 0.75
    L.new(ldot.outputs["Value"], lw.inputs["Value"])
    has_l = new(N, "FunctionNodeCompare", (-700, -1600)); has_l.data_type = "FLOAT"; has_l.operation = "GREATER_THAN"
    # no light object -> Light Info scale is 0
    ls = vmath(N, (-850, -1650), "LENGTH"); L.new(lio.outputs["Scale"], ls.inputs[0])
    L.new(ls.outputs["Value"], has_l.inputs[0]); has_l.inputs[1].default_value = 0.0
    lwf = math(N, (-550, -1600), "MULTIPLY"); L.new(I("Light Weight"), lwf.inputs[0]); L.new(has_l.outputs[0], lwf.inputs[1])
    lwm = new(N, "ShaderNodeMix", (-350, -1450)); lwm.data_type = "FLOAT"
    L.new(lwf.outputs[0], sock(lwm.inputs, "Factor", "VALUE"))
    sock(lwm.inputs, "A", "VALUE").default_value = 1.0
    L.new(lw.outputs["Result"], sock(lwm.inputs, "B", "VALUE"))

    t1 = math(N, (-500, -650), "MULTIPLY"); L.new(I("Thickness"), t1.inputs[0]); L.new(sock(ss.outputs, "Result", "VALUE"), t1.inputs[1])
    t2 = math(N, (-350, -700), "MULTIPLY"); L.new(t1.outputs[0], t2.inputs[0]); L.new(fade.outputs["Result"], t2.inputs[1])
    t3 = math(N, (-150, -750), "MULTIPLY"); L.new(t2.outputs[0], t3.inputs[0]); L.new(sock(jm.outputs, "Result", "VALUE"), t3.inputs[1])
    t4 = math(N, (-50, -850), "MULTIPLY", label="Light Weighted"); L.new(t3.outputs[0], t4.inputs[0])
    L.new(sock(lwm.outputs, "Result", "VALUE"), t4.inputs[1])

    t3l = math(N, (50, -750), "DIVIDE", label="To Object Space"); L.new(t4.outputs[0], t3l.inputs[0]); L.new(WS, t3l.inputs[1])
    off_n = vmath(N, (150, -400), "SCALE"); L.new(nrm.outputs[0], off_n.inputs[0]); L.new(t3l.outputs[0], off_n.inputs["Scale"])
    pushw = math(N, (0, -650), "MULTIPLY"); L.new(t2.outputs[0], pushw.inputs[0]); L.new(I("Camera Push"), pushw.inputs[1])
    pushf = math(N, (100, -650), "DIVIDE"); L.new(pushw.outputs[0], pushf.inputs[0]); L.new(WS, pushf.inputs[1])
    off_c = vmath(N, (250, -550), "SCALE"); L.new(away.outputs[0], off_c.inputs[0]); L.new(pushf.outputs[0], off_c.inputs["Scale"])
    off = vmath(N, (400, -450), "ADD"); L.new(off_n.outputs[0], off.inputs[0]); L.new(off_c.outputs[0], off.inputs[1])

    setp = new(N, "GeometryNodeSetPosition", (500, -150))
    L.new(weld.outputs[0], setp.inputs["Geometry"]); L.new(off.outputs[0], setp.inputs["Offset"])
    flip = new(N, "GeometryNodeFlipFaces", (680, -150)); L.new(setp.outputs[0], flip.inputs[0])
    smat = new(N, "GeometryNodeSetMaterial", (840, -150))
    L.new(flip.outputs[0], smat.inputs["Geometry"]); L.new(I("Material"), smat.inputs["Material"])
    join = new(N, "GeometryNodeJoinGeometry", (1000, 0))
    L.new(smat.outputs[0], join.inputs[0]); L.new(I("Geometry"), join.inputs[0])
    L.new(join.outputs[0], go.inputs["Geometry"])
    return ng


def set_mod_input(mod, name, value):
    for item in mod.node_group.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == name:
            props = getattr(mod, "properties", None)          # Blender 5.x
            if props is not None and hasattr(props, "inputs"):
                getattr(props.inputs, item.identifier).value = value
            else:                                             # Blender 4.x
                mod[item.identifier] = value
            return True
    return False


def is_flat_plane(obj):
    vs = obj.data.vertices
    if not vs or len(obj.data.polygons) > 256:
        return False
    zs = [v.co.z for v in vs]
    xs = [v.co.x for v in vs]
    return (max(zs) - min(zs)) < 1e-4 * max(1e-6, max(xs) - min(xs)) + 1e-6


def add_outline(obj, scene):
    if obj.type != "MESH" or obj.get(TAG + "_skip") or not obj.is_editable:
        return False
    if is_flat_plane(obj):
        obj[TAG + "_ground"] = 1.0           # read by the material: no contour along the ground's far edge
        return False
    build_outline_group()
    mat = bpy.data.materials.get(OUTLINE_MAT)
    if mat is None or mat.get(TAG + "_ver") != INK_VER:
        mat = build_outline_material()
    mod = obj.modifiers.get(OUTLINE_MOD) or obj.modifiers.new(OUTLINE_MOD, "NODES")
    mod.node_group = bpy.data.node_groups[OUTLINE_GROUP]
    set_mod_input(mod, "Material", mat)
    apply_outline_settings(scene, [obj])
    return True


def remove_outline(obj):
    if not obj.is_editable:
        return
    if TAG + "_ground" in obj:
        del obj[TAG + "_ground"]
    mod = obj.modifiers.get(OUTLINE_MOD)
    if mod:
        obj.modifiers.remove(mod)


def apply_outline_settings(scene, objs=None):
    s = scene.senga
    mat = bpy.data.materials.get(OUTLINE_MAT)
    if mat and mat.node_tree:
        fb = mat.node_tree.nodes.get("Senga Fallback ink_color")
        if fb is not None:
            fb.outputs[0].default_value = tuple(s.ink_color) + (1.0,)
        mat.node_tree.update_tag()
    if not objs:
        from .autosetup import expand
        objs = [o for o in expand(scene.objects) if o.modifiers.get(OUTLINE_MOD)]
    key = s.key_light if (s.key_light and s.key_light.type == "LIGHT") else None
    for o in objs:
        mod = o.modifiers.get(OUTLINE_MOD)
        if not mod or not mod.node_group:
            continue
        ov = getattr(o, "senga_obj", None)
        scale = ov.outline_scale if (ov and ov.use_override) else 1.0
        enabled = s.outline_enable and not (ov and ov.use_override and not ov.outline_enable)
        dark = 1.0 - 0.45 * s.tone_invert          # chalk / blueprint lines are thinner
        # Line Width 1 = 1.55 mm per metre of camera distance (a pen nib at any scene scale)
        width = LINE_ANG * s.line_width * s.outline_ref_distance
        set_mod_input(mod, "Thickness", width * scale * dark)
        set_mod_input(mod, "Screen Space", 1.0)
        set_mod_input(mod, "Reference Distance", s.outline_ref_distance)
        set_mod_input(mod, "Fade Distance", s.outline_fade_distance)
        set_mod_input(mod, "Fade Min", s.outline_fade_min)
        set_mod_input(mod, "Jitter", s.outline_jitter)
        set_mod_input(mod, "Jitter Scale", s.outline_jitter_scale)
        set_mod_input(mod, "Boil", 1.0 if s.outline_boil else 0.0)
        set_mod_input(mod, "Boil Rate", float(s.boil_rate))
        set_mod_input(mod, "Weld Seams", bool(s.outline_weld))
        set_mod_input(mod, "Light", key)
        set_mod_input(mod, "Light Is Sun", bool(key is None or key.data.type == "SUN"))
        set_mod_input(mod, "Light Weight", s.line_light_weight)
        mod.show_viewport = mod.show_render = enabled
        o.update_tag()
