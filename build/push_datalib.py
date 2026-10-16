#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「数据文库」的模块清单写进云数据库 public.wb_data_mods。

  python3 push_datalib.py          # 幂等 upsert（按 id 覆盖）+ 回读核对
  python3 push_datalib.py --dry    # 只打印，不写库

★ 这就是「以后再加一个模块页面」的入口：往 MODS 里加一条（或直接在数据文库页面上点
  「＋ 新增模块」），不用改工作台代码、不用重新构建、不用重新部署。
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
KEY = CFG['key']

MODS = [
    {
        'id': 'commodity-daily',
        'title': '大宗商品日线对比图',
        'sub': '31 条日线序列（国内期货主力连续 + 国际期货连续），可自由缩放对比；'
               '归一化基期随视窗左端自动跟随，十字光标实时读数 + 右上角命中列表。',
        'icon': '📈', 'tag': '商品 · 日线', 'url': 'commodity-daily.html',
        'sort': 10, 'accent': '#c8102e', 'on_line': True,
        'meta': {'points': '105,755', 'span': '1996-10-14 → 2026-10-30',
                 'src': '新浪财经期货日线 · iFinD EDB'},
    },
    {
        'id': 'commodity-century',
        'title': '大宗商品百年周期全景',
        'sub': '1900—2025 年主要农产品 / 化工品 / 有色金属 / 贵金属的长周期走势，'
               '逐轮涨跌的先后顺序与轮动节奏复盘。',
        'icon': '🌍', 'tag': '商品 · 长周期', 'url': 'commodity-century.html',
        'sort': 20, 'accent': '#c9a227', 'on_line': True,
        'meta': {'span': '1900 — 2025', 'src': '公开长历史数据 · iFinD · 发现研报'},
    },
    {
        'id': 'a-share-history',
        'title': '中国股市牛熊全史',
        'sub': '1990—2026 年 A 股全历史走势与历轮牛熊复盘，含区间涨跌统计与阶段对照。',
        'icon': '🐂', 'tag': '股市 · 长周期', 'url': 'market-history.html',
        'sort': 30, 'accent': '#8c0a20', 'on_line': True,
        'meta': {'span': '1990 — 2026', 'src': '交易所公开行情'},
    },
]


def api(path, method='GET', body=None, prefer=None):
    h = {'Authorization': 'Bearer ' + KEY}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        h['Content-Type'] = 'application/json'
    if prefer:
        h['Prefer'] = prefer
    req = urllib.request.Request(REST + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            t = r.read().decode('utf-8')
            return r.status, (json.loads(t) if t.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')[:400]


def main():
    dry = '--dry' in sys.argv
    for m in MODS:
        print('  %-20s %s %-26s → %s' % (m['id'], m['icon'], m['title'], m['url']))
    if dry:
        print('\n--dry：未写库。')
        return 0
    st, resp = api('wb_data_mods?on_conflict=id', 'POST', MODS,
                   'resolution=merge-duplicates,return=minimal')
    if st not in (200, 201, 204):
        print('✗ 写入失败 HTTP %s %s' % (st, resp))
        return 1
    print('✓ 已写入 %d 个模块' % len(MODS))

    st, back = api('wb_data_mods?select=id,title,tag,url,sort,on_line&order=sort.asc')
    if st != 200:
        print('✗ 回读失败 HTTP %s %s' % (st, back))
        return 1
    print('\n回读 %d 条：' % len(back))
    for b in back:
        print('  %-20s sort=%-3s %s → %s' % (b['id'], b['sort'], b['title'], b['url']))
    ids = {b['id'] for b in back}
    miss = [m['id'] for m in MODS if m['id'] not in ids]
    if miss:
        print('✗ 缺失：' + ','.join(miss))
        return 1
    print('✓ 核对通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
