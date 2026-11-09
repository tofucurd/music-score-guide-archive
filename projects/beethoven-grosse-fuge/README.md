# 贝多芬《大赋格》Op.133 · 最终工程

录音：好莱坞弦乐四重奏，1957；所用发行标签为 **PACM082 — HOLLYWOOD QUARTET Beethoven: The Late Quartets (1957)**。音频仅有公开标签、指纹和处理配方，不随仓库分发。

归档状态：最终长连线修订 `spanner-visibility-04`，封面 `cover-revision-04`。本次只整理最终代码与配置，**未执行恢复、解码、对齐、渲染或端到端重建测试**。

## 包含什么

- OpenScore CC0 修订 MusicXML，最终原生 SVG/MEI、音符身份与几何；保留原作者和许可。
- 已审录音对齐、装饰音时刻、源小节与谱号调号标记、双层结构导航、全部材料归属及视觉补全。
- 58,868个绝对输出帧的冻结状态，包含镜头、声部、音符高亮和进度条。它们是可重渲的JSON配置，不是视频或图片。
- 最终普通谱面渲染器及其实际依赖，含原生长连线可见范围、混合连线与共享符杠的染色修正。
- 两比例封面场景与配方：作品号采用 `Op.133`，与 `GROSSE FUGE` 小字整体上移32像素。
- 曲式文献来源和阅读范围、材料参考视频身份、录音公开标签与外部素材指纹。

不含录音、原始PDF、参考视频、预览、封面PNG/JPG、成片、编码分块、旧版产物、废弃对齐候选、登录或渲染机配置。其他项目的冻结vendor代码未替换，本项目使用自己的最终renderer。

## 重建入口

在仓库根目录安装依赖后执行；这些是提供给使用者的命令，本次归档没有运行。

```bash
python archive.py show-inputs beethoven-grosse-fuge
python archive.py restore beethoven-grosse-fuge
python archive.py prepare-audio beethoven-grosse-fuge --sources /path/to/external-sources
python archive.py render beethoven-grosse-fuge --workers 5
python archive.py covers beethoven-grosse-fuge
```

外部素材根目录下需要 `materials/audio/Hollywood Quartet 1957.flac`，文件SHA-256必须匹配 `sources.json`。其他原始素材只用于查阅；冻结重渲和封面不要求再次取得PDF/MXL或参考视频。

程序恢复到 `workspaces/beethoven-grosse-fuge/`。正式视频输出在 `output/reproduced/`，封面在 `output/covers/`。封面不需要先准备音频。只重放最终状态，不重新对齐、刻谱或按最新skill重新编译材料；源数据也保存供进一步研究，但编辑它们不会自动改变已冻结的逐帧场景。

需要Node.js 22+、Chromium、FFmpeg/FFprobe在PATH，`SCORE_SYNC_CHROME`可指定浏览器。正式视频沿用NVENC HEVC 10bit 4:4:4、p7/hq、CQ16、25Mbps码率上限；需要支持该编码格式的NVIDIA环境，不静默降至4:2:0。字体子集已冻结在场景中，许可来自仓库vendor中的思源宋体OFL文件。

每个任务5秒，最后一个不足5秒；默认1路，最多允许7路。7路是原机器最终使用上限，不是所有机器都适合的默认值；Linux上每次增加任务前检查可用内存，RAM不足6GiB时先等待现有任务。只为活动任务生成临时场景，编码完成即删除临时JSON；保留分块及绑定receipt用于续渲。源图形不变形，不使用历史成片作为重建输入。

## 时钟与音频

原录音48kHz、24bit、双声道，46,988,160样本；输出前导105,600样本（2.2秒），总47,093,760样本。前导从原音频0.06–0.26秒的底噪采样，交叉淡化0.02秒、两端淡化0.12秒；原录音随后逐样本保留。原有alignment仍以原录音为零点，输出帧另带前导时间；不得再给alignment整体加2.2秒。

原生产只重做受影响的54个五秒片段，其余143段复用前版。公开入口从197个冻结帧区间完整渲染，不依赖这些未公开的旧chunks。音频最后无损封装为ALAC；视频58,868帧，音轨981.12秒。编解码器、驱动和运行库版本会影响压缩文件字节，保存配置不等于保证跨环境文件SHA一致。

## 来源和边界

源XML：OpenScore CC0，由markpearse转录自IMSLP/Dover谱；源声明保留在XML内。材料位置和同族配色关系参考Richard Atkinson的公开视频，实际配色及逐句补全由本工程审定；参考视频录音不能替代本项目音轨。

双层导航的文献与编辑判断见 `structure-sources.json`。保留原文献实际阅读范围、边界差异和本工程编辑处理，不能把某一种导航层级称为所有文献一致认定的唯一曲式。

`inventory.json`保存发布文件及未匿名化前的来源指纹。公开快照仅清除私人home路径并更新对应元数据绑定；音符、材料、几何、时刻和帧状态未重新计算。媒体交付记录在 `delivery-record.json`，本次归档不把历史成片检查冒充新环境复现结果。
