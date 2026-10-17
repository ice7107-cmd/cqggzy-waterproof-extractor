#!/usr/bin/env python3
"""
从 工程量清单 PDF 提取防水材料条目。

首选方案：PyMuPDF (fitz) 词坐标法重建表格。
  - 按 y 坐标聚类成行，按表头检测列边界，按列切分单元格
  - 解决 markitdown 文本流把名称拆散、综合单价列丢失的问题
  - 综合单价缺失时由 合价/工程量 反推

兜底方案：markitdown 转 Markdown 后按旧正则解析（仅当 PyMuPDF 不可用时）。
"""
import re
import os
import json
import argparse
import sys

# ---------- 公共部分 ----------

KW = ['防水卷材', '防水涂料', '防水砂浆', '防水', '非沥青基', '橡胶自粘', '预铺', 'TPO', 'SBS',
      '分子粘', '聚乙烯胎', '耐根穿刺', 'PVC防水', '聚氨酯', '水泥基渗透结晶', '渗透结晶', '聚合物水泥防水',
      'JS防水', '丙烯酸防水', '非固化', '高分子自粘', '自粘型', '止水带', '止水条', '涂膜',
      '聚脲', '防潮层', '防水剂', '改性沥青']

# 强关键词：排除泛泛的“防水”二字，降低误判（如模板支架、措施费）
STRONG_KW = [k for k in KW if k != '防水']

# 宽进关键词：在强关键词基础上再加“防水”“防渗”“止水”等泛词，
# 宁可多抓一批候选，交给 screen_waterproof.py 用 TypeSafe 精确剔除。
# （“20mm厚1:2.5砂浆防水”这类倒装写法只有放宽才抓得到）
BROAD_KW = STRONG_KW + ['防水', '防渗', '止水', '防潮']

# 用户确认口径（2026-10-17）：清单项的名称**或项目特征**里出现下面这些材料写法，
# 一律算防水，不再等 TypeSafe 复核：
#   渗透结晶（含水泥基渗透结晶型）、聚合物防水涂料、聚合物水泥防水涂料／砂浆
# 只认「材料名」本身，不认泛词，避免把「抗裂防水砂浆」「1:3 水泥砂浆找平层」误收。
# 具体清单放在 references/material_rules.json，PDF 与 Excel 两条路线共用同一份。
# ---------- 本地边界材料清单（PDF / Excel 两条路线共用一份） ----------
_RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'references', 'material_rules.json')


def load_material_rules(path=None):
    """读 references/material_rules.json；读不到就退化回纯关键词，不报错中断。"""
    try:
        with open(path or _RULES_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'always_waterproof': [], 'never_waterproof': []}


def _alt(pats):
    pats = sorted({p for p in pats if p}, key=len, reverse=True)
    return '|'.join(re.escape(p) for p in pats) if pats else None


MATERIAL_RULES = load_material_rules()
_ALWAYS = MATERIAL_RULES.get('always_waterproof') or []
_NEVER = MATERIAL_RULES.get('never_waterproof') or []
_ALWAYS_ALT = _alt([p for r in _ALWAYS for p in (r.get('patterns') or [])])
_NEVER_ALT = _alt([p for r in _NEVER for p in (r.get('patterns') or [])])
BOUNDARY_RE = re.compile(_ALWAYS_ALT) if _ALWAYS_ALT else None
EXCLUDE_RE = re.compile(_NEVER_ALT) if _NEVER_ALT else None
# Excel 分包清单用：厚度规格 + 材料名（不需要写「厚」字）
USER_MAT_RE = re.compile(
    r'(?:(?P<spec>\d+(?:\.\d+)?\s*(?:mm)?\s*厚?)\s*)?'
    r'(?P<noun>' + (_ALWAYS_ALT or '') + r')') if _ALWAYS_ALT else None


