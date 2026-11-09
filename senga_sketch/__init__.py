# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
# Additional term (GPLv3 section 7(b)), see NOTICE.md: if you convey this add-on or a work based on it,
# keep this attribution in its description and documentation:
#   Senga Sketch by KanaWorks_AI (@KanaWorks_AI) — https://github.com/kanaworksai-hue/senga-sketch
"""Senga Sketch — turn any 3D scene into a hand-inked drawing (Blender 5.x, EEVEE).

  1. Sketch material : graphite tone from light x albedo, hand-wobbled hatching that thickens
                       with darkness (screen-space or following the form), cross / deep hatching,
                       screentone dots or stipple, solid blacks with dry-brush edges, colour wash.
  2. Outline         : Geometry-Nodes inverted hull, constant screen width, pen-pressure breakup,
                       boil on twos, heavier on the side away from the light.
  3. Compositor      : contour lines from normal + depth (interior creases), paper tooth, smudge,
                       unfinished-edge fade, any ink on any paper (incl. chalk on dark paper).
"""

bl_info = {
    "name": "Senga Sketch",
    "author": "Tokyo AI Visuals LLC (KanaWorks_AI)",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Sidebar (N) > Senga",
    "description": "Hand-inked sketch look: hatching, ink outlines, contour lines and paper in one click",
    "category": "Render",
}

import math as _m
import random

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty)

from . import shade, outline, post, autosetup, i18n
from .util import TAG, SHADE_GROUP, OUTLINE_MAT, OUTLINE_MOD, srgb

sketch_materials = shade.sketch_materials


# --------------------------------------------------------------------------
# update callbacks
# --------------------------------------------------------------------------
def _scene(self):
    return self.id_data if isinstance(self.id_data, bpy.types.Scene) else bpy.context.scene


def _upd_shade(self, context):
    if not self.get("_lock"):
        shade.apply_shade_settings(_scene(self))


def _upd_outline(self, context):
    if not self.get("_lock"):
        outline.apply_outline_settings(_scene(self))


def _upd_post(self, context):
    if not self.get("_lock"):
        post.apply_post_settings(_scene(self))


def _upd_shade_post(self, context):
    _upd_shade(self, context)
    _upd_post(self, context)


def _upd_pattern(self, context):
    self.pattern_id = {"LINES": 0.0, "DOTS": 1.0, "STIPPLE": 2.0}.get(self.pattern, 0.0)
    self.fade_bottom = 1.0 if self.fade_mode == "BOTTOM" else 0.0


def _upd_fade_mode(self, context):
    _upd_pattern(self, context)
    _upd_shade(self, context)
    _upd_post(self, context)


def _upd_key(self, context):
    link_key_light(_scene(self))
    _upd_outline(self, context)


def _upd_pattern_shade(self, context):
    _upd_pattern(self, context)
    _upd_shade(self, context)


def _upd_hatch_boil(self, context):
    link_boil(_scene(self))


def _upd_boil(self, context):
    _upd_outline(self, context)
    link_boil(_scene(self))


def _upd_obj(self, context):
    sc = context.scene
    shade.apply_shade_settings(sc)
    outline.apply_outline_settings(sc)


def _col(name, hexv, upd, desc=""):
    return FloatVectorProperty(name=name, subtype="COLOR", size=3, min=0, max=1,
                               default=srgb(hexv), update=upd, description=desc)


