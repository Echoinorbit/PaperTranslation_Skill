# 上游 PDF Translate Skill 的十页实测

2026-11-24。在 Windows 上以当前 Codex 翻译，使用 JiaJunDeng5930 的 PDF Translate Skill 回填。四篇论文共选 10 张源页，全部真实生成了中文页。四份摘录分别只含选中的 3、2、2、3 页。上游接受了 154 项译文，记录的翻译回退数为 0。回退数描述程序是否接受各项，中文字号、阅读顺序和公式仍需在译页上核对。下表记录上游的逐页测量。连续排版路线的源块覆盖和译页数量见首轮计数表。[固定上游版本](https://github.com/JiaJunDeng5930/PDF-translate-skill/tree/c0d55d172a722055bddfe5f442b7148e84c123cb) · [连续排版逐页计数](../Paper_Translation_Stimulation/round-01/coverage.csv)

| 摘录 | 物理源页 | 上游接受项数 | 逐页最小中文字号（pt） |
| --- | --- | ---: | --- |
| SkySense | 1、2、3 | 13、27、12 | 3.59、5.58、1.79 |
| DETR | 5、6 | 10、32 | 8.97、2.89 |
| GenCD | 1、2 | 14、17 | 5.98、7.97 |
| SPGAN-DA | 10、11、12 | 13、7、9 | 5.18、5.74、3.19 |

字号取 PDF 文字层中所有含汉字的文本片段的最小值，含图内标签与页眉。每页一次真实运行，使用共享中文材料按上游原有文本块切分，公式、引文及富文本标记保持原顺序。局部措辞、公式写法和跨页切分随上游占位符调整。两条路线在这些位置具有对应语义；SPGAN 第 10、12 页另作图表说明全文的同文比较。

## 读者能在原位置看到什么

- **SkySense。** 原第 1 页正文以「SAR 传感器能够」结束，第 2 页在表 1 附近接「全天候获取清晰影像」。这句来自人工对原始断词 `cap-/ture` 的核对。阅读路径仍需经过下一页的原表。图中原图形保留。图 1 补入的完整中文说明有部分降到 3.59 pt；图 2 的长架构图键缩至 1.79 pt。
- **DETR。** 第 5 页式 (1) 的求和、下标和式号均可见。按同一坐标截取并以 2 倍灰度渲染，36,144 个像素中有 36,051 个完全相同。第 6 页中，图 2 原有的「目标查询」「编码器」「无目标」等文本标签可直接回填；个别中文标签仅 2.89 pt。
- **GenCD。** 第 1 页图 1 与相应中文图键留在右栏，图题为 5.98 pt。第 2 页式 (1) 在相同区域以 2 倍渲染，13,824 个灰度像素全部相同。已用放大图核对相邻的输入、编码器、特征及下标。
- **SPGAN-DA。** 第 11 页单独提出的七项为页眉、三条表题、两栏正文及授权行。表格内部的类别名与数值没有进入待译清单。Codex 阅读原表，将中文列名和解释写入各自表题。在最终摘录中，表 II、III、IV 里的数值与原列对应，中文说明可检索到「不透水面」及 53.31、54.41、42.07、48.56。实验同时保留了第 10 页结果叙述中的 52.93% 和接在第 11 页的 21.89%。

## 同样的图表说明会被排成多大

| SPGAN-DA 检查点 | 实际送入上游的内容 | 译页中文字大小 |
| --- | --- | --- |
| 第 11 页表 II、III、IV，首轮 | 三段较长的双语列名说明，连同原表数值 | 5.10、5.10、4.78 pt |
| 第 11 页表 II、III、IV，最终稿 | 两条路线共享的精简中文表键，仍逐列说明含义 | 6.38、6.06、5.74 pt |
| 第 10 页图 7、8，最终稿 | 两条路线共享的中文说明，含色块及子图含义 | 两处均为 5.18 pt |
| 第 12 页图 9、表 V，最终稿 | 两条路线共享的完整图 9 图键和表 V 缩写说明 | 图 9 两个块为 3.19 和 6.38 pt，表 V 为 4.14 pt |

已对图 7、8、9 与表 V 的四个目标区域逐项核对，归一化后的中文及拉丁字母与共享图键相符。第 11 页三幅表体在同倍率下对照原页，三个区域均无 8 位灰度差超过 16 的像素。字号比较体现长中文进入既有图题框后的代价。若产品要求公式留在原位、图键能按正文字号阅读且允许增加页数，需要额外处理扩框或重排。

## 新增页的实际限制

把四篇论文所选范围中的第一张源页各制成一页 PDF，再分别添加一页。四个单页对照均通过上游校验，四个含续页的样本均返回 `mono output PDF must contain one page; found 2`。最终发布逻辑也会检查总页数是否等于原件。源文本、几何和占位符仍可作为其他排版器的输入。[上游发布检查](https://github.com/JiaJunDeng5930/PDF-translate-skill/blob/c0d55d172a722055bddfe5f442b7148e84c123cb/pdf-translate/scripts/file_task_pdf_translate/runner.py#L1105-L1126)

## 复核与复现

以下命令在独立临时目录执行。上游环境为 CPython 3.12.14、PyMuPDF 2.1、ONNX Runtime 1.32.0；不需要翻译 API 凭据。依赖清单首次解析为 60 个包，其中 bitstring 5.0.0 导致 `cannot import name 'BitStream'`。固定为 4.4.0 后成功。资源准备下载了一个版面模型、34 个字体、146 个 CMap、一个分词缓存及校验清单。

```powershell
git clone https://github.com/JiaJunDeng5930/PDF-translate-skill.git upstream
git -C upstream checkout c0d55d172a722055bddfe5f442b7148e84c123cb
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r upstream/pdf-translate/scripts/requirements.txt
uv pip install --python .venv/Scripts/python.exe bitstring==4.4.0
.venv/Scripts/python.exe upstream/pdf-translate/scripts/download_assets.py runtime-assets
```

每份论文的 `pdf_translate.yaml` 指向本地英文原件及已校验的 `asset_dir`，并设置 `lang_in: en`、`lang_out: zh-CN`、`output_mode: mono`、`add_formula_placehold_hint: true`。在配置所在目录运行上游 `pdf-translate/scripts/advance.py`。本机受限沙箱内，Windows asyncio 在创建本机回环套接字时挂起；线程栈停在 `socket._fallback_socketpair → accept`。允许本机回环后，四组源页均进入 `needs_ai_edit`。

首先以 1–3、5–6、1–2、10–12 四组分析。随后在独立单页目录用 `pages_per_advance: 1`，分别设置每张源页号以取得完整的单页编辑任务。填好 `current_translation.yaml` 的 `translation` 字段并回放相同命令至 `done`。从这些原生输出中按源页号提取真正译过的页，再组成四份摘录。模型、上游源代码和整本只译一页的临时 PDF 均未纳入仓库。

首次实测把十张 1.5 倍页图写入 `.work/upstream/results/`，每页任务、接受记录和原生输出留在各自的本地工作目录中。公开报告保留表中的逐页数字、对照区域和这套复现方法。按上文步骤重跑时，从对应出版方取得相同版本的输入，在本地生成四份摘录。[四篇论文的版本与页码](../Paper_Translation_Stimulation/README.md) · [来源与使用范围](../Paper_Translation_Stimulation/SOURCES.md)