def rule_for(text):
    """返回命中的边界材料规则（dict），未命中返回 None。

    边界材料优先：只要命中 always_waterproof 就算数，不看排除清单。
    「1:2.5 聚合物水泥防水砂浆」这类既要排「1:2.5 普通砂浆」又要留的场景，
    靠这条优先级解决。
    """
    if not text or BOUNDARY_RE is None:
        return None
    m = BOUNDARY_RE.search(re.sub(r'\s+', '', text))
    if not m:
        return None
    for r in _ALWAYS:
        if any(p and p in m.group(0) for p in (r.get('patterns') or [])):
            return r
    return None


def vetoed(text):
    """名称层否决：命中排除清单、且不是边界材料时才否决。

    用于拦「聚氨酯金属洁净板」「1:3 水泥砂浆找平层」这类靠单个词混进来的条目。
    """
    if EXCLUDE_RE is None or not text:
        return False
    t = re.sub(r'\s+', '', text)
    return bool(EXCLUDE_RE.search(t)) and rule_for(t) is None


def boundary_type(text):
    """边界材料对应的材料大类；未命中返回 None。"""
    r = rule_for(text)
    return r.get('type') if r else None

# 调用 TypeSafe 复核时，候选条目数超过这个值会提示（避免无意中花很多 token）
SCREEN_WARN_N = 1500

UNITS = {'m2', 'm²', 'm3', 'm³', 'kg', 't', '个', 'm', '樘', '套', '项', '座', '组', '台', '根', '块', '间', 'km'}


def classify(n):
    for k in ['砂浆', '防水砂浆', '防水剂']:
        if k in n:
            return '防水砂浆'
    # 名称里明写「涂料／涂膜」、且没有「卷材」的，按涂料走。
    # 否则「改性沥青防水涂料」会被下面的「改性沥青」误判成卷材；
    # 而「涂料+卷材」的复合项保持原判（算卷材），不动已出报告的口径。
    if '卷材' not in n:
        for k in ['涂料', '涂膜']:
            if k in n:
                return '防水涂料'
    for k in ['卷材', '非沥青基', '橡胶自粘', '预铺', 'TPO', 'SBS', '分子粘', '聚乙烯胎', '耐根穿刺', '自粘型', '改性沥青']:
        if k in n:
            return '防水卷材'
    for k in ['涂料', '涂膜', '聚氨酯', '水泥基', '聚合物水泥防水', 'JS防水', '丙烯酸', '非固化', '聚脲', '防潮层']:
        if k in n:
            return '防水涂料'
    return '其他防水'


LOC_KEYWORDS = ['楼(地)面', '屋面', '墙面', '地面', '楼地面', '顶棚', '天棚', '阳台', '卫生间', '厨房',
                '挡土墙', '外墙面', '内墙面']


def extract_location(nm):
    loc = ''
    m = re.match(r'^([\u4e00-\u9fff（）()]+?)[-—]', nm)
    # 只有当破折号后面确实是个材料名时才把前面当部位。
    # 否则「墙身防潮层-立面」会被切成 部位=墙身防潮层、名称=立面，材料名就丢了。
    if m and classify(m.string[m.end():]) != '其他防水':
        loc = m.group(1)
        nm = nm[len(loc) + 1:]
    else:
        for kw in LOC_KEYWORDS:
            if nm.startswith(kw):
                loc = kw
                nm = nm[len(kw):]
                break
    return loc, nm


def handle_dao(it):
    """名称以 'N道' 开头时，去掉前缀并把工程量乘 N。"""
    m = re.match(r'^(\d+)道', it['name'])
    if m:
        n = int(m.group(1))
        it['name'] = it['name'][m.end():].strip()
        it['quantity'] = round(it['quantity'] * n, 2)
        it['total_price'] = round(it['quantity'] * it['unit_price'], 2)
        it['_dao_note'] = f'(×{n})'
    return it


def _norm_unit(u):
    u = (u or 'm²').replace('2', '²').replace('3', '³')
    return u


# 单数字价格推断用：合理综合单价区间（元）
UNIT_PRICE_MIN = 0.5
UNIT_PRICE_MAX = 5000.0


def _unit_plausible(u):
    return u is not None and UNIT_PRICE_MIN <= u <= UNIT_PRICE_MAX


