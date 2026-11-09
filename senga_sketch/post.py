# SPDX-License-Identifier: GPL-3.0-or-later
"""Senga Sketch compositor (Blender 5.x node-group compositor).

Works in "ink coverage" space: the materials write how much ink each pixel holds
(AOV), the compositor adds contour lines found in the normal/depth passes, lets the
paper tooth break the graphite, smudges it, fades the drawing out towards the edges
like an unfinished sketch, then lays ink of any colour onto any paper:

    final = mix(paper x wash, ink colour, coverage) (+ white chalk highlights)

so dark ink on white paper and white chalk on a blackboard use the same graph.
Pixel sizes are authored for a 1920 px long edge and rescaled inside the graph.
"""
import bpy
from .util import (TAG, POST_GROUP, AOV_COVER, AOV_WASH, AOV_HI, AOV_NORMAL, AOV_DEPTH, sock, new, iface, menu,
                   mix, mix_io, math, vmath, maprange, ensure_aov)

VER = 15


def _out(node, name):
    return next((o for o in node.outputs if o.name == name), None)


def _is_post(ng):
    return ng is not None and ng.bl_idname == "CompositorNodeTree" and ng.get(TAG + "_ver") is not None


def scene_post(scene):
    if _is_post(scene.compositing_node_group):
        return scene.compositing_node_group
    return next((g for g in bpy.data.node_groups if _is_post(g) and
                 any(n.type == "R_LAYERS" and n.scene == scene for n in g.nodes)), None)


def build_post(scene, rebuild=False):
    for vl in scene.view_layers:
        ensure_aov(vl, AOV_COVER, "COLOR")    # colour AOVs: value AOVs come through empty in 5.2
        ensure_aov(vl, AOV_WASH, "COLOR")
        ensure_aov(vl, AOV_HI, "COLOR")
        ensure_aov(vl, AOV_NORMAL, "COLOR")
        ensure_aov(vl, AOV_DEPTH, "COLOR")
        vl.use_pass_z = True
    if scene.compositing_node_group and not _is_post(scene.compositing_node_group) \
            and TAG + "_prev_comp" not in scene:
        scene[TAG + "_prev_comp"] = scene.compositing_node_group.name
    ng = scene_post(scene)
    if ng is None or rebuild or ng.get(TAG + "_ver") != VER:
        if ng is None:
            ng = bpy.data.node_groups.new(POST_GROUP, "CompositorNodeTree")
        _build(ng, scene)
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    apply_post_settings(scene)
    return ng


def _value(N, loc, name, v=0.0):
    n = new(N, "ShaderNodeValue", loc, name)
    n.outputs[0].default_value = v
    return n.outputs[0]


def _bw(N, loc):
    try:
        return new(N, "CompositorNodeRGBToBW", loc)
    except RuntimeError:
        return new(N, "ShaderNodeRGBToBW", loc)