# --------------------------------------------------------------------------
# media: how the drawing is made. Every medium sets the same technique keys,
# so switching back and forth is lossless. Papers (below) set colour keys only.
# --------------------------------------------------------------------------
_PEN = dict(
    pattern="LINES", hatch_form=0.0, hatch_spacing=0.005, hatch_width=0.45, hatch_wobble=0.45,
    wobble_scale=6.0, hatch_breakup=0.45, hatch_start=0.3, cross_start=0.6, deep_start=0.8,
    cross_angle=_m.radians(72.0), hatch_amount=1.0, tone_steps=0.0,
    fill_strength=0.55, fill_start=0.32, fill_texture=0.15,
    solid_amount=1.0, solid_start=0.72, dry_brush=0.6,
    cel_amount=0.3, softness=0.12, shadow_floor=0.45,
    albedo_influence=0.9, albedo_black=0.08, albedo_white=0.66, albedo_floor=0.08, gloss=0.6, white_lines=0.85,
    line_width=1.5, line_opacity=1.0, outline_jitter=0.7, line_light_weight=0.7,
    contour_strength=1.0, contour_width=1.0, contour_wobble=1.5, contour_breakup=0.3,
    contour_normal=0.75, contour_depth=0.05,
    paper_tooth=0.05, smudge=0.0, smudge_size=6.0, wet_edges=0.0,
    fade_mode="RADIAL", edge_fade=0.0, edge_fade_start=0.9,
)
MEDIA = {
    "PEN": dict(_PEN),
    "PENCIL": {**_PEN, **dict(hatch_spacing=0.0042, hatch_width=0.5, hatch_wobble=0.5, hatch_breakup=0.55,
                              hatch_start=0.3, cross_start=0.62, deep_start=0.86, fill_strength=0.6,
                              fill_start=0.2, fill_texture=0.9, solid_amount=0.75, solid_start=0.76,
                              dry_brush=1.0, cel_amount=0.0, shadow_floor=0.4, albedo_floor=0.08, gloss=0.0,
                              line_width=1.0, line_opacity=0.7, outline_jitter=0.85, line_light_weight=0.7,
                              contour_strength=0.75, contour_width=0.9, contour_wobble=2.0, contour_breakup=0.45,
                              paper_tooth=0.6, smudge=0.25, smudge_size=5.0, edge_fade=0.6, edge_fade_start=0.85)},
    "CHARCOAL": {**_PEN, **dict(hatch_spacing=0.016, hatch_width=0.95, hatch_wobble=0.5, wobble_scale=3.0,
                                hatch_breakup=0.6, hatch_start=0.4, cross_start=0.75, deep_start=0.98,
                                hatch_amount=0.5, fill_strength=1.0, fill_start=0.0, fill_texture=0.8,
                                solid_amount=1.0, solid_start=0.62, dry_brush=1.6, cel_amount=0.2, gloss=0.0,
                                shadow_floor=0.25, albedo_floor=0.08, line_width=1.1, line_opacity=0.9,
                                outline_jitter=1.0, line_light_weight=0.5, contour_strength=0.15, contour_width=2.2,
                                contour_wobble=3.0, contour_breakup=0.55, paper_tooth=0.85, smudge=0.6,
                                smudge_size=12.0, wet_edges=0.1, edge_fade=0.7, edge_fade_start=0.85)},
    "BALLPOINT": {**_PEN, **dict(hatch_spacing=0.0042, hatch_width=0.42, hatch_wobble=0.5, wobble_scale=8.0,
                                 hatch_breakup=0.3, hatch_start=0.22, cross_start=0.42, deep_start=0.62,
                                 cross_angle=_m.radians(90.0), fill_strength=0.0, solid_amount=0.8, solid_start=0.8,
                                 cel_amount=0.0, shadow_floor=0.42, albedo_floor=0.08, gloss=0.0, line_width=0.95,
                                 outline_jitter=0.9, line_light_weight=0.5, contour_width=0.8,
                                 contour_wobble=2.2, contour_breakup=0.2, paper_tooth=0.0, edge_fade=0.35)},
    "INK_WASH": {**_PEN, **dict(hatch_amount=0.0, tone_steps=3.0, albedo_floor=0.1, white_lines=0.6, gloss=0.0,
                                fill_strength=0.9, fill_start=0.12, fill_texture=0.25, solid_amount=1.0,
                                solid_start=0.74, dry_brush=1.6, cel_amount=0.4, softness=0.2, shadow_floor=0.45,
                                line_width=2.2, outline_jitter=1.0, line_light_weight=0.9, contour_strength=0.6,
                                contour_width=2.0, contour_wobble=3.0, contour_breakup=0.5, paper_tooth=0.2,
                                smudge=0.3, smudge_size=6.0, wet_edges=1.0, edge_fade=0.5)},
    "ENGRAVING": {**_PEN, **dict(hatch_form=1.0, hatch_spacing=0.0075, hatch_width=0.8, hatch_wobble=0.03,
                                 wobble_scale=3.0, hatch_breakup=0.03, hatch_start=0.2, cross_start=0.6,
                                 deep_start=0.85, cross_angle=_m.radians(80.0), fill_strength=0.0, albedo_floor=0.1,
                                 solid_amount=0.9, solid_start=0.76, dry_brush=0.0, cel_amount=0.0, gloss=0.0,
                                 white_lines=0.0, shadow_floor=0.3, line_width=1.2, outline_jitter=0.2, line_light_weight=0.5,
                                 contour_wobble=0.4, contour_breakup=0.0, paper_tooth=0.0)},
    "SCREENTONE": {**_PEN, **dict(pattern="DOTS", tone_steps=3.0, albedo_floor=0.1, albedo_influence=0.35, gloss=0.0,
                                  hatch_spacing=0.0068,
                                  hatch_start=0.25, hatch_wobble=0.0, hatch_breakup=0.0, fill_strength=0.0,
                                  solid_amount=1.0, solid_start=0.68, dry_brush=0.4, cel_amount=0.9, softness=0.03,
                                  shadow_floor=0.45, outline_jitter=0.5, contour_wobble=0.8,
                                  contour_breakup=0.1, paper_tooth=0.0)},
    "STIPPLE": {**_PEN, **dict(pattern="STIPPLE", albedo_floor=0.08, gloss=0.0, hatch_spacing=0.005, hatch_start=0.4,
                               hatch_wobble=0.0, hatch_breakup=0.0, fill_strength=0.0, solid_amount=0.8,
                               solid_start=0.82, dry_brush=0.0, cel_amount=0.0, shadow_floor=0.3, line_width=0.8,
                               outline_jitter=0.6, contour_breakup=0.25, paper_tooth=0.0, edge_fade=0.3)},
}

# papers: colour and mood only
PAPERS = {
    "SKETCHBOOK": dict(paper_color=srgb("#F7F4EC"), paper_texture=0.25, ink_color=srgb("#141418"),
                       rule_lines=0.0, chalk=0.0, wash_amount=0.0, tone_invert=0.0, paper_marks=1.0, grain=0.03,
                       vignette=0.12),
    "SEPIA": dict(paper_color=srgb("#F1E4C8"), paper_texture=0.35, ink_color=srgb("#3A2416"),
                  rule_lines=0.0, chalk=0.0, wash_amount=0.0, tone_invert=0.0, paper_marks=1.0, grain=0.04,
                  vignette=0.22),
    "KRAFT": dict(paper_color=srgb("#B89A72"), paper_texture=0.4, ink_color=srgb("#1E1712"),
                  rule_lines=0.0, chalk=0.85, chalk_color=srgb("#FFF8EC"), highlight_threshold=0.8,
                  wash_amount=0.0, tone_invert=0.0, paper_marks=1.0, grain=0.05, vignette=0.2),
    "TONED_GREY": dict(paper_color=srgb("#8E9196"), paper_texture=0.3, ink_color=srgb("#121318"),
                       rule_lines=0.0, chalk=0.85, chalk_color=srgb("#FFFFFF"), highlight_threshold=0.8,
                       wash_amount=0.0, tone_invert=0.0, paper_marks=1.0, grain=0.04, vignette=0.18),
    "NOTEBOOK": dict(paper_color=srgb("#FAFAF6"), paper_texture=0.15, ink_color=srgb("#1C2C8C"),
                     rule_lines=0.55, rule_color=srgb("#7FA6D9"), rule_spacing=46.0, chalk=0.0,
                     wash_amount=0.0, tone_invert=0.0, paper_marks=1.0, grain=0.025, vignette=0.08),
    "BLUEPRINT": dict(paper_color=srgb("#1D4E8F"), paper_texture=0.3, ink_color=srgb("#EAF2FF"),
                      rule_lines=0.25, rule_color=srgb("#3E73B8"), rule_spacing=38.0, chalk=0.0,
                      wash_amount=0.0, tone_invert=1.0, paper_marks=0.0, grain=0.03, vignette=0.25),
    "CHALKBOARD": dict(paper_color=srgb("#23302A"), paper_texture=0.45, ink_color=srgb("#F2F0E6"),
                       rule_lines=0.0, chalk=0.0, wash_amount=0.0, tone_invert=1.0, paper_marks=0.75, grain=0.05,
                       vignette=0.3),
    "WATERCOLOUR": dict(paper_color=srgb("#FBF8F1"), paper_texture=0.4, ink_color=srgb("#2A2026"),
                        rule_lines=0.0, chalk=0.0, wash_amount=0.55, wash_saturation=0.85, tone_invert=0.0,
                        paper_marks=1.0, grain=0.03, vignette=0.1),
}

