# SPDX-License-Identifier: GPL-3.0-or-later
"""Senga Sketch material: graphite tone from light x albedo, hand-inked hatching
(screen-space or following the form), screentone / stipple, solid blacks, colour wash.

Every look setting is read inside the shader from the scene (VIEW_LAYER attribute
"senga.<prop>") with a baked fallback, or from the per-object override
(OBJECT attribute "senga_obj.<prop>"), so shared materials stay correct and files
render the same without the add-on installed.
"""
import bpy
from .util import (TAG, SHADE_GROUP, OUTLINE_MAT, AOV_COVER, AOV_WASH, AOV_HI, AOV_NORMAL, AOV_DEPTH,
                   sock, new, iface, mix, mix_io, math, vmath, maprange)

VER = 12
MAT_VER = 3

SHADE_INPUTS = [
    ("Base Color", "NodeSocketColor", (0.8, 0.8, 0.8, 1.0), None, None),
    ("Alpha", "NodeSocketFloat", 1.0, 0.0, 1.0),
    ("Emission", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None, None),
    ("Normal", "NodeSocketVector", (0.0, 0.0, 1.0), None, None),
    ("Use Normal", "NodeSocketFloat", 0.0, 0.0, 1.0),
    ("Roughness", "NodeSocketFloat", 0.5, 0.0, 1.0),
]

# group-internal name -> (scene prop, object-override prop or None, output kind)
SETTINGS = {
    "Light Scale": ("light_scale", None, "Fac"),
    "Ambient": ("ambient_level", None, "Fac"),
    "Threshold": ("threshold", "threshold", "Fac"),
    "Softness": ("softness", None, "Fac"),
    "Cel": ("cel_amount", None, "Fac"),
    "Shadow Floor": ("shadow_floor", "shadow_floor", "Fac"),
    "Brightness": ("brightness", "brightness", "Fac"),
    "Albedo Influence": ("albedo_influence", "albedo_influence", "Fac"),
    "Albedo Black": ("albedo_black", None, "Fac"),
    "Albedo White": ("albedo_white", None, "Fac"),
    "Fill": ("fill_strength", "fill_strength", "Fac"),
    "Fill Start": ("fill_start", None, "Fac"),
    "Fill Texture": ("fill_texture", None, "Fac"),
    "Solid": ("solid_amount", "solid_amount", "Fac"),
    "Solid Start": ("solid_start", None, "Fac"),
    "Dry Brush": ("dry_brush", None, "Fac"),
    "Hatch": ("hatch_amount", "hatch_amount", "Fac"),
    "Hatch Start": ("hatch_start", None, "Fac"),
    "Cross Start": ("cross_start", None, "Fac"),
    "Deep Start": ("deep_start", None, "Fac"),
    "Hatch Spacing": ("hatch_spacing", None, "Fac"),
    "Hatch Width": ("hatch_width", None, "Fac"),
    "Hatch Angle": ("hatch_angle", None, "Fac"),
    "Cross Angle": ("cross_angle", None, "Fac"),
    "Wobble": ("hatch_wobble", None, "Fac"),
    "Wobble Scale": ("wobble_scale", None, "Fac"),
    "Breakup": ("hatch_breakup", None, "Fac"),
    "Form": ("hatch_form", None, "Fac"),
    "Pattern": ("pattern_id", None, "Fac"),
    "Seed": ("seed", None, "Fac"),
    "Phase": ("hatch_phase", None, "Fac"),
    "Wash": ("wash_amount", "wash_amount", "Fac"),
    "Wash Saturation": ("wash_saturation", None, "Fac"),
    "Ink Color": ("ink_color", None, "Color"),
    "Highlight": ("highlight_threshold", None, "Fac"),
    "Tone Invert": ("tone_invert", None, "Fac"),
    "Albedo Floor": ("albedo_floor", None, "Fac"),
    "Gloss": ("gloss", "gloss", "Fac"),
    "Tone Steps": ("tone_steps", None, "Fac"),
    "Paper Marks": ("paper_marks", None, "Fac"),
    "Depth Ref": ("outline_ref_distance", None, "Fac"),
    "Fade Amount": ("edge_fade", None, "Fac"),
    "Fade Start": ("edge_fade_start", None, "Fac"),
    "Fade Bottom": ("fade_bottom", None, "Fac"),
}


class _Settings:
    """Lazily creates attribute readers (+ baked fallbacks) inside the group."""

    def __init__(self, N, L, x=-3600):
        self.N, self.L, self.cache, self.y, self.x = N, L, {}, 2400, x
        self.ov = self.alive = None

    def _attr(self, kind, path):
        n = new(self.N, "ShaderNodeAttribute", (self.x, self.y))
        self.y -= 160
        n.attribute_type = kind
        n.attribute_name = path
        return n

    def override_fac(self):
        if self.ov is None:
            self.ov = self._attr("OBJECT", "senga_obj.use_override").outputs["Factor"]
        return self.ov

    def alive_fac(self):
        if self.alive is None:
            self.alive = self._attr("VIEW_LAYER", "senga.alive").outputs["Factor"]
        return self.alive

    def _fallback(self, scene_prop, dtype):
        idn = "ShaderNodeRGB" if dtype == "RGBA" else "ShaderNodeValue"
        n = new(self.N, idn, (self.x - 220, self.y + 160), "Senga Fallback " + scene_prop)
        n["senga_prop"] = scene_prop
        return n.outputs[0]

    def __call__(self, name):
        if name in self.cache:
            return self.cache[name]
        scene_prop, obj_prop, kind = SETTINGS[name]
        out = "Color" if kind == "Color" else "Factor"
        dtype = "RGBA" if kind == "Color" else "FLOAT"
        g = None
        if scene_prop:
            live = self._attr("VIEW_LAYER", "senga." + scene_prop).outputs[out]
            fb = self._fallback(scene_prop, dtype)
            am = mix(self.N, (self.x + 120, self.y + 160), dtype=dtype)
            f, a, b, g = mix_io(am)
            self.L.new(self.alive_fac(), f)
            self.L.new(fb, a)
            self.L.new(live, b)
        if obj_prop:
            o = self._attr("OBJECT", "senga_obj." + obj_prop).outputs[out]
            m = mix(self.N, (self.x + 200, self.y + 160), dtype=dtype)
            f, a, b, r = mix_io(m)
            self.L.new(self.override_fac(), f)
            self.L.new(g, a)
            self.L.new(o, b)
            g = r
        self.cache[name] = g
        return g

    def render(self, path, default):
        """Built-in scene RNA (render resolution): readable with or without the add-on."""
        key = "render:" + path
        if key not in self.cache:
            a = self._attr("VIEW_LAYER", path).outputs["Factor"]
            # attribute missing -> 0: fall back to a sane default instead of dividing by zero
            ok = math(self.N, (self.x + 120, self.y + 160), "GREATER_THAN", b=0.5)
            self.L.new(a, ok.inputs[0])
            m = mix(self.N, (self.x + 260, self.y + 160), dtype="FLOAT")
            f, a_, b_, r = mix_io(m)
            self.L.new(ok.outputs[0], f)
            a_.default_value = default
            self.L.new(a, b_)
            self.cache[key] = r
        return self.cache[key]


def _light_term(N, L, normal_out, light_scale, ambient, x, y):
    """Diffuse -> Shader to RGB -> (irradiance*pi - ambient) / light scale (brightest channel)."""
    diff = new(N, "ShaderNodeBsdfDiffuse", (x, y), "Light Diffuse")
    diff.inputs["Color"].default_value = (1, 1, 1, 1)
    L.new(normal_out, diff.inputs["Normal"])
    s2r = new(N, "ShaderNodeShaderToRGB", (x + 180, y), "Light ShaderToRGB")
    L.new(diff.outputs[0], s2r.inputs[0])
    sp = new(N, "ShaderNodeSeparateColor", (x + 340, y + 60))
    L.new(s2r.outputs["Color"], sp.inputs[0])
    m1 = math(N, (x + 480, y + 100), "MAXIMUM"); L.new(sp.outputs[0], m1.inputs[0]); L.new(sp.outputs[1], m1.inputs[1])
    m2 = math(N, (x + 480, y + 20), "MAXIMUM"); L.new(m1.outputs[0], m2.inputs[0]); L.new(sp.outputs[2], m2.inputs[1])
    pi = math(N, (x + 620, y + 60), "MULTIPLY", b=3.14159265); L.new(m2.outputs[0], pi.inputs[0])
    sub = math(N, (x + 760, y + 60), "SUBTRACT", label="Minus Ambient")
    L.new(pi.outputs[0], sub.inputs[0]); L.new(ambient, sub.inputs[1])
    div = math(N, (x + 900, y + 60), "DIVIDE", label="Light / Scale")
    L.new(sub.outputs[0], div.inputs[0]); L.new(light_scale, div.inputs[1])
    return div.outputs[0]


