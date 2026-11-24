# 英文论文翻译测试样本

项目测试过八篇论文。最初五篇视觉与遥感论文合计 80 页，另三篇气象水文、地学观测和数学论文合计 24 页。这里可下载 Open-Canopy 与三篇跨学科论文的英文原稿及中文手稿。首轮四篇出版版提供官方入口、测试页码和实测数据。页码从各 PDF 首页算起。[论文署名、来源与改编说明 / Sources and credits](SOURCES.md)

**第 8 轮 · 跨学科论文。** 三篇新原稿逐页做了版面预检，各选一页制作卡其纸中文手稿。

| 论文 | 原稿 | 中文样页及所检验的问题 |
| --- | --- | --- |
| MetSim 气象水文软件 | [6 页英文原版](round-08-cross-domain/originals/MetSim-JOSS-2020.pdf) | [原第 2 页](round-08-cross-domain/joss-metsim-p02.pdf) · 单栏里的多面板图，逐日输入如何变为逐小时输出。[出处与许可](round-08-cross-domain/joss-metsim-source.md) |
| Proulx 等的积雪野外观测 | [8 页英文原版](round-08-cross-domain/originals/Proulx-snow-depth-2023.pdf) | [原第 5 页](round-08-cross-domain/geo-snow-depth-p05-zh-notes.pdf) · 跨栏散点图与右栏箱线图，逐点与按格取平均时样本单位如何变化。[出处与许可](round-08-cross-domain/geo-snow-depth-source.md) |
| Grinberg 的斐波那契恒等式 | [10 页英文原版](round-08-cross-domain/originals/Grinberg-Zeckendorf-brief.pdf) | [原第 1 页](round-08-cross-domain/math-zeckendorf-p01.pdf) · 检查公式、下标条件与存在唯一性的表述。[出处与版本](round-08-cross-domain/math-zeckendorf-source.md) |

**第 7 轮 · Open-Canopy 卡其纸精读手稿。** 全文与补充材料共 25 页。第 4 页可对照文楷正文与悠哉手记，看模型段旁如何就地画出从四波段影像到树高的预测流程。第 18 页并排比较 U-Net 和 PVTv2 在 RGB 与 RGB 加近红外两种输入下的误差。复核图色时可将遥感图、色标与下表的英文原页并排查看。[下载完整手稿](round-07-Open-Canopy/Open-Canopy-CVPR2025-卡其纸精读手稿.pdf) · [第 4 页样张](../docs/reading-notes/Open-Canopy-khaki-p04.png) · [本轮手记清单](round-07-Open-Canopy/notes.json)

第 4 轮白纸版在第 3、5、7、8、14、16、21 页各有一则研究手记，保留供前后对照。[第 4 轮中文阅读手稿](round-04-Open-Canopy/Open-Canopy-CVPR2025-阅读手稿.pdf) · [译文排版清单](round-03-Open-Canopy/translation.json) · [红黄蓝页边手记清单](round-04-Open-Canopy/notes.json)

| 文件 | 来源与版本 | 页数 | 建议测试页 |
| --- | --- | ---: | --- |
| [CVPR2025-Open-Canopy-arXiv-v4.pdf](CVPR2025-Open-Canopy-arXiv-v4.pdf) | CVPR 2025 主会，使用含补充材料的作者公开版本 arXiv v4。[会议出版版](https://openaccess.thecvf.com/content/CVPR2025/papers/Fogel_Open-Canopy_Towards_Very_High_Resolution_Forest_Monitoring_CVPR_2025_paper.pdf) · [作者版与许可](https://arxiv.org/abs/2407.09392v4) | 25 | 全部 25 页。含 77 条书目、多面板遥感图、林冠高度变化掩膜、按树高分组的误差表、公式和数据集说明书。[完整中文 PDF](round-02-Open-Canopy/Open-Canopy-CVPR2025-zh-CN.pdf) · [英文与中文同页对照](round-02-Open-Canopy/page-07-comparison.png) |
| SkySense | CVPR 2024，CVF 开放获取版。[CVF 原文](https://openaccess.thecvf.com/content/CVPR2024/papers/Guo_SkySense_A_Multi-Modal_Remote_Sensing_Foundation_Model_Towards_Universal_Interpretation_CVPR_2024_paper.pdf) | 12 | 第 1–2 页。引言中的 `capture` 拆成两页的 `cap-` 和 `ture`，第 2 页顶部还有表 1。检查译文能否还原整句并将表格与正文分开。 |
| DETR | ECCV 2020，ECVA 会议论文集公开版。[出版记录](https://link.springer.com/chapter/10.1007/978-3-030-58452-8_13) · [ECVA 原文](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123460205.pdf) | 17 | 第 5 页。第 3.1 节的公式 (1) 和相邻正文解释匈牙利匹配。检查排列索引、上下标和公式编号与译文的对应关系。 |
| GenCD | AAAI 2026，AAAI 官方论文集版。[AAAI 原文](https://ojs.aaai.org/index.php/AAAI/article/download/38262/42224) | 9 | 第 1 页。图 1 和摘要同页。检查跨栏阅读顺序、图注所指的三个维度，以及 GCD、GenCD 两个名称。 |
| SPGAN-DA | IEEE TGRS 2023，第 61 卷，作者网站提供的期刊排版版。[期刊记录](https://doi.org/10.1109/TGRS.2023.3313883) · [作者存档](https://te-shi.com/fiels/SPGAN-DA-TGRS.pdf) | 17 | 第 11 页。表 II–IV 并列比较三种域迁移设置。逐列核验地物类别、数值和加粗标记。例如表 II 的 SPGAN-DA 行，mIoU 应为 **53.31**。 |

TGRS 第 11 页也是覆盖率测试。在本地用 pypdf 和 PDFium 均能提取表题，按字符串查找却都没有读出表内的 `Impervious` 和 `53.31`。核对整页应结合实际渲染，表头、图内标签和图例都属于可见内容。

## 第 1 轮选页记录

| 论文 | 首轮本地实测的英文原页与译页数 |
| --- | --- |
| SkySense | 第 1–3 页，对应 4 张译页。 |
| DETR | 第 5–6 页，对应 2 张译页。 |
| GenCD | 第 1–2 页，对应 2 张译页。 |
| SPGAN-DA | 第 10–12 页，对应 3 张译页。 |

首轮在本地并排核对了十张英文源页和译页，包括 SkySense 第 3 页如何续排、SPGAN-DA 第 11 页三张表的列名和数值如何对应。公开记录保留逐页计数及固定页框路线的字号和公式对照结果。[逐页计数](round-01/coverage.csv) · [固定页框路线的实测报告](../docs/benchmark-upstream.md)
