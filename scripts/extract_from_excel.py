#!/usr/bin/env python3
"""
从 Excel/CSV 版工程量清单里提取防水材料。

适用场景：甲方或总包直接给了 .xlsx/.xls/.csv 版「分部分项工程清单计价表」，
而不是 cqggzy 上的 PDF。（新津项目就是这种）

用法：
  python3 extract_from_excel.py "新津-防水.xlsx" --project-name "新津项目" -o /tmp/data.json
  python3 extract_from_excel.py "清单.xlsx" --screen -o /tmp/data.json     # 顺带 TypeSafe 复核
  python3 extract_from_excel.py "清单.csv" --dry-run                       # 只看解析结果
"""
import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_waterproof as ew

# 表头列名候选（出现这些词就认为是这一列）
COL_HINTS = {
    'code': ['项目编码', '编码', '清单编码', '项目编号'],
    'name': ['项目名称', '清单名称', '名称', '项目'],
    'feature': ['项目特征', '特征描述', '项目特征描述'],
    'unit': ['计量单位', '单位'],
    'qty': ['工程量', '数量'],
    'unit_price': ['综合单价', '单价'],
    'total_price': ['合价', '金额'],
    'seq': ['序号'],
}


def _s(v):
    return '' if v is None else str(v).strip()


def _num(v):
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r'[,\s￥¥元]', '', str(v))
    m = re.fullmatch(r'-?\d+\.?\d*', t)
    return float(m.group()) if m else None


def _match_col(header_cell):
    """把表头单元格文字映射到列名。"""
    h = re.sub(r'\s+', '', _s(header_cell))
    if not h:
        return None
    for key, hints in COL_HINTS.items():
        for hint in hints:
            if h == hint:
                return key
    for key, hints in COL_HINTS.items():
        for hint in hints:
            if hint in h:
                return key
    return None


def _sheet_rows(ws):
    return [[c for c in row] for row in ws.iter_rows(values_only=True)]


def _merge_subheader(cols, sub_row):
    """清单表头常拆两行：「金额（元）」在上一行，「综合单价／合价」在下一行。

    子表头（下一行）里能认出来的列名以它为准，覆盖父行的映射，避免单价串列。
    """
    if not sub_row:
        return cols
    for ci, cell in enumerate(sub_row):
        k = _match_col(cell)
        if not k:
            continue
        for kk in [x for x, i in cols.items() if i == ci]:
            cols.pop(kk, None)
        cols[k] = ci
    return cols


def _find_header(rows):
    """在前 15 行里找表头行，返回 (行号, {列名: 列索引})。"""
    for ri, row in enumerate(rows[:15]):
        cols = {}
        for ci, cell in enumerate(row):
            k = _match_col(cell)
            if k and k not in cols:
                cols[k] = ci
        if 'code' in cols and ('name' in cols or 'qty' in cols):
            return ri, _merge_subheader(cols, rows[ri + 1] if ri + 1 < len(rows) else None)
    return None, None


def _building_of(sheet_title):
    """从 sheet 名里取单体名：…【地下室‖建筑… → 地下室"""
    m = re.search(r'[【\[]([^】\]‖|]+)', sheet_title)
    if m:
        return m.group(1).strip()
    m = re.search(r'工程名称[:：]\s*([^\s]+)', sheet_title)
    if m:
        return m.group(1).strip()
    return sheet_title.strip()


def _project_name_marks(rows):
    """扫描整表，找出所有「工程名称：X」所在行，返回 {行号: 单体名}。

    有些清单把多个单体拼在同一张 sheet 里（如 多联式转运中心／综合楼／室外工程），
    每个单体前面会重新写一行「工程名称：xxx」。
    """
    marks = {}
    for ri, row in enumerate(rows):
        for cell in row:
            t = _s(cell)
            m = re.match(r'^工程名称\s*[:：]\s*(.+)$', t)
            if m:
                marks[ri] = m.group(1).strip()
                break
    return marks


