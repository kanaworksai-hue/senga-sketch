# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Senga tab in the 3D view sidebar (N). Every text goes through i18n.t(), so the panel follows
Blender's language automatically, or the language picked in the 🌐 header menu."""
import bpy

from . import i18n
from .i18n import t
from .util import TAG


def _prop(layout, owner, name, label=None, **kw):
    if label is None:
        label = owner.bl_rna.properties[name].name
    layout.prop(owner, name, text=t(label), translate=False, **kw)


def _op(layout, idname, label, **kw):
    return layout.operator(idname, text=t(label), text_ctxt="Operator", translate=False, **kw)


def _enum(layout, owner, name):
    """Enum dropdown whose item names follow the panel language."""
    prop = owner.bl_rna.properties[name]
    cur = getattr(owner, name)
    label = next((i.name for i in prop.enum_items if i.identifier == cur), cur)
    row = layout.row(align=True)
    row.label(text=t(prop.name), translate=False)
    row.menu(f"SENGA_MT_{name}", text=t(label), translate=False)


def _enum_menu(prop_name):
    class _M(bpy.types.Menu):
        bl_idname = f"SENGA_MT_{prop_name}"
        bl_label = prop_name.title()

        def draw(self, context):
            s = context.scene.senga
            for it in s.bl_rna.properties[prop_name].enum_items:
                op = self.layout.operator("senga.set_enum", text=t(it.name), translate=False,
                                          depress=getattr(s, prop_name) == it.identifier)
                op.prop = prop_name
                op.value = it.identifier
    _M.__name__ = f"SENGA_MT_{prop_name}"
    return _M


class SENGA_OT_set_enum(bpy.types.Operator):
    bl_idname = "senga.set_enum"
    bl_label = "Set"
    bl_description = "Choose this option"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    prop: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    value: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        try:
            prop = context.scene.senga.bl_rna.properties[props.prop]
            it = next(i for i in prop.enum_items if i.identifier == props.value)
            return t(it.description)
        except (KeyError, StopIteration, AttributeError):
            return ""

    def execute(self, context):
        setattr(context.scene.senga, self.prop, self.value)
        return {"FINISHED"}


class SengaPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Senga"


class SengaSub(SengaPanel):
    bl_parent_id = "SENGA_PT_main"
    bl_options = {"DEFAULT_CLOSED"}
    title = ""

    def draw_header(self, context):
        self.layout.label(text=t(self.title), translate=False)


class SENGA_PT_main(SengaPanel, bpy.types.Panel):
    bl_label = "Senga Sketch"
    bl_idname = "SENGA_PT_main"

    def draw_header_preset(self, context):
        prefs = i18n.prefs(context)
        if prefs is not None:
            self.layout.prop(prefs, "ui_language", text="", icon="WORLD_DATA")

    def draw(self, context):
        s = context.scene.senga
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.5
        _op(col, "senga.apply_all", "Make It Senga", icon="GREASEPENCIL")
        col = layout.column(align=True)
        _enum(col, s, "medium")
        _enum(col, s, "paper")
        row = layout.row(align=True)
        _prop(row, s, "variation")
        _op(row, "senga.shuffle", "Shuffle", icon="FILE_REFRESH")
        row = layout.row(align=True)
        _op(row, "senga.revert", "Revert Sketch", icon="LOOP_BACK")
        _op(row, "senga.reset", "Reset to Defaults", icon="FILE_BLANK")
        col = layout.column(align=True)
        _prop(col, s, "only_selected")
        _prop(col, s, "auto_key_light")
        _prop(col, s, "auto_fit")
        if context.scene.render.engine not in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            layout.label(text=t("Needs EEVEE (Make It Senga switches)"), icon="INFO", translate=False)


class SENGA_PT_tone(SengaSub, bpy.types.Panel):
    bl_label = ""
    title = "Tone"

    def draw(self, context):
        s = context.scene.senga
        col = self.layout.column(align=True)
        col.label(text=t("Light"), translate=False)
        _prop(col, s, "key_light")
        _prop(col, s, "threshold")
        _prop(col, s, "softness")
        _prop(col, s, "cel_amount", slider=True)
        _prop(col, s, "shadow_floor", slider=True)
        _prop(col, s, "brightness")
        col = self.layout.column(align=True)
        col.label(text=t("Model colours"), translate=False)
        _prop(col, s, "albedo_influence", slider=True)
        _prop(col, s, "albedo_floor", slider=True)
        _prop(col, s, "gloss")
        col = self.layout.column(align=True)
        col.label(text=t("Graphite & solid blacks"), translate=False)
        _prop(col, s, "fill_strength", slider=True)
        _prop(col, s, "fill_texture", slider=True)
        _prop(col, s, "solid_amount", slider=True)
        _prop(col, s, "solid_start", slider=True)
        _prop(col, s, "dry_brush")


