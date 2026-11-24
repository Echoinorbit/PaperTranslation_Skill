# Open-Canopy 全文翻译测试

[打开 25 页中文 PDF](Open-Canopy-CVPR2025-zh-CN.pdf) · [打开本轮英文输入](../CVPR2025-Open-Canopy-arXiv-v4.pdf) · [并排查看第 7 页](page-07-comparison.png)

Fajwel Fogel 等人的 *Open-Canopy: Towards Very High Resolution Forest Monitoring* 收录于 CVPR 2025 主会，第 1395–1406 页。本轮使用 2024 年 12 月 11 日提交的 arXiv v4，以便一次测试论文及随附的补充材料。这里的页码、参考文献序号和图注均以这份作者版为准。论文采用 CC BY 4.0，作者与来源列于译本首页。附录所述的 Etalab 开放许可证 2.0 适用于研究数据集。[会议出版版](https://openaccess.thecvf.com/content/CVPR2025/papers/Fogel_Open-Canopy_Towards_Very_High_Resolution_Forest_Monitoring_CVPR_2025_paper.pdf) · [作者版本](https://arxiv.org/abs/2407.09392v4) · [论文许可](https://creativecommons.org/licenses/by/4.0/)

## 翻译范围和版面

| 原页和译页 | 内容 | 阅读时可以核对的地方 |
| --- | --- | --- |
| 1–8 | 摘要、方法、实验和结论开头 | 主文的图 1–6 和表 1–6 保留原始影像、线条、数值及缩写。中文解释跟随对应图表。第 7 页展示各树高区间的误差分布。 |
| 9–12 | 结论末段及参考文献 | 77 条书目保留英文著录和原编号，每条附中文题名。第 9–11 页的中文题名索引排在对应栏底，第 12 页排在书目右侧。 |
| 13–25 | 补充实验、公式、数据集和问答说明书 | 图 A–F、表 A–D、式 (A) 都在对应源页。第 19 页保留三组森林变化图，第 20 页接回数据文件目录，第 25 页列出获取和联系信息。 |

逐页结构检查覆盖 495 个源文本块和 187 个排印条目。25 张译页分别对应 25 张源页，纸张尺寸相同，译文在段内重新换行。每个源块认领一次，每个排印条目均已落位，记录的排版矩形无越界或超过 1 平方点的相交。核对中文书目索引的实际字号，第 9–11 页为 8.6 磅，第 12 页为 9.1 磅。图表原有的英文标签和单位保留在图内，中文释义排在图旁。部分网页地址以可复制文字呈现，原 PDF 的链接点击区域未全部保留。[排版核对数据](Open-Canopy-CVPR2025-zh-CN.qa.json) · [逐项译文与源块对应清单](translation.json)

## 原文中影响阅读的差异

用成品 PDF 再次抽取各页文字后，各条译文的连续汉字均可在对应页找到。7 个书目栏内的原始著录与源栏逐字一致（忽略空白），中文题名编号从 1 连续到 77。复核 32 个图、表、公式和书目裁切区时，将源区按译页位置与比例渲染，再与译页对照。在 1.5 倍灰度图上，31 区无像素差超过 16 个灰度级。其余一处为补充材料图 C，185,500 个像素中有 40 个超过该阈值，目视检查可辨认全部面板和图例。

| 作者版位置 | 作者版文字与实际内容 | 译文处理 |
| --- | --- | --- |
| 第 1 页图 1 | 图注将模型写作 PVPTv2，正文和文献 [72] 采用 PVTv2。 | 模型名写作 PVTv2，就近标明原图注拼写。 |
| 第 5 页图 4 | 图注描述上下两行，并提到 UNet 的误差超过 20 m。该版仅有一排面板，面板 (c) 标为 ViT-B。 | 中文图注分别交代原作者表述和可见面板，保留图上误差数值。 |
| 第 8 页图 6 | 图注将全球森林变化产品（GFC）的变化图写成 (c)，面板标为 (e)。 | 图旁译注给出两种标记。 |
| 第 20、23、24 页 | 第 20 页的文件说明把最小面积单位写作 m。第 23、24 页的数据说明书以 km² 描述缓冲区，E.1 节按宽度 1 km 描述。 | 分别标明原处写法与同一论文中的参照位置。 |

## 复现

原文 SHA-256 为 `57cc76a9da348b891efd45a4360c18335ba0544a343a012be31ea7f5fa3bc6b0`。在本仓库根目录，使用可导入 PyMuPDF 的 Python 和一个新的工作目录运行以下 PowerShell 命令。此次实测使用 Python 3.12.14、PyMuPDF 1.28.2。

```powershell
$source = 'Paper_Translation_Stimulation/CVPR2025-Open-Canopy-arXiv-v4.pdf'
$work = '.work/reproduce-open-canopy'
$paper = 'skills/translate-paper-zh/scripts/paper.py'
python $paper prepare $source $work
Copy-Item 'Paper_Translation_Stimulation/round-02-Open-Canopy/translation.json' "$work/translation.json"
python $paper render $source $work "$work/Open-Canopy-zh.pdf"
```
