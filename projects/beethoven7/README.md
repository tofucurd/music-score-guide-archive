# 贝多芬第七交响曲

本目录保存最终 **sync-revision10** 全曲同步工程，使用当前 `.score-sync/m1` 至 `m4` 的正式快照。四乐章各保留八项运行输入：`score.json`、`score.svg`、`geometry.json`、`alignment.json`、`audio.json`、`labels.json`、`materials.json`、`structure.json`。当前第二乐章 SVG 已含 notation09 的24处beam、9处slur隐藏及 Ob75 文字修复；第四乐章已含最后同步修订。未附旧方案、预览、增量修正脚本、历史chunks、视频、音频、PDF、位图或最终封面SVG。

本次仅做静态选择、哈希、压缩及路径整理，未运行解压恢复入口、渲染、对齐、播放、声学校验或测试。最终记录来自已保存的正式交付元数据，不是本次重新验证的结果。

## 文件与恢复

`inventory.json` 按目标相对路径列出全部归档输入、压缩存储路径、未压缩字节数和 SHA-256。大 JSON、刻谱 SVG 和四份修订 MusicXML 使用标准 gzip 压缩；未来恢复时将 `archive_path` 解压到 `path`，保留原字节。四份 `score.json` 中的私人绝对项目路径已改为相对 PDF 路径；清单同时记录修改前哈希。其他正式快照数据未改变。

`derived/m1.musicxml` 至 `m4.musicxml` 为修订源谱出处，冻结视频复现应直接使用已保存的 score.svg/geometry/alignment，不要重新刻谱或重新对齐覆盖正式快照。`source_route` 保留原演奏重复路线，不能按数字去重。

`project.json` 保留作品、乐章、source_route、录音相对路径、最终60fps/2160p设置及封面选择；去除了预览参数和历史报告引用。共享代码与字体由仓库统一的 `vendor/score-sync-video` 和公共 runner 提供，此目录不重复打包 skill。

## 外置素材

`sources.json` 给出四个原 FLAC 和一份 IMSLP/Unger PDF 的准确文件名、字节数和 SHA-256。原录音为 Teodor Currentzis / musicAeterna 的 Beethoven Symphony No.7 (2021)，四个立体声96kHz/24bit轨道。请从合法持有者取得**相同文件**，按清单放回 `materials/` 中的相对位置；其他发行版即使曲名相同也不能替代。总谱 PDF 用于出处核对，已有冻结画面不需重读PDF刻谱。

每乐章 `audio.json` 保留原音频输入哈希、准备后 WAV 哈希、样本数和 FFmpeg decode-only 配方。未来公共runner应先由原FLAC按该配方生成 `.score-sync/mN/audio.wav`，不做归一化、拉伸或重新剪辑。本归档没有执行音频生成。

## 未来单入口调用约定

使用仓库公共 runner 的 **恢复冻结快照 → 按 audio.json 准备音频 → 全量渲染冻结数据 → 按乐章章节封装**流程，并指定此目录的 `project.json`。本包没有依赖已清理旧chunks的 `render_correction.py`，也不应调用会重新执行 alignment/engraving 的整套 prepare。具体命令见仓库根 README：`python archive.py restore/prepare-audio/render/covers beethoven7`。

封面单独使用 `code/build_reference_cover.py`，从当前 M1 原生刻谱选取第67—76小节（16:9）或67—74小节（4:3），声部 `P1:1/P4:1/P11:1`，`sample_q=266.08`。`cover-parameters.json` 保存尺寸与文案，正确中文为“库伦齐斯指挥”。脚本默认从仓库 `vendor/score-sync-video/scripts` 导入，也支持 `SCORE_SYNC_VENDOR` 环境变量覆盖共享代码根目录；此脚本未执行。

## 最终交付记录与范围

`delivery-record.json` 保留正式交付文件哈希、流参数及四章章节。正式交付为 `output/曲谱同步-2160p-同步修正版.mov`，144122帧，3840×2160、60fps、HEVC Rext / yuv444p10le，音频 ALAC 96kHz/24bit立体声。视频约2402.033333秒，音频230594560样本、约2402.026667秒；这是保存记录中的帧取整关系，不应擅自加入静音或拉伸音频。

最终M4 alignment SHA-256：`1c393eca6b0b59b95a45ad2b67c6a46871c2482a8e02276f8d7fa4e4ffdcc2be`。

当前所需32项正式快照均已保存，没有发现类似马九最终着色映射丢失的缺口。原素材、共享代码和字体按归档设计外置；公共runner对冻结快照的集成尚未执行，也没有声称在新环境可得到逐字节相同的压缩视频。
