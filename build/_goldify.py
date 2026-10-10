# -*- coding: utf-8 -*-
"""把 000731 / 000830 从「v3.1 初版 31 模块顺序」整体搬到「宝钛母本 31 槽位」。

为什么不能直接重渲染：这两家的线上正文（约 4.0 万字符 / 16 图）是**上一代管线**
产出的，比本地 data_v31_*.json 现在能渲染出来的（约 2.5 万字符 / 8 图）厚得多。
重渲染 = 掉内容。所以本脚本走「原位搬家」：**正文一字不改，只换位置与标题**。

════════════════════════════════════════════════════════════════════
搬家规则（旧 31 → 母本 31，与 report_template_v31.OLD23_TO_GOLD 同源）

  旧位置  模块                        新位置
  1..8    公司简介…主要子公司与基地      不动
   9      行业总览与市场空间      →    24  {行业}行业介绍与市场规模
  10      下游需求结构拆解        →    20
  11      竞争格局与市场份额      →    21
  12      管理层与治理            →     9
  13      产业链结构              →    22
  14      上游原料价格            →    23
  15      产品价格与成本          →    12
  16      在建工程与新项目        →    17
  17      护城河与竞争优势量化    →    18
  18      风险矩阵                →    19
  19      公司营业收入与利润      →    10
  20      公司产品收入与毛利结构  →    11
  21      盈利能力与杜邦分解      →    13
  22      费用结构                →    14
  23      现金流与资产负债三表    →    15
  24      历年分红与股东回报      →    16
  25      盈利预测模型            →    27
  26      估值分析  ┐
  27      估值敏感性├─ 三块合成 ─→    28  估值分析
  28      公司股价表现┘
  29..31  企业评分/多空/结论      不动
  25/26   （母本新增槽位）← 产量储量分布及价格分析 / 供需格局与平衡表

铁律（与 move_mod_600456.py / merge_mod_600456.py 同源）
  · 正文「模块 N」交叉引用必须**单遍同时**替换（顺序替换会级联错位）
  · 模块 id = `{code}_m{no}` 是**位置主键**。本次 31→31、不删行不加行，
    走 push_reports_v31.py 的 `on_conflict=id` upsert 正好整位覆盖，
    所以**不需要** move/merge 那套两段式改号。
  · 图表完全不参与：靠正文里的 `data-chart="键名"` 挂载，与模块号无关。
    本脚本把线上 16 个图表行原样带回 seed，避免出现孤儿图。

用法：
  python build/_goldify.py 000731                 # 干跑（只打印，不写盘）
  python build/_goldify.py 000731 --go            # 写 seed/report_000731.json
  python build/_goldify.py 000731 000830 --go
  写盘后： python build/push_reports_v31.py 000731 000830
"""
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, B)
SEED = os.path.join(B, 'seed')
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Accept': 'application/json'}

from report_template_v31 import MOD_BY_NO, title_of, new_toc, TEMPLATE_VERSION  # noqa: E402
import report_build_v31 as RB  # noqa: E402  （只为复用 m_res / m_sdbalance）

GO = '--go' in sys.argv

# ------------------------------------------------------------------ 搬家映射
OLD31_TO_GOLD = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
    9: 24, 10: 20, 11: 21, 12: 9, 13: 22, 14: 23, 15: 12, 16: 17,
    17: 18, 18: 19, 19: 10, 20: 11, 21: 13, 22: 14, 23: 15, 24: 16,
    25: 27, 26: 28, 27: 28, 28: 28,
    29: 29, 30: 30, 31: 31,
}
MERGE_SRC = [26, 27, 28]      # 依次并入 28
MERGE_H3 = {26: None, 27: '估值敏感性', 28: '区间股价表现'}
NEW_SLOTS = {25: 'resource', 26: 'sdbalance'}

# 线上旧顺序的 31 个标题 —— 用来**证明**映射方向没搞反（错一个字就拒跑）
EXPECT_OLD_TITLES = [
    '公司简介', '公司历史沿革', '股东结构', '实控人与集团背景',
    '业务及产品', '主要产品产能与技术', '主要产品产量与销量（量价拆分）', '主要子公司与基地',
    '行业总览与市场空间', '下游需求结构拆解', '竞争格局与市场份额', '管理层与治理',
    '产业链结构', '上游原料价格', '产品价格与成本', '在建工程与新项目',
    '护城河与竞争优势量化', '风险矩阵', '公司营业收入与利润', '公司产品收入与毛利结构',
    '盈利能力与杜邦分解', '费用结构', '现金流与资产负债三表', '历年分红与股东回报',
    '盈利预测模型', '估值分析', '估值敏感性', '公司股价表现',
    '企业评分（选股原则 10 项 · 满分 100）', '多空论点对照', '投资结论与跟踪清单',
]

