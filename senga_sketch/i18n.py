# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI in English, 日本語, 简体中文 and 한국어.

Two ways in:
1. Automatic: set Blender's language (Preferences > Interface > Translation) and Senga Sketch follows,
   tooltips included, through Blender's own translation system.
2. By hand: the 🌐 menu in the panel header (or the add-on preferences) picks a language for the panel,
   whatever language Blender itself uses.

Shared terms follow Blender's official translations (アウトライン / 描边 / 외곽선, レンダー / 渲染 / 렌더,
コンポジター / 合成器 / 합성기, キーライト, ...).
"""
import re

import bpy

PACKAGE = __package__

# msgid: (Japanese, Simplified Chinese, Korean)
UI = {
    # panels and sections
    "Senga Sketch": ("線画スケッチ (Senga Sketch)", "线画素描 (Senga Sketch)", "선화 스케치 (Senga Sketch)"),
    "Tone": ("トーン（明暗）", "色调（明暗）", "톤 (명암)"),
    "Hatching": ("ハッチング", "排线", "해칭"),
    "Lines": ("線", "线条", "선"),
    "Paper & Colour": ("紙と色", "纸张与颜色", "종이와 색"),
    "Active Object Override": ("アクティブオブジェクトの上書き", "活动物体覆盖", "활성 오브젝트 재정의"),
    "Tools": ("ツール", "工具", "도구"),
    "Light": ("ライト", "灯光", "라이트"),
    "Model colours": ("モデルの色", "模型颜色", "모델 색상"),
    "Graphite & solid blacks": ("鉛筆の塗りとベタ", "铅笔涂色与实黑", "흑연 칠과 먹칠"),
    "Needs EEVEE (Make It Senga switches)": ("EEVEE が必要です（「線画にする」で切り替わります）",
                                             "需要 EEVEE（点「变成线画」会自动切换）",
                                             "EEVEE가 필요합니다 (「선화로 만들기」가 전환합니다)"),
    "Free add-ons (GitHub)": ("無料アドオン（GitHub）", "免费插件（GitHub）", "무료 애드온 (GitHub)"),
    "UI Language": ("表示言語", "界面语言", "표시 언어"),
    "Language of the Senga Sketch panel. Automatic follows Blender's own language":
        ("Senga Sketch パネルの表示言語。自動では Blender の言語設定に合わせます",
         "Senga Sketch 面板的显示语言。自动 = 跟随 Blender 的语言设置",
         "Senga Sketch 패널의 표시 언어. 자동은 Blender 언어 설정을 따릅니다"),
    "Automatic (follow Blender)": ("自動（Blender に合わせる）", "自动（跟随 Blender）", "자동 (Blender를 따름)"),
    "Auto": ("自動", "自动", "자동"),
    # main settings
    "Drawing Medium": ("画材", "画材", "재료"),
    "Paper": ("紙", "纸张", "종이"),
    "Variation": ("バリエーション", "变体", "변형"),
    "Re-rolls hatch angle, spacing, wobble, line breakup, edge fade and paper shade around the current medium "
    "and paper. 0 = off":
        ("いまの画材と紙のまま、線の角度・間隔・揺れ・かすれ・端のフェード・紙の色味を振り直します。0 でオフ",
         "在当前画材和纸张基础上，重新随机排线角度、间距、抖动、断笔、边缘淡出和纸色。0 = 关闭",
         "현재 재료와 종이를 유지한 채 해칭 각도·간격·흔들림·끊김·가장자리 페이드·종이 색조를 다시 뽑습니다. 0 = 끔"),
    "Selected Objects Only": ("選択中のオブジェクトのみ", "仅选中物体", "선택한 오브젝트만"),
    "Make It Senga only converts the selected objects": ("「線画にする」を選択中のオブジェクトだけに適用します",
                                                         "「变成线画」只处理选中的物体",
                                                         "「선화로 만들기」를 선택한 오브젝트에만 적용합니다"),
    "Add Key Light if Missing": ("キーライトがなければ追加", "缺少主光时自动添加", "키 라이트가 없으면 추가"),
    "Add a Sun aimed from the camera side when the scene has no light (removed again by Revert)":
        ("シーンにライトがないとき、カメラ側から照らすサンを追加します（元に戻すで削除）",
         "场景没有灯光时，从相机一侧添加一盏日光（还原时会删除）",
         "씬에 라이트가 없으면 카메라 쪽에서 비추는 썬을 추가합니다 (되돌리기로 삭제)"),
    "Fit to Scene Scale": ("シーンのスケールに合わせる", "适配场景尺寸", "씬 스케일에 맞추기"),
    "Set form-hatch spacing and outline fade from object size and camera distance":
        ("オブジェクトの大きさとカメラ距離から、立体に沿う線の間隔とアウトラインの減衰を設定します",
         "根据物体大小和相机距离设置沿形排线的间距和描边的远处衰减",
         "오브젝트 크기와 카메라 거리로 형태 해칭 간격과 외곽선 감쇠를 설정합니다"),
    "Add-on Loaded": ("アドオン読み込み済み", "插件已加载", "애드온 로드됨"),
    "Read by the shader; missing when the add-on is not installed, so materials fall back to baked values":
        ("シェーダーが読み取ります。アドオンがない環境では、保存された値で描画されます",
         "着色器读取此值；未安装插件时材质会使用烘焙的数值",
         "셰이더가 읽습니다. 애드온이 없으면 저장된 값으로 렌더됩니다"),
    # light / tone
    "Key Light": ("キーライト", "主光源", "키 라이트"),
    "Light the tone is measured against (drives Light Scale) and the light the outlines thicken away from":
        ("明暗の基準になるライト（ライトスケールを駆動）。アウトラインはこのライトの反対側で太くなります",
         "用来测量明暗的灯光（驱动光照比例），描边会在背光一侧变粗",
         "명암의 기준이 되는 라이트 (라이트 스케일 구동). 외곽선은 이 라이트 반대쪽에서 굵어집니다"),
    "Light Scale": ("ライトスケール", "光照比例", "라이트 스케일"),
    "Key light strength x brightest colour channel (driven by Key Light)":
        ("キーライトの強さ × いちばん明るい色チャンネル（キーライトで自動設定）",
         "主光强度 × 最亮的颜色通道（由主光源驱动）",
         "키 라이트 강도 × 가장 밝은 색 채널 (키 라이트로 자동 설정)"),
    "Ambient Compensation": ("環境光の補正", "环境光补偿", "환경광 보정"),
    "World fill removed before the tone is measured, so bright worlds keep their shadows (estimated by Setup "
    "Render)": ("明暗を測る前にワールドの環境光を差し引き、明るいワールドでも影が残るようにします（レンダー設定で推定）",
                "测量明暗前减去世界环境光，让明亮的世界也保留阴影（由渲染设置估算）",
                "명암을 재기 전에 월드 환경광을 빼서 밝은 월드에서도 그림자가 남게 합니다 (렌더 설정에서 추정)"),
    "Shadow Threshold": ("影のしきい値", "阴影阈值", "그림자 임계값"),
    "Light level where the shadow side starts": ("影側が始まる明るさ", "阴影面开始的亮度", "그림자 쪽이 시작되는 밝기"),
    "Shadow Softness": ("影のやわらかさ", "阴影柔和度", "그림자 부드러움"),
    "Cel Shading": ("セルシェーディング", "赛璐璐分明暗", "셀 셰이딩"),
    "0 = soft graphite gradient, 1 = hard light/shadow split": ("0 でやわらかい鉛筆のグラデーション、1 でくっきり明暗二分",
                                                              "0 = 柔和的铅笔渐变，1 = 明暗硬切",
                                                              "0 = 부드러운 연필 그라데이션, 1 = 또렷한 명암 분리"),
    "Shadow Lightness": ("影の明るさ", "阴影亮度", "그림자 밝기"),
    "How light the darkest shadow stays": ("いちばん暗い影をどれだけ明るく残すか", "最暗的阴影保留多亮",
                                           "가장 어두운 그림자를 얼마나 밝게 남길지"),
    "Brightness": ("明るさ", "亮度", "밝기"),
    "Lighter drawing = less ink overall": ("明るいほどインクが減ります", "越亮墨越少", "밝을수록 잉크가 줄어듭니다"),
    "Texture Values": ("テクスチャの明暗", "贴图明暗", "텍스처 명암"),
    "How much the model's own colours turn into tone (dark hair -> black ink). 0 = lighting only":
        ("モデル自身の色をどれだけ明暗にするか（黒い髪 → ベタ）。0 でライティングのみ",
         "模型自身颜色转成明暗的程度（深色头发 → 实黑）。0 = 只看光照",
         "모델 자체 색을 얼마나 명암으로 바꿀지 (검은 머리 → 먹칠). 0 = 조명만"),
    "Dark Texture Lift": ("暗い色の持ち上げ", "深色提亮", "어두운 색 끌어올리기"),
    "Black textures still show light and shadow: their lit side is hatched instead of solid ink":
        ("黒いテクスチャにも明暗を残します。光の当たる側はベタではなくハッチングになります",
         "黑色贴图也保留明暗：受光面用排线而不是实黑",
         "검은 텍스처도 명암을 남깁니다. 빛 받는 쪽은 먹칠 대신 해칭이 됩니다"),
    "Gloss Highlights": ("光沢のハイライト", "光泽高光", "광택 하이라이트"),
    "Leave white streaks where the key light reflects (glossy and black objects)":
        ("キーライトが映り込むところを白く残します（ツヤのある物・黒い物に）",
         "在主光反射处留出白色高光（适合有光泽或黑色的物体）",
         "키 라이트가 반사되는 곳을 하얗게 남깁니다 (광택·검은 물체)"),
    "Texture Black Point": ("テクスチャの黒点", "贴图黑点", "텍스처 블랙 포인트"),
    "Texture White Point": ("テクスチャの白点", "贴图白点", "텍스처 화이트 포인트"),
    "Graphite Fill": ("鉛筆の塗り", "铅笔涂色", "흑연 칠"),
    "Soft grey shading under the lines": ("線の下のやわらかいグレーの陰影", "线条下面柔和的灰色阴影",
                                          "선 아래의 부드러운 회색 음영"),
    "Fill Start": ("塗りの開始", "涂色起点", "칠 시작"),
    "Fill Strokes": ("塗りのタッチ", "涂色笔触", "칠의 결"),
    "Directional stroke texture inside the fill": ("塗りの中の方向のあるタッチ", "涂色里有方向的笔触纹理",
                                                   "칠 안의 방향성 있는 결"),
    "Solid Blacks": ("ベタ", "实黑", "먹칠"),
    "Fill the darkest areas (hair, deep shadow) with solid ink": ("いちばん暗い所（髪・深い影）をベタで塗ります",
                                                                  "最暗的区域（头发、深阴影）用实黑填满",
                                                                  "가장 어두운 곳 (머리카락·깊은 그림자)을 먹칠합니다"),
    "Solid Black Start": ("ベタの開始", "实黑起点", "먹칠 시작"),
    "Dry Brush Edge": ("かすれ（ドライブラシ）", "枯笔边缘", "드라이 브러시 가장자리"),
    "Streaky, broken edge where solid black meets the hatching": ("ベタとハッチングの境目をかすれさせます",
                                                                 "实黑与排线交界处的枯笔飞白",
                                                                 "먹칠과 해칭이 만나는 곳을 갈라지게 합니다"),
    # hatching
    "Pattern": ("パターン", "图案", "패턴"),
    "Parallel hand-drawn lines, crossing in darker areas": ("手描きの平行線。暗い所では交差します",
                                                            "手绘平行线，暗处交叉", "손으로 그린 평행선. 어두운 곳에서 교차합니다"),
    "Screentone": ("スクリーントーン", "网点", "스크린톤"),
    "Halftone dots": ("網点", "半调网点", "망점"),
    "Stipple": ("点描", "点描", "점묘"),
    "Randomly placed dots": ("ランダムな点", "随机分布的点", "무작위 점"),
    "Hatch Start": ("ハッチングの開始", "排线起点", "해칭 시작"),
    "Tone where the first lines appear (lower = more lines)": ("最初の線が現れる暗さ（低いほど線が増えます）",
                                                               "第一层线出现的暗度（越低线越多）",
                                                               "첫 선이 나타나는 어두움 (낮을수록 선이 많아집니다)"),
    "Cross-hatch Start": ("クロスハッチングの開始", "交叉排线起点", "크로스 해칭 시작"),
    "Deep Hatch Start": ("3層目の線の開始", "第三层排线起点", "3번째 선 시작"),
    "Line Spacing": ("線の間隔", "线间距", "선 간격"),
    "Distance between hatch lines, as a fraction of the image height (resolution independent)":
        ("ハッチングの線の間隔（画像の高さに対する割合。解像度に依存しません）",
         "排线之间的距离（相对图像高度的比例，与分辨率无关）",
         "해칭 선 사이 거리 (이미지 높이에 대한 비율, 해상도와 무관)"),
    "Hatch Weight": ("ハッチングの太さ", "排线粗细", "해칭 굵기"),
    "Widest line, as a fraction of the spacing": ("いちばん太い線（間隔に対する割合）", "最粗的线（相对间距的比例）",
                                                  "가장 굵은 선 (간격에 대한 비율)"),
    "Hatch Angle": ("ハッチングの角度", "排线角度", "해칭 각도"),
    "Cross Angle": ("交差の角度", "交叉角度", "교차 각도"),
    "Hand Wobble": ("手の揺れ", "手抖", "손떨림"),
    "Wobble Scale": ("揺れのスケール", "抖动尺度", "흔들림 스케일"),
    "Stroke Breakup": ("線のかすれ", "断笔", "선 끊김"),
    "Gaps and tapered ends along the lines": ("線の途切れと入り抜き", "线条的断开与收笔", "선의 끊김과 붓끝"),
    "Follow Form": ("立体に沿わせる", "沿着形体", "형태 따라가기"),
    "0 = lines fixed on the screen like the reference drawing, 1 = lines bend over the shape (engraving). Objects "
    "added later need Fit to Scene":
        ("0 で画面に固定された線（参考の絵のように）、1 で形に沿って曲がる線（銅版画風）。あとから追加したオブジェクトは「シーンに合わせる」を押してください",
         "0 = 线固定在画面上（像参考作品），1 = 线顺着形体弯曲（铜版画风）。之后新加的物体请点「适配场景」",
         "0 = 화면에 고정된 선 (참고 그림처럼), 1 = 형태를 따라 휘는 선 (동판화). 나중에 추가한 오브젝트는 「씬에 맞추기」를 누르세요"),
    "Tone Steps": ("明暗の段階", "明暗层级", "명암 단계"),
    "Quantise the shading into flat steps (sumi washes, two-level screentone). 0 = smooth":
        ("陰影を平らな段階に分けます（墨の濃淡、2段階のトーン）。0 でなめらか",
         "把明暗分成平涂的几个层级（水墨浓淡、两级网点）。0 = 平滑",
         "음영을 평평한 단계로 나눕니다 (먹의 농담, 2단계 톤). 0 = 부드럽게"),
    "Shading Marks": ("陰影の描き込み", "阴影笔触量", "음영 표현량"),
    "How much shading and hatching the paper takes (blueprint: lines only)":
        ("紙にのせる陰影とハッチングの量（青焼きは線だけ）", "纸上画多少阴影和排线（蓝图只画线）",
         "종이에 올릴 음영과 해칭의 양 (청사진은 선만)"),
    "Seed": ("シード", "种子", "시드"),
    "Hatch Boil": ("ハッチングのブル", "排线抖动动画", "해칭 보일"),
    "Re-draw the hatching on the boil rate (lively, but busier)": ("ブルの間隔でハッチングを描き直します（生き生きしますが、にぎやかになります）",
                                                                   "按抖动间隔重画排线（更生动，但更花）",
                                                                   "보일 간격마다 해칭을 다시 그립니다 (생동감 있지만 복잡해집니다)"),
    "Hatch Phase": ("ハッチングの位相", "排线相位", "해칭 위상"),
    "Driven: floor(frame / boil rate) * 0.37 when Hatch Boil is on": ("ドライバー：ハッチングのブルがオンのとき floor(フレーム / 間隔) × 0.37",
                                                                       "驱动器：排线抖动开启时为 floor(帧 / 间隔) × 0.37",
                                                                       "드라이버: 해칭 보일이 켜지면 floor(프레임 / 간격) × 0.37"),
    "Pattern ID": ("パターン ID", "图案 ID", "패턴 ID"),
    "Fade Bottom": ("下へのフェード", "向下淡出", "아래로 페이드"),
    # colour
    "Ink Colour": ("インクの色", "墨色", "잉크 색"),
    "Colour Wash": ("色のにじみ（淡彩）", "淡彩", "담채"),
    "Light watercolour tint of the model's own colours under the ink": ("インクの下に、モデル自身の色を淡い水彩で",
                                                                       "在墨线下面用模型自身的颜色淡淡地上一层水彩",
                                                                       "잉크 아래에 모델 자체 색을 연한 수채로"),
    "Wash Saturation": ("淡彩の彩度", "淡彩饱和度", "담채 채도"),
    "Draw the Light": ("光を描く", "画光", "빛을 그리기"),
    "Marks describe the light instead of the shadow (chalk / blueprint on dark paper)":
        ("影ではなく光を描きます（暗い紙にチョークや青焼き）", "描绘光而不是影（深色纸上的粉笔或蓝图）",
         "그림자 대신 빛을 그립니다 (어두운 종이에 분필·청사진)"),
    "Highlight Threshold": ("ハイライトのしきい値", "高光阈值", "하이라이트 임계값"),
    "Where white chalk highlights start (toned papers)": ("白いチョークのハイライトが始まる明るさ（色紙）",
                                                          "白色粉笔高光开始的亮度（色纸）",
                                                          "흰 분필 하이라이트가 시작되는 밝기 (색지)"),
    # outline
    "Outlines": ("アウトライン", "描边", "외곽선"),
    "Outline": ("アウトライン", "描边", "외곽선"),
    "Line Width": ("線の幅", "线宽", "선 너비"),
    "Outline width. 1 = a fine pen nib; it stays the same on screen whatever the scene size":
        ("アウトラインの幅。1 で細めのペン先。シーンの大きさにかかわらず画面上で同じ幅です",
         "描边宽度。1 = 细笔尖；不论场景多大，画面上的宽度都一样",
         "외곽선 너비. 1 = 가는 펜촉. 씬 크기와 관계없이 화면에서 같은 너비입니다"),
    "Line Darkness": ("線の濃さ", "线条浓度", "선 농도"),
    "Outlines and contour lines (pencil and charcoal draw them lighter)": ("アウトラインと輪郭線の濃さ（鉛筆・木炭は薄め）",
                                                                           "描边和轮廓线的浓度（铅笔、炭笔更淡）",
                                                                           "외곽선과 윤곽선의 농도 (연필·목탄은 연하게)"),
    "Fade Shape": ("フェードの形", "淡出形状", "페이드 모양"),
    "Fade towards every frame edge": ("画面の四方に向かって消えていきます", "向画面四周淡出", "화면 가장자리 사방으로 사라집니다"),
    "Bottom": ("下", "底部", "아래"),
    "Fade towards the bottom, like a bust drawn on a page": ("下に向かって消えていきます（紙に描いた胸像のように）",
                                                             "向下淡出，像画在纸上的半身像",
                                                             "아래로 사라집니다 (종이에 그린 흉상처럼)"),
    "Reference Distance": ("基準距離", "参考距离", "기준 거리"),
    "Fade Distance": ("減衰距離", "衰减距离", "감쇠 거리"),
    "Far Width": ("遠くの線幅", "远处线宽", "먼 곳 선 너비"),
    "Pen Pressure": ("筆圧", "笔压", "필압"),
    "Width breaks up along the line like a pen lifting": ("ペンを浮かせたように、線の太さが途切れながら変わります",
                                                          "线宽像提笔一样断续变化", "펜을 들었다 놓듯 선 굵기가 끊기며 변합니다"),
    "Pressure Scale": ("筆圧のスケール", "笔压尺度", "필압 스케일"),
    "Line Boil": ("線のブル", "线条抖动", "선 보일"),
    "Boil Rate (frames)": ("ブルの間隔（フレーム）", "抖动间隔（帧）", "보일 간격 (프레임)"),
    "Weld UV Seams": ("UV の継ぎ目を溶接", "焊接 UV 接缝", "UV 이음새 용접"),
    "Shadow-side Weight": ("影側を太く", "背光侧加粗", "그림자 쪽 굵게"),
    "Lines get heavier on the side turned away from the key light": ("キーライトの反対側の線を太くします（入りの強弱）",
                                                                    "背对主光的一侧线条更粗",
                                                                    "키 라이트 반대쪽 선을 굵게 합니다"),
    "Contour Lines": ("輪郭線（内側）", "轮廓线（内部）", "윤곽선 (안쪽)"),
    "Inner lines found from creases and depth jumps": ("折れ目と奥行きの段差から内側の線を描きます",
                                                       "根据折痕和深度跳变画出内部线条",
                                                       "접힌 곳과 깊이 차이에서 안쪽 선을 그립니다"),
    "Contour Strength": ("輪郭線の強さ", "轮廓线强度", "윤곽선 강도"),
    "Crease Threshold": ("折れ目のしきい値", "折痕阈值", "주름 임계값"),
    "Lower = more crease lines": ("低いほど折れ目の線が増えます", "越低折痕线越多", "낮을수록 주름 선이 많아집니다"),
    "Depth Threshold": ("奥行きのしきい値", "深度阈值", "깊이 임계값"),
    "Lower = more lines at depth jumps": ("低いほど奥行きの段差に線が増えます", "越低深度跳变处的线越多",
                                         "낮을수록 깊이 차이에 선이 많아집니다"),
    "Contour Width (px)": ("輪郭線の幅（px）", "轮廓线宽（px）", "윤곽선 너비 (px)"),
    "Contour Wobble (px)": ("輪郭線の揺れ（px）", "轮廓线抖动（px）", "윤곽선 흔들림 (px)"),
    "Contour Breakup": ("輪郭線のかすれ", "轮廓线断续", "윤곽선 끊김"),
    "White Lines in Blacks": ("ベタの中の白線", "实黑里的白线", "먹칠 속 흰 선"),
    "Contour lines inside solid black areas are scratched out in white, so black objects keep their shape":
        ("ベタの中の輪郭線は白く抜いて、黒い物の形が分かるようにします",
         "实黑区域里的轮廓线改成白线，让黑色物体保持形状",
         "먹칠 영역 안의 윤곽선을 하얗게 빼서 검은 물체의 형태가 보이게 합니다"),
    # paper
    "Paper Colour": ("紙の色", "纸色", "종이 색"),
    "Paper Texture": ("紙の質感", "纸张纹理", "종이 질감"),
    "Paper Tooth": ("紙の凹凸", "纸张颗粒", "종이 결"),
    "Paper grain breaks up light strokes (pencil, charcoal)": ("紙の凹凸で軽いタッチがかすれます（鉛筆・木炭）",
                                                              "纸的颗粒让轻的笔触断开（铅笔、炭笔）",
                                                              "종이 결 때문에 가벼운 획이 끊깁니다 (연필·목탄)"),
    "Smudge": ("こすれ", "晕擦", "문지름"),
    "Smudge Size (px)": ("こすれの大きさ（px）", "晕擦大小（px）", "문지름 크기 (px)"),
    "Wet Edges": ("にじみの縁", "水渍边", "번짐 가장자리"),
    "Ink pools at the edge of each wash (sumi, watercolour)": ("墨だまりのように、塗りの縁が濃くなります（墨・水彩）",
                                                              "墨在每片晕染边缘聚集（水墨、水彩）",
                                                              "먹이 칠의 가장자리에 고입니다 (수묵·수채)"),
    "Unfinished Edges": ("描きかけの余白", "未完成的边缘", "미완성 가장자리"),
    "The drawing fades out in loose strokes: shading first, then lines": ("ラフなタッチで絵が消えていきます。陰影が先に、線はあとまで残ります",
                                                                          "画以松散的笔触淡出：先淡出阴影，线条保留得更久",
                                                                          "느슨한 획으로 그림이 사라집니다. 음영이 먼저, 선은 더 오래 남습니다"),
    "Fade Start": ("フェード開始", "淡出起点", "페이드 시작"),
    "1 = the frame edge": ("1 で画面の端", "1 = 画面边缘", "1 = 화면 가장자리"),
    "Ruled Lines": ("罫線", "横格线", "괘선"),
    "Rule Spacing (px)": ("罫線の間隔（px）", "横格间距（px）", "괘선 간격 (px)"),
    "Rule Colour": ("罫線の色", "横格线颜色", "괘선 색"),
    "White Chalk": ("白チョーク", "白色粉笔", "흰 분필"),
    "White highlights on the lit side (toned paper)": ("光の当たる側に白いハイライト（色紙）",
                                                       "受光面的白色高光（色纸）", "빛 받는 쪽의 흰 하이라이트 (색지)"),
    "Chalk Colour": ("チョークの色", "粉笔颜色", "분필 색"),
    "Grain": ("粒子", "颗粒", "그레인"),
    "Vignette": ("周辺減光", "暗角", "비네트"),
    # object override
    "Override": ("上書き", "覆盖", "재정의"),
    "Line Width x": ("線の幅 ×", "线宽 ×", "선 너비 ×"),
    # media
    "Manga Pen": ("マンガのペン（Gペン）", "漫画钢笔（G笔）", "만화 펜 (G펜)"),
    "G-pen ink: hand hatching that thickens in shadow, solid blacks, light graphite (default)":
        ("Gペンのインク：影で太くなる手描きのハッチング、ベタ、軽い鉛筆の塗り（標準）",
         "G笔墨线：越暗越粗的手绘排线、实黑、淡淡的铅笔涂色（默认）",
         "G펜 잉크: 그림자에서 굵어지는 손 해칭, 먹칠, 옅은 흑연 (기본)"),
    "Graphite Pencil": ("鉛筆デッサン", "铅笔素描", "연필 소묘"),
    "Soft graphite shading, fine hatching, paper tooth and smudging": ("やわらかい鉛筆の陰影、細いハッチング、紙の凹凸とこすれ",
                                                                       "柔和的铅笔明暗、细排线、纸纹和晕擦",
                                                                       "부드러운 흑연 음영, 가는 해칭, 종이 결과 문지름"),
    "Charcoal": ("木炭", "炭笔", "목탄"),
    "Heavy smudged blacks, coarse strokes, rough paper": ("こすれた濃い黒、粗いタッチ、ざらざらの紙",
                                                         "晕开的浓黑、粗犷笔触、粗糙纸面", "문지른 짙은 검정, 거친 획, 거친 종이"),
    "Ballpoint": ("ボールペン", "圆珠笔", "볼펜"),
    "Thin crossing lines only, like a pen sketch in a notebook": ("細い交差線だけ。ノートの落書きのように",
                                                                 "只有细细的交叉线，像笔记本上的钢笔速写",
                                                                 "가는 교차선만. 노트의 펜 낙서처럼"),
    "Sumi Ink Wash": ("墨の濃淡（水墨）", "水墨", "수묵"),
    "Brush outlines and grey ink washes, no hatching": ("筆の輪郭と墨の濃淡。ハッチングなし",
                                                        "毛笔轮廓和墨色浓淡，不排线", "붓 윤곽과 먹의 농담. 해칭 없음"),
    "Engraving": ("銅版画", "铜版画", "동판화"),
    "Fine lines that follow the form, like an etching or banknote": ("形に沿う細い線。エッチングや紙幣のように",
                                                                     "沿着形体的细线，像蚀刻版画或钞票",
                                                                     "형태를 따르는 가는 선. 에칭이나 지폐처럼"),
    "Manga Screentone": ("マンガのトーン", "漫画网点", "만화 스크린톤"),
    "Clean ink lines with halftone-dot shading": ("きれいなペン線と網点の陰影", "干净的墨线配网点阴影",
                                                  "깔끔한 펜 선과 망점 음영"),
    "Shading built from thousands of ink dots": ("何千もの点で描く陰影", "用成千上万个墨点堆出的明暗",
                                                 "수천 개의 점으로 만든 음영"),
    # papers
    "Sketchbook": ("スケッチブック", "速写本", "스케치북"),
    "Warm white paper, near-black ink (default)": ("あたたかい白の紙と黒に近いインク（標準）",
                                                   "暖白色纸，近黑色墨（默认）", "따뜻한 흰 종이, 검정에 가까운 잉크 (기본)"),
    "Sepia on Cream": ("クリーム紙にセピア", "米色纸·棕褐墨", "크림지에 세피아"),
    "Brown ink on cream paper, like an old study": ("クリーム色の紙に茶色のインク。古い習作のように",
                                                    "米色纸上的棕色墨，像旧习作", "크림색 종이에 갈색 잉크. 오래된 습작처럼"),
    "Kraft + White Chalk": ("クラフト紙＋白チョーク", "牛皮纸＋白粉笔", "크라프트지 + 흰 분필"),
    "Dark ink and white chalk highlights on brown paper": ("茶色の紙に黒インクと白チョークのハイライト",
                                                           "棕色纸上的深色墨和白色粉笔高光", "갈색 종이에 검은 잉크와 흰 분필 하이라이트"),
    "Toned Grey + Chalk": ("グレーの色紙＋チョーク", "灰色纸＋粉笔", "회색 색지 + 분필"),
    "Dark ink and white chalk highlights on grey paper": ("グレーの紙に黒インクと白チョークのハイライト",
                                                          "灰色纸上的深色墨和白色粉笔高光", "회색 종이에 검은 잉크와 흰 분필 하이라이트"),
    "Notebook": ("ノート", "笔记本", "노트"),
    "Blue ballpoint ink on ruled notebook paper": ("罫線ノートに青いボールペン", "横格本上的蓝色圆珠笔",
                                                  "줄 노트에 파란 볼펜"),
    "Blueprint": ("青焼き（ブループリント）", "蓝图", "청사진"),
    "White lines on blueprint blue": ("青焼きの青に白い線", "蓝图底色上的白线", "청사진 파랑 위의 흰 선"),
    "Chalkboard": ("黒板", "黑板", "칠판"),
    "Chalk lines on a green-black board": ("深緑の黒板にチョークの線", "墨绿黑板上的粉笔线", "짙은 녹색 칠판에 분필 선"),
    "Ink + Watercolour": ("ペン＋淡彩", "钢笔淡彩", "펜 + 담채"),
    "Ink drawing with a light watercolour tint of the model's colours": ("ペン画に、モデルの色で淡い水彩をのせます",
                                                                        "钢笔画上用模型自身颜色淡淡上一层水彩",
                                                                        "펜화에 모델 색으로 연한 수채를 올립니다"),
}

# operators: label and tooltip (registered under "Operator" and "*")
OPS = {
    "Make It Senga": ("線画にする", "变成线画", "선화로 만들기"),
    "Setup render, sketch shader, ink outlines, contour lines and paper in one click (whole scene, or only the "
    "selection when 'Selected Objects Only' is on)":
        ("レンダー設定・線画シェーダー・インクのアウトライン・輪郭線・紙をワンクリックで（シーン全体、または"
         "「選択中のオブジェクトのみ」がオンなら選択だけ）",
         "一键完成渲染设置、线画着色器、墨线描边、轮廓线和纸张（整个场景；勾选「仅选中物体」时只处理选中）",
         "렌더 설정·선화 셰이더·잉크 외곽선·윤곽선·종이를 원클릭으로 (씬 전체, 「선택한 오브젝트만」이 켜져 있으면 선택만)"),
    "Shuffle": ("シャッフル", "随机一下", "셔플"),
    "New variation: hatch angle, spacing, wobble, line breakup, edge fade and paper shade are re-rolled around "
    "the current medium and paper":
        ("新しいバリエーション：いまの画材と紙のまま、線の角度・間隔・揺れ・かすれ・端のフェード・紙の色味を振り直します",
         "新变体：在当前画材和纸张基础上重新随机排线角度、间距、抖动、断笔、边缘淡出和纸色",
         "새 변형: 현재 재료와 종이를 유지한 채 해칭 각도·간격·흔들림·끊김·가장자리 페이드·종이 색조를 다시 뽑습니다"),
    "Revert Sketch": ("線画を元に戻す", "还原", "선화 되돌리기"),
    "Restore original materials, remove outlines and restore compositor / render settings (whole scene, or only "
    "the selection when 'Selected Objects Only' is on)":
        ("元のマテリアルに戻し、アウトラインを削除し、コンポジターとレンダー設定を元に戻します（シーン全体、または選択だけ）",
         "恢复原材质，删除描边，并恢复合成器和渲染设置（整个场景，或仅选中物体）",
         "원래 머티리얼로 되돌리고 외곽선을 지우며 합성기·렌더 설정을 복원합니다 (씬 전체 또는 선택만)"),
    "Reset to Defaults": ("初期値に戻す", "恢复默认", "기본값으로"),
    "Every setting back to its default (Manga Pen on Sketchbook paper)": ("すべての設定を初期値に（スケッチブックにマンガのペン）",
                                                                          "所有设置恢复默认（速写本＋漫画钢笔）",
                                                                          "모든 설정을 기본값으로 (스케치북 + 만화 펜)"),
    "Setup Render": ("レンダー設定", "渲染设置", "렌더 설정"),
    "EEVEE, Standard view transform, transparent film (the paper is drawn by the compositor), key light. "
    "Previous settings are restored by Revert":
        ("EEVEE・ビュー変換「標準」・透過フィルム（紙はコンポジターで描きます）・キーライト。元に戻すで以前の設定に戻ります",
         "EEVEE、视图变换「标准」、透明胶片（纸张由合成器绘制）、主光源。还原时恢复之前的设置",
         "EEVEE, 뷰 변환 「표준」, 투명 필름 (종이는 합성기로 그림), 키 라이트. 되돌리기로 이전 설정 복원"),
    "Apply Sketch Shader": ("線画シェーダーを適用", "应用线画着色器", "선화 셰이더 적용"),
    "Convert the materials of the selected objects (or all visible) to the sketch shader":
        ("選択中（なければ表示中すべて）のオブジェクトのマテリアルを線画シェーダーにします",
         "把选中物体（未选中则所有可见物体）的材质换成线画着色器",
         "선택한 오브젝트 (없으면 보이는 전부)의 머티리얼을 선화 셰이더로 바꿉니다"),
    "Add Ink Outlines": ("インクのアウトラインを追加", "添加墨线描边", "잉크 외곽선 추가"),
    "Add hand-inked outlines (flat ground planes are skipped)": ("手描き風のアウトラインを追加します（平らな地面は除きます）",
                                                               "添加手绘墨线描边（跳过平坦的地面）",
                                                               "손으로 그린 듯한 외곽선을 추가합니다 (평평한 바닥은 제외)"),
    "Build Paper & Contours": ("紙と輪郭線を作成", "生成纸张和轮廓线", "종이와 윤곽선 만들기"),
    "Create the sketch compositor (the previous compositor is remembered for Revert)":
        ("線画のコンポジターを作ります（以前のコンポジターは元に戻すために記憶します）",
         "创建线画合成器（会记住之前的合成器以便还原）",
         "선화 합성기를 만듭니다 (이전 합성기는 되돌리기용으로 기억합니다)"),
    "Fit to Scene": ("シーンに合わせる", "适配场景", "씬에 맞추기"),
    "Set": ("設定", "设置", "설정"),
    "Choose this option": ("この項目を選びます", "选择此项", "이 항목을 선택합니다"),
}

# reports: English pattern -> template per language (ja, zh, ko)
REPORTS = [
    (r"Sketch look on (\d+) object\(s\)", ("{0} 個のオブジェクトを線画にしました", "已将 {0} 个物体变成线画",
                                           "오브젝트 {0}개를 선화로 만들었습니다")),
    (r"Nothing to draw: add or select a mesh, curve or text object",
     ("描くものがありません。メッシュ・カーブ・テキストを追加または選択してください", "没有可画的物体：请添加或选择网格、曲线或文字",
      "그릴 것이 없습니다. 메시·커브·텍스트를 추가하거나 선택하세요")),
    (r"Reverted (\d+) material\(s\)", ("{0} 個のマテリアルを元に戻しました", "已还原 {0} 个材质", "머티리얼 {0}개를 되돌렸습니다")),
    (r"Variation (\d+)", ("バリエーション {0}", "变体 {0}", "변형 {0}")),
    (r"Render ready \(Light Scale ([\d.]+)\)", ("レンダー準備完了（ライトスケール {0}）", "渲染就绪（光照比例 {0}）",
                                                "렌더 준비 완료 (라이트 스케일 {0})")),
    (r"No light in the scene: added 'Senga Key Sun'", ("シーンにライトがないので「Senga Key Sun」を追加しました",
                                                       "场景没有灯光：已添加「Senga Key Sun」",
                                                       "씬에 라이트가 없어 「Senga Key Sun」을 추가했습니다")),
    (r"Sketch shader on (\d+) material\(s\)(.*)", ("{0} 個のマテリアルに線画シェーダーを適用{1}", "已对 {0} 个材质应用线画着色器{1}",
                                                    "머티리얼 {0}개에 선화 셰이더 적용{1}")),
    (r"Outline on (\d+) object\(s\)", ("{0} 個のオブジェクトにアウトライン", "已为 {0} 个物体添加描边",
                                       "오브젝트 {0}개에 외곽선")),
    (r"Fitted: object size ([\d.]+), camera distance ([\d.]+)", ("調整しました：大きさ {0}、カメラ距離 {1}",
                                                                 "已适配：物体大小 {0}，相机距离 {1}",
                                                                 "맞췄습니다: 크기 {0}, 카메라 거리 {1}")),
    (r"No measurable objects", ("測れるオブジェクトがありません", "没有可测量的物体", "측정할 오브젝트가 없습니다")),
]

LANGS = ("JA", "ZH", "KO")
_IDX = {"JA": 0, "ZH": 1, "KO": 2}


def prefs(context=None):
    try:
        addon = (context or bpy.context).preferences.addons.get(PACKAGE)
        return addon.preferences if addon else None
    except AttributeError:
        return None


def language():
    """EN / JA / ZH / KO for the panel: the 🌐 choice, else Blender's own language."""
    p = prefs()
    choice = getattr(p, "ui_language", "AUTO") if p else "AUTO"
    if choice != "AUTO":
        return choice
    view = bpy.context.preferences.view
    if not view.use_translate_interface:
        return "EN"
    loc = bpy.app.translations.locale or ""
    if loc.startswith("ja"):
        return "JA"
    if loc.startswith("zh_HANS") or loc.startswith("zh_CN"):
        return "ZH"
    if loc.startswith("ko"):
        return "KO"
    return "EN"


