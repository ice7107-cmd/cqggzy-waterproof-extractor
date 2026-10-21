#!/usr/bin/env python3
"""Generate waterproof analysis HTML report from JSON data."""
import json, re, sys
from datetime import date

TEMPLATE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#1a2332;padding:30px}
.container{max-width:1200px;margin:0 auto}
.hero{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-radius:16px;padding:40px 48px;margin-bottom:28px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-50%;right:-20%;width:500px;height:500px;background:radial-gradient(circle,rgba(255,255,255,0.04) 0%,transparent 70%);border-radius:50%}
.hero-badge{display:inline-block;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);color:#93c5fd;font-size:12px;padding:4px 14px;border-radius:20px;margin-bottom:16px;letter-spacing:1px}
.hero h1{color:#fff;font-size:22px;font-weight:700;line-height:1.5;margin-bottom:8px;max-width:90%}
.hero .subtitle{color:rgba(255,255,255,0.65);font-size:14px}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}
.stat-card{background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,0.06);transition:transform 0.15s}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.08)}
.stat-label{font-size:12px;color:#94a3b8;letter-spacing:0.5px;margin-bottom:6px}
.stat-value{font-size:24px;font-weight:700;color:#0a1628}
.stat-value.gold{color:#b8860b}.stat-value.green{color:#16a34a}.stat-value.blue{color:#2563eb}.stat-value.red{color:#dc2626}
.stat-note{font-size:12px;color:#94a3b8;margin-top:4px}
.section-card{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.06);margin-bottom:20px;overflow:hidden}
.section-header{padding:18px 28px;border-bottom:1px solid #eef2f6;display:flex;align-items:center;gap:10px}
.section-header .icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}
.section-header .icon.blue{background:#eff6ff}.section-header .icon.green{background:#f0fdf4}.section-header .icon.amber{background:#fffbeb}
.section-header .icon.purple{background:#faf5ff}.section-header .icon.cyan{background:#ecfeff}.section-header .icon.rose{background:#fff1f2}
.section-header h2{font-size:16px;font-weight:600;color:#1a2332}
.section-body{padding:24px 28px}
.info-grid{display:grid;grid-template-columns:140px 1fr;gap:4px 0;font-size:14px}
.info-label{color:#64748b;padding:3px 0}
.info-value{color:#1a2332;font-weight:500;padding:3px 16px;background:#f8fafc;border-radius:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{background:#f8fafc;color:#475569;font-weight:600;font-size:12px;letter-spacing:0.3px;padding:10px 12px;border-bottom:2px solid #e2e8f0;text-align:left;white-space:nowrap}
tbody td{padding:9px 12px;border-bottom:1px solid #f1f5f9;vertical-align:top;line-height:1.5}
tbody tr:hover{background:#f8fafc}
tbody tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500}
.tag.membrane{background:#dbeafe;color:#1d4ed8}.tag.coating{background:#fef3c7;color:#b45309}.tag.mortar{background:#d1fae5;color:#047857}
.summary-box{margin-top:18px;padding:14px 18px;background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border-radius:10px;border-left:4px solid #22c55e;font-size:13px;line-height:1.7;color:#1a2332}
.summary-box strong{color:#15803d}
.split-note em{color:#94a3b8;font-size:11px;font-style:normal}
footer{text-align:center;padding:20px;color:#94a3b8;font-size:12px;line-height:1.8}
footer a{color:#2563eb;text-decoration:none}
@media(max-width:768px){.stats-grid{grid-template-columns:repeat(2,1fr)}body{padding:16px}.hero{padding:24px 20px}.hero h1{font-size:18px;max-width:100%}.section-body{padding:16px}.section-header{padding:14px 16px}table{font-size:12px}thead th,tbody td{padding:6px 6px}}
"""

MOBILE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#1a2332;padding:12px;-webkit-text-size-adjust:100%}
.container{max-width:100%;margin:0 auto}
.hero{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-radius:12px;padding:20px 18px;margin-bottom:16px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-50%;right:-20%;width:300px;height:300px;background:radial-gradient(circle,rgba(255,255,255,0.04) 0%,transparent 70%);border-radius:50%}
.hero-badge{display:inline-block;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);color:#93c5fd;font-size:10px;padding:3px 10px;border-radius:16px;margin-bottom:10px;letter-spacing:0.5px}
.hero h1{color:#fff;font-size:16px;font-weight:700;line-height:1.4;margin-bottom:6px}
.hero .subtitle{color:rgba(255,255,255,0.65);font-size:12px}
.stats-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px}
.stat-card{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}
.stat-label{font-size:10px;color:#94a3b8;letter-spacing:0.3px;margin-bottom:4px}
.stat-value{font-size:18px;font-weight:700;color:#0a1628}
.stat-value.gold{color:#b8860b}.stat-value.green{color:#16a34a}.stat-value.blue{color:#2563eb}.stat-value.red{color:#dc2626}
.stat-note{font-size:10px;color:#94a3b8;margin-top:2px}
.section-card{background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.06);margin-bottom:14px;overflow:hidden}
.section-header{padding:12px 16px;border-bottom:1px solid #eef2f6;display:flex;align-items:center;gap:8px}
.section-header .icon{width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0}
.section-header .icon.blue{background:#eff6ff}.section-header .icon.green{background:#f0fdf4}.section-header .icon.amber{background:#fffbeb}
.section-header .icon.purple{background:#faf5ff}.section-header .icon.cyan{background:#ecfeff}.section-header .icon.rose{background:#fff1f2}
.section-header h2{font-size:14px;font-weight:600;color:#1a2332}
.section-body{padding:14px 16px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.info-grid{display:grid;grid-template-columns:90px 1fr;gap:3px 0;font-size:12px}
.info-label{color:#64748b;padding:2px 0}
.info-value{color:#1a2332;font-weight:500;padding:2px 10px;background:#f8fafc;border-radius:3px;font-size:12px;word-break:break-all}
.info-value a{color:#2563eb;text-decoration:none}
table{width:100%;border-collapse:collapse;font-size:11px;min-width:600px}
thead th{background:#f8fafc;color:#475569;font-weight:600;font-size:10px;letter-spacing:0.2px;padding:7px 6px;border-bottom:2px solid #e2e8f0;text-align:left;white-space:nowrap}
tbody td{padding:6px;border-bottom:1px solid #f1f5f9;vertical-align:top;line-height:1.4}
tbody tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;font-weight:500}
.tag.membrane{background:#dbeafe;color:#1d4ed8}.tag.coating{background:#fef3c7;color:#b45309}.tag.mortar{background:#d1fae5;color:#047857}
.summary-box{margin-top:12px;padding:10px 14px;background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border-radius:8px;border-left:3px solid #22c55e;font-size:12px;line-height:1.6;color:#1a2332}
.summary-box strong{color:#15803d}
.split-note em{color:#94a3b8;font-size:11px;font-style:normal}
footer{text-align:center;padding:14px;color:#94a3b8;font-size:10px;line-height:1.6}
footer a{color:#2563eb;text-decoration:none}
"""

def fmt_money(n):
    if n is None: return "\u2014"
    return f"\u00a5{n:,.2f}"

def fmt_pct(n, total):
    if total and total > 0: return f"{n/total*100:.2f}%"
    return "\u2014"

def merge_items_by_name(items, max_parts=3):
    """把同名材料合并成一条：工程量求和、合价求和，部位归并显示。

    同名 = (材料大类, 材料名称) 完全相同。合并后 `_merged_n` 记录原本有几条。

    部位显示规则：
      - 只出现在一个单体 → 「地下室 · 墙面、楼面」
      - 跨多个单体       → 「地下室、1#楼、2#楼（共10处）」
    """
    order, groups = [], {}
    for it in items:
        k = (it.get('type'), it.get('name'))
        if k not in groups:
            groups[k] = {'base': dict(it), 'bldgs': [], 'parts': [],
                         'qty': 0.0, 'tp': 0.0, 'n': 0, 'nloc': 0}
            order.append(k)
        g = groups[k]
        g['qty'] += it.get('quantity', 0) or 0
        g['tp'] += it.get('total_price', 0) or 0
        g['n'] += 1
        b = (it.get('building') or '').strip()
        part = (it.get('location') or '').strip()
        if b or part:
            g['nloc'] += 1
        if b and b not in g['bldgs']:
            g['bldgs'].append(b)
        if part and part not in g['parts']:
            g['parts'].append(part)

    out = []
    for k in order:
        g = groups[k]
        it = g['base']
        it['quantity'] = round(g['qty'], 2)
        it['total_price'] = round(g['tp'], 2)
        if g['qty'] > 0:
            it['unit_price'] = round(g['tp'] / g['qty'], 2)

        bldgs, parts = g['bldgs'], g['parts']
        if len(bldgs) > 1:
            it['location'] = '、'.join(bldgs) + f'（共{g["nloc"]}处）'
        else:
            head = bldgs[0] if bldgs else ''
            if len(parts) > max_parts:
                ptxt = '、'.join(parts[:max_parts]) + f' 等{len(parts)}处'
            else:
                ptxt = '、'.join(parts)
            it['location'] = ' · '.join(x for x in [head, ptxt] if x)

        it.pop('building', None)
        it['_merged_n'] = g['n']
        out.append(it)
    return out


_THICK_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:mm|㎜|毫米|MM)?\s*厚')


def norm_material_name(nm):
    """厚度写法归一：把「1.5厚」「1.5mm」「1.5mm厚」统一成「1.5mm」。"""
    return _THICK_RE.sub(lambda m: f'{m.group(1)}mm', nm or '')


_LOC_PREFIX_RE = re.compile(r'^(外墙面|内墙面|外墙|内墙|墙面|屋面|楼地面|顶棚|天棚|地面|地下室|卫生间|厨房|阳台)')
_BUILD_SUFFIX_RE = re.compile(r'(抹灰|找平|找坡|防水层)+$')


def norm_material_key(nm):
    """合并键用的进一步归一：去掉名称里的部位前缀和施工做法后缀。

    「外墙20mm防水砂浆抹灰」→「20mm防水砂浆」，与「20mm防水砂浆」合并；
    只影响汇总表的归组，展示名仍用 norm_material_name（保留原文措辞）。
    """
    s = norm_material_name(nm)
    s = _LOC_PREFIX_RE.sub('', s)
    s = _BUILD_SUFFIX_RE.sub('', s)
    # 括号统一成全角、并把括号内容统一挪到末尾：
    # 「…防水卷材（TJ）」与「…(TJ)防水卷材」是同一种材料的两种写法，位置不归一就并不到一起。
    s = s.replace('(', '（').replace(')', '）')
    # 「（Ⅱ）型」→「（Ⅱ型）」，避免把型号拆成「…JS型（Ⅱ）」
    s = re.sub(r'（([^（）]*)）型', r'（\1型）', s)
    parens = re.findall(r'（[^（）]*）', s)
    if parens:
        s = re.sub(r'（[^（）]*）', '', s) + ''.join(parens)
    return s.strip()


def summary_rows(items):
    """汇总表按「材料大类 + 归一化材料名 + 单位」合并求和（2026-10-21 用户口径）。

    材料名称里含厚度规格时，清单原文的写法很不统一：「1.5厚」「1.5mm」「1.5mm厚」
    指的是同一个厚度，不归一化就会被拆成好几行。这里把厚度统一写成 `<数字>mm`，
    再按「大类 + 归一化名称 + 单位」求和；不同厚度（1.2mm / 1.5mm）数字不同，
    不会误合并；不同材料（防水砂浆 vs 聚合物水泥防水砂浆）名称不同，也不合并。
    分类明细表仍逐条列（保留部位与原文），只有这张汇总表合并。
    """
    groups, order = {}, []
    for it in items:
        key_name = norm_material_key(it.get('name') or '')
        k = (it.get('type') or '', key_name, it.get('unit') or '')
        if k not in groups:
            groups[k] = {
                'type': it.get('type') or '',
                'name': key_name,
                'unit': it.get('unit') or '',
                'quantity': 0.0,
                'total_price': 0.0,
                'n': 0,
                'split': False,
            }
            order.append(k)
        g = groups[k]
        g['quantity'] += it.get('quantity') or 0
        g['total_price'] += it.get('total_price') or 0
        g['n'] += 1
        if it.get('_split_note'):
            g['split'] = True
    rows = [groups[k] for k in order]
    for g in rows:
        g['unit_price'] = (g['total_price'] / g['quantity']) if g['quantity'] else 0.0
    return rows


def render_item_table(title, icon, icon_cls, items, type_label, discount_ratio=None, has_price=True):
    if not items: return ""
    tag_map = {"防水卷材": "membrane", "防水涂料": "coating", "防水砂浆": "mortar", "其他": "mortar"}
    tag_cls = tag_map.get(type_label, "mortar")
    has_adj = has_price and discount_ratio is not None and discount_ratio > 0

    # Header
    if has_adj:
        h = f'<div class="section-card"><div class="section-header"><div class="icon {icon_cls}">{icon}</div><h2>{title}</h2></div><div class="section-body"><table><thead><tr><th>序号</th><th>部位</th><th>材料名称</th><th>单位</th><th class="num">工程量</th><th class="num">综合单价(元)</th><th class="num">下浮后单价(元)</th><th class="num">合价(元)</th><th class="num">下浮后合价(元)</th></tr></thead><tbody>'
    elif has_price:
        h = f'<div class="section-card"><div class="section-header"><div class="icon {icon_cls}">{icon}</div><h2>{title}</h2></div><div class="section-body"><table><thead><tr><th>序号</th><th>部位</th><th>材料名称</th><th>单位</th><th class="num">工程量</th><th class="num">综合单价(元)</th><th class="num">合价(元)</th></tr></thead><tbody>'
    else:
        h = f'<div class="section-card"><div class="section-header"><div class="icon {icon_cls}">{icon}</div><h2>{title}</h2></div><div class="section-body"><table><thead><tr><th>序号</th><th>部位</th><th>材料名称</th><th>单位</th><th class="num">工程量</th></tr></thead><tbody>'
    
    for idx, it in enumerate(items, 1):
        nm = it['name'][:50]
        loc = it.get('location', '') or ''
        bld = it.get('building', '') or ''
        if bld:
            loc = f'{bld} · {loc}' if loc else bld
        dao_note = it.get('_dao_note', '')
        if dao_note:
            qty_display = f"{it['quantity']:,.2f} {dao_note}"
        else:
            qty_display = f"{it['quantity']:,.2f}"
        
        tag_text = "卷材" if type_label=="防水卷材" else "涂料" if type_label=="防水涂料" else "砂浆"
        # 复合项拆分出来的行：工程量照记，金额显示「—」（钱只计在主材料行，避免重复）
        _is_split = bool(it.get('_split_note'))
        _up = '—' if _is_split else f'{it["unit_price"]:.2f}'
        _tp = '—' if _is_split else f'{it["total_price"]:,.2f}'
        _nm_attr = ' title="复合清单项拆分而来，金额计入主材料行"' if _is_split else ''
        _nm_txt = f'<span{_nm_attr}>{nm}</span>' if not _is_split else f'<span class="split-note"{_nm_attr}>{nm} <em>（复合项拆分，金额见主材料行）</em></span>'

        if has_adj:
            _adj_up = '—' if _is_split else f'{it["unit_price"] * (1 - discount_ratio / 100):.2f}'
            _adj_tp = '—' if _is_split else f'{it["total_price"] * (1 - discount_ratio / 100):,.2f}'
            h += f'<tr><td>{idx}</td><td>{loc}</td><td><span class="tag {tag_cls}">{tag_text}</span> {_nm_txt}</td><td>{it.get("unit","m²")}</td><td class="num">{qty_display}</td><td class="num">{_up}</td><td class="num">{_adj_up}</td><td class="num">{_tp}</td><td class="num">{_adj_tp}</td></tr>'
        elif has_price:
            h += f'<tr><td>{idx}</td><td>{loc}</td><td><span class="tag {tag_cls}">{tag_text}</span> {_nm_txt}</td><td>{it.get("unit","m²")}</td><td class="num">{qty_display}</td><td class="num">{_up}</td><td class="num">{_tp}</td></tr>'
        else:
            h += f'<tr><td>{idx}</td><td>{loc}</td><td><span class="tag {tag_cls}">{tag_text}</span> {_nm_txt}</td><td>{it.get("unit","m²")}</td><td class="num">{qty_display}</td></tr>'
    
    # Total row
    total_qty = sum(it['quantity'] for it in items)
    total_price = sum(it['total_price'] for it in items)
    unit = items[0].get('unit', 'm²') if items else ''
    if has_adj:
        adj_total = total_price * (1 - discount_ratio / 100)
        h += f'<tr style="background:#f0fdf4;font-weight:600"><td colspan="2"></td><td><span style="color:#15803d">本类合计</span></td><td class="num">{unit}</td><td class="num">{total_qty:,.2f}</td><td></td><td></td><td class="num">{total_price:,.2f}</td><td class="num">{adj_total:,.2f}</td></tr>'
    elif has_price:
        h += f'<tr style="background:#f0fdf4;font-weight:600"><td colspan="2"></td><td><span style="color:#15803d">本类合计</span></td><td class="num">{unit}</td><td class="num">{total_qty:,.2f}</td><td></td><td class="num">{total_price:,.2f}</td></tr>'
    else:
        h += f'<tr style="background:#f0fdf4;font-weight:600"><td colspan="2"></td><td><span style="color:#15803d">本类合计</span></td><td class="num">{unit}</td><td class="num">{total_qty:,.2f}</td></tr>'
    
    h += '</tbody></table></div></div>'
    return h

def prepare_items(data):
    """统一入口：剔除「其他防水」类 + 合并同名 + 重算合计。

    2026-10-21 用户口径：收集范围只有 卷材／涂料／砂浆 三类，「其他防水」类别已取消。
    历史数据里仍可能残留该类型（如钢板止水带），报告一律不展示；并按过滤后的条目
    重算 grand_total 与 type_totals，保证表格行和合计对得上，不出现「行加起来 ≠ 合计」。
    """
    items = data.get('items', []) or []
    drop = [it for it in items if (it.get('type') or '') == '其他防水']
    if drop:
        items = [it for it in items if (it.get('type') or '') != '其他防水']
        print(f'[提示] 报告已剔除 {len(drop)} 条「其他防水」类条目（不在收集范围）：',
              file=sys.stderr)
        for it in drop[:10]:
            print(f"   - {str(it.get('name', ''))[:40]} | "
                  f"{it.get('quantity')} {it.get('unit', '')} | {it.get('total_price')} 元",
                  file=sys.stderr)
    if data.get('merge_by_name'):
        items = merge_items_by_name(items)
    if items:
        gt = sum((it.get('total_price') or 0) for it in items)
        tt = {}
        for it in items:
            t = it.get('type') or ''
            d = tt.setdefault(t, {'count': 0, 'total_qty': 0, 'total_price': 0})
            d['count'] += 1
            d['total_qty'] += (it.get('quantity') or 0)
            d['total_price'] += (it.get('total_price') or 0)
        return items, gt, tt
    return items, data.get('grand_total', 0), data.get('type_totals', {})


def generate_html(data):
    items, gt, type_totals = prepare_items(data)
    bp = data.get('bid_price')
    cp = data.get('control_price')
    disc = data.get('discount_ratio')
    # 清单里完全没有单价时（如甲方只给了工程量清单），不显示价格列和金额卡片
    has_price = any((it.get('unit_price') or 0) > 0 for it in items)
    if not has_price:
        bp = cp = disc = None
    # 有没有「招投标信息」（中标金额／最高限价／下浮比例）。
    # 只有价格、没有中标信息的（如总包下发的分包清单），卡片改显示工程量口径。
    has_bid = bool(bp or cp or disc is not None)
    src = data.get('data_source', '重庆市公共资源交易网 \u00b7 答疑补遗附件 \u00b7 工程量清单.pdf')
    em = '—'
    pn = data.get('project_name', '未知项目')
    bu = data.get('bid_url', '')
    cu = data.get('clarify_url', '')
    winner = data.get('winner') or data.get('top_candidate') or ''
    winner_label = '中标人' if data.get('winner') else '中标候选人第一名'
    td = date.today().strftime('%Y-%m-%d')

    membranes = [it for it in items if it['type'] == '防水卷材']
    coatings = [it for it in items if it['type'] == '防水涂料']
    mortars = [it for it in items if it['type'] == '防水砂浆']
    others = [it for it in items if it['type'] == '其他防水']

    total_mem_qty = sum(it['quantity'] for it in membranes)

    L = []
    L.append('<!DOCTYPE html><html lang="zh-CN"><head>')
    L.append('<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">')
    L.append(f'<title>{pn} \u2014 防水材料工程量清单分析</title><style>{TEMPLATE_CSS}</style></head><body><div class="container">')

    # Hero
    L.append(f'<div class="hero"><div class="hero-badge">\U0001f4cb 防水材料工程量清单分析</div>')
    L.append(f'<h1>{pn}<br>防水卷材 &amp; 防水涂料工程量清单分析</h1>')
    L.append(f'<div class="subtitle">数据来源：{src}</div></div>')

    # Stats
    L.append('<div class="stats-grid">')
    if has_bid:
        L.append(f'<div class="stat-card"><div class="stat-label">中标金额</div><div class="stat-value gold">{fmt_money(bp)}</div><div class="stat-note">施工总承包</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">最高限价</div><div class="stat-value red">{fmt_money(cp)}</div><div class="stat-note">招标控制价</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">下浮比例</div><div class="stat-value green">{disc if disc is not None else em}%</div><div class="stat-note">较最高限价下浮</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">防水卷材总面积</div><div class="stat-value blue">{total_mem_qty:,.2f}</div><div class="stat-note">m\u00b2</div></div>')
    else:
        total_qty_all = sum(it['quantity'] for it in items)
        n_kinds = len(set(it['name'] for it in items))
        total_ct_qty = sum(it['quantity'] for it in coatings)
        L.append(f'<div class="stat-card"><div class="stat-label">防水总面积</div><div class="stat-value blue">{total_qty_all:,.2f}</div><div class="stat-note">m\u00b2</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">材料种类</div><div class="stat-value gold">{n_kinds}</div><div class="stat-note">去重后</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">卷材面积</div><div class="stat-value blue">{total_mem_qty:,.2f}</div><div class="stat-note">m\u00b2</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">涂料面积</div><div class="stat-value" style="color:#d97706">{total_ct_qty:,.2f}</div><div class="stat-note">m\u00b2</div></div>')
    L.append('</div>')

    # Project info
    if pn or bu or cu:
        L.append('<div class="section-card"><div class="section-header"><div class="icon cyan">\U0001f4cc</div><h2>项目基本信息</h2></div><div class="section-body"><div class="info-grid">')
        L.append(f'<div class="info-label">项目名称</div><div class="info-value">{pn}</div>')
        if winner: L.append(f'<div class="info-label">{winner_label}</div><div class="info-value">{winner}</div>')
        if bp: L.append(f'<div class="info-label">中标金额</div><div class="info-value">{fmt_money(bp)}</div>')
        if cp: L.append(f'<div class="info-label">最高限价</div><div class="info-value">{fmt_money(cp)}</div>')
        if disc is not None: L.append(f'<div class="info-label">下浮比例</div><div class="info-value">{disc}%</div>')
        if cu: L.append(f'<div class="info-label">答疑补遗</div><div class="info-value"><a href="{cu}" target="_blank">查看原文</a></div>')
        if bu: L.append(f'<div class="info-label">中标结果公告</div><div class="info-value"><a href="{bu}" target="_blank">查看原文</a></div>')
        L.append('</div></div></div>')

    # Tables
    L.append(render_item_table('防水卷材', '\U0001f504', 'blue', membranes, '防水卷材', disc, has_price))
    L.append(render_item_table('防水涂料', '\U0001f6e2\ufe0f', 'amber', coatings, '防水涂料', disc, has_price))
    L.append(render_item_table('防水砂浆', '\U0001f9f1', 'green', mortars, '防水砂浆', disc, has_price))
    if others:
        L.append(render_item_table('其他防水材料', '\U0001f4cb', 'rose', others, '其他', disc, has_price))

    # Fallback: show type_totals when items is empty
    if not items:
        tt_labels = []
        for tt, tv in type_totals.items():
            if tv.get('count', 0) > 0:
                tt_labels.append(f'{tv["count"]}种{tt}')
        if tt_labels:
            L.append('<div class="section-card"><div class="section-header"><div class="icon purple">📊</div><h2>防水材料分类汇总</h2></div><div class="section-body">')
            L.append('<div style="padding:12px 0;line-height:1.8;color:#64748b;font-size:13px;">')
            L.append('<p style="margin-bottom:10px">📋 本项目的工程量清单PDF已识别出防水类别信息，但暂未提取详细条目数据。</p>')
            L.append('<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">')
            for tt, tv in type_totals.items():
                if tv.get('count', 0) > 0:
                    cls = {'防水卷材':'blue','防水涂料':'amber','防水砂浆':'green','其他防水':'rose'}.get(tt, 'gray')
                    L.append(f'<span style="display:inline-block;padding:6px 14px;background:#f8fafc;border-radius:8px;font-size:13px;color:#1a2332"><strong>{tt}</strong>：{tv["count"]}项</span>')
            L.append('</div>')
            L.append(f'<p>防水部分总造价约 <strong>¥{gt:,.2f}</strong></p>')
            if bp: L.append(f'<p>占中标金额约 <strong>{gt/bp*100:.2f}%</strong></p>')
            L.append('</div></div></div>')
        elif type_totals and all(tv.get('count',0)==0 for tv in type_totals.values()):
            # Show basic grand total card
            L.append('<div class="section-card"><div class="section-header"><div class="icon purple">📊</div><h2>防水材料概况</h2></div><div class="section-body">')
            L.append(f'<div style="padding:12px 0;line-height:1.8;font-size:14px;text-align:center;color:#94a3b8">')
            L.append('<p>📋 本项目防水部分总造价约 <strong style="color:#b8860b">¥{gt:,.2f}</strong></p>'.format(gt=gt))
            if bp: L.append(f'<p style="margin-top:4px">占中标金额约 <strong>{gt/bp*100:.2f}%</strong></p>')
            L.append('</div></div></div>')
    # Summary
    _sum_qty = sum(it['quantity'] for it in items)
    if items:
        has_adj = has_price and disc is not None and disc > 0
        _hdr = '<div class="section-card"><div class="section-header"><div class="icon purple">\U0001f4ca</div><h2>防水材料综合汇总</h2></div><div class="section-body" style="padding-bottom:4px;"><table><thead><tr><th>材料大类</th><th>材料名称</th><th class="num">工程量</th>'
        if has_adj:
            L.append(_hdr + '<th class="num">综合单价(元)</th><th class="num">下浮后单价(元)</th><th class="num">合价(元)</th><th class="num">下浮后合价(元)</th><th class="num">占比</th></tr></thead><tbody>')
        elif has_price:
            L.append(_hdr + '<th class="num">综合单价(元)</th><th class="num">合价(元)</th><th class="num">占比</th></tr></thead><tbody>')
        else:
            L.append(_hdr + '<th class="num">占比</th></tr></thead><tbody>')
        for it in summary_rows(items):
            tl = {'防水卷材':'卷材','防水涂料':'涂料','防水砂浆':'砂浆','其他防水':'其他'}.get(it['type'],'')
            _itunit = it.get('unit') or 'm\u00b2'
            _cnt = (f'<span style="color:#94a3b8;font-size:11px;">（{it["n"]} 条）</span>'
                    if it.get('n', 1) > 1 else '')
            _split_row = bool(it.get('split')) and not (it.get('total_price') or 0)
            if _split_row:
                _cnt += '<span style="color:#94a3b8;font-size:11px;">（复合项拆分，金额计入主材料行）</span>'
            _base = f'<tr><td style="font-weight:600;">{it["type"]}</td><td>{tl} {it["name"][:35]}{_cnt}</td><td class="num">{it["quantity"]:,.2f} {_itunit}</td>'
            if has_adj:
                if _split_row:
                    L.append(_base + '<td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>')
                else:
                    adj_up = it['unit_price'] * (1 - disc/100)
                    adj_tp = it['total_price'] * (1 - disc/100)
                    L.append(_base + f'<td class="num">{it["unit_price"]:.2f}</td><td class="num">{adj_up:.2f}</td><td class="num" style="font-weight:600;">{it["total_price"]:,.2f}</td><td class="num">{adj_tp:,.2f}</td><td class="num">{fmt_pct(it["total_price"], gt)}</td></tr>')
            elif has_price:
                if _split_row:
                    L.append(_base + '<td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>')
                else:
                    L.append(_base + f'<td class="num">{it["unit_price"]:.2f}</td><td class="num" style="font-weight:600;">{it["total_price"]:,.2f}</td><td class="num">{fmt_pct(it["total_price"], gt)}</td></tr>')
            else:
                L.append(_base + f'<td class="num">{fmt_pct(it["quantity"], _sum_qty)}</td></tr>')
        if has_adj:
            adj_gt = gt * (1 - disc/100)
            L.append(f'<tr style="background:#f8fafc;font-weight:700;"><td colspan="4" style="text-align:right;">防水部分合计</td><td class="num" style="color:#b8860b;">{gt:,.2f}</td><td class="num" style="color:#b8860b;">{adj_gt:,.2f}</td><td class="num">100%</td></tr>')
        elif has_price:
            L.append(f'<tr style="background:#f8fafc;font-weight:700;"><td colspan="4" style="text-align:right;">防水部分合计</td><td class="num" style="color:#b8860b;">{gt:,.2f}</td><td class="num">100%</td></tr>')
        else:
            L.append(f'<tr style="background:#f8fafc;font-weight:700;"><td colspan="2" style="text-align:right;">面积合计</td><td class="num" style="color:#2563eb;">{_sum_qty:,.2f}</td><td class="num">100%</td></tr>')
        if has_adj:
            if bp: L.append(f'<tr style="background:#f0fdf4;"><td colspan="4" style="text-align:right;color:#166534;">占中标金额比例</td><td class="num" style="color:#16a34a;font-weight:700;">{fmt_pct(gt, bp)}</td><td class="num" style="color:#16a34a;">—</td><td class="num" style="color:#16a34a;">—</td></tr>')
            if cp: L.append(f'<tr style="background:#fef2f2;"><td colspan="4" style="text-align:right;color:#991b1b;">占最高限价比例</td><td class="num" style="color:#dc2626;font-weight:700;">{fmt_pct(gt, cp)}</td><td class="num" style="color:#dc2626;">—</td><td class="num" style="color:#dc2626;">—</td></tr>')
        elif has_price:
            if bp: L.append(f'<tr style="background:#f0fdf4;"><td colspan="4" style="text-align:right;color:#166534;">占中标金额比例</td><td class="num" style="color:#16a34a;font-weight:700;">{fmt_pct(gt, bp)}</td><td class="num" style="color:#16a34a;">—</td></tr>')
            if cp: L.append(f'<tr style="background:#fef2f2;"><td colspan="4" style="text-align:right;color:#991b1b;">占最高限价比例</td><td class="num" style="color:#dc2626;font-weight:700;">{fmt_pct(gt, cp)}</td><td class="num" style="color:#dc2626;">—</td></tr>')
        L.append('</tbody></table></div></div>')
    # Summary box
    # Compute type_totals counts for fallback when items empty
    tt_total_count = sum(tv.get('count',0) for tv in type_totals.values())
    tt_mem_count = type_totals.get('防水卷材',{}).get('count',0)
    tt_ct_count = type_totals.get('防水涂料',{}).get('count',0)
    tt_mort_count = type_totals.get('防水砂浆',{}).get('count',0)
    _n_show = len(items) if items else tt_total_count
    _merged_note = ''
    if data.get('merge_by_name') and items:
        _raw = sum(it.get('_merged_n', 1) for it in items)
        if _raw > len(items):
            _merged_note = f'（原始清单 {_raw} 条，同名材料已合并）'
    if not _merged_note and items:
        _sr = len(summary_rows(items))
        if _sr < len(items):
            _merged_note = f'（汇总表按同种材料合并为 {_sr} 行）'
    if items:
        _n_split = sum(1 for it in items if it.get('_split_note'))
        if _n_split:
            _merged_note += (f'；其中 {_n_split} 条为复合清单项按材料拆分，'
                             f'工程量各计一份、金额只计一次')
    _prefix = f'<div class="summary-box"><strong>\U0001f4cc 防水体系概览：</strong>本项目防水材料共提取到 <strong>{_n_show}</strong> 项{_merged_note}，其中防水卷材 <strong>{len(membranes) if items else tt_mem_count}</strong> 项、防水涂料 <strong>{len(coatings) if items else tt_ct_count}</strong> 项、防水砂浆 <strong>{len(mortars) if items else tt_mort_count}</strong> 项。'
    L.append(_prefix)
    if has_price:
        L.append(f'防水部分总造价约 <strong>\u00a5{gt:,.2f}</strong>。')
        if bp:     L.append(f'占中标金额约 <strong>{fmt_pct(gt, bp)}</strong>。')
        if disc is not None:
            adj_gt = gt * (1 - disc/100)
            L.append(f'下浮后防水总价约 <strong>¥{adj_gt:,.2f}</strong>（下浮{disc:.2f}%）。')
    else:
        L.append(f'防水总面积约 <strong>{_sum_qty:,.2f} m\u00b2</strong>。本清单未含综合单价，故只列工程量。')
    L.append('</div>')

    # Footer
    L.append('<footer>')
    if data.get('data_source'):
        L.append(f'<p>数据来源：{src}</p>')
    else:
        L.append('<p>数据来源：<a href="https://www.cqggzy.com" target="_blank">重庆市公共资源交易网（cqggzy.com）</a></p>')
    if bu: L.append(f'<p>中标结果公告：<a href="{bu}" target="_blank">查看原文</a></p>')
    if cu: L.append(f'<p>答疑补遗：<a href="{cu}" target="_blank">查看原文</a></p>')
    _src_note = 'Excel 工程量清单自动解析生成' if data.get('data_source') else '工程量清单PDF自动解析生成'
    L.append(f'<p style="margin-top:4px;">本报告由{_src_note} \u00b7 数据抓取日期：{td} \u00b7 仅供参考</p>')
    L.append('</footer></div></body></html>')

    return '\n'.join(L)


def generate_html_mobile(data):
    """Generate iPhone-optimized mobile HTML report."""
    items, gt, _tt = prepare_items(data)
    bp = data.get('bid_price')
    cp = data.get('control_price')
    disc = data.get('discount_ratio')
    has_price = any((it.get('unit_price') or 0) > 0 for it in items)
    if not has_price:
        bp = cp = disc = None
    # 有没有「招投标信息」（中标金额／最高限价／下浮比例）。
    # 只有价格、没有中标信息的（如总包下发的分包清单），卡片改显示工程量口径。
    has_bid = bool(bp or cp or disc is not None)
    src = data.get('data_source', '重庆市公共资源交易网 \u00b7 工程量清单.pdf')
    em = '—'
    pn = data.get('project_name', '未知项目')
    bu = data.get('bid_url', '')
    cu = data.get('clarify_url', '')
    winner = data.get('winner') or data.get('top_candidate') or ''
    winner_label = '中标人' if data.get('winner') else '中标候选人第一名'
    td = date.today().strftime('%Y-%m-%d')

    membranes = [it for it in items if it['type'] == '防水卷材']
    coatings = [it for it in items if it['type'] == '防水涂料']
    mortars = [it for it in items if it['type'] == '防水砂浆']
    others = [it for it in items if it['type'] == '其他防水']

    total_mem_qty = sum(it['quantity'] for it in membranes)
    gt_label = '¥{:,.2f}'.format(gt)

    L = []
    L.append('<!DOCTYPE html><html lang="zh-CN"><head>')
    L.append('<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">')
    L.append(f'<title>{pn} — 防水材料工程量清单分析</title><style>{MOBILE_CSS}</style></head><body><div class="container">')

    # Hero
    L.append(f'<div class="hero"><div class="hero-badge">📋 防水材料工程量清单分析</div>')
    L.append(f'<h1>{pn}</h1>')
    L.append(f'<div class="subtitle">{src}</div></div>')

    # Stats
    L.append('<div class="stats-grid">')
    if has_bid:
        L.append(f'<div class="stat-card"><div class="stat-label">中标金额</div><div class="stat-value gold">{fmt_money(bp)}</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">最高限价</div><div class="stat-value red">{fmt_money(cp)}</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">下浮比例</div><div class="stat-value green">{disc if disc is not None else em}%</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">防水材料总价</div><div class="stat-value blue">{gt_label}</div></div>')
    else:
        _mq = sum(it['quantity'] for it in items)
        _mk = len(set(it['name'] for it in items))
        _mc = sum(it['quantity'] for it in coatings)
        L.append(f'<div class="stat-card"><div class="stat-label">防水总面积</div><div class="stat-value blue">{_mq:,.2f} m\u00b2</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">材料种类</div><div class="stat-value gold">{_mk}</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">卷材面积</div><div class="stat-value blue">{total_mem_qty:,.2f} m\u00b2</div></div>')
        L.append(f'<div class="stat-card"><div class="stat-label">涂料面积</div><div class="stat-value" style="color:#d97706">{_mc:,.2f} m\u00b2</div></div>')
    L.append('</div>')

    # Project info
    if pn or bu or cu:
        L.append('<div class="section-card"><div class="section-header"><div class="icon cyan">📌</div><h2>项目基本信息</h2></div><div class="section-body"><div class="info-grid">')
        L.append(f'<div class="info-label">项目名称</div><div class="info-value">{pn}</div>')
        if winner: L.append(f'<div class="info-label">{winner_label}</div><div class="info-value">{winner}</div>')
        if bp: L.append(f'<div class="info-label">中标金额</div><div class="info-value">{fmt_money(bp)}</div>')
        if cp: L.append(f'<div class="info-label">最高限价</div><div class="info-value">{fmt_money(cp)}</div>')
        if disc is not None: L.append(f'<div class="info-label">下浮比例</div><div class="info-value">{disc}%</div>')
        if cu: L.append(f'<div class="info-label">答疑补遗</div><div class="info-value"><a href="{cu}" target="_blank">查看原文</a></div>')
        if bu: L.append(f'<div class="info-label">中标结果</div><div class="info-value"><a href="{bu}" target="_blank">查看原文</a></div>')
        L.append('</div></div></div>')

    # Tables
    L.append(render_item_table('防水卷材', '🔄', 'blue', membranes, '防水卷材', disc, has_price))
    L.append(render_item_table('防水涂料', '🛢️', 'amber', coatings, '防水涂料', disc, has_price))
    L.append(render_item_table('防水砂浆', '🧱', 'green', mortars, '防水砂浆', disc, has_price))
    if others:
        L.append(render_item_table('其他防水材料', '📋', 'rose', others, '其他', disc, has_price))

    # Summary box
    _mq2 = sum(it['quantity'] for it in items)
    if has_price:
        L.append(f'<div class="summary-box"><strong>📌 防水体系概览：</strong>本项目共提取 <strong>{len(items)}</strong> 项，其中防水卷材 <strong>{len(membranes)}</strong> 项、防水涂料 <strong>{len(coatings)}</strong> 项、防水砂浆 <strong>{len(mortars)}</strong> 项。防水部分总造价约 <strong>¥{gt:,.2f}</strong>。')
        if bp:     L.append(f'占中标金额约 <strong>{fmt_pct(gt, bp)}</strong>。')
        if disc is not None:
            adj_gt = gt * (1 - disc/100)
            L.append(f'下浮后防水总价约 <strong>¥{adj_gt:,.2f}</strong>（下浮{disc:.2f}%）。')
    else:
        L.append(f'<div class="summary-box"><strong>📌 防水体系概览：</strong>本项目共提取 <strong>{len(items)}</strong> 项，其中防水卷材 <strong>{len(membranes)}</strong> 项、防水涂料 <strong>{len(coatings)}</strong> 项、防水砂浆 <strong>{len(mortars)}</strong> 项。防水总面积约 <strong>{_mq2:,.2f} m\u00b2</strong>。')
        L.append('本清单未含综合单价，故只列工程量。')
    L.append('</div>')

    # Footer
    L.append('<footer>')
    L.append('<p>数据来源：<a href="https://www.cqggzy.com" target="_blank">重庆市公共资源交易网</a></p>')
    if bu: L.append(f'<p>中标结果：<a href="{bu}" target="_blank">查看原文</a></p>')
    if cu: L.append(f'<p>答疑补遗：<a href="{cu}" target="_blank">查看原文</a></p>')
    L.append(f'<p style="margin-top:4px;">PDF自动解析 · {td} · 仅供参考</p>')
    L.append('</footer></div></body></html>')

    return '\n'.join(L)



# ── Data warehouse: append project data to waterproof_database.json ──
DB_PATH = '/Users/xiabing/AI/大禹/waterproof_database.json'
def save_to_database(data):
    import os, json
    import datetime
    proj = {
        'project_name': data.get('project_name', ''),
        'bid_price': data.get('bid_price'),
        'control_price': data.get('control_price'),
        'discount_ratio': data.get('discount_ratio'),
        'grand_total': data.get('grand_total', 0),
        'type_totals': {
            '防水卷材': {'count': len([i for i in data.get('items',[]) if i.get('type')=='防水卷材']), 'total_price': sum(i['total_price'] for i in data.get('items',[]) if i.get('type')=='防水卷材')},
            '防水涂料': {'count': len([i for i in data.get('items',[]) if i.get('type')=='防水涂料']), 'total_price': sum(i['total_price'] for i in data.get('items',[]) if i.get('type')=='防水涂料')},
            '防水砂浆': {'count': len([i for i in data.get('items',[]) if i.get('type')=='防水砂浆']), 'total_price': sum(i['total_price'] for i in data.get('items',[]) if i.get('type')=='防水砂浆')},
        },
        'items': data.get('items', []),
        'has_detail': True,
        # 优先使用公示日期，缺省才用生成日期
        'date': data.get('date') or datetime.date.today().strftime('%Y-%m-%d'),
        'bid_url': data.get('bid_url'),
        'clarify_url': data.get('clarify_url'),
        'winner': data.get('winner'),
        'top_candidate': data.get('top_candidate'),
    }
    # 优先使用传入数据的 district，否则从项目名匹配
    district_from_data = data.get('district', '')
    if district_from_data:
        proj['district'] = district_from_data
    else:
        dm = {'潼南':'潼南区','书院坡':'潼南区','国航':'渝北区','武隆':'武隆区','大足':'大足区',
              '渝中':'渝中区','东港':'南岸区','鱼胡路':'巴南区','大渡口':'大渡口区','铜梁':'铜梁区',
              '沙坪坝':'沙坪坝区','南岸':'南岸区','巴南':'巴南区','渝北':'渝北区','江北':'江北区',
              '九龙坡':'九龙坡区','北碚':'北碚区','两江新区':'两江新区','高新区':'高新区'}
        for k, v in dm.items():
            if k in proj['project_name']:
                proj['district'] = v
                break
        if not proj['district']:
            proj['district'] = '其它'
    db = {'version':1,'created':'2026-07-23','projects':[]}
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, encoding='utf-8') as f:
                existing = json.load(f)
                if 'projects' in existing:
                    db = existing
        except:
            pass
    # 同名项目原地更新，避免重复分析与修正后仪表盘仍显示旧数据
    replaced = False
    for idx, old in enumerate(db['projects']):
        if old.get('project_name') == proj['project_name']:
            # 保留旧记录里仍有效、新数据未提供的字段
            for k, v in old.items():
                if k not in proj or proj.get(k) in (None, '', []):
                    proj.setdefault(k, v)
            db['projects'][idx] = proj
            replaced = True
            break
    if not replaced:
        db['projects'].append(proj)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print('    [数据仓库] ' + ('已更新' if replaced else '已保存到') + ' ' + DB_PATH)


# ── WeChat-friendly report ──
WECHAT_CSS_STR = (
    '*{margin:0;padding:0;box-sizing:border-box}'
    'body{font-family:-apple-system,BlinkMacSystemFont,"Microsoft YaHei","PingFang SC",sans-serif;background:#f5f7fa;color:#1a2332;padding:0;-webkit-text-size-adjust:100%}'
    '.container{max-width:600px;margin:0 auto;background:#fff;min-height:100vh}'
    '.top{background:linear-gradient(135deg,#0a1628,#16213e,#0f3460);padding:28px 20px 20px;color:#fff}'
    '.top h1{font-size:17px;font-weight:700;line-height:1.5;margin-bottom:6px}'
    '.top .meta{font-size:12px;color:rgba(255,255,255,0.6)}'
    '.summary{padding:16px 20px;background:#fff;border-bottom:1px solid #eef2f6}'
    '.s-row{display:flex;gap:10px;margin-bottom:10px}'
    '.s-row:last-child{margin-bottom:0}'
    '.s-item{flex:1;background:#f8fafc;border-radius:10px;padding:10px 12px}'
    '.s-item .lbl{font-size:10px;color:#94a3b8;letter-spacing:0.3px;margin-bottom:3px}'
    '.s-item .val{font-size:20px;font-weight:700;color:#0a1628;line-height:1.2}'
    '.s-item .val.gold{color:#b8860b}.s-item .val.green{color:#16a34a}.s-item .val.blue{color:#2563eb}.s-item .val.red{color:#dc2626}'
    '.type-row{padding:14px 20px;display:flex;gap:8px;flex-wrap:wrap;border-bottom:8px solid #f5f7fa}'
    '.type-tag{padding:5px 12px;border-radius:14px;font-size:12px;font-weight:500}'
    '.type-tag.m{background:#dbeafe;color:#1d4ed8}.type-tag.c{background:#fef3c7;color:#b45309}.type-tag.s{background:#d1fae5;color:#047857}'
    '.items{padding:0 20px 16px}'
    '.items h2{font-size:14px;font-weight:600;color:#1a2332;margin:12px 0 8px}'
    '.item-card{background:#f8fafc;border-radius:8px;padding:10px 12px;margin-bottom:6px}'
    '.item-card .it-name{font-size:13px;font-weight:500;color:#1a2332;margin-bottom:4px}'
    '.item-card .it-detail{display:flex;gap:10px;font-size:11px;color:#64748b;flex-wrap:wrap}'
    '.item-card .it-detail strong{color:#1a2332}'
    '.footer{padding:16px 20px;text-align:center;font-size:11px;color:#94a3b8;line-height:1.8;border-top:1px solid #eef2f6}'
    '.footer a{color:#2563eb;text-decoration:none}'
    '.badge{display:inline-block;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);color:#93c5fd;font-size:10px;padding:3px 10px;border-radius:12px;margin-bottom:8px;letter-spacing:0.5px}'
)

def generate_html_wechat(data):
    import datetime
    items, gt, _tt = prepare_items(data)
    bp = data.get('bid_price')
    cp = data.get('control_price')
    disc = data.get('discount_ratio')
    has_price = any((it.get('unit_price') or 0) > 0 for it in items)
    if not has_price:
        bp = cp = disc = None
    # 有没有「招投标信息」（中标金额／最高限价／下浮比例）。
    # 只有价格、没有中标信息的（如总包下发的分包清单），卡片改显示工程量口径。
    has_bid = bool(bp or cp or disc is not None)
    src = data.get('data_source', '重庆市公共资源交易网')
    pn = data.get('project_name', '未知项目')
    winner = data.get('winner') or data.get('top_candidate') or ''
    winner_label = '中标人' if data.get('winner') else '中标候选人第一名'
    td = datetime.date.today().strftime('%Y-%m-%d')
    
    def fm(n):
        if n is None: return '—'
        return '¥{:,.2f}'.format(n)
    
    membranes = [it for it in items if it.get('type') == '防水卷材']
    coatings = [it for it in items if it.get('type') == '防水涂料']
    mortars = [it for it in items if it.get('type') == '防水砂浆']
    others = [it for it in items if it.get('type') == '其他防水']
    
    L = ['<!DOCTYPE html><html lang="zh-CN"><head>']
    L.append('<meta charset="UTF-8">')
    L.append('<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">')
    L.append(f'<title>{pn} — 防水材料分析</title><style>{WECHAT_CSS_STR}</style></head><body>')
    L.append('<div class="container">')
    L.append(f'<div class="top"><div class="badge">🔨 防水材料分析</div>')
    L.append(f'<h1>{pn}</h1>')
    L.append(f'<div class="meta">{src} · {td}</div></div>')
    if winner: L.append(f'<div style="text-align:center;font-size:14px;font-weight:bold;color:#b8860b;background:#fff7e6;border-radius:8px;padding:8px 12px;margin:-4px 14px 12px;">\U0001f3c6 {winner_label}：{winner}</div>')
    
    disc_str = f'{disc:.2f}%' if disc is not None else '—'
    L.append('<div class="summary">')
    if has_bid:
        L.append('<div class="s-row">')
        L.append(f'<div class="s-item"><div class="lbl">中标金额</div><div class="val gold">{fm(bp)}</div></div>')
        L.append(f'<div class="s-item"><div class="lbl">最高限价</div><div class="val red">{fm(cp)}</div></div>')
        L.append('</div><div class="s-row">')
        L.append(f'<div class="s-item"><div class="lbl">下浮比例</div><div class="val green">{disc_str}</div></div>')
        L.append(f'<div class="s-item"><div class="lbl">防水总价</div><div class="val blue">{fm(gt)}</div></div>')
        L.append('</div>')
        if bp and bp > 0:
            pct = gt/bp*100
            L.append(f'<div style="text-align:center;font-size:12px;color:#64748b;margin-top:6px">防水占中标金额约 <strong style="color:#16a34a">{pct:.2f}%</strong></div>')
    else:
        _wq = sum(it.get('quantity',0) for it in items)
        _wk = len(set(it.get('name','') for it in items))
        L.append('<div class="s-row">')
        L.append(f'<div class="s-item"><div class="lbl">防水总面积</div><div class="val blue">{_wq:,.2f} m\u00b2</div></div>')
        L.append(f'<div class="s-item"><div class="lbl">材料种类</div><div class="val gold">{_wk}</div></div>')
        L.append('</div>')
        if not has_price:
            L.append('<div style="text-align:center;font-size:12px;color:#64748b;margin-top:6px">本清单未含综合单价，只列工程量</div>')
    L.append('</div>')
    
    L.append('<div class="type-row">')
    if membranes: L.append(f'<span class="type-tag m">防水卷材 {len(membranes)}项</span>')
    if coatings: L.append(f'<span class="type-tag c">防水涂料 {len(coatings)}项</span>')
    if mortars: L.append(f'<span class="type-tag s">防水砂浆 {len(mortars)}项</span>')
    if others: L.append(f'<span class="type-tag" style="background:#f1f5f9;color:#64748b">其它 {len(others)}项</span>')
    L.append('</div>')
    
    L.append('<div class="items">')
    for tname, tcls, tlist in [('防水卷材','m',membranes),('防水涂料','c',coatings),('防水砂浆','s',mortars),('其它防水','',others)]:
        if not tlist: continue
        L.append(f'<h2>{tname} ({len(tlist)}项)</h2>')
        for it in tlist:
            nm = it.get('name','')[:50]
            qty = it.get('quantity',0)
            up = it.get('unit_price',0)
            tp = it.get('total_price',0)
            loc = it.get('location','') or ''
            bld = it.get('building','') or ''
            if bld: loc = f'{bld} · {loc}' if loc else bld
            L.append('<div class="item-card">')
            L.append(f'<div class="it-name">{nm}</div>')
            L.append('<div class="it-detail">')
            _unit = it.get('unit', 'm\u00b2')
            if loc: L.append(f'<span><strong>{loc}</strong></span>')
            L.append(f'<span>量: <strong>{qty:,.2f} {_unit}</strong></span>')
            if has_price:
                L.append(f'<span>单价: <strong>¥{up:,.2f}</strong></span>')
                L.append(f'<span>合计: <strong>¥{tp:,.2f}</strong></span>')
            L.append('</div>')
            L.append('</div>')
    L.append('</div>')
    
    L.append(f'<div class="footer">')
    L.append(f'<p>数据来源：{src}</p>')
    L.append(f'<p>自动解析 · {td}</p>')
    L.append('</div></div></body></html>')
    
    return '\n'.join(L)


if __name__ == '__main__':
    import argparse as ap
    parser = ap.ArgumentParser(description='Generate waterproof analysis HTML report')
    parser.add_argument('input_json', help='Input JSON data file')
    parser.add_argument('output_html', nargs='?', help='Output desktop HTML file')
    parser.add_argument('--mobile-output', help='Output iPhone-optimized HTML file')
    parser.add_argument('--wechat-output', help='Output WeChat-optimized HTML file')
    parser.add_argument('--save-to-db', action='store_true', help='Append data to shared data warehouse')
    parser.add_argument('--merge-by-name', action='store_true',
                        help='把材料名称相同的条目合并成一条，工程量求和')
    args = parser.parse_args()

    with open(args.input_json) as f:
        data = json.load(f)

    if args.merge_by_name:
        data['merge_by_name'] = True

    # Save to data warehouse
    if args.save_to_db:
        save_to_database(data)
    
    # Desktop report
    html = generate_html(data)
    if args.output_html:
        with open(args.output_html, 'w') as f:
            f.write(html)
        print(f'Desktop report written to {args.output_html}')
    else:
        print(html)

    # Mobile report (optional)
    if args.mobile_output:
        mobile_html = generate_html_mobile(data)
        with open(args.mobile_output, 'w') as f:
            f.write(mobile_html)
        print(f'Mobile report written to {args.mobile_output}')
    
    # WeChat report (optional)
    if args.wechat_output:
        wechat_html = generate_html_wechat(data)
        with open(args.wechat_output, 'w') as f:
            f.write(wechat_html)
        print(f'WeChat report written to {args.wechat_output}')
