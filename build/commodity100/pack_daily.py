#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/daily/*.json 打包成页面用的紧凑格式 data/daily_data.json。

压缩策略：日期 -> Unix 天数(UTC)，价格 -> 分(×100 取整)。
体积约为原始 JSON 的 45%。
"""
import json, os, datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, 'data', 'daily')
DST = os.path.join(BASE, 'data', 'daily_data.json')

# (序列code, 显示名, 品种key, 分类, 市场, 单位, 颜色)
GROUPS = [
    ('贵金属', [
        ('gold',      '黄金 · 沪金',    'gold',     '元/克',    '沪金主连',      '#F5C542'),
        ('gold_i',    '黄金 · COMEX',   'gold',     '美元/盎司', 'COMEX 连续',   '#FFE08A'),
        ('silver',    '白银 · 沪银',    'silver',   '元/千克',  '沪银主连',      '#C8D2E0'),
        ('silver_i',  '白银 · COMEX',   'silver',   '美元/盎司', 'COMEX 连续',   '#E8EEF6'),
        ('platinum',  '铂金 · 伦敦',    'platinum', '美元/盎司', '伦敦现货',      '#9FE8D8'),
        ('palladium', '钯金 · 伦敦',    'palladium','美元/盎司', '伦敦现货',      '#7FD8C8'),
    ]),
    ('有色金属', [
        ('copper',    '铜 · 沪铜',      'copper',   '元/吨',    '沪铜主连',      '#E07B39'),
        ('copper_lme','铜 · LME',       'copper',   '美元/吨',  'LME 三月',      '#F5A05C'),
        ('aluminum',  '铝 · 沪铝',      'aluminum', '元/吨',    '沪铝主连',      '#5FA8D3'),
        ('aluminum_i','铝 · LME',       'aluminum', '美元/吨',  'LME 三月',      '#8CC5E3'),
        ('zinc',      '锌 · 沪锌',      'zinc',     '元/吨',    '沪锌主连',      '#A78BFA'),
        ('zinc_i',    '锌 · LME',       'zinc',     '美元/吨',  'LME 三月',      '#C4B0FC'),
        ('lead',      '铅 · 沪铅',      'lead',     '元/吨',    '沪铅主连',      '#8B95A8'),
        ('lead_i',    '铅 · LME',       'lead',     '美元/吨',  'LME 三月',      '#AEB6C6'),
        ('tin',       '锡 · 沪锡',      'tin',      '元/吨',    '沪锡主连',      '#D98CC8'),
        ('tin_i',     '锡 · LME',       'tin',      '美元/吨',  'LME 三月',      '#E8B0DB'),
        ('nickel',    '镍 · 沪镍',      'nickel',   '元/吨',    '沪镍主连',      '#28C98A'),
        ('nickel_i',  '镍 · LME',       'nickel',   '美元/吨',  'LME 三月',      '#6FE0B0'),
    ]),
    ('农产品', [
        ('wheat',     '小麦 · 郑麦',    'wheat',    '元/吨',    '郑强麦主连',    '#D9C36A'),
        ('maize',     '玉米 · 连玉米',  'maize',    '元/吨',    '连玉米主连',    '#E8D07A'),
        ('soybean',   '大豆 · 连豆一',  'soybean',  '元/吨',    '连豆一主连',    '#8FBC5A'),
        ('cotton',    '棉花 · 郑棉',    'cotton',   '元/吨',    '郑棉主连',      '#EDEFF5'),
        ('cotton_i',  '棉花 · ICE',     'cotton',   '美分/磅',  'ICE 连续',      '#F8FAFF'),
        ('sugar',     '白糖 · 郑糖',    'sugar',    '元/吨',    '郑糖主连',      '#F08AA8'),
        ('coffee_i',  '咖啡 · ICE',     'coffee',   '美分/磅',  'ICE 连续',      '#A0644A'),
    ]),
    ('能源化工', [
        ('crude',     '原油 · SC',      'crude',    '元/桶',    'SC 原油主连',   '#7C8CA8'),
        ('crude_i',   '原油 · WTI',     'crude',    '美元/桶',  'NYMEX 连续',    '#9DAECB'),
        ('gas_i',     '天然气 · NYMEX', 'gas',      '美元/MMBtu','NYMEX 连续',   '#4AA3DF'),
        ('rubber',    '天然橡胶 · 沪胶','rubber',   '元/吨',    '沪胶主连',      '#B8B0A0'),
        ('urea',      '尿素 · 郑尿素',  'urea',     '元/吨',    '郑尿素主连',    '#56C596'),
        ('dap',       '磷酸二铵 · 现货','dap',      '元/吨',    '生意社现货',    '#C084FC'),
    ]),
]


def dayno(dstr):
    y, m, d = map(int, dstr.split('-'))
    return (dt.date(y, m, d) - dt.date(1970, 1, 1)).days


out = {'built': dt.date.today().isoformat(), 'groups': []}
total = 0
for gname, items in GROUPS:
    g = {'name': gname, 'series': []}
    for code, label, breed, unit, market, color in items:
        p = os.path.join(SRC, code + '.json')
        if not os.path.exists(p):
            print(f'  ! 缺 {code}')
            continue
        raw = json.load(open(p, encoding='utf-8'))
        pts = raw['points']
        d = [[dayno(dt_), int(round(px * 100))] for dt_, px in pts]
        d.sort(key=lambda x: x[0])
        # 去重（同一天保留最后一个）
        ded, seen = [], set()
        for x in reversed(d):
            if x[0] not in seen:
                seen.add(x[0]); ded.append(x)
        d = list(reversed(ded))
        g['series'].append({
            'c': code, 'n': label, 'b': breed, 'u': unit, 'm': market,
            'col': color, 'src': raw.get('src', ''), 'sym': raw.get('symbol', ''),
            'd': d,
        })
        total += len(d)
    out['groups'].append(g)

json.dump(out, open(DST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
sz = os.path.getsize(DST)
print(f'打包完成: {DST}')
print(f'  序列 {sum(len(g["series"]) for g in out["groups"])} 个 / 数据点 {total} 个 / {sz/1024:.0f} KB')
for g in out['groups']:
    print(f'  [{g["name"]}] ' + ', '.join(f"{s['n']}({len(s['d'])})" for s in g['series']))
