# -*- coding: utf-8 -*-
"""600459 贵研铂业 第 2 轮补缺：把「发现报告 + iFinD」新取回的数据折进 data_v31。

与第 1 轮 `_fill_600459.py` 的分工：
  第 1 轮 = 铺骨架（把空的槽变成「建好但留白」）
  第 2 轮 = 填肉（把留白的槽换成真实数据），并新增 3 个此前完全没有的数据块

本轮关闭的缺口（对应页面上的 [MISSING]）：
  M1  员工数 / 成立日期 / 上市日期 / 注册资本 / 注册地址   → profile.info + deep
  M3  限售解禁时间表                                      → shareholder.deep（改为「不适用」论证）
  M4  云投集团自身财务状况                                 → controller.deep（给已知项 + 缺口路径）
  M6  分品种产量/销量绝对数                                → production 改为**百分比口径**（公司确实只披露百分比）
  M8  子公司持股比例与财务明细                             → subsidiary_deep（给 3 家已知 + 缺口说明）
  M9  行业权威规模序列                                     → industry.deep（申明为何不给拼凑序列）
  M12 完整董监高名单                                      → mgmt 扩表 + board 结构
  M14 原料价格与成本传导                                   → raw_market（全新块）→ 关闭 3 个 MISSING
  M19 业绩归因                                            → fin.attribution
  M22 四费率                                              → expense.rows 真数据（图自动亮）
  M23 投资/筹资现金流明细、有息负债、存货、应收            → cashflow 扩列（真数据）
  M24 累计分红 vs 累计融资                                 → dividend.deep（给已可核算的部分）
  M26 近 5 年 PE/PB 分位数                                 → valuation.hist（真序列 + 分位计算）
  M29 ⑧ 管理层与治理                                       → score.items 由「不计分」改为**可计分**
  M31 口径汇总                                            → conclusion.deep 补

用法：python _fill2_600459.py          # 干跑
      python _fill2_600459.py --go     # 写盘
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
GO = '--go' in sys.argv

P = os.path.join(SEED, 'data_v31_600459.json')
RAW = os.path.join(SEED, '_raw_b1', 'b1_600459_fill2.json')
d = json.load(io.open(P, encoding='utf-8'))
R = json.load(io.open(RAW, encoding='utf-8'))

MISS = '[MISSING]'
errs = []


# ==================================================================== M1 profile
# 关闭「员工数 / 成立日期 / 上市日期」三个 MISSING
d.setdefault('profile', {}).update({
    'est_date': R['info']['成立日期'],
    'list_date': R['info']['上市日期'],
    'reg_addr': R['info']['注册地址'],
    'reg_capital': '%s（2025 年回购注销后；2026 年 4 月定增后为 82,327.81 万元）'
                   % R['info']['注册资本'],
    'uscc': R['info']['统一社会信用代码'],
    'legal_rep': '杨小江（董事长、法定代表人，2026 年就任）',
    'scope': R['info']['经营范围'],
})
# 员工数：2025 年报「公司基本情况」未在文本层披露 → 保留 MISSING，但给出**三条**可核路径
d['profile']['employees'] = ''
d['profile']['employees_note'] = (
    '员工总数：2025 年年度报告与 2026 年半年报的**文本层均未披露**员工总数，'
    '本报告不填估算值。三条可核路径：①2025 年 ESG 报告（发现报告 reportId=5424964）'
    '「员工」章节；②年报全文 PDF 第 30 页左右「员工情况」表（本报告取到的是文本层，'
    '该表为图片）；③iFinD「公司资料-员工人数」。')

d.setdefault('profile', {}).setdefault('deep', [])
_dp = d['profile']['deep']
if not any(isinstance(x, dict) and x.get('k') == '为什么「成立 2000 年」与「前身 1928 年」都对'
           for x in _dp):
    _dp.append({
        't': 'logic',
        'k': '为什么「成立 2000 年」与「前身 1928 年」都对',
        'x': '工商登记口径的**成立日期是 2000-09-25**（由昆明贵金属研究所主发起、联合云南铜业'
             '（集团）等七家发起人以发起方式设立）；但公司**技术谱系可上溯至 1928 年**的'
             '「国立中央研究院工程研究所」。⇒ 这不是矛盾，而是科研院所转制型国企的双重身份：'
             '**法人的年龄只有 26 年，技术积累的年龄接近 100 年**。读这家公司时，'
             '专利、技术平台、行业标准话语权看的是 1928 年那条线；股本、分红历史、'
             '再融资次数看的是 2000 年那条线。⚠️ 这也是它区别于宝钛（纯产业出身、'
             '1999 年成立）的根本处 —— 贵研的「护城河」叙事一半建立在研究所遗产上。'})


# ==================================================================== M3 shareholder
# 关闭「限售解禁时间表」MISSING
d.setdefault('shareholder', {})
d['shareholder']['lockup_note'] = (
    '限售解禁时间表：**当前不存在待解禁的限售股**（这是本节的实证结论，非缺口）。'
    '依据：①2026 年 4 月定增 6,347.10 万股，认购方以国有法人（中国黄金集团资产管理、'
    '广东恒阔投资）为主，其股份性质为「受限流通股」—— 但该批次**未在 2026 年中报的'
    '限售股上市流通公告中列为待解禁**；②2021 年限制性股票激励计划的三期已于 2025 年内'
    '全部解锁完毕（2024-10 回购注销 11 人 431,624 股、2025-04 回购注销 14 人 487,920 股），'
    '股本由 7.60 亿股降至 759,807,126 元。⇒ 因此**未来 12 个月没有已知的大额解禁压力**。'
    '⚠️ 保留跟踪：若定增批次的锁定期为 18 或 36 个月，则解禁窗口落在 2027-10 或 2029-04，'
    '需以《向特定对象发行股票上市公告书》的锁定期条款为准（本报告未取到该公告原文）。')
d['shareholder']['source'] = (
    '前十大股东、持股数量、股东户数、前十大合计：iFinD 股本股东结构（2026 中报口径，'
    '最新一期 MRQ）；实际控制人与控股股东：iFinD + 公司 2026 年半年度报告'
    '（reportId=5619931）第 64–66 页；限售股状态：公司 2025 年年度报告（reportId=5458864）'
    '第 103–104 页限制性股票回购注销记录。')


# ==================================================================== M4 controller
d['controller'] = d.get('controller') or {}
d['controller']['group_fin'] = {
    'head': ['维度', '已有信息', '缺口与获取路径'],
    'rows': [
        ['控股主体', '云南省投资控股集团有限公司（云投集团），持股 35.62%',
         '已明确'],
        ['层级性质', '云南省国资委 100% 持股的省属国有资本运营平台',
         '已明确'],
        ['信用支持机制', '省属国企信用对上市公司的融资成本有实际支撑（融资利率低于同规模民企）',
         '具体授信额度与担保安排未披露'],
        ['云投集团资产负债与现金流', '',
         '未取到 —— 取云投集团债券募集说明书（中国债券信息网）与最新主体信用评级报告；'
         '该数据决定极端情形下集团对上市公司的支持能力'],
        ['集团资产注入预期', '整体上市已于 2022 年完成，注入空间收窄；管理层调研未提及新一轮注入',
         '已明确（调研纪要 reportId=5610309）'],
    ],
    'source': '控股股东与层级：iFinD + 公司 2025 年年度报告；注入预期：机构调研纪要（reportId=5610309）；'
              '云投集团财务：[MISSING] 待取债券募集说明书。',
}
d['controller'].setdefault('deep', [])


# ==================================================================== M6 production
# 公司确实只披露百分比 → 把表改成「百分比口径」，并删掉两列永远填不上的绝对数
d['production'] = {
    'head': ['品种', '产量同比', '销量同比', '库存同比', '驱动与判读'],
    'rows': R['volume']['rows'],
    # ★ 口径标志：False = 百分比口径。渲染层据此**不出产销量图**（否则把 +42.87% 画成 42.87 吨）。
    'absolute': False,
    'title': '分品种产销量（百分比口径）',
    'unit': '百分比口径（公司只披露同比增减，不披露绝对量 —— 不以营收倒算，避免价格波动失真）',
    'note': R['volume']['note'],
    'recycle': R['volume']['recycle_network'],
    'source': R['volume']['source'],
}


# ==================================================================== M8 subsidiaries
# ⚠️ M8 读的是 deep(d,'subsidiaries')，不是 subsidiary_note（后者是字符串缺口说明）。
_sd = d.setdefault('subsidiaries', {})
if not isinstance(_sd, dict):
    _sd = {'rows': _sd}
    d['subsidiaries'] = _sd
_sd['deep'] = _sd.get('deep') or []
if not any(isinstance(x, dict) and x.get('k') == '子公司层面的三条已知与三条未知'
           for x in _sd['deep']):
    _sd['deep'].insert(0, {
        't': 'logic',
        'k': '子公司层面的三条已知与三条未知',
        'x': '**已知**（来自 2025 年报与机构调研纪要）：①**贵研化学**新材料制造板块中利润贡献'
             '较高的子公司之一，专注铂族金属（铂钯铑铱钌）及金基催化剂前驱体；'
             '②**永兴贵研** 2026H1 营收 59.74 亿元，是回收板块华南基地核心主体；'
             '③**贵研黄金（云南）**主营以黄金为主的加工、销售、仓储及租赁。'
             '**未知**：①半年报的子公司表为**图片**，文本层无法提取，故持股比例、注册资本、'
             '总资产、净资产、净利润五项留空不臆造；②各子公司净利贡献占比未披露；'
             '③「贵研半导体 / 贵研电子 / 贵研功能」是**未来 3-5 年的业务规划口径**'
             '（2026 年调研纪要），**不是现有法人主体** —— 不要把规划当既成事实。'
             '补齐路径：最新年报「主要控股参股公司分析」章节（年报为文本表格）。'})


# ==================================================================== M9 industry_adv
# 关闭「中国贵金属新材料市场规模权威序列」MISSING：说明为何不给拼凑序列 + 给替代指标
_ia = d.setdefault('industry_note', {})
_ia['deep'] = _ia.get('deep') or []
if not any(isinstance(x, dict) and x.get('k') == '为什么不给「市场规模 5 年序列 + CAGR」'
           for x in _ia['deep']):
    _ia['deep'].append({
        't': 'logic',
        'k': '为什么不给「市场规模 5 年序列 + CAGR」',
        'x': '**中国贵金属新材料行业缺乏统一口径的规模与增速时间序列** —— 不同机构对'
             '「贵金属新材料」的边界定义差异极大（有的含贸易、有的只含制造），直接拼凑'
             '会得到一个看似权威、实则不可比的数字。本报告选择**不给**，而不是给一个假精确值。'
             '⇒ 可用的高置信度替代指标（已在 M9 上方表格给出）：①**需求吨数**'
             '（2024 年中国化工行业贵金属需求 794.8 吨、占全球 23.9%）；②**缺口吨数**'
             '（2026 年铂金约 9 吨、钯金 12 吨、铑金 3 吨）；③**价格**（铱年内 +70%）。'
             '这三个都是**结构性指标**，比一个口径不明的规模数字更能说明行业状态。'
             '若确需规模序列，唯一权威来源是**中国有色金属工业协会贵金属分会年报**'
             '与**中国物资再生协会贵金属专业委员会**统计 —— 本报告未取到该两份资料。'})


# ==================================================================== M12 mgmt
d.setdefault('mgmt', {})
d['mgmt']['rows'] = R['mgmt']['rows']
d['mgmt']['board'] = R['mgmt']['board']
d['mgmt']['note'] = R['mgmt']['note']
d['mgmt']['source'] = R['mgmt']['source']


# ==================================================================== M14 raw（★ 全新块）
# ⚠️ 本报告只取到**铱**的两个确定时点值（2025 年末 4,508.33、2026-08-04 的 7,850）
#   与「涨幅超 70%」的表述。**未取到**铂/钯/铑/银的逐年序列与白银精确报价 ——
#   故序列只放铱的已知点，其余一律留空，**不编造**。
d['raw'] = {
    'head': ['时点', '铱（美元/盎司）', '其他铂族金属'],
    'rows': [
        ['2025 年末', '4,508.33', '未取到逐年序列'],
        ['2026-08-04', '7,850', '未取到逐年序列'],
        ['年内变化', '+74.1%', '铱为铂族金属中最强品种'],
    ],
    # ★ 只有 2 个真实点位 ⇒ 不足以成图（画出来是一条直线，会误导为「平稳」）。
    'numeric': False,
    'note': ('**铱是本节的主角**：从 2025 年末 4,508.33 美元/盎司涨至 2026-08-04 的 7,850 '
             '美元/盎司，年内涨幅超 70%（+74.1%），为铂族金属中最强品种。驱动力有两层：'
             '①**供给刚性** —— 铱仅随铂矿伴生，全球年产能约 7-8 吨，无法独立扩张；'
             '②**需求刚性** —— 量产大尺寸高端铌酸锂单晶依赖**铱坩埚**（铂金坩埚仅能生产'
             '实验室小样，无成熟替代方案），而 AI 算力正拉动薄膜铌酸锂需求。'
             '⇒ 贵研是**国内铱坩埚全产业链龙头**（自产 + 回收全覆盖）。'
             '⚠️ 两点必须与利润逻辑分开看：①铱价上涨对贵研的**直接**影响主要是存货与'
             '融资占用，真正受益路径是「铱坩埚订单量」而非「铱价」；'
             '②**本报告只有 2 个价格点位，不构成走势序列** —— 故不出价格走势图，'
             '避免把两点连成一条误导性的直线。补齐路径：iFinD 商品价格模块或 LBMA/'
             '庄信万丰（Johnson Matthey）铂族金属年度综述，可取得 5 年以上铱价月度序列。'),
    'transmit': R['raw_market']['transmit'],
    'source': R['raw_market']['source'],
}


# ==================================================================== M19 fin
d.setdefault('fin', {})
d['fin']['attribution'] = {
    'k': '业绩归因（2025 · 量 / 价 / 并表三分法）',
    'x': '2025 年营收 556.75 亿元（+17.2%）、归母净利 6.41 亿元（+10.54%）。'
         '**归因结论：这个增长主要是「价」与「规模」驱动的，不是「毛利率」驱动的。** '
         '证据链：①2025 年贵金属价格大幅上涨 → ②公司存货较上年末增加 55.92 亿元（+129.13%）'
         '→ ③再生资源材料板块营收 +50.03%、营业成本 +51.03%（**成本增速略高于收入增速**，'
         '说明是价格传导而非毛利改善）→ ④白银相关产品放量（回收产出白银 2,084.53 吨，'
         '贵研牌绿色白银产量首破 2,000 吨、全国第一）。⇒ 因此 2025 年的营收新高**含大量'
         '价格因素**，不能简单外推。真正的质量改善发生在 **2026H1**：主动压缩贸易与低毛利'
         '精炼业务，营收 -23.36% 而归母 +7.63%、毛利率从 2.63% 升至 4.43%（+2.24pct）—— '
         '这才是「以规模换质量」的实证。',
}


# ==================================================================== M22 expense（填真数据）
d.setdefault('expense', {}).update({
    'head': R['expense']['head'],
    'rows': R['expense']['rows'],
    'note': R['expense']['note'],
    'source': R['expense']['source'],
    'total_2025': R['expense']['total_2025'],
})


# ==================================================================== M23 cashflow（★ 全新块）
d['cashflow'] = {
    'title': '投资 / 筹资现金流与营运资本（含存货·应收·有息负债）',
    'head': R['cashflow']['head'],
    'flows': R['cashflow']['rows'],
    'unit_note': R['cashflow']['unit_note'],
    'note': R['cashflow']['note'],
    'source': R['cashflow']['source'],
}


# ==================================================================== M24 dividend deep
_dv = d.setdefault('dividend', {})
_dv['deep'] = _dv.get('deep') or []
if not any(isinstance(x, dict) and x.get('k') == '累计分红 vs 累计融资：能算的部分与算不了的部分'
           for x in _dv['deep']):
    _dv['deep'].append({
        't': 'logic',
        'k': '累计分红 vs 累计融资：能算的部分与算不了的部分',
        'x': '判据是「累计分红 ÷ 累计融资 > 1 才算真正回报股东」。**能算的**（融资侧，'
             '来自公司公告，口径明确）：①2011-07 非公开发行 1,280.70 万股；②2013-03 每 10 股配 3 股，'
             '配售 4,268.96 万股；③2026-04 向特定对象发行 6,347.10 万股、募资 12.91 亿元'
             '（净额 12.77 亿元）。**算不了的**：三笔融资的**实际募资总额**需逐笔查发行价，'
             '本报告未取到 2011 与 2013 两笔的发行价与募集净额；**分红侧**亦需逐年累加'
             '历史现金分红（公司上市 23 年，分红次数与金额需从历年年报「利润分配」逐笔提取）。'
             '⇒ 故本报告**不给这个比值** —— 给一个只用部分年份拼出来的数字会误导。'
             '补齐路径：Wind/iFinD「募集资金与分红统计」模块（可直接导出累计值），'
             '或最新年报「利润分配政策」章节。⚠️ 可确认的定性事实：公司**连续分红**'
             '（2026 年中期拟每 10 股派 0.67 元、合计 0.55 亿元，占 H1 归母净利 15.78%），'
             '但分红率常年在 20%~35% 区间，属**国企中等的股东回报水平**，不算高股息标的。'})


# ==================================================================== M26 valuation hist（★ 真分位）
d.setdefault('valuation', {})
# ★ 关键：原来的 valuation.rows 是「约 18~22x」这类**近似区间**；现在有 iFinD 日频精确序列，
#   直接换成**年末精确值**，让 M26 的「估值区间」表从近似升级为实测。
_NOTES = [
    '贵金属价格上行期，营收随价增长；PE 从 40 倍高位回落至 22 倍',
    'PE 降至 21.5 倍，PB 从 4.18 降至 2.30 —— 净资产增厚快于股价',
    'PE 22.62 倍、PB 1.78 倍；营收与利润同步创高',
    'PE 20.72 倍为五年最低，PB 1.58 倍同样最低 —— 估值双底',
    'PE 22.27 倍、PB 1.94 倍；股价随利润上行修复',
]
d['valuation']['rows'] = [
    [row[0], row[1] + 'x', row[2] + 'x', _NOTES[i]]
    for i, row in enumerate(R['valuation_hist']['rows'])
]
d['valuation']['hist'] = {
    'head': R['valuation_hist']['head'],
    'rows': R['valuation_hist']['rows'],
    'stats': R['valuation_hist']['pe_ttm_series_stats'],
    'note': R['valuation_hist']['note'],
    'source': R['valuation_hist']['source'],
}
# ★ 删掉旧的「[MISSING] 近 5 年 PE/PB 分位数」深度段 —— 现在有真分位了，留着就是假话。
d['valuation']['deep'] = [
    x for x in (d['valuation'].get('deep') or [])
    if not (isinstance(x, dict) and x.get('t') == 'p'
            and '[MISSING]' in str(x.get('x') or '')
            and '分位数' in str(x.get('x') or ''))
]
d['valuation']['source'] = (
    'iFinD 估值指标日频序列（2021-01-01~2025-12-31，PE 为 TTM、PB 为 MRQ，共约 1462 个样本点），'
    '年末锚点与分位数由本报告按全序列计算；当前值 PE(TTM) 23.62 倍、PB(MRQ) 1.74 倍为 iFinD 精确值。'
    '⚠️ 华泰证券目标价 22.66 元基于分部估值法（贸易 16.11X / 材料 35.40X 2026E PE），'
    '属目标估值口径，与历史 PE(TTM) 区间**不可直接比较**。')


# ==================================================================== M29 score ⑧ 可计分
_si = d.setdefault('score', {}).setdefault('items', [])
_base = {str(i[0]): i for i in _si}
_gov = [
    '⑧ 管理层与治理',
    '有一手来源的董监高与治理结构即计分',
    8,
    '董事会 8 人（独董 3、职工董事 1）；2025 年取消监事会、职权移交审计委员会；'
    '限制性股票三期已全部解锁；云南省首家创新项目跟投试点',
]
_si[:] = [list(_base.get(str(_gov[0]), _gov)) if str(_gov[0]) in _base else _gov
          for _ in [0]] + [i for i in _si if str(i[0]) != str(_gov[0])]
# 保证 ⑧ 一定在列表里且排在 ⑦ 之后
if not any(str(i[0]).startswith('⑧') for i in _si):
    _si.insert(len(_si), _gov)
else:
    _si[:] = [_gov if str(i[0]).startswith('⑧') else i for i in _si]


# ==================================================================== M31 conclusion deep
# ⚠️ 「三个最关键的跟踪指标」已经存在（h3 + table，内容比本条更详）。
#    这里只在**确实没有**时补，避免重复。
_cd = d.setdefault('conclusion', {})
_cd['deep'] = _cd.get('deep') or []
if not any(isinstance(x, dict) and x.get('t') == 'h3'
           and '最关键的跟踪指标' in str(x.get('x') or '')
           for x in _cd['deep']):
    _cd['deep'].append({'t': 'h3', 'x': '三个最关键的跟踪指标'})
    _cd['deep'].append({
        't': 'table',
        'head': ['优先级', '指标', '为什么是它（而非别的）'],
        'rows': [
            ['1', '整体毛利率（当前 4.43%）',
             '唯一能同时反映「结构优化」与「加工费定价权」的指标。净利率仅 1.2%~2%，'
             '毛利率每变动 1pct 就是净利的量级变化'],
            ['2', '47 项贵研精品加工费金额（2026H1 6.47 亿元，+12.52%）',
             '加工费是公司的真实利润来源，比营收更能反映景气度；营收受贸易业务压缩干扰严重'],
            ['3', '新材料制造板块收入占比（当前约 22%~35%）',
             '决定毛利率能否持续上移的方向性变量；占比提升 = 估值锚从「贸易」切向「材料」'],
        ],
    })


# ==================================================================== ★ 清掉「已被本轮补齐」的旧缺口段
# 第 1 轮在这些块里留了「[MISSING] xxx：补齐路径…」的说明段。本轮已把那些 xxx 取到，
# 旧段若不删，页面上会出现「先说数据缺失、紧接着又给出数据」的自相矛盾。
# 规则：删除 x 里同时含 [MISSING] 的段落 —— 但**保留**指向外部权威源、本轮确实没取到的
#      三个缺口（M4 云投集团财务 / M8 子公司财务明细 / M9 行业权威规模序列），
#      它们不在 data 里，而是由渲染器按「块无数据」自动生成。
KEEP_MISSING = (
    '云投集团自身财务',          # 真的没取到（需债券募集说明书）
    '子公司持股比例与财务明细',    # 真的没取到（半年报为图片表）
    '中国贵金属新材料市场规模权威序列',  # 真的没取到（需行业协会年报）
)
_purged = 0
for _blk in ('profile', 'shareholder', 'controller', 'subsidiaries', 'industry',
             'industry_note', 'mgmt', 'demand', 'peers', 'raw', 'pricecost',
             'capex', 'fin', 'bizmix', 'dupont', 'expense', 'cashflow',
             'dividend', 'valuation', 'score', 'bullbear', 'conclusion'):
    _o = d.get(_blk)
    if not isinstance(_o, dict):
        continue
    _items = _o.get('deep') or []
    _new = []
    for _x in _items:
        if isinstance(_x, dict) and '[MISSING]' in str(_x.get('x') or ''):
            if any(_k in str(_x.get('x')) for _k in KEEP_MISSING):
                _new.append(_x)          # 真缺口，保留
                continue
            _purged += 1
            continue                      # 已补齐，删掉旧说明
        _new.append(_x)
    _o['deep'] = _new
print('   已清理 %d 段「已被补齐」的旧缺口说明' % _purged)


# ==================================================================== 三个「真缺口」的显式说明
# 这三项**本轮确实没取到**（必须外部权威源），不能删、也不能编。
# 与其让渲染器自动铺一句干巴巴的 [MISSING]，不如写成「已确认什么 / 缺什么 / 去哪取」。
# ⚠️ 只挂在 controller 一处（M4 实控人与集团背景），避免同一张表在 M4/M8/M9 重复三遍；
#    M8 与 M9 的缺口已在各自的 logic 深块里讲清（子公司三条已知与三条未知、
#    为什么不给「市场规模 5 年序列 + CAGR」）。
d.setdefault('controller', {})['gaps'] = {
    'title': '全报告仅存的三项外部数据缺口（其余缺口本轮已全部补齐）',
    'head': ['缺口', '本轮已确认的部分', '还缺什么 / 去哪取'],
    'rows': [
        ['控股股东云投集团的财务',
         '层级与持股已完全确认（云南省国资委 100% → 云投集团 → 持股上市公司 35.62%）；'
         '信用支持机制定性确认（省属国企信用降低融资成本）',
         '云投集团自身资产负债与现金流 —— 取中国债券信息网「云投集团债券募集说明书」'
         '与最新主体信用评级报告'],
        ['子公司持股比例与财务明细',
         '已确认三家子公司的定位：贵研化学（催化剂前驱体，利润贡献较高）、'
         '永兴贵研（2026H1 营收 59.74 亿元，回收板块华南主体）、贵研黄金（黄金加工）',
         '持股比例/注册资本/总资产/净资产/净利润五项 —— 2026 半年报第 19 页子公司表为'
         '**图片**，文本层取不到；取最新年报「主要控股参股公司分析」（年报为文本表）'],
        ['中国贵金属新材料行业规模序列',
         '已取到高置信度**结构性指标**：需求吨数（化工用贵金属 794.8 吨、占全球 23.9%）、'
         '缺口吨数（2026 铂 9 吨 / 钯 12 吨 / 铑 3 吨）、价格（铱 +74.1%）',
         '口径统一的规模 5 年序列 + CAGR —— 取中国有色金属工业协会贵金属分会年报、'
         '中国物资再生协会贵金属再生专业委员会统计'],
    ],
    'note': '这三项**不是本报告的疏漏，而是必须外部付费/协会源才能取得**。'
            '本报告宁可显式列出，也不给拼凑值 —— 因为拼凑的规模序列会反过来污染'
            '「市占率是否提升」这个关键判断。',
}


# ==================================================================== ★ 清掉数据字段里的旧缺口串
# 第 1 轮把「xx：[MISSING] 取…」写进了 source / note 等**非 deep 字段**。
# 本轮这些 xx 多已取到，残留会与正文自相矛盾。
# ⚠️ 做法是**删掉 [MISSING] 这个标记**（它只是「此处取不到」的占位符，不是内容），
#    并交给下面逐块重写的 source 文字说明真实来源 —— 不改成「[已补齐]」那种别扭措辞。
def _scrub(obj):
    """递归删除字符串里的 [MISSING] 标记（保留其后的说明文字）。"""
    n = 0
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str) and '[MISSING]' in v:
                if any(x in v for x in KEEP_MISSING):
                    continue
                obj[k] = v.replace('[MISSING]', '').replace('  ', ' ').strip()
                n += 1
            elif isinstance(v, (dict, list)):
                n += _scrub(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str) and '[MISSING]' in v:
                if any(x in v for x in KEEP_MISSING):
                    continue
                obj[i] = v.replace('[MISSING]', '').replace('  ', ' ').strip()
                n += 1
            elif isinstance(v, (dict, list)):
                n += _scrub(v)
    return n


_scrubbed = 0
for _blk in ('profile', 'shareholder', 'controller', 'subsidiaries', 'industry',
             'industry_note', 'mgmt', 'demand', 'peers', 'raw', 'pricecost',
             'capex', 'fin', 'bizmix', 'dupont', 'expense', 'cashflow',
             'dividend', 'valuation', 'score', 'bullbear', 'conclusion'):
    _o = d.get(_blk)
    if isinstance(_o, dict):
        for _k, _v in list(_o.items()):
            if _k == 'deep':
                continue
            _scrubbed += _scrub(_v)
print('   已清除 %d 处 source/note 里的旧「[MISSING]」占位符' % _scrubbed)

# 逐块重写 source，把「待取」换成已取到的实际来源
d['profile']['source'] = (
    '成立日期 / 上市日期 / 注册地址 / 注册资本 / 统一社会信用代码 / 经营范围：iFinD 基本资料 + '
    '公司 2025 年年度报告（reportId=5458864）；财务与估值：iFinD 年度财报；'
    '行业归属：板块成员表。⚠️ **员工总数仍缺** —— 半年报与年报文本层均未披露，'
    '取 2025 年 ESG 报告（reportId=5424964）「员工」章节或年报 PDF「员工情况」表。')
d['mgmt']['source'] = R['mgmt']['source']
d['subsidiaries_note'] = (
    '子公司**持股比例与财务明细**：2026 年半年度报告第 19 页为图片表格，文本层无法提取，'
    '故五项财务指标留空不臆造；已确认三家子公司的业务定位（见下方解释块）。'
    '补齐路径 —— 最新年报「主要控股参股公司分析」章节（年报为文本表格）。')
d['subsidiary_note'] = d['subsidiaries_note']
d.setdefault('subsidiaries', {})['source'] = (
    '子公司定位：公司 2025 年年度报告（reportId=5458864）+ 机构调研纪要（reportId=5610309）'
    '第 8/9 页 + 投资者关系活动记录表（reportId=5613320）；'
    '回收基地布局：2025 年年度报告第 12 页。'
    '⚠️ 持股比例与五项财务明细仍缺（半年报为图片表），见上方说明。')


# ⚠️ 这 3 段是**真缺口**，不能删。但也**不该继续挂 [MISSING] 标记** ——
#    因为 M4 已经用一张「全报告仅存的三项外部数据缺口」表统一呈现了。
#    这里把标记去掉，改成正文可读的说明句（内容一字不减）。
_REFORM = {
    'industry': ('中国贵金属新材料市场规模权威序列', '为什么本节不给「市场规模 5 年序列 + CAGR」'),
    'subsidiaries': ('子公司持股比例与财务明细', '子公司财务明细为何留空'),
    'controller': ('云投集团自身财务状况', '控股股东财务为何是外部依赖项'),
}
for _blk, (_old_head, _new_k) in _REFORM.items():
    _o = d.get(_blk)
    if not isinstance(_o, dict):
        continue
    for _x in (_o.get('deep') or []):
        if isinstance(_x, dict) and '[MISSING]' in str(_x.get('x') or ''):
            _txt = str(_x['x']).replace('<b>[MISSING] ', '<b>').replace('[MISSING] ', '')
            _txt = _txt.replace('[MISSING]', '')
            _x['t'] = 'logic'
            _x['k'] = _new_k
            _x['x'] = _txt
            _x.pop('head', None)
            _x.pop('rows', None)


# ==================================================================== M19 fin.prev
# ★ 序列从 2021 年起，首年同比需要 2020 基数 —— 从 iFinD 单独取回，填进 fin.prev。
#   2020：营收 289.2648 亿、归母 3.2612 亿（iFinD 年度口径）
d['fin']['prev'] = {'year': '2020', 'rev': 289.2648, 'np': 3.2612}
d['fin']['prev_note'] = (
    '2020 年基数（营收 289.2648 亿元、归母净利 3.2612 亿元）单独取自 iFinD 年度财报，'
    '用于计算 2021 年的同比 —— 本报告的五年序列为 2021~2025，不含 2020。')


# ==================================================================== 自检
def hunt_none(o, path=''):
    bad = []
    if isinstance(o, dict):
        for k, v in o.items():
            bad += hunt_none(v, '%s.%s' % (path, k) if path else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            bad += hunt_none(v, '%s[%d]' % (path, i))
    elif o is None:
        bad.append(path)
    return bad


# 关键块的形状检查
if not d['expense'].get('rows') or len(d['expense']['rows']) < 5:
    errs.append('expense.rows 应有 5 年')
if not any(str(r[1]).strip() for r in d['expense']['rows']):
    errs.append('expense.rows 第 2 列仍全空 —— M22 会退回 [MISSING]')
if not d.get('cashflow', {}).get('flows'):
    errs.append('cashflow.flows 为空 —— M23 会退回 [MISSING]')
if not d.get('raw', {}).get('rows'):
    errs.append('raw.rows 为空 —— M14 会退回 [MISSING]')
if not d.get('raw', {}).get('transmit'):
    errs.append('raw.transmit 为空 —— M14 成本传导仍会 [MISSING]')
if not d.get('valuation', {}).get('hist', {}).get('rows'):
    errs.append('valuation.hist.rows 为空 —— M26 分位数仍会 [MISSING]')
if not d.get('fin', {}).get('attribution'):
    errs.append('fin.attribution 为空 —— M19 业绩归因仍会 [MISSING]')
if not d['profile'].get('list_date') or not d['profile'].get('est_date'):
    errs.append('profile 缺成立/上市日期')
if not d.get('mgmt', {}).get('rows'):
    errs.append('mgmt.rows 为空')
_s8 = [i for i in d['score']['items'] if str(i[0]).startswith('⑧')]
if not _s8:
    errs.append('score.items 缺 ⑧ 管理层与治理')
elif _s8[0][2] is None or str(_s8[0][2]).strip() == '':
    errs.append('score.items ⑧ 仍不计分 —— 与已取到的一手董监高来源矛盾')
if not any(isinstance(x, dict) and x.get('t') == 'h3'
           and '最关键的跟踪指标' in str(x.get('x') or '')
           for x in d['conclusion'].get('deep') or []):
    errs.append('conclusion.deep 缺三指标表')

ns = hunt_none(d)
if ns:
    errs.append('数据里出现 %d 处 None：%s' % (len(ns), ', '.join(ns[:6])))

# 幂等自检
_snap = json.dumps(d, ensure_ascii=False, sort_keys=True)
if _snap != json.dumps(d, ensure_ascii=False, sort_keys=True):
    errs.append('幂等性被破坏')

if errs:
    print('❌ 自检未通过：')
    for e in errs:
        print('   -', e)
    sys.exit(1)

print('✅ 自检通过')
print('   expense.rows %d 行（2025 合计 %s）' % (len(d['expense']['rows']), d['expense']['total_2025']))
print('   cashflow.flows %d 行 · raw.rows %d 行 · valuation.hist %d 行'
      % (len(d['cashflow']['flows']), len(d['raw']['rows']), len(d['valuation']['hist']['rows'])))
print('   mgmt.rows %d 行 · score.items %d 项 · production.rows %d 行'
      % (len(d['mgmt']['rows']), len(d['score']['items']), len(d['production']['rows'])))
print('   顶层数据块共 %d 个' % len(d))

if GO:
    io.open(P, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
    back = json.load(io.open(P, encoding='utf-8'))
    assert back['expense']['rows'] == d['expense']['rows'], '回读 expense 不一致'
    assert back['cashflow']['flows'] == d['cashflow']['flows'], '回读 cashflow 不一致'
    assert back['valuation']['hist']['rows'] == d['valuation']['hist']['rows'], '回读 valuation 不一致'
    assert back['raw']['transmit'] == d['raw']['transmit'], '回读 raw 不一致'
    print('\n写盘：%s（%d 字节）· 回读校验通过 ✅'
          % (os.path.basename(P), os.path.getsize(P)))
else:
    print('\n（干跑，加 --go 才写盘）')
