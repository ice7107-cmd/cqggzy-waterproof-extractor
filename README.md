# cqggzy-waterproof-extractor

> 从重庆市公共资源交易网 (cqggzy.com) 中标候选人公示页面自动提取防水材料数据并生成分析报告

## 概述

`cqggzy-waterproof-extractor` 是一个 [Codex](https://github.com/openai/codex) skill，能够自动完成从 cqggzy.com 的中标候选人公示页面到防水材料分析报告的全流程：

1. 解析中标候选人页面，提取项目信息、中标金额、招标控制价
2. 查找对应答疑补遗附件中的工程量清单 PDF
3. 使用 markitdown 解析 PDF，提取防水卷材、防水涂料、防水砂浆清单项
4. 生成带统计图表的桌面版和移动版 HTML 分析报告

## 安装

```bash
# 通过 Codex skill-installer 安装
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ice7107-cmd/cqggzy-waterproof-extractor \
  --path .

# 或手动克隆
git clone git@github.com:ice7107-cmd/cqggzy-waterproof-extractor.git \
  ~/.codex/skills/cqggzy-waterproof-extractor
```

### 前置依赖

```bash
pip install markitdown
# 或
uv tool install markitdown
```

## 使用方法

在 Codex 中给定一个 cqggzy.com 的中标候选人公示 URL 即可自动触发。例如：

> https://www.cqggzy.com/trade/014001/xxx?categoryNum=014001003

Codex 会自动执行完整工作流并生成报告。

### 手动运行

也可以单独使用目录中的脚本：

```bash
# Step 1: 下载工程量清单 PDF
bash scripts/download_qingdan.sh \
  "https://www.cqggzy.com/trade/014001/<答疑补遗infoId>?categoryNum=014001002"

# Step 2: 提取防水材料
python3 scripts/extract_waterproof.py /tmp/qingdan.pdf \
  --project-name "项目名称" \
  --bid-price 13708357.76 \
  --control-price 16085845.76 \
  --bid-url "https://..." \
  --clarify-url "https://..." \
  -o /tmp/waterproof_data.json

# Step 3: 生成报告
python3 scripts/generate_report.py /tmp/waterproof_data.json \
  "项目名称_防水材料分析报告.html" \
  --mobile-output "项目名称_防水材料分析报告_移动版.html"
```

## 报告示例

生成的 HTML 报告包含：
- 中标金额、控制价、下浮比例、防水材料总价四格统计
- 项目基本信息
- 按材料类型（防水卷材/防水涂料/防水砂浆）分类的清单表格
- 综合汇总表（含占中标金额/控制价比例）
- 防水体系概览摘要

![报告示例](assets/report_preview.png)

## 分类规则

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
│   ├── extract_waterproof.py   # 提取防水材料数据
│   └── generate_report.py      # 生成 HTML 报告
├── references/                 # 参考文档（预留）
└── assets/                     # 资源文件（预留）
```

## 注意事项

- 中标候选人页面可能因更正存在多个版本的 infoId，优先使用最新日期
- 工程量清单 PDF 可能在答疑补遗页面，也可能在招标公告页面（回退机制）
- 部分复杂 PDF 格式需要手动辅助提取，SKILL.md 中有详细的手动提取指引

## License

MIT