def is_waterproof_row(name, feature=''):
    """宽进过滤：项目名称（或特征）里带防水关键词就留，其余整表跳过。

    不这么做的话，一张完整的「分部分项清单计价表」会把几千条土建、电气条目
    一起收进来（只有 TypeSafe 复核那一步才做剔除）。
    """
    nm = _s(name)
    if ew.vetoed(nm):
        return False   # 洁净板／1:3 普通砂浆找平层／划线漆… 名称层就排除
    if ew.classify(nm) != '其他防水' or ew.rule_for(nm):
        return True
    # 材料只写在「项目特征」里的行（如「消防水池楼板整治」+「1.5mm水泥基渗透结晶」）
    return bool(ew.feature_spec(_s(feature)))


def parse_xlsx(path, verbose=True, sheets=None, only_waterproof=True):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    items, sheets_used = [], []
    for ws in wb.worksheets:
        if sheets and ws.title not in sheets:
            continue
        rows = _sheet_rows(ws)
        hi, cols = _find_header(rows)
        if cols is None:
            # 退一步：试试「防水专业分包清单」布局
            fb = parse_fenbao_sheet(ws, verbose)
            if fb:
                items.extend(fb)
                sheets_used.append((ws.title, len(fb)))
                if verbose:
                    print(f'  {ws.title[:46]:<48} {len(fb):>4} 条（专业分包清单）', file=sys.stderr)
                continue
            if verbose:
                print(f'  [跳过] {ws.title}：没找到表头', file=sys.stderr)
            continue
        marks = _project_name_marks(rows)
        bldg = _building_of(ws.title)
        n0 = len(items)
        for ri, row in enumerate(rows[hi + 1:], start=hi + 1):
            if ri in marks:
                bldg = marks[ri]
            def cell(key):
                i = cols.get(key)
                return row[i] if i is not None and i < len(row) else None
            code = _s(cell('code'))
            if not re.fullmatch(r'\d{6,20}', code):
                continue
            nm = _s(cell('name'))
            if not nm:
                continue
            qty = _num(cell('qty'))
            if not qty or qty <= 0:
                continue
            if only_waterproof and not is_waterproof_row(nm, _s(cell('feature'))):
                continue
            up = _num(cell('unit_price'))
            tp = _num(cell('total_price'))
            unit = _s(cell('unit')) or 'm2'
            feat = _s(cell('feature'))
            spec = ew.feature_spec(feat)
            loc, rest = ew.extract_location(nm)
            if not loc:
                parts = nm.split(' ', 1)
                if len(parts) == 2:
                    loc, rest = parts[0], parts[1]
            disp = (rest or nm).strip()
            # 2026-10-21 用户口径：材料名称只取防水材料本身，构造名进 location（与 PDF 路线一致）
            material = spec.strip() if spec else disp
            if not loc:
                _base = disp
                if spec:
                    for _cand in (f'（{spec[:60]}）', f'（{spec}）'):
                        if _base.endswith(_cand):
                            _base = _base[:-len(_cand)]
                            break
                if _base and _base != material and not any(k in _base for k in ew.STRONG_KW):
                    loc = _base.strip(' 　:：-—、')
            # 与 PDF 路线同款：名称无材料词 + 长度单位的附属构件项排除
            if (not any(k in nm for k in ew.STRONG_KW)) and not ew.rule_for(nm) \
                    and ew._norm_unit(unit) in ('m', 'km'):
                continue
            t = ew.classify(nm)
            if t == '其他防水':
                t = ew.boundary_type(spec or nm) or (ew.classify(spec) if spec else t)
            items.append({
                'item_no': len(items) + 1,
                'code': code,
                'name': material[:120],
                'item_name': nm[:120],
                'location': loc,
                'building': bldg,
                'unit': ew._norm_unit(unit),
                'quantity': round(qty, 2),
                'unit_price': round(up, 2) if up else 0.0,
                'total_price': round(tp, 2) if tp else (round(qty * up, 2) if up else 0.0),
                'type': t,
                'page': bldg,
                'feature': feat[:300],
            })
        sheets_used.append((ws.title, len(items) - n0))
        if verbose:
            print(f'  {ws.title[:46]:<48} {len(items)-n0:>4} 条', file=sys.stderr)
    return items, sheets_used