# --------------------------------------------------------------------------
# variation: a seed re-rolls hatch angle, spacing, wobble, breakup, edge fade and
# a nearby paper shade around the current medium + paper. 0 = off.
# --------------------------------------------------------------------------
VARY_KEYS = ("seed", "hatch_angle", "cross_angle", "hatch_spacing", "hatch_wobble", "wobble_scale",
             "hatch_breakup", "outline_jitter", "outline_jitter_scale", "contour_wobble", "edge_fade_start",
             "paper_color", "ink_color")
_BASE = "_var_base"


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _restore_base(s):
    base = s.get(_BASE)
    if base is None:
        return
    for k in VARY_KEYS:
        if k in base:
            v = base[k]
            setattr(s, k, tuple(v) if hasattr(v, "__len__") else v)
    del s[_BASE]


def _vary(s):
    if s.variation == 0:
        _restore_base(s)
        return
    if s.get(_BASE) is None or any(k not in s[_BASE] for k in VARY_KEYS):
        s[_BASE] = {k: (list(getattr(s, k)) if k in ("paper_color", "ink_color") else getattr(s, k))
                    for k in VARY_KEYS}
    b = {k: (tuple(v) if hasattr(v, "__len__") else v) for k, v in s[_BASE].items()}
    r = random.Random(s.variation * 7919 + 23)
    s.seed = b["seed"] + s.variation * 3.17
    # hand-drawn hatching leans the way the hand moves: mostly 20-65 deg, either side
    s.hatch_angle = r.choice((-1.0, 1.0)) * _m.radians(r.uniform(18.0, 66.0))
    s.cross_angle = _m.radians(r.uniform(55.0, 95.0))
    s.hatch_spacing = _clamp(b["hatch_spacing"] * r.uniform(0.8, 1.3), 0.002, 0.05)
    s.hatch_wobble = _clamp(b["hatch_wobble"] * r.uniform(0.6, 1.6) + (r.uniform(0.0, 0.06) if b["hatch_wobble"] else 0), 0.0, 1.0)
    s.wobble_scale = _clamp(b["wobble_scale"] * r.uniform(0.7, 1.5), 0.5, 30.0)
    s.hatch_breakup = _clamp(b["hatch_breakup"] + r.uniform(-0.15, 0.2), 0.0, 1.0)
    s.outline_jitter = _clamp(b["outline_jitter"] + r.uniform(-0.2, 0.2), 0.0, 1.0)
    s.outline_jitter_scale = _clamp(b["outline_jitter_scale"] * r.uniform(0.6, 1.6), 0.1, 100.0)
    s.contour_wobble = _clamp(b["contour_wobble"] * r.uniform(0.6, 1.5), 0.0, 12.0)
    s.edge_fade_start = _clamp(b["edge_fade_start"] + r.uniform(-0.12, 0.08), 0.2, 1.5)
    # a nearby paper shade and ink tone (never a different hue family: the paper defines the look)
    pv, iv = r.uniform(0.92, 1.04), r.uniform(0.85, 1.25)
    s.paper_color = tuple(_clamp(c * pv + r.uniform(-0.015, 0.015), 0.0, 1.0) for c in b["paper_color"])
    s.ink_color = tuple(_clamp(c * iv, 0.0, 1.0) for c in b["ink_color"])


def _apply_all(sc):
    shade.apply_shade_settings(sc)
    outline.apply_outline_settings(sc)
    post.apply_post_settings(sc)


def _locked(sc, fn):
    s = sc.senga
    s["_lock"] = True
    try:
        fn(s)
    finally:
        s["_lock"] = False
    _upd_pattern(s, None)
    _apply_all(sc)


def apply_medium(self, context):
    def go(s):
        _restore_base(s)
        for k, v in MEDIA.get(s.medium, {}).items():
            setattr(s, k, v)
        _vary(s)
    _locked(_scene(self), go)


def apply_paper(self, context):
    def go(s):
        _restore_base(s)
        for k, v in PAPERS.get(s.paper, {}).items():
            setattr(s, k, v)
        _vary(s)
    _locked(_scene(self), go)


def apply_variation(self, context):
    if not self.get("_lock"):
        _locked(_scene(self), _vary)


