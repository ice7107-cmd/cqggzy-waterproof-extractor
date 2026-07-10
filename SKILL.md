---
name: cqggzy-waterproof-extractor
description: >
  从重庆市公共资源交易网 (cqggzy.com) 的中标候选人公示页面，自动提取中标候选人信息和招标控制价，
  查找对应答疑补遗页面下载工程量清单.pdf，提取防水材料（防水卷材/防水涂料/防水砂浆）数据，
  并生成HTML分析报告。使用 markitdown 将PDF转换为Markdown后解析。
  当用户提供 cqggzy.com 的中标候选人公示 URL 时使用。
---

# 重庆公共资源交易网投标防水材料分析

从 中标候选人公示 页面自动提取项目中标信息，下载工程量清单PDF，提取防水材料数据并生成报告。

## 前置条件

- `markitdown` CLI 已安装（`pip install markitdown` 或 `uv tool install markitdown`）
- Python 3.10+
- 所需 Python 包：`markitdown`

## 工作流程

### Step 1: 下载中标候选人公示页面

给定 cqggzy.com 的中标候选人公示 URL（categoryNum=014001003），下载页面 HTML：

```bash
curl -sL --connect-timeout 15 "https://www.cqggzy.com/trade/014001/xxx?categoryNum=014001003" -o /tmp/candidate_page.html
```

### Step 2: 提取中标候选人信息

清理 HTML 文本（去除 script/style 标签），解析获取：

- **项目名称**（在"项目标段名称"附近）
- **最高限价/招标控制价**（在"最高限价"附近，如 `16085845.76` 元）
- **投标报价**（在"投标报价"附近，如 `13708357.76` 元）
- **中标候选人**（第一名/第二名/第三名的名称和得分）
- **项目编码**（如 `50000120260610025100101`）
- **招标人名称**

从中标候选人页面提取价格数据的 Python 示例：

```python
text_clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL)
text_clean = re.sub(r'<[^>]+>', '\n', text_clean)
text_clean = re.sub(r'\n\s*\n', '\n', text_clean)
# 搜索"最高限价"附近行获取 control_price
# 搜索"投标报价"下第一名的数字行获取 bid_price
```

### Step 3: 查找答疑补遗页面并下载 工程量清单.pdf

从中标候选人页面提取 **答疑补遗 infoId**（页面 Vue 数据中包含 `categoryNum"014001002"` 的 infoId），然后：

```bash
# 下载答疑补遗页面
curl -sL "https://www.cqggzy.com/trade/014001/<infoId>?categoryNum=014001002" -o /tmp/clarify_page.html
```

在页面中搜索 `downloadAttach` 调用找到 工程量清单.pdf 的 GUID 和 Code：

```bash
grep -o "downloadAttach('[^']*" /tmp/clarify_page.html
grep -o "downloadAttach('[^']*','[^']*" /tmp/clarify_page.html
```

如果找不到（没有答疑补遗页面），回退到 **招标公告页面**（categoryNum=014001001）：
```bash
curl -sL "https://www.cqggzy.com/trade/014001/<projectInfoId>?categoryNum=014001001" -o /tmp/bid_page.html
```

### Step 4: 下载工程量清单 PDF

```bash
curl -sL --connect-timeout 30 -b /tmp/cookies.txt \
  -e "$PAGE_URL" \
  -o /tmp/qingdan.pdf \
  "https://ggzydl.cqggzy.com/CQTPBidder/jsgcztbmis2/pages/zbfilelingqu_hy/cQZBFileDownAttachAction.action?cmd=download&AttachGuid=$GUID&FileCode=$CODE&ClientGuid=631ba536-309c-405c-8c7e-8650a5bac8f8"
```

PDF 下载后用 `file` 命令验证文件是否为有效 PDF。

### Step 5: 提取防水材料

使用 `extract_waterproof.py` 脚本：

```bash
python3 scripts/extract_waterproof.py /tmp/qingdan.pdf \
  --project-name "项目名称" \
  --bid-price <中标金额> \
  --control-price <招标控制价> \
  --bid-url "https://..." \
  --clarify-url "https://..." \
  -o /tmp/waterproof_data.json
```

如果自动提取不准确（复杂PDF格式），**手动根据 markitdown 输出提取**防水清单项：

```bash
markitdown /tmp/qingdan.pdf > /tmp/qingdan.md
```

然后在输出中搜索防水关键词。手动构建 JSON 数据，格式参照自动脚本输出结构。

### Step 6: 生成 HTML 报告

桌面版 + 移动版：

```bash
python3 scripts/generate_report.py /tmp/waterproof_data.json \
  "/path/to/output/项目名称_防水材料分析报告.html" \
  --mobile-output "/path/to/output/项目名称_防水材料分析报告_移动版.html"
```

### Step 7: 验证

打开 HTML 报告检查布局和数据。

## 分类规则

| 类型 | 名称中包含的关键词 |
|------|-----------------|
| 防水卷材 | 卷材, 非沥青基, 橡胶自粘, 预铺, TPO, SBS, 分子粘, 聚乙烯胎, 耐根穿刺, 自粘型, 改性沥青 |
| 防水涂料 | 涂料, 聚氨酯, 水泥基渗透结晶, 聚合物水泥防水涂, JS防水, JS-Ⅱ, 丙烯酸, 非固化, 涂膜, 聚脲, 环氧树脂, 防潮层 |
| 防水砂浆 | 砂浆, 防水砂浆, 防水剂 |

## 注意事项

- 中标候选人公示页面的 URL 可能对应着 **两个不同版本的 infoId**（因更正或撤回重新发布），优先选择最新的（日期更新）。
- 中标候选人页面有时也直接包含附件附件（中标候选人公示.pdf），需区分文件类型。
- 答疑补遗的 infoId 需从候选人页面的 Vue 数据中提取，在 `categoryNum` 为 `014001002` 的部分查找。
- 如果答疑补遗页面没有 工程量清单.pdf，回退到招标公告页面查找。
- 两个页面的文件 Code 通常是 `J080`。
- 构建 JSON 时确保 `grand_total`、`type_totals` 等字段结构正确，与 `generate_report.py` 的输入格式匹配。
- 生成的 HTML 报告文件名包含中文时需要使用引号包裹。