def build_shade_group(rebuild=False):
    ng = bpy.data.node_groups.get(SHADE_GROUP)
    if ng and not rebuild and ng.get(TAG + "_ver") == VER:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(SHADE_GROUP, "ShaderNodeTree")
    ng.nodes.clear()
    ng.interface.clear()
    for name, st, d, lo, hi in SHADE_INPUTS:
        iface(ng, name, "INPUT", st, d, lo, hi)
    iface(ng, "Shader", "OUTPUT", "NodeSocketShader")
    iface(ng, "Ink", "OUTPUT", "NodeSocketFloat")
    iface(ng, "Wash", "OUTPUT", "NodeSocketColor")
    iface(ng, "Highlight", "OUTPUT", "NodeSocketFloat")
    iface(ng, "View Normal", "OUTPUT", "NodeSocketColor")
    iface(ng, "Depth", "OUTPUT", "NodeSocketColor")
    iface(ng, "Tone", "OUTPUT", "NodeSocketFloat")
    ng[TAG + "_ver"] = VER

    N, L = ng.nodes, ng.links
    gi = new(N, "NodeGroupInput", (-3000, 0))
    go = new(N, "NodeGroupOutput", (3600, 0))
    S = _Settings(N, L)
    I = lambda n: gi.outputs[n] if n in gi.outputs else S(n)

    # ---------------------------------------------------------------- normal
    geo = new(N, "ShaderNodeNewGeometry", (-2800, 600))
    bn = mix(N, (-2600, 600), dtype="VECTOR", label="Base Normal")
    bn.factor_mode = "UNIFORM"
    f, a, b, r = mix_io(bn)
    L.new(I("Use Normal"), f); L.new(geo.outputs["Normal"], a); L.new(I("Normal"), b)
    bnn = vmath(N, (-2450, 600), "NORMALIZE"); L.new(r, bnn.inputs[0])
    base_n = bnn.outputs[0]

    # view-space normal for the compositor crease pass (geometric: normal maps would add noise lines)
    vt = new(N, "ShaderNodeVectorTransform", (-2600, 900), "View Normal")
    vt.vector_type = "NORMAL"; vt.convert_from = "WORLD"; vt.convert_to = "CAMERA"
    L.new(geo.outputs["Normal"], vt.inputs[0])
    vn = vmath(N, (-2450, 900), "MULTIPLY_ADD")
    vn.inputs[1].default_value = (0.5, 0.5, 0.5); vn.inputs[2].default_value = (0.5, 0.5, 0.5)
    L.new(vt.outputs[0], vn.inputs[0])
    L.new(vn.outputs[0], go.inputs["View Normal"])
    VNS = new(N, "ShaderNodeSeparateXYZ", (-2300, 1000)); L.new(vt.outputs[0], VNS.inputs[0])

    # anti-aliased depth for the compositor: d / (d + ref), background stays 0
    tc = new(N, "ShaderNodeTexCoord", (-2800, -900))
    cdl = vmath(N, (-2600, 1150), "LENGTH"); L.new(tc.outputs["Camera"], cdl.inputs[0])
    cdr = math(N, (-2450, 1150), "ADD"); L.new(cdl.outputs["Value"], cdr.inputs[0]); L.new(I("Depth Ref"), cdr.inputs[1])
    cdn = math(N, (-2300, 1150), "DIVIDE"); L.new(cdl.outputs["Value"], cdn.inputs[0]); L.new(cdr.outputs[0], cdn.inputs[1])
    cdc = new(N, "ShaderNodeCombineColor", (-2150, 1150))
    for i in range(3):
        L.new(cdn.outputs[0], cdc.inputs[i])
    L.new(cdc.outputs[0], go.inputs["Depth"])

    # ---------------------------------------------------------------- light
    light = _light_term(N, L, base_n, I("Light Scale"), I("Ambient"), -2300, 400)
    grad = math(N, (-1300, 520), "MAXIMUM", b=0.0, label="Lambert")
    L.new(light, grad.inputs[0])
    gradc = math(N, (-1150, 520), "MINIMUM", b=1.0); L.new(grad.outputs[0], gradc.inputs[0])
    lo = math(N, (-1300, 300), "SUBTRACT"); L.new(I("Threshold"), lo.inputs[0]); L.new(I("Softness"), lo.inputs[1])
    hi = math(N, (-1300, 180), "ADD"); L.new(I("Threshold"), hi.inputs[0]); L.new(I("Softness"), hi.inputs[1])
    cel = new(N, "ShaderNodeMapRange", (-1150, 300), "Cel Ramp")
    cel.clamp = True; cel.interpolation_type = "SMOOTHSTEP"
    L.new(light, cel.inputs["Value"]); L.new(lo.outputs[0], cel.inputs["From Min"]); L.new(hi.outputs[0], cel.inputs["From Max"])
    shmix = mix(N, (-950, 400), dtype="FLOAT", label="Gradient Or Cel")
    f, a, b, shade01 = mix_io(shmix)
    L.new(I("Cel"), f); L.new(gradc.outputs[0], a); L.new(cel.outputs["Result"], b)
    sfl = new(N, "ShaderNodeMapRange", (-780, 400), "Shade Value")
    sfl.clamp = True
    L.new(shade01, sfl.inputs["Value"]); L.new(I("Shadow Floor"), sfl.inputs["To Min"])
    shade = sfl.outputs["Result"]

    # ---------------------------------------------------------------- albedo value
    lum = new(N, "ShaderNodeRGBToBW", (-1300, -100), "Albedo Luminance")
    L.new(I("Base Color"), lum.inputs[0])
    lg = math(N, (-1150, -100), "POWER", b=0.4545); L.new(lum.outputs[0], lg.inputs[0])
    amr = new(N, "ShaderNodeMapRange", (-1000, -100), "Albedo Levels")
    amr.clamp = True; amr.interpolation_type = "SMOOTHSTEP"
    L.new(lg.outputs[0], amr.inputs["Value"])
    L.new(I("Albedo Black"), amr.inputs["From Min"]); L.new(I("Albedo White"), amr.inputs["From Max"])
    afl = new(N, "ShaderNodeMapRange", (-900, -250), "Albedo Floor")
    afl.clamp = True
    flg = maprange(N, (-1150, -350), 0.6, 0.9, smooth=True, label="Lift Only In Light"); L.new(shade01, flg.inputs["Value"])
    flm = math(N, (-1000, -350), "MULTIPLY"); L.new(I("Albedo Floor"), flm.inputs[0]); L.new(flg.outputs["Result"], flm.inputs[1])
    L.new(amr.outputs["Result"], afl.inputs["Value"]); L.new(flm.outputs[0], afl.inputs["To Min"])
    ainf = mix(N, (-820, -100), dtype="FLOAT", label="Albedo Influence")
    f, a, b, alb = mix_io(ainf)
    L.new(I("Albedo Influence"), f); a.default_value = 1.0; L.new(afl.outputs["Result"], b)

    val = math(N, (-600, 200), "MULTIPLY", label="Value"); L.new(shade, val.inputs[0]); L.new(alb, val.inputs[1])
    valb = math(N, (-450, 200), "MULTIPLY", label="Brightness", clamp=True)
    L.new(val.outputs[0], valb.inputs[0]); L.new(I("Brightness"), valb.inputs[1])
    V = valb.outputs[0]
    gl = new(N, "ShaderNodeBsdfGlossy", (-2300, 0), "Gloss BSDF")
    gl.inputs["Color"].default_value = (1, 1, 1, 1)
    gl.inputs["Roughness"].default_value = 0.15
    L.new(base_n, gl.inputs["Normal"])
    gs2r = new(N, "ShaderNodeShaderToRGB", (-2100, 0), "Gloss ShaderToRGB"); L.new(gl.outputs[0], gs2r.inputs[0])
    glum = new(N, "ShaderNodeRGBToBW", (-1950, 0)); L.new(gs2r.outputs["Color"], glum.inputs[0])
    gdv = math(N, (-1800, 0), "DIVIDE"); L.new(glum.outputs[0], gdv.inputs[0]); L.new(I("Light Scale"), gdv.inputs[1])
    gmr = maprange(N, (-1650, 0), 0.75, 0.95, smooth=True, label="Gloss Ramp"); L.new(gdv.outputs[0], gmr.inputs["Value"])
    grf = maprange(N, (-1650, -150), 0.2, 0.65, 1.0, 0.0, smooth=True, label="Gloss From Roughness")
    L.new(gi.outputs["Roughness"], grf.inputs["Value"])
    gm2 = math(N, (-1500, -100), "MULTIPLY"); L.new(gmr.outputs["Result"], gm2.inputs[0]); L.new(grf.outputs["Result"], gm2.inputs[1])
    gam = math(N, (-1350, 0), "MULTIPLY", label="Gloss Amount"); L.new(gm2.outputs[0], gam.inputs[0])
    L.new(I("Gloss"), gam.inputs[1])
    GLOSS_KO = gam.outputs[0]           # white highlight scratched out of the finished ink (see Coverage)
    tone = math(N, (-300, 200), "SUBTRACT", a=1.0, label="Tone"); L.new(V, tone.inputs[1])
    # dark paper (chalk, blueprint): marks describe the light, strongest at the lit edges
    lwf = new(N, "ShaderNodeLayerWeight", (-600, 650), "Edge Facing")
    lwf.inputs["Blend"].default_value = 0.5
    L.new(base_n, lwf.inputs["Normal"])
    edg = math(N, (-450, 650), "MULTIPLY_ADD", b=0.7, c=0.3); L.new(lwf.outputs["Facing"], edg.inputs[0])
    vedge = math(N, (-300, 650), "MULTIPLY"); L.new(V, vedge.inputs[0]); L.new(edg.outputs[0], vedge.inputs[1])
    tinv = mix(N, (-150, 200), dtype="FLOAT", label="Tone Invert"); f, a, b, T0 = mix_io(tinv)
    L.new(I("Tone Invert"), f); L.new(tone.outputs[0], a); L.new(vedge.outputs[0], b)
    # unfinished edges: the drawing thins out (solid black -> hatching -> sparse -> paper), never greys out
    fw = new(N, "ShaderNodeSeparateXYZ", (-700, 1400)); L.new(tc.outputs["Window"], fw.inputs[0])
    fex = math(N, (-550, 1450), "MULTIPLY_ADD", b=2.0, c=-1.0); L.new(fw.outputs[0], fex.inputs[0])
    fey = math(N, (-550, 1350), "MULTIPLY_ADD", b=2.0, c=-1.0); L.new(fw.outputs[1], fey.inputs[0])
    fev = new(N, "ShaderNodeCombineXYZ", (-400, 1400)); L.new(fex.outputs[0], fev.inputs[0]); L.new(fey.outputs[0], fev.inputs[1])
    fel = vmath(N, (-250, 1400), "LENGTH"); L.new(fev.outputs[0], fel.inputs[0])
    fbt = math(N, (-400, 1250), "SUBTRACT", a=1.0); L.new(fw.outputs[1], fbt.inputs[1])
    fmd = mix(N, (-100, 1350), dtype="FLOAT", label="Fade Shape"); f, a, b, FD = mix_io(fmd)
    L.new(I("Fade Bottom"), f); L.new(fel.outputs["Value"], a); L.new(fbt.outputs[0], b)
    fsn, fcs = math(N, (-700, 1600), "SINE"), math(N, (-700, 1700), "COSINE")
    L.new(I("Hatch Angle"), fsn.inputs[0]); L.new(I("Hatch Angle"), fcs.inputs[0])
    fu1 = math(N, (-550, 1650), "MULTIPLY"); L.new(fw.outputs[0], fu1.inputs[0]); L.new(fcs.outputs[0], fu1.inputs[1])
    fu2 = math(N, (-550, 1550), "MULTIPLY"); L.new(fw.outputs[1], fu2.inputs[0]); L.new(fsn.outputs[0], fu2.inputs[1])
    fuu = math(N, (-400, 1600), "ADD"); L.new(fu1.outputs[0], fuu.inputs[0]); L.new(fu2.outputs[0], fuu.inputs[1])
    fv1 = math(N, (-550, 1800), "MULTIPLY"); L.new(fw.outputs[1], fv1.inputs[0]); L.new(fcs.outputs[0], fv1.inputs[1])
    fv2 = math(N, (-550, 1900), "MULTIPLY"); L.new(fw.outputs[0], fv2.inputs[0]); L.new(fsn.outputs[0], fv2.inputs[1])
    fvv = math(N, (-400, 1850), "SUBTRACT"); L.new(fv1.outputs[0], fvv.inputs[0]); L.new(fv2.outputs[0], fvv.inputs[1])
    fnv = new(N, "ShaderNodeCombineXYZ", (-250, 1700))
    fus = math(N, (-300, 1600), "MULTIPLY", b=3.0); L.new(fuu.outputs[0], fus.inputs[0]); L.new(fus.outputs[0], fnv.inputs[0])
    fvs = math(N, (-300, 1850), "MULTIPLY", b=55.0); L.new(fvv.outputs[0], fvs.inputs[0]); L.new(fvs.outputs[0], fnv.inputs[1])
    fnz = new(N, "ShaderNodeTexNoise", (-100, 1700), "Fade Stroke Noise")
    fnz.noise_dimensions = "3D"; fnz.inputs["Scale"].default_value = 1.0; fnz.inputs["Detail"].default_value = 2.0
    L.new(fnv.outputs[0], fnz.inputs["Vector"])
    fno = math(N, (50, 1600), "MULTIPLY_ADD", b=0.4, c=-0.2); L.new(fnz.outputs[0], fno.inputs[0])
    fdd = math(N, (200, 1450), "ADD"); L.new(FD, fdd.inputs[0]); L.new(fno.outputs[0], fdd.inputs[1])
    fen = math(N, (200, 1300), "ADD", b=0.35); L.new(I("Fade Start"), fen.inputs[0])
    frp = new(N, "ShaderNodeMapRange", (350, 1400), "Fade Ramp")
    frp.clamp = True; frp.interpolation_type = "SMOOTHSTEP"
    L.new(fdd.outputs[0], frp.inputs["Value"]); L.new(I("Fade Start"), frp.inputs["From Min"]); L.new(fen.outputs[0], frp.inputs["From Max"])
    fam = math(N, (500, 1400), "MULTIPLY"); L.new(frp.outputs["Result"], fam.inputs[0]); L.new(I("Fade Amount"), fam.inputs[1])
    fkp = math(N, (650, 1400), "SUBTRACT", a=1.0, label="Fade Keep"); L.new(fam.outputs[0], fkp.inputs[1])
    KEEP = fkp.outputs[0]
    tf = math(N, (0, 200), "MULTIPLY", label="Tone (faded)"); L.new(T0, tf.inputs[0]); L.new(KEEP, tf.inputs[1])
    T = tf.outputs[0]
    ninv = math(N, (-150, 350), "SUBTRACT", a=1.0, label="Not Inverted"); L.new(I("Tone Invert"), ninv.inputs[1])
    NINV = ninv.outputs[0]
    L.new(T, go.inputs["Tone"])
    # tone steps (sumi washes, two-level screentone): T quantised, soft 4 % edge
    stp = math(N, (0, 350), "MAXIMUM", b=1.0); L.new(I("Tone Steps"), stp.inputs[0])
    tq0 = math(N, (150, 350), "MULTIPLY"); L.new(T, tq0.inputs[0]); L.new(stp.outputs[0], tq0.inputs[1])
    tqf = math(N, (300, 300), "FLOOR"); L.new(tq0.outputs[0], tqf.inputs[0])
    tqr = math(N, (300, 400), "FRACT"); L.new(tq0.outputs[0], tqr.inputs[0])
    tqs = maprange(N, (420, 400), 0.36, 0.64, smooth=True, label="Soft Step"); L.new(tqr.outputs[0], tqs.inputs["Value"])
    tq1 = math(N, (540, 350), "ADD"); L.new(tqf.outputs[0], tq1.inputs[0]); L.new(tqs.outputs["Result"], tq1.inputs[1])
    tq2 = math(N, (660, 350), "DIVIDE"); L.new(tq1.outputs[0], tq2.inputs[0]); L.new(stp.outputs[0], tq2.inputs[1])
    use_q = math(N, (300, 450), "GREATER_THAN", b=0.5); L.new(I("Tone Steps"), use_q.inputs[0])
    tqm = mix(N, (600, 350), dtype="FLOAT", label="Stepped Tone"); f, a, b, TQ = mix_io(tqm)
    L.new(use_q.outputs[0], f); L.new(T, a); L.new(tq2.outputs[0], b)

    # highlight mask (white chalk on toned paper): lit and light-coloured
    hhi = math(N, (-300, 800), "ADD", b=0.15); L.new(I("Highlight"), hhi.inputs[0])
    hr = new(N, "ShaderNodeMapRange", (-150, 800), "Highlight Ramp")
    hr.clamp = True; hr.interpolation_type = "SMOOTHSTEP"
    L.new(V, hr.inputs["Value"]); L.new(I("Highlight"), hr.inputs["From Min"]); L.new(hhi.outputs[0], hr.inputs["From Max"])
    L.new(hr.outputs["Result"], go.inputs["Highlight"])

    # ---------------------------------------------------------------- screen coordinates
    wsep = new(N, "ShaderNodeSeparateXYZ", (-2600, -900)); L.new(tc.outputs["Window"], wsep.inputs[0])
    rx = S.render("render.resolution_x", 1920.0)
    ry = S.render("render.resolution_y", 1080.0)
    rp = S.render("render.resolution_percentage", 100.0)
    asp = math(N, (-2450, -1000), "DIVIDE", label="Aspect"); L.new(rx, asp.inputs[0]); L.new(ry, asp.inputs[1])
    sx = math(N, (-2300, -900), "MULTIPLY"); L.new(wsep.outputs[0], sx.inputs[0]); L.new(asp.outputs[0], sx.inputs[1])
    SX, SY = sx.outputs[0], wsep.outputs[1]
    pxh = math(N, (-2450, -1150), "MULTIPLY", b=0.01, label="Pixels High"); L.new(ry, pxh.inputs[0])
    pxh2 = math(N, (-2300, -1150), "MULTIPLY"); L.new(pxh.outputs[0], pxh2.inputs[0]); L.new(rp, pxh2.inputs[1])
    PXH = pxh2.outputs[0]
    # Follow Form profile: a smooth dome over the object's bounding sphere (radius stored on the object by
    # Make It Senga), so the lines bow once over each form and ignore small sculpted bumps
    oinf = new(N, "ShaderNodeObjectInfo", (-2800, -1700))
    o2c = new(N, "ShaderNodeVectorTransform", (-2600, -1700), "Origin To Camera")
    o2c.vector_type = "POINT"; o2c.convert_from = "WORLD"; o2c.convert_to = "CAMERA"
    # centre and radius are stored in the object's own space, so moving / animated objects and
    # collection instances keep their lines on the form
    cen_a = new(N, "ShaderNodeAttribute", (-3000, -1600), "Object Centre")
    cen_a.attribute_type = "OBJECT"; cen_a.attribute_name = TAG + "_centre"
    o2c.convert_from = "OBJECT"
    L.new(cen_a.outputs["Vector"], o2c.inputs[0])
    rel = vmath(N, (-2450, -1750), "SUBTRACT"); L.new(tc.outputs["Camera"], rel.inputs[0]); L.new(o2c.outputs[0], rel.inputs[1])
    rsx = new(N, "ShaderNodeSeparateXYZ", (-2300, -1750)); L.new(rel.outputs[0], rsx.inputs[0])
    rxy = new(N, "ShaderNodeCombineXYZ", (-2150, -1750)); L.new(rsx.outputs[0], rxy.inputs[0]); L.new(rsx.outputs[1], rxy.inputs[1])
    rln = vmath(N, (-2000, -1750), "LENGTH"); L.new(rxy.outputs[0], rln.inputs[0])
    rad_a = new(N, "ShaderNodeAttribute", (-2600, -1950), "Object Radius")
    rad_a.attribute_type = "OBJECT"; rad_a.attribute_name = TAG + "_radius"
    # local radius -> world: scale by the object's mean axis scale
    rsc = new(N, "ShaderNodeVectorTransform", (-2600, -2050), "Radius Scale")
    rsc.vector_type = "VECTOR"; rsc.convert_from = "OBJECT"; rsc.convert_to = "WORLD"
    rsc.inputs[0].default_value = (0.57735, 0.57735, 0.57735)
    rsl = vmath(N, (-2450, -2050), "LENGTH"); L.new(rsc.outputs[0], rsl.inputs[0])
    rw = math(N, (-2450, -1950), "MULTIPLY", label="World Radius"); L.new(rad_a.outputs["Factor"], rw.inputs[0])
    L.new(rsl.outputs["Value"], rw.inputs[1])
    RW = rw.outputs[0]
    rad = math(N, (-2300, -1950), "MAXIMUM", b=1e-4); L.new(RW, rad.inputs[0])
    rr = math(N, (-1850, -1800), "DIVIDE"); L.new(rln.outputs["Value"], rr.inputs[0]); L.new(rad.outputs[0], rr.inputs[1])
    rr2 = math(N, (-1700, -1800), "MULTIPLY"); L.new(rr.outputs[0], rr2.inputs[0]); L.new(rr.outputs[0], rr2.inputs[1])
    dm0 = math(N, (-1550, -1800), "SUBTRACT", a=1.0); L.new(rr2.outputs[0], dm0.inputs[1])
    dm1 = math(N, (-1400, -1800), "MAXIMUM", b=0.0); L.new(dm0.outputs[0], dm1.inputs[0])
    rim = maprange(N, (-1400, -1950), 0.85, 1.1, 1.0, 0.0, smooth=True, label="Dome Rim"); L.new(rr.outputs[0], rim.inputs["Value"])
    dome = math(N, (-1250, -1800), "MULTIPLY", label="Dome"); L.new(dm1.outputs[0], dome.inputs[0]); L.new(rim.outputs["Result"], dome.inputs[1])
    osz = new(N, "ShaderNodeSeparateXYZ", (-2450, -2100)); L.new(o2c.outputs[0], osz.inputs[0])
    az0 = math(N, (-2300, -2100), "ABSOLUTE"); L.new(osz.outputs[2], az0.inputs[0])
    az1 = math(N, (-2150, -2100), "MAXIMUM", b=1e-4); L.new(az0.outputs[0], az1.inputs[0])
    rs_ = math(N, (-2000, -2100), "DIVIDE"); L.new(RW, rs_.inputs[0]); L.new(az1.outputs[0], rs_.inputs[1])
    db = math(N, (-1100, -1900), "MULTIPLY"); L.new(dome.outputs[0], db.inputs[0]); L.new(rs_.outputs[0], db.inputs[1])
    dzk = math(N, (-950, -1900), "MULTIPLY", b=0.45, label="Depth Bend"); L.new(db.outputs[0], dzk.inputs[0])
    DEPTH_BEND = dzk.outputs[0]
    minsp = math(N, (-2300, -1300), "DIVIDE", a=3.0, label="3 px"); L.new(PXH, minsp.inputs[1])
    spacing = math(N, (-2150, -1150), "MAXIMUM", label="Spacing"); L.new(I("Hatch Spacing"), spacing.inputs[0])
    L.new(minsp.outputs[0], spacing.inputs[1])
    SP = spacing.outputs[0]
    sp_px = math(N, (-2000, -1150), "MULTIPLY"); L.new(SP, sp_px.inputs[0]); L.new(PXH, sp_px.inputs[1])
    aa = math(N, (-1850, -1150), "DIVIDE", a=0.55, label="AA"); L.new(sp_px.outputs[0], aa.inputs[1])
    AA = aa.outputs[0]
    seedp = math(N, (-2000, -1300), "ADD", label="Seed + Boil"); L.new(I("Seed"), seedp.inputs[0]); L.new(I("Phase"), seedp.inputs[1])
    SEED = seedp.outputs[0]
    # big soft patches: hatching comes in groups, not one even field
    pv = new(N, "ShaderNodeCombineXYZ", (-2000, -1500)); L.new(SX, pv.inputs[0]); L.new(SY, pv.inputs[1]); L.new(SEED, pv.inputs[2])
    patch = new(N, "ShaderNodeTexNoise", (-1850, -1500), "Patch Noise")
    patch.noise_dimensions = "3D"
    patch.inputs["Scale"].default_value = 4.0
    patch.inputs["Detail"].default_value = 1.0
    L.new(pv.outputs[0], patch.inputs["Vector"])
    pch = math(N, (-1700, -1500), "SUBTRACT", b=0.5); L.new(patch.outputs[0], pch.inputs[0])
    pch2 = math(N, (-1550, -1500), "MULTIPLY", b=0.22, label="Patch Offset"); L.new(pch.outputs[0], pch2.inputs[0])
    PATCH = pch2.outputs[0]

    def rotated(angle_sock, loc):
        """(u along the line, v across), screen space; Follow Form bends v with the view normal so
        the lines curve over the volume like engraving / cross-contour hatching."""
        x0, y0 = loc
        sn = math(N, (x0, y0), "SINE"); L.new(angle_sock, sn.inputs[0])
        cs = math(N, (x0, y0 - 80), "COSINE"); L.new(angle_sock, cs.inputs[0])
        neg = math(N, (x0, y0 - 160), "MULTIPLY", b=-1.0); L.new(sn.outputs[0], neg.inputs[0])

        def lin(a1, s1, a2, s2, yy):
            m1 = math(N, (x0 + 150, yy), "MULTIPLY"); L.new(a1, m1.inputs[0]); L.new(s1, m1.inputs[1])
            m2 = math(N, (x0 + 150, yy - 50), "MULTIPLY"); L.new(a2, m2.inputs[0]); L.new(s2, m2.inputs[1])
            ad = math(N, (x0 + 300, yy), "ADD"); L.new(m1.outputs[0], ad.inputs[0]); L.new(m2.outputs[0], ad.inputs[1])
            return ad.outputs[0]

        u = lin(SX, cs.outputs[0], SY, sn.outputs[0], y0)
        v_s = lin(SX, neg.outputs[0], SY, cs.outputs[0], y0 - 200)
        # Follow Form: lines bow over the volume by the point's depth relative to the object's centre
        # (smooth on any mesh, unlike bending by the normal, which swirls on sculpted detail)
        bend = math(N, (x0 + 600, y0 - 400), "MULTIPLY"); L.new(DEPTH_BEND, bend.inputs[0]); L.new(I("Form"), bend.inputs[1])
        v = math(N, (x0 + 600, y0 - 200), "ADD"); L.new(v_s, v.inputs[0]); L.new(bend.outputs[0], v.inputs[1])
        return u, v.outputs[0]

    def hatch_layer(angle_sock, start_sock, loc, seed_off):
        """One family of parallel hand-drawn lines: every line has its own offset, weight, start tone and
        wobble; strokes break into tapered pieces of varied length; width follows the tone."""
        x0, y0 = loc
        u, v = rotated(angle_sock, (x0, y0))
        x1 = x0 + 800
        so = math(N, (x1 - 100, y0 + 450), "ADD", b=seed_off); L.new(SEED, so.inputs[0])
        SO = so.outputs[0]
        ph0 = math(N, (x1, y0), "DIVIDE"); L.new(v, ph0.inputs[0]); L.new(SP, ph0.inputs[1])
        ph = math(N, (x1 + 120, y0), "ADD"); L.new(ph0.outputs[0], ph.inputs[0]); L.new(SO, ph.inputs[1])
        PH = ph.outputs[0]
        k = math(N, (x1 + 240, y0 - 100), "ROUND", label="Line Index"); L.new(PH, k.inputs[0])
        K = k.outputs[0]
        # per-line random numbers
        kv = new(N, "ShaderNodeCombineXYZ", (x1 + 360, y0 + 300)); L.new(K, kv.inputs[0]); L.new(SO, kv.inputs[1])
        kv.inputs[2].default_value = seed_off * 0.37
        wn = new(N, "ShaderNodeTexWhiteNoise", (x1 + 480, y0 + 300), "Line Random")
        wn.noise_dimensions = "3D"
        L.new(kv.outputs[0], wn.inputs["Vector"])
        rnd = new(N, "ShaderNodeSeparateColor", (x1 + 620, y0 + 300)); L.new(wn.outputs["Color"], rnd.inputs[0])
        R1, R2, R3 = rnd.outputs[0], rnd.outputs[1], rnd.outputs[2]
        # wobble along the line, independent per line
        uk = math(N, (x1 + 360, y0 + 550), "MULTIPLY"); L.new(u, uk.inputs[0]); L.new(I("Wobble Scale"), uk.inputs[1])
        kk = math(N, (x1 + 360, y0 + 650), "MULTIPLY", b=0.618); L.new(K, kk.inputs[0])
        wv = new(N, "ShaderNodeCombineXYZ", (x1 + 480, y0 + 600)); L.new(uk.outputs[0], wv.inputs[0])
        L.new(kk.outputs[0], wv.inputs[1]); L.new(SO, wv.inputs[2])
        wnz = new(N, "ShaderNodeTexNoise", (x1 + 620, y0 + 600), "Wobble Noise")
        wnz.noise_dimensions = "3D"
        wnz.inputs["Scale"].default_value = 1.0
        wnz.inputs["Detail"].default_value = 1.0
        L.new(wv.outputs[0], wnz.inputs["Vector"])
        wc_ = math(N, (x1 + 760, y0 + 600), "SUBTRACT", b=0.5); L.new(wnz.outputs[0], wc_.inputs[0])
        wa = math(N, (x1 + 900, y0 + 600), "MULTIPLY"); L.new(wc_.outputs[0], wa.inputs[0]); L.new(I("Wobble"), wa.inputs[1])
        jit = math(N, (x1 + 760, y0 + 450), "MULTIPLY_ADD", b=0.24, c=-0.12); L.new(R1, jit.inputs[0])   # spacing +-12 %
        off = math(N, (x1 + 1040, y0 + 500), "ADD"); L.new(wa.outputs[0], off.inputs[0]); L.new(jit.outputs[0], off.inputs[1])
        offc = math(N, (x1 + 1180, y0 + 500), "MINIMUM", b=0.26); L.new(off.outputs[0], offc.inputs[0])
        offc2 = math(N, (x1 + 1300, y0 + 500), "MAXIMUM", b=-0.26); L.new(offc.outputs[0], offc2.inputs[0])
        dc0 = math(N, (x1 + 360, y0), "SUBTRACT"); L.new(PH, dc0.inputs[0]); L.new(K, dc0.inputs[1])
        dc = math(N, (x1 + 1400, y0), "SUBTRACT"); L.new(dc0.outputs[0], dc.inputs[0]); L.new(offc2.outputs[0], dc.inputs[1])
        d = math(N, (x1 + 1520, y0), "ABSOLUTE", label="Line Distance"); L.new(dc.outputs[0], d.inputs[0])
        # tone -> width; each line starts at its own tone, groups follow the patch noise
        st0 = math(N, (x1 + 760, y0 - 300), "MULTIPLY_ADD", b=0.12, c=-0.06); L.new(R3, st0.inputs[0])
        st1 = math(N, (x1 + 900, y0 - 300), "ADD"); L.new(start_sock, st1.inputs[0]); L.new(st0.outputs[0], st1.inputs[1])
        st2 = math(N, (x1 + 1040, y0 - 300), "ADD"); L.new(st1.outputs[0], st2.inputs[0]); L.new(PATCH, st2.inputs[1])
        tend = math(N, (x1 + 1180, y0 - 380), "ADD", b=0.4); L.new(st2.outputs[0], tend.inputs[0])
        tr = new(N, "ShaderNodeMapRange", (x1 + 1320, y0 - 300), "Tone Ramp")
        tr.clamp = True
        L.new(T, tr.inputs["Value"]); L.new(st2.outputs[0], tr.inputs["From Min"]); L.new(tend.outputs[0], tr.inputs["From Max"])
        TR = tr.outputs["Result"]
        # strokes: per-line noise along the line, each line with its own stroke length
        sl = math(N, (x1 + 760, y0 - 600), "MULTIPLY_ADD", b=0.1, c=0.05); L.new(R2, sl.inputs[0])
        bu = math(N, (x1 + 900, y0 - 600), "DIVIDE"); L.new(u, bu.inputs[0]); L.new(SP, bu.inputs[1])
        bu2 = math(N, (x1 + 1040, y0 - 600), "MULTIPLY"); L.new(bu.outputs[0], bu2.inputs[0]); L.new(sl.outputs[0], bu2.inputs[1])
        bk = math(N, (x1 + 1040, y0 - 700), "MULTIPLY", b=1.731); L.new(K, bk.inputs[0])
        bv = new(N, "ShaderNodeCombineXYZ", (x1 + 1180, y0 - 650))
        L.new(bu2.outputs[0], bv.inputs[0]); L.new(bk.outputs[0], bv.inputs[1]); L.new(SO, bv.inputs[2])
        bn_ = new(N, "ShaderNodeTexNoise", (x1 + 1320, y0 - 650), "Breakup Noise")
        bn_.noise_dimensions = "3D"
        bn_.inputs["Scale"].default_value = 1.0
        bn_.inputs["Detail"].default_value = 2.0
        L.new(bv.outputs[0], bn_.inputs["Vector"])
        t6 = math(N, (x1 + 1180, y0 - 850), "MULTIPLY_ADD", b=-0.6, c=1.0); L.new(TR, t6.inputs[0])
        t7 = math(N, (x1 + 1320, y0 - 850), "MULTIPLY", b=0.45); L.new(I("Breakup"), t7.inputs[0])
        t8 = math(N, (x1 + 1460, y0 - 850), "MULTIPLY_ADD", c=0.25); L.new(t6.outputs[0], t8.inputs[0]); L.new(t7.outputs[0], t8.inputs[1])
        t9 = math(N, (x1 + 1460, y0 - 950), "ADD", b=0.14); L.new(t8.outputs[0], t9.inputs[0])
        gap = new(N, "ShaderNodeMapRange", (x1 + 1600, y0 - 650), "Stroke Taper")
        gap.clamp = True; gap.interpolation_type = "SMOOTHSTEP"
        L.new(bn_.outputs[0], gap.inputs["Value"]); L.new(t8.outputs[0], gap.inputs["From Min"]); L.new(t9.outputs[0], gap.inputs["From Max"])
        # half width = ramp * weight * 0.5 * per-line weight (0.7..1.2) * taper
        lw = math(N, (x1 + 1320, y0 - 150), "MULTIPLY_ADD", b=0.5, c=0.7); L.new(R2, lw.inputs[0])
        hw = math(N, (x1 + 1460, y0 - 300), "MULTIPLY"); L.new(TR, hw.inputs[0]); L.new(I("Hatch Width"), hw.inputs[1])
        hw2 = math(N, (x1 + 1600, y0 - 300), "MULTIPLY"); L.new(hw.outputs[0], hw2.inputs[0]); L.new(lw.outputs[0], hw2.inputs[1])
        hw3 = math(N, (x1 + 1740, y0 - 300), "MULTIPLY", b=0.5); L.new(hw2.outputs[0], hw3.inputs[0])
        hw4 = math(N, (x1 + 1880, y0 - 300), "MULTIPLY", label="Half Width")
        L.new(hw3.outputs[0], hw4.inputs[0]); L.new(gap.outputs["Result"], hw4.inputs[1])
        W = hw4.outputs[0]
        e0 = math(N, (x1 + 2020, y0 - 150), "SUBTRACT"); L.new(W, e0.inputs[0]); L.new(AA, e0.inputs[1])
        e1 = math(N, (x1 + 2020, y0 - 250), "ADD"); L.new(W, e1.inputs[0]); L.new(AA, e1.inputs[1])
        ink = new(N, "ShaderNodeMapRange", (x1 + 2160, y0), "Line AA")
        ink.clamp = True
        ink.inputs["To Min"].default_value = 1.0; ink.inputs["To Max"].default_value = 0.0
        L.new(d.outputs[0], ink.inputs["Value"]); L.new(e0.outputs[0], ink.inputs["From Min"]); L.new(e1.outputs[0], ink.inputs["From Max"])
        thin = math(N, (x1 + 2160, y0 - 250), "DIVIDE", clamp=True); L.new(W, thin.inputs[0]); L.new(AA, thin.inputs[1])
        out = math(N, (x1 + 2300, y0), "MULTIPLY"); L.new(ink.outputs["Result"], out.inputs[0]); L.new(thin.outputs[0], out.inputs[1])
        return out.outputs[0], u, v

    # three line families: main, cross (core shadow), deep (between the two)
    a1 = I("Hatch Angle")
    a2 = math(N, (-1800, -2600), "ADD"); L.new(a1, a2.inputs[0]); L.new(I("Cross Angle"), a2.inputs[1])
    a3h = math(N, (-1950, -3800), "MULTIPLY", b=0.5); L.new(I("Cross Angle"), a3h.inputs[0])
    a3 = math(N, (-1800, -3800), "SUBTRACT"); L.new(a1, a3.inputs[0]); L.new(a3h.outputs[0], a3.inputs[1])
    h1, u1, v1 = hatch_layer(a1, I("Hatch Start"), (-1600, -1800), 0.0)
    h2, _u2, _v2 = hatch_layer(a2.outputs[0], I("Cross Start"), (-1600, -2900), 17.3)
    h3, _u3, _v3 = hatch_layer(a3.outputs[0], I("Deep Start"), (-1600, -4000), 41.7)
    hm1 = math(N, (1300, -2400), "MAXIMUM"); L.new(h1, hm1.inputs[0]); L.new(h2, hm1.inputs[1])
    hm2 = math(N, (1450, -2400), "MAXIMUM", label="Lines"); L.new(hm1.outputs[0], hm2.inputs[0]); L.new(h3, hm2.inputs[1])
    LINES = hm2.outputs[0]

    # ---------------------------------------------------------------- screentone dots / stipple
    cov = new(N, "ShaderNodeMapRange", (300, -4900), "Dot Coverage")
    cov.clamp = True
    L.new(TQ, cov.inputs["Value"]); L.new(I("Hatch Start"), cov.inputs["From Min"])
    cs_end = math(N, (150, -5000), "ADD", b=0.45); L.new(I("Hatch Start"), cs_end.inputs[0])
    L.new(cs_end.outputs[0], cov.inputs["From Max"])
    rad = math(N, (450, -4900), "SQRT"); L.new(cov.outputs["Result"], rad.inputs[0])
    radr = math(N, (600, -4900), "MULTIPLY", b=0.62, label="Dot Radius"); L.new(rad.outputs[0], radr.inputs[0])
    dv = new(N, "ShaderNodeCombineXYZ", (300, -4600)); L.new(u1, dv.inputs[0]); L.new(v1, dv.inputs[1])
    dsc = vmath(N, (450, -4600), "DIVIDE"); L.new(dv.outputs[0], dsc.inputs[0])
    spv = new(N, "ShaderNodeCombineXYZ", (300, -4750)); L.new(SP, spv.inputs[0]); L.new(SP, spv.inputs[1]); spv.inputs[2].default_value = 1.0
    L.new(spv.outputs[0], dsc.inputs[1])
    dfr = vmath(N, (600, -4600), "FRACTION"); L.new(dsc.outputs[0], dfr.inputs[0])
    dce = vmath(N, (750, -4600), "SUBTRACT"); dce.inputs[1].default_value = (0.5, 0.5, 0.0); L.new(dfr.outputs[0], dce.inputs[0])
    dln = vmath(N, (900, -4600), "LENGTH"); L.new(dce.outputs[0], dln.inputs[0])
    vor = new(N, "ShaderNodeTexVoronoi", (750, -5200), "Stipple")
    vor.voronoi_dimensions = "2D"
    vor.inputs["Scale"].default_value = 1.0
    vor.inputs["Randomness"].default_value = 0.55     # evenly spread, not clumpy grain
    L.new(dsc.outputs[0], vor.inputs["Vector"])
    pat_st = math(N, (900, -4950), "COMPARE", b=2.0, c=0.5); L.new(I("Pattern"), pat_st.inputs[0])
    dmix = mix(N, (1050, -4700), dtype="FLOAT", label="Dots Or Stipple"); f, a, b, dd = mix_io(dmix)
    L.new(pat_st.outputs[0], f); L.new(dln.outputs["Value"], a); L.new(vor.outputs["Distance"], b)
    st_r = math(N, (900, -5100), "MULTIPLY", b=0.8); L.new(radr.outputs[0], st_r.inputs[0])
    rmix = mix(N, (1050, -4900), dtype="FLOAT"); f, a, b, rr = mix_io(rmix)
    L.new(pat_st.outputs[0], f); L.new(radr.outputs[0], a); L.new(st_r.outputs[0], b)
    r0 = math(N, (1200, -4800), "SUBTRACT"); L.new(rr, r0.inputs[0]); L.new(AA, r0.inputs[1])
    r1 = math(N, (1200, -4900), "ADD"); L.new(rr, r1.inputs[0]); L.new(AA, r1.inputs[1])
    dot = new(N, "ShaderNodeMapRange", (1350, -4700), "Dot AA")
    dot.clamp = True
    dot.inputs["To Min"].default_value = 1.0; dot.inputs["To Max"].default_value = 0.0
    L.new(dd, dot.inputs["Value"]); L.new(r0.outputs[0], dot.inputs["From Min"]); L.new(r1.outputs[0], dot.inputs["From Max"])
    dthin = math(N, (1350, -4950), "DIVIDE", clamp=True); L.new(rr, dthin.inputs[0]); L.new(AA, dthin.inputs[1])
    dots = math(N, (1500, -4700), "MULTIPLY"); L.new(dot.outputs["Result"], dots.inputs[0]); L.new(dthin.outputs[0], dots.inputs[1])
    is_pt = math(N, (1500, -4950), "GREATER_THAN", b=0.5); L.new(I("Pattern"), is_pt.inputs[0])
    pm = mix(N, (1650, -2400), dtype="FLOAT", label="Pattern"); f, a, b, PAT = mix_io(pm)
    L.new(is_pt.outputs[0], f); L.new(LINES, a); L.new(dots.outputs[0], b)
    hamt = math(N, (1800, -2400), "MULTIPLY", label="Hatch Amount", clamp=True)
    L.new(PAT, hamt.inputs[0]); L.new(I("Hatch"), hamt.inputs[1])
    hmk = math(N, (1950, -2400), "MULTIPLY", clamp=True); L.new(hamt.outputs[0], hmk.inputs[0]); L.new(I("Paper Marks"), hmk.inputs[1])
    H = hmk.outputs[0]

    # ---------------------------------------------------------------- stroke texture (along the hatch)
    sv = new(N, "ShaderNodeCombineXYZ", (300, -1200))
    su = math(N, (150, -1150), "MULTIPLY", b=2.5); L.new(u1, su.inputs[0])
    svv = math(N, (150, -1250), "MULTIPLY", b=60.0); L.new(v1, svv.inputs[0])
    L.new(su.outputs[0], sv.inputs[0]); L.new(svv.outputs[0], sv.inputs[1]); L.new(SEED, sv.inputs[2])
    streak = new(N, "ShaderNodeTexNoise", (450, -1200), "Streak Noise")
    streak.noise_dimensions = "3D"
    streak.inputs["Scale"].default_value = 1.0
    streak.inputs["Detail"].default_value = 3.0
    streak.inputs["Roughness"].default_value = 0.6
    L.new(sv.outputs[0], streak.inputs["Vector"])
    STK = streak.outputs[0]

    # ---------------------------------------------------------------- graphite fill (tonal wash)
    fr_ = new(N, "ShaderNodeMapRange", (300, -400), "Fill Ramp")
    fr_.clamp = True
    L.new(TQ, fr_.inputs["Value"]); L.new(I("Fill Start"), fr_.inputs["From Min"])
    fsk = math(N, (450, -600), "SUBTRACT", b=0.5); L.new(STK, fsk.inputs[0])
    fsk2 = math(N, (600, -600), "MULTIPLY"); L.new(fsk.outputs[0], fsk2.inputs[0]); L.new(I("Fill Texture"), fsk2.inputs[1])
    fsk3 = math(N, (750, -600), "MULTIPLY_ADD", b=4.0, c=1.0); L.new(fsk2.outputs[0], fsk3.inputs[0])
    ftx = math(N, (600, -400), "MULTIPLY", clamp=True); L.new(fr_.outputs["Result"], ftx.inputs[0]); L.new(fsk3.outputs[0], ftx.inputs[1])
    famt = math(N, (750, -400), "MULTIPLY", label="Fill Amount", clamp=True)
    L.new(ftx.outputs[0], famt.inputs[0]); L.new(I("Fill"), famt.inputs[1])
    # dark papers: almost no fill (chalk is drawn, not rubbed in)
    finv = math(N, (900, -500), "MULTIPLY_ADD", b=0.6, c=0.4); L.new(NINV, finv.inputs[0])
    fmk = math(N, (900, -400), "MULTIPLY"); L.new(famt.outputs[0], fmk.inputs[0]); L.new(finv.outputs[0], fmk.inputs[1])
    fmk2 = math(N, (1050, -400), "MULTIPLY", clamp=True); L.new(fmk.outputs[0], fmk2.inputs[0]); L.new(I("Paper Marks"), fmk2.inputs[1])
    fmk3 = math(N, (1200, -400), "MULTIPLY", clamp=True); L.new(fmk2.outputs[0], fmk3.inputs[0]); L.new(KEEP, fmk3.inputs[1])
    F = fmk3.outputs[0]

    # ---------------------------------------------------------------- solid blacks with dry-brush edge
    dsk = math(N, (300, -800), "SUBTRACT", b=0.5); L.new(STK, dsk.inputs[0])
    dsk2 = math(N, (450, -800), "MULTIPLY"); L.new(dsk.outputs[0], dsk2.inputs[0]); L.new(I("Dry Brush"), dsk2.inputs[1])
    dsk3 = math(N, (600, -800), "MULTIPLY_ADD", b=0.3); L.new(dsk2.outputs[0], dsk3.inputs[0]); L.new(T, dsk3.inputs[2])
    se = math(N, (600, -950), "ADD", b=0.04); L.new(I("Solid Start"), se.inputs[0])
    sr = new(N, "ShaderNodeMapRange", (750, -800), "Solid Ramp")
    sr.clamp = True; sr.interpolation_type = "SMOOTHSTEP"
    L.new(dsk3.outputs[0], sr.inputs["Value"]); L.new(I("Solid Start"), sr.inputs["From Min"]); L.new(se.outputs[0], sr.inputs["From Max"])
    samt = math(N, (900, -800), "MULTIPLY", label="Solid Amount", clamp=True)
    L.new(sr.outputs["Result"], samt.inputs[0]); L.new(I("Solid"), samt.inputs[1])
    sinv = math(N, (1050, -800), "MULTIPLY"); L.new(samt.outputs[0], sinv.inputs[0]); L.new(NINV, sinv.inputs[1])
    SOL = sinv.outputs[0]

    # ---------------------------------------------------------------- coverage = 1 - (1-F)(1-H)(1-S)
    i1 = math(N, (2100, -800), "SUBTRACT", a=1.0); L.new(F, i1.inputs[1])
    i2 = math(N, (2100, -950), "SUBTRACT", a=1.0); L.new(H, i2.inputs[1])
    i3 = math(N, (2100, -1100), "SUBTRACT", a=1.0); L.new(SOL, i3.inputs[1])
    p1 = math(N, (2250, -900), "MULTIPLY"); L.new(i1.outputs[0], p1.inputs[0]); L.new(i2.outputs[0], p1.inputs[1])
    p2 = math(N, (2400, -950), "MULTIPLY"); L.new(p1.outputs[0], p2.inputs[0]); L.new(i3.outputs[0], p2.inputs[1])
    C = math(N, (2550, -950), "SUBTRACT", a=1.0, label="Coverage", clamp=True); L.new(p2.outputs[0], C.inputs[1])
    gko = math(N, (2550, -1100), "SUBTRACT", a=1.0, clamp=True); L.new(GLOSS_KO, gko.inputs[1])
    C2 = math(N, (2700, -950), "MULTIPLY", label="Coverage - Gloss", clamp=True); L.new(C.outputs[0], C2.inputs[0]); L.new(gko.outputs[0], C2.inputs[1])
    COV = C2.outputs[0]
    L.new(COV, go.inputs["Ink"])

    # ---------------------------------------------------------------- colour wash under the ink
    sep = new(N, "ShaderNodeSeparateColor", (1500, 300)); L.new(I("Base Color"), sep.inputs[0])
    c1 = math(N, (1650, 350), "MAXIMUM"); L.new(sep.outputs[0], c1.inputs[0]); L.new(sep.outputs[1], c1.inputs[1])
    c2 = math(N, (1800, 350), "MAXIMUM"); L.new(c1.outputs[0], c2.inputs[0]); L.new(sep.outputs[2], c2.inputs[1])
    c3 = math(N, (1950, 350), "MAXIMUM", b=1e-3); L.new(c2.outputs[0], c3.inputs[0])
    nrm = vmath(N, (2100, 300), "DIVIDE"); L.new(I("Base Color"), nrm.inputs[0]); L.new(c3.outputs[0], nrm.inputs[1])
    hs = new(N, "ShaderNodeHueSaturation", (2250, 300), "Wash Saturation")
    L.new(nrm.outputs[0], hs.inputs["Color"]); L.new(I("Wash Saturation"), hs.inputs["Saturation"])
    wm = mix(N, (2450, 300), "MIX", label="Wash Mix"); f, a, b, WASH = mix_io(wm)
    L.new(I("Wash"), f); a.default_value = (1, 1, 1, 1); L.new(hs.outputs[0], b)
    wem = vmath(N, (2600, 300), "ADD"); L.new(WASH, wem.inputs[0]); L.new(I("Emission"), wem.inputs[1])
    L.new(wem.outputs[0], go.inputs["Wash"])

    # ---------------------------------------------------------------- surface (white paper preview)
    fin = mix(N, (2900, 0), "MIX", label="Ink Over Wash"); f, a, b, FIN = mix_io(fin)
    L.new(COV, f); L.new(wem.outputs[0], a); L.new(I("Ink Color"), b)
    emit = new(N, "ShaderNodeEmission", (3100, 0)); L.new(FIN, emit.inputs["Color"])
    tr = new(N, "ShaderNodeBsdfTransparent", (3100, 150))
    ms = new(N, "ShaderNodeMixShader", (3300, 50))
    L.new(I("Alpha"), ms.inputs[0]); L.new(tr.outputs[0], ms.inputs[1]); L.new(emit.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], go.inputs["Shader"])
    return ng