MEDIUM_ITEMS = [
    ("PEN", "Manga Pen", "G-pen ink: hand hatching that thickens in shadow, solid blacks, light graphite (default)"),
    ("PENCIL", "Graphite Pencil", "Soft graphite shading, fine hatching, paper tooth and smudging"),
    ("CHARCOAL", "Charcoal", "Heavy smudged blacks, coarse strokes, rough paper"),
    ("BALLPOINT", "Ballpoint", "Thin crossing lines only, like a pen sketch in a notebook"),
    ("INK_WASH", "Sumi Ink Wash", "Brush outlines and grey ink washes, no hatching"),
    ("ENGRAVING", "Engraving", "Fine lines that follow the form, like an etching or banknote"),
    ("SCREENTONE", "Manga Screentone", "Clean ink lines with halftone-dot shading"),
    ("STIPPLE", "Stipple", "Shading built from thousands of ink dots"),
]
PAPER_ITEMS = [
    ("SKETCHBOOK", "Sketchbook", "Warm white paper, near-black ink (default)"),
    ("SEPIA", "Sepia on Cream", "Brown ink on cream paper, like an old study"),
    ("KRAFT", "Kraft + White Chalk", "Dark ink and white chalk highlights on brown paper"),
    ("TONED_GREY", "Toned Grey + Chalk", "Dark ink and white chalk highlights on grey paper"),
    ("NOTEBOOK", "Notebook", "Blue ballpoint ink on ruled notebook paper"),
    ("BLUEPRINT", "Blueprint", "White lines on blueprint blue"),
    ("CHALKBOARD", "Chalkboard", "Chalk lines on a green-black board"),
    ("WATERCOLOUR", "Ink + Watercolour", "Ink drawing with a light watercolour tint of the model's colours"),
]


