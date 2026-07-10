#!/usr/bin/env python3
"""
Extract waterproof material items from 工程量清单 PDF.
Uses markitdown to convert PDF to Markdown, then parses the Markdown text.
"""
import re
import json
import argparse
import sys
import subprocess

# Try to import markitdown as a library; fall back to CLI subprocess
HAVE_MARKITDOWN_LIB = False
try:
    from markitdown import MarkItDown
    HAVE_MARKITDOWN_LIB = True
except ImportError:
    pass

KW = ['防水卷材','防水涂料','防水砂浆','防水','非沥青基','橡胶自粘','预铺','TPO','SBS','分子粘','聚乙烯胎','耐根穿刺','PVC防水','聚氨酯','水泥基渗透结晶','聚合物水泥防水','JS防水','丙烯酸防水','非固化','高分子自粘','自粘型','止水带','止水条']

def classify(n):
    for k in ['卷材','非沥青基','橡胶自粘','预铺','TPO','SBS','分子粘','聚乙烯胎','耐根穿刺','自粘型']:
        if k in n: return '防水卷材'
    for k in ['涂料','聚氨酯','水泥基渗透结晶','聚合物水泥防水涂','JS防水','丙烯酸','非固化','涂膜']:
        if k in n: return '防水涂料'
    for k in ['砂浆','防水砂浆']:
        if k in n: return '防水砂浆'
    return '其他防水'

LOC_KEYWORDS = ['屋面','墙面','地面','楼地面','顶棚','天棚','阳台','卫生间','厨房','挡土墙','外墙面','内墙面']

def extract_location(nm):
    loc = ''
    m = re.match(r'^([\u4e00-\u9fff]+)[-—]', nm)
    if m:
        loc = m.group(1)
        nm = nm[len(loc)+1:]
    else:
        for kw in LOC_KEYWORDS:
            if nm.startswith(kw):
                loc = kw
                nm = nm[len(kw):]
                break
    return loc, nm


def handle_dao(it):
    """If item name starts with 'N道', remove it and multiply quantity by N."""
    m = re.match(r'^(\d+)道', it['name'])
    if m:
        n = int(m.group(1))
        it['name'] = it['name'][m.end():].strip()
        it['quantity'] = round(it['quantity'] * n, 2)
        it['total_price'] = round(it['quantity'] * it['unit_price'], 2)
        it['_dao_note'] = f'(×{n})'
    return it


def clean_name(nm):
    nm = re.sub(r'\s+', ' ', nm).strip()
    # Strip leading price numbers (like "32.97 " or "32.97 44.9 ")
    nm = re.sub(r'^[\d,.]+(?:\s+[\d,.]+)?\s+', '', nm)
    # Strip leading long digit code (12+ digits). The code may have eaten 1+ digits
    # from the thickness pattern (e.g. "1140109020010011.5厚" where the code ate the "1").
    # We give back the eaten digit(s).
    def strip_code(m):
        digits = m.group(1)
        rest = m.group(2)
        # Case 1: rest starts with ".5厚" or ".5mm" (code ate 1 digit, e.g. "1" from "1.5厚")
        if re.match(r'\.\d+(?:厚|mm)', rest):
            return digits[-1] + rest
        # Case 2: rest starts with "mm" or "厚" (code ate the whole thickness digit)
        if rest.startswith('mm') or rest.startswith('厚'):
            return digits[-1] + rest
        # Case 3: other content after digits - strip the digits fully
        return rest
    nm = re.sub(r'^(\d{12,})(.*)', strip_code, nm)
    # Fix remaining artifacts: ".5厚" -> "0.5厚", ".5mm" -> "0.5mm"
    nm = re.sub(r'^\.(\d+(?:厚|mm))', r'0.\1', nm)
    # Strip leading * from names like "*300mm钢板止水带"
    nm = re.sub(r'^\*+', '', nm)
    nm = re.sub(r'\s+', ' ', nm).strip()
    return nm


def extract_item(item_no, code, name_text, rest_text):
    """Try to extract a waterproof item from parsed text parts.

    Works on both raw PDF text and Markdown-formatted text.
    """
    nm = clean_name(name_text)
    # Check keywords with spaces removed (PDF text may break Chinese chars)
    nm_no_space = re.sub(r'\s+', '', nm)
    if not any(kw.replace(' ', '') in nm_no_space for kw in KW):
        return None
    # Find qty/price in rest text — support both plain text and Markdown table cells
    pm = re.search(r'(?:m[2²])\s*\|\s*([\d,.]+)\s*\|\s*([\d,.]+)', rest_text) or \
         re.search(r'(?:m[2²])\s*([\d,.]+)\s*([\d,.]+)', rest_text)
    if not pm:
        return None
    try:
        q = float(pm.group(1).replace(',',''))
        p = float(pm.group(2).replace(',',''))
    except ValueError:
        return None
    if q == 0 or p == 0:
        return None
    loc, nm_clean = extract_location(nm)
    return {
        'item_no': int(item_no),
        'code': code or '',
        'name': nm_clean[:80],
        'location': loc,
        'unit': 'm²',
        'quantity': q,
        'unit_price': p,
        'total_price': round(q * p, 2),
        'type': classify(nm)
    }


