# 马勒第九交响曲第四乐章 · 导赏版

归档 **production-04（2026-11-07）** 的最终工程。录音为 Bruno Walter / Columbia Symphony Orchestra，沿用原马九项目的第四乐章录音与用户最终选择的旧 alignment。最终规格为 3840×2160、60fps、75,845 帧，HEVC 10bit 4:4:4、NVENC p7/hq、CQ16、25 Mbps 码率上限；原声 ALAC 96kHz/24bit 双声道，121,351,268 样本，约 21 分 04 秒。

只归档代码、配置及重建所需的冻结数据，**不包含视频、封面图片、录音、PDF、预览、分块或缓存**。本次仅整理最终依赖并检查隐私，**没有运行恢复、音频解码、渲染或重建测试**。

## 保存的最终状态

- 完整录音时间映射、音符身份和原生谱面几何，不重新对齐或刻谱。
- 全篇导赏文案、阅读阶段、原生对照谱例、材料颜色、标签锚点、连线窗口与完整路由参考帧。
- 52px 右栏正文、增量文字过渡、持续语义色、紧凑纵向排版、同步标签/连线寿命、最上层蓝游标。
- PDF 对应的双层导航、常驻谱号/调号、小节/排练号与实际声部布局。
- 最后采用的标签合行、动机2上移修订；两处“长笛”改为“双簧管”，见 [勘误](text-errata.json)。
- 16:9 与 4:3 封面的冻结场景和 renderer：纸色、细字重 IX、“第四乐章导赏”，本乐章第3–10小节第一小提琴/中提琴/大提琴原生谱例。

[inventory.json](inventory.json) 列出唯一最终版本的文件。较大的 JSON/SVG 用标准 gzip 保存：它们是重建用的场景、曲谱与排版数据，并非已渲染的媒体。`snapshot/output/production-04/queue/template.json.gz` 内包含实际使用的完整导赏 compositor 和最终画面配置，帧数组为空；未带入历史队列、旧候选及其覆盖链。目录中保留少量原 `research/` 路径，以保持最终 renderer 的相对 import 不变，不代表发布实验版本。

[guide-content.json](guide-content.json) 是可直接阅读的最终文案与来源页码索引；原始 PDF 不随仓库分发。[delivery-record.json](delivery-record.json) 记录已有最终成片的规格、指纹和当时的核验结果，不代表此次归档做过新的复现检查。

## 重建入口

环境依赖见仓库根 README。项目同时保存实际生产 engine 的 `requirements.lock`；Node.js 22+、FFmpeg/FFprobe、Chromium 可从 PATH 查找，`SCORE_SYNC_CHROME` 可指定浏览器。正式渲染需要支持 HEVC 10bit 4:4:4 的 NVIDIA NVENC，不会自动换成420。共享字体与仓库已有字体字节相同，恢复时按哈希复制，不重复归档。

在仓库根运行：

```bash
python archive.py show-inputs mahler9-mvt4-illustration
python archive.py restore mahler9-mvt4-illustration

python archive.py prepare-audio mahler9-mvt4-illustration \
  --sources /path/to/external-source-root
python archive.py render mahler9-mvt4-illustration --workers 5
python archive.py covers mahler9-mvt4-illustration
```

外部目录需包含 `materials/audio/4th Movement Adagio.dsf`，文件指纹见 [sources.json](sources.json)。使用相同指挥的另一发行版不能保证时间匹配。音频仅使用冻结的 DSD→96kHz PCM 解码配方，无增益、裁切、归一化或时间伸缩；音频文件不上传。封面只需恢复快照，不必准备音频。

输出到被 Git 忽略的 `workspaces/mahler9-mvt4-illustration/output/`。公共入口重建全部43块，不依赖原生产时复用的42块。默认1路，`--workers 1…5` 可调整并发；此入口不自动测量内存或管理远端服务，资源不足时自行降低。按绝对录音时间生成帧，切块沿用完整连线路由组件和固定参考帧。中断后重新运行会继续采用当前快照绑定的已完成块；改变快照后需使用新的输出目录或清理旧块，不能混用。

## 归档边界

冻结配置已经包含最终谱面、文案和标注，恢复画面不需要读取 PDF 或重新调用导赏编译器。原始乐谱/导赏 PDF 仅列来源标签与哈希，用于使用者自行核对。第三方文案及谱例保留原有权利，不因归档而改成 MIT 授权。

只匿名化机器路径、删除服务器配置并更新受影响的源文件绑定，没有重算任何音乐时间、文字位置或配色。音频的源文件哈希与 PCM 摘要保留；不同 FFmpeg、GPU 驱动可能生成不同容器或压缩码流哈希。

此工程拥有自己的完整第四乐章导赏映射，**不补齐旧 [马九全曲项目](../mahler9/README.md) 已明确披露的最终配色缺口**。也不自动升级到后来发布的通用 skill，以免改变此片已定稿的行为。通用实现另见 [score-sync-video v1.1.0](https://github.com/tofucurd/score-sync-video/tree/v1.1.0)。