def infer_single_price(col, value, qty, page_hint):
    """页面只有一个价格数字时，判断它是综合单价还是合价。

    col: 数字所在的列（综合单价/合价/暂估价）
    page_hint: 该页其他条目的推断结果（'unit'/'total'/None），用于两可情况投票
    """
    if col == '综合单价':
        return 'unit'
    if col == '合价':
        return 'total'
    # 暂估价列：用合理性判断（潼南类 PDF 数字错位到暂估价列，实际是合价）
    if not qty or qty <= 0:
        return None
    u_as_unit = value            # 假设它是综合单价
    u_as_total = value / qty     # 假设它是合价，反推单价
    as_unit = _unit_plausible(u_as_unit)
    as_total = _unit_plausible(u_as_total)
    if as_unit and not as_total:
        return 'unit'
    if as_total and not as_unit:
        return 'total'
    if as_unit and as_total:
        return page_hint or 'total'  # 两可：跟随页面多数；缺省按合价
    return None


def feature_spec(feat):
    """从「项目特征」里抽出含边界材料的短句，拼成 'A + B'，用于补全材料名。

    「2.防水1品种及厚度:1.5mm水泥基渗透结晶型防水涂料 3.防水2品种及厚度:1.0mm聚合物防水涂料」
      → '1.5mm水泥基渗透结晶型防水涂料 + 1.0mm聚合物防水涂料'
    只取 references/material_rules.json 里 always_waterproof 命中的短句，
    [工作内容] 段和 never_waterproof 命中的抹灰层/找平层会被丢掉。
    """
    if not feat:
        return ''
    t = re.sub(r'\s+', '', feat)
    t = re.split(r'[\[【](?:工作内容|工程内容)[\]】]', t)[0]
    t = t.replace('[项目特征]', '').replace('【项目特征】', '')
    out = []
    for part in re.split(r'(?=\d{1,2}[.．、](?!\d))|[;；]', t):
        part = part.strip(' .,、;')
        if not part:
            continue
        # 只收命中边界材料的短句；抗裂砂浆／找平层这类本来就不命中
        if BOUNDARY_RE is None or not BOUNDARY_RE.search(part):
            continue
        # 「防水1品种及厚度:1.5mm…」只留冒号后的规格
        spec = re.split(r'[:：]', part)[-1].strip(' .,、;')
        if spec and spec not in out:
            out.append(spec)
    return ' + '.join(out)


def make_item(seq, code, name, unit, qty, unit_price, total_price, page, kw=None, strong=None, feat=None):
    name = re.sub(r'\s+', '', name or '').strip()
    if not name:
        return None
    # 名称命中排除清单（洁净板、1:3 普通砂浆找平层、划线漆…）直接不要，
    # 否则「聚氨酯金属洁净板」会靠「聚氨酯」两个字混进来；
    # 但边界材料优先，所以「1:2.5 聚合物水泥防水砂浆」照样留
    if vetoed(name):
        return None
    strong_kw = STRONG_KW if strong is None else strong
    spec = feature_spec(feat)
    name_rule = rule_for(name)   # 名称本身命中边界材料清单
    # 名称命中关键词、或名称/特征命中边界材料清单，才进入候选；
    # 很多清单的名称只有一句「消防水池楼板整治」，材料写在特征栏里。
    if (not any(k in name for k in (kw if kw is not None else STRONG_KW))
            and not spec and not name_rule):
        return None
    is_strong = any(k in name for k in strong_kw) or bool(spec) or bool(name_rule)
    if not qty or qty <= 0:
        return None
    # 反推综合单价
    if unit_price is None or unit_price <= 0:
        if total_price and total_price > 0:
            unit_price = total_price / qty
        else:
            return None
    if total_price is None or total_price <= 0:
        total_price = round(qty * unit_price, 2)
    if not _unit_plausible(unit_price):
        return None
    loc, nm = extract_location(name)
    # 名称里没写材料规格时，把特征栏的规格补进名字，报告上才看得出是什么材料
    if spec and not any(k in nm for k in strong_kw):
        nm = f'{nm}（{spec[:60]}）'
    type_ = classify(name)
    if type_ == '其他防水':
        # 名称看不出类别时，用边界材料清单 / 特征里的规格定类
        type_ = boundary_type(spec or name) or (classify(spec) if spec else type_)
    return {
        'item_no': seq,
        'code': code or '',
        'name': nm[:80],
        'location': loc,
        'unit': _norm_unit(unit),
        'quantity': round(qty, 2),
        'unit_price': round(unit_price, 2),
        'total_price': round(total_price, 2),
        'type': type_,
        'page': page,
        'feature': (feat or '')[:300],
        '_strong': is_strong,
    }