def pdf_to_markdown(path):
    """Convert PDF to Markdown text using markitdown."""
    if HAVE_MARKITDOWN_LIB:
        try:
            md = MarkItDown()
            result = md.convert(path)
            return result.text_content
        except Exception as e:
            print(f"markitdown library error: {e}, falling back to CLI", file=sys.stderr)

    # Fallback: use markitdown CLI
    result = subprocess.run(
        ['markitdown', path],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"markitdown error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def extract(path):
    md_text = pdf_to_markdown(path)

    # Try to estimate page count from form feeds in the markdown output
    total_pages = md_text.count('\f') + 1

    items = []

    # Process the full document text (with newlines collapsed for regex search)
    t = md_text.replace('\n', ' ')

    # Split into page-like chunks if form feeds exist, otherwise process as one block
    pages = md_text.split('\f') if '\f' in md_text else [md_text]

    for pn, page_text in enumerate(pages, 1):
        page_text_flat = page_text.replace('\n', ' ')
        items_before_page = len(items)

        # --- Format 3: Markdown table rows ---
        for line in page_text.split('\n'):
            line_stripped = re.sub(r'\s+', '', line)
            if not any(kw.replace(' ', '') in line_stripped for kw in KW):
                continue
            # Match Markdown table row: | code | name | ... | unit | qty | price |
            table_m = re.match(r'^\|\s*(\d+)\s*\|(.+?)\|.*?\|.*?\|(m[2²]|kg|t|m³)\s*\|([\d,.]+)\s*\|([\d,.]+)', line)
            if table_m:
                item_no, name_cell = table_m.group(1), table_m.group(2)
                unit, qty_str, price_str = table_m.group(3), table_m.group(4), table_m.group(5)
                it = extract_item(item_no, '', name_cell, line)
                if it:
                    it['page'] = pn
                    items.append(it)
                    continue

        # Try format 1: item_no \s+ code (item_no and code separated by whitespace)
        for kw in KW:
            if kw not in t:
                continue
            for m in re.finditer(
                r'(\d+)\s+(\d{10,20})?\s*([^\[]*' + re.escape(kw) + r'[^\[]*?)\[项目特征\].*?(?:m2|kg|t|m³)\s*([\d,.]+)\s*([\d,.]+)',
                t
            ):
                item_no, code, name_text, qty_str, price_str = m.group(1), (m.group(2) or ''), m.group(3), m.group(4), m.group(5)
                nm = clean_name(name_text)
                if not any(k in nm for k in KW):
                    continue
                try:
                    q = float(qty_str.replace(',',''))
                    p = float(price_str.replace(',',''))
                except ValueError:
                    continue
                if q == 0 or p == 0:
                    continue
                loc, nm_clean = extract_location(nm)
                items.append({
                    'page': pn,
                    'item_no': int(item_no), 'code': code or '',
                    'name': nm_clean[:80], 'location': loc, 'unit': 'm²',
                    'quantity': q, 'unit_price': p, 'total_price': round(q * p, 2),
                    'type': classify(nm)
                })
        # Try format 2 only if format 1 found nothing (prevents duplicates)
        if items_before_page == len(items):
            for m in re.finditer(
                r'(\d+)(\d{12})([^\[]*?)\[项目特征\]',
                t
            ):
                item_no, code = m.group(1), m.group(2)
                name_text = m.group(3)
                # Check keywords with flexible whitespace
                nm_clean = re.sub(r'\s+', '', name_text)
                if not any(kw.replace(' ', '') in nm_clean for kw in KW):
                    continue
                rest = t[m.end():m.end() + 800]
                it = extract_item(item_no, code, name_text, rest)
                if it:
                    it['page'] = pn
                    items.append(it)

    # Dedup
    seen = set()
    res = []
    for it in items:
        it = handle_dao(it)
        k = (it['name'][:30], round(it['quantity'], 1), it.get('page', 0))
        if k not in seen:
            seen.add(k)
            res.append(it)
    # Filter out items with very low total price (likely PDF extraction artifacts)
    res = [it for it in res if it['total_price'] >= 10.0]
    return {'total_pages': total_pages, 'items': res, 'material_prices': []}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf_path')
    ap.add_argument('--project-name')
    ap.add_argument('--bid-price', type=float)
    ap.add_argument('--control-price', type=float)
    ap.add_argument('--bid-url')
    ap.add_argument('--clarify-url')
    ap.add_argument('-o', '--output')
    a = ap.parse_args()
    r = extract(a.pdf_path)
    r['project_name'] = a.project_name or ''
    r['bid_price'] = a.bid_price
    r['control_price'] = a.control_price
    r['bid_url'] = a.bid_url
    r['clarify_url'] = a.clarify_url
    if a.bid_price and a.control_price and a.control_price > 0:
        r['discount_ratio'] = round((1 - a.bid_price / a.control_price) * 100, 2)
    tt = {}
    for it in r['items']:
        t = it['type']
        tt.setdefault(t, {'count': 0, 'total_qty': 0, 'total_price': 0})
        tt[t]['count'] += 1
        tt[t]['total_qty'] += it['quantity']
        tt[t]['total_price'] += it['total_price']
    r['type_totals'] = tt
    r['grand_total'] = sum(it['total_price'] for it in r['items'])
    o = json.dumps(r, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, 'w') as f:
            f.write(o)
    else:
        print(o)
