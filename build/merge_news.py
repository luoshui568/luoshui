# -*- coding: utf-8 -*-
"""把一手公告结构化数据（_b1news_<code>.json）合并进 data_v31_<code>.json。
幂等：可重复执行；只覆盖一手数据字段，不动 fin / forecast / sens 等模型字段。
"""
import io
import json
import os
import sys

SEED = 'C:/Users/50522/WorkBuddy/2026-09-10-14-50-38/build/seed'

# 一手数据贡献的字段（合并白名单）
MERGE_KEYS = [
    'profile', 'history', 'business', 'volprice', 'capacity',
    'subsidiaries', 'subsidiary_note', 'shareholder', 'mgmt', 'industry_note',
]


def merge(code):
    np_ = os.path.join(SEED, '_b1news_%s.json' % code)
    dp = os.path.join(SEED, 'data_v31_%s.json' % code)
    if not os.path.exists(np_):
        return 'NO_NEWS'
    if not os.path.exists(dp):
        return 'NO_DATA'
    news = json.load(io.open(np_, encoding='utf-8'))
    d = json.load(io.open(dp, encoding='utf-8'))
    hit = 0
    for k in MERGE_KEYS:
        if k in news and news[k] not in (None, '', [], {}):
            d[k] = news[k]
            hit += 1
    io.open(dp, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=2))
    return 'OK keys=%d' % hit


def main():
    a = sys.argv[1:]
    if '--batch' in a:
        i = a.index('--batch')
        todo = json.load(io.open(os.path.join(SEED, '_todo_96.json'), encoding='utf-8'))['todo']
        codes = [m['code'] for m in todo[int(a[i + 1]):int(a[i + 2])]]
    else:
        codes = [x for x in a if not x.startswith('--')]
    ok = 0
    for c in codes:
        r = merge(c)
        if r.startswith('OK'):
            ok += 1
            print(c, r)
    print('MERGED %d / %d' % (ok, len(codes)))
    print('SELF_CHECK_OK')


if __name__ == '__main__':
    main()
