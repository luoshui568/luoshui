# -*- coding: utf-8 -*-
"""新建公司研报脚手架（标准模板 v3.1 · 31 模块 / 六篇）。

用法：
    python new_report_v31.py 688122 西部超导 "高端钛合金材料"
    python new_report_v31.py 601899 紫金矿业 --force        # 覆盖已存在的骨架

产出：
    build/seed/report_<code>.json       31 模块骨架（可直接推送入库）
    build/seed/data_v31_<code>.json     数据填写模板（字段即渲染器入参，含填写指引）

之后的标准流程：
    1) 填 build/seed/data_v31_<code>.json（财务/可比/行业/预测等）
    2) python upgrade_report_v31.py <code>     # 把数据渲染进 31 个模块
    3) python push_reports_v31.py <code>       # 备份 + 推送 + 回读核对
    ⚠️ 若公司已有 23 模块的旧研报，先把它归档为 seed/report_<code>_v23.json，
       upgrade 脚本会优先读归档件做「旧内容保留 + 新模块补齐」。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from report_template_v31 import MODULES, TEMPLATE_VERSION, new_toc, PART_TITLE

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')


def blank_mod_html(spec):
    """骨架内容：把「本模块应含」清单写进正文，打开就能照着填。"""
    must = spec.get('must') or []
    head = '<p>[待填] <b>%s</b> —— 本模块应含 %d 项：</p>' % (spec['title'], len(must))
    if not must:
        return head.replace('应含 0 项：', '说明：')
    lis = ''.join('<li>%s</li>' % x for x in must)
    return head + '\n    <ul style="margin-left:18px;font-size:13.5px;">%s</ul>' % lis


def blank_kpis():
    return [{'label': l, 'val': '—', 'unit': '', 'cls': '', 'style': ''}
            for l in ['现价', '总市值', 'PE(TTM)', 'PB', 'EPS', '营业收入', '归母净利', '每股净资产']]


def blank_data(code, name, industry):
    """数据填写模板 —— 字段名与 upgrade_report_v31.py 的渲染器一一对应。"""
    return {
        '_说明': '本文件是 seed/report_%s.json 的数据源；填好后跑 upgrade_report_v31.py %s' % (code, code),
        'code': code,
        'fin': {
            '_说明': '一手财务数据（单位：亿元 / %），years 与各数组等长',
            'years': ['2021', '2022', '2023', '2024', '2025'],
            'rev': [], 'np': [], 'gm': [], 'nm': [], 'ocf': [],
            'roe': [], 'roic': [], 'lev': [], 'dps': [],
            'wacc': None, 'wacc_note': 'WACC 假设口径写这里',
            'price': None, 'mktcap': None, 'pe': None, 'pb': None,
        },
        'industry': {'overview': '', 'cagr': '', 'drivers': [], 'source': '',
                     'size': [], 'sizeYears': [], 'sizeGrow': [], 'sizeUnit': ''},
        'demand': {'overview': '', 'rows': [], 'pie': [], 'note': '', 'source': ''},
        'peers': {'overview': '', 'rows': [], 'share': [], 'position': '', 'source': ''},
        'mgmt': {'overview': '', 'rows': [], 'incentive': '', 'governance': '', 'source': ''},
        'moat': {'items': [], 'verdict': ''},
        'forecast': {'cases': {}, 'note': '', 'years': [], 'series': []},
        'sens': {'overview': '', 'matrix': {}, 'heat': {}, 'margin': ''},
        'bullbear': {'bull': [], 'bear': [], 'tilt': ''},
        'chartNames': {},
    }


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) < 2:
        print(__doc__)
        sys.exit(1)
    code, name = a[0], a[1]
    industry = a[2] if len(a) > 2 else ''
    force = '--force' in sys.argv

    seedp = os.path.join(SEED, 'report_%s.json' % code)
    datap = os.path.join(SEED, 'data_v31_%s.json' % code)
    if os.path.exists(seedp) and not force:
        print('⚠ %s 已存在。若确认要重建，请加 --force（会覆盖骨架，但不会删除旧的 v23 归档）' % seedp)
        sys.exit(2)

    mods = []
    for spec in MODULES:
        mods.append({'seq': spec['no'], 'no': str(spec['no']),
                     'title': spec['title'], 'html': blank_mod_html(spec)})
    rep = {
        'code': code, 'name': name,
        'kicker': 'DEEP DIVE · 深度研究报告',
        'title': '%s（%s）深度研究报告' % (name, code),
        'subtitle': industry or '（副标题：一句话行业定位）',
        'badges': [], 'verdict_title': '核心结论',
        'verdict_html': '<p>[待填] 核心结论：中期方向、关键变量、估值位置、评级与目标价。</p>',
        'kpis': blank_kpis(), 'kpi_note': '',
        'toc': new_toc(),
        'essence_html': ('<div class="essence"><div class="et">THE ESSENCE · 一句话本质（可证伪命题）</div>'
                         '<div class="ec">[待填] 买它本质上是在买什么；什么条件下成立、什么条件下证伪。</div></div>'),
        'footer_html': ('<div class="disclaimer"><strong>免责声明</strong>：以上内容基于公开数据整理，'
                        '仅供参考，不构成投资建议。市场有风险，投资需谨慎。</div>'),
        'theme': 'red', 'sort': 99,
    }
    io.open(seedp, 'w', encoding='utf-8').write(
        json.dumps({'report': rep, 'mods': mods, 'charts': []},
                   ensure_ascii=False, separators=(',', ':')))
    io.open(datap, 'w', encoding='utf-8').write(
        json.dumps(blank_data(code, name, industry), ensure_ascii=False, indent=1))

    print('✓ 已按模板 %s 生成 %s（%d 模块 / %d 篇）' % (TEMPLATE_VERSION, name, len(mods), 6))
    print('  %s' % seedp)
    print('  %s' % datap)
    print('\n模块清单：')
    for spec in MODULES:
        flag = '🆕' if spec['new'] else ('⬆' if spec['upgrade'] else '  ')
        print('  %s %2d. %-22s  [%s]%s' % (flag, spec['no'], spec['title'],
                                           PART_TITLE[spec['part']].split(' · ')[0],
                                           ('  图：' + ','.join(spec['charts'])) if spec['charts'] else ''))
    print('\n下一步：填 %s → upgrade_report_v31.py %s → push_reports_v31.py %s' %
          (os.path.basename(datap), code, code))


if __name__ == '__main__':
    main()
