# -*- coding: utf-8 -*-
"""五家新建研报的数据落盘共享工具。

用法（每个 _mk_<code>.py 的末尾）：
    from _mk_lib import dump
    dump(D)
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')

# ---------------- 基础换算 ----------------
Y = ['2021', '2022', '2023', '2024', '2025']


def yoy(cur, prev):
    if not prev:
        return None
    return (cur / prev - 1) * 100


def series_yoy(vals):
    out = [None]
    for i in range(1, len(vals)):
        out.append(yoy(vals[i], vals[i - 1]))
    return out


def rnd(vals, nd=2):
    return [None if v is None else round(v, nd) for v in vals]


def pe_series(closes, np_, shares, nd=2):
    """静态 PE = 年末收盘价 × 年末总股本 ÷ 当年归母净利。

    `shares` 可为标量（全年同一股本）或与 closes 等长的列表（股本变动年份）。
    ⚠️ 与 iFinD 的 TTM PE 口径不同（TTM 用滚动四季净利），差异已在正文注明。
    """
    if not isinstance(shares, (list, tuple)):
        shares = [shares] * len(closes)
    out = []
    for c, n, s in zip(closes, np_, shares):
        out.append(None if (not n or n <= 0) else round(c * s / n, nd))
    return out


def pb_series(closes, np_, dps, shares, bps_now, nd=2):
    """PB 与每股净资产：由**最新每股净资产**按「权益滚存」向前回推。

    回推式：BPS[t-1] = BPS[t] − (np[t] − dps[t-1] × 股本[t-1]) ÷ 股本[t-1]
    （当年留存 = 当年归母净利 − 上年利润在本年派发的现金股利）

    ⚠️ 这是**近似口径**：未考虑其他综合收益、少数股东权益变动、股本转增与追溯调整，
       已在 valuation.source / note 中写明。校验：国泰 2025 年末 PB 得 2.51，
       iFinD 同日为 2.529，偏差 0.7%。
    """
    if not isinstance(shares, (list, tuple)):
        shares = [shares] * len(closes)
    n = len(closes)
    bps = [None] * n
    cur = float(bps_now)
    for i in range(n - 1, -1, -1):
        bps[i] = cur
        if i > 0:
            cur = cur - (np_[i] - (dps[i - 1] or 0) * shares[i - 1]) / shares[i - 1]
    pb = [None if (b is None or not b) else round(c / b, nd)
          for c, b in zip(closes, bps)]
    return pb, [round(b, 3) for b in bps]


def dump(D):
    code = D['code']
    p = os.path.join(SEED, 'data_v31_%s.json' % code)
    io.open(p, 'w', encoding='utf-8').write(
        json.dumps(D, ensure_ascii=False, indent=1))
    # 自检：形状体检（把最容易踩的坑前置报错）
    errs = []
    fin = D.get('fin') or {}
    n = len(fin.get('years') or [])
    for k in ('rev', 'np', 'gm', 'nm', 'ocf', 'roe', 'roic', 'lev', 'dps', 'eps'):
        v = fin.get(k)
        if v is not None and len(v) != n:
            errs.append('fin.%s 长度 %d != years %d' % (k, len(v), n))
    for s in ((D.get('business') or {}).get('segments') or []):
        if len(s) != 5:
            errs.append('business.segments 行不是 5 列：%r' % (s[:1],))
    if (D.get('peers') or {}).get('rows'):
        for r in D['peers']['rows']:
            if len(r) != 6:
                errs.append('peers.rows 行不是 6 列：%r' % (r[0],))
    if (D.get('bizmix') or {}).get('rows'):
        for r in D['bizmix']['rows']:
            if len(r) != 5:
                errs.append('bizmix.rows 行不是 5 列：%r' % (r[0],))
    if (D.get('volprice') or {}).get('rows'):
        for r in D['volprice']['rows']:
            if len(r) != 5:
                errs.append('volprice.rows 行不是 5 列：%r' % (r[0],))
    print('%s %s  写出 %d 字节  顶层键 %d 个' %
          ('OK ' if not errs else 'X  ', code, os.path.getsize(p), len(D)))
    for e in errs:
        print('   ! ' + e)
    return not errs
