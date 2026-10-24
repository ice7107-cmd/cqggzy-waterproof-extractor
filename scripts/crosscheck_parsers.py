#!/usr/bin/env python3
"""pdfplumber 交叉校验：独立复核 PyMuPDF 坐标法的结果，抓「静默漏收」。

背景（2026-10-21）：
  坐标法（extract_waterproof.py）靠词汇坐标重建表格，遇到名称跨行拆字
  （「电梯挡墙外侧防」+「水」）或材料只写在项目特征里时，会整条静默丢弃。
  实测 n1.pdf（412 页）因此漏掉 5 条真实防水项，其中 4 条是卷材。
  pdfplumber 有真实表格线可依，列结构更稳，适合当「第二双眼睛」。

它不是第二条提取线（不做名称补全/部位拆分/TypeSafe 复核），
只做一件事：**比对两边的条目集合，把差异摆出来**。

用法：
  python3 crosscheck_parsers.py /tmp/qingdan.pdf                       # 现场跑坐标法后比对
  python3 crosscheck_parsers.py /tmp/qingdan.pdf --json /tmp/wp.json   # 复用已有提取结果
  python3 crosscheck_parsers.py /tmp/qingdan.pdf --strict              # 有差异即退出码 1

退出码：0 = 无差异；1 = 存在疑似漏收或数值不一致；2 = 参数/环境问题。
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_waterproof as ew  # noqa: E402  复用同一份判定口径

CODE_RE = re.compile(r'^\d{10,20}$')
SEQ_RE = re.compile(r'^\d{1,4}$')
# 宽进口径：名称/特征里出现这些词才值得比对（与 extract_waterproof 的 BROAD_KW 保持同源）
BROAD = set(ew.BROAD_KW) | {'防水', '防渗', '止水', '防潮', '卷材', '涂膜', '自粘胶膜'}
HDR = {
    'seq': ('序号',),
    'code': ('项目编码', '编码'),
    'name': ('项目名称', '名称'),
    'feat': ('项目特征', '特征'),
    'unit': ('计量单位', '单位'),
    'qty': ('工程量', '数量'),
    'up': ('综合单价',),
    'tp': ('合价', '金额'),
}


def _num(s):
    m = re.fullmatch(r'-?[\d,]+\.?\d*', (s or '').replace(' ', ''))
    if not m:
        return None
    try:
        return float(m.group().replace(',', ''))
    except ValueError:
        return None


def _header_map(table):
    """在表格前 3 行里定位列名 → 列号；表头常分两行（计量/单位、综合单价/合价）。"""
    col = {}
    for row in table[:3]:
        for i, c in enumerate(row):
            t = re.sub(r'\s+', '', (c or ''))
            if not t:
                continue
            for key, names in HDR.items():
                if key in col:
                    continue
                if any(t == n for n in names):
                    col[key] = i
    need = {'code', 'name', 'feat', 'qty'}
    return col if need <= set(col) else None


def pdfplumber_items(pdf_path):
    """用 pdfplumber 抽表 → 按列名取值 → 套用同一套规则，返回 {code: item}。"""
    import pdfplumber

    out, tables_seen, pages_seen = {}, 0, 0
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                continue
            pages_seen += 1
            for tb in tables:
                tables_seen += 1
                col = _header_map(tb)
                if not col:
                    continue
                for row in tb:
                    def cell(k):
                        i = col.get(k)
                        return (row[i] or '') if i is not None and i < len(row) else ''
                    code = re.sub(r'\s+', '', cell('code'))
                    seq = re.sub(r'\s+', '', cell('seq'))
                    if not CODE_RE.match(code) or not SEQ_RE.match(seq):
                        continue
                    name = re.sub(r'\s+', '', cell('name'))
                    feat = re.sub(r'\s+', '', cell('feat'))
                    text = name + feat
                    if not any(k in text for k in BROAD):
                        continue
                    if ew.vetoed(name):          # 与主流程同一套否决口径
                        continue
                    spec = ew.feature_spec(feat)
                    # 与 make_item 同款：拆除项（特征是旧做法、工作内容写拆除）不靠特征收录
                    if spec and ew.is_demolition(feat) and not any(k in name for k in ew.STRONG_KW):
                        spec = ''
                    if (not any(k in name for k in BROAD)
                            and not spec and not ew.rule_for(name)):
                        continue
                    # 与 make_item 的 is_strong 同款门槛：只有会被写进报告的条目才值得比对。
                    # 否则「脚手架搭拆-消防水」（消防水 里含「防水」子串）这类噪音会刷屏。
                    if not (any(k in name for k in ew.STRONG_KW)
                            or spec or ew.rule_for(name)):
                        continue
                    # 与 make_item 同款：附属构件项按长度计量的排除（名称无材料词 + m/km）
                    if (not any(k in name for k in ew.STRONG_KW)
                            and not ew.rule_for(name)
                            and ew._norm_unit(cell('unit')) in ('m', 'km')):
                        continue
                    qty = _num(cell('qty'))
                    up = _num(cell('up'))
                    tp = _num(cell('tp'))
                    if not qty or qty <= 0:
                        continue
                    if not up and tp:
                        up = tp / qty
                    if not up or up <= 0:
                        continue
                    out[code] = {
                        'code': code, 'item_no': int(seq), 'name': name,
                        'unit': cell('unit') or '', 'quantity': round(qty, 2),
                        'unit_price': round(up, 2), 'page': pno,
                        'type': ew.classify(name) if ew.classify(name) != '其他防水'
                                else (ew.boundary_type(spec) or '其他防水'),
                    }
    return out, {'pages_with_tables': pages_seen, 'tables': tables_seen}


def main():
    ap = argparse.ArgumentParser(description='pdfplumber 交叉校验（抓静默漏收）')
    ap.add_argument('pdf')
    ap.add_argument('--json', help='复用 extract_waterproof.py 已输出的 JSON，不重跑坐标法')
    ap.add_argument('--strict', action='store_true', help='有差异时退出码 1')
    args = ap.parse_args()

    t0 = time.time()
    if args.json:
        with open(args.json, encoding='utf-8') as f:
            coord = json.load(f)
        main_items = coord.get('items', [])
    else:
        main_items = ew.extract(args.pdf)['items']
    # 同一条清单项被复合拆分后会有多行共用同一个项目编码：比对时只取主行
    # （金额行），拆分行是「工程量重复、金额为 0」的补充行，不参与数值比对。
    by_code = {}
    for i in main_items:
        c = i.get('code')
        if not c:
            continue
        if i.get('_split_note') and c in by_code:
            continue
        by_code[c] = i

    pl, stats = pdfplumber_items(args.pdf)

    only_pl = [v for k, v in pl.items() if k not in by_code]
    only_main = [v for k, v in by_code.items() if k not in pl]
    mismatch = []
    for k, v in by_code.items():
        o = pl.get(k)
        if not o:
            continue
        dq = abs((o['quantity'] or 0) - (v.get('quantity') or 0))
        du = abs((o['unit_price'] or 0) - (v.get('unit_price') or 0))
        if dq > 0.01 or du > 0.01:
            mismatch.append((k, v['name'][:24], v.get('quantity'), v.get('unit_price'),
                             o['quantity'], o['unit_price']))

    elapsed = round(time.time() - t0, 1)
    print(f'== 交叉校验 {os.path.basename(args.pdf)} ==')
    print(f'   坐标法条目 {len(by_code)} | pdfplumber 条目 {len(pl)} | '
          f'有表页 {stats["pages_with_tables"]} 表 {stats["tables"]} | 用时 {elapsed}s')
    if only_pl:
        print(f'\n⚠️  疑似漏收（pdfplumber 有、坐标法没有）{len(only_pl)} 条：')
        for v in sorted(only_pl, key=lambda x: (x['page'], x['item_no'])):
            print(f"   p{v['page']} 序号{v['item_no']} {v['code']} | {v['name'][:40]} | "
                  f"{v['unit']} {v['quantity']} @{v['unit_price']}")
    if mismatch:
        print(f'\n⚠️  数值不一致 {len(mismatch)} 条：')
        for k, nm, q1, u1, q2, u2 in mismatch:
            print(f'   {k} {nm} | 坐标法 {q1}@{u1} vs pdfplumber {q2}@{u2}')
    if only_main:
        print(f'\nℹ️  仅坐标法有 {len(only_main)} 条（可能是 pdfplumber 未识别该页表格，需人工确认）：')
        for v in sorted(only_main, key=lambda x: (x.get('page') or 0, x.get('item_no') or 0))[:20]:
            print(f"   p{v.get('page')} {v.get('code')} | {v.get('name','')[:40]} | "
                  f"{v.get('unit')} {v.get('quantity')} @{v.get('unit_price')}")
    if not (only_pl or mismatch or only_main):
        print('\n✅ 两条解析线结果一致，无差异。')

    bad = bool(only_pl or mismatch)
    if args.strict and bad:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