# 各家的行业名 + 新增槽位的「去哪取数」提示（化肥/化工都没有矿产禀赋，必须改写口径）
CFG_IN = {
    '000731': {
        'ind': '化肥',
        'resource': {
            'title': '中国尿素产能与产量分布',
            'price_title': '尿素价格走势',
            'note_title': '禀赋与产出的错配',
            'miss_hint': '取 iFinD EDB（尿素市场价 / 合成氨价格）与氮肥工业协会年报，'
                         '按「省份 / 产能（万吨） / 产量（万吨） / 占比」逐行列出，'
                         '并给近 24 个月尿素价格序列。判读要点：产能大省是否等于产量大省、'
                         '以及煤头/气头成本差异如何决定开工。'
                         '本槽**没有矿产储量口径**，不要去找一份不存在的储量表。',
            'source': '',
        },
        'sdbalance': {
            'miss_hint': '取氮肥工业协会年报 + 海关总署进出口数据，做成'
                         '「年份 / 供给（产量+进口） / 需求（表观消费+出口） / 缺口或过剩」四列表；'
                         '供给侧再给「煤头/气头产能占比 + CR5」，需求侧给「农业直施 / 工业（车用尿素·三聚氰胺）」。',
        },
    },
    '000830': {
        'ind': '化工',
        'resource': {
            'title': '主要产品产能分布',
            'price_title': '主要产品价格走势',
            'note_title': '产能布局与成本曲线',
            'miss_hint': '取 iFinD EDB 或卓创/百川的主要产品价格序列（PC / PA6 / 双氧水 / '
                         '甲烷氯化物 / 甲酸），并按「产品 / 产能（万吨） / 产量 / 占比」列出'
                         '公司产能构成。判读要点：一体化园区带来的原料自给率如何改变成本曲线。'
                         '本槽**没有矿产储量口径**，不要去找一份不存在的储量表。',
            'source': '',
        },
        'sdbalance': {
            'miss_hint': '取卓创资讯 / 百川盈孚供需平衡表 + 海关进出口数据，做成'
                         '「年份 / 供给 / 需求 / 缺口或过剩」四列表；供给侧给「产能 / 产量 / 进口依赖度」，'
                         '需求侧给「下游行业 / 占比 / 增速」。',
        },
    },
}

REPORT_KEYS = ['code', 'name', 'kicker', 'title', 'subtitle', 'badges', 'verdict_title',
               'verdict_html', 'kpis', 'kpi_note', 'toc', 'essence_html', 'footer_html', 'theme']


def get(path):
    rq = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(rq, timeout=90) as r:
        return json.loads(r.read().decode('utf-8'))


def fix_xref(html, mapping):
    """单遍同时替换正文里的「模块 N」——顺序替换会级联错位。"""
    def rep(m):
        n = int(m.group(2))
        return '%s%d' % (m.group(1), mapping.get(n, n))
    return re.sub(r'(模块\s*)(\d+)', rep, html or '')


def merge_before_src(dst_html, block_html):
    """把 block 接到 dst 正文里第一个 <p class="src"> 之前（各模块 src 惯例是收尾）。"""
    d = dst_html or ''
    i = d.find('<p class="src">')
    if i < 0:
        # 没有 src 脚注就直接接尾
        return d.rstrip() + '\n    ' + block_html
    return d[:i].rstrip() + '\n    ' + block_html + '\n    ' + d[i:]


def wrap_h3(title, html):
    body = '\n    '.join(p.strip() for p in re.split(r'\n\s*', (html or '').strip()) if p.strip())
    return '<h3>%s</h3>\n    %s' % (title, body)


