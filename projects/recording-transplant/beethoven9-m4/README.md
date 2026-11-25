# 贝多芬第九交响曲第四乐章速度移植

**15 全乐章多尺度声学对齐＋谱面音序复核＋乐句脉动约束（Rubber Band R3）＋打击乐分声部调整**

滕斯泰特 1992 年的演出提供全部乐器、人声和原始立体声声场。富特文格勒 1942 年的录音提供演绎时间与打击乐参照。项目按原谱比较两个演出的对应位置，将滕斯泰特的录音一次变速，再按谱中可辨认的击奏调整定音鼓、钹、三角铁与大鼓的起音。定稿母带是 44.1 kHz、24 位双声道，共 64,169,096 个采样帧。

## 从归档重建

从仓库根目录运行。先用第一条命令查看自备录音的发行信息与 SHA-256。将滕斯泰特的原始 FLAC 命名为 `tennstedt.flac`，放入外部素材目录。定稿已保存富特文格勒的时间测量和打击乐事件，有原始参考录音时可在同一目录放入 `furtwangler.flac` 核对指纹。

```sh
project=recording-transplant/beethoven9-m4
python archive.py show-inputs "$project"
python archive.py restore "$project"
python archive.py prepare-audio "$project" --sources /path/to/recordings
python archive.py render "$project" --workers 5
python archive.py covers "$project"
```

音频准备需要 Python 3.11 或以上、NumPy、SciPy、SoundFile/libsndfile，以及 Rubber Band CLI。发行工程使用 Rubber Band 4.0.0 的 R3 引擎。画面需要可用的 FFmpeg、PyAV/libx264、Pillow、Cairo、librsvg 的 GObject 绑定及 Fontconfig。单独运行封面命令需要 FontTools、rsvg-convert 和 ImageMagick 7。重建文件写入仓库的 `workspaces/recording-transplant/beethoven9-m4/`。

## 定稿保存了什么

| 制作环节 | 工程入口 |
|---|---|
| 全乐章时间映射 | [最终拟合方法与冻结观测](clock/README.md)。[连续时间映射](data/command.csv)给出滕斯泰特原音到目标时间的对应关系。[采样级关键点](data/engine-keyframes.txt)包含实际送入 R3 的 24,344 个内部位置，加上首尾共 24,346 点。 |
| 打击乐 | [逐音事件](data/percussion-events.csv)与[处理记录](data/percussion.json)保留了四个声部共 1,538 个采纳事件的击奏位置和调整依据。 |
| 播放画面 | [参考时间表](data/reference.csv)、[原音和移植实测时间表](data/learned-beat-fingerprints.csv)及[导航结构](data/structure.json)供渲染直接读取。全曲包含 943 小节，导航分为 7 个大段、35 个子段。三条曲线共用 4 个四分音符的测速窗口。上图并列富特文格勒、滕斯泰特和移植，下图以富特文格勒为零线。成片以 3 秒静默海报开场。 |
| 封面 | 标题为「滕斯泰特又遭夺舍LPO狂轰500BPM？！」。插画、字体与排版代码可分别生成 3840 × 2160 和 2880 × 2160 两种画幅。 |

如需研究最终时间映射，可单独复算第 15 版的拟合。命令会将新结果写到工作区的 `refit/`。成片重建始终读取归档的发行映射。

```sh
python projects/recording-transplant/beethoven9-m4/archive.py refit
```

[交付指纹](data/release.json)记录移植母带、4K60 成片和两张定稿 JPG 的 SHA-256。成片使用 H.264 和 ALAC。母带同时登记了解码为小端有符号 32 位 PCM 的指纹，便于区分音频内容与 FLAC 封装的差异。

本次归档从冻结观测复算了最终拟合，输出的 30,177 对时间坐标和 24,344 对内部采样键均与定稿逐字节一致。母带和成片沿用原交付指纹，本次未重新渲染。原录音由使用者自备。