class SENGA_Settings(bpy.types.PropertyGroup):
    alive: BoolProperty(name="Add-on Loaded", default=True,
                        description="Read by the shader; missing when the add-on is not installed, "
                                    "so materials fall back to baked values")
    medium: EnumProperty(name="Drawing Medium", default="PEN", update=apply_medium, items=MEDIUM_ITEMS)
    paper: EnumProperty(name="Paper", default="SKETCHBOOK", update=apply_paper, items=PAPER_ITEMS)
    variation: IntProperty(name="Variation", default=0, min=0, max=99999, update=apply_variation,
                           description="Re-rolls hatch angle, spacing, wobble, line breakup, edge fade and paper "
                                       "shade around the current medium and paper. 0 = off")
    only_selected: BoolProperty(name="Selected Objects Only", default=False,
                                description="Make It Senga only converts the selected objects")
    auto_key_light: BoolProperty(name="Add Key Light if Missing", default=True,
                                 description="Add a Sun aimed from the camera side when the scene has no light "
                                             "(removed again by Revert)")
    auto_fit: BoolProperty(name="Fit to Scene Scale", default=True,
                           description="Set form-hatch spacing and outline fade from object size and camera distance")
    # light / tone
    key_light: PointerProperty(name="Key Light", type=bpy.types.Object,
                               poll=lambda self, o: o.type == "LIGHT",
                               description="Light the tone is measured against (drives Light Scale) and the "
                                           "light the outlines thicken away from",
                               update=_upd_key)
    light_scale: FloatProperty(name="Light Scale", default=1.0, min=0.001, soft_max=50,
                               description="Key light strength x brightest colour channel (driven by Key Light)",
                               update=_upd_shade)
    ambient_level: FloatProperty(name="Ambient Compensation", default=0.0, min=0, soft_max=10,
                                 description="World fill removed before the tone is measured, so bright worlds "
                                             "keep their shadows (estimated by Setup Render)", update=_upd_shade)
    threshold: FloatProperty(name="Shadow Threshold", default=0.45, min=0, max=2, update=_upd_shade,
                             description="Light level where the shadow side starts")
    softness: FloatProperty(name="Shadow Softness", default=0.12, min=0.001, max=0.5, update=_upd_shade)
    cel_amount: FloatProperty(name="Cel Shading", default=0.3, min=0, max=1, update=_upd_shade,
                              description="0 = soft graphite gradient, 1 = hard light/shadow split")
    shadow_floor: FloatProperty(name="Shadow Lightness", default=0.45, min=0, max=1, update=_upd_shade,
                                description="How light the darkest shadow stays")
    brightness: FloatProperty(name="Brightness", default=1.0, min=0, max=3, update=_upd_shade,
                              description="Lighter drawing = less ink overall")
    albedo_influence: FloatProperty(name="Texture Values", default=0.9, min=0, max=1, update=_upd_shade,
                                    description="How much the model's own colours turn into tone "
                                                "(dark hair -> black ink). 0 = lighting only")
    albedo_floor: FloatProperty(name="Dark Texture Lift", default=0.08, min=0, max=1, update=_upd_shade,
                                description="Black textures still show light and shadow: their lit side is "
                                            "hatched instead of solid ink")
    gloss: FloatProperty(name="Gloss Highlights", default=0.6, min=0, max=2, update=_upd_shade,
                         description="Leave white streaks where the key light reflects (glossy and black objects)")
    albedo_black: FloatProperty(name="Texture Black Point", default=0.08, min=0, max=1, update=_upd_shade)
    albedo_white: FloatProperty(name="Texture White Point", default=0.66, min=0, max=1, update=_upd_shade)
    # graphite fill / solid blacks
    fill_strength: FloatProperty(name="Graphite Fill", default=0.55, min=0, max=1, update=_upd_shade,
                                 description="Soft grey shading under the lines")
    fill_start: FloatProperty(name="Fill Start", default=0.32, min=0, max=1, update=_upd_shade)
    fill_texture: FloatProperty(name="Fill Strokes", default=0.15, min=0, max=1, update=_upd_shade,
                                description="Directional stroke texture inside the fill")
    solid_amount: FloatProperty(name="Solid Blacks", default=1.0, min=0, max=1, update=_upd_shade,
                                description="Fill the darkest areas (hair, deep shadow) with solid ink")
    solid_start: FloatProperty(name="Solid Black Start", default=0.72, min=0, max=1, update=_upd_shade)
    dry_brush: FloatProperty(name="Dry Brush Edge", default=0.6, min=0, max=3, update=_upd_shade,
                             description="Streaky, broken edge where solid black meets the hatching")
    # hatching
    pattern: EnumProperty(name="Pattern", default="LINES", update=_upd_pattern_shade,
                          items=[("LINES", "Hatching", "Parallel hand-drawn lines, crossing in darker areas"),
                                 ("DOTS", "Screentone", "Halftone dots"),
                                 ("STIPPLE", "Stipple", "Randomly placed dots")])
    pattern_id: FloatProperty(name="Pattern ID", default=0.0, options={"HIDDEN"})
    fade_bottom: FloatProperty(name="Fade Bottom", default=0.0, options={"HIDDEN"})
    hatch_amount: FloatProperty(name="Hatching", default=1.0, min=0, max=1, update=_upd_shade)
    hatch_start: FloatProperty(name="Hatch Start", default=0.3, min=0, max=1, update=_upd_shade,
                               description="Tone where the first lines appear (lower = more lines)")
    cross_start: FloatProperty(name="Cross-hatch Start", default=0.6, min=0, max=1.5, update=_upd_shade)
    deep_start: FloatProperty(name="Deep Hatch Start", default=0.8, min=0, max=1.5, update=_upd_shade)
    hatch_spacing: FloatProperty(name="Line Spacing", default=0.005, min=0.001, max=0.1, precision=4, step=0.01,
                                 update=_upd_shade, description="Distance between hatch lines, as a fraction of "
                                                                "the image height (resolution independent)")
    hatch_width: FloatProperty(name="Hatch Weight", default=0.45, min=0.05, max=1, update=_upd_shade,
                               description="Widest line, as a fraction of the spacing")
    hatch_angle: FloatProperty(name="Hatch Angle", subtype="ANGLE", default=_m.radians(35.0),
                               min=-_m.pi, max=_m.pi, update=_upd_shade_post)
    cross_angle: FloatProperty(name="Cross Angle", subtype="ANGLE", default=_m.radians(72.0),
                               min=0, max=_m.pi, update=_upd_shade)
    hatch_wobble: FloatProperty(name="Hand Wobble", default=0.45, min=0, max=1, update=_upd_shade)
    wobble_scale: FloatProperty(name="Wobble Scale", default=6.0, min=0.1, max=50, update=_upd_shade)
    hatch_breakup: FloatProperty(name="Stroke Breakup", default=0.45, min=0, max=1, update=_upd_shade,
                                 description="Gaps and tapered ends along the lines")
    hatch_form: FloatProperty(name="Follow Form", default=0.0, min=0, max=2, update=_upd_shade,
                              description="0 = lines fixed on the screen like the reference drawing, "
                                          "1 = lines bend over the shape (engraving). Objects added later need "
                                          "Fit to Scene")
    tone_steps: FloatProperty(name="Tone Steps", default=0.0, min=0, max=8, step=100, precision=0, update=_upd_shade,
                              description="Quantise the shading into flat steps (sumi washes, two-level screentone). "
                                          "0 = smooth")
    paper_marks: FloatProperty(name="Shading Marks", default=1.0, min=0, max=1, update=_upd_shade,
                               description="How much shading and hatching the paper takes (blueprint: lines only)")
    seed: FloatProperty(name="Seed", default=0.0, update=_upd_shade)
    hatch_boil: BoolProperty(name="Hatch Boil", default=False, update=_upd_hatch_boil,
                             description="Re-draw the hatching on the boil rate (lively, but busier)")
    hatch_phase: FloatProperty(name="Hatch Phase", default=0.0,
                               description="Driven: floor(frame / boil rate) * 0.37 when Hatch Boil is on")
    # colour
    ink_color: _col("Ink Colour", "#141418", _upd_shade_post)
    wash_amount: FloatProperty(name="Colour Wash", default=0.0, min=0, max=1, update=_upd_shade,
                               description="Light watercolour tint of the model's own colours under the ink")
    wash_saturation: FloatProperty(name="Wash Saturation", default=1.0, min=0, max=2, update=_upd_shade)
    tone_invert: FloatProperty(name="Draw the Light", default=0.0, min=0, max=1, update=_upd_shade,
                               description="Marks describe the light instead of the shadow (chalk / blueprint "
                                           "on dark paper)")
    highlight_threshold: FloatProperty(name="Highlight Threshold", default=0.72, min=0, max=1, update=_upd_shade,
                                       description="Where white chalk highlights start (toned papers)")
    # outline
    outline_enable: BoolProperty(name="Outlines", default=True, update=_upd_outline)
    line_width: FloatProperty(name="Line Width", default=1.5, min=0, max=10, soft_max=4, update=_upd_outline,
                              description="Outline width. 1 = a fine pen nib; it stays the same on screen "
                                          "whatever the scene size")
    line_opacity: FloatProperty(name="Line Darkness", default=1.0, min=0, max=1, update=_upd_post,
                                description="Outlines and contour lines (pencil and charcoal draw them lighter)")
    outline_ref_distance: FloatProperty(name="Reference Distance", default=6.0, min=0.01, update=_upd_outline)
    outline_fade_distance: FloatProperty(name="Fade Distance", default=30.0, min=0.01, update=_upd_outline)
    outline_fade_min: FloatProperty(name="Far Width", default=0.35, min=0, max=1, update=_upd_outline)
    outline_jitter: FloatProperty(name="Pen Pressure", default=0.7, min=0, max=1, update=_upd_outline,
                                  description="Width breaks up along the line like a pen lifting")
    outline_jitter_scale: FloatProperty(name="Pressure Scale", default=6.0, min=0, max=100, update=_upd_outline)
    outline_boil: BoolProperty(name="Line Boil", default=True, update=_upd_outline)
    boil_rate: IntProperty(name="Boil Rate (frames)", default=2, min=1, max=12, update=_upd_boil)
    outline_weld: BoolProperty(name="Weld UV Seams", default=True, update=_upd_outline)
    line_light_weight: FloatProperty(name="Shadow-side Weight", default=0.7, min=0, max=1, update=_upd_outline,
                                     description="Lines get heavier on the side turned away from the key light")
    # contour lines (compositor)
    contour_enable: BoolProperty(name="Contour Lines", default=True, update=_upd_post,
                                 description="Inner lines found from creases and depth jumps")
    contour_strength: FloatProperty(name="Contour Strength", default=1.0, min=0, max=1, update=_upd_post)
    contour_normal: FloatProperty(name="Crease Threshold", default=0.75, min=0.01, max=2, update=_upd_post,
                                  description="Lower = more crease lines")
    contour_depth: FloatProperty(name="Depth Threshold", default=0.05, min=0.001, max=1, precision=3,
                                 update=_upd_post, description="Lower = more lines at depth jumps")
    contour_width: FloatProperty(name="Contour Width (px)", default=1.0, min=0.3, max=10, update=_upd_post)
    contour_wobble: FloatProperty(name="Contour Wobble (px)", default=1.5, min=0, max=12, update=_upd_post)
    contour_breakup: FloatProperty(name="Contour Breakup", default=0.3, min=0, max=1, update=_upd_post)
    white_lines: FloatProperty(name="White Lines in Blacks", default=0.85, min=0, max=1, update=_upd_post,
                               description="Contour lines inside solid black areas are scratched out in white, "
                                           "so black objects keep their shape")
    # paper
    paper_color: _col("Paper Colour", "#F7F4EC", _upd_post)
    paper_texture: FloatProperty(name="Paper Texture", default=0.25, min=0, max=1, update=_upd_post)
    paper_tooth: FloatProperty(name="Paper Tooth", default=0.05, min=0, max=1, update=_upd_post,
                               description="Paper grain breaks up light strokes (pencil, charcoal)")
    smudge: FloatProperty(name="Smudge", default=0.0, min=0, max=1, update=_upd_post)
    wet_edges: FloatProperty(name="Wet Edges", default=0.0, min=0, max=1, update=_upd_post,
                             description="Ink pools at the edge of each wash (sumi, watercolour)")
    smudge_size: FloatProperty(name="Smudge Size (px)", default=6.0, min=0.5, max=60, update=_upd_post)
    fade_mode: EnumProperty(name="Fade Shape", default="RADIAL", update=_upd_fade_mode, items=[
        ("RADIAL", "Vignette", "Fade towards every frame edge"),
        ("BOTTOM", "Bottom", "Fade towards the bottom, like a bust drawn on a page")])
    edge_fade: FloatProperty(name="Unfinished Edges", default=0.0, min=0, max=1, update=_upd_shade_post,
                             description="The drawing fades out in loose strokes: shading first, then lines")
    edge_fade_start: FloatProperty(name="Fade Start", default=0.9, min=0.1, max=2, update=_upd_shade_post,
                                   description="1 = the frame edge")
    rule_lines: FloatProperty(name="Ruled Lines", default=0.0, min=0, max=1, update=_upd_post)
    rule_spacing: FloatProperty(name="Rule Spacing (px)", default=46.0, min=4, max=400, update=_upd_post)
    rule_color: _col("Rule Colour", "#7FA6D9", _upd_post)
    chalk: FloatProperty(name="White Chalk", default=0.0, min=0, max=1, update=_upd_post,
                         description="White highlights on the lit side (toned paper)")
    chalk_color: _col("Chalk Colour", "#FFFFFF", _upd_post)
    grain: FloatProperty(name="Grain", default=0.03, min=0, max=1, update=_upd_post)
    vignette: FloatProperty(name="Vignette", default=0.12, min=0, max=1, update=_upd_post)


