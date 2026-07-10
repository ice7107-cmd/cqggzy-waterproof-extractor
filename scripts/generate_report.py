#!/usr/bin/env python3
"""Generate waterproof analysis HTML report from JSON data."""
import json, sys
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
footer{text-align:center;padding:14px;color:#94a3b8;font-size:10px;line-height:1.6}
footer a{color:#2563eb;text-decoration:none}
"""

def fmt_money(n):
    if n is None: return "\u2014"
    return f"\u00a5{n:,.2f}"

def fmt_pct(n, total):
    if total and total > 0: return f"{n/total*100:.2f}%"
    return "\u2014"

def render_item_table(title, icon, icon_cls, items, type_label):
    if not items: return ""
    tag_map = {"防水卷材": "membrane", "防水涂料": "coating", "防水砂浆": "mortar", "其他": "mortar"}
    tag_cls = tag_map.get(type_label, "mortar")
    h = f'<div class="section-card"><div class="section-header"><div class="icon {icon_cls}">{icon}</div><h2>{title}</h2></div><div class="section-body"><table><thead><tr><th>序号</th><th>部位</th><th>材料名称</th><th>单位</th><th class="num">工程量</th><th class="num">综合单价(元)</th><th class="num">合价(元)</th></tr></thead><tbody>'
    for idx, it in enumerate(items, 1):
        nm = it['name'][:50]
        loc = it.get('location', '') or ''
        dao_note = it.get('_dao_note', '')
        if dao_note:
            qty_display = f"{it['quantity']:,.2f} {dao_note}"
        else:
            qty_display = f"{it['quantity']:,.2f}"
        h += f'<tr><td>{idx}</td><td>{loc}</td><td><span class="tag {tag_cls}">{"卷材" if type_label=="防水卷材" else "涂料" if type_label=="防水涂料" else "砂浆"}</span> {nm}</td><td>{it["unit"]}</td><td class="num">{qty_display}</td><td class="num">{it["unit_price"]:.2f}</td><td class="num">{it["total_price"]:,.2f}</td></tr>'
    # Add total row
    total_qty = sum(it['quantity'] for it in items)
    total_price = sum(it['total_price'] for it in items)
    unit = items[0]['unit'] if items else ''
    h += f'<tr style="background:#f0fdf4;font-weight:600"><td colspan="2"></td><td><span style="color:#15803d">本类合计</span></td><td class="num">{unit}</td><td class="num">{total_qty:,.2f}</td><td></td><td class="num">{total_price:,.2f}</td></tr>'
    h += '</tbody></table></div></div>'
    return h

def generate_html(data):
    items = data.get('items', [])
    gt = data.get('grand_total', 0)
    bp = data.get('bid_price')
    cp = data.get('control_price')
    disc = data.get('discount_ratio')
    em = '—'
    pn = data.get('project_name', '未知项目')
    bu = data.get('bid_url', '')
    cu = data.get('clarify_url', '')
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
    L.append(f'<div class="subtitle">数据来源：重庆市公共资源交易网 \u00b7 答疑补遗附件 \u00b7 工程量清单.pdf</div></div>')

    # Stats
    L.append('<div class="stats-grid">')
    L.append(f'<div class="stat-card"><div class="stat-label">中标金额</div><div class="stat-value gold">{fmt_money(bp)}</div><div class="stat-note">施工总承包</div></div>')
    L.append(f'<div class="stat-card"><div class="stat-label">最高限价</div><div class="stat-value red">{fmt_money(cp)}</div><div class="stat-note">招标控制价</div></div>')
    L.append(f'<div class="stat-card"><div class="stat-label">下浮比例</div><div class="stat-value green">{disc if disc is not None else em}</div><div class="stat-note">较最高限价下浮</div></div>')
    L.append(f'<div class="stat-card"><div class="stat-label">防水卷材总面积</div><div class="stat-value blue">{total_mem_qty:,.2f}</div><div class="stat-note">m\u00b2</div></div>')
    L.append('</div>')

    # Project info
    if pn or bu or cu:
        L.append('<div class="section-card"><div class="section-header"><div class="icon cyan">\U0001f4cc</div><h2>项目基本信息</h2></div><div class="section-body"><div class="info-grid">')
        L.append(f'<div class="info-label">项目名称</div><div class="info-value">{pn}</div>')
        if bp: L.append(f'<div class="info-label">中标金额</div><div class="info-value">{fmt_money(bp)}</div>')
        if cp: L.append(f'<div class="info-label">最高限价</div><div class="info-value">{fmt_money(cp)}</div>')
        if disc is not None: L.append(f'<div class="info-label">下浮比例</div><div class="info-value">{disc}%</div>')
        if cu: L.append(f'<div class="info-label">答疑补遗</div><div class="info-value"><a href="{cu}" target="_blank">查看原文</a></div>')
        if bu: L.append(f'<div class="info-label">中标结果公告</div><div class="info-value"><a href="{bu}" target="_blank">查看原文</a></div>')
        L.append('</div></div></div>')

    # Tables
    L.append(render_item_table('防水卷材', '\U0001f504', 'blue', membranes, '防水卷材'))
    L.append(render_item_table('防水涂料', '\U0001f6e2\ufe0f', 'amber', coatings, '防水涂料'))
    L.append(render_item_table('防水砂浆', '\U0001f9f1', 'green', mortars, '防水砂浆'))
    if others:
        L.append(render_item_table('其他防水材料', '\U0001f4cb', 'rose', others, '其他'))

    # Summary
    if items:
        L.append('<div class="section-card"><div class="section-header"><div class="icon purple">\U0001f4ca</div><h2>防水材料综合汇总</h2></div><div class="section-body" style="padding-bottom:4px;"><table><thead><tr><th>材料大类</th><th>材料名称</th><th class="num">工程量</th><th class="num">综合单价(元)</th><th class="num">合价(元)</th><th class="num">占比</th></tr></thead><tbody>')
        for it in items:
            tl = {'防水卷材':'卷材','防水涂料':'涂料','防水砂浆':'砂浆','其他防水':'其他'}.get(it['type'],'')
            L.append(f'<tr><td style="font-weight:600;">{it["type"]}</td><td>{tl} {it["name"][:35]}</td><td class="num">{it["quantity"]:,.2f} {it["unit"]}</td><td class="num">{it["unit_price"]:.2f}</td><td class="num" style="font-weight:600;">{it["total_price"]:,.2f}</td><td class="num">{fmt_pct(it["total_price"], gt)}</td></tr>')
        L.append(f'<tr style="background:#f8fafc;font-weight:700;"><td colspan="4" style="text-align:right;">防水部分合计</td><td class="num" style="color:#b8860b;">{gt:,.2f}</td><td class="num">100%</td></tr>')
        if bp: L.append(f'<tr style="background:#f0fdf4;"><td colspan="4" style="text-align:right;color:#166534;">占中标金额比例</td><td class="num" style="color:#16a34a;font-weight:700;">{fmt_pct(gt, bp)}</td><td class="num" style="color:#16a34a;">\u2014</td></tr>')
        if cp: L.append(f'<tr style="background:#fef2f2;"><td colspan="4" style="text-align:right;color:#991b1b;">占最高限价比例</td><td class="num" style="color:#dc2626;font-weight:700;">{fmt_pct(gt, cp)}</td><td class="num" style="color:#dc2626;">\u2014</td></tr>')
        L.append('</tbody></table></div></div>')

    # Summary box
    L.append(f'<div class="summary-box"><strong>\U0001f4cc 防水体系概览：</strong>本项目防水材料共提取到 <strong>{len(items)}</strong> 项可量化条目，其中防水卷材 <strong>{len(membranes)}</strong> 项、防水涂料 <strong>{len(coatings)}</strong> 项、防水砂浆 <strong>{len(mortars)}</strong> 项。防水部分总造价约 <strong>\u00a5{gt:,.2f}</strong>。')
    if bp: L.append(f'占中标金额约 <strong>{fmt_pct(gt, bp)}</strong>。')
    L.append('</div>')

    # Footer
    L.append('<footer>')
    L.append('<p>数据来源：<a href="https://www.cqggzy.com" target="_blank">重庆市公共资源交易网（cqggzy.com）</a></p>')
    if bu: L.append(f'<p>中标结果公告：<a href="{bu}" target="_blank">查看原文</a></p>')
    if cu: L.append(f'<p>答疑补遗：<a href="{cu}" target="_blank">查看原文</a></p>')
    L.append(f'<p style="margin-top:4px;">本报告由工程量清单PDF自动解析生成 \u00b7 数据抓取日期：{td} \u00b7 仅供参考</p>')
    L.append('</footer></div></body></html>')

    return '\n'.join(L)


def generate_html_mobile(data):
    """Generate iPhone-optimized mobile HTML report."""
    items = data.get('items', [])
    gt = data.get('grand_total', 0)
    bp = data.get('bid_price')
    cp = data.get('control_price')
    disc = data.get('discount_ratio')
    em = '—'
    pn = data.get('project_name', '未知项目')
    bu = data.get('bid_url', '')
    cu = data.get('clarify_url', '')
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
    L.append(f'<div class="subtitle">重庆市公共资源交易网 · 工程量清单.pdf</div></div>')

    # Stats
    L.append('<div class="stats-grid">')
    L.append(f'<div class="stat-card"><div class="stat-label">中标金额</div><div class="stat-value gold">{fmt_money(bp)}</div></div>')
    L.append(f'<div class="stat-card"><div class="stat-label">最高限价</div><div class="stat-value red">{fmt_money(cp)}</div></div>')
    L.append(f'<div class="stat-card"><div class="stat-label">下浮比例</div><div class="stat-value green">{disc if disc is not None else em}</div></div>')
    L.append(f'<div class="stat-card"><div class="stat-label">防水材料总价</div><div class="stat-value blue">{gt_label}</div></div>')
    L.append('</div>')

    # Project info
    if pn or bu or cu:
        L.append('<div class="section-card"><div class="section-header"><div class="icon cyan">📌</div><h2>项目基本信息</h2></div><div class="section-body"><div class="info-grid">')
        L.append(f'<div class="info-label">项目名称</div><div class="info-value">{pn}</div>')
        if bp: L.append(f'<div class="info-label">中标金额</div><div class="info-value">{fmt_money(bp)}</div>')
        if cp: L.append(f'<div class="info-label">最高限价</div><div class="info-value">{fmt_money(cp)}</div>')
        if disc is not None: L.append(f'<div class="info-label">下浮比例</div><div class="info-value">{disc}%</div>')
        if cu: L.append(f'<div class="info-label">答疑补遗</div><div class="info-value"><a href="{cu}" target="_blank">查看原文</a></div>')
        if bu: L.append(f'<div class="info-label">中标结果</div><div class="info-value"><a href="{bu}" target="_blank">查看原文</a></div>')
        L.append('</div></div></div>')

    # Tables
    L.append(render_item_table('防水卷材', '🔄', 'blue', membranes, '防水卷材'))
    L.append(render_item_table('防水涂料', '🛢️', 'amber', coatings, '防水涂料'))
    L.append(render_item_table('防水砂浆', '🧱', 'green', mortars, '防水砂浆'))
    if others:
        L.append(render_item_table('其他防水材料', '📋', 'rose', others, '其他'))

    # Summary box
    L.append(f'<div class="summary-box"><strong>📌 防水体系概览：</strong>本项目共提取 <strong>{len(items)}</strong> 项，其中防水卷材 <strong>{len(membranes)}</strong> 项、防水涂料 <strong>{len(coatings)}</strong> 项、防水砂浆 <strong>{len(mortars)}</strong> 项。防水部分总造价约 <strong>¥{gt:,.2f}</strong>。')
    if bp: L.append(f'占中标金额约 <strong>{fmt_pct(gt, bp)}</strong>。')
    L.append('</div>')

    # Footer
    L.append('<footer>')
    L.append('<p>数据来源：<a href="https://www.cqggzy.com" target="_blank">重庆市公共资源交易网</a></p>')
    if bu: L.append(f'<p>中标结果：<a href="{bu}" target="_blank">查看原文</a></p>')
    if cu: L.append(f'<p>答疑补遗：<a href="{cu}" target="_blank">查看原文</a></p>')
    L.append(f'<p style="margin-top:4px;">PDF自动解析 · {td} · 仅供参考</p>')
    L.append('</footer></div></body></html>')

    return '\n'.join(L)


if __name__ == '__main__':
    import argparse as ap
    parser = ap.ArgumentParser(description='Generate waterproof analysis HTML report')
    parser.add_argument('input_json', help='Input JSON data file')
    parser.add_argument('output_html', nargs='?', help='Output desktop HTML file')
    parser.add_argument('--mobile-output', help='Output iPhone-optimized HTML file')
    args = parser.parse_args()

    with open(args.input_json) as f:
        data = json.load(f)

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