# ---------------------------------------------------------------- 专业分包清单布局
# 总包/甲方下发的「防水工程专业分包清单」：没有项目编码列，材料写在「项目特征描述」里。
FENBAO_COL_HINTS = {
    'seq': ['序号'],
    'name': ['项目名称', '清单项目名称', '分项名称'],
    'feature': ['项目特征描述', '项目特征', '特征描述', '工作内容'],
    'qty': ['工程量', '数量'],
    'unit': ['单位', '计量单位'],
    'unit_price': ['含税单价', '不含税单价', '综合单价', '单价'],
    'total_price': ['含税合计', '不含税合价', '合价'],
    'note': ['备注'],
}

# 好材料名 = 厚度规格 + （可选）做法描述 + 材料名词
_MAT_RE = re.compile(
    r'(?:(?P<coats>\d+\s*道)\s*)?'
    r'(?P<spec>\d+(?:\.\d+)?\s*(?:mm)?'
    r'(?:\s*\+\s*\d+(?:\.\d+)?\s*(?:mm)?)*\s*厚)'
    r'(?P<mid>[^,，;；()（）]{0,12}?)'
    r'(?P<noun>防水卷材|涂膜防水|防水涂料|卷材|防水砂浆|防水涂膜)'
    r'(?P<tail>\([^()（）]{0,8}\))?'
    r'(?P<extra>一布两涂|两布三涂|一布一涂)?'
)
_LONG_PAREN = re.compile(r'[(（][^()（）]{9,}[)）]')
_GROUP_SEQ = re.compile(r'^[一二三四五六七八九十]+$')
# 边界材料清单（渗透结晶、聚合物防水涂料、聚合物水泥防水涂料／砂浆）统一由
# references/material_rules.json 定义，这里不再另写一份正则，避免两条路线口径漂移。


def find_materials(text):
    """从项目特征描述里抽出防水材料名（一条可能含多种材料）。"""
    if not text:
        return []
    t = _LONG_PAREN.sub('', str(text))
    out = []
    spans = []
    for m in _MAT_RE.finditer(t):
        spans.append(m.span())
        name = ''.join(x for x in (m.group('coats'), m.group('spec'),
                                   m.group('mid'), m.group('noun')) if x)
        if m.group('tail'):
            name += m.group('tail')
        if m.group('extra'):
            name += m.group('extra')
        name = re.sub(r'\s+', '', name)
        if name not in out:
            out.append(name)
    # 与上面已匹配区间重叠时跳过，避免同一行拆出两种材料重复计量
    if ew.USER_MAT_RE is not None:
        for m in ew.USER_MAT_RE.finditer(t):
            if any(s <= m.start() < e for s, e in spans):
                continue
            # 排除项（抗裂砂浆／水泥砂浆找平层…）旁边的命中不算
            window = t[max(0, m.start() - 30):m.end() + 10]
            if ew.vetoed(window):
                continue
            name = ''.join(x for x in (m.group('spec'), m.group('noun')) if x)
            name = re.sub(r'\s+', '', name)
            if name and name not in out:
                out.append(name)
    return out


def clean_fenbao_location(name):
    """「不发火混凝土地面 位置：浅圆仓地面」→「不发火混凝土地面」"""
    t = re.sub(r'\s*位置[:：].*$', '', str(name or ''))
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _match_fenbao_col(cell):
    h = re.sub(r'\s+', '', _s(cell))
    if not h:
        return None
    for key, hints in FENBAO_COL_HINTS.items():
        if h in hints:
            return key
    for key, hints in FENBAO_COL_HINTS.items():
        for hint in hints:
            if hint in h:
                return key
    return None


def _find_fenbao_header(rows):
    for ri, row in enumerate(rows[:15]):
        cols = {}
        for ci, cell in enumerate(row):
            k = _match_fenbao_col(cell)
            if k and k not in cols:
                cols[k] = ci
        if 'name' in cols and 'qty' in cols and 'code' not in cols:
            return ri, _merge_subheader(cols, rows[ri + 1] if ri + 1 < len(rows) else None)
    return None, None