def _build(ng, scene):
    ng.nodes.clear()
    ng.interface.clear()
    iface(ng, "Image", "OUTPUT", "NodeSocketColor")
    ng[TAG + "_ver"] = VER
    N, L = ng.nodes, ng.links
    X = -3000
    rl = new(N, "CompositorNodeRLayers", (X, 0), "Render")
    rl.scene = scene
    img = _out(rl, "Image")
    alpha = _out(rl, "Alpha")
    cov_in = _out(rl, AOV_COVER)
    wash_in = _out(rl, AOV_WASH)
    hi_in = _out(rl, AOV_HI)
    nrm_in = _out(rl, AOV_NORMAL)
    z_in = _out(rl, AOV_DEPTH)

    ic = new(N, "CompositorNodeImageCoordinates", (X, -900))
    L.new(img, ic.inputs[0])
    uni, pix, nrmc = ic.outputs["Uniform"], ic.outputs["Pixel"], ic.outputs["Normalized"]
    info = new(N, "CompositorNodeImageInfo", (X, -1200))
    L.new(img, info.inputs[0])
    res = next(o for o in info.outputs if o.name in ("Resolution", "Size"))
    rsep = new(N, "ShaderNodeSeparateXYZ", (X + 180, -1200)); L.new(res, rsep.inputs[0])
    rmax = math(N, (X + 330, -1200), "MAXIMUM"); L.new(rsep.outputs[0], rmax.inputs[0]); L.new(rsep.outputs[1], rmax.inputs[1])
    rs = math(N, (X + 480, -1200), "DIVIDE", b=1920.0, label="Res Scale"); L.new(rmax.outputs[0], rs.inputs[0])
    RS = rs.outputs[0]
    pxn = vmath(N, (X + 480, -1050), "SCALE"); L.new(pix, pxn.inputs[0])
    rinv = math(N, (X + 480, -1350), "DIVIDE", a=1.0); L.new(RS, rinv.inputs[1])
    L.new(rinv.outputs[0], pxn.inputs["Scale"])
    PIX = pxn.outputs[0]            # pixel coords at 1920-px scale (resolution independent)

    def scaled(name, loc, v):
        val = _value(N, loc, name, v)
        m = math(N, (loc[0] + 150, loc[1]), "MULTIPLY")
        L.new(val, m.inputs[0]); L.new(RS, m.inputs[1])
        return m.outputs[0]

    def grey_img(sock_, loc):
        c = new(N, "CompositorNodeCombineColor", loc)
        for i in range(3):
            L.new(sock_, c.inputs[i])
        return c.outputs[0]

    def blur(img_sock, size_sock, loc, name):
        b = new(N, "CompositorNodeBlur", loc, name)
        menu(b.inputs["Type"], "Gaussian", "GAUSS")
        v = new(N, "ShaderNodeCombineXYZ", (loc[0] - 150, loc[1] - 150)); L.new(size_sock, v.inputs[0]); L.new(size_sock, v.inputs[1])
        L.new(v.outputs[0], b.inputs["Size"]); L.new(img_sock, b.inputs["Image"])
        sep = new(N, "CompositorNodeSeparateColor", (loc[0] + 150, loc[1])); L.new(b.outputs[0], sep.inputs[0])
        return b, sep.outputs[0]

    # ------------------------------------------------------------ ink AOV: R shading, G outline hull, B ground
    if cov_in:
        c0s = new(N, "CompositorNodeSeparateColor", (X + 300, 0)); L.new(cov_in, c0s.inputs[0])
        RCH, HULL, GND = c0s.outputs[0], c0s.outputs[1], c0s.outputs[2]
    else:
        RCH = HULL = GND = _value(N, (X + 300, 0), "No Coverage", 0.0)
    # premultiplied shares of one pixel: R = hull share + surface share x coverage, G = hull share
    nh = math(N, (X + 450, 100), "SUBTRACT"); L.new(RCH, nh.inputs[0]); L.new(HULL, nh.inputs[1])
    sh0 = math(N, (X + 600, 100), "MAXIMUM", b=0.0, label="Shading Coverage"); L.new(nh.outputs[0], sh0.inputs[0])
    S0 = sh0.outputs[0]
    if hi_in:
        his = new(N, "CompositorNodeSeparateColor", (X + 300, -1000)); L.new(hi_in, his.inputs[0])
        hi_in = his.outputs[0]

    # grown masks: near the hull (silhouettes are drawn by the hull) and near the ground plane
    _b, hgrow = blur(grey_img(HULL, (X + 450, 1700)), scaled("Hull Grow Px", (X + 300, 1900), 5.0), (X + 650, 1700), "Hull Grow")
    near_h = maprange(N, (X + 900, 1700), 0.0, 0.03, label="Near Hull"); L.new(hgrow, near_h.inputs["Value"])
    _b, ggrow = blur(grey_img(GND, (X + 450, 2100)), scaled("Ground Grow Px", (X + 300, 2300), 4.0), (X + 650, 2100), "Ground Grow")
    near_g = maprange(N, (X + 900, 2100), 0.0, 0.03, label="Near Ground"); L.new(ggrow, near_g.inputs["Value"])
    keep_e = math(N, (X + 1050, 1900), "MAXIMUM"); L.new(near_h.outputs["Result"], keep_e.inputs[0])
    L.new(near_g.outputs["Result"], keep_e.inputs[1])
    keep_e2 = math(N, (X + 1200, 1900), "SUBTRACT", a=1.0, label="Contour Allowed"); L.new(keep_e.outputs[0], keep_e2.inputs[1])

    # ------------------------------------------------------------ contour lines (creases + anti-aliased depth)
    # creases, one-sided: 1 - dot(n, n shifted by 1 px) in x and y -> a single line per crease, not a pair
    if nrm_in:
        nb_ = new(N, "CompositorNodeBlur", (X + 0, 1200), "Normal Soften")
        menu(nb_.inputs["Type"], "Gaussian", "GAUSS")
        nbs = scaled("Normal Soften Px", (X - 200, 1350), 1.5)
        nbv = new(N, "ShaderNodeCombineXYZ", (X - 50, 1350)); L.new(nbs, nbv.inputs[0]); L.new(nbs, nbv.inputs[1])
        L.new(nbv.outputs[0], nb_.inputs["Size"]); L.new(nrm_in, nb_.inputs["Image"])
        nrm_in = nb_.outputs[0]

    def shifted_dot(dx, dy, loc):
        tr = new(N, "CompositorNodeTranslate", loc)
        tr.inputs["X"].default_value = dx; tr.inputs["Y"].default_value = dy
        for nm in ("Extension X", "Extension Y"):
            if nm in tr.inputs:
                menu(tr.inputs[nm], "Extend", "EXTEND", "Clip")
        if nrm_in:
            L.new(nrm_in, tr.inputs["Image"])
        a_ = vmath(N, (loc[0] + 150, loc[1] + 60), "MULTIPLY_ADD")
        a_.inputs[1].default_value = (2.0, 2.0, 2.0); a_.inputs[2].default_value = (-1.0, -1.0, -1.0)
        if nrm_in:
            L.new(nrm_in, a_.inputs[0])
        b_ = vmath(N, (loc[0] + 150, loc[1] - 60), "MULTIPLY_ADD")
        b_.inputs[1].default_value = (2.0, 2.0, 2.0); b_.inputs[2].default_value = (-1.0, -1.0, -1.0)
        L.new(tr.outputs[0], b_.inputs[0])
        dt = vmath(N, (loc[0] + 300, loc[1]), "DOT_PRODUCT"); L.new(a_.outputs[0], dt.inputs[0]); L.new(b_.outputs[0], dt.inputs[1])
        cr = math(N, (loc[0] + 450, loc[1]), "SUBTRACT", a=1.0); L.new(dt.outputs["Value"], cr.inputs[1])
        return cr.outputs[0]
    cx = shifted_dot(1.0, 0.0, (X + 150, 1000))
    cy = shifted_dot(0.0, 1.0, (X + 150, 800))
    fnl = math(N, (X + 650, 900), "MAXIMUM", label="Crease"); L.new(cx, fnl.inputs[0]); L.new(cy, fnl.inputs[1])
    nthr = _value(N, (X + 480, 1100), "Normal Threshold", 0.75)
    # threshold is in Sobel-like units (UI compatible): 1 - cos for ~ the same crease angle
    nth_a = math(N, (X + 630, 1150), "MULTIPLY", b=0.12); L.new(nthr, nth_a.inputs[0])
    nthr2 = math(N, (X + 630, 1050), "MULTIPLY", b=0.2); L.new(nthr, nthr2.inputs[0])
    en = new(N, "ShaderNodeMapRange", (X + 800, 900), "Normal Edge Ramp")
    en.clamp = True
    L.new(fnl.outputs[0], en.inputs["Value"]); L.new(nth_a.outputs[0], en.inputs["From Min"]); L.new(nthr2.outputs[0], en.inputs["From Max"])
    fz = new(N, "CompositorNodeFilter", (X + 750, 650), "Depth Edges")
    menu(fz.inputs["Type"], "Sobel", "SOBEL")
    if z_in:
        L.new(z_in, fz.inputs["Image"])
    fzs = new(N, "CompositorNodeSeparateColor", (X + 900, 650)); L.new(fz.outputs[0], fzs.inputs[0])
    zthr = _value(N, (X + 900, 450), "Depth Threshold", 0.05)
    zthr2 = math(N, (X + 1050, 450), "MULTIPLY", b=2.5); L.new(zthr, zthr2.inputs[0])
    ez = new(N, "ShaderNodeMapRange", (X + 1050, 650), "Depth Edge Ramp")
    ez.clamp = True
    L.new(fzs.outputs[0], ez.inputs["Value"]); L.new(zthr, ez.inputs["From Min"]); L.new(zthr2.outputs[0], ez.inputs["From Max"])
    cw = scaled("Contour Width", (X + 1300, 1050), 1.0)
    cw2 = math(N, (X + 1450, 1050), "MULTIPLY", b=2.0); L.new(cw, cw2.inputs[0])
    emk_n = math(N, (X + 1350, 900), "MULTIPLY"); L.new(en.outputs["Result"], emk_n.inputs[0]); L.new(keep_e2.outputs[0], emk_n.inputs[1])
    emk_z = math(N, (X + 1350, 650), "MULTIPLY"); L.new(ez.outputs["Result"], emk_z.inputs[0]); L.new(keep_e2.outputs[0], emk_z.inputs[1])
    _b, ebn = blur(grey_img(emk_n.outputs[0], (X + 1450, 900)), cw, (X + 1600, 900), "Contour Blur")
    _b, ebz = blur(grey_img(emk_z.outputs[0], (X + 1450, 650)), cw2.outputs[0], (X + 1600, 650), "Overlap Blur")
    esn = maprange(N, (X + 1800, 900), 0.05, 0.6, smooth=True, label="Contour Sharpen"); L.new(ebn, esn.inputs["Value"])
    esz = maprange(N, (X + 1800, 650), 0.05, 0.5, smooth=True, label="Overlap Sharpen"); L.new(ebz, esz.inputs["Value"])
    esh = math(N, (X + 1950, 800), "MAXIMUM"); L.new(esn.outputs["Result"], esh.inputs[0]); L.new(esz.outputs["Result"], esh.inputs[1])
    # hand wobble (displace) and pen lifts (gaps); the wobble boils with the lines
    st = new(N, "CompositorNodeSceneTime", (X + 1350, 1500))
    bph = math(N, (X + 1500, 1500), "DIVIDE"); L.new(st.outputs["Frame"], bph.inputs[0])
    L.new(_value(N, (X + 1350, 1650), "Boil Rate", 2.0), bph.inputs[1])
    bfl = math(N, (X + 1650, 1500), "FLOOR"); L.new(bph.outputs[0], bfl.inputs[0])
    bon = math(N, (X + 1800, 1500), "MULTIPLY", label="Boil Phase"); L.new(bfl.outputs[0], bon.inputs[0])
    L.new(_value(N, (X + 1650, 1650), "Boil On", 1.0), bon.inputs[1])
    wn = new(N, "ShaderNodeTexNoise", (X + 1950, 1300), "Contour Wobble Noise")
    wn.noise_dimensions = "4D"
    wn.inputs["Scale"].default_value = 1.0
    wn.inputs["Detail"].default_value = 2.0
    wsc = vmath(N, (X + 1800, 1300), "SCALE"); wsc.inputs["Scale"].default_value = 0.012
    L.new(PIX, wsc.inputs[0]); L.new(wsc.outputs[0], wn.inputs["Vector"])
    bw = math(N, (X + 1950, 1500), "MULTIPLY", b=1.37); L.new(bon.outputs[0], bw.inputs[0]); L.new(bw.outputs[0], wn.inputs["W"])
    wsub = vmath(N, (X + 2100, 1300), "SUBTRACT"); wsub.inputs[1].default_value = (0.5, 0.5, 0.5)
    L.new(wn.outputs["Color"], wsub.inputs[0])
    wamp = vmath(N, (X + 2250, 1300), "SCALE"); L.new(wsub.outputs[0], wamp.inputs[0])
    L.new(scaled("Contour Wobble Px", (X + 2000, 1500), 1.5), wamp.inputs["Scale"])
    disp = new(N, "CompositorNodeDisplace", (X + 2100, 800), "Contour Wobble")
    for nm in ("Extension X", "Extension Y"):
        if nm in disp.inputs:
            menu(disp.inputs[nm], "Extend", "EXTEND", "Clip")
    L.new(grey_img(esh.outputs[0], (X + 2000, 950)), disp.inputs["Image"]); L.new(wamp.outputs[0], disp.inputs["Displacement"])
    dsep = new(N, "CompositorNodeSeparateColor", (X + 2250, 800)); L.new(disp.outputs[0], dsep.inputs[0])
    gn = new(N, "ShaderNodeTexNoise", (X + 2100, 1100), "Pen Lift Noise")
    gn.noise_dimensions = "4D"
    gn.inputs["Scale"].default_value = 1.0
    gn.inputs["Detail"].default_value = 1.0
    gsc = vmath(N, (X + 1950, 1100), "SCALE"); gsc.inputs["Scale"].default_value = 0.03
    L.new(PIX, gsc.inputs[0]); L.new(gsc.outputs[0], gn.inputs["Vector"]); L.new(bw.outputs[0], gn.inputs["W"])
    gb = _value(N, (X + 2100, 1300), "Contour Breakup", 0.3)
    gb0 = math(N, (X + 2250, 1150), "MULTIPLY_ADD", b=0.4, c=0.18); L.new(gb, gb0.inputs[0])
    gb1 = math(N, (X + 2400, 1150), "ADD", b=0.1); L.new(gb0.outputs[0], gb1.inputs[0])
    gm = new(N, "ShaderNodeMapRange", (X + 2400, 1050), "Pen Lift")
    gm.clamp = True; gm.interpolation_type = "SMOOTHSTEP"
    L.new(gn.outputs[0], gm.inputs["Value"]); L.new(gb0.outputs[0], gm.inputs["From Min"]); L.new(gb1.outputs[0], gm.inputs["From Max"])
    eg = math(N, (X + 2550, 900), "MULTIPLY"); L.new(dsep.outputs[0], eg.inputs[0]); L.new(gm.outputs["Result"], eg.inputs[1])
    estr = math(N, (X + 2700, 900), "MULTIPLY", label="Contour Amount", clamp=True); L.new(eg.outputs[0], estr.inputs[0])
    E = estr.outputs[0]

    # inside solid black a dark line is invisible: inkers scratch a white line instead
    ko_g = maprange(N, (X + 2850, 450), 0.82, 0.97, smooth=True, label="Knockout Gate"); L.new(S0, ko_g.inputs["Value"])
    ko_w = math(N, (X + 3000, 450), "MULTIPLY", label="White Line Amount"); L.new(ko_g.outputs["Result"], ko_w.inputs[0])
    ko_e = math(N, (X + 3150, 450), "MULTIPLY"); L.new(E, ko_e.inputs[0]); L.new(ko_w.outputs[0], ko_e.inputs[1])
    ko_i = math(N, (X + 3300, 450), "SUBTRACT", a=1.0); L.new(ko_e.outputs[0], ko_i.inputs[1])
    s1 = math(N, (X + 3450, 300), "MULTIPLY", clamp=True, label="White Lines"); L.new(S0, s1.inputs[0]); L.new(ko_i.outputs[0], s1.inputs[1])
    S1 = s1.outputs[0]
    ko_n = math(N, (X + 3150, 600), "SUBTRACT", a=1.0); L.new(ko_w.outputs[0], ko_n.inputs[1])
    e_ink = math(N, (X + 3300, 650), "MULTIPLY"); L.new(E, e_ink.inputs[0]); L.new(ko_n.outputs[0], e_ink.inputs[1])
    lopv = _value(N, (X + 3300, 900), "Line Opacity Value", 1.0)
    _sb, sgrow = blur(grey_img(S1, (X + 3300, 1050)), scaled("Hull Shade Px", (X + 3150, 1200), 3.0), (X + 3450, 1050), "Shade Grow")
    sg2 = math(N, (X + 3600, 1050), "MULTIPLY", b=1.6, clamp=True); L.new(sgrow, sg2.inputs[0])
    hop = math(N, (X + 3750, 950), "MAXIMUM"); L.new(lopv, hop.inputs[0]); L.new(sg2.outputs[0], hop.inputs[1])
    lh = math(N, (X + 3900, 850), "MULTIPLY", label="Hull Ink", clamp=True); L.new(HULL, lh.inputs[0]); L.new(hop.outputs[0], lh.inputs[1])
    lop = math(N, (X + 3600, 700), "MULTIPLY", label="Contour Ink", clamp=True); L.new(e_ink.outputs[0], lop.inputs[0])
    L.new(lopv, lop.inputs[1])
    LH0 = lh.outputs[0]
    LN0 = lop.outputs[0]

    # ------------------------------------------------------------ paper grain (tooth, chalk and the paper itself)
    fib = new(N, "ShaderNodeTexNoise", (X + 2700, -1600), "Paper Fibre")
    fib.inputs["Scale"].default_value = 1.0
    fib.inputs["Detail"].default_value = 6.0
    fib.inputs["Roughness"].default_value = 0.7
    fsc = vmath(N, (X + 2550, -1600), "SCALE"); fsc.inputs["Scale"].default_value = 0.16
    L.new(PIX, fsc.inputs[0]); L.new(fsc.outputs[0], fib.inputs["Vector"])
    trot = new(N, "ShaderNodeVectorRotate", (X + 2400, -1900)); trot.rotation_type = "Z_AXIS"
    trot.inputs["Angle"].default_value = 0.5
    L.new(PIX, trot.inputs["Vector"])
    tst = vmath(N, (X + 2550, -1900), "MULTIPLY"); tst.inputs[1].default_value = (0.35, 0.06, 1.0)
    L.new(trot.outputs[0], tst.inputs[0])
    tnz = new(N, "ShaderNodeTexNoise", (X + 2700, -1900), "Tooth Noise")
    tnz.inputs["Scale"].default_value = 1.0
    tnz.inputs["Detail"].default_value = 3.0
    tnz.inputs["Roughness"].default_value = 0.65
    L.new(tst.outputs[0], tnz.inputs["Vector"])
    tsum = math(N, (X + 2850, -1800), "MULTIPLY_ADD", b=0.5); L.new(tnz.outputs[0], tsum.inputs[0])
    L.new(fib.outputs[0], tsum.inputs[2])
    tsum2 = math(N, (X + 3000, -1800), "MULTIPLY", b=0.667); L.new(tsum.outputs[0], tsum2.inputs[0])
    peaks = maprange(N, (X + 3150, -1800), 0.5, 0.66, smooth=True, label="Tooth Peaks")
    L.new(tsum2.outputs[0], peaks.inputs["Value"])
    PEAK = peaks.outputs["Result"]

    # tooth: grain peaks stay bare, most where the shading is light (light pressure); lines a little
    tlite = math(N, (X + 3600, 0), "SUBTRACT", a=1.25); L.new(S1, tlite.inputs[1])
    tpk = math(N, (X + 3750, -100), "MULTIPLY"); L.new(PEAK, tpk.inputs[0]); L.new(tlite.outputs[0], tpk.inputs[1])
    tam = math(N, (X + 3900, -100), "MULTIPLY", label="Paper Tooth Amount", clamp=True); L.new(tpk.outputs[0], tam.inputs[0])
    tinv = math(N, (X + 4050, -100), "SUBTRACT", a=1.0); L.new(tam.outputs[0], tinv.inputs[1])
    ct = math(N, (X + 4200, 100), "MULTIPLY", clamp=True); L.new(S1, ct.inputs[0]); L.new(tinv.outputs[0], ct.inputs[1])
    S2 = ct.outputs[0]
    ltt = math(N, (X + 4050, 700), "MULTIPLY_ADD", b=0.35, c=0.65); L.new(tinv.outputs[0], ltt.inputs[0])
    ltooth = math(N, (X + 4200, 700), "MULTIPLY", clamp=True); L.new(LN0, ltooth.inputs[0]); L.new(ltt.outputs[0], ltooth.inputs[1])
    htooth = math(N, (X + 4200, 850), "MULTIPLY", clamp=True); L.new(LH0, htooth.inputs[0]); L.new(ltt.outputs[0], htooth.inputs[1])
    LN = ltooth.outputs[0]
    LH = htooth.outputs[0]

    # smudge + wet edges (shading only)
    sb, sbs = blur(grey_img(S2, (X + 4300, 300)), scaled("Smudge Size", (X + 4200, 550), 6.0), (X + 4450, 300), "Smudge Blur")
    wdif = math(N, (X + 4650, 500), "SUBTRACT"); L.new(S2, wdif.inputs[0]); L.new(sbs, wdif.inputs[1])
    wpos = math(N, (X + 4800, 500), "MAXIMUM", b=0.0); L.new(wdif.outputs[0], wpos.inputs[0])
    wamt = math(N, (X + 4950, 500), "MULTIPLY", b=8.0); L.new(wpos.outputs[0], wamt.inputs[0])
    wedge = math(N, (X + 5100, 500), "MULTIPLY", label="Wet Edge Amount"); L.new(wamt.outputs[0], wedge.inputs[0])
    smx = mix(N, (X + 4800, 100), dtype="FLOAT", label="Smudge"); f, a, b, smout = mix_io(smx)
    L.new(S2, a); L.new(sbs, b)
    wadd2 = math(N, (X + 5100, 100), "ADD", clamp=True, label="Wet Edges"); L.new(smout, wadd2.inputs[0])
    L.new(wedge.outputs[0], wadd2.inputs[1])
    S3 = wadd2.outputs[0]

    # ------------------------------------------------------------ unfinished edges (radial or bottom)
    ang = _value(N, (X + 4300, -500), "Fade Angle", 0.5)
    frot = new(N, "ShaderNodeVectorRotate", (X + 4450, -600)); frot.rotation_type = "Z_AXIS"
    L.new(uni, frot.inputs["Vector"]); L.new(ang, frot.inputs["Angle"])
    fst = vmath(N, (X + 4600, -600), "MULTIPLY"); fst.inputs[1].default_value = (2.5, 40.0, 1.0)
    L.new(frot.outputs[0], fst.inputs[0])
    fnz = new(N, "ShaderNodeTexNoise", (X + 4750, -600), "Fade Stroke Noise")
    fnz.inputs["Scale"].default_value = 1.0
    fnz.inputs["Detail"].default_value = 2.0
    L.new(fst.outputs[0], fnz.inputs["Vector"])
    fd = vmath(N, (X + 4450, -800), "MULTIPLY_ADD"); fd.inputs[1].default_value = (2.0, 2.0, 0.0)
    fd.inputs[2].default_value = (-1.0, -1.0, 0.0)
    L.new(nrmc, fd.inputs[0])
    fdl = vmath(N, (X + 4600, -800), "LENGTH"); L.new(fd.outputs[0], fdl.inputs[0])
    nsep = new(N, "ShaderNodeSeparateXYZ", (X + 4450, -950)); L.new(nrmc, nsep.inputs[0])
    fbot = math(N, (X + 4600, -950), "SUBTRACT", a=1.0, label="From Top"); L.new(nsep.outputs[1], fbot.inputs[1])
    fmode = mix(N, (X + 4750, -850), dtype="FLOAT", label="Fade Mode"); f, a, b, FDIST = mix_io(fmode)
    L.new(_value(N, (X + 4600, -1100), "Fade Bottom", 0.0), f); L.new(fdl.outputs["Value"], a); L.new(fbot.outputs[0], b)
    fns = math(N, (X + 4900, -700), "MULTIPLY_ADD", b=0.35, c=-0.175); L.new(fnz.outputs[0], fns.inputs[0])
    fdd = math(N, (X + 5050, -750), "ADD"); L.new(FDIST, fdd.inputs[0]); L.new(fns.outputs[0], fdd.inputs[1])
    fs = _value(N, (X + 4900, -950), "Fade Start", 0.9)
    fe = math(N, (X + 5050, -950), "ADD", b=0.3); L.new(fs, fe.inputs[0])

    def fade_mask(lag, loc, name):
        s0 = math(N, (loc[0], loc[1] - 100), "ADD", b=lag); L.new(fs, s0.inputs[0])
        s1_ = math(N, (loc[0], loc[1] - 200), "ADD", b=lag); L.new(fe.outputs[0], s1_.inputs[0])
        mr = new(N, "ShaderNodeMapRange", loc, name + " Ramp")
        mr.clamp = True; mr.interpolation_type = "SMOOTHSTEP"
        L.new(fdd.outputs[0], mr.inputs["Value"]); L.new(s0.outputs[0], mr.inputs["From Min"]); L.new(s1_.outputs[0], mr.inputs["From Max"])
        am = math(N, (loc[0] + 150, loc[1]), "MULTIPLY", label=name + " Amount"); L.new(mr.outputs["Result"], am.inputs[0])
        kp = math(N, (loc[0] + 300, loc[1]), "SUBTRACT", a=1.0); L.new(am.outputs[0], kp.inputs[1])
        return kp.outputs[0]
    MS = fade_mask(0.0, (X + 5200, -750), "Edge Fade")            # wash and chalk (the shading thins out in the shader)
    ML = fade_mask(0.16, (X + 5200, -1050), "Line Fade")          # lines hold on longer ...
    # ... and break into pieces at full darkness instead of turning grey
    mlg = math(N, (X + 5550, -1050), "SUBTRACT", a=1.0); L.new(ML, mlg.inputs[1])
    mlo = math(N, (X + 5700, -1150), "SUBTRACT", b=0.06); L.new(mlg.outputs[0], mlo.inputs[0])
    mhi = math(N, (X + 5700, -1250), "ADD", b=0.06); L.new(mlg.outputs[0], mhi.inputs[0])
    gn2 = new(N, "ShaderNodeTexNoise", (X + 5550, -1350), "Break Noise 2")
    gn2.inputs["Scale"].default_value = 1.0; gn2.inputs["Detail"].default_value = 1.0
    gsc2 = vmath(N, (X + 5400, -1350), "SCALE"); gsc2.inputs["Scale"].default_value = 0.09
    L.new(PIX, gsc2.inputs[0]); L.new(gsc2.outputs[0], gn2.inputs["Vector"])
    gmx = math(N, (X + 5700, -1350), "MULTIPLY_ADD", b=0.5); L.new(gn2.outputs[0], gmx.inputs[0]); L.new(gn.outputs[0], gmx.inputs[2])
    gmx2 = math(N, (X + 5850, -1350), "MULTIPLY", b=0.667); L.new(gmx.outputs[0], gmx2.inputs[0])
    brk = new(N, "ShaderNodeMapRange", (X + 5850, -1100), "Line Break")
    brk.clamp = True; brk.interpolation_type = "SMOOTHSTEP"
    L.new(gmx2.outputs[0], brk.inputs["Value"]); L.new(mlo.outputs[0], brk.inputs["From Min"]); L.new(mhi.outputs[0], brk.inputs["From Max"])
    brk2 = math(N, (X + 6000, -1100), "MULTIPLY", b=1.6, clamp=True); L.new(brk.outputs["Result"], brk2.inputs[0])
    KL = brk2.outputs[0]
    # thinner pen through the fade zone: erode the outline (blur + rising threshold) as it fades
    _tb, lhb = blur(grey_img(LH, (X + 5300, 1150)), scaled("Fade Thin Px", (X + 5150, 1300), 2.0), (X + 5450, 1150), "Fade Thin Blur")
    tlo = math(N, (X + 5650, 1250), "MULTIPLY_ADD", b=0.5, c=0.3); L.new(mlg.outputs[0], tlo.inputs[0])
    thi = math(N, (X + 5650, 1350), "ADD", b=0.25); L.new(tlo.outputs[0], thi.inputs[0])
    thn = new(N, "ShaderNodeMapRange", (X + 5800, 1150), "Fade Thin")
    thn.clamp = True; thn.interpolation_type = "SMOOTHSTEP"
    L.new(lhb, thn.inputs["Value"]); L.new(tlo.outputs[0], thn.inputs["From Min"]); L.new(thi.outputs[0], thn.inputs["From Max"])
    thm = mix(N, (X + 5950, 1000), dtype="FLOAT", label="Fade Thin Mix"); f_, a_, b_, LHT = mix_io(thm)
    tfl = math(N, (X + 5800, 1000), "MULTIPLY", b=3.0, clamp=True); L.new(mlg.outputs[0], tfl.inputs[0])
    L.new(tfl.outputs[0], f_); L.new(LH, a_); L.new(thn.outputs["Result"], b_)
    lhk = math(N, (X + 6100, 850), "MULTIPLY"); L.new(LHT, lhk.inputs[0]); L.new(KL, lhk.inputs[1])
    lnk = math(N, (X + 5600, 700), "MULTIPLY"); L.new(LN, lnk.inputs[0]); L.new(KL, lnk.inputs[1])
    # shares of the same pixel add (no seam between outline and solid black); contours sit on top
    sadd = math(N, (X + 5750, 400), "ADD", clamp=True); L.new(S3, sadd.inputs[0]); L.new(lhk.outputs[0], sadd.inputs[1])
    i1 = math(N, (X + 5900, 400), "SUBTRACT", a=1.0); L.new(sadd.outputs[0], i1.inputs[1])
    i2 = math(N, (X + 5900, 700), "SUBTRACT", a=1.0); L.new(lnk.outputs[0], i2.inputs[1])
    pp = math(N, (X + 6050, 500), "MULTIPLY"); L.new(i1.outputs[0], pp.inputs[0]); L.new(i2.outputs[0], pp.inputs[1])
    cf = math(N, (X + 6200, 500), "SUBTRACT", a=1.0, clamp=True, label="Final Coverage"); L.new(pp.outputs[0], cf.inputs[1])
    CF = cf.outputs[0]

    # ------------------------------------------------------------ wash colour (premultiplied over white)
    if wash_in:
        wbw = _bw(N, (X + 150, -550)); L.new(wash_in, wbw.inputs[0])
        wmiss = math(N, (X + 300, -550), "LESS_THAN", b=0.0005, label="No Wash AOV"); L.new(wbw.outputs[0], wmiss.inputs[0])
        wma = math(N, (X + 450, -550), "MULTIPLY"); L.new(wmiss.outputs[0], wma.inputs[0]); L.new(alpha, wma.inputs[1])
        ainv0 = math(N, (X + 150, -300), "SUBTRACT", a=1.0); L.new(alpha, ainv0.inputs[1])
        ainv = math(N, (X + 300, -300), "ADD"); L.new(ainv0.outputs[0], ainv.inputs[0]); L.new(wma.outputs[0], ainv.inputs[1])
        wadd = mix(N, (X + 450, -300), "ADD", label="Wash Over White"); f, a, b, wsh = mix_io(wadd)
        f.default_value = 1.0
        L.new(wash_in, a); L.new(grey_img(ainv.outputs[0], (X + 300, -450)), b)
    else:
        wsh = None
    if wsh is not None:
        # watercolour: the colour is laid loosely - a little off register, pulled back from the lines,
        # highlights left white, pigment pooling at the edge of each wash
        dnz = new(N, "ShaderNodeTexNoise", (X + 5300, -1400), "Wash Offset Noise")
        dnz.inputs["Scale"].default_value = 1.0
        dnz.inputs["Detail"].default_value = 1.0
        dns = vmath(N, (X + 5150, -1400), "SCALE"); dns.inputs["Scale"].default_value = 0.004
        L.new(PIX, dns.inputs[0]); L.new(dns.outputs[0], dnz.inputs["Vector"])
        dsb = vmath(N, (X + 5450, -1400), "SUBTRACT"); dsb.inputs[1].default_value = (0.5, 0.5, 0.5)
        L.new(dnz.outputs["Color"], dsb.inputs[0])
        dam = vmath(N, (X + 5600, -1400), "SCALE"); L.new(dsb.outputs[0], dam.inputs[0])
        L.new(scaled("Wash Offset Px", (X + 5450, -1600), 7.0), dam.inputs["Scale"])
        wdisp = new(N, "CompositorNodeDisplace", (X + 5600, -1200), "Wash Offset")
        for nm in ("Extension X", "Extension Y"):
            if nm in wdisp.inputs:
                menu(wdisp.inputs[nm], "Extend", "EXTEND", "Clip")
        L.new(wsh, wdisp.inputs["Image"]); L.new(dam.outputs[0], wdisp.inputs["Displacement"])
        _lb, lgrow = blur(grey_img(LN, (X + 5300, -1800)), scaled("Wash Lift Px", (X + 5150, -2000), 3.5),
                          (X + 5450, -1800), "Line Grow")
        lgm = maprange(N, (X + 5650, -1800), 0.05, 0.35, smooth=True); L.new(lgrow, lgm.inputs["Value"])
        lga = math(N, (X + 5800, -1800), "MULTIPLY", label="Wash Lift Amount"); L.new(lgm.outputs["Result"], lga.inputs[0])
        hiw = math(N, (X + 5800, -1950), "MULTIPLY", b=0.75); L.new(hi_in if hi_in else _value(N, (X + 5650, -2050), "No Hi W", 0.0), hiw.inputs[0])
        lgt = math(N, (X + 5950, -1850), "MAXIMUM"); L.new(lga.outputs[0], lgt.inputs[0]); L.new(hiw.outputs[0], lgt.inputs[1])
        wl = mix(N, (X + 5900, -1200), "MIX", label="Wash Lift"); f, a, b, WL = mix_io(wl)
        L.new(lgt.outputs[0], f); L.new(wdisp.outputs[0], a); b.default_value = (1, 1, 1, 1)
        wbl = new(N, "CompositorNodeBlur", (X + 6050, -1350), "Wash Edge Blur")
        menu(wbl.inputs["Type"], "Gaussian", "GAUSS")
        wes = scaled("Wash Edge Px", (X + 5900, -1500), 8.0)
        wev = new(N, "ShaderNodeCombineXYZ", (X + 6000, -1500)); L.new(wes, wev.inputs[0]); L.new(wes, wev.inputs[1])
        L.new(wev.outputs[0], wbl.inputs["Size"]); L.new(WL, wbl.inputs["Image"])
        wl1 = _bw(N, (X + 6200, -1200)); L.new(WL, wl1.inputs[0])
        wl2 = _bw(N, (X + 6200, -1350)); L.new(wbl.outputs[0], wl2.inputs[0])
        wdd = math(N, (X + 6350, -1250), "SUBTRACT"); L.new(wl2.outputs[0], wdd.inputs[0]); L.new(wl1.outputs[0], wdd.inputs[1])
        wdp = math(N, (X + 6500, -1250), "MAXIMUM", b=0.0); L.new(wdd.outputs[0], wdp.inputs[0])
        wdk = math(N, (X + 6650, -1250), "MULTIPLY", b=2.5, label="Wash Pool"); L.new(wdp.outputs[0], wdk.inputs[0])
        wpl = mix(N, (X + 6350, -1050), "MULTIPLY", label="Wash Pooling"); f, a, b, WP = mix_io(wpl)
        L.new(wdk.outputs[0], f); L.new(WL, a); L.new(WL, b)
        wsrc = WP
    else:
        wsrc = None
    wfade = mix(N, (X + 6500, -300), "MIX", label="Wash Fade"); f, a, b, WASH = mix_io(wfade)
    L.new(MS, f); a.default_value = (1, 1, 1, 1)
    if wsrc is not None:
        L.new(wsrc, b)
    else:
        b.default_value = (1, 1, 1, 1)

    # ------------------------------------------------------------ paper
    blot = new(N, "ShaderNodeTexNoise", (X + 2700, -2200), "Paper Blotch")
    blot.inputs["Scale"].default_value = 2.0
    blot.inputs["Detail"].default_value = 3.0
    L.new(uni, blot.inputs["Vector"])
    pt = math(N, (X + 2900, -2100), "MULTIPLY_ADD", b=0.4); L.new(blot.outputs[0], pt.inputs[0])
    L.new(fib.outputs[0], pt.inputs[2])
    ptc = math(N, (X + 3050, -2100), "SUBTRACT", b=0.7); L.new(pt.outputs[0], ptc.inputs[0])
    pts = math(N, (X + 3200, -2100), "MULTIPLY", label="Paper Texture Amount"); L.new(ptc.outputs[0], pts.inputs[0])
    pt1 = math(N, (X + 3350, -2100), "ADD", a=1.0); L.new(pts.outputs[0], pt1.inputs[1])
    pc_mix = mix(N, (X + 3500, -2100), "MULTIPLY", label="Paper"); f, a, b, PAPER0 = mix_io(pc_mix)
    f.default_value = 1.0
    L.new(grey_img(pt1.outputs[0], (X + 3350, -2250)), b)
    rsp = _value(N, (X + 3350, -2500), "Rule Spacing", 46.0)
    psep = new(N, "ShaderNodeSeparateXYZ", (X + 3350, -2650)); L.new(PIX, psep.inputs[0])
    rdv = math(N, (X + 3500, -2600), "DIVIDE"); L.new(psep.outputs[1], rdv.inputs[0]); L.new(rsp, rdv.inputs[1])
    rfr = math(N, (X + 3650, -2600), "PINGPONG", b=0.5); L.new(rdv.outputs[0], rfr.inputs[0])
    rpx = math(N, (X + 3650, -2750), "DIVIDE", a=1.1); L.new(rsp, rpx.inputs[1])
    rln = new(N, "ShaderNodeMapRange", (X + 3800, -2600), "Rule Line")
    rln.clamp = True
    rln.inputs["To Min"].default_value = 1.0; rln.inputs["To Max"].default_value = 0.0
    L.new(rfr.outputs[0], rln.inputs["Value"]); rln.inputs["From Min"].default_value = 0.0
    L.new(rpx.outputs[0], rln.inputs["From Max"])
    ram = math(N, (X + 3950, -2600), "MULTIPLY", label="Rule Amount"); L.new(rln.outputs["Result"], ram.inputs[0])
    rmx = mix(N, (X + 3700, -2100), "MIX", label="Rules"); f, a, b, PAPER = mix_io(rmx)
    L.new(ram.outputs[0], f); L.new(PAPER0, a)

    pw = mix(N, (X + 6650, -300), "MULTIPLY", label="Paper x Wash"); f, a, b, PW = mix_io(pw)
    f.default_value = 1.0
    L.new(PAPER, a); L.new(WASH, b)

    # ------------------------------------------------------------ ink onto paper
    ink = mix(N, (X + 6850, 0), "MIX", label="Ink"); f, a, b, INK = mix_io(ink)
    L.new(CF, f); L.new(PW, a)

    # white chalk on the lit side (toned paper): grainy, catching the paper's peaks
    # chalk in long directional strokes along the hatch angle (never per-pixel salt)
    crt = new(N, "ShaderNodeVectorRotate", (X + 6050, -1300)); crt.rotation_type = "Z_AXIS"
    L.new(PIX, crt.inputs["Vector"]); L.new(_value(N, (X + 5900, -1400), "Chalk Angle", 0.6), crt.inputs["Angle"])
    cst = vmath(N, (X + 6200, -1300), "MULTIPLY"); cst.inputs[1].default_value = (0.012, 0.11, 1.0)
    L.new(crt.outputs[0], cst.inputs[0])
    cnz = new(N, "ShaderNodeTexNoise", (X + 6350, -1300), "Chalk Stroke Noise")
    cnz.inputs["Scale"].default_value = 1.0; cnz.inputs["Detail"].default_value = 2.0
    L.new(cst.outputs[0], cnz.inputs["Vector"])
    cmx = math(N, (X + 6450, -1200), "MULTIPLY_ADD", b=0.75); L.new(cnz.outputs[0], cmx.inputs[0])
    L.new(tnz.outputs[0], cmx.inputs[2])
    cmx2 = math(N, (X + 6550, -1200), "MULTIPLY", b=1.2); L.new(cmx.outputs[0], cmx2.inputs[0])
    hc0 = maprange(N, (X + 6650, -1150), 0.56, 0.74, smooth=True, label="Chalk Strokes"); L.new(cmx2.outputs[0], hc0.inputs["Value"])
    hc = math(N, (X + 6650, -1100), "MULTIPLY_ADD", b=0.7, c=0.3); L.new(hc0.outputs["Result"], hc.inputs[0])
    hm = math(N, (X + 6800, -1000), "MULTIPLY"); L.new(hi_in if hi_in else _value(N, (X + 6650, -900), "No Hi", 0.0), hm.inputs[0])
    L.new(hc.outputs[0], hm.inputs[1])
    hcv = math(N, (X + 6950, -1000), "MULTIPLY_ADD", b=-0.3, c=1.0); L.new(CF, hcv.inputs[0])   # chalk sits on graphite
    hm2 = math(N, (X + 7100, -1000), "MULTIPLY"); L.new(hm.outputs[0], hm2.inputs[0]); L.new(hcv.outputs[0], hm2.inputs[1])
    hm3 = math(N, (X + 7250, -1000), "MULTIPLY"); L.new(hm2.outputs[0], hm3.inputs[0]); L.new(MS, hm3.inputs[1])
    ham = math(N, (X + 7400, -1000), "MULTIPLY", label="Chalk Amount", clamp=True); L.new(hm3.outputs[0], ham.inputs[0])
    chalk = mix(N, (X + 7050, 0), "MIX", label="Chalk"); f, a, b, CH = mix_io(chalk)
    L.new(ham.outputs[0], f); L.new(INK, a)

    # paper grain + soft vignette
    wn2 = new(N, "ShaderNodeTexWhiteNoise", (X + 7050, -1400), "Grain Noise")
    wn2.noise_dimensions = "2D"
    L.new(pix, wn2.inputs["Vector"])
    grain = mix(N, (X + 7250, 0), "OVERLAY", label="Grain"); f, a, b, GR = mix_io(grain)
    L.new(CH, a); L.new(wn2.outputs["Value"], b)
    vl_ = vmath(N, (X + 7250, -400), "LENGTH"); L.new(uni, vl_.inputs[0])
    vr = maprange(N, (X + 7400, -400), 0.5, 1.25, smooth=True, label="Vignette Falloff")
    L.new(vl_.outputs["Value"], vr.inputs["Value"])
    vf = math(N, (X + 7550, -400), "MULTIPLY", label="Vignette Amount"); L.new(vr.outputs["Result"], vf.inputs[0])
    vig = mix(N, (X + 7450, 0), "MULTIPLY", label="Vignette"); f, a, b, VG = mix_io(vig)
    L.new(vf.outputs[0], f); L.new(GR, a)
    b.default_value = (0.55, 0.52, 0.5, 1.0)
    go = new(N, "NodeGroupOutput", (X + 7750, 0))
    L.new(VG, go.inputs["Image"])


