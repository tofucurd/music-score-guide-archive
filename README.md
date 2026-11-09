# 曲谱同步最终工程存档

保存四个已经交付项目的最终工程状态。只收录实际采用的代码、冻结曲谱几何、录音时间映射、声部与材料配置、唱词排版和封面配方；不收录废弃方案、预览、渲染分块或最终媒体。

| 项目 | 录音 | 归档状态 |
|---|---|---|
| [贝多芬第七交响曲](projects/beethoven7/README.md) | Teodor Currentzis / musicAeterna，2021 | 最终同步修订10；正式快照齐备，未重新执行复现 |
| [贝多芬第九交响曲](projects/beethoven9/README.md) | Klaus Tennstedt / London Philharmonic Orchestra & Choir，1992-10-08 | production04，25 Mbps上限；含最终谱号标签、唱词与最新封面姓名，未重新执行复现 |
| [马勒第九交响曲](projects/mahler9/README.md) | Bruno Walter / Columbia Symphony Orchestra | 最终源码与可恢复数据；**最终配色映射存在已知缺口，不能完整精确复现** |
| [马九第四乐章导赏版](projects/mahler9-mvt4-illustration/README.md) | Bruno Walter / Columbia Symphony Orchestra | production-04；最终导赏、连线、标签、染色、对照谱例及双比例封面配置，未执行重建测试 |

未完成的马勒第二交响曲不在本仓库。

## 素材与结果的边界

音频仅保留公开音乐标签、文件 SHA-256、采样规格、裁切配方和样本章节。录音、原始PDF、成片、PNG/JPG封面、缓存及私有机器配置不随仓库分发。使用者需要自行持有 `sources.json` 指定的相同录音。相同曲目名称或同一指挥的另一发行版不能替代同一文件。

大体积的最终曲谱数据采用标准 gzip 保存，恢复时解压到独立的 `workspaces/`。这些是冻结的制作输入，不是播放用的媒体产物。恢复后直接使用已校准的时钟和原生谱面；不要重新对齐或重新刻谱覆盖它们。

本次整理只做文件选择、压缩、静态依赖梳理和隐私检查，**没有执行恢复、对齐、渲染或端到端复现测试**。贝七、贝九的快照齐备不等于本次已验证可运行；新加入的第四乐章导赏版也只做归档与隐私检查，未测试重建。具体限制见各项目说明。即使画面、时钟和PCM相同，不同编解码器、GPU驱动或字体版本也可能产生不同的压缩文件哈希。

## 将来使用

需要 Python 3.14、Node.js、FFmpeg/FFprobe、Chromium和 `requirements.txt` 中的依赖。项目的原工具版本写在对应环境记录中；`SCORE_SYNC_CHROME` 可指定浏览器。贝九及马九第四乐章导赏版正式编码需要支持 HEVC 10bit 4:4:4 的 NVIDIA NVENC，不能静默改成420。

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

python archive.py show-inputs beethoven7
python archive.py restore beethoven7
python archive.py prepare-audio beethoven7 --sources /path/to/external-source-root
python archive.py render beethoven7
python archive.py covers beethoven7

python archive.py show-inputs beethoven9
python archive.py restore beethoven9
python archive.py prepare-audio beethoven9 --sources /path/to/external-source-root
python archive.py render beethoven9
python archive.py covers beethoven9

python archive.py restore mahler9-mvt4-illustration
python archive.py prepare-audio mahler9-mvt4-illustration --sources /path/to/external-source-root
python archive.py render mahler9-mvt4-illustration --workers 5
python archive.py covers mahler9-mvt4-illustration
```

`--sources` 所指目录应包含清单中以 `materials/` 开头的相对路径。例如贝九的第一轨位于该目录下的 `materials/audio/m1.flac`。音频准备只解码和应用既定裁切，保留冻结谱面与时钟；输出位于 `workspaces/<project>/output/`。封面只需恢复快照，不必先准备音频。

公共入口以全量重渲替代旧项目的增量分块拼接，避免依赖未分发的历史chunks。该入口在本次整理中没有执行。原马九全曲项目因明确缺失最终映射，公共入口拒绝直接渲染；其原最终代码、恢复入口和缺口文件见项目目录。

## 目录

- `projects/`：四个最终工程的精简快照与外部素材清单。
- `vendor/score-sync-video/`：冻结的公共逐帧、导航、音频封装与封面代码，以及带OFL许可的思源宋体；不包含旧实验或对齐候选缓存。
- `archive.py`：显式恢复、音频准备、渲染和封面入口，导入时不会自动渲染。
- `MANIFEST.sha256`：本次公开归档文件指纹，不是端到端复现结果。
- `PRIVACY.md`：公开范围和隐私处理说明。

通用算法及远端队列另维护在 [score-sync-video](https://github.com/tofucurd/score-sync-video)。本仓库固定工程快照，不随skill升级自动重算时间映射。

代码与原创文档采用MIT；字体、刻谱字形及源谱数据保留各自许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。
