---
name: cqggzy-waterproof-extractor
description: >
  从重庆市公共资源交易网 (cqggzy.com) 的中标候选人公示页面，自动提取中标候选人信息和招标控制价，
  查找对应答疑补遗页面下载工程量清单.pdf，提取防水材料（防水卷材/防水涂料/防水砂浆）数据，
  并生成HTML分析报告。使用 PyMuPDF 坐标法重建清单表格解析（markitdown 兜底）。
  关键词宽进抓候选 + TypeSafe(Jev) 严出复核，剔除误收、补入漏项。
  当用户提供 cqggzy.com 的中标候选人公示 URL 时使用；
  也支持甲方/总包直接给的 Excel/CSV 版工程量清单（走 extract_from_excel.py）。
---

# 重庆公共资源交易网投标防水材料分析

从 中标候选人公示 页面自动提取项目中标信息，下载工程量清单PDF，提取防水材料数据并生成报告。

## 前置条件

- Python 3.10+
- **推荐**：`pymupdf`（`pip install pymupdf`）——用词坐标重建表格，名称拆行、综合单价缺失都能正确处理
- **兜底**：`markitdown` CLI（`pip install markitdown` 或 `uv tool install markitdown`）
- 其他：`curl`（下载页面与附件）

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

> ⚠️ **先判断输入类型**：cqggzy 下载的是 PDF，走 `extract_waterproof.py`；
> 甲方/总包直接给的 `.xlsx`／`.xls`／`.csv` 清单走 `extract_from_excel.py`（见 Step 5E）。
> 两条路的输出 JSON 结构一致，后面的复核、出报告、同步仪表盘完全通用。

**PDF 路线**，使用 `extract_waterproof.py`：

```bash
python3 /Users/xiabing/.dsh/skills/cqggzy-waterproof-extractor/scripts/extract_waterproof.py /tmp/qingdan.pdf \
  --project-name "项目名称" \
  --district "沙坪坝区" \
  --bid-price <中标金额> \
  --control-price <招标控制价> \
  --bid-url "https://..." \
  --clarify-url "https://..." \
  --date "YYYY-MM-DD" \
  -o /tmp/waterproof_data.json
```

说明：
- `--district` 区县、`--date` 公示日期会写入数据仓库，务必填写
- 脚本优先用 PyMuPDF 坐标法重建表格；若 PDF 无文本（扫描件）会自动回退 markitdown
- 无综合单价列时，脚本按 合价 ÷ 工程量 自动反推；只有工程量、没有价格的条目会跳过
- **默认必须加 `--screen`**（见 Step 5.5），否则报告会带进误收项、漏掉倒装写法的条目

### Step 5.5: TypeSafe 复核候选条目（必做）

> ✅ **渗透结晶／聚合物防水涂料／聚合物水泥防水涂料·砂浆** 这几类已在本地直接判定收录
> （见「判断标准」小节），**不需要**联网复核。TypeSafe 只管这三类之外的边界条目。

关键词匹配负责「宽进」（不漏），TypeSafe 负责「严出」（不错收）。加 `--screen` 即可在提取后自动复核：

```bash
python3 .../extract_waterproof.py /tmp/qingdan.pdf --screen ... -o /tmp/waterproof_data.json
```

脚本行为：
1. 先用**宽关键词**（强关键词 + `防水`/`防渗`/`止水`/`防潮`）把候选抓成超集，写进 `candidates`
2. 逐条问 TypeSafe「这条是不是防水材料」，拿到 0~1 的概率
3. 概率 ≥ 阈值（默认 0.5）的保留，判否的剔除，被判是但关键词没抓到的**补进** `items`
4. 汇总（`type_totals`、`grand_total`）自动重算

复核结果写入 JSON 的 `screen` 字段，生成报告前**必须向用户汇报**这三件事：

- `screen.dropped` — 被剔除的误收项（如改性沥青砼层、聚氨酯划线漆、无纺聚氨酯纤维布、防水套管）
- `screen.added` — 补入的漏项（通常来自倒装写法，如 `20mm厚1:2.5砂浆防水`）
- `screen.flagged` — 打分在 0.2~0.8 之间「拿不准」的条目，**逐条报给用户确认**

补充参数：

