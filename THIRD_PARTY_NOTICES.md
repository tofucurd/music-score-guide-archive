# 第三方说明

根目录MIT许可适用于本项目代码和原创说明，不覆盖录音、原始PDF、第三方字体及源谱资料的既有权利。

## 思源宋体

`vendor/score-sync-video/assets/fonts/SourceHanSerifSC-*.otf` 为Adobe Source Han Serif 2.003，采用SIL Open Font License 1.1。完整原许可位于同目录 `LICENSE.txt`。

## 刻谱与字形

Verovio采用LGPLv3，工具本身通过依赖安装，不在仓库附带二进制。冻结刻谱SVG含生成的音乐字形，相关字体保留其上游OFL条款。见 https://www.verovio.org/ 及 https://github.com/rism-digital/verovio/blob/develop/fonts/README.md 。

贝九修订源来自OpenScore CC0版本，原XML权利声明保留。贝七和马九的修订数据及冻结刻谱按原谱源记录保存；原始参考PDF、录音不分发，来源及指纹见各项目素材清单。本仓库不会将第三方原资料重新授予MIT许可。

## 外部运行环境

Python依赖、Chromium、Node.js和FFmpeg沿用各自许可。FFmpeg的许可受编译组件影响，包括libx265。马九原刻谱使用的额外文字/音乐字体按其缺口清单由使用者自行合法取得，没有在本仓库分发。

## 马九第四乐章导赏资料

该项目的原导赏 PDF 不分发，来源文件名与指纹见项目 sources.json。冻结导赏文案、原生谱例及和声/主题标注用于保存已交付工程，保留各自原有权利；本仓库 MIT 许可不向第三方文案、分析或谱例追加授权。使用或再次发布这些内容前，应自行确认其来源许可。项目代码和重建入口仍适用仓库代码许可。

## 贝多芬大赋格

修订MusicXML来自OpenScore CC0，保留转录者markpearse、作曲家和原谱来源声明。冻结SVG/MEI保留原生刻谱字形；嵌入的思源宋体子集沿用上述OFL许可。Richard Atkinson的公开视频只作为材料位置与色彩关系参考，原视频未分发；曲式文献只保留引文信息和本工程分析，不附带论文PDF。1957年Hollywood String Quartet录音不分发，使用者自行持有sources.json指定发行文件。第三方录音和文献不会因本仓库代码采用MIT而获得额外授权。
