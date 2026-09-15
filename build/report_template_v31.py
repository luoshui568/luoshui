# -*- coding: utf-8 -*-
"""研报标准模板 v3.1 —— 31 模块 / 六篇。

这是「补全后的新模板」的**唯一权威定义**，三处共用：
  1. 新建研报脚手架  build/new_report_v31.py
  2. 存量研报升级    build/upgrade_report_v31.py
  3. 研报页模板      deploy/report.template.html 的 MOD_SKELETON（由本文件导出）

相对旧模板（23 模块）的改动：
  * 新增 8 个模块：9 行业总览 / 10 下游需求结构 / 11 竞争格局与份额 / 12 管理层与治理
                   17 护城河量化 / 25 盈利预测模型 / 27 估值敏感性 / 30 多空论点对照
  * 升级 4 个模块：6 产能技术（+利用率趋势）/ 21 盈利能力（+杜邦分解）
                   23 现金流（+资产负债三表）/ 24 分红（+股东回报）/ 26 估值（+目标价推导）
  * 模块按「六篇」分组，toc 由 4 项扩到 6 项
  * 图表 16 → 28：新增 chartIndustrySize / chartDemandMix / chartShare / chartRoic
                   chartCashflow / chartDividend / chartEstimate / chartSens

⚠️ 模块编号是**位置主键**：库里 id = `{code}_m{no}`。升级时必须按 OLD2NEW 整位重排，
   不能只追加，否则旧内容会与新编号语义错位。
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_VERSION = 'v3.1'
TEMPLATE_MOD_COUNT = 31


# ----------------------------------------------------------------- 六篇
PARTS = [
    (1, '第一篇', '公司与行业基础'),
    (2, '第二篇', '产业链与成本'),
    (3, '第三篇', '经营与项目'),
    (4, '第四篇', '财务分析'),
    (5, '第五篇', '预测与估值'),
    (6, '第六篇', '结论与跟踪'),
]

PART_TITLE = {n: '%s · %s' % (a, b) for n, a, b in PARTS}


def M(no, part, title, charts=(), new=False, upgrade=False, must=()):
    return dict(no=no, part=part, title=title, charts=list(charts),
                new=new, upgrade=upgrade, must=list(must))


# ----------------------------------------------------------------- 31 模块
# charts：本模块标配图表 key（空 = 无图）。new=新增模块；upgrade=在旧模块上扩内容。
MODULES = [
    # —— 第一篇 公司与行业基础（12） ——
    M(1, 1, '公司简介', must=['基本信息表（成立/上市/代码/实控人/员工数）', '主营概要', '行业地位一句话']),
    M(2, 1, '公司历史沿革', must=['关键时间轴', '改制/重组/更名节点']),
    M(3, 1, '股东结构', must=['前十大股东表', '持股比例', '股东户数变化']),
    M(4, 1, '实控人与集团背景', must=['实控人性质（央企/省国资委/民营）', '集团资产与协同']),
    M(5, 1, '业务及产品', must=['产品矩阵表', '收入占比', '应用领域']),
    M(6, 1, '主要产品产能与技术', ['chartCap'], upgrade=True,
      must=['产能表（品种×产能）', '产能利用率趋势（新增）', '技术壁垒']),
    M(7, 1, '主要产品产量与销量（量价拆分）', ['chartProd'], upgrade=True,
      must=['产销量表', '均价×销量=收入 的拆解（新增）', '产销率']),
    M(8, 1, '主要子公司与基地', must=['子公司表（名称/持股/主营/净利）', '生产基地分布']),
    M(9, 1, '行业总览与市场空间', ['chartIndustrySize'], new=True,
      must=['行业定义与边界', '全球/中国市场规模表（年份/规模/增速）', '未来 3 年 CAGR',
            '增长驱动因素（政策/需求/替代）', '数据来源标注']),
    M(10, 1, '下游需求结构拆解', ['chartDemandMix'], new=True,
      must=['下游应用占比表', '各下游景气度（增速/订单）', '结构性变化趋势']),
    M(11, 1, '竞争格局与市场份额', ['chartShare'], new=True,
      must=['可比公司对比表（营收/毛利率/份额/市值）', '份额演变', '公司相对定位']),
    M(12, 1, '管理层与治理', new=True,
      must=['核心管理层表（姓名/职务/任期/背景）', '股权激励与考核目标', '治理结构特征']),

    # —— 第二篇 产业链与成本（3） ——
    M(13, 2, '产业链结构', must=['上中下游链条', '自给率', '一体化程度']),
    M(14, 2, '上游原料价格', ['chartRaw'], must=['原料价格走势', '供需平衡', '成本传导']),
    M(15, 2, '产品价格与成本', ['chartPrice'], must=['产品售价与成本均价', '剪刀差', '盈利弹性']),

    # —— 第三篇 经营与项目（3） ——
    M(16, 3, '在建工程与新项目', must=['在建项目表（投资额/进度/投产时间）', '达产效益', '资金来源']),
    M(17, 3, '护城河与竞争优势量化', ['chartRoic'], new=True,
      must=['ROIC vs WACC 利差（近 5 年）', '壁垒来源分项打分', '与同业对比']),
    M(18, 3, '风险矩阵', must=['风险表（概率×影响×预警信号）', '已发生风险事件']),

    # —— 第四篇 财务分析（6） ——
    M(19, 4, '公司营业收入与利润', ['chartRev'], must=['营收/归母净利历年表', '增速', '业绩归因']),
    M(20, 4, '公司产品收入与毛利结构', ['chartMix', 'chartMargin'], must=['分产品收入表', '毛利构成']),
    M(21, 4, '盈利能力与杜邦分解', ['chartMargin'], upgrade=True,
      must=['毛利率/净利率/ROE 趋势', '杜邦三因子分解（新增）', '与同业对比']),
    M(22, 4, '费用结构', ['chartExp'], must=['四费率趋势', '费用率异动解释']),
    M(23, 4, '现金流与资产负债三表', ['chartCashflow'], upgrade=True,
      must=['经营/投资/筹资现金流（新增）', '净现比', '资产负债率与有息负债（新增）',
            '营运资本（存货/应收）']),
    M(24, 4, '历年分红与股东回报', ['chartDividend'], upgrade=True,
      must=['历年分红表（每股股利/总额/分红率/股息率）', '累计回报', '分红政策']),

    # —— 第五篇 预测与估值（4） ——
    M(25, 5, '盈利预测模型', ['chartEstimate'], new=True,
      must=['量价成本三档假设（悲观/中性/乐观）显式列出', '未来 3 年营收/净利预测表',
            '关键假设敏感变量']),
    M(26, 5, '估值分析', ['chartValuation'], upgrade=True,
      must=['PE/PB 历史区间', '可比公司估值表', '估值方法选择与目标价推导（新增）']),
    M(27, 5, '估值敏感性', ['chartSens'], new=True,
      must=['敏感性矩阵（价格×销量 / 增速×折现率）', '目标价区间', '安全边际']),
    M(28, 5, '公司股价表现', ['chartPrice2'], must=['股价走势', '技术位置', '区间涨跌']),

    # —— 第六篇 结论与跟踪（3） ——
    M(29, 6, '企业评分（选股原则 10 项 · 满分 100）', must=['十项加权评分', '评级档位']),
    M(30, 6, '多空论点对照', new=True,
      must=['多方论点（含验证指标）', '空方论点（含证伪信号）', '当前天平倾向与理由']),
    M(31, 6, '投资结论与跟踪清单', must=['评级/目标价/时间维度', '催化剂日历', '跟踪阈值与复核触发条件']),
]

MOD_BY_NO = {m['no']: m for m in MODULES}
assert len(MODULES) == TEMPLATE_MOD_COUNT, '模块数应为 %d' % TEMPLATE_MOD_COUNT
assert [m['no'] for m in MODULES] == list(range(1, TEMPLATE_MOD_COUNT + 1))

# ----------------------------------------------------------------- 新旧映射
# 旧 23 模块 → 新 31 槽位。未出现在此表中的新编号 = 全新模块。
OLD2NEW = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,          # 第一篇前 8 项位置不变
    9: 13, 10: 14, 11: 15, 12: 16,                            # 产业链/原料/价格/在建 → 第二三篇
    13: 18,                                                   # 风险 → 18
    14: 19, 15: 20, 16: 21, 17: 22,                           # 财务四项
    18: 23, 19: 24,                                           # 现金流 / 分红（升级）
    20: 26, 21: 28,                                           # 估值 / 股价
    22: 29, 23: 31,                                           # 评分 / 结论
}
NEW_NOS = [m['no'] for m in MODULES if m['new']]
UPGRADE_NOS = [m['no'] for m in MODULES if m['upgrade']]
OLD_NOS = sorted(OLD2NEW)
assert len(OLD2NEW) == 23, '旧模块映射应为 23 项'
assert sorted(OLD2NEW.values()) == [n for n in range(1, 32) if n not in NEW_NOS], \
    '映射值应恰好覆盖非新增槽位'


def new_toc():
    """新建研报的默认目录：六篇各取一个代表模块。"""
    reps = [1, 13, 16, 19, 25, 29]
    return [{'anchor': 'm%d' % n, 'text': '%s %s' % (PART_TITLE[MOD_BY_NO[n]['part']].split(' · ')[0],
                                                     MOD_BY_NO[n]['title'][:8])}
            for n in reps]


def mod_skeleton_js():
    """导出给 report.template.html 的 MOD_SKELETON JS 字面量（按新编号顺序）。"""
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
        'parts': [{'no': n, 'label': a, 'name': b} for n, a, b in PARTS],
        'modules': MODULES, 'old2new': {str(k): v for k, v in OLD2NEW.items()},
        'new_nos': NEW_NOS, 'upgrade_nos': UPGRADE_NOS,
        'toc': new_toc(),
    }, ensure_ascii=False, indent=1))
    return p


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('模板 %s · %d 模块 / %d 篇' % (TEMPLATE_VERSION, len(MODULES), len(PARTS)))
    print('新增 %d 个：%s' % (len(NEW_NOS), NEW_NOS))
    print('升级 %d 个：%s' % (len(UPGRADE_NOS), UPGRADE_NOS))
    print('映射：', ', '.join('%d→%d' % (a, b) for a, b in sorted(OLD2NEW.items())))
    print('JSON 已写出：', dump_json())
    print()
    print(mod_skeleton_js())