| 参数 | 说明 |
|------|------|
| `--screen-threshold 0.5` | 判定阈值。默认 0.5；调高更严（少收多漏），调低更宽 |
| `--criteria <path>` | 判定标准文件，默认 `references/waterproof_criteria.json` |
| `--key-file <path>` | TypeSafe API Key 文件 |

单独复核一个已有的候选清单（或换阈值离线重算，不联网不花钱）：

```bash
# 只复核候选
python3 .../screen_waterproof.py /tmp/waterproof_data.json
# 换阈值重算，用已存的打分结果，不联网
python3 .../screen_waterproof.py /tmp/waterproof_data.json --reapply --threshold 0.7
# 只看会发什么，不联网
python3 .../screen_waterproof.py /tmp/waterproof_data.json --dry-run
```

**没有 API Key 时**：脚本会打印提示并**跳过复核**，结果退回关键词匹配，不会报错中断。Key 的读取顺序是 `--key-file` → 环境变量 `TYPESAFE_API_KEY` → `references/typesafe_key.txt` → `~/.typesafe_key`。

> ⚠️ `references/typesafe_key.txt` 含密钥，不要提交到 git（已在 `.gitignore` 中排除）。

### Step 5E: Excel/CSV 清单路线

甲方或总包直接给 Excel 时用这个脚本。它会自动识别表头、按 sheet 名取单体名
（`…【地下室‖建筑…` → `地下室`），并把单体写进每条 `building` 字段。

```bash
python3 /Users/xiabing/.dsh/skills/cqggzy-waterproof-extractor/scripts/extract_from_excel.py "新津-防水.xlsx" \
  --project-name "新津项目" \
  --screen \
  -o /tmp/waterproof_data.json
```

说明：
- 支持 `.xlsx`／`.xlsm`／`.csv`；**老版 `.xls` 要先在 Excel 里另存为 `.xlsx`**
- 表头在前 15 行内自动查找，列名支持「项目编码／项目名称／项目特征描述／计量单位／工程量／综合单价／合价」
- 无综合单价的清单（只给了工程量）也能处理：此时 `unit_price`／`total_price` 为 0，报告会自动隐藏金额列
- `--district`／`--date` 同 PDF 路线

**专业分包清单布局（自动识别）**

总包/甲方下发的「防水工程专业分包清单」通常**没有项目编码列**，材料不写在项目名称里，
而是写在各条的「项目特征描述」里（如「5、粘贴4厚改性沥青聚乙烯胎防水卷材一层满粘」）。

`extract_from_excel.py` 在标准表头找不到时会自动切换到这种布局：
- 以「序号」为 `一/二/三…` 且无工程量的行作为**单体分隔**（浅圆仓／平房仓／工作塔及卸粮站）
- 用正则从「项目特征描述」里抽出材料名（要求带厚度规格，如 `4厚`／`2mm厚`／`3.0+3.0厚`，
  避免把「设备穿透卷材处」这类描述误当成材料）
- 一条清单项含多种材料时**拆成多条**（如屋面同时有卷材+涂料 → 各记一条，工程量相同）
- 长括号里的施工说明（`(屋面洞口、支墩…附加)`）自动剔除，短规格括号（`(聚酯胎)`、`(Ⅱ型)`）保留
- 单价列取「含税单价」

如果自动提取仍不准确（复杂PDF格式），**手动根据 markitdown 输出提取**防水清单项：

```bash
markitdown /tmp/qingdan.pdf > /tmp/qingdan.md
```

然后在输出中搜索防水关键词。手动构建 JSON 数据，格式参照自动脚本输出结构（含 `district`、`date`、`bid_url`、`clarify_url`）。

### Step 6: 生成 HTML 报告 + 数据仓库

> 📁 **输出目录约定**：所有 HTML 报告（桌面版/移动版/微信版）统一输出到 `/Users/xiabing/AI/大禹/html/` 文件夹，仪表盘 `waterproof_dashboard.html` 也在其中。


