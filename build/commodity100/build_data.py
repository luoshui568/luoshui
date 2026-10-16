#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百年商品价格对比 · 数据构建
把 World Bank 年度价 / 长期实际价格指数 / 黄金超长序列 / iFinD 校验序列
整合为页面用的精简 JSON。
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, 'data')

cons = json.load(open(os.path.join(D, 'consolidated.json')))
ifind = json.load(open(os.path.join(D, 'ifind_check.json')))
wb = cons['worldbank_nominal']
lr = cons['longrun_real_1900']
gold = cons['gold_annual']

# ------- 商品字典：code -> (中文名, 分类, wb列名, 长期指数列名, 颜色) -------
SPEC = [
    # 贵金属
    ('gold',      '黄金',   '贵金属', 'Gold',             'Metal.Gold',      '#F5C542'),
    ('silver',    '白银',   '贵金属', 'Silver',           'Metal.Silver',    '#C8D2E0'),
    ('platinum',  '铂金',   '贵金属', 'Platinum',         'Metal.Platinum',  '#9FE8D8'),
    # 有色金属
    ('copper',    '铜',     '有色金属', 'Copper',         'Metal.Copper',    '#E07B39'),
    ('aluminum',  '铝',     '有色金属', 'Aluminum',       'Metal.Aluminum',  '#7EC8E3'),
    ('zinc',      '锌',     '有色金属', 'Zinc',           'Metal.Zinc',      '#6C8CE8'),
    ('lead',      '铅',     '有色金属', 'Lead',           'Metal.Lead',      '#9AA5B1'),
    ('tin',       '锡',     '有色金属', 'Tin',            'Metal.Tin',       '#A78BFA'),
    ('nickel',    '镍',     '有色金属', 'Nickel',         'Metal.Nickel',    '#4ADE80'),
    # 农产品
    ('wheat',     '小麦',   '农产品', 'Wheat, US HRW',    'Grain.Wheat',     '#E8B84B'),
    ('maize',     '玉米',   '农产品', 'Maize',            'Grain.Corn',      '#F2D06B'),
    ('soybean',   '大豆',   '农产品', 'Soybeans',         None,              '#8FBC5A'),
    ('cotton',    '棉花',   '农产品', 'Cotton, A Index',  'Plant extract.Cotton', '#E3E7EC'),
    ('sugar',     '白糖',   '农产品', 'Sugar, world',     'Plant extract.Sugar',  '#F08AA8'),
    ('coffee',    '咖啡',   '农产品', 'Coffee, Arabica',  'Plant extract.Coffee', '#B5794B'),
    # 能源化工
    ('crude',     '原油',   '能源化工', 'Crude oil, average', 'Fuel.Petroleum', '#7C8CA8'),
    ('gas',       '天然气', '能源化工', 'Natural gas, US',     'Fuel.Natural gas', '#4AA3DF'),
    ('rubber',    '天然橡胶', '能源化工', 'Rubber, RSS3',    'Plant extract.Rubber', '#6B7280'),
    ('urea',      '尿素',   '能源化工', 'Urea',           None,              '#56C596'),
    ('dap',       '磷酸二铵', '能源化工', 'DAP',          None,              '#C084FC'),
]

series = {}
for code, cn, cat, wbkey, lrkey, color in SPEC:
    item = {'code': code, 'name': cn, 'cat': cat, 'color': color,
            'unit': wb[wbkey]['unit'] if wbkey in wb else '',
            'wb': {}, 'lr': {}}
    if wbkey in wb:
        item['wb'] = {str(y): round(v, 4) for y, v in sorted(wb[wbkey]['data'].items())}
    if lrkey and lrkey in lr:
        item['lr'] = {str(y): round(v, 2) for y, v in sorted(lr[lrkey].items())}
    series[code] = item

# 黄金超长系列（1833-2025）挂到 gold 上
series['gold']['ultra'] = {str(y): v for y, v in sorted(gold.items())}

out = {
    'meta': {
        'title': '大宗商品百年周期全景',
        'subtitle': '1900—2025 · 农产品 / 化工品 / 有色金属 / 贵金属 价格走势与轮动节奏',
        'built': '2026-10-12',
        'sources': [
            {'k': 'iFinD', 'v': '同花顺 iFinD 宏观行业经济数据库（EDB）—— 年度价格序列、指标元数据、交叉校验'},
            {'k': '发现研报', 'v': '国联期货《商品市场历史回顾、当前思考和未来展望》；招商证券《货币、地缘与滞胀：70-80 年代大宗商品牛市复盘》；浙商证券《如何理性布局历史最强厄尔尼诺？》；国信证券《本轮厄尔尼诺强度有概率创历史新高》'},
            {'k': 'World Bank', 'v': 'Commodity Markets Outlook · Pink Sheet 年度价格（1960—2024，名义美元）'},
            {'k': '长期序列', 'v': '1900 年起百年实际价格指数（1900=100）；黄金 1833—2025 年名义年均价（Timothy Green / LBMA 汇编）'},
        ],
    },
    'cats': ['贵金属', '有色金属', '农产品', '能源化工'],
    'series': series,
    'ifind_check': ifind,
}
json.dump(out, open(os.path.join(D, 'page_data.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('page_data.json', os.path.getsize(os.path.join(D, 'page_data.json')) // 1024, 'KB')
print('series:', len(series), '| gold ultra:', len(series['gold']['ultra']), '| lr gold:', len(series['gold']['lr']))
