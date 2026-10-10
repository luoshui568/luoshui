# -*- coding: utf-8 -*-
"""生成「旧 23 模块 → 新 31 槽位」重排对照 SVG（供 show_widget 使用）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OLD = [
    (1, '公司简介'), (2, '公司历史沿革'), (3, '股东结构'), (4, '实控人与集团背景'),
    (5, '业务及产品'), (6, '主要产品产能与技术'), (7, '产量与销量（量价拆分）'),
    (8, '主要子公司与基地'), (9, '产业链结构'), (10, '上游原料价格'), (11, '产品价格与成本'),
    (12, '在建工程与新项目'), (13, '风险事件与关注事项'), (14, '公司营业收入与利润'),
    (15, '公司产品收入与毛利结构'), (16, '毛利率、净利率、ROE'), (17, '费用结构'),
    (18, '现金流与资产负债'), (19, '历年分红情况'), (20, '公司估值'), (21, '公司股价表现'),
    (22, '企业评分'), (23, '投资结论与跟踪清单'),
]

NEW = [
    (1, '公司简介', 'keep'), (2, '公司历史沿革', 'keep'), (3, '股东结构', 'keep'),
    (4, '实控人与集团背景', 'keep'), (5, '业务及产品', 'keep'),
    (6, '主要产品产能与技术', 'up'), (7, '产量与销量（量价拆分）', 'up'),
    (8, '主要子公司与基地', 'keep'), (9, '行业总览与市场空间', 'new'),
    (10, '下游需求结构拆解', 'new'), (11, '竞争格局与市场份额', 'new'),
    (12, '管理层与治理', 'new'), (13, '产业链结构', 'keep'), (14, '上游原料价格', 'keep'),
    (15, '产品价格与成本', 'keep'), (16, '在建工程与新项目', 'keep'),
    (17, '护城河与竞争优势量化', 'new'), (18, '风险矩阵', 'keep'),
    (19, '公司营业收入与利润', 'keep'), (20, '公司产品收入与毛利结构', 'keep'),
    (21, '盈利能力与杜邦分解', 'up'), (22, '费用结构', 'keep'),
    (23, '现金流与资产负债三表', 'up'), (24, '历年分红与股东回报', 'up'),
    (25, '盈利预测模型', 'new'), (26, '估值分析', 'up'), (27, '估值敏感性', 'new'),
    (28, '公司股价表现', 'keep'), (29, '企业评分（选股 10 项）', 'keep'),
    (30, '多空论点对照', 'new'), (31, '投资结论与跟踪清单', 'keep'),
]

OLD2NEW = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 13, 10: 14, 11: 15, 12: 16,
           13: 18, 14: 19, 15: 20, 16: 21, 17: 22, 18: 23, 19: 24, 20: 26, 21: 28,
           22: 29, 23: 31}

STYLE = {
    'keep': ('#444441', '#888780', '#D3D1C7'),
    'up':   ('#633806', '#EF9F27', '#FAC775'),
    'new':  ('#085041', '#5DCAA5', '#9FE1CB'),
}
LEFT_FILL, LEFT_STROKE, LEFT_TEXT = 'none', '#5F5E5A', '#B4B2A9'

Y0, PITCH, BH = 50, 22, 20
LX, LW = 40, 150
RX, RW = 490, 150
W = 680
H = Y0 + 31 * PITCH + 20


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


out = []
out.append('<svg viewBox="0 0 %d %d" width="100%%" role="img" xmlns="http://www.w3.org/2000/svg">' % (W, H))
out.append('<title>旧 23 模块模板到新 31 槽位的位置重排对照</title>')
out.append('<desc>左列是旧模板 m1 到 m23 的模块，右列是 v3.1 的 31 个位置，连线表示每个旧模块落到哪个新槽位，'
           '其中 9 行业总览、10 下游需求、11 竞争格局、12 管理层、17 护城河、25 盈利预测、27 估值敏感性、'
           '30 多空论点这 8 个槽位是新增。</desc>')

out.append('<text x="%d" y="34" font-size="12" font-weight="500" fill="#B4B2A9">旧 23 模块 ｜ 宝钛模板 20260826</text>' % LX)
out.append('<text x="%d" y="34" font-size="12" font-weight="500" fill="#B4B2A9">新 31 槽位 ｜ 研报模板 v3.1</text>' % RX)

# 连线（先画，压在方块下面）
for old_no, new_no in OLD2NEW.items():
    y1 = Y0 + (old_no - 1) * PITCH + BH / 2
    y2 = Y0 + (new_no - 1) * PITCH + BH / 2
    out.append('<path d="M%d %.1f L%d %.1f" fill="none" stroke="#5F5E5A" stroke-width="0.5"/>'
               % (LX + LW, y1, RX, y2))

# 左列
for no, title in OLD:
    y = Y0 + (no - 1) * PITCH
    out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="0.5"/>'
               % (LX, y, LW, BH, LEFT_FILL, LEFT_STROKE))
    out.append('<text x="%d" y="%.1f" font-size="11" fill="%s">%s</text>'
               % (LX + 8, y + BH / 2, LEFT_TEXT, esc('m%d %s' % (no, title))))

# 右列
for no, title, st in NEW:
    y = Y0 + (no - 1) * PITCH
    f, s, t = STYLE[st]
    out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="0.5"/>'
               % (RX, y, RW, BH, f, s))
    out.append('<text x="%d" y="%.1f" font-size="11" fill="%s">%s</text>'
               % (RX + 8, y + BH / 2, t, esc('m%d %s' % (no, title))))

out.append('</svg>')

svg = '\n'.join(out)
p = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_out_widget2.svg'
io.open(p, 'w', encoding='utf-8').write(svg)
print('写出 %s （%d 字符，H=%d）' % (p, len(svg), H))
print('连线 %d 条 ｜ 左 %d 格 ｜ 右 %d 格' % (len(OLD2NEW), len(OLD), len(NEW)))
print('新增槽位：', [n for n, _, s in NEW if s == 'new'])
print('升级槽位：', [n for n, _, s in NEW if s == 'up'])
