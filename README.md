# cqggzy-waterproof-extractor

> 从重庆市公共资源交易网 (cqggzy.com) 中标候选人公示页面自动提取防水材料数据并生成分析报告

## 概述

`cqggzy-waterproof-extractor` 是一个 [Codex](https://github.com/openai/codex) / DSH (DeepSeek Harness) skill，能够自动完成从 cqggzy.com 的中标候选人公示页面到防水材料分析报告的全流程：

1. 解析中标候选人页面，提取项目信息、中标金额、招标控制价
2. 查找对应答疑补遗附件中的工程量清单 PDF
3. 使用 PyMuPDF 坐标法重建清单表格（名称拆行、综合单价缺失可反推），提取防水卷材、防水涂料、防水砂浆清单项
4. 用 TypeSafe(Jev) 逐条复核候选条目，剔除误收、补入漏项、标出拿不准的（见下）
5. 生成带统计图表的桌面版/移动版/微信版 HTML 分析报告

## 两级筛选：关键词宽进，TypeSafe 严出

单纯靠关键词匹配有两个老毛病：`改性沥青混凝土`、`聚氨酯划线漆` 会被误收；`20mm厚1:2.5砂浆防水`
这种倒装写法会被漏掉。现在改成两级：

| 环节 | 作用 | 做法 |
|------|------|------|
| 宽进 | 保证不漏 | 强关键词 + `防水`/`防渗`/`止水`/`防潮`，把候选抓成超集 |
| 严出 | 保证不错 | 把候选逐条交给 TypeSafe 判断「是不是防水材料」，概率 ≥ 阈值才留下 |

判断口径写在 `references/waterproof_criteria.json`，改标准不用改代码。

实测（渝北 N18-6-3 小学项目，3862 页清单，232 条人工核对样本）：

| 办法 | 准确率 | 误收 | 漏项 |
|------|--------|------|------|
| 纯关键词匹配 | 97.4% | 4 | 2 |
| 关键词 + TypeSafe，标准写清楚 | 99.6% | 0 | 0 |

复核结果会写进 JSON 的 `screen` 字段（`dropped` 剔除项 / `added` 补入项 / `flagged` 待确认项），
生成报告前应把这三项汇报给用户。

## 安装

Codex（`~/.codex/skills`）：

```bash
# 通过 Codex skill-installer 安装
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ice7107-cmd/cqggzy-waterproof-extractor \
  --path .

# 或手动克隆
git clone git@github.com:ice7107-cmd/cqggzy-waterproof-extractor.git \
  ~/.codex/skills/cqggzy-waterproof-extractor
```

DSH / DeepSeek Harness（`~/.dsh/skills`，放进去即被自动发现）：

```bash
git clone git@github.com:ice7107-cmd/cqggzy-waterproof-extractor.git \
  ~/.dsh/skills/cqggzy-waterproof-extractor
```

> 本机现状：实体目录在 `~/.dsh/skills/cqggzy-waterproof-extractor`，
> `~/.codex/skills/cqggzy-waterproof-extractor` 是指向它的软链，两个 agent 共用同一份文件，
> 改一处两边同时生效。

### 前置依赖

```bash
# 推荐：坐标法解析，处理拆行/丢列更可靠
pip install pymupdf
# 兜底：PDF 转 Markdown（扫描件等特殊场景）
pip install markitdown
```

## 使用方法

在 Codex 中给定一个 cqggzy.com 的中标候选人公示 URL 即可自动触发。例如：

> https://www.cqggzy.com/trade/014001/xxx?categoryNum=014001003

Codex 会自动执行完整工作流并生成报告。

### 两种输入

| 输入 | 脚本 | 说明 |
|------|------|------|
| cqggzy 的 `工程量清单.pdf` | `scripts/extract_waterproof.py` | PyMuPDF 坐标法重建表格 |
| 甲方/总包给的 `.xlsx`／`.csv` | `scripts/extract_from_excel.py` | 自动识别表头，按 sheet 取单体名 |

两条路输出同一套 JSON，后面的 TypeSafe 复核、出报告、同步仪表盘完全通用。
清单里没有综合单价时（只给工程量），报告会自动隐藏所有金额列，改用面积占比。

### 手动运行

也可以单独使用目录中的脚本：

```bash
# Step 1: 下载工程量清单 PDF
bash scripts/download_qingdan.sh \
  "https://www.cqggzy.com/trade/014001/<答疑补遗infoId>?categoryNum=014001002"

# Step 2a: PDF 路线，提取防水材料（--screen 走 TypeSafe 复核，推荐加上）
python3 scripts/extract_waterproof.py /tmp/qingdan.pdf \
  --screen \
  --project-name "项目名称" \
  --district "沙坪坝区" \
  --bid-price 13708357.76 \
  --control-price 16085845.76 \
  --bid-url "https://..." \
  --clarify-url "https://..." \
  --date "YYYY-MM-DD" \
  -o /tmp/waterproof_data.json

# Step 2b: Excel 路线（甲方直接给清单时用这个）
python3 scripts/extract_from_excel.py "新津-防水.xlsx" \
  --project-name "新津项目" \
  --data-source "甲方工程量清单（Excel）" \
  --screen \
  -o /tmp/waterproof_data.json

# Step 3: 生成报告（--save-to-db 追加到数据仓库）
python3 scripts/generate_report.py /tmp/waterproof_data.json \
  "项目名称_防水材料分析报告.html" \
  --mobile-output "项目名称_防水材料分析报告_移动版.html" \
  --wechat-output "项目名称_防水材料分析报告_微信版.html" \
  --save-to-db
```

## 报告示例

生成的 HTML 报告包含：
- 中标金额、控制价、下浮比例、防水材料总价四格统计
- 项目基本信息
- 按材料类型（防水卷材/防水涂料/防水砂浆）分类的清单表格
- 综合汇总表（含占中标金额/控制价比例）
- 防水体系概览摘要

![报告示例](assets/report_preview.png)

## 判定标准 / 分类规则

判断口径统一在 `references/waterproof_criteria.json`，改标准不用改代码。

**收集范围只有三类：防水卷材／防水涂料／防水砂浆。**

已确认**不算**（2026-09-22 用户拍板）：止水带／止水条／钢板止水带／防水板／防水密封膏（不在收集范围）、
防渗膜、乳化沥青类（粘接层/透层油/冷底子油）、消防水池的水泥砂浆找平层、环氧树脂防潮层、
1:2.5／1:3 普通水泥砂浆防水层。

**暂时保留**待后续按需求再定：聚合物水泥防水砂浆（干粉类等）。

关键词表（宽进口径）：

| 类型 | 识别关键词 |
|------|-----------|
| 防水卷材 | 卷材, 非沥青基, 橡胶自粘, 预铺, TPO, SBS, 分子粘, 聚乙烯胎, 耐根穿刺, 自粘型, 改性沥青 |
| 防水涂料 | 涂料, 聚氨酯, 水泥基渗透结晶, 聚合物水泥防水涂, JS防水, JS-Ⅱ, 丙烯酸, 非固化, 涂膜, 聚脲, 环氧树脂, 防潮层 |
| 防水砂浆 | 砂浆, 防水砂浆, 防水剂 |

## 项目结构

```
cqggzy-waterproof-extractor/
├── SKILL.md                    # Codex skill 说明
├── README.md                   # 本文件
├── agents/
│   └── openai.yaml             # Codex UI 元数据
├── scripts/
│   ├── download_qingdan.sh     # 下载工程量清单 PDF
│   ├── extract_waterproof.py   # 从 PDF 提取防水材料（--screen 触发 TypeSafe 复核）
│   ├── extract_from_excel.py   # 从 Excel/CSV 清单提取防水材料
│   ├── screen_waterproof.py    # TypeSafe 复核候选条目（可单独调用 / 离线换阈值）
│   └── generate_report.py      # 生成 HTML 报告
├── references/
│   ├── waterproof_criteria.json  # 防水材料判定标准（改这里即可调整口径）
│   └── typesafe_key.txt          # TypeSafe API Key（不入库）
└── assets/                     # 资源文件（预留）
```

## 注意事项

- 中标候选人页面可能因更正存在多个版本的 infoId，优先使用最新日期
- 工程量清单 PDF 可能在答疑补遗页面，也可能在招标公告页面（回退机制）
- 部分复杂 PDF 格式需要手动辅助提取，SKILL.md 中有详细的手动提取指引
- 没有 TypeSafe API Key 时会自动跳过复核，退回纯关键词匹配，不会中断
- 复核消耗的 token 与候选条数成正比（约 1 条 1000 输入 token），跑前可用 `--dry-run` 预览

## License

MIT