OBJ_KEYS = ("threshold", "shadow_floor", "brightness", "albedo_influence", "fill_strength", "solid_amount",
            "hatch_amount", "wash_amount", "gloss")


def _upd_use_override(self, context):
    if self.use_override and not self.get("_seeded"):
        s = context.scene.senga
        for k in OBJ_KEYS:
            setattr(self, k, getattr(s, k))
        self["_seeded"] = True
    _upd_obj(self, context)


class SENGA_ObjSettings(bpy.types.PropertyGroup):
    use_override: BoolProperty(name="Override", default=False, update=_upd_use_override)
    threshold: FloatProperty(name="Shadow Threshold", default=0.45, min=0, max=2, update=_upd_obj)
    shadow_floor: FloatProperty(name="Shadow Lightness", default=0.5, min=0, max=1, update=_upd_obj)
    brightness: FloatProperty(name="Brightness", default=1.0, min=0, max=3, update=_upd_obj)
    albedo_influence: FloatProperty(name="Texture Values", default=0.9, min=0, max=1, update=_upd_obj)
    fill_strength: FloatProperty(name="Graphite Fill", default=0.55, min=0, max=1, update=_upd_obj)
    solid_amount: FloatProperty(name="Solid Blacks", default=1.0, min=0, max=1, update=_upd_obj)
    hatch_amount: FloatProperty(name="Hatching", default=1.0, min=0, max=1, update=_upd_obj)
    wash_amount: FloatProperty(name="Colour Wash", default=0.0, min=0, max=1, update=_upd_obj)
    gloss: FloatProperty(name="Gloss Highlights", default=0.6, min=0, max=2, update=_upd_obj)
    outline_enable: BoolProperty(name="Outline", default=True, update=_upd_obj)
    outline_scale: FloatProperty(name="Line Width x", default=1.0, min=0, max=10, update=_upd_obj)


# --------------------------------------------------------------------------
# drivers (no frame/render handlers)
# --------------------------------------------------------------------------
def _driver_var(drv, name, id_type, idb, path):
    v = drv.variables.new()
    v.name = name
    v.type = "SINGLE_PROP"
    v.targets[0].id_type = id_type
    v.targets[0].id = idb
    v.targets[0].data_path = path


def link_key_light(scene):
    """Drive Light Scale from the key light (strength x brightest colour channel)."""
    s = scene.senga
    try:
        scene.driver_remove("senga.light_scale")
    except TypeError:
        pass
    key = s.key_light
    if key is None or key.type != "LIGHT":
        return
    fc = scene.driver_add("senga.light_scale")
    drv = fc.driver
    drv.type = "SCRIPTED"
    _driver_var(drv, "e", "LIGHT", key.data, "energy")
    for i, c in enumerate("rgb"):
        _driver_var(drv, c, "LIGHT", key.data, f"color[{i}]")
    k = 1.0
    if key.data.type != "SUN":
        c = autosetup.subject_centre(scene)
        k = autosetup.light_irradiance(key, c) / max(1e-9, key.data.energy * max(key.data.color))
    drv.expression = "e * max(max(r, g), b)" + (f" * {k:.6g}" if k != 1.0 else "")