# --------------------------------------------------------------------------
def _output_node(nt):
    """The output EEVEE actually uses: an EEVEE-target output wins over the active 'All' output."""
    outs = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"]
    return (next((n for n in outs if n.target == "EEVEE"), None)
            or next((n for n in outs if n.is_active_output and n.target == "ALL"), None)
            or next((n for n in outs if n.is_active_output), None)
            or (outs[0] if outs else None))


def _shade_node(nt):
    return next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name == SHADE_GROUP), None)


_COLOR_INPUTS = ("Base Color", "Color", "Base Colour")
_CLEAR = ("BSDF_TRANSPARENT", "HOLDOUT")


def _upstream(out):
    seen, stack = set(), []
    if out and out.inputs["Surface"].is_linked:
        stack.append(out.inputs["Surface"].links[0].from_node)
    while stack:
        n = stack.pop()
        if n.name in seen:
            continue
        seen.add(n.name)
        yield n
        for i in n.inputs:
            for lk in i.links:
                stack.append(lk.from_node)


def _mix_alpha(out):
    """Classic cut-out: Mix Shader(Fac, Transparent, X) on the surface -> (socket, invert)."""
    surf = out.inputs["Surface"] if out else None
    n = surf.links[0].from_node if (surf and surf.is_linked) else None
    if n is None or n.type != "MIX_SHADER" or not n.inputs[0].is_linked:
        return None
    a, b = n.inputs[1], n.inputs[2]
    if a.is_linked and a.links[0].from_node.type in _CLEAR:
        return n.inputs[0].links[0].from_socket, False
    if b.is_linked and b.links[0].from_node.type in _CLEAR:
        return n.inputs[0].links[0].from_socket, True
    return None


