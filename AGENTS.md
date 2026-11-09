# Senga Sketch — instructions for AI agents

The human only says something like *"make my Blender scene look hand-drawn"*, *「線画っぽくして」*,
*「漫画のペン画にして」* or *「做成素描风」*. You do everything: install, apply, show a preview.
Do not ask the human to click anything in Blender.

## 1. Find Blender
- macOS: `/Applications/Blender*.app/Contents/MacOS/Blender`
- Windows: `C:\Program Files\Blender Foundation\Blender */blender.exe`
- Linux: `blender` on PATH

Needs **5.0+** (EEVEE). Folder names don't always show the version, so ask each one and pick the newest:
```bash
for b in /Applications/Blender*.app/Contents/MacOS/Blender; do echo "$("$b" --version | head -1) | $b"; done
```

## 2. Install (once)
Get the latest `senga_sketch-<version>.zip` from https://github.com/kanaworksai-hue/senga-sketch/releases
and `agent/senga_agent.py` from the repository:
```bash
git clone --depth 1 https://github.com/kanaworksai-hue/senga-sketch.git
gh release download -R kanaworksai-hue/senga-sketch -p 'senga_sketch-*.zip'      # with gh
# or without gh:
curl -sL "$(curl -s https://api.github.com/repos/kanaworksai-hue/senga-sketch/releases/latest \
  | grep -o 'https://[^"]*senga_sketch-[^"]*\.zip' | head -1)" -o senga_sketch.zip
```
Then:
```bash
<blender> -b --python senga-sketch/agent/senga_agent.py -- --install senga_sketch-<version>.zip
```
Never add `--factory-startup` to the install command — the install is saved into the user's
preferences and factory startup would overwrite them. The script refuses in that case.
Success = last line starts with `SENGA OK`.

## 3. Apply

### a) To a .blend file (Blender closed, headless)
```bash
<blender> -b scene.blend --python agent/senga_agent.py -- \
    --medium PEN --paper SKETCHBOOK --save scene_sketch.blend --render preview.png
```
Install and apply can be one command: add `--install senga_sketch-<version>.zip`.
Show the human `preview.png`. Save to a new file unless they asked to overwrite.

### b) To a model file (.glb .gltf .fbx .obj)
```bash
<blender> -b --python agent/senga_agent.py -- --model chair.glb --medium PEN --render preview.png
```
A camera is aimed at the model and a key light is added when the scene has none.

### c) Into a running Blender (e.g. through a Blender MCP / Python console)
```python
import bpy
s = bpy.context.scene.senga
bpy.ops.senga.apply_all()          # Make It Senga (whole visible scene; set s.only_selected = True for the selection)
s.medium = "PENCIL"                # technique
s.paper = "KRAFT"                  # paper & ink colour
s.variation = 918                  # or bpy.ops.senga.shuffle()
s.hatch_spacing = 0.008            # any setting, see --list
bpy.ops.senga.revert()             # undo everything
```

## 4. Turning the human's words into options

**If the human gives no style at all** ("make it a sketch"), use `--medium PEN --paper SKETCHBOOK`.
On later tweaks, omit what they didn't mention: the current medium, paper and variation are kept.

| They say | `--medium` |
|---|---|
| ink drawing, manga, pen and ink, 線画, ペン画, 漫画, 钢笔画, 线稿 (default) | `PEN` |
| pencil sketch, graphite, drawing, 鉛筆, デッサン, 素描, 铅笔 | `PENCIL` |
| charcoal, smudgy, dramatic, 木炭, 炭笔 | `CHARCOAL` |
| ballpoint, doodle, notebook sketch, ボールペン, 落書き, 圆珠笔 | `BALLPOINT` |
| sumi-e, ink wash, brush, 水墨, 墨絵, 水墨画 | `INK_WASH` |
| engraving, etching, banknote, woodcut, 銅版画, 版画, 铜版画 | `ENGRAVING` |
| manga screentone, halftone, comic dots, トーン, 网点 | `SCREENTONE` |
| stippling, pointillism, dots, 点描 | `STIPPLE` |

| They say | `--paper` |
|---|---|
| white paper, plain (default) | `SKETCHBOOK` |
| old, vintage, sepia, 古い, セピア, 复古 | `SEPIA` |
| brown paper, kraft, with white highlights, クラフト紙, 牛皮纸 | `KRAFT` |
| grey paper, toned paper, 色紙, 灰色纸 | `TONED_GREY` |
| notebook, school, blue pen, ノート, 笔记本 | `NOTEBOOK` |
| blueprint, technical, 青焼き, 蓝图 | `BLUEPRINT` |
| chalkboard, blackboard, 黒板, 黑板 | `CHALKBOARD` |
| with colour, watercolour tint, line and wash, 淡彩, 水彩, 上色 | `WATERCOLOUR` |

| They say | option |
|---|---|
| "something different", "another version", 別パターン, 换一个 | `--shuffle` (prints the variation number) |
| "go back to version 918" | `--variation 918` |
| denser / finer hatching, 線を細かく, 排线密一点 | `--set hatch_spacing=<current × 0.7>` |
| lines follow the shape, 立体に沿って, 沿着形体 | `--set hatch_form=1` |
| thinner outlines, 線を細く, 线细一点 | `--set outline_thickness=<current × 0.6>` |
| no outlines, 線なし, 不要描边 | `--set outline_enable=false` |
| lighter, less ink, 明るく, 淡一点 | `--set brightness=1.3` |
| more contrast, bolder blacks, ベタを多く, 黑一点 | `--set solid_start=0.7 --set shadow_floor=0.35` |
| fade out at the edges, 余白を残す, 边缘留白 | `--set edge_fade=0.8` |
| add colour, 色をつけて, 加点颜色 | `--set wash_amount=0.5` (or `--paper WATERCOLOUR`) |

Unknown names fail with a hint; run `--list` and pick the closest, then tell the human what you chose.

The panel follows Blender's language automatically (English, 日本語, 简体中文, 한국어). If the human wants the panel in
another language than Blender itself, run `--ui-language JA` (or `EN`, `ZH`, `KO`, `AUTO`) — without `--factory-startup`.

## Getting the best result (do this, the human won't ask)
1. Render a preview (`--render preview.png --preview-size 50`) and look at it before reporting back.
   If objects are cut off, add `--frame-camera` (a separate camera; the human's own camera is not touched).
   Hatching is drawn in screen space: judge it at the final resolution, it blurs into grey in tiny previews.
2. Offer two or three variations as small previews (e.g. two media, or `--shuffle` twice) and let the human pick
   in one word.
3. Glass is kept as it is and drawn as an outline with a little rim tone. Curves and text get the sketch material
   but no outline.
4. Report what you changed in one sentence, with the preview.

## Notes
- Don't mix up the commands: **installing** must not use `--factory-startup`; the README's Development section uses it
  only for tests and builds.
- Needs EEVEE. Make It Senga switches the scene to EEVEE, the Standard view transform and a transparent film (the paper
  is drawn by the compositor); `--revert` restores them.
- Sister add-ons: [Painterly 2.5D](https://github.com/kanaworksai-hue/painterly-25d/blob/main/AGENTS.md) (oil /
  watercolour / crayon / anime paint), [KiraPaint](https://github.com/kanaworksai-hue/kirapaint/blob/main/AGENTS.md)
  (sparkly / キラキラ) and [MochiToon](https://github.com/kanaworksai-hue/mochitoon/blob/main/AGENTS.md) (cute comic toon).
  Pick Senga Sketch for black-and-white drawing, hatching, manga ink, pencil, engraving or chalk looks. Use one add-on per
  scene.
