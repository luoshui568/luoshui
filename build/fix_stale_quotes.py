# -*- coding: utf-8 -*-
"""定点修补已有研报 seed 里残留的旧行情数据。

背景：build/refresh_report_seed.py 只覆盖「徽标 / KPI / 模块 20 统计块 / 模块 21」四处，
评分页（M22 的 kv 块）、结论页（M23）与分红页（M19）里的行情数字会漏掉。
本脚本用**显式补丁表**补齐这些位置——每条补丁必须精确命中，漏命中会报错。

补丁表格式：[(code, old_substring, new_substring), ...]，命中次数必须等于 expect。

用法： python fix_stale_quotes.py            # 只检查、不写
       python fix_stale_quotes.py --apply    # 写回 seed（之后需重新 push_report.py）
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')

# --------------------------------------------------------------- 补丁表
KV = '<div class="k">%s</div><div class="v">%s</div>'

PATCH = {
    '002237': [
        # M19 分红：按最新价重算股息率
        ('2025年每股股利0.13元，股息率约0.87%（按现价14.92元）',
         '2025年每股股利0.13元，股息率约0.92%（按现价14.12元）'),
        # M22 评分页 kv 块
        (KV % ('总市值（亿元）', '213.35'), KV % ('总市值（亿元）', '201.91')),
        (KV % ('PE（TTM，倍）', '15.86'), KV % ('PE（TTM，倍）', '20.32')),
        (KV % ('PB（MRQ，倍）', '1.55'), KV % ('PB（MRQ，倍）', '1.47')),
        (KV % ('当前价格（元）', '14.92'), KV % ('当前价格（元）', '14.12')),
        # M23 结论页
        ('PE(TTM)约15.9倍、PB约1.55倍，处于行业中低位；但低估值对应低利润率',
         'PE(TTM)约20.32倍、PB约1.47倍，处于行业中低位；但低估值对应低利润率'),
        ('当前PE约15.9倍处于低位', '当前PE约20.32倍处于低位'),
        # 壳 verdict（顺带修正与 M22 不一致的评分）
        ('当前PE(TTM)约15.9倍、PB约1.55倍，处于行业中低位；评分63.5/100',
         '当前PE(TTM)约20.32倍、PB约1.47倍，处于行业中低位；评分61.8/100'),
    ],
    '600459': [
        # M19 分红
        ('股息率（按21.13元）', '股息率（按18.94元）'),
        ('约1.18%', '约1.32%'),
        # M22 评分页 kv 块
        (KV % ('总市值（亿元）', '173.96'), KV % ('总市值（亿元）', '155.91')),
        (KV % ('PE（TTM，倍）', '24.88'), KV % ('PE（TTM，倍）', '23.43')),
        (KV % ('PB（MRQ，倍）', '1.93'), KV % ('PB（MRQ，倍）', '1.73')),
        (KV % ('当前价格（元）', '21.13'), KV % ('当前价格（元）', '18.94')),
        # M23 结论页
        ('PE(TTM)约24.9倍、PB约1.93倍，处于历史中位',
         'PE(TTM)约23.43倍、PB约1.73倍，处于历史中位'),
        ('当前PE约24.9倍对应龙头溢价', '当前PE约23.43倍对应龙头溢价'),
        # 壳 verdict
        ('当前PE(TTM)约24.9倍、PB约1.93倍；评分68.5/100',
         '当前PE(TTM)约23.43倍、PB约1.73倍；评分66.1/100'),
    ],
}


def _walk(obj):
    """深度遍历，产出所有字符串字段的 (容器, 键) 便于原地改写。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                yield obj, k
            else:
                for x in _walk(v):
                    yield x
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                yield obj, i
            else:
                for x in _walk(v):
                    yield x


def run(code, apply=False):
    p = os.path.join(SEED, 'report_%s.json' % code)
    j = json.load(io.open(p, encoding='utf-8'))
    hits, miss = 0, []
    counts = {}
    for a, b in PATCH[code]:
        counts[a] = 0
    for cont, key in _walk(j):
        s = cont[key]
        for a, b in PATCH[code]:
            if a in s:
                counts[a] += s.count(a)
                s = s.replace(a, b)
        cont[key] = s
    hits = sum(counts.values())
    miss = [a for a, n in counts.items() if n == 0]
    print('=== %s ===' % code)
    print('  命中替换 %d 处；未命中 %d 条' % (hits, len(miss)))
    for m in miss:
        print('    !! 未命中：%s' % m)
    if miss:
        raise SystemExit(1)
    if apply:
        io.open(p, 'w', encoding='utf-8').write(
            json.dumps(j, ensure_ascii=False, separators=(',', ':')))
        print('  已写回 seed（请再跑 push_report.py）')
    else:
        print('  （未加 --apply，仅检查）')


if __name__ == '__main__':
    for c in PATCH:
        run(c, '--apply' in sys.argv)
