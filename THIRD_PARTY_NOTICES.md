# 第三方说明

根目录MIT许可适用于本项目代码和原创说明，不覆盖录音、原始PDF、第三方字体及源谱资料的既有权利。

## 思源宋体

`vendor/score-sync-video/assets/fonts/SourceHanSerifSC-*.otf` 为Adobe Source Han Serif 2.003，采用SIL Open Font License 1.1。完整原许可位于同目录 `LICENSE.txt`。

## 刻谱与字形

Verovio采用LGPLv3，工具本身通过依赖安装，不在仓库附带二进制。冻结刻谱SVG含生成的音乐字形，相关字体保留其上游OFL条款。见 https://www.verovio.org/ 及 https://github.com/rism-digital/verovio/blob/develop/fonts/README.md 。

贝九修订源来自OpenScore CC0版本，原XML权利声明保留。贝七和马九的修订数据及冻结刻谱按原谱源记录保存；原始参考PDF、录音不分发，来源及指纹见各项目素材清单。本仓库不会将第三方原资料重新授予MIT许可。

## 外部运行环境

Python依赖、Chromium、Node.js和FFmpeg沿用各自许可。FFmpeg的许可受编译组件影响，包括libx265。马九原刻谱使用的额外文字/音乐字体按其缺口清单由使用者自行合法取得，没有在本仓库分发。