def goldify(code, go):
    cfg = CFG_IN[code]
    print('=' * 78)
    print('%s ｜ 目标：搬到宝钛母本 31 槽位（行业名「%s」）' % (code, cfg['ind']))

    # -------- 读线上
    mods, off = [], 0
    while True:
        b = get('wb_report_mods?select=no,seq,title,html&report_id=eq.%s'
                '&order=seq.asc&limit=1000&offset=%d' % (code, off))
        mods += b
        if len(b) < 1000:
            break
        off += 1000
    mods.sort(key=lambda x: int(x['no']))
    rep = get('wb_reports?select=*&id=eq.%s' % code)[0]
    charts = get('wb_report_charts?select=seq,id,name,opt&report_id=eq.%s'
                 '&order=seq.asc&limit=1000' % code)

    # -------- 自检 1：必须正好 31 位、编号 1..31
    assert [int(m['no']) for m in mods] == list(range(1, 32)), \
        '线上不是 31 个连续模块：%s' % [m['no'] for m in mods]
    print('  线上：模块 %d ｜ 图 %d ｜ 正文 %d 字符'
          % (len(mods), len(charts), sum(len(m['html'] or '') for m in mods)))

    # -------- 自检 2：旧顺序标题必须逐字对上（防映射方向搞反）
    got_titles = [(m['title'] or '') for m in mods]
    bad = [(i + 1, got_titles[i], EXPECT_OLD_TITLES[i])
           for i in range(31) if got_titles[i] != EXPECT_OLD_TITLES[i]]
    if bad:
        print('  ❌ 线上标题与「v3.1 初版顺序」不符，拒绝搬家：')
        for n, g, e in bad:
            print('     m%-2d 实际「%s」≠ 期望「%s」' % (n, g, e))
        raise SystemExit(1)
    print('  旧顺序 31 个标题逐字校验通过 ✅（映射方向确认）')

    # -------- 自检 3：目标槽位覆盖 1..31 且不重不漏（28 是唯一的多对一）
    tgt = sorted(set(OLD31_TO_GOLD.values()) | set(NEW_SLOTS))
    assert tgt == list(range(1, 32)), '映射目标未覆盖 1..31：缺 %s' % (
        [n for n in range(1, 32) if n not in tgt])
    assert sorted(OLD31_TO_GOLD) == list(range(1, 32)), '映射源不是 1..31'
    multi = [k for k in OLD31_TO_GOLD if list(OLD31_TO_GOLD.values()).count(OLD31_TO_GOLD[k]) > 1]
    assert set(multi) == set(MERGE_SRC), '多对一只允许 %s，实际 %s' % (MERGE_SRC, multi)
    print('  映射覆盖 1..31 ✅（多对一仅 %s → 28）' % MERGE_SRC)

    byold = {int(m['no']): m for m in mods}

    # -------- 构造新 31 个模块
    new_mods = []
    for n in range(1, 32):
        spec = MOD_BY_NO[n]
        title = title_of(spec, cfg['ind'])
        if n in NEW_SLOTS:
            data = {NEW_SLOTS[n]: cfg[NEW_SLOTS[n]]}
            html = RB.m_res(data) if n == 25 else RB.m_sdbalance(data)
            new_mods.append({'seq': n, 'no': n, 'title': title, 'html': html})
            continue
        srcs = [k for k, v in OLD31_TO_GOLD.items() if v == n]
        assert len(srcs) >= 1, '槽位 %d 没有来源' % n
        if len(srcs) == 1:
            html = fix_xref(byold[srcs[0]]['html'], OLD31_TO_GOLD)
        else:
            html = byold[srcs[0]]['html']
            for extra in srcs[1:]:
                blk = wrap_h3(MERGE_H3[extra], fix_xref(byold[extra]['html'], OLD31_TO_GOLD))
                html = merge_before_src(html, blk)
        assert html and html.strip(), '槽位 %d 正文为空' % n
        new_mods.append({'seq': n, 'no': n, 'title': title, 'html': html})

    # -------- 自检 4：内容不丢（字数只增不减；表格/图槽/h3 不许减少）
    old_len = sum(len(m['html'] or '') for m in mods)
    new_len = sum(len(m['html'] or '') for m in new_mods)
    old_ch = sorted(set(re.findall(r'data-chart="([^"]+)"',
                                   '\n'.join(m['html'] or '' for m in mods))))
    new_ch = sorted(set(re.findall(r'data-chart="([^"]+)"',
                                   '\n'.join(m['html'] or '' for m in new_mods))))
    for label, pat in (('表格', r'<table\b'), ('h3 小节', r'<h3>'), ('图槽', r'data-chart=')):
        a = len(re.findall(pat, '\n'.join(m['html'] or '' for m in mods)))
        b = len(re.findall(pat, '\n'.join(m['html'] or '' for m in new_mods)))
        flag = '' if b >= a else '   ❌ 减少'
        print('  %-8s %d → %d%s' % (label, a, b, flag))
        assert b >= a, '%s 数量减少，拒绝执行' % label
    print('  正文 %d → %d 字符（新增槽位 %s）' % (old_len, new_len, [n for n in NEW_SLOTS]))
    print('  正文引用图槽 %d 个，与搬家前一致：%s' % (len(new_ch), new_ch == old_ch))
    assert new_ch == old_ch, '图槽集合变了：%s → %s' % (old_ch, new_ch)
    assert len(charts) >= len(new_ch), '图表行少于被引用的图槽'

    # -------- 自检 5：新顺序的标题必须与母本一致
    diffs = [(m['no'], m['title']) for m in new_mods
             if m['title'] != title_of(MOD_BY_NO[m['no']], cfg['ind'])]
    assert not diffs, '标题与母本不一致：%s' % diffs
    print('  31 个标题 = 宝钛母本（第 24 槽按行业名替换）✅')

    # -------- 目录
    toc = new_toc()
    print('  目录 %d 条：%s' % (len(toc), [x['text'] for x in toc]))

    # -------- 打印对照
    print()
    print('  %-4s %-32s %-8s %-30s %s' % ('slot', '新标题', '来源', '由图', '字数'))
    for n in range(1, 32):
        srcs = [k for k, v in OLD31_TO_GOLD.items() if v == n]
        c = sorted(set(re.findall(r'data-chart="([^"]+)"', new_mods[n - 1]['html'])))
        print('  %-4d %-32s %-8s %-30s %d'
              % (n, new_mods[n - 1]['title'][:32],
                 '新增' if n in NEW_SLOTS else '旧 m%s' % ','.join(str(x) for x in srcs),
                 ','.join(c)[:30], len(new_mods[n - 1]['html'])))

    if not go:
        print()
        print('（干跑结束，加 --go 才写 seed）')
        return

    # -------- 写 seed（先把现有 seed 备份）
    sp = os.path.join(SEED, 'report_%s.json' % code)
    if os.path.exists(sp):
        bak = os.path.join(B, 'backup', 'report_%s_pre_goldify_%s.json'
                           % (code, time.strftime('%Y%m%d-%H%M%S')))
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copy2(sp, bak)
        print('  旧 seed 备份 → %s' % os.path.basename(bak))

    seed = {
        'report': {k: (toc if k == 'toc' else rep.get(k)) for k in REPORT_KEYS},
        'mods': new_mods,
        'charts': [{'seq': c['seq'], 'id': c['id'].replace(code + '_', '', 1),
                    'name': c['name'],
                    'opt': json.loads(c['opt']) if isinstance(c['opt'], str) else c['opt']}
                   for c in charts],
    }
    seed['report']['toc'] = toc
    seed['_goldify'] = {'at': int(time.time() * 1000), 'tpl': TEMPLATE_VERSION,
                        'map': {str(k): v for k, v in OLD31_TO_GOLD.items()}}
    io.open(sp, 'w', encoding='utf-8').write(
        json.dumps(seed, ensure_ascii=False, separators=(',', ':')))

    # -------- 回读校验
    back = json.load(io.open(sp, encoding='utf-8'))
    assert [m['no'] for m in back['mods']] == list(range(1, 32))
    assert [c['id'] for c in back['charts']] == [c['id'] for c in seed['charts']]
    assert back['report']['toc'] == toc
    print('  写盘 %s（%d 字节）｜ 模块 %d ｜ 图 %d ｜ 正文 %d 字符 ｜ [MISSING] %d 处'
          % (os.path.basename(sp), os.path.getsize(sp), len(back['mods']),
             len(back['charts']), sum(len(m['html']) for m in back['mods']),
             sum(m['html'].count('[MISSING]') for m in back['mods'])))
    print('  回读校验通过 ✅')


if __name__ == '__main__':
    codes = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not codes:
        raise SystemExit('用法： python build/_goldify.py 000731 [000830] [--go]')
    for c in codes:
        goldify(c, GO)
    print()
    print('完成。下一步： python build/push_reports_v31.py %s' % ' '.join(codes))
