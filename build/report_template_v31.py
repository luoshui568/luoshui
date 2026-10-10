# -*- coding: utf-8 -*-
"""研报标准模板 v3.1 —— 31 模块 / 十节（以「宝钛股份 600456」线上版为母本）。

★ 2026-09-21 重写：**本文件现在的模块顺序与标题 = 宝钛股份线上报告的逐字复刻。**
  用户指令：「所有的 31 模块都按宝钛股份的 31 模块去做，不可乱改……目录也要按宝钛股份的目录去做。」

母本来源（宝钛线上库，2026-09-21 实测）：
  * wb_report_mods 的 no 1..31 + title —— 见本文件 MODULES
  * wb_reports.toc 的 10 条 —— 见本文件 SECTIONS / new_toc()

═══ 与「v3.1 初版蓝图」（2026-09-17）的差别 ═══
初版蓝图把 行业/需求/竞争 放在第 9-12 位、财务从第 19 位起、结尾是「估值敏感性 + 公司股价表现」。
宝钛线上经手工重构后（restructure_600456.py → move_mod → merge_mod → add_ti_mod）变成：
  · 第 9 位起就是「管理层与治理」，第 10-16 位是财务七项（营收→成本→盈利→费用→现金流→分红）
  · 产业链四项（下游需求/竞争格局/产业链/上游原料）挪到第 20-23 位
  · 第 24-26 位是「行业篇」三连：{行业}介绍与市场规模 / 产量储量分布及价格分析 / 供需格局与平衡表
  · 「估值敏感性」与「公司股价表现」不再单列，并入第 28 位「估值分析」
本文件即按此重构。

═══ 消费方（改本文件前先读这里）═══
  1. report_build_v31.py   —— 按 MODULES 逐槽取 RENDER[no] 渲染；POS2RENDER 定义「哪个槽用哪个渲染器」
  2. deploy/report.template.html 的 MOD_SKELETON（由 mod_skeleton_js() 导出）
  3. new_report_v31.py / upgrade_report_v31.py / mk_blueprint_html.py / patch_toc_labels.py

⚠️ 模块编号是**位置主键**：库里 id = `{code}_m{no}`。任何重排都必须整位重写
   （见 build/move_mod_600456.py 的「两段式改号」——先全改临时值再落终值，否则 m9↔m19 撞主键）。
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_VERSION = 'v3.1-gold'
TEMPLATE_MOD_COUNT = 31
GOLD_SOURCE = '600456'          # 母本代码：宝钛股份


# ----------------------------------------------------------------- 十节（= 宝钛线上 toc）
# (序号, 节名, 锚点, 覆盖的模块号)
SECTIONS = [
    (1,  '投资核心', 'verdict', []),
    (2,  '公司简介', 'm1',  [1, 2, 3, 4]),
    (3,  '公司业务', 'm5',  [5, 6, 7, 8, 9]),
    (4,  '公司营收', 'm10', [10, 11, 12, 13, 14, 15, 16]),
    (5,  '公司投资', 'm17', [17, 18, 19]),
    (6,  '公司链条', 'm20', [20, 21, 22, 23]),
    (7,  '行业分析', 'm24', [24, 25]),
    (8,  '供需分析', 'm26', [26]),
    (9,  '盈利预测', 'm27', [27, 28]),
    (10, '企业评分', 'm29', [29, 30, 31]),
]

# 保留 PART_TITLE 的 'X · Y' 形状（新报告脚手架与蓝图审计文档按 ' · ' 切分取值）。
_PARTS_LABEL = {1: '第一节', 2: '第二节', 3: '第三节', 4: '第四节', 5: '第五节',
                6: '第六节', 7: '第七节', 8: '第八节', 9: '第九节', 10: '第十节'}
PARTS = [(n, _PARTS_LABEL[n], nm) for n, nm, _a, _m in SECTIONS]
PART_TITLE = {n: '%s · %s' % (a, b) for n, a, b in PARTS}


def M(no, part, title, charts=(), must=()):
    return dict(no=no, part=part, title=title, charts=list(charts), must=list(must))


# ----------------------------------------------------------------- 31 模块（宝钛母本，逐字）
# charts：本槽渲染器会输出的图槽 key（空 = 无图）。
# 第 24 槽标题含 {ind} 占位符：由 title_of() 用 industry_name 填成「黄金行业介绍与市场规模」这类。
MODULES = [
    # —— 第二节 公司简介（1-4） ——
    M(1, 2, '公司简介',
      must=['基本信息表（成立/上市/代码/实控人/员工数）', '主营概要', '行业地位一句话']),
    M(2, 2, '公司历史沿革', must=['关键时间轴', '改制/重组/更名节点']),
    M(3, 2, '股东结构', must=['前十大股东表', '持股比例', '股东户数变化']),
    M(4, 2, '实控人与集团背景', must=['实控人性质（央企/省国资委/民营）', '集团资产与协同']),

    # —— 第三节 公司业务（5-9） ——
    M(5, 3, '业务及产品', must=['产品矩阵表', '收入占比', '应用领域']),
    M(6, 3, '主要产品产能与技术', ['chartCap'],
      must=['产能表（品种×产能）', '产能利用率趋势', '技术壁垒']),
    M(7, 3, '主要产品产量与销量（量价拆分）', ['chartProd'],
      must=['产销量表', '均价×销量=收入 的拆解', '产销率']),
    M(8, 3, '主要子公司与基地', must=['子公司表（名称/持股/主营/净利）', '生产基地分布']),
    M(9, 3, '管理层与治理',
      must=['核心管理层表（姓名/职务/任期/背景）', '股权激励与考核目标', '治理结构特征']),

    # —— 第四节 公司营收（10-16） ——
    M(10, 4, '公司营业收入与利润', ['chartRev'],
      must=['营收/归母净利历年表', '增速', '业绩归因']),
    M(11, 4, '公司产品收入与毛利结构', ['chartMargin'], must=['分产品收入表', '毛利构成']),
    M(12, 4, '产品价格与成本', ['chartPrice'], must=['产品售价与成本均价', '剪刀差', '盈利弹性']),
    M(13, 4, '盈利能力与杜邦分解', ['chartMargin'],
      must=['毛利率/净利率/ROE 趋势', '杜邦三因子分解', '与同业对比']),
    M(14, 4, '费用结构', ['chartExp'], must=['四费率趋势', '费用率异动解释']),
    M(15, 4, '现金流与资产负债三表', ['chartCashflow'],
      must=['经营/投资/筹资现金流', '净现比', '资产负债率与有息负债', '营运资本（存货/应收）']),
    M(16, 4, '历年分红与股东回报', ['chartDividend'],
      must=['历年分红表（每股股利/总额/分红率/股息率）', '累计回报', '分红政策']),

    # —— 第五节 公司投资（17-19） ——
    M(17, 5, '在建工程与新项目', must=['在建项目表（投资额/进度/投产时间）', '达产效益', '资金来源']),
    M(18, 5, '护城河与竞争优势量化', ['chartRoic'],
      must=['ROIC vs WACC 利差（近 5 年）', '壁垒来源分项打分', '与同业对比']),
    M(19, 5, '风险矩阵', must=['风险表（概率×影响×预警信号）', '已发生风险事件']),

    # —— 第六节 公司链条（20-23） ——
    M(20, 6, '下游需求结构拆解', ['chartDemandMix'],
      must=['下游应用占比表', '各下游景气度（增速/订单）', '结构性变化趋势']),
    M(21, 6, '竞争格局与市场份额', ['chartShare'],
      must=['可比公司对比表（营收/毛利率/份额/市值）', '份额演变', '公司相对定位']),
    M(22, 6, '产业链结构', must=['上中下游链条', '自给率', '一体化程度']),
    M(23, 6, '上游原料价格', ['chartRaw'], must=['原料价格走势', '供需平衡', '成本传导']),

    # —— 第七节 行业分析（24-25） / 第八节 供需分析（26） ——
    M(24, 7, '{ind}行业介绍与市场规模', ['chartIndustrySize'],
      must=['行业定义与边界', '全球/中国市场规模表（年份/规模/增速）', '未来 3 年 CAGR',
            '增长驱动因素（政策/需求/替代）', '数据来源标注']),
    M(25, 7, '产量储量分布及价格分析', ['chartResDist', 'chartResPrice'],
      must=['资源储量/产量分布（前 N 位）', '禀赋与产出的错配', '价格走势与成本传导']),
    M(26, 8, '供需格局与平衡表', ['chartSDBalance'],
      must=['供给侧结构（产能/产量/进口集中度）', '需求侧结构', '供需平衡表（缺口/过剩量）']),

    # —— 第九节 盈利预测（27-28） ——
    M(27, 9, '盈利预测模型', ['chartEstimate'],
      must=['量价成本三档假设（悲观/中性/乐观）显式列出', '未来 3 年营收/净利预测表',
            '关键假设敏感变量']),
    M(28, 9, '估值分析', ['chartValuation', 'chartSens', 'chartPrice2'],
      must=['PE/PB 历史区间', '可比公司估值表', '估值方法选择与目标价推导',
            '敏感性矩阵（并入）', '股价区间表现（并入）']),

    # —— 第十节 企业评分（29-31） ——
    M(29, 10, '企业评分（选股原则 10 项 · 满分 100）',
      must=['十项加权评分', '评级档位']),
    M(30, 10, '多空论点对照',
      must=['多方论点（含验证指标）', '空方论点（含证伪信号）', '当前天平倾向与理由']),
    M(31, 10, '投资结论与跟踪清单',
      must=['评级/目标价/时间维度', '催化剂日历', '跟踪阈值与复核触发条件']),
]

MOD_BY_NO = {m['no']: m for m in MODULES}
assert len(MODULES) == TEMPLATE_MOD_COUNT, '模块数应为 %d' % TEMPLATE_MOD_COUNT
assert [m['no'] for m in MODULES] == list(range(1, TEMPLATE_MOD_COUNT + 1))

# 十节必须无重叠地覆盖 1..31
_covered = sorted(n for _no, _nm, _a, mem in SECTIONS for n in mem)
assert _covered == list(range(1, 32)), '十节对模块的覆盖有误：%s' % _covered
for _no, _nm, _a, _mem in SECTIONS:
    for _n in _mem:
        assert MOD_BY_NO[_n]['part'] == _no, '模块 %d 的 part 与十节定义不符' % _n
    assert len(_nm) == 4, '节名「%s」不是 4 个字（侧栏统一 4 字）' % _nm
    assert not _nm.startswith('第'), '节名别带「第X节」前缀：%s' % _nm


# ----------------------------------------------------------------- 槽位 → 渲染器
# report_build_v31.py 的 RENDER 由此生成。值 = 该脚本里的函数名。
# ★ 第 24 槽用 m9（行业总览与市场空间）：内容即「{行业}介绍与市场规模」。
# ★ 第 28 槽用 m_val：把原「估值分析 + 估值敏感性 + 公司股价表现」三块合成一节（宝钛母本只有一节）。
# ★ 第 25/26 槽是本轮新增，渲染器为 m_res / m_sdbalance（数据块 resource / sdbalance）。
POS2RENDER = {
    1: 'm1', 2: 'm2', 3: 'm3', 4: 'm4', 5: 'm5', 6: 'm6', 7: 'm7', 8: 'm8', 9: 'm12',
    10: 'm19', 11: 'm20', 12: 'm15', 13: 'm21', 14: 'm22', 15: 'm23', 16: 'm24',
    17: 'm16', 18: 'm17', 19: 'm18', 20: 'm10', 21: 'm11', 22: 'm13', 23: 'm14',
    24: 'm9', 25: 'm_res', 26: 'm_sdbalance', 27: 'm25', 28: 'm_val', 29: 'm29',
    30: 'm30', 31: 'm31',
}
assert sorted(POS2RENDER) == list(range(1, 32)), 'POS2RENDER 必须覆盖 1..31'
_uniq = [v for v in POS2RENDER.values() if v not in ('m_val',)]
assert len(set(_uniq)) == len(_uniq), 'POS2RENDER 里出现了不该有的重复渲染器'


# ----------------------------------------------------------------- 新旧映射（历史存档）
# ★ 下面 OLD2NEW / NEW_NOS / UPGRADE_NOS 描述的是 **v3.1 初版蓝图（2026-09-17）** 那次升级，
#   已被本文件的宝钛母本取代。保留它们只是为了 mk_blueprint_html.py 与
#   upgrade_report_v31.py 不倒。**新工作不要再用它们做位置判断。**
OLD2NEW = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,          # 第一篇前 8 项位置不变
    9: 13, 10: 14, 11: 15, 12: 16,                            # 产业链/原料/价格/在建
    13: 18,                                                   # 风险 → 18
    14: 19, 15: 20, 16: 21, 17: 22,                           # 财务四项
    18: 23, 19: 24,                                           # 现金流 / 分红
    20: 26, 21: 28,                                           # 估值 / 股价
    22: 29, 23: 31,                                           # 评分 / 结论
}
NEW_NOS = [9, 10, 11, 12, 17, 25, 27, 30]        # v3.1 初版「新增」；历史值，勿用于新判断
UPGRADE_NOS = [6, 7, 21, 23, 24, 26]             # v3.1 初版「升级」；历史值，勿用于新判断
OLD_NOS = sorted(OLD2NEW)
assert len(OLD2NEW) == 23, '旧模块映射应为 23 项'
assert sorted(OLD2NEW.values()) == [n for n in range(1, 32) if n not in NEW_NOS], \
    '映射值应恰好覆盖非新增槽位（历史存档，勿改）'

# ★ 真正该用的映射：旧 23 模块 → 宝钛母本 31 槽位。
#   新增槽位：9 管理层与治理 / 18 护城河 / 20 下游需求 / 21 竞争格局 /
#             24 行业介绍 / 25 产量储量 / 26 供需格局 / 27 盈利预测 / 30 多空
#   合并槽位：28 估值分析（旧 20 估值 + 旧 21 股价表现）
OLD23_TO_GOLD = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
    9: 22,     # 产业链结构
    10: 23,    # 上游原料价格
    11: 12,    # 产品价格与成本
    12: 17,    # 在建工程与新项目
    13: 19,    # 风险矩阵
    14: 10,    # 公司营业收入与利润
    15: 11,    # 公司产品收入与毛利结构
    16: 13,    # 盈利能力与杜邦分解
    17: 14,    # 费用结构
    18: 15,    # 现金流与资产负债三表
    19: 16,    # 历年分红与股东回报
    20: 28,    # 估值分析（含敏感性/股价表现）
    21: 28,    # 公司股价表现 → 并入估值分析
    22: 29,    # 企业评分
    23: 31,    # 投资结论与跟踪清单
}
assert sorted(OLD23_TO_GOLD) == list(range(1, 24)), '旧 23 模块映射不完整'


# ----------------------------------------------------------------- 目录
TOC_REPS = [(a, nm) for _no, nm, a, _mem in SECTIONS]


def new_toc():
    """新建研报的目录 = **宝钛线上 wb_reports.toc 的逐字复刻**（10 条）。

    第 1 条锚在 `verdict`（页面顶部「核心结论」区，不是模块），其余锚在每节的首个模块。
    侧栏只有 160px，所以文案统一 4 个字；节名与锚点的对应关系见 SECTIONS。
    """
    return [{'anchor': a, 'text': t} for a, t in TOC_REPS]


def _check_toc():
    assert len(TOC_REPS) == len(SECTIONS), '目录条数应等于节数'
    mod_anchors = {('m%d' % n) for n in MOD_BY_NO}
    for a, t in TOC_REPS:
        assert a == 'verdict' or a in mod_anchors, \
            '目录锚点 %s 既不是 verdict 也不是模块' % a
        assert len(t) == 4, '目录文案「%s」不是 4 个字（侧栏统一 4 字）' % t
        assert not t.startswith('第'), '目录文案别带「第X节」前缀：%s' % t
    assert len(SECTIONS) == len(PARTS), '十节定义与 PARTS 不一致'


_check_toc()


def title_of(spec, ind_name=''):
    """模块标题：把第 24 槽的 {ind} 占位符换成具体行业名。

    宝钛母本叫「钛行业介绍与市场规模」；换成别的公司就是「黄金行业介绍与市场规模」。
    行业名缺失时退化成「行业介绍与市场规模」（不留 {ind} 字面量）。
    """
    t = spec['title']
    if '{ind}' in t:
        t = t.replace('{ind}', (ind_name or '').strip())
    return t


def mod_skeleton_js():
    """导出给 report.template.html 的 MOD_SKELETON JS 字面量（按母本编号顺序）。"""
    lines = []
    for m in MODULES:
        t = m['title'].replace("'", "\\'")
        lines.append("  '%s'%s" % (t, ',' if m['no'] < TEMPLATE_MOD_COUNT else ''))
    return 'var MOD_SKELETON = [\n' + '\n'.join(lines) + '\n];'


def dump_json(path=None):
    """把模板定义落成 JSON（给页面/其他脚本读取，便于版本对照）。"""
    p = path or os.path.join(HERE, 'seed', 'mod_template_v31.json')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, 'w', encoding='utf-8').write(json.dumps({
        'version': TEMPLATE_VERSION, 'count': TEMPLATE_MOD_COUNT,
        'gold_source': GOLD_SOURCE,
        'sections': [{'no': n, 'name': nm, 'anchor': a, 'mods': mem}
                     for n, nm, a, mem in SECTIONS],
        'parts': [{'no': n, 'label': a, 'name': b} for n, a, b in PARTS],
        'modules': MODULES, 'pos2render': POS2RENDER,
        'old2new': {str(k): v for k, v in OLD2NEW.items()},
        'old23_to_gold': {str(k): v for k, v in OLD23_TO_GOLD.items()},
        'new_nos': NEW_NOS, 'upgrade_nos': UPGRADE_NOS,
        'toc': new_toc(),
    }, ensure_ascii=False, indent=1))
    return p


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('模板 %s（母本 %s）· %d 模块 / %d 节' % (TEMPLATE_VERSION, GOLD_SOURCE,
                                                 len(MODULES), len(SECTIONS)))
    print()
    print('%-4s %-32s %-8s %s' % ('no', '标题', '节', '图槽'))
    for m in MODULES:
        print('%-4d %-32s %-8s %s' % (m['no'], m['title'], _PARTS_LABEL[m['part']],
                                      ','.join(m['charts'])))
    print()
    print('目录 %d 条：' % len(TOC_REPS))
    for a, t in TOC_REPS:
        print('  %-9s %s' % (a, t))
    print()
    print('槽位→渲染器：')
    print('  ' + ', '.join('%d:%s' % (k, POS2RENDER[k]) for k in sorted(POS2RENDER)))
    print()
    print('JSON 已写出：', dump_json())
