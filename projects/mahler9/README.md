# Mahler IX / Walter 连续曲谱同步最终工程

归档对象为已完成的 Walter 连续 3840×2160 / 60 fps 曲谱同步版本。最终渲染入口是 `work/score-sync-02/render_full.py`，`Frames` 为 `frame_params.py`，浏览器实际加载 `scene_noteink_stroke.mjs`，使用 `run_scene.mjs`；没有保留其他 scene 或 cursor 备选。封面仅保留最终制作代码（16:9、4:3），不附带任何成品。

本包是**最终工程的精简源码存档，尚未形成完整可复现闭包**。关键着色输入已在原项目清理时丢失；提供相同录音和字体仍不足以精确重现最终着色。缺口明确列在下文，不以近似映射冒充最终数据。本次仅读取、选择、压缩、写入和静态梳理，未执行复现、对齐、渲染或测试。

## 单入口与文件布局

先阅读本文件；将来需要恢复文本文件时，从本项目目录（`projects/mahler9/`）运行 `python3 archive.py restore`。此入口只解压清单内 JSON/MEI，不生成媒体。`restore-manifest.json` 给出每个目标相对路径、未压缩大小和 SHA-256。直接可读的代码与小数据位于原相对 `work/` 布局，较大的冻结数据以 `.gz` 存放。不要修改或重新对齐冻结 `timeline.json` 与四份 `data.json`。

`environment.json` 为最后冻结的工具版本。渲染要求 macOS、Google Chrome、Node、Python、FFmpeg/libx265，以及 numpy、scipy、Pillow；重建原生刻谱还需要 Verovio，封面需要 fontTools。原环境严格冻结，跨版本不能声称像素相同。原代码中的 `/Applications/Google Chrome.app/...` 为系统应用位置；工程与素材路径均相对。旧 trill 修复代码的私人 MXL 路径改为 `MAHLER9_M1_MXL`、`MAHLER9_M3_MXL` 环境变量。

## 原始素材与取得

没有分发音频、视频、位图、PDF、字体或最终封面 SVG。`external-inputs.json` 按原冻结记录给出所需外部文件和可重建几何文件的大小、SHA-256、目标相对路径。

* 录音：从合法持有者取得 Bruno Walter / Columbia Symphony Orchestra 的同一套四乐章 DSF。`work/revision-04/source-inventory/recording-native-clocks.json` 保留原文件名、DSF大小及源 SHA-256，放置为 `external/recordings/M1.dsf` 至 `M4.dsf`。本包不承诺其他发行版音频可替代。保留的 `recipe-candidate.json` 和 `prepare_audio.py` 是最终 96kHz/24bit 解码与无缝连接配方；四份 PCM 哈希、总样本数、连续 PCM 哈希见 `work/score-sync-01/audio/manifest.json`。优先从原制作方取得该清单中逐字节相同的 `Walter-full-96k24.m4a`。
* 字体：向有许可的持有者取得 Times-0..3.ttf，按清单哈希核对。不能按名称相同就认定等价。Leland.otf 可从 MuseScore/Leland 官方来源取得，Source Han Serif SC 可从 Adobe 官方 Source Han Serif 发布取得，仍须匹配清单哈希。封面另需思源宋体 Light、Medium；旧快照没有这两字重的已冻结哈希，版本需原作者补充。可以使用公共 vendor 字体目录的符号链接恢复原相对位置。
* 乐谱：四乐章最终 `normalized.mei` 已保存，是重建原生刻谱的直接输入，无需重新取得原始 MXL 才能使用这些冻结乐谱。若主动运行旧的上游 trill/MXL 配方，则必须另行提供其原始 MXL；本包不把该旧入口作为冻结 MEI 的必要步骤。

## 后续重建顺序（本次未执行）

1. 恢复压缩文本，按外部清单补齐录音和字体；保留所有已有源时间和事件 ID。
2. 用每乐章冻结 `canonical/M*/normalized.mei` 直接输入 Verovio。刻谱选项完整保留在 `build_canonical.py` 的 `options`：`xmlIdSeed=314159265`、`breaks=none`、`condense=none`、单系统、不重排staff、18000×60000、固定页边距等。应沿用该代码的 ID 前缀、measure 拆分、defs/style/system 拆分规则。原 `build_canonical.py` 的上游入口读取旧 projection/MEI，不应原样运行来覆盖冻结 normalized.mei；需将其刻谱输入接到冻结 MEI，并从现有 `source.json` 保留 selected_staves。`repair_svg` 的最终刻谱修复仍见 `trill_display.py`。本包没有实际执行此改接或验证重建几何。
3. 恢复 defs.svg、system.svg、measures/*.svg 后，可通过 `run_scene.mjs --geometry N --scene scene_noteink_stroke.mjs --output work/score-sync-02/canonical/MN/geometry-ink-final.json` 提取四份 geometry。清单包含原 geometry/native/measure 哈希，必须逐项核对；不同 Verovio/Chrome/字体版本可能不一致。
4. **必须先补回下面的最终着色映射。** 其后由制作人员重新冻结精简后的实际依赖，并重新批准视觉审阅，才能运行最终 `render_full.py`。保留的 `render-inputs.json` 是原历史冻结记录（含当时过度收集的备选文件），不是本精简包的现行运行清单；原 `visual-review.json` 的批准哈希也不能自动覆盖精简或移植后的工程。不要通过取消校验来掩盖缺口。
5. 封面制作代码位于 `covers/build_covers.py`、`render_covers.mjs`，使用同一原生刻谱 M1 第6—10小节与第二小提琴/中提琴/大提琴，字形细 IX。补齐其字体与刻谱依赖后另行制作。

## 尚缺的最终输入

最关键的是 `work/score-sync-02/assets/highlight-strands.json`：原大小 5,217,349 bytes，SHA-256 `caea2ebd67434ed4b12ca666d8ac6d0cbad7feae665cad38bc841e788232cdbf`。最终检查记录为72个strand、2200个strand事件、2662个display事件。应向原制作方/备份提供者索取**该精确文件**，恢复后 `frame_params.py` 只需要它的 `display_event_map`。

`recovery/strand-membership-evidence.json.gz` 是从最终72份逐strand记录静态摘取的事件成员、identity、slot、color和局部override；它保留可用的明确成员证据，但没有被改写为最终 display map。它不能覆盖至少462个strand之外的核心事件，也不能证明局部override以外的所有最终优先级。`recovery/build_highlight_manifest.py` 和配色决策是原构建配方备查；该配方还依赖未保存的 `theme-phrases.json`、最终合并 `representative-instances.json` 和四份 `events_ref`。三个独立候选代表动机文件不是最终合并结果，未混入最终工程。

已静态检查源码ZIP、原git对象路径及保存的帧配置：没有完整 final-render 帧配置；只有入口与pressure抽样配置，不能覆盖全曲颜色。原生SVG、geometry和部分字体缺失可依配方重建/补齐；**最终display映射缺口目前不能确定性恢复**。因此本包如实停在整理状态，不宣称已经可一键重现成片。