```bash
# 桌面版 + 移动版 + 微信分享版 + 保存到数据仓库
python3 /Users/xiabing/.dsh/skills/cqggzy-waterproof-extractor/scripts/generate_report.py /tmp/waterproof_data.json \
  "/Users/xiabing/AI/大禹/html/项目名称_防水材料分析报告.html" \
  --mobile-output "/Users/xiabing/AI/大禹/html/项目名称_防水材料分析报告_移动版.html" \
  --wechat-output "/Users/xiabing/AI/大禹/html/项目名称_防水材料分析报告_微信版.html" \
  --save-to-db
```
- `--wechat-output`: 生成适合微信分享的轻量版报告（大字、无横向滚动、卡片式布局）
- **中标人字段**：JSON 中加 `winner`（中标人）或 `top_candidate`（中标候选人第一名），报告会在「项目名称」和「中标金额」之间显示该行；有 `winner` 时标签为「中标人」，否则为「中标候选人第一名」。
- `--save-to-db`: 将项目数据写入 `/Users/xiabing/AI/大禹/waterproof_database.json` 数据仓库。**同名项目（如先按候选人公示分析、后拿到中标结果公示）会原地更新该条目**，不会重复添加、也不会被跳过，因此重跑即可刷新金额/中标人/下浮比例。

> **数据仓库**：每次运行自动积累数据到 `waterproof_database.json`。注意：仪表盘 HTML 内嵌数据，不会自动读取该文件，新增项目后需要同步（见「数据仓库」小节）。

### Step 6B: 导出 Excel（可选）

需要把结果给同事/甲方，或自己用 Excel 二次核算时使用：

```bash
python3 /Users/xiabing/.dsh/skills/cqggzy-waterproof-extractor/scripts/export_excel.py /tmp/waterproof_data.json \
  "/Users/xiabing/AI/大禹/项目名称_防水材料汇总.xlsx" \
  --merge-by-name
```

生成三个工作表：
- `防水材料汇总`：按材料大类分组，同名材料合并后的名称/工程量/占比/使用部位/出现处数，带小计与总计
- `按单体分布`：材料 × 单体的工程量交叉表，一眼看出每栋楼要什么材料、要多少
- `原始清单`：未合并的全部明细（项目编码、单体、部位、工程量）

- `--merge-by-name`：同名材料合并、数量求和（与 HTML 报告的合并口径一致）；不加则按原始清单逐条导出

### Step 7: 同步并打开 Dashboard

```bash
# 先把新项目同步进仪表盘
python3 /Users/xiabing/AI/大禹/scripts/sync_dashboard.py
open "/Users/xiabing/AI/大禹/html/waterproof_dashboard.html"
```

Dashboard 功能：
- 📊 项目总数、防水总金额、平均造价、覆盖区县统计
- 🔍 按区县/材料类型/防水总价区间筛选
- 📱 移动端自适应，微信中可打开
- 📄 点击项目查看详细信息
- 🗂️ 新增项目后需同步仪表盘（见「数据仓库」）

### Step 8: 验证

打开 HTML 报告检查布局和数据。

## 数据仓库

每次通过 `--save-to-db` 运行后，数据自动积累到 `/Users/xiabing/AI/大禹/waterproof_database.json`。
仪表盘（`html/waterproof_dashboard.html`）的数据**内嵌在页面 `var DB={...}` 中**，不会自动更新。新增项目后运行一键同步脚本：

```bash
python3 /Users/xiabing/AI/大禹/scripts/sync_dashboard.py
```

脚本会自动：
1. 用 `waterproof_database.json` 的 `projects` 覆盖仪表盘内嵌 `DB`
2. 为新增项目自动补充报告名称映射（`reportNames`）

**删除项目**不再需要脚本：双击「启动仪表盘.command」打开本地服务（http://127.0.0.1:8765）后，在仪表盘页面点项目卡片右上角 ✕ → 确认，即可自动删除数据库条目、对应 HTML 报告文件并刷新页面。

「启动仪表盘.command」会在**后台常驻**启动服务（关掉弹出的窗口服务也不会停），重复双击会自动检测并只打开浏览器，不会重复启动；查看原始分析报告也需在此服务模式下打开（直接双击 HTML 也能看报告，但删除功能需走启动器）。

> ⚠️ 新增项目后必须运行同步脚本，否则 Dashboard 不会反映最新数据。

## 判断标准 / 分类规则