def apply_post_settings(scene):
    s = scene.senga
    ng = scene_post(scene)
    if not _is_post(ng):
        return
    n = ng.nodes

    def setin(node, name, val, kind=None):
        nd = n.get(node)
        if nd is None:
            return
        try:
            (sock(nd.inputs, name, kind) if kind else nd.inputs[name]).default_value = val
        except (KeyError, TypeError, ValueError, IndexError):
            pass

    def setval(node, val):
        nd = n.get(node)
        if nd is not None:
            nd.outputs[0].default_value = val

    col = lambda c: tuple(c)[:3] + (1.0,)
    setval("Line Opacity Value", s.line_opacity)
    setval("Boil Rate", float(s.boil_rate))
    setval("Boil On", 1.0 if s.outline_boil else 0.0)
    setval("Fade Bottom", 1.0 if s.fade_mode == "BOTTOM" else 0.0)
    setin("Line Fade Amount", 1, s.edge_fade)
    setin("Wash Lift Amount", 1, 0.9 if s.wash_amount > 0 else 0.0)
    setin("Wash Pooling", "Factor", 1.0 if s.wash_amount > 0 else 0.0, "VALUE")
    for nm in ("Wash Offset", "Wash Edge Blur", "Line Grow"):
        if n.get(nm):
            n[nm].mute = s.wash_amount <= 0.0
    setval("Normal Threshold", s.contour_normal)
    setval("Depth Threshold", s.contour_depth)
    setval("Contour Width", s.contour_width)
    setval("Contour Wobble Px", s.contour_wobble)
    setval("Contour Breakup", s.contour_breakup)
    setin("Contour Amount", 1, s.contour_strength if s.contour_enable else 0.0)
    setin("Paper Tooth Amount", 1, s.paper_tooth)
    setin("White Line Amount", 1, s.white_lines if s.contour_enable else 0.0)
    setval("Smudge Size", s.smudge_size)
    setin("Smudge", "Factor", s.smudge, "VALUE")
    setin("Wet Edge Amount", 1, s.wet_edges)
    if n.get("Fade Thin Blur"):
        n["Fade Thin Blur"].mute = s.edge_fade <= 0.0
    if n.get("Smudge Blur"):
        n["Smudge Blur"].mute = s.smudge <= 0.0 and s.wet_edges <= 0.0
    if n.get("Contour Blur"):
        n["Contour Blur"].mute = False
    setval("Fade Angle", s.hatch_angle)
    setval("Chalk Angle", -s.hatch_angle)
    setval("Fade Start", s.edge_fade_start)
    setin("Edge Fade Amount", 1, s.edge_fade)
    setin("Paper Texture Amount", 1, s.paper_texture)
    setin("Paper", "A", col(s.paper_color), "RGBA")
    setval("Rule Spacing", s.rule_spacing)
    setin("Rule Amount", 1, s.rule_lines)
    setin("Rules", "B", col(s.rule_color), "RGBA")
    setin("Ink", "B", col(s.ink_color), "RGBA")
    setin("Chalk", "B", col(s.chalk_color), "RGBA")
    setin("Chalk Amount", 1, s.chalk)
    setin("Grain", "Factor", s.grain, "VALUE")
    setin("Vignette Amount", 1, s.vignette)


def remove_post(scene):
    prev = scene.get(TAG + "_prev_comp")
    scene.compositing_node_group = bpy.data.node_groups.get(prev) if prev else None
    if TAG + "_prev_comp" in scene:
        del scene[TAG + "_prev_comp"]