class SENGA_PT_hatch(SengaSub, bpy.types.Panel):
    bl_label = ""
    title = "Hatching"

    def draw(self, context):
        s = context.scene.senga
        col = self.layout.column(align=True)
        _enum(col, s, "pattern")
        _prop(col, s, "hatch_amount", slider=True)
        _prop(col, s, "hatch_start", slider=True)
        _prop(col, s, "cross_start", slider=True)
        _prop(col, s, "deep_start", slider=True)
        col = self.layout.column(align=True)
        _prop(col, s, "hatch_spacing")
        _prop(col, s, "hatch_width", slider=True)
        _prop(col, s, "hatch_angle")
        _prop(col, s, "cross_angle")
        col = self.layout.column(align=True)
        _prop(col, s, "hatch_wobble", slider=True)
        _prop(col, s, "wobble_scale")
        _prop(col, s, "hatch_breakup", slider=True)
        _prop(col, s, "hatch_form", slider=True)
        _prop(col, s, "tone_steps")
        _prop(col, s, "hatch_boil")


class SENGA_PT_lines(SengaSub, bpy.types.Panel):
    bl_label = ""
    title = "Lines"

    def draw(self, context):
        s = context.scene.senga
        col = self.layout.column(align=True)
        _prop(col, s, "outline_enable")
        sub = col.column(align=True)
        sub.active = s.outline_enable
        _prop(sub, s, "line_width")
        _prop(sub, s, "line_opacity", slider=True)
        _prop(sub, s, "outline_jitter", slider=True)
        _prop(sub, s, "line_light_weight", slider=True)
        row = sub.row(align=True)
        _prop(row, s, "outline_boil")
        _prop(row, s, "boil_rate")
        col = self.layout.column(align=True)
        _prop(col, s, "contour_enable")
        sub = col.column(align=True)
        sub.active = s.contour_enable
        _prop(sub, s, "contour_strength", slider=True)
        _prop(sub, s, "contour_normal")
        _prop(sub, s, "contour_depth")
        _prop(sub, s, "contour_width")
        _prop(sub, s, "contour_wobble")
        _prop(sub, s, "contour_breakup", slider=True)
        _prop(sub, s, "white_lines", slider=True)


class SENGA_PT_paper(SengaSub, bpy.types.Panel):
    bl_label = ""
    title = "Paper & Colour"

    def draw(self, context):
        s = context.scene.senga
        col = self.layout.column(align=True)
        _prop(col, s, "ink_color")
        _prop(col, s, "paper_color")
        _prop(col, s, "paper_texture", slider=True)
        _prop(col, s, "paper_tooth", slider=True)
        col = self.layout.column(align=True)
        _prop(col, s, "smudge", slider=True)
        _prop(col, s, "wet_edges", slider=True)
        _prop(col, s, "edge_fade", slider=True)
        _enum(col, s, "fade_mode")
        _prop(col, s, "edge_fade_start")
        col = self.layout.column(align=True)
        _prop(col, s, "wash_amount", slider=True)
        _prop(col, s, "wash_saturation")
        _prop(col, s, "chalk", slider=True)
        _prop(col, s, "chalk_color")
        _prop(col, s, "highlight_threshold", slider=True)
        _prop(col, s, "tone_invert", slider=True)
        _prop(col, s, "paper_marks", slider=True)
        col = self.layout.column(align=True)
        _prop(col, s, "rule_lines", slider=True)
        _prop(col, s, "rule_color")
        _prop(col, s, "rule_spacing")
        _prop(col, s, "grain", slider=True)
        _prop(col, s, "vignette", slider=True)


class SENGA_PT_object(SengaSub, bpy.types.Panel):
    bl_label = ""
    title = "Active Object Override"

    @classmethod
    def poll(cls, context):
        return context.object is not None and hasattr(context.object, "senga_obj")

    def draw(self, context):
        ov = context.object.senga_obj
        col = self.layout.column(align=True)
        _prop(col, ov, "use_override")
        sub = col.column(align=True)
        sub.active = ov.use_override
        for k in ("threshold", "shadow_floor", "brightness", "albedo_influence", "fill_strength",
                  "solid_amount", "hatch_amount", "wash_amount", "gloss", "outline_enable", "outline_scale"):
            _prop(sub, ov, k)


class SENGA_PT_advanced(SengaSub, bpy.types.Panel):
    bl_label = ""
    title = "Tools"

    def draw(self, context):
        col = self.layout.column(align=True)
        _op(col, "senga.setup_scene", "Setup Render", icon="SCENE")
        _op(col, "senga.sketchify", "Apply Sketch Shader", icon="MATERIAL")
        _op(col, "senga.outline", "Add Ink Outlines", icon="MOD_SOLIDIFY")
        _op(col, "senga.post", "Build Paper & Contours", icon="NODE_COMPOSITING")
        _op(col, "senga.fit_scene", "Fit to Scene", icon="FULLSCREEN_ENTER")
        col = self.layout.column(align=True)
        col.label(text="Senga Sketch by KanaWorks_AI", translate=False)
        op = col.operator("wm.url_open", text="x.com/KanaWorks_AI", icon="URL", translate=False)
        op.url = "https://x.com/KanaWorks_AI"
        op = col.operator("wm.url_open", text=t("Free add-ons (GitHub)"), icon="URL", translate=False)
        op.url = "https://github.com/kanaworksai-hue"


CLASSES = (SENGA_OT_set_enum, _enum_menu("medium"), _enum_menu("paper"), _enum_menu("pattern"), _enum_menu("fade_mode"),
           SENGA_PT_main, SENGA_PT_tone, SENGA_PT_hatch, SENGA_PT_lines, SENGA_PT_paper, SENGA_PT_object,
           SENGA_PT_advanced)