**判断口径**统一放在 `references/waterproof_criteria.json`，改这个文件即可调整标准，不需要改代码。
`criteria.true` / `criteria.false` 写得越具体，TypeSafe 判得越准（实测：标准写清楚后准确率 97.8% → 99.6%）。

### 已经用户拍板的口径（不要再问，也不要收进报告）

这几类**明确不算**防水项，已写进 `criteria.false`：

- **防渗膜**（HDPE / 土工膜等）——属隔离/辅助材料
- **乳化沥青类**：粘接层、透层油、粘层油、冷底子油
- **消防水池的水泥砂浆**：1:3 纤维水泥砂浆、水泥砂浆找平层（抗渗靠混凝土本体的 P8 等级，不靠这层砂浆）
- **环氧树脂防潮层**：仅作防潮处理的涂层
- **普通水泥砂浆防水层**：1:2.5、1:3 普通配比，含名称写作「砂浆防水」、内掺防水剂的抹面
- **止水类与防水配件**：止水带、止水条、钢板止水带、止水钢板、防水板、防水密封膏——**不在收集范围内**

> ⚠️ **收集范围只有三类：防水卷材／防水涂料／防水砂浆。**
> 「其他防水」类别已取消，报告中不会出现该类卡片；止水带、防水板、防水密封膏等配件一律不收。

**暂时保留、以后按需求再定**的：

- **聚合物水泥防水砂浆**（含干粉类、聚合物水泥防水砂浆找平／找坡／防水层）——当前**算**防水项。
  用户 2026-09-22 明确表态「暂时保留」。若要剔除，改 `criteria.true` 第③条并把该类写进 `criteria.false`。

**一律算防水（2026-10-17 用户确认，本地直接判，不必等复核）**：

名称**或「项目特征」栏**里出现下列写法的，脚本直接收进报告：

- **渗透结晶**（含「水泥基渗透结晶型防水涂料」各种版本）
- **聚合物防水涂料**
- **聚合物水泥防水涂料／砂浆**

这条很关键：很多清单的项目名称只写「消防水池楼板整治」「外墙面砂浆防水」，
真正的材料写在**项目特征**栏里。脚本会读特征栏并按上面的材料写法判定，
名称里没写规格时还会把特征里的规格补进名字（如「砂浆防水（6mm厚聚合物水泥防水砂浆）」）。

> 📋 **改口径只改一个文件：`references/material_rules.json`**
>
> PDF 路线（`extract_waterproof.py`）和 Excel 路线（`extract_from_excel.py`）共用它，
> 两条路不会再各写一份正则。结构：
> - `always_waterproof`：命中的写法 + 归到哪个材料大类（`type`）
> - `never_waterproof`：即使出现也排除的写法（抗裂砂浆、水泥砂浆找平层、玻纤网格布…）
>
> 改完直接生效，不用改代码；加一条材料只加一个 pattern 即可。
> 注意 `waterproof_criteria.json` 是给 TypeSafe 看的判断说明，两份文件要保持一致——
> 先改 `material_rules.json`，再同步标准文件顶部的 `_已确认口径`。

> ⚠️ 只认上面这些**材料写法**，不认泛词。所以「抗裂防水砂浆」「1:3 水泥砂浆找平层」
> 「玻纤网格布加固」这类即使在特征栏里出现「防水砂浆」字样，也不会被误收
> （实测：按「锚行~下一锚行」取窗口会把下一条的特征串到本条上，已改成按
> `[项目特征]` 标记定界）。

用户若对某条边界材料另有说法，先改 `criteria.false` 再跑，不要只在报告里手工删。
标准文件顶部 `_已确认口径` 记录了每一条口径的确认时间，改之前先看一眼。

关键词表（宽进口径，用于抓候选）：

| 类型 | 名称中包含的关键词 |
|------|-----------------|
| 防水卷材 | 卷材, 非沥青基, 橡胶自粘, 预铺, TPO, SBS, 分子粘, 聚乙烯胎, 耐根穿刺, 自粘型, 改性沥青 |
| 防水涂料 | 涂料, 聚氨酯, 水泥基渗透结晶, 渗透结晶, 聚合物水泥防水涂, JS防水, JS-Ⅱ, 丙烯酸, 非固化, 涂膜, 聚脲, 环氧树脂, 防潮层 |
| 防水砂浆 | 砂浆, 防水砂浆, 防水剂 |