def parse_fenbao_sheet(ws, verbose=True):
    rows = _sheet_rows(ws)
    hi, cols = _find_fenbao_header(rows)
    if cols is None:
        return []
    items, bldg = [], ''
    for row in rows[hi + 1:]:
        def cell(key):
            i = cols.get(key)
            return row[i] if i is not None and i < len(row) else None
        seq = _s(cell('seq'))
        nm = _s(cell('name'))
        qty = _num(cell('qty'))
        # 分部标题行：序号是「一/二/三」且没有工程量
        if seq and _GROUP_SEQ.fullmatch(seq) and not qty:
            bldg = nm
            continue
        if not qty or qty <= 0:
            continue
        mats = find_materials(cell('feature'))
        if not mats:
            continue
        up = _num(cell('unit_price')) or 0.0
        tp = _num(cell('total_price')) or (round(qty * up, 2) if up else 0.0)
        unit = ew._norm_unit(_s(cell('unit')) or 'm2')
        # 与 PDF 路线同款：名称无材料词 + 长度单位的附属构件项排除
        if (not any(k in nm for k in ew.STRONG_KW)) and not ew.rule_for(nm) and unit in ('m', 'km'):
            continue
        loc = clean_fenbao_location(nm)
        for mat in mats:
            items.append({
                'item_no': len(items) + 1,
                'code': '',
                'name': mat,
                'location': loc,
                'building': bldg,
                'unit': unit if unit in ('m²', '㎡') else ew._norm_unit(_s(cell('unit'))),
                'quantity': round(qty, 2),
                'unit_price': round(up, 2),
                'total_price': round(tp, 2),
                'type': ew.classify(mat),
                'page': bldg,
                'feature': _s(cell('feature'))[:300],
            })
    return items


def parse_csv(path, verbose=True, only_waterproof=True):
    items = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.reader(f)]
    hi, cols = _find_header(rows)
    if cols is None:
        return [], []
    for row in rows[hi + 1:]:
        def cell(key):
            i = cols.get(key)
            return row[i] if i is not None and i < len(row) else None
        code = _s(cell('code'))
        if not re.fullmatch(r'\d{6,20}', code):
            continue
        nm = _s(cell('name'))
        qty = _num(cell('qty'))
        if not nm or not qty or qty <= 0:
            continue
        if only_waterproof and not is_waterproof_row(nm, _s(cell('feature'))):
            continue
        up = _num(cell('unit_price')) or 0.0
        tp = _num(cell('total_price')) or (round(qty * up, 2) if up else 0.0)
        feat = _s(cell('feature'))
        spec = ew.feature_spec(feat)
        loc, rest = ew.extract_location(nm)
        disp = (rest or nm).strip()
        # 2026-10-21 用户口径：材料名称只取防水材料本身，构造名进 location（与 PDF 路线一致）
        material = spec.strip() if spec else disp
        if not loc:
            _base = disp
            if spec:
                for _cand in (f'（{spec[:60]}）', f'（{spec}）'):
                    if _base.endswith(_cand):
                        _base = _base[:-len(_cand)]
                        break
            if _base and _base != material and not any(k in _base for k in ew.STRONG_KW):
                loc = _base.strip(' 　:：-—、')
        _unit = ew._norm_unit(_s(cell('unit')) or 'm2')
        # 与 PDF 路线同款：名称无材料词 + 长度单位的附属构件项排除
        if (not any(k in nm for k in ew.STRONG_KW)) and not ew.rule_for(nm) and _unit in ('m', 'km'):
            continue
        t = ew.classify(nm)
        if t == '其他防水':
            t = ew.boundary_type(spec or nm) or (ew.classify(spec) if spec else t)
        items.append({
            'item_no': len(items) + 1, 'code': code, 'name': material[:120],
            'item_name': nm[:120],
            'location': loc, 'building': '', 'unit': _unit,
            'quantity': round(qty, 2), 'unit_price': round(up, 2), 'total_price': round(tp, 2),
            'type': t, 'page': '', 'feature': feat[:300],
        })
    return items, [('(csv)', len(items))]