def _base_color_source(nt, out):
    surf = out.inputs["Surface"] if out else None
    node = surf.links[0].from_node if (surf and surf.is_linked) else None
    seen = set()
    while node is not None and node.name not in seen:
        seen.add(node.name)
        if node.type == "TEX_IMAGE":
            return node.outputs["Color"]
        for name in _COLOR_INPUTS:
            i = node.inputs.get(name)
            if i is not None and i.type == "RGBA":
                return i.links[0].from_socket if i.is_linked else tuple(i.default_value)
        shaders = [i for i in node.inputs if i.is_linked and i.type == "SHADER"]
        nxt = next((i for i in shaders if i.links[0].from_node.type not in _CLEAR), None) or \
            (shaders[0] if shaders else None)
        node = nxt.links[0].from_node if nxt else None
    img = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image), None)
    return img.outputs["Color"] if img else None


def is_glass(mat):
    nt = mat.node_tree
    if nt is None:
        return False
    for n in _upstream(_output_node(nt)):
        if n.type in ("BSDF_GLASS", "BSDF_REFRACTION"):
            return True
        if n.type == "BSDF_PRINCIPLED":
            met = n.inputs.get("Metallic")
            metallic = met is not None and (met.is_linked or met.default_value > 0.5)
            tw = n.inputs.get("Transmission Weight") or n.inputs.get("Transmission")
            if not metallic and tw is not None and not tw.is_linked and tw.default_value > 0.5:
                return True
            al = n.inputs.get("Alpha")
            if getattr(mat, "surface_render_method", "") == "BLENDED" and al is not None and \
                    (al.is_linked or al.default_value < 0.95):
                return True
    return False