# ---------- 方案一：PyMuPDF 坐标法 ----------

def _page_rows(page):
    """把一页的 words 按 y 聚类成行，每行按 x 排序。"""
    words = [w for w in page.get_text('words') if w[4].strip()]
    words.sort(key=lambda w: (w[1], w[0]))
    rows, cur, cur_y = [], [], None
    for w in words:
        if cur_y is None or abs(w[1] - cur_y) <= 3.5:
            cur.append(w)
            cur_y = w[1] if cur_y is None else cur_y
        else:
            rows.append(cur)
            cur = [w]
            cur_y = w[1]
    if cur:
        rows.append(cur)
    for r in rows:
        r.sort(key=lambda w: w[0])
    return rows


def _detect_columns(rows):
    """在表头行里定位各列中心 x。找不到返回 None。"""
    for i, row in enumerate(rows[:40]):
        joined = ''.join(w[4] for w in row)
        if '项目编码' not in joined or '项目名称' not in joined or '项目特征' not in joined:
            continue
        pos = {}
        for w in row:
            if w[4] in ('序号', '项目编码', '项目名称', '项目特征', '工程量'):
                pos[w[4]] = (w[0] + w[2]) / 2
        # “计量/单位/综合单价/合价/暂估价”表头常在相邻行（表头分两行显示）
        for j in range(max(0, i - 4), min(len(rows), i + 5)):
            for w in rows[j]:
                if w[4] in ('计量', '单位', '综合单价', '合价', '暂估价') and w[4] not in pos:
                    pos[w[4]] = (w[0] + w[2]) / 2
        if '项目编码' in pos and '项目名称' in pos and '项目特征' in pos and '工程量' in pos:
            order = ('序号', '项目编码', '项目名称', '项目特征', '计量', '单位', '工程量', '综合单价', '合价', '暂估价')
            centers = [(n, pos[n]) for n in order if n in pos]
            return centers
    return None


def _nearest_col(centers, xc):
    return min(centers, key=lambda c: abs(c[1] - xc))[0]


def _num(s):
    m = re.fullmatch(r'[\d,]+\.?\d*', s or '')
    return float(m.group().replace(',', '')) if m else None