def link_boil(scene):
    s = scene.senga
    try:
        scene.driver_remove("senga.hatch_phase")
    except TypeError:
        pass
    if not s.hatch_boil:
        s.hatch_phase = 0.0
        return
    fc = scene.driver_add("senga.hatch_phase")
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = f"floor(frame / {max(1, s.boil_rate)}) * 0.37"


def revalidate_drivers(*_):
    """Drivers on senga.* are flagged invalid if a file loads before the add-on registers."""
    for sc in bpy.data.scenes:
        ad = sc.animation_data
        if ad:
            for fc in ad.drivers:
                if fc.data_path.startswith("senga."):
                    fc.driver.is_valid = True
                    fc.is_valid = True


# --------------------------------------------------------------------------
# operators
# --------------------------------------------------------------------------
SCOPE = EnumProperty(name="Scope", default="AUTO", options={"SKIP_SAVE", "HIDDEN"}, items=[
    ("AUTO", "Auto", "Selected objects, or all visible objects when nothing is selected"),
    ("ALL", "All Visible", "Every visible object"),
    ("SELECTED", "Selected", "Selected objects only")])


class SENGA_OT_setup_scene(bpy.types.Operator):
    bl_idname = "senga.setup_scene"
    bl_label = "Setup Render"
    bl_description = ("EEVEE, Standard view transform, transparent film (the paper is drawn by the compositor), "
                      "key light. Previous settings are restored by Revert")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        vs = sc.view_settings
        if TAG + "_prev_view" not in sc:
            sc[TAG + "_prev_view"] = vs.view_transform
            sc[TAG + "_prev_look"] = vs.look
            sc[TAG + "_prev_engine"] = sc.render.engine
            sc[TAG + "_prev_film"] = sc.render.film_transparent
        try:
            sc.render.engine = "BLENDER_EEVEE"
        except TypeError:
            sc.render.engine = "BLENDER_EEVEE_NEXT"
        vs.view_transform = "Standard"
        try:
            vs.look = "None"
        except TypeError:
            pass
        sc.render.film_transparent = True
        sc.eevee.use_shadows = True
        sc.eevee.taa_render_samples = max(sc.eevee.taa_render_samples, 48)
        sc.render.compositor_device = "GPU"
        sc.render.use_lock_interface = True
        s = sc.senga
        key = s.key_light
        if key is None or key.name not in sc.objects:
            sun = None
            if s.auto_key_light:
                sun, made = autosetup.ensure_key_sun(sc)
                if made:
                    self.report({"INFO"}, i18n.report("No light in the scene: added 'Senga Key Sun'"))
            sun = sun or autosetup.pick_key(sc, autosetup.subject_centre(sc))
            if sun:
                s.key_light = sun
        else:
            link_key_light(sc)
        link_boil(sc)
        s.ambient_level = autosetup.estimate_ambient(sc)
        sp = context.space_data
        if sp and sp.type == "VIEW_3D":
            sp.shading.type = "RENDERED"
            sp.shading.use_compositor = "CAMERA"
        self.report({"INFO"}, i18n.report(f"Render ready (Light Scale {s.light_scale:.2f})"))
        return {"FINISHED"}


class SENGA_OT_sketchify(bpy.types.Operator):
    bl_idname = "senga.sketchify"
    bl_label = "Apply Sketch Shader"
    bl_description = "Convert the materials of the selected objects (or all visible) to the sketch shader"
    bl_options = {"REGISTER", "UNDO"}
    scope: SCOPE

    def execute(self, context):
        objs = autosetup.targets(context, self.scope)
        made = autosetup.ensure_materials(objs)
        n = sum(shade.sketchify_material(m) for m in autosetup.materials_of(objs))
        shade.apply_shade_settings(context.scene)
        extra = f" ({made} object(s) had no material)" if made else ""
        self.report({"INFO"}, i18n.report(f"Sketch shader on {n} material(s){extra}"))
        return {"FINISHED"}


class SENGA_OT_outline(bpy.types.Operator):
    bl_idname = "senga.outline"
    bl_label = "Add Ink Outlines"
    bl_description = "Add hand-inked outlines (flat ground planes are skipped)"
    bl_options = {"REGISTER", "UNDO"}
    scope: SCOPE

    def execute(self, context):
        objs = autosetup.outline_targets(autosetup.targets(context, self.scope))
        n = sum(outline.add_outline(o, context.scene) for o in objs)
        self.report({"INFO"}, i18n.report(f"Outline on {n} object(s)"))
        return {"FINISHED"}


class SENGA_OT_post(bpy.types.Operator):
    bl_idname = "senga.post"
    bl_label = "Build Paper & Contours"
    bl_description = "Create the sketch compositor (the previous compositor is remembered for Revert)"
    bl_options = {"REGISTER", "UNDO"}
    rebuild: BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        post.build_post(context.scene, rebuild=self.rebuild)
        return {"FINISHED"}