# colour AOVs only: value AOVs come through empty in Blender 5.2 EEVEE
_AOVS = (("Senga AOV Ink", AOV_COVER, "Ink", "Color"),
         ("Senga AOV Wash", AOV_WASH, "Wash", "Color"),
         ("Senga AOV Highlight", AOV_HI, "Highlight", "Color"),
         ("Senga AOV Normal", AOV_NORMAL, "View Normal", "Color"),
         ("Senga AOV Depth", AOV_DEPTH, "Depth", "Color"))
_HELPERS = ("Senga Emission", "Senga Alpha", "Senga Ink RGB", "Senga Ground Flag") + tuple(a[0] for a in _AOVS)


def sketchify_material(mat):
    """Insert the Senga Shade group in front of the material output (the original link is
    remembered, so Revert restores it). Glass / see-through surfaces are left alone."""
    if mat is None or mat.name == OUTLINE_MAT or getattr(mat, "library", None):
        return False
    if mat.node_tree is None:
        try:
            mat.use_nodes = True
        except Exception:
            return False
        if mat.node_tree is None:
            return False
    nt = mat.node_tree
    if is_glass(mat):
        mat[TAG + "_glass"] = True
        _glass_aovs(nt)
        return False
    ng = build_shade_group()
    out = _output_node(nt) or nt.nodes.new("ShaderNodeOutputMaterial")
    grp = _shade_node(nt)
    if grp is None:
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = ng
        grp.name = grp.label = SHADE_GROUP
        grp.location = (out.location.x - 280, out.location.y - 300)
        grp.width = 240
    bsdf = next((n for n in _upstream(out) if n.type == "BSDF_PRINCIPLED"), None) or \
        next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bcs = bsdf.inputs["Base Color"]
        if bcs.is_linked:
            nt.links.new(bcs.links[0].from_socket, grp.inputs["Base Color"])
        else:
            grp.inputs["Base Color"].default_value = bcs.default_value
        al = bsdf.inputs["Alpha"]
        if al.is_linked:
            nt.links.new(al.links[0].from_socket, grp.inputs["Alpha"])
        else:
            grp.inputs["Alpha"].default_value = al.default_value
        rg = bsdf.inputs.get("Roughness")
        if rg is not None:
            if rg.is_linked:
                nt.links.new(rg.links[0].from_socket, grp.inputs["Roughness"])
            else:
                grp.inputs["Roughness"].default_value = rg.default_value
        nm = bsdf.inputs["Normal"]
        if nm.is_linked:
            nt.links.new(nm.links[0].from_socket, grp.inputs["Normal"])
            grp.inputs["Use Normal"].default_value = 1.0
        ec, es = bsdf.inputs.get("Emission Color"), bsdf.inputs.get("Emission Strength")
        if ec is not None and es is not None and (ec.is_linked or es.default_value > 0):
            sc = nt.nodes.get("Senga Emission") or nt.nodes.new("ShaderNodeVectorMath")
            sc.operation = "SCALE"
            sc.location = (grp.location.x - 200, grp.location.y - 400)
            sc.name = sc.label = "Senga Emission"
            if ec.is_linked:
                nt.links.new(ec.links[0].from_socket, sc.inputs[0])
            else:
                sc.inputs[0].default_value = ec.default_value[:3]
            if es.is_linked:
                nt.links.new(es.links[0].from_socket, sc.inputs["Scale"])
            else:
                sc.inputs["Scale"].default_value = es.default_value
            nt.links.new(sc.outputs[0], grp.inputs["Emission"])
    else:
        src = _base_color_source(nt, out)
        if src is None:
            grp.inputs["Base Color"].default_value = tuple(mat.diffuse_color)
        elif isinstance(src, tuple):
            grp.inputs["Base Color"].default_value = src
        else:
            nt.links.new(src, grp.inputs["Base Color"])
    ma = _mix_alpha(out) if not grp.inputs["Alpha"].is_linked else None
    if ma:
        sock_, invert = ma
        inv = nt.nodes.get("Senga Alpha") or nt.nodes.new("ShaderNodeMath")
        inv.name = inv.label = "Senga Alpha"
        inv.operation = "SUBTRACT" if invert else "ADD"
        inv.inputs[0].default_value = 1.0 if invert else 0.0
        inv.location = (grp.location.x - 200, grp.location.y - 250)
        nt.links.new(sock_, inv.inputs[1])
        nt.links.new(inv.outputs[0], grp.inputs["Alpha"])
    surf = out.inputs["Surface"]
    if surf.is_linked and surf.links[0].from_node != grp:
        mat[TAG + "_orig_node"] = surf.links[0].from_node.name
        mat[TAG + "_orig_sock"] = surf.links[0].from_socket.identifier
    mat[TAG + "_out_node"] = out.name
    nt.links.new(grp.outputs["Shader"], surf)
    # ink AOV: R = coverage, G = 0 (the outline hull writes G = 1 so the compositor can tell them apart)
    rgb = nt.nodes.get("Senga Ink RGB") or nt.nodes.new("ShaderNodeCombineColor")
    rgb.name = rgb.label = "Senga Ink RGB"
    rgb.location = (out.location.x - 160, out.location.y - 160)
    nt.links.new(grp.outputs["Ink"], rgb.inputs[0])
    # B = "flat ground" flag (set on the object by Make It Senga): no contour lines along its far edge
    gf = nt.nodes.get("Senga Ground Flag") or nt.nodes.new("ShaderNodeAttribute")
    gf.name = gf.label = "Senga Ground Flag"
    gf.attribute_type = "OBJECT"; gf.attribute_name = TAG + "_ground"
    gf.location = (out.location.x - 340, out.location.y - 240)
    nt.links.new(gf.outputs["Factor"], rgb.inputs[2])
    for i, (name, aov_name, out_name, in_name) in enumerate(_AOVS):
        aov = nt.nodes.get(name) or nt.nodes.new("ShaderNodeOutputAOV")
        aov.name = aov.label = name
        aov.aov_name = aov_name
        aov.location = (out.location.x, out.location.y - 160 - 140 * i)
        src = rgb.outputs[0] if out_name == "Ink" else grp.outputs[out_name]
        nt.links.new(src, aov.inputs[in_name])
    mat[TAG] = True
    return True