def build(path, verbose=True, sheets=None, only_waterproof=True):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        items, used = parse_csv(path, verbose, only_waterproof)
    elif ext in ('.xlsx', '.xlsm'):
        items, used = parse_xlsx(path, verbose, sheets, only_waterproof)
    elif ext == '.xls':
        # 老版 Excel 交给 pandas 读，避免额外依赖
        import pandas as pd
        tmp = path + '.tmp.xlsx'
        pd.read_excel(path, sheet_name=None).items()
        raise SystemExit('老版 .xls 请先用 Excel 另存为 .xlsx 再跑。')
    else:
        raise SystemExit(f'不支持的文件类型：{ext}')

    # 去重（同编码/同名 且 同量、同单体 才算重复）
    seen, res = set(), []
    for it in items:
        k = (it['code'], it['name'], round(it['quantity'], 1), it['building'])
        if k not in seen:
            seen.add(k)
            res.append(it)

    tt = {}
    for it in res:
        e = tt.setdefault(it['type'], {'count': 0, 'total_qty': 0, 'total_price': 0})
        e['count'] += 1
        e['total_qty'] += it['quantity']
        e['total_price'] += it['total_price']
    return {
        'items': res, 'candidates': res, 'type_totals': tt,
        'grand_total': round(sum(it['total_price'] for it in res), 2),
        'sheets': [{'name': n, 'count': c} for n, c in used],
    }


def main():
    ap = argparse.ArgumentParser(description='从 Excel/CSV 工程量清单提取防水材料')
    ap.add_argument('excel_path')
    ap.add_argument('--project-name', default='')
    ap.add_argument('--district')
    ap.add_argument('--date')
    ap.add_argument('--data-source', default='工程量清单（Excel）')
    ap.add_argument('--sheet', action='append', help='只处理指定 sheet（可重复）')
    ap.add_argument('-o', '--output')
    ap.add_argument('--screen', action='store_true', help='用 TypeSafe 复核候选条目')
    ap.add_argument('--screen-threshold', type=float, default=0.5)
    ap.add_argument('--criteria')
    ap.add_argument('--key-file')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-filter', action='store_true',
                    help='不做防水关键词过滤，把表里所有条目都收进来（默认只收防水条目）')
    a = ap.parse_args()

    print(f'解析 {os.path.basename(a.excel_path)} …', file=sys.stderr)
    r = build(a.excel_path, sheets=a.sheet, only_waterproof=not a.no_filter)
    r['project_name'] = a.project_name or os.path.splitext(os.path.basename(a.excel_path))[0]
    r['data_source'] = a.data_source
    if a.district: r['district'] = a.district
    if a.date: r['date'] = a.date

    print(f'\n共 {len(r["items"])} 条防水候选，按类型：', file=sys.stderr)
    for t, v in r['type_totals'].items():
        print(f'  {t}: {v["count"]} 项，{v["total_qty"]:,.2f} m²', file=sys.stderr)

    if a.dry_run:
        out = json.dumps(r, ensure_ascii=False, indent=2)
        print(out if not a.output else f'（--dry-run 未写文件）')
        return

    if a.screen:
        import screen_waterproof as sw
        key = sw.load_key(a.key_file)
        cand = r.get('candidates') or r['items']
        if not key:
            print('⚠️  没找到 TypeSafe API Key，跳过复核。', file=sys.stderr)
        elif cand:
            questions = sw.load_criteria(a.criteria)
            scored, usage = sw.screen(cand, key, questions)
            if scored and all(s.get('probability') is None for s in scored):
                print('⚠️  复核接口全部调用失败（可能是地区限制／网络问题），本次跳过复核，'
                      '结果退回关键词匹配。请人工过一遍候选清单。', file=sys.stderr)
            else:
                r = sw.apply_screen(r, scored, threshold=a.screen_threshold)
            sc = r.get('screen')
            if sc:
                print(f"[复核] 候选 {len(cand)} → 保留 {sc['kept']}｜剔除 {len(sc['dropped'])}"
                      f"｜补入 {len(sc['added'])}｜待确认 {len(sc['flagged'])}", file=sys.stderr)
                for d in sc['dropped']:
                    dp = d.get('probability')
                    print(f"  ✗ 剔除 {d['name'][:40]}  "
                          f"{'调用出错' if dp is None else f'p={dp:.2f}'}", file=sys.stderr)
                for g in sc['flagged']:
                    gp = g['probability']
                    print(f"  ? 待确认 {g['name'][:40]}  "
                          f"{'调用出错' if gp is None else f'p={gp:.2f}'}", file=sys.stderr)

    for it in r['items']:
        it.pop('_strong', None)

    out = json.dumps(r, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, 'w', encoding='utf-8') as f:
            f.write(out)
        print(f'\n已写入 {a.output}', file=sys.stderr)
    else:
        print(out)


if __name__ == '__main__':
    main()