def extract_with_fitz(path):
    import fitz
    doc = fitz.open(path)
    items = []        # 命中强关键词的，即关键词法的结果
    candidates = []   # 宽进候选（含弱命中），交给 TypeSafe 复核

    for pno in range(doc.page_count):
        page = doc[pno]
        rows = _page_rows(page)
        centers = _detect_columns(rows)
        if not centers:
            continue
        code_cx = dict(centers)['项目编码']
        name_cx = dict(centers)['项目名称']

        # 找出锚行（序号 + 编码 在同一行）
        anchors = []
        for idx, row in enumerate(rows):
            seq = None
            code = None
            for w in row:
                xc = (w[0] + w[2]) / 2
                if seq is None and xc < code_cx and re.fullmatch(r'\d{1,4}', w[4]):
                    seq = int(w[4])
                elif code is None and xc < name_cx and re.fullmatch(r'\d{10,20}', w[4]):
                    code = w[4]
            if seq is not None and code is not None:
                anchors.append((idx, seq, code, row[0][1]))
        if not anchors:
            continue

        raw_items = []  # 本页原始条目，价格稍后统一推断
        # 特征栏的几何边界：列中心靠近边界的长词（如「涂料」「[工作」）会被
        # _nearest_col 分到左右邻列，只按列名取词会丢字，所以按 x 区间取。
        feat_cx = dict(centers).get('项目特征')
        if feat_cx is None:
            continue
        _right = [v for k, v in centers if v > feat_cx + 1]
        feat_left = feat_cx - (feat_cx - name_cx) / 2 - 12
        feat_right = (min(_right) if _right else feat_cx + 90) - 15
        # 本页所有 [项目特征] 标记的 y，用来给每条清单划定特征单元格的起止
        feat_marks = sorted({w[1] for r in rows for w in r
                             if w[4] in ('[项目特征]', '【项目特征】')})
        for ai, (idx, seq, code, y0) in enumerate(anchors):
            y_end = anchors[ai + 1][3] if ai + 1 < len(anchors) else 10 ** 9
            y_start = y0 - 30  # 名称列最多可高出锚行 2~3 行
            # 特征单元格：起于本条的 [项目特征] 标记，止于下一条的标记。
            # 不能用「锚行~下一锚行」当窗口——下一条的名称/特征常先于它的锚行出现，
            # 会把下一条的防水材料错算到本条目头上。
            _starts = [m for m in feat_marks if m <= y0 + 2]
            y_feat = _starts[-1] if _starts else None
            _ends = [m for m in feat_marks if y_feat is not None and m > y_feat + 1]
            y_feat_end = _ends[0] if _ends else y_end
            name_parts = []
            feat_parts = []
            unit = None
            qty = None
            prices = []
            for row in rows:
                if row[0][1] < y_start or row[0][1] >= y_end:
                    continue
                for w in row:
                    xc = (w[0] + w[2]) / 2
                    c = _nearest_col(centers, xc)
                    if c == '项目名称':
                        name_parts.append((w[1], xc, w[4]))
                    elif c in ('计量', '单位') and unit is None and w[4] in UNITS:
                        unit = w[4]
                    elif c == '工程量' and qty is None:
                        qty = _num(w[4])
                    elif c in ('综合单价', '合价', '暂估价'):
                        v = _num(w[4])
                        if v is not None:
                            prices.append((xc, c, v))
            # 特征栏按几何 x 区间独立取词（见上方 feat_left/feat_right），
            # 这样列边界上的词不会被邻列吃掉。
            # y 留 0.5 的容差：标记行本身要收进来，下一条标记行（常与上一条
            # 末行同一 y）不能收进来，否则会把下一条的材料算到本条头上。
            for row in rows:
                for w in row:
                    if y_feat is None or w[1] < y_feat - 0.5 or w[1] > y_feat_end - 0.5:
                        continue
                    if feat_left - 2 <= w[0] <= feat_right:
                        feat_parts.append((w[1], w[0], w[4]))
            # 特征列左缘碎片（如“价”“单价”）可能被误分进名称列，按特征列左界过滤
            if feat_parts:
                name_parts = [t for t in name_parts if t[1] <= feat_left]
            name_parts.sort(key=lambda t: (t[0], t[1]))
            # 名称列跨多行显示，按 y 间隙聚类，取最接近锚行的那一段
            clusters, cur, prev = [], [], None
            for t in name_parts:
                if prev is None or t[0] - prev <= 10:
                    cur.append(t)
                else:
                    clusters.append(cur)
                    cur = [t]
                prev = t[0]
            if cur:
                clusters.append(cur)
            if not clusters:
                continue
            best = min(clusters, key=lambda c: min(abs(t[0] - y0) for t in c))
            name = ''.join(p[2] for p in best)
            feat_parts.sort(key=lambda t: (t[0], t[1]))
            feat = ''.join(p[2] for p in feat_parts)
            # 本条目只认最后一个 [项目特征] 之后的内容——向上追溯窗口可能带上
            # 上一条的工作内容尾巴
            for marker in ('[项目特征]', '【项目特征】'):
                pos = feat.rfind(marker)
                if pos >= 0:
                    feat = feat[pos + len(marker):]
                    break
            # 名称里有泛防水词，或特征栏点到了具体防水材料，都进入候选
            if (not any(k in re.sub(r'\s+', '', name) for k in BROAD_KW)
                    and not feature_spec(feat) and not rule_for(name)):
                continue
            prices.sort()
            raw_items.append({'seq': seq, 'code': code, 'name': name, 'unit': unit,
                              'qty': qty, 'prices': prices, 'feat': feat})

        # 页面级投票：两可情况下决定“单数字=单价还是合价”
        single_cols = [p[1][1] for r in raw_items if len(r['prices']) == 1 for p in [r['prices'][0]]]
        page_hint = None
        for r in raw_items:
            if len(r['prices']) >= 2:
                page_hint = 'both'
                break
        if page_hint is None:
            # 用“暂估价列”单数字的合理性投票
            votes = {'unit': 0, 'total': 0}
            for r in raw_items:
                if len(r['prices']) == 1 and r['prices'][0][1] == '暂估价':
                    kind = infer_single_price('暂估价', r['prices'][0][2], r['qty'], None)
                    if kind:
                        votes[kind] += 1
            page_hint = 'unit' if votes['unit'] > votes['total'] else ('total' if votes['total'] > votes['unit'] else None)

        for r in raw_items:
            qty = r['qty']
            prices = r['prices']
            if not qty or qty <= 0:
                continue
            if len(prices) >= 2:
                up, tp = prices[0][2], prices[1][2]
            elif len(prices) == 1:
                xc, col, v = prices[0]
                kind = infer_single_price(col, v, qty, page_hint)
                if kind == 'unit':
                    up, tp = v, None
                elif kind == 'total':
                    up, tp = None, v
                else:
                    continue
            else:
                continue
            it = make_item(r['seq'], r['code'], r['name'], r['unit'], qty, up, tp, pno + 1,
                           kw=BROAD_KW, strong=STRONG_KW, feat=r.get('feat'))
            if it:
                candidates.append(it)
                if it['_strong']:
                    items.append(it)

    doc.close()
    return items, candidates