_GLASS_NODES = ("Senga Glass Rim", "Senga Glass Ramp", "Senga Glass Ink", "Senga Glass Wash", "Senga Glass View",
                "Senga Glass Normal", "Senga Glass Normal AOV", "Senga Glass Ink RGB")


def _glass_aovs(nt):
    """Glass keeps its own shader; it is drawn as an outline plus a little tone at the grazing rim,
    the way illustrators draw glass (and it no longer reads as an empty black hole in the compositor)."""
    out = _output_node(nt)
    x, y = (out.location.x, out.location.y) if out else (300, 0)
    N, L = nt.nodes, nt.links

    def node(idn, name, dx, dy):
        n = N.get(name) or N.new(idn)
        n.name = n.label = name
        n.location = (x + dx, y + dy)
        return n
    lw = node("ShaderNodeLayerWeight", "Senga Glass Rim", -600, -300)
    lw.inputs["Blend"].default_value = 0.35
    rr = node("ShaderNodeMapRange", "Senga Glass Ramp", -420, -300)
    rr.inputs["From Min"].default_value = 0.35; rr.inputs["From Max"].default_value = 0.95
    rr.inputs["To Max"].default_value = 0.55
    L.new(lw.outputs["Facing"], rr.inputs["Value"])
    rgb = node("ShaderNodeCombineColor", "Senga Glass Ink RGB", -240, -300)
    L.new(rr.outputs["Result"], rgb.inputs[0])
    ai = node("ShaderNodeOutputAOV", "Senga Glass Ink", 0, -300); ai.aov_name = AOV_COVER
    L.new(rgb.outputs[0], ai.inputs["Color"])
    aw = node("ShaderNodeOutputAOV", "Senga Glass Wash", 0, -440); aw.aov_name = AOV_WASH
    aw.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    geo = node("ShaderNodeNewGeometry", "Senga Glass Normal", -600, -560)
    vt = node("ShaderNodeVectorTransform", "Senga Glass View", -420, -560)
    vt.vector_type = "NORMAL"; vt.convert_from = "WORLD"; vt.convert_to = "CAMERA"
    L.new(geo.outputs["Normal"], vt.inputs[0])
    an = node("ShaderNodeOutputAOV", "Senga Glass Normal AOV", 0, -580); an.aov_name = AOV_NORMAL
    L.new(vt.outputs[0], an.inputs["Color"])