## 注意事项

- 中标候选人公示页面的 URL 可能对应着 **两个不同版本的 infoId**（因更正或撤回重新发布），优先选择最新的（日期更新）。
- 中标候选人页面有时也直接包含附件附件（中标候选人公示.pdf），需区分文件类型。
- 答疑补遗的 infoId 需从候选人页面的 Vue 数据中提取，在 `categoryNum` 为 `014001002` 的部分查找。
- 如果答疑补遗页面没有 工程量清单.pdf，回退到招标公告页面查找。
- 两个页面的文件 Code 通常是 `J080`。
- 构建 JSON 时确保 `grand_total`、`type_totals` 等字段结构正确，与 `generate_report.py` 的输入格式匹配。
- 生成的 HTML 报告文件名包含中文时需要使用引号包裹。
- 报告的数据来源行会读 JSON 里的 `data_source` 字段；Excel 路线请把 `--data-source` 设成甲方清单的名称，否则会误写成"重庆市公共资源交易网"。
- 条目带 `building` 字段时，「部位」列会显示成 `地下室 · 底板` 这种「单体 · 部位」形式。

## 报告格式标准

所有生成的分析报告必须使用 `generate_report.py` 生成，格式统一为以下结构：

### 无报价清单的处理（只有工程量、没有综合单价）
当所有条目的 `unit_price` 都是 0 时，报告自动切换为「工程量模式」：
- 隐藏「综合单价／合价／下浮后单价／下浮后合价」列
- 综合汇总表的「占比」按**面积**算，不再按金额
- 四格统计卡改为：防水总面积／材料种类／卷材面积／涂料面积
- 摘要框写「本清单未含综合单价，故只列工程量」

### 桌面版报告结构
1. **顶部 Hero 区** — 渐变深蓝背景 + 项目名称 + 数据来源
2. **四格统计卡片** — 中标金额（金色）、最高限价（红色）、下浮比例（绿色）、防水卷材总面积（蓝色）
3. **项目基本信息区** — 项目名称、中标金额、最高限价、下浮比例、答疑补遗/中标公告链接
4. **材料分类明细表** — 每类材料一个独立卡片：
   - 防水卷材（蓝色标签）
   - 防水涂料（橙色标签）
   - 防水砂浆（绿色标签）
   - 其他防水材料（如有）
   - 表头：序号、部位、材料名称、单位、工程量、综合单价、**[有下浮比例时] 下浮后单价**、合价、**[有下浮比例时] 下浮后合价**
   - 底部：本类合计行（浅绿背景）
5. **防水材料综合汇总表** — 全项目所有材料汇总：
   - 表头：材料大类、材料名称、工程量、综合单价、**[有下浮比例时] 下浮后单价**、合价、**[有下浮比例时] 下浮后合价**、占比
   - 底部：防水部分合计、占中标金额比例、占最高限价比例
6. **摘要框** — 绿色左边框背景，显示总条目数、分类统计、防水总价、**[有下浮比例时] 下浮后总价**、占中标金额比例
7. **页脚** — 数据来源 + 原文链接 + 生成日期

### 样式要求
- 字体：`-apple-system, BlinkMacSystemFont, "Microsoft YaHei", "PingFang SC"`
- 背景：`#f0f2f5` 浅灰
- Hero：渐变 `#1a1a2e → #16213e → #0f3460`
- 卡片：白色背景 `#fff`，圆角 `12-14px`，轻微阴影
- 统计值颜色：中标金额 `#b8860b`、最高限价 `#dc2626`、下浮比例 `#16a34a`、防水总价 `#2563eb`
- 表格：表头 `#f8fafc` 背景，悬停 `#f8fafc`，底部双线边框
- 无下浮比例时（`discount_ratio` 为 `None`），**完全隐藏**"下浮后单价"和"下浮后合价"列

### 移动版报告
- 使用 `--mobile-output` 参数生成，专为手机优化
- 卡片自适应宽度，无水平滚动

### 微信分享版报告
- 使用 `--wechat-output` 参数生成
- 大字、无横向滚动、卡片式布局，适合微信内浏览

> ⚠️ 禁止手写 HTML 报告模板，始终使用 `generate_report.py` 生成。
