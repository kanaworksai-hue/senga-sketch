# Changelog

## 1.0.0 — 2026-11

First release.

- **Make It Senga**: EEVEE, sketch material, hand-inked outlines, contour lines and paper in one click; Revert restores
  everything.
- Sketch material: graphite tone from light × the model's own colours, hand-wobbled hatching that thickens with darkness
  (screen-space like a drawing, or following the form), cross and deep hatching, screentone and stipple patterns, solid
  blacks with a dry-brush edge, gloss highlights, dark-texture lift, optional watercolour wash.
- Outlines: Geometry-Nodes inverted hull with pen-pressure breakup, boil on twos and heavier lines on the side away from
  the key light.
- Compositor: crease and depth contour lines (white lines inside solid blacks), paper tooth, smudge, wet edges,
  unfinished-edge fade, any ink on any paper — including chalk on dark paper.
- 8 media (Manga Pen, Graphite Pencil, Charcoal, Ballpoint, Sumi Ink Wash, Engraving, Manga Screentone, Stipple) and
  8 papers (Sketchbook, Sepia, Kraft + Chalk, Toned Grey + Chalk, Notebook, Blueprint, Chalkboard, Ink + Watercolour);
  Shuffle re-rolls a reproducible variation.
- Works on any scene: material-less objects, vertex colours, image / Diffuse / Emission materials, text, curves,
  collection instances; glass is kept and drawn with a rim tone.
- UI in English, 日本語, 简体中文 and 한국어 — follows Blender's language, or pick one in the 🌐 menu.
- AI-agent ready: `AGENTS.md` and `agent/senga_agent.py` (install, apply, render in one command).