class SENGA_OT_revert(bpy.types.Operator):
    bl_idname = "senga.revert"
    bl_label = "Revert Sketch"
    bl_description = ("Restore original materials, remove outlines and restore compositor / render settings "
                      "(whole scene, or only the selection when 'Selected Objects Only' is on)")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        full = not sc.senga.only_selected
        objs = autosetup.all_targets(sc) if full else autosetup.targets(context, "SELECTED")
        n = sum(shade.revert_material(m) for m in autosetup.materials_of(objs))
        for o in objs:
            if o.type == "MESH":
                outline.remove_outline(o)
            if not o.is_editable:
                continue
            for k in (TAG + "_radius", TAG + "_centre"):
                if k in o:
                    del o[k]
            for s in o.material_slots:
                if s.link == "OBJECT" and s.material and s.material.get(TAG + "_auto"):
                    s.material = None
            if getattr(o.data, "library", None):
                continue
            mats = o.data.materials
            for i in reversed(range(len(mats))):
                if mats[i] and mats[i].get(TAG + "_auto"):
                    if len(mats) == 1:
                        mats.pop(index=i)
                    else:
                        mats[i] = None
        if full:
            post.remove_post(sc)
            for path in ("senga.light_scale", "senga.hatch_phase"):
                try:
                    sc.driver_remove(path)
                except TypeError:
                    pass
            if TAG + "_prev_view" in sc:
                sc.view_settings.view_transform = sc[TAG + "_prev_view"]
                try:
                    sc.view_settings.look = sc[TAG + "_prev_look"]
                except TypeError:
                    pass
                del sc[TAG + "_prev_view"], sc[TAG + "_prev_look"]
            if TAG + "_prev_film" in sc:
                sc.render.film_transparent = bool(sc[TAG + "_prev_film"])
                del sc[TAG + "_prev_film"]
            if TAG + "_prev_engine" in sc:
                try:
                    sc.render.engine = sc[TAG + "_prev_engine"]
                except TypeError:
                    pass
                del sc[TAG + "_prev_engine"]
            for o in [o for o in sc.objects if o.type == "LIGHT" and o.get(TAG + "_auto")]:
                if sc.senga.key_light == o:
                    sc.senga.key_light = None
                ld = o.data
                bpy.data.objects.remove(o)
                if ld.users == 0:
                    bpy.data.lights.remove(ld)
        self.report({"INFO"}, i18n.report(f"Reverted {n} material(s)"))
        return {"FINISHED"}


class SENGA_OT_reset(bpy.types.Operator):
    bl_idname = "senga.reset"
    bl_label = "Reset to Defaults"
    bl_description = "Every setting back to its default (Manga Pen on Sketchbook paper)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        s = sc.senga
        s["_lock"] = True
        try:
            if _BASE in s:
                del s[_BASE]
            keep = ("rna_type", "key_light", "light_scale", "hatch_phase", "ambient_level",
                    "outline_ref_distance", "outline_fade_distance")
            for name, prop in s.bl_rna.properties.items():
                if name in keep or prop.is_readonly:
                    continue
                if prop.type == "ENUM":
                    setattr(s, name, prop.default)
                elif getattr(prop, "is_array", False):
                    setattr(s, name, tuple(prop.default_array))
                elif hasattr(prop, "default"):
                    setattr(s, name, prop.default)
        finally:
            s["_lock"] = False
        _upd_pattern(s, None)
        link_boil(sc)
        _apply_all(sc)
        return {"FINISHED"}


class SENGA_OT_shuffle(bpy.types.Operator):
    bl_idname = "senga.shuffle"
    bl_label = "Shuffle"
    bl_description = ("New variation: hatch angle, spacing, wobble, line breakup, edge fade and paper shade "
                      "are re-rolled around the current medium and paper")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.senga
        v = s.variation
        while v == s.variation:
            v = random.randint(1, 9999)
        s.variation = v
        self.report({"INFO"}, i18n.report(f"Variation {v}"))
        return {"FINISHED"}


class SENGA_OT_all(bpy.types.Operator):
    bl_idname = "senga.apply_all"
    bl_label = "Make It Senga"
    bl_description = ("Setup render, sketch shader, ink outlines, contour lines and paper in one click "
                      "(whole scene, or only the selection when 'Selected Objects Only' is on)")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        scope = "SELECTED" if sc.senga.only_selected else "ALL"
        objs = autosetup.targets(context, scope)
        if not objs:
            self.report({"WARNING"}, i18n.report("Nothing to draw: add or select a mesh, curve or text object"))
            return {"CANCELLED"}
        bpy.ops.senga.setup_scene()
        bpy.ops.senga.sketchify(scope=scope)
        autosetup.store_radii(objs)
        bpy.ops.senga.outline(scope=scope)
        if sc.senga.auto_fit:
            autosetup.fit_to_scene(sc, objs)
        bpy.ops.senga.post()
        _upd_pattern(sc.senga, None)
        _apply_all(sc)
        self.report({"INFO"}, i18n.report(f"Sketch look on {len(objs)} object(s)"))
        return {"FINISHED"}


class SENGA_OT_fit(bpy.types.Operator):
    bl_idname = "senga.fit_scene"
    bl_label = "Fit to Scene"
    bl_description = "Set form-hatch spacing and outline fade from object size and camera distance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        objs = autosetup.targets(context)
        autosetup.store_radii(objs)
        met = autosetup.fit_to_scene(sc, objs)
        if met is None:
            self.report({"WARNING"}, i18n.report("No measurable objects"))
            return {"CANCELLED"}
        _apply_all(sc)
        self.report({"INFO"}, i18n.report(f"Fitted: object size {met[0]:.2f}, camera distance {met[3]:.2f}"))
        return {"FINISHED"}


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
from .ui import CLASSES as UI_CLASSES   # noqa: E402

CLASSES = (SENGA_Settings, SENGA_ObjSettings, SENGA_OT_setup_scene, SENGA_OT_sketchify, SENGA_OT_outline,
           SENGA_OT_post, SENGA_OT_revert, SENGA_OT_reset, SENGA_OT_shuffle, SENGA_OT_all,
           SENGA_OT_fit) + UI_CLASSES


@bpy.app.handlers.persistent
def _on_load(*_):
    revalidate_drivers()


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.senga = PointerProperty(type=SENGA_Settings)
    bpy.types.Object.senga_obj = PointerProperty(type=SENGA_ObjSettings)
    i18n.register()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    i18n.unregister()
    del bpy.types.Object.senga_obj
    del bpy.types.Scene.senga
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
