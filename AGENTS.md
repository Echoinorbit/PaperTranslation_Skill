# 论文翻译与精读手稿

在本仓库翻译论文时，先读 [翻译 Skill](skills/translate-paper-zh/SKILL.md)。写页边手记前，读取[精读手记规范](skills/translate-paper-zh/references/reading-voice.md)。这份规范供各 Agent 共用，每次以仓库中的版本为准。

英文期刊文章、会议论文和预印本均从同一 PDF 入口开始。依本页文字层、栏型、方向和插图判断读序，按照作者实际使用的证明、观测、实验或文献材料写手记。遇到生僻版式和扫描页，先看原页再确定如何续排。

当前 Agent 负责读原文、翻译、撰写手记并核对出处。默认交付一份卡其纸中文精读手稿 PDF。先运行 `paper.py prepare` 并填写译文，再用 `paper.py render` 的 `--notebook-paper` 选项排出文楷正文。核对译文、原图颜色与图例后，在这份实际底本上定位笔记，运行 `annotate.py` 时同时传入 `--uniform-margin --notebook-paper`。[翻译清单](skills/translate-paper-zh/references/manifest.md) · [手记清单](skills/translate-paper-zh/references/reading-notes.md)

用悠哉写中文短句、用 Caveat 写英文短词，数字和易混标识用正体。圈划指向译文同页的具体词句、式子或数据格，小图和就地短句落在附近空白，较长的推理放到页边。对照原页检查遥感影像、连续色标、图例与表格，确保墨迹和底纹都没有遮住待辨认的内容。
