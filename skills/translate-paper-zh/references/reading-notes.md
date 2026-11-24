# 手稿笔记清单

本文定义本地排版工具的输入。Agent 撰写手记时采用[精读手记规范](reading-voice.md)，随后用 UTF-8 保存下面的 JSON 清单。以校对完成的中文 PDF 为底本。页码是译本的物理页码，`source` 回指英文原页、节、图表或公式。先在这份底本中搜索锚点。文字需在本页唯一且位于同一行。重复的表格数字、编码异常的公式或子图可在渲染页中核对位置，用 PDF 点填写 `bbox`（左、上、右、下）。底本有变动时，重新定位批注并更新指纹。

```json
{
  "base_sha256": "<本次干净译本的 SHA-256>",
  "notes": [
    {
      "page": 7,
      "ink": "yellow",
      "anchor": {"text": "时间错配"},
      "mark": "highlight",
      "lines": ["若有两类观测的采集日期，", "可在同一林型内按间隔分组。", "间隔越长，误差也越大吗？"],
      "source": "原第 7 页 · §3.4"
    }
  ]
}
```

| 字段 | 写法 |
| --- | --- |
| `ink` | 新清单用 `blue`、`red` 或 `yellow`。蓝墨 `#1F4E79` 适合多数手记，红墨 `#A63429` 用在少量值得再看的词句，黄笔的页边文字和细线为深琥珀 `#8A5A00`。三色均可用于研究想法。 |
| `anchor` | 写 `{"text": "时间错配"}` 或 `{"bbox": [443,647,482,660]}`。示例坐标对应本次 Open-Canopy 作者版译本第 14 页式 (A) 的分母。 |
| `mark` | `circle` 圈数字、公式或关键词，`underline` 划出短语，`bracket` 用括线收住一组内容。`highlight` 与 `yellow` 配对，在锚点上用 `#F4DF7D`、65% 不透明度的原生 PDF 荧光笔叠底。一次选一个词或短数值，引线只穿过留白。 |
| `lines`、`source` | 用几行短句写手记，只选少数有价值的位置。论文观察写成可核对的陈述，研究设想写成「若把……」「可以试试……」等自然句式，交代要观察的结果。为设想标的原页指向引起这个问题的原句或图表。 |
| `inline` | 在原版心内直写，填留白的 `bbox` 和一至两行 `lines`，可附 `sketch`。在当前底本上量位置，避开译文、图表和其他手写框。纸面太窄时，可将图和长句移至同页外侧。 |
| `sketch`、`inline.sketch` | 前者画在外侧，后者紧跟原页短批。`{"kind":"flow","steps":["四波段","PVTv2","树高"]}` 用箭头串联两三步。`{"kind":"table","rows":[["参考高","误差贡献"],["4 米","40%"],["19 米","10%"]],"focus":[1,1]}` 抄一张小表。`focus` 可选，按从零开始的行号、列号点亮一格。 |
| `also` | 一个数组，元素各含 `anchor` 和 `mark`。读同一张表的两行时，可以用一则手记圈出一个数，再划出另一个数。 |
| `reference_links` | 清单顶层可填经核实的原文编号与 HTTPS 地址，如 `{"[72]":"https://doi.org/10.1007/s41095-022-0274-8"}`。写在手记里的编号可点击。 |

已有清单中的 `kind: evidence`、`kind: calculation`、`kind: idea` 仍可使用，旧笔色 `green` 与 `ochre` 分别映射到新的黄系与红系。编写新手记时直接填写 `ink`。笔记属于论文观察、读者验算还是待验证的方法，由句子本身和指向的原文交代。

卡其纸模式中，中文译文使用黑色霞鹜文楷 Regular，中文手记使用悠哉 Medium。页内短批为 10.5 磅，页边长句为 12.2 磅，普通拉丁字母用 Caveat Medium 放大 15% 对齐。数字及容易混淆的技术标识采用文楷正体，如 `ImageNet1k`、`2000`、`mIoU`、`F1`、`R²`。节号和出处用较小的正体。纸色为 `#FAF3E3`，外侧用淡横线承接手记。遥感图、色标、表格和公式保留原裁切底色。导出使用随附字体，读者无需安装。[字体来源与许可](../assets/fonts/README.md)

先用 `paper.py render ... --notebook-paper` 生成卡其色全文底本。在这份底本上定位手记，再从仓库根目录取得 SHA-256。将第一条命令输出的小写校验值填入 `base_sha256`，再运行第二条命令。

```text
python -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('paper-work/reviewed.pdf').read_bytes()).hexdigest())"
python skills/translate-paper-zh/scripts/annotate.py paper-work/reviewed.pdf paper-work/notes.json paper.zh-notes.pdf --uniform-margin --notebook-paper
```

统一扩边使等尺寸的原页在翻页时保持相同纸宽，未写手记的页自然留白。可在命令末尾加 `--font <可嵌入的手写字体路径>` 指定字形。重开成品核对锚点、图表、标点和算式，再交付一份精读手稿 PDF。校对底本与 JSON 清单保存在工作目录内。