def t(msg):
    """Panel text in the chosen language. Draw it with translate=False so Blender leaves it alone."""
    lang = language()
    if lang == "EN":
        return msg
    row = UI.get(msg) or OPS.get(msg)
    return row[_IDX[lang]] if row else msg


def report(msg):
    lang = language()
    if lang == "EN":
        return msg
    for pattern, templates in REPORTS:
        m = re.fullmatch(pattern, msg)
        if m:
            return templates[_IDX[lang]].format(*m.groups())
    return msg


class SengaPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE
    ui_language: bpy.props.EnumProperty(
        name="UI Language", default="AUTO",
        description="Language of the Senga Sketch panel. Automatic follows Blender's own language",
        items=[("AUTO", "Auto", "Automatic (follow Blender)"), ("EN", "English", ""), ("JA", "日本語", ""),
               ("ZH", "简体中文", ""), ("KO", "한국어", "")])

    def draw(self, context):
        self.layout.prop(self, "ui_language")


def _dictionary():
    out = {"ja_JP": {}, "zh_HANS": {}, "ko_KR": {}}
    for table, ctxs in ((UI, ("*",)), (OPS, ("Operator", "*"))):
        for msg, row in table.items():
            for loc, text in zip(("ja_JP", "zh_HANS", "ko_KR"), row):
                for c in ctxs:
                    out[loc][(c, msg)] = text
    out["zh_CN"] = out["zh_HANS"]
    out["ja"] = out["ja_JP"]
    return out


def register():
    bpy.utils.register_class(SengaPreferences)
    try:
        bpy.app.translations.register(PACKAGE, _dictionary())
    except ValueError:
        bpy.app.translations.unregister(PACKAGE)
        bpy.app.translations.register(PACKAGE, _dictionary())


def unregister():
    try:
        bpy.app.translations.unregister(PACKAGE)
    except ValueError:
        pass
    bpy.utils.unregister_class(SengaPreferences)
