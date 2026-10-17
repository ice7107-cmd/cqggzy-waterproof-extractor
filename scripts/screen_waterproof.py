#!/usr/bin/env python3
"""
用 TypeSafe(Jev) 复核工程量清单里的候选防水条目。

作用：关键词匹配负责「宽进」（不漏），TypeSafe 负责「严出」（不错收）。
      被它判否的条目从报告里剔除，被判是的条目补进报告，打分居中的单独标出来
      交给人工确认。

用法：
  python3 screen_waterproof.py candidates.json -o screened.json
  python3 screen_waterproof.py candidates.json --dry-run          # 只打印，不联网
  python3 screen_waterproof.py candidates.json --threshold 0.6

API Key 读取顺序：--key-file > 环境变量 TYPESAFE_API_KEY
                  > <skill>/references/typesafe_key.txt > ~/.typesafe_key
标准文件默认读 <skill>/references/waterproof_criteria.json，可用 --criteria 替换。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-latest'
DEFAULT_CRITERIA = os.path.join(SKILL, 'references', 'waterproof_criteria.json')

# 打分落在这个区间视为「拿不准」，需要人工看一眼
FLAG_LO, FLAG_HI = 0.2, 0.8


def load_key(key_file=None):
    if key_file and os.path.exists(key_file):
        v = open(key_file, encoding='utf-8').read().strip()
        if v:
            return v
    v = os.environ.get('TYPESAFE_API_KEY')
    if v:
        return v.strip()
    for p in (os.path.join(SKILL, 'references', 'typesafe_key.txt'),
              os.path.expanduser('~/.typesafe_key')):
        if os.path.exists(p):
            v = open(p, encoding='utf-8').read().strip()
            if v:
                return v
    return None


def load_criteria(path=None):
    p = path or DEFAULT_CRITERIA
    with open(p, encoding='utf-8') as f:
        return json.load(f)['questions']


def state_of(item):
    s = {'清单项名称': item.get('name', ''),
         '项目编码': item.get('code', ''),
         '计量单位': item.get('unit', ''),
         '工程量': item.get('quantity'),
         '综合单价': item.get('unit_price')}
    if item.get('page'):
        s['清单页码'] = item['page']
    if item.get('feature'):
        s['项目特征摘录'] = item['feature'][:300]
    return s


def ask(key, item, questions, timeout=60, retries=3):
    body = json.dumps({'state': state_of(item), 'model': MODEL,
                       'questions': questions}, ensure_ascii=False).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'ignore')[:200]
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {'error': f'HTTP {e.code}: {detail}'}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {'error': str(e)}


def screen(items, key, questions, workers=8, threshold=0.5, verbose=True):
    """给每个候选条目打一个「是防水材料」的概率。返回 (结果列表, token用量)。"""
    results, usage = [], {'input_tokens': 0, 'output_tokens': 0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(ask, key, it, questions): it for it in items}
        for n, f in enumerate(futs, 1):
            it = futs[f]
            resp = f.result()
            rec = dict(it)
            if 'error' in resp:
                rec['error'] = resp['error']
            else:
                a = resp.get('answers', {})
                rec['probability'] = a.get('is_waterproof', {}).get('noul')
                rec['category_pred'] = a.get('category', {}).get('choice')
                u = resp.get('usage', {}) or {}
                for k in usage:
                    usage[k] += u.get(k, 0) or 0
            results.append(rec)
            if verbose and (n % 20 == 0 or n == len(futs)):
                print(f'  已复核 {n}/{len(futs)}', flush=True)
    return results, usage


def _info(r):
    return {'name': r.get('name'), 'code': r.get('code'), 'page': r.get('page'),
            'probability': r.get('probability'), 'category': r.get('category_pred'),
            'unit_price': r.get('unit_price'), 'quantity': r.get('quantity'),
            'total_price': r.get('total_price')}


def apply_screen(data, scored, threshold=0.5, flag_lo=FLAG_LO, flag_hi=FLAG_HI):
    """把打分结果套回数据：判否的剔除，判是的保留，拿不准的标记出来。

    不修改传入的 scored 里的 dict（避免概率被后续 pop 掉），全部产出新对象。
    """
    kept, dropped, flagged, failed = [], [], [], []

    for r in scored:
        p = r.get('probability')
        if p is None:
            # 调用出错：退回关键词法的结论——关键词抓到的就保留，只是宽进多抓的就不要，
            # 避免把「防水套管」这类噪声当成漏项补进报告。
            failed.append(r)
            if r.get('_strong'):
                it = {k: v for k, v in r.items()
                      if k not in ('probability', 'category_pred', 'error')}
                kept.append(it)
            else:
                dropped.append(r)
            flagged.append(_info(r))
            continue

        if p >= threshold:
            it = {k: v for k, v in r.items() if k not in ('probability', 'category_pred')}
            if r.get('category_pred') and r['category_pred'] != '非防水':
                it['type'] = r['category_pred']
            kept.append(it)
            if p <= flag_hi:
                flagged.append(_info(r))
        else:
            dropped.append(r)
            if p >= flag_lo:
                flagged.append(_info(r))

    def key(x):
        return (x.get('name'), x.get('code'), x.get('page'))

    old = data.get('items', [])
    old_keys = {key(i) for i in old}
    new_keys = {key(i) for i in kept}

    # 条目变了，汇总必须跟着重算，否则报告里的总价是旧的
    tt = {}
    for it in kept:
        t = it.get('type') or '其他防水'
        e = tt.setdefault(t, {'count': 0, 'total_qty': 0, 'total_price': 0})
        e['count'] += 1
        e['total_qty'] += it.get('quantity', 0) or 0
        e['total_price'] += it.get('total_price', 0) or 0

    out = dict(data)
    out['candidates'] = scored          # 保留候选全量，便于换阈值重算时无需再联网
    out['items'] = kept
    out['type_totals'] = tt
    out['grand_total'] = round(sum(it.get('total_price', 0) or 0 for it in kept), 2)
    out['screen'] = {
        'threshold': threshold,
        'total_candidates': len(scored),
        'kept': len(kept),
        'dropped': [_info(d) for d in dropped],
        'added': [_info(k) for k in kept if key(k) not in old_keys],
        'flagged': flagged,
        'errors': len(failed),
        'keyword_only': [_info(k) for k in old if key(k) not in new_keys],
    }
    return out


def main():
    ap = argparse.ArgumentParser(description='用 TypeSafe 复核候选防水条目')
    ap.add_argument('input', help='extract_waterproof.py 输出的 JSON（含 candidates 或 items）')
    ap.add_argument('-o', '--output', help='输出 JSON，缺省覆盖输入文件')
    ap.add_argument('--threshold', type=float, default=0.5, help='判定阈值，默认 0.5')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--criteria', help='判定标准文件，默认 references/waterproof_criteria.json')
    ap.add_argument('--key-file')
    ap.add_argument('--dry-run', action='store_true', help='只打印将发送的内容，不联网')
    ap.add_argument('--reapply', action='store_true',
                    help='不联网，用文件里已存的打分结果 + 新阈值重新计算（换阈值时用）')
    args = ap.parse_args()

    with open(args.input, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):
        data = {'items': data}

    questions = load_criteria(args.criteria)
    items = data.get('candidates') or data.get('items') or []
    if args.limit:
        items = items[:args.limit]

    print(f'候选条目 {len(items)} 条｜阈值 {args.threshold}｜标准文件 '
          f'{os.path.basename(args.criteria or DEFAULT_CRITERIA)}')

    if args.reapply:
        scored = data.get('candidates') or []
        if not scored or scored[0].get('probability') is None:
            print('❌ 这个文件里没有已存的打分结果，无法离线重算。')
            sys.exit(2)
        out = apply_screen(data, scored, threshold=args.threshold)
        dest = args.output or args.input
        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f'离线重算完成（阈值 {args.threshold}）：保留 {out["screen"]["kept"]} 条，'
              f'剔除 {len(out["screen"]["dropped"])} 条，已写入 {dest}')
        return

    if args.dry_run:
        if items:
            print(json.dumps({'state': state_of(items[0]), 'model': MODEL,
                              'questions': questions}, ensure_ascii=False, indent=1)[:1500])
        print('（--dry-run 不联网）')
        return

    key = load_key(args.key_file)
    if not key:
        print('⚠️  没找到 TypeSafe API Key，跳过复核，沿用关键词结果。')
        print('   设置方法：把 Key 存到 ' + os.path.join(SKILL, 'references', 'typesafe_key.txt'))
        print('   或设置环境变量 TYPESAFE_API_KEY。当前结果未做任何改动。')
        sys.exit(0)

    if not items:
        print('没有候选条目，无需复核。')
        return

    t0 = time.time()
    scored, usage = screen(items, key, questions, workers=args.workers)
    if scored and all(s.get('probability') is None for s in scored):
        first = next((s.get('error') for s in scored if s.get('error')), None)
        print('⚠️  复核接口全部调用失败（可能是地区限制／网络问题），本次跳过复核，'
              '结果退回关键词匹配，输入文件未改动，请人工过一遍候选清单。',
              file=sys.stderr)
        print(f'   首个错误：{first}', file=sys.stderr)
        sys.exit(3)
    out = apply_screen(data, scored, threshold=args.threshold)
    n = len(items)
    n_drop, n_add = len(out['screen']['dropped']), len(out['screen']['added'])
    print(f"\n完成：{n} 条候选，用时 {time.time()-t0:.1f}s"
          f"｜保留 {out['screen']['kept']} 条｜剔除 {n_drop} 条｜补入 {n_add} 条"
          f"｜拿不准 {len(out['screen']['flagged'])} 条｜出错 {out['screen']['errors']} 条")
    if usage['input_tokens']:
        print(f"Token 用量：输入 {usage['input_tokens']:,}｜输出 {usage['output_tokens']:,}")
    if out['screen']['errors']:
        first = next((s.get('error') for s in scored if s.get('error')), None)
        print(f"⚠️  {out['screen']['errors']} 条调用出错，结果已退回关键词口径。"
              f"首个错误：{first}", file=sys.stderr)
    for d in out['screen']['dropped']:
        dp = d.get('probability')
        print(f"  ✗ 剔除 {d['name'][:44]:<46} "
              f"{'调用出错' if dp is None else f'p={dp:.2f}'}")
    for a in out['screen']['added']:
        print(f"  + 补入 {a['name'][:44]:<46} {a.get('page','')}")
    for g in out['screen']['flagged']:
        p = g['probability']
        tag = '调用出错，已保守保留' if p is None else f"p={p:.2f}"
        print(f"  ? 待确认 {g['name'][:42]:<44} {tag}")

    dest = args.output or args.input
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n复核后条目数 {len(out['items'])}，已写入 {dest}")


if __name__ == '__main__':
    main()
