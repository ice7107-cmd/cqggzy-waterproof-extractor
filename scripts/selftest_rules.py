#!/usr/bin/env python3
"""判定口径自测：改 material_rules.json / vetoed 之后先跑这个，别只信 PDF 回归。

用法：python3 selftest_rules.py            # 全过返回 0
      python3 selftest_rules.py -v         # 打印每条结果

覆盖的坑（都真实踩过）：
  1. 「防水卷材防潮层」必须否决——always 里补了「防水卷材」写法后，不能让 always 优先
     把 2026-10-17 确认的口径翻掉。
  2. 「防潮层 + 防水涂料/渗透结晶」必须放行。
  3. 普通配比砂浆（1:2.5 / 1:3）否决，但同一条里出现「聚合物水泥防水砂浆」要放行。
  4. 抗裂砂浆、洁净板、玻纤网格布否决。
  5. 材料只写在特征里的卷材（PV100 高分子自粘胶膜）要能判成防水卷材。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_waterproof as ew  # noqa: E402

# (文本, 期望 vetoed, 期望 rule_for 是否非空, 期望 type 或 None)
CASES = [
    ('防水卷材防潮层（4厚SBS改性沥青防水卷材）', True, True, None),
    ('防潮层（1.5mm聚合物水泥防水涂料）', False, True, '防水涂料'),
    ('防潮层（水泥基渗透结晶型）', False, True, '防水涂料'),
    ('1:2.5聚合物水泥防水砂浆', False, True, '防水砂浆'),
    ('1:3水泥砂浆找平层', True, False, None),
    ('抗裂防水砂浆（5mm厚聚合物抗裂砂浆打底）', True, False, None),
    ('聚氨酯金属洁净板', True, False, None),
    ('玻纤网格布加固', True, False, None),
    ('1.2mm厚PV100高分子自粘胶膜防水卷材', False, True, '防水卷材'),
    ('4厚改性沥青聚乙烯胎防水卷材一层满粘', False, True, '防水卷材'),
    ('外墙面涂膜防水（聚合物水泥防水涂料）', False, True, '防水涂料'),
    # 止水类与防水配件：不在收集范围（2026-10-21 补规则，潼南项目曾误收钢板止水带）
    ('钢板止水带（3*300mm）', True, False, None),
    ('遇水膨胀止水条', True, False, None),
    ('止水钢板', True, False, None),
    ('防水密封膏', True, False, None),
    ('防水套管', True, False, None),
    # 反向守卫：真卷材不能被这条规则误伤
    ('4厚SBS改性沥青防水卷材一道', False, True, '防水卷材'),
]

# make_item 层面的收录门槛：(名称, 单位, 特征, 期望是否保留)
# 2026-10-21 用户口径：附属构件项若按长度（m/km）计量，即使特征里有防水材料也排除。
PV100 = '4.防水:1.2厚PV100高分子自粘胶膜防水卷材'
MAKE_CASES = [
    ('车库出入口截水沟（坡底）', 'm', PV100, False),
    ('车库出入口截水沟（坡底）', 'm²', PV100, True),      # 判据是单位，不是名字
    ('电梯挡墙外侧防水', 'm²', PV100, True),              # 名称本身没材料词，但按面积计
    ('墙面变形缝', 'm', PV100, False),
]

# 材料名称口径（2026-10-21）：材料名只取防水材料本身，构造名进部位
# (清单项名, 单位, 特征, 期望材料名, 期望部位)
NAME_CASES = [
    ('室外砼雨棚板、风井板顶、烟道出屋面板（屋面三）', 'm²',
     '1.防水膜品种:聚合物水泥防水涂料JS（Ⅱ）型2.涂膜厚度、遍数:1.5mm厚，1遍',
     '1.5mm厚聚合物水泥防水涂料JS（Ⅱ）型', '室外砼雨棚板、风井板顶、烟道出屋面板（屋面三）'),
    ('1.5mm厚JS（Ⅱ）聚合物水泥防水涂料（立面）', 'm²',
     '1.防水膜品种:聚合物水泥防水涂料JS（Ⅱ）型2.涂膜厚度、遍数:1.5mm厚，2遍',
     '1.5mm厚聚合物水泥防水涂料JS（Ⅱ）型', '立面'),
    ('电梯挡墙外侧防水', 'm²',
     '1.部位:电梯挡墙外侧2.防水层:1.2mm厚PV100高分子自粘胶膜防水卷材',
     '1.2mm厚PV100高分子自粘胶膜防水卷材', '电梯挡墙外侧防水'),
]

# 复合清单项拆分（2026-10-21）：涂料+卷材写在同一项里，按材料类型拆行，
# 工程量各计一份；「二道」是遍数、不进材料名。
# (特征, 期望 [(类型, 材料名), ...])
SPLIT_CASES = [
    ('1.防水层做法:1.5mm厚JS防水涂料，1.5厚分子粘三胎基纤维增强型(TJ)防水卷材，二道'
     '2.防水层二:聚合物水泥防水涂料JS（Ⅱ）型',
     # JS 防水涂料 = 聚合物水泥防水涂料，同一种材料合成一条并保留厚度与型号
     [('防水涂料', '1.5mm厚聚合物水泥防水涂料JS（Ⅱ）型'),
      ('防水卷材', '1.5厚分子粘三胎基纤维增强型(TJ)防水卷材')]),
    ('1.防水膜品种:聚合物水泥防水涂料JS（Ⅱ）型2.涂膜厚度:1.5mm厚',
     [('防水涂料', '聚合物水泥防水涂料JS（Ⅱ）型')]),
]


def main():
    verbose = '-v' in sys.argv
    bad = 0
    for text, exp_veto, exp_rule, exp_type in CASES:
        got_veto = ew.vetoed(text)
        rule = ew.rule_for(text)
        got_rule = rule is not None
        got_type = (rule or {}).get('type')
        ok = got_veto == exp_veto and got_rule == exp_rule
        if exp_type is not None:
            ok = ok and got_type == exp_type
        if not ok:
            bad += 1
            print(f'✗ {text}')
            print(f'    vetoed={got_veto} (期望 {exp_veto}) | rule={got_type} (期望 {exp_type})')
        elif verbose:
            print(f'✓ {text} → vetoed={got_veto} rule={got_type}')

    for name, unit, feat, keep in MAKE_CASES:
        got = ew.make_item(1, '010507003003', name, unit, 10.0, 100.0, 1000.0, 1, feat=feat)
        is_kept = got is not None
        if is_kept != keep:
            bad += 1
            print(f'✗ {name} / {unit} → {"保留" if is_kept else "排除"}'
                  f'（期望 {"保留" if keep else "排除"}）')
        elif verbose:
            print(f'✓ {name} / {unit} → {"保留" if is_kept else "排除"}')

    for name, unit, feat, exp_name, exp_loc in NAME_CASES:
        got = ew.make_item(1, '010903002001', name, unit, 10.0, 100.0, 1000.0, 1, feat=feat)
        if got is None:
            bad += 1
            print(f'✗ {name[:24]} → 被排除（期望保留）')
            continue
        if got['name'] != exp_name or got['location'] != exp_loc:
            bad += 1
            print(f'✗ {name[:24]}')
            print(f'    材料={got["name"]!r}（期望 {exp_name!r}）| 部位={got["location"]!r}（期望 {exp_loc!r}）')
        elif verbose:
            print(f'✓ 材料={got["name"]} | 部位={got["location"]}')

    for feat, exp in SPLIT_CASES:
        got = ew.split_spec_by_type(ew.feature_spec(feat))
        if got != exp:
            bad += 1
            print(f'✗ 拆分 {feat[:24]}…\n    得到 {got}\n    期望 {exp}')
        elif verbose:
            print(f'✓ 拆分 → {got}')

    total = len(CASES) + len(MAKE_CASES) + len(NAME_CASES) + len(SPLIT_CASES)
    if bad:
        print(f'\n失败 {bad}/{total} 条')
        return 1
    print(f'✅ {total} 条口径用例全部通过（规则 {len(CASES)} + 收录门槛 {len(MAKE_CASES)}'
          f' + 材料命名 {len(NAME_CASES)} + 复合拆分 {len(SPLIT_CASES)}）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
