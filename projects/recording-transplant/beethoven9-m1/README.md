# 贝多芬第九交响曲第一乐章速度移植

**共同粗钟＋02（学习型声学匹配＋全曲单调解码）**

成片中的乐器声音全部来自滕斯泰特 1992 年指挥伦敦爱乐乐团的录音。富特文格勒 1942 年的演出提供时间参考，制作使用 Pristine PASC 250 转录。下表列出定稿实际使用的数据。

| 制作环节 | 定稿依据 |
|---|---|
| 对齐 | 两份原录音从 254 个粗时间对应点起步。声学模型估计候选位置及无匹配概率，三状态时序模型在全乐章上解码，得到 8,418 个严格递增的时间对应点。代码和两份冻结权重在 `clock/`。 |
| 变速 | Rubber Band R3 3.3.0 使用 2,935 个含首尾的引擎关键点，对原始立体声一次变速。定稿选择直接输出。声音来源从采样 0 取至 44,545,277（右端不含），输出为 45,647,777 个采样帧，44.1 kHz，24 位双声道。 |
| 画面 | 成片以 3 秒静默海报开场，随后显示两个全乐章速度图。富特文格勒、滕斯泰特、移植共用四个四分音符的测速窗口。相对速度以富特文格勒为零线。游标和双层曲式导航跟随移植音频的实测时间。 |
| 封面 | 最新双人肖像插画、思源黑体标题和两种画幅的排版代码。两种封面分别为 3840 × 2160 和 2880 × 2160。 |

## 自备录音

将两个原始 FLAC 放在同一个外部素材目录，分别命名为 `tennstedt.flac` 和 `furtwangler.flac`。文件名可以调整为这两个名称，文件内容须与[录音标签及指纹](sources.json)一致。音频通过文件指纹识别。

## 重建成片

以下命令从仓库根目录执行。定稿使用 Linux、Python 3.12、Rubber Band CLI、libsndfile、FFmpeg、Cairo、Fontconfig 和 librsvg 2.0 的 GObject 绑定。Python 需能导入 `numpy`、`soundfile`、`PIL`、`gi`、`cairo` 和 `av`。PyAV 需支持 libx264，FFmpeg 需支持 ALAC。正式渲染环境的版本见[交付记录](data/release.json)。

```sh
project=recording-transplant/beethoven9-m1
python archive.py show-inputs "$project"
python archive.py restore "$project"
python archive.py prepare-audio "$project" --sources /path/to/recordings
python archive.py render "$project" --workers 5
```

准备音频直接读取定稿映射。视频采用 3840 × 2160、60 fps、H.264 画面和 ALAC 音轨，默认五路并行。静默海报、成片及封面均写到 `workspaces/recording-transplant/beethoven9-m1/output/定稿/`。可通过环境变量 `FFMPEG` 指定封装程序。

原始母带的 FLAC 和解码后 24 位 PCM 各有独立指纹。若 FLAC 字节不同，准备程序会比较 PCM 并报告结果。不同 Rubber Band 构建可能产生数值差异，编码器也会影响最终 MOV 的文件指纹。

## 重建封面

封面仅需 FontTools、rsvg-convert、ImageMagick 7 和仓库内的图层与字体。可以独立执行：

```sh
python archive.py covers recording-transplant/beethoven9-m1
```

## 查看或重新运行对齐

定稿的初始粗钟在 `data/initial.csv`，最终原音到目标时间的映射在 `data/command.csv`，传给 Rubber Band 的逐采样关键点在 `data/engine-keyframes.txt`。需要研究对齐模型时，可用同一对录音、同一初始粗钟和冻结权重重新拟合。此步骤还需要 SciPy。

```sh
python projects/recording-transplant/beethoven9-m1/archive.py refit --sources /path/to/recordings
```

重新拟合的映射和后验区间写入工作区的 `refit/`。原定稿的模型、输入与输出指纹见[拟合记录](data/fit.json)，一次变速的采样范围、参数、增益与文件指纹见[音频记录](data/receipt.json)。

本次归档核对了定稿文件与渲染输入的指纹，未执行端到端重建。仓库分发工程源码、冻结参数、测速数据及封面排版素材。原始录音、移植音频和成片由使用者在本地提供或生成。