def _remove_glass_aovs(mat):
    nt = mat.node_tree
    if nt is None:
        return
    for n in list(nt.nodes):
        if n.name in _GLASS_NODES:
            nt.nodes.remove(n)
    if TAG + "_glass" in mat:
        del mat[TAG + "_glass"]


def revert_material(mat):
    if mat and mat.get(TAG + "_glass"):
        _remove_glass_aovs(mat)
        return False
    if not mat or not mat.get(TAG):
        return False
    nt = mat.node_tree
    out = nt.nodes.get(mat.get(TAG + "_out_node", "")) or _output_node(nt)
    on = nt.nodes.get(mat.get(TAG + "_orig_node", ""))
    if out and on:
        s = next((s for s in on.outputs if s.identifier == mat.get(TAG + "_orig_sock")), on.outputs[0])
        nt.links.new(s, out.inputs["Surface"])
    for n in list(nt.nodes):
        base = n.name.rsplit(".", 1)[0] if n.name[-4:-3] == "." and n.name[-3:].isdigit() else n.name
        if (n.type == "GROUP" and n.node_tree and n.node_tree.name == SHADE_GROUP) or base in _HELPERS:
            nt.nodes.remove(n)
    for k in (TAG, TAG + "_orig_node", TAG + "_orig_sock", TAG + "_out_node"):
        if k in mat:
            del mat[k]
    return True


# --------------------------------------------------------------------------
def apply_shade_settings(scene):
    """Settings are read inside the shader; only the baked fallbacks are refreshed here."""
    ng = bpy.data.node_groups.get(SHADE_GROUP)
    s = getattr(scene, "senga", None)
    if ng and s:
        for n in ng.nodes:
            prop = n.get("senga_prop")
            if prop and hasattr(s, prop):
                v = getattr(s, prop)
                if n.type == "RGB":
                    n.outputs[0].default_value = tuple(v)[:3] + (1.0,)
                else:
                    n.outputs[0].default_value = float(v)
    for m in sketch_materials():
        m.node_tree.update_tag()
    scene.update_tag()


def sketch_materials():
    return [m for m in bpy.data.materials if m.get(TAG) and m.node_tree]
