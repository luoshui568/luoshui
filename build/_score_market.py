# -*- coding: utf-8 -*-
"""槽 29 评分第 8/9/10 项的行情底数（月线派生）。

数据来源优先级：
  ① _score_src/<code>_charts.json 的 chartPrice2（报告自带股价图，已核实）
  ② 本地 seed/report_<code>.json 的 charts.chartPrice2（新五家，通达信年线）

★ 2026-09-22 当日 tdx-connector 会话过期、westock 月 K 线持续限频，
  故本轮以**年度末收盘序列**为口径（note 里标注 caliber），不编造月线数据。
  月线源恢复后重跑本脚本即可升级为月线口径。

用法：python _score_market.py [--go]
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '_score_src')
OUT = os.path.join(HERE, '_score_market')

ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']


def clean(x):
    x = re.sub(r'<[^>]+>', ' ', str(x or ''))
    return re.sub(r'\s+', ' ', x).strip()


def num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r'[-+]?\d+(?:\.\d+)?', str(x).replace(',', ''))
    return float(m.group(0)) if m else None


def kpi_of(mods):
    for m in mods:
        if '企业评分' in clean(m.get('title')):
            h = m.get('html') or ''
            kv = re.findall(r'<div class="k">(.*?)</div>\s*<div class="v"[^>]*>(.*?)</div>',
                            h, re.S)
            return {clean(a): clean(b) for a, b in kv}
    return {}


def pick(d, *keys, exclude=()):
    for k, v in d.items():
        if any(x in k for x in keys) and not any(e in k for e in exclude):
            return v
    return None


def build(code):
    mods = json.loads(io.open(os.path.join(SRC, '%s.json' % code),
                              encoding='utf-8').read())['mods']
    charts = json.loads(io.open(os.path.join(SRC, '%s_charts.json' % code),
                                encoding='utf-8').read())
    cmap = {c['id']: c.get('opt') for c in charts}
    kpi = kpi_of(mods)
    price = num(pick(kpi, '价格'))
    pb = num(pick(kpi, 'PB'))

    o = cmap.get('%s_chartPrice2' % code)
    if not isinstance(o, dict):
        return None
    xa = o.get('xAxis')
    xd = (xa.get('data') if isinstance(xa, dict) else xa) or []
    ser = {clean(s.get('name')): (s.get('data') or []) for s in (o.get('series') or [])}
    if not ser:
        return None

    hi_s = pick(ser, '年内最高', '最高')
    lo_s = pick(ser, '年内最低', '最低')
    cl_s = pick(ser, '收盘价（年均）', '收盘价（元）', '收盘价', exclude=('最高', '最低'))
    vol_s = pick(ser, '成交额', '成交量')

    # 年度标签（去重保序）
    yrs = []
    for x in xd:
        m = re.search(r'(\d{4})', str(x))
        yrs.append(int(m.group(1)) if m else None)
    if cl_s is None:
        return None
    n = len(cl_s)

    # 完整年度 = 当年之前的年份（最新一年多半是「年初至今」）
    report_year = max([y for y in yrs if y] or [2026])
    idx_full = [i for i, y in enumerate(yrs)
                if y and y < report_year and i < n and num(cl_s[i]) is not None]
    if len(idx_full) < 2:
        idx_full = [i for i in range(n) if num(cl_s[i]) is not None]

    def rng(idxs, with_price=False):
        if hi_s is not None and len(hi_s) == n:
            his = [num(hi_s[i]) for i in idxs if num(hi_s[i]) is not None]
        else:
            his = [num(cl_s[i]) for i in idxs]
        if lo_s is not None and len(lo_s) == n:
            los = [num(lo_s[i]) for i in idxs if num(lo_s[i]) is not None]
        else:
            los = [num(cl_s[i]) for i in idxs]
        his = [x for x in his if x] or []
        los = [x for x in los if x] or []
        if not his or not los:
            return None
        # ★ 现价必须并进区间 —— 否则现价低于/高于近年所有年末收盘时
        #   pos 会跑到区间外成负数或 >1（002237 曾算成 −104%）。
        if with_price and price:
            his, los = his + [price], los + [price]
        return max(his), min(los)

    short = idx_full[-4:]           # 近 4 个完整年度
    long_ = idx_full[-6:]           # 近 6 个完整年度
    if price is None:
        price = num(cl_s[-1])
    r1, r2 = rng(short, True), rng(long_, True)
    if not r1 or not r2:
        return None
    hi1, lo1 = r1
    hi2, lo2 = r2

    # 趋势方向：近 4 个完整年度的收盘序列
    # ★ 只用「逐期单调」判定会漏掉缓跌（002408 每期跌 3-5% 被判成 flat）
    #   ⇒ 叠加「首尾累计变化」作为兜底。
    cs = [num(cl_s[i]) for i in short if num(cl_s[i]) is not None]
    trend = 'flat'
    if len(cs) >= 3 and cs[0]:
        chg = cs[-1] / cs[0] - 1
        mono_up = all(b >= a for a, b in zip(cs, cs[1:]))
        mono_dn = all(b <= a for a, b in zip(cs, cs[1:]))
        if mono_dn or chg <= -0.25:
            trend = 'down'
        elif mono_up or chg >= 0.35:
            trend = 'up'
    closes36 = cs

    def pos(hi, lo):
        return None if (price is None or hi == lo) else (price - lo) / (hi - lo)

    # 量能：最新一期 ÷ 更早各期均值
    vol_ratio = vol_recent = vol_base = None
    if vol_s is not None and len(vol_s) == n:
        vs = [num(v) for v in vol_s]
        base = [v for v in vs[:-1] if v]
        if base and vs[-1]:
            vol_recent = round(vs[-1] / 1e8, 2) if vs[-1] > 1e6 else vs[-1]
            vol_base = round(sum(base) / len(base) / 1e8, 2) if base[0] > 1e6 \
                else round(sum(base) / len(base), 2)
            vol_ratio = vs[-1] / (sum(base) / len(base))

    return {
        'price': price, 'pb': pb,
        'amp36': (hi1 - lo1) / lo1 if lo1 else None,
        'pos36': pos(hi1, lo1), 'hi36': hi1, 'lo36': lo1,
        'trend36': trend, 'closes36': closes36,
        'pos48': pos(hi2, lo2), 'hi48': hi2, 'lo48': lo2,
        'vol_ratio': vol_ratio, 'vol_recent': vol_recent, 'vol_base': vol_base,
        'caliber': '口径：基于年度末收盘序列（近 4 / 近 6 个完整年度）',
        'years_full': [yrs[i] for i in idx_full],
    }


def main():
    go = '--go' in sys.argv
    if go:
        os.makedirs(OUT, exist_ok=True)
    ok = miss = 0
    for code in ALL:
        m = build(code)
        if not m:
            print('%-7s ✗ 无可用的股价图数据' % code)
            miss += 1
            continue
        ok += 1
        print('%-7s price=%s PB=%s | 近4年 %s~%s pos=%.0f%% amp=%.0f%% | '
              '近6年 %s~%s pos=%.0f%% | 量比=%s'
              % (code, m['price'], m['pb'], m['lo36'], m['hi36'],
                 (m['pos36'] or 0) * 100, (m['amp36'] or 0) * 100,
                 m['lo48'], m['hi48'], (m['pos48'] or 0) * 100,
                 ('%.2f' % m['vol_ratio']) if m['vol_ratio'] else '—'))
        if go:
            io.open(os.path.join(OUT, '%s.json' % code), 'w', encoding='utf-8') \
                .write(json.dumps(m, ensure_ascii=False, indent=1))
    print('\n可用 %d / %d' % (ok, len(ALL)))
    if go:
        print('已写 → _score_market/')


if __name__ == '__main__':
    main()