# ---------- 方案二：markitdown 文本兜底 ----------

def pdf_to_markdown(path):
    try:
        from markitdown import MarkItDown
        return MarkItDown().convert(path).text_content
    except Exception:
        import subprocess
        r = subprocess.run(['markitdown', path], capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            print(f'markitdown error: {r.stderr}', file=sys.stderr)
            sys.exit(1)
        return r.stdout


def extract_with_markitdown(path):
    md = pdf_to_markdown(path)
    total_pages = md.count('\f') + 1
    t = md.replace('\n', ' ')
    items = []

    for kw in STRONG_KW:
        if kw not in t:
            continue
        for m in re.finditer(
            r'(\d+)\s+(\d{10,20})?\s*([^\[]*' + re.escape(kw) + r'[^\[]*?)\[项目特征\].*?(?:m2|kg|t|m³)\s*([\d,.]+)\s*([\d,.]+)',
            t,
        ):
            item_no, code, name_text, qty_str, price_str = m.group(1), (m.group(2) or ''), m.group(3), m.group(4), m.group(5)
            nm = re.sub(r'\s+', ' ', name_text).strip()
            q = _num(qty_str)
            p = _num(price_str)
            if not q or not p or q <= 0 or p <= 0:
                continue
            it = make_item(int(item_no), code, nm, 'm2', q, None, p, 1,
                           kw=BROAD_KW, strong=STRONG_KW)
            if it:
                items.append(it)

    # 去重
    seen, res = set(), []
    for it in items:
        it = handle_dao(it)
        k = (it['name'][:30], round(it['quantity'], 1), it.get('page', 0))
        if k not in seen:
            seen.add(k)
            res.append(it)
    return {'total_pages': total_pages, 'items': res}


# ---------- 入口 ----------

def extract(path):
    items, candidates = [], []
    total_pages = None
    try:
        import fitz  # noqa: F401
        items, candidates = extract_with_fitz(path)
    except Exception as e:
        print(f'[提示] PyMuPDF 解析失败，改用 markitdown 兜底：{e}', file=sys.stderr)

    if not items:
        fallback = extract_with_markitdown(path)
        items = fallback['items']
        candidates = fallback['items']
        total_pages = fallback.get('total_pages')

    # 统一去重 + 过滤异常小项
    seen, res = set(), []
    for it in items:
        it = handle_dao(it)
        k = (it['name'][:30], round(it['quantity'], 1), it.get('page', 0))
        if k not in seen and it['total_price'] >= 10.0:
            seen.add(k)
            res.append(it)

    seen2, cand = set(), []
    for it in candidates:
        it = handle_dao(it)
        k = (it['name'][:30], round(it['quantity'], 1), it.get('page', 0))
        if k not in seen2 and it['total_price'] >= 10.0:
            seen2.add(k)
            cand.append(it)
    return {'total_pages': total_pages, 'items': res, 'candidates': cand, 'material_prices': []}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf_path')
    ap.add_argument('--project-name')
    ap.add_argument('--bid-price', type=float)
    ap.add_argument('--control-price', type=float)
    ap.add_argument('--bid-url')
    ap.add_argument('--clarify-url')
    ap.add_argument('--district', help='区县，如 沙坪坝区')
    ap.add_argument('--date', help='公示日期 YYYY-MM-DD，会写入数据仓库')
    ap.add_argument('-o', '--output')
    ap.add_argument('--screen', action='store_true',
                    help='用 TypeSafe 复核候选条目：剔除误收、补入漏项、标出拿不准的')
    ap.add_argument('--screen-threshold', type=float, default=0.5)
    ap.add_argument('--criteria', help='判定标准文件，默认 references/waterproof_criteria.json')
    ap.add_argument('--key-file', help='TypeSafe API Key 文件')
    a = ap.parse_args()
    r = extract(a.pdf_path)
    r['project_name'] = a.project_name or ''
    r['bid_price'] = a.bid_price
    r['control_price'] = a.control_price
    r['bid_url'] = a.bid_url
    r['clarify_url'] = a.clarify_url
    if a.district:
        r['district'] = a.district
    if a.date:
        r['date'] = a.date
    if a.bid_price and a.control_price and a.control_price > 0:
        r['discount_ratio'] = round((1 - a.bid_price / a.control_price) * 100, 2)
    tt = {}
    for it in r['items']:
        t = it['type']
        tt.setdefault(t, {'count': 0, 'total_qty': 0, 'total_price': 0})
        tt[t]['count'] += 1
        tt[t]['total_qty'] += it['quantity']
        tt[t]['total_price'] += it['total_price']
    if a.screen:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import screen_waterproof as sw
        cand = r.get('candidates') or r['items']
        key = sw.load_key(a.key_file)
        if not key:
            print('⚠️  没找到 TypeSafe API Key，跳过复核，结果沿用关键词匹配。', file=sys.stderr)
        elif cand:
            if len(cand) > SCREEN_WARN_N:
                print(f'[提示] 候选 {len(cand)} 条，较多，复核会消耗较多 token。', file=sys.stderr)
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
                      f"｜补入 {len(sc['added'])}｜待确认 {len(sc['flagged'])}｜出错 {sc['errors']}",
                      file=sys.stderr)
                for d in sc['dropped']:
                    dp = d.get('probability')
                    print(f"  ✗ 剔除 {d['name'][:40]}  "
                          f"{'调用出错' if dp is None else f'p={dp:.2f}'}", file=sys.stderr)
                for ad in sc['added']:
                    print(f"  + 补入 {ad['name'][:40]}", file=sys.stderr)
                for g in sc['flagged']:
                    gp = g['probability']
                    note = '（调用出错，已保守保留）' if gp is None else f"p={gp:.2f}"
                    print(f"  ? 待确认 {g['name'][:40]}  {note}", file=sys.stderr)
        else:
            print('[复核] 没有候选条目，跳过。', file=sys.stderr)

    # 清理内部字段，不写入下游 JSON
    for it in r['items']:
        it.pop('_strong', None)

    tt = {}
    for it in r['items']:
        t = it['type']
        tt.setdefault(t, {'count': 0, 'total_qty': 0, 'total_price': 0})
        tt[t]['count'] += 1
        tt[t]['total_qty'] += it['quantity']
        tt[t]['total_price'] += it['total_price']
    r['type_totals'] = tt
    r['grand_total'] = sum(it['total_price'] for it in r['items'])
    out = json.dumps(r, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, 'w') as f:
            f.write(out)
    else:
        print(out)
