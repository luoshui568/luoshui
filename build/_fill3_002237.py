# -*- coding: utf-8 -*-
"""_fill3_002237.py —— 恒邦股份 002237 第二轮数据补全（补齐渲染器非 deep 分支所需的结构块）

第一轮 _fill2_002237.py 把「叙述」补进了 deep（M1/M3/M4/M5/M6/M9… 的正文已经变厚），
但 report_build_v31.py 的这些模块**先读结构字段、有则渲染表格、无则回落 [MISSING]**，
而 deep 只被少数模块额外挂载。⇒ 本轮把「结构字段」本身补齐：

  M1  ← industry_name                      （细分行业归属，2 处）
  M2  ← timeline 必须 dict{nodes:[...]}     （我上轮误写成 list，故仍走 fallback，2 处）
  M3  ← shareholder.chain（字符串）         （1 处）
  M4  ← shareholder.controller / controller_type / controlling / hub_count / siblings（2 处）
  M5  ← business.segments + industry_name   （3 处）
  M6  ← capacity.rows + tech.items          （3 处，并点亮 chartCap）
  M18 ← risk.events 或 risk.events_note     （1 处）
  M28 ← volprice.rows                       （1 处，并点亮 chartPrice2）

铁律沿用：
  ① 渲染与自检分离（本脚本不调 selfcheck）
  ② 幂等：build(build(x)) == build(x)
  ③ 不编造：取不到的数写 [MISSING] 或如实说明缺口
  ④ 一次只改一处 + 改完复验

用法：
  python _fill3_002237.py          # 干跑，打印统计与自检
  python _fill3_002237.py --go     # 写回 seed/data_v31_002237.json
"""
import os, sys, json, copy

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
GO = '--go' in sys.argv
P = os.path.join(SEED, 'data_v31_002237.json')
RAW = os.path.join(SEED, '_raw_b1', 'b1_002237_fill2.json')
MISS = '[MISSING]'

D = json.load(open(P, encoding='utf-8'))
R = json.load(open(RAW, encoding='utf-8'))
errs = []


# ============================ 通用工具 ============================
def note(k, s):
    errs.append(k + ': ' + s)


def g(d, k, sub=None, default=None):
    v = d.get(k)
    if not isinstance(v, dict):
        return default
    if sub is None:
        return v
    return v.get(sub, default)


def has_marker(lst, marker):
    """只在 it['k'] 与 it['x']（h3/h4）里找 marker，避免误命中整段 JSON。"""
    for it in (lst or []):
        if not isinstance(it, dict):
            continue
        if marker in str(it.get('k') or ''):
            return True
        if it.get('t') in ('h3', 'h4') and marker in str(it.get('x') or ''):
            return True
    return False


def deep_list(d, key):
    d.setdefault(key, {})
    if not isinstance(d[key], dict):
        d[key] = {}
    d[key].setdefault('deep', [])
    if not isinstance(d[key]['deep'], list):
        d[key]['deep'] = []
    return d[key]['deep']


def scrub_none(obj, path='$', out=None):
    if out is None:
        out = []
    if obj is None:
        out.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            scrub_none(v, path + '.' + str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scrub_none(v, '%s[%d]' % (path, i), out)
    return out


# ============================ M2 时间轴：list → dict ============================
def fix_m2(d):
    """m2() 要求 timeline 是 dict 且 tl['nodes'] 非空；上轮误写成 list。"""
    tl = d.get('timeline')
    if isinstance(tl, list) and tl:
        nodes = []
        for row in tl:
            if not isinstance(row, (list, tuple)):
                continue
            if len(row) >= 3:
                # [年份, 标题, 说明] → [年份, '<b>标题</b><br>说明']
                nodes.append([str(row[0]), '<b>%s</b><br>%s' % (row[1], row[2])])
            elif len(row) == 2:
                nodes.append([str(row[0]), str(row[1])])
        d['timeline'] = {
            'en': 'COMPANY HISTORY',
            'title': '恒邦股份发展历程',
            'sub': '从烟台牟平的民营冶炼厂，到江西省国资委控股的黄金冶炼平台',
            'foot': '★ 关键分水岭：2019—2020 年江西铜业取得控制权',
            'nodes': nodes,
        }
    elif isinstance(tl, dict) and tl.get('nodes'):
        pass  # 已是正确形状
    else:
        note('M2', 'timeline 无可用数据')


# ============================ M1/M5 行业归属 ============================
def fix_industry_name(d):
    if not d.get('industry_name'):
        d['industry_name'] = '黄金（申万：贵金属 / 证监会：C32 有色金属冶炼和压延加工 — C322 贵金属冶炼）'


# ============================ M3/M4 股东结构 ============================
def fix_shareholder(d):
    sh = d.setdefault('shareholder', {})
    if not isinstance(sh, dict):
        sh = d['shareholder'] = {}
    # M3：chain 是字符串
    if not sh.get('chain'):
        sh['chain'] = ('江西省国有资产监督管理委员会 → 江西省国有资本运营控股集团有限公司 → '
                       '江西铜业集团有限公司 → 江西铜业股份有限公司（36.50%）→ 山东恒邦冶炼股份有限公司')
    # M4：controller / controller_type / controlling / hub_count / siblings
    sh.setdefault('controller', '江西省国有资产监督管理委员会')
    sh.setdefault('controller_type', '地方国资委（江西省）')
    sh.setdefault('controlling', '江西铜业股份有限公司（持股 36.50%）')
    if not sh.get('hub_count'):
        sh['hub_count'] = '见最新定期报告（本轮未取到具体户数）'
    if not sh.get('siblings'):
        sh['siblings'] = ('同一实际控制人（江西省国资委）体系内的 A 股上市公司主要为 '
                          '江西铜业（600362.SH）；江西铜业同时是本公司控股股东，'
                          '构成「母公司即产业方」的特殊结构。')
    if not sh.get('source'):
        sh['source'] = ('发现报告 reportId=5619995 第七节附注「本公司的母公司为江西铜业股份有限公司」；'
                        '第五节「重要事项 — 承诺相关方」；iFinD 股东数据。')
    # M4 的 gaps 表：把真缺口集中列一次，替代散落 [MISSING]
    ct = d.setdefault('controller', {})
    if 'gaps' not in ct:
        ct['gaps'] = {
            'title': '外部数据缺口（本轮未取到，不填估算值）',
            'head': ['缺口字段', '已确认部分', '待取路径'],
            'rows': [
                ['股东户数（户）', '未取到', '最新定期报告「股东情况」章节 / iFinD 股东数据'],
                ['前十大股东完整名单及各自持股比例', '仅确认控股股东江铜股份 36.50%',
                 '最新定期报告「前十大股东持股情况」表'],
                ['集团是否提供订单 / 原料 / 融资担保（金额）', '定性上原料渠道与套保体系由江铜背书',
                 '年报「关联交易」附注（采购与销售金额）'],
                ['江铜体系内其他同类资产（同业竞争范围）', '石坞金矿 42.24% 矿权、江西黄金 60% 股权为承诺注入标的',
                 '江铜《关于避免同业竞争的承诺函》原文 / 年报「承诺事项」附注'],
            ],
            'note': ('**这些都是「可核实但本轮未取到」的字段，因此留空而不填估算值。**'
                     '理由：①股东户数与前十大名单属于时点快照，用上一年数据会造成口径错误；'
                     '②关联交易金额直接决定「股东协同」是真实收益还是叙事；'
                     '③同业竞争范围决定了石坞金矿注入是否还有更多标的。'
                     '⇒ 三者都会实质影响对恒邦「产业链地位」的判断，用猜测值会把结论带偏。'),
        }


# ============================ M5 业务与产品 ============================
def fix_business(d):
    """m5() 读 business.segments。

    ⚠️ 行必须是 **5 列**：[板块, 收入(亿), 毛利率(%), 定位标签, 产品与定位]。
       len<5 时 m5 走 else 分支把第 2、3 列直接写成 [MISSING]（本次踩过）。
       与 600459 的 business.segments 保持同构。
    """
    # ★ 修复：若已写入的是旧的 4 列格式（m5 会当成缺数），就地补成 5 列。
    bu = d.get('business')
    if isinstance(bu, dict) and isinstance(bu.get('segments'), list):
        fixed = []
        for s in bu['segments']:
            if isinstance(s, (list, tuple)) and len(s) == 4:
                fixed.append([s[0], s[1], s[2], '—', s[3]])
            else:
                fixed.append(list(s))
        bu['segments'] = fixed
        return
    if isinstance(bu, dict) and bu.get('segments'):
        return
    d['business'] = {
        'segments': [
            ['黄金（标准金锭）', 712.60, 1.80, '营收主体',
             '上海黄金交易所 T+D 平台销售；原料绝大部分外购，加工费为唯一稳定利润来源'],
            ['白银', 186.40, 12.50, '副产收益核心',
             '长单合同 + 按合同点价，提货前预付全款；预收模式对现金流正面'],
            ['电解铜 / 铅等有色金属', 148.30, 2.10, '规模基础',
             '按长江有色网 / 上海有色网报价，本地销售或上海点价，贸易商自行套保'],
            ['硫酸及化工副产品', 42.70, 81.57, '★ 本期利润弹性来源',
             '2026H1 毛利率 81.57%（同比 +34.48pct）；受易制毒化学品管制，销售须办证报备'],
            ['稀散金属（砷、锑、铋等）', 33.94, '(未单独披露)', '技术溢价试验田',
             '精三氧化二砷—金属砷—高纯砷产业链；「全球砷治理的恒邦模式」'],
        ],
        'products': ('核心产品为标准金锭（Au99.99/99.95）、标准银锭、电解铜、硫酸及砷系高纯材料。'
                     '黄金以冶炼加工为主，产品同质化程度高、对上金所无议价空间。'),
        'markets': ('海外采购网络：恒邦国际商贸、恒邦拉美，并在秘鲁、赞比亚设子公司与办事处；'
                    '2026H1 进口原料产金 77.080 吨（+4.62%），是行业减产背景下公司维持产量的关键。'),
        'source': '发现报告 reportId=5619995 第三节「经营模式」四小段、「核心竞争力分析」、'
                  '财务报告附注「营业收入构成」；2026 年半年度报告分产品毛利率数据。',
    }


# ============================ M6 产能与技术 ============================
def fix_capacity(d):
    """m6() 读 capacity.rows，行格式 [年份, 设计产能, 实际产量, 产能利用率]；点亮 chartCap。"""
    if g(d, 'capacity', 'rows'):
        return
    d['capacity'] = {
        'head': ['品种', '年产能', '2026H1 产量', '年化产能利用率', '说明'],
        'rows': [
            ['黄金', '109.817 吨', '37.51 吨', '68.31%',
             '4 套火法冶金系统；原料外购为主，利用率受原料可得性约束'],
            ['白银', '1,200 吨', '562.59 吨', '93.77%',
             '接近满产，副产收益主要来源之一'],
            ['电解铜', '33.5 万吨', '12.58 万吨', '75.10%',
             '按长江有色网报价销售，贸易商自行套保'],
            ['硫酸', '168 万吨', '80.30 万吨', '95.60%',
             '★ 2026H1 毛利率 81.57%（+34.48pct），本期利润核心贡献品种'],
        ],
        'overview': ('恒邦的产能在冶炼端已基本建成（4 套火法冶金系统全部投产），'
                     '黄金年产能 109.817 吨、白银 1,200 吨、电解铜 33.5 万吨、硫酸 168 万吨。'
                     '⇒ 增长的上限不在冶炼产能，而在①原料可得性 ②副产价差 ③自有矿山放量 —— '
                     '其中①②是年度变量，③是 2027 年后才有可能的长期变量。'),
        'note': ('**读产能表要区分「冶炼产能」与「资源产能」两件事。**'
                 '①冶炼端：黄金年化利用率 68.31% —— 说明产能未打满，瓶颈是原料而不是设备；'
                 '②白银 93.77%、硫酸 95.60% —— 已接近物理满产，这两项没有增量空间；'
                 '③资源端：自产金资源储量 150.10 吨，相对 109.817 吨年产能仅够约 1.4 年，'
                 '且辽上金矿进度约 21.45%（计划 2027 年底投产）。'
                 '⇒ 结论：**中短期不存在「产能放量驱动利润」的路径**，'
                 '利润弹性只能来自副产价差与加工费，这与 M14/M15 的结论一致。'),
        'source': '发现报告 reportId=5619995 第三节「核心竞争力分析 — 规模优势」、'
                  '「经营模式 — 生产」；2026 年半年度报告主要产品产量数据。',
    }


def fix_tech(d):
    """m6() 读 tech.items，行格式 [壁垒维度, 公司现状, 强度]。"""
    if g(d, 'tech', 'items'):
        return
    d['tech'] = {
        'items': [
            ['核心工艺自主性', '造锍捕金为核心工艺，自研；突破骤冷干法收砷技术，'
                            '建成精三氧化二砷—金属砷—高纯砷生产线，被行业称为「全球砷治理的恒邦模式」', '强'],
            ['关键配方 / 牌号', '复杂金精矿、含金银伴生有色金属精矿处理能力；多元素综合回收率高',
                           '中偏强'],
            ['标准制定参与度', '参与制修订标准 169 项（国际 1 / 国家 39 / 行业 116 / 团体 14）；'
                          '获国家科技进步二等奖 2 项、省部级一等奖 12 项', '中'],
            ['客户切换成本（认证周期）', '黄金产品售至上金所 T+D 平台，标准化交割、无品牌认证壁垒；'
                                '硫酸受易制毒化学品管制，资质门槛反而是壁垒', '弱—中'],
            ['技术→毛利转化', '★ 169 项标准与 2 项国家科技进步二等奖并未转化为毛利率：'
                          '毛利率 2021 年 5.03% 单调降至 2025 年 2.03%', '弱'],
        ],
        'note': ('**技术壁垒的判读必须落到「是否转化为超额回报」这一判据上。**'
                 '恒邦的技术实力是一手可证的（169 项标准、国家级奖项、独创砷治理工艺），'
                 '但它服务的是「把复杂矿处理干净」这一进料端能力 —— '
                 '在原料外购、产品售至上金所的定价结构下，'
                 '**这部分技术溢价被上游矿主与下游交易所两头分走**，'
                 '所以技术强 ≠ 毛利率高。⇒ 这是 M11 护城河结论的技术侧证据。'),
        'source': '发现报告 reportId=5619995 第三节「核心竞争力分析」1.技术优势 / '
                  '2.资源综合利用优势；iFinD 财务指标（毛利率五年序列）。',
    }


# ============================ M18 风险事件 ============================
def fix_risk(d):
    rk = d.setdefault('risk', {})
    if not isinstance(rk, dict):
        rk = d['risk'] = {}
    if rk.get('events') or rk.get('events_note'):
        return
    rk['events'] = [
        ['2024-04', '山东证监局对控股股东江西铜业出具〔2024〕35 号责令改正决定',
         '行政监管措施', '涉同业竞争承诺超期未履行；至今（2026H1）石坞金矿矿权与江西黄金股权仍未交割'],
        ['2026H1', '减持万国黄金 4,312 万股，确认投资收益 3.45 亿元（含于山东恒邦矿业净利 +559.91% 中）',
         '非经常性损益', '★ 一次性收益，剔除后经营性利润为负 —— 不可外推至未来年度'],
        ['2026Q1', '计提存货跌价准备 6.24 亿元',
         '资产减值', '金价高位震荡期的原料库存价格敞口体现；公司已用期货/T+D/期权套保但仍有敞口'],
        ['2025 年度', '经营性现金流 -20.05 亿元（营收 1,123.94 亿）',
         '现金流风险', '存货与预付原料款占款激增；价格上行期反而消耗现金，属模式性问题'],
        ['2025-12', '取得高新技术企业证书（有效期 2025—2027）',
         '正面事项（税收）', '减按 15% 征收企业所得税，到期前需重新认定'],
        ['长期', '原料绝大部分外购、加工费定价权不在自己手上',
         '结构性风险', '毛利率五年单调下行 5.03%→2.03%；ROIC 3.52% 低于 WACC 7.0%'],
        ['待履行', '石坞金矿 42.24% 矿权 + 江西黄金 60% 股权的受让承诺',
         '承诺履行不确定性', '自 2024-10-11 转让函起已超两年未完成交割，且曾引发监管介入'],
    ]
    rk.setdefault('note', ('**风险矩阵里「概率 / 影响」为研判打分（非披露值），'
                           '「已发生风险事件」为公开可查的一手记录。**'
                           '本公司的风险特征与贵研、宝钛不同之处在于：'
                           '它的高风险项集中在「结构性低毛利 + 现金占用」而非行业景气，'
                           '且已发生的存货跌价（6.24 亿）与负经营现金流（-20.05 亿）'
                           '已经把这一风险实证化，不是假设。'))
    rk.setdefault('source', ('发现报告 reportId=5619995 2026 年半年度报告「重要事项」'
                             '（承诺履行、非经常性损益）；2026 年一季报存货跌价准备；'
                             '山东证监局〔2024〕35 号决定；iFinD 财务指标；风险概率/影响为本模型研判。'))


# ============================ M28 股价表现 ============================
def fix_volprice(d):
    """m28() 读 volprice.rows，行格式 [期间, 收盘价, 成交额, 区间涨跌]；点亮 chartPrice2。"""
    vp = d.setdefault('volprice', {})
    if not isinstance(vp, dict):
        vp = d['volprice'] = {}
    if vp.get('rows'):
        return
    vh = R.get('valuation_hist') or {}
    anchors = vh.get('anchors') or vh.get('rows') or []
    rows = []
    for a in anchors:
        if isinstance(a, (list, tuple)) and len(a) >= 3:
            rows.append([str(a[0]), str(a[1]), '—', str(a[2])])
    if len(rows) < 3:
        # 用已确认的估值序列反推价格区间，而不是编造 K 线
        rows = [
            ['2021 年末', '—', '—', 'PE(TTM) 26.95x / PB 1.73x（iFinD 年末锚点）'],
            ['2022 年末', '—', '—', 'PE(TTM) 23.59x / PB 1.47x'],
            ['2023 年末', '—', '—', 'PE(TTM) 24.52x / PB 1.43x'],
            ['2024 年末', '—', '—', 'PE(TTM) 20.67x / PB 1.29x'],
            ['2025 年末', '—', '—', 'PE(TTM) 30.28x / PB 1.94x'],
            ['2026-09（现值）', '14.07 元', '—', 'PE(TTM) 20.25x / PB 1.465x'],
        ]
    vp['head'] = ['期间', '收盘价 / 估值锚点', '成交额', '区间估值变化']
    vp['rows'] = rows
    vp['span'] = '2021 年末—2026 年 9 月（估值锚点序列）'
    vp['note'] = ('**本节诚实说明：未取到日频前复权行情，因此不画 K 线，'
                  '改用「年末估值锚点序列」呈现市场定价的变化。**'
                  '可用信息：2025 年末 PE 30.28x / PB 1.94x → 2026 年 9 月 PE 20.25x / PB 1.465x，'
                  '**估值（而非盈利）在 2026 年内明显回落**；'
                  '这组变化与基本面互相印证 —— 金价高位但公司毛利率未改善，'
                  '市场因此下调了对它的估值倍数。'
                  '⚠️ 缺口：日频复权价格序列与区间涨跌幅需 iFinD 行情接口或腾讯行情，'
                  '已列入 M31 跟踪清单，**不做估算填充**。')
    vp['source'] = ('iFinD 估值快照（PE/PB/市值，时点见文首徽标）与 2021—2025 年末估值锚点序列；'
                    '日频复权行情：本轮未取到，见 M31 跟踪清单。')


# ============================ 主流程 ============================
def build(d):
    fix_m2(d)
    fix_industry_name(d)
    fix_shareholder(d)
    fix_business(d)
    fix_capacity(d)
    fix_tech(d)
    fix_risk(d)
    fix_volprice(d)
    return d


def stat(d):
    nblocks = sum(1 for v in d.values() if isinstance(v, dict) and v.get('deep'))
    nsegs = sum(len(v.get('deep') or []) for v in d.values()
                if isinstance(v, dict) and isinstance(v.get('deep'), list))
    raw = json.dumps(d, ensure_ascii=False)
    return {
        'keys': len(d),
        'deep_blocks': nblocks,
        'deep_segs': nsegs,
        'bytes': len(raw.encode('utf-8')),
        'missing': raw.count(MISS),
    }


def main():
    before = stat(D)
    d2 = build(copy.deepcopy(D))

    # 自检 1：幂等
    d3 = build(copy.deepcopy(d2))
    if json.dumps(d2, ensure_ascii=False, sort_keys=True) != json.dumps(d3, ensure_ascii=False, sort_keys=True):
        errs.append('IDEMPOTENCY: build(build(x)) != build(x)')

    # 自检 2：deep 段里不得出现 None
    bad = []
    for k, v in d2.items():
        if isinstance(v, dict) and isinstance(v.get('deep'), list):
            bad += ['%s%s' % (k, p) for p in scrub_none(v['deep'])]
    if bad:
        errs.append('NONE_IN_DEEP: %s' % bad[:10])

    # 自检 3：结构断言
    tl = d2.get('timeline')
    if not (isinstance(tl, dict) and tl.get('nodes')):
        errs.append('M2: timeline 不是 dict 或 nodes 为空')
    if not d2.get('industry_name'):
        errs.append('M1: industry_name 缺失')
    sh = d2.get('shareholder') or {}
    for f in ('chain', 'controller', 'controller_type', 'controlling'):
        if not sh.get(f):
            errs.append('M3/M4: shareholder.%s 缺失' % f)
    if not (g(d2, 'business', 'segments')):
        errs.append('M5: business.segments 缺失')
    if not (g(d2, 'capacity', 'rows')):
        errs.append('M6: capacity.rows 缺失')
    if not (g(d2, 'tech', 'items')):
        errs.append('M6: tech.items 缺失')
    rk = d2.get('risk') or {}
    if not (rk.get('events') or rk.get('events_note')):
        errs.append('M18: risk.events 缺失')
    if not (g(d2, 'volprice', 'rows')):
        errs.append('M28: volprice.rows 缺失')

    after = stat(d2)
    print('--- 干跑%s ---' % ('' if not GO else '（写回）'))
    print('前: %s' % before)
    print('后: %s' % after)
    print('delta: keys %+d / deep_blocks %+d / deep_segs %+d / bytes %+d' % (
        after['keys'] - before['keys'], after['deep_blocks'] - before['deep_blocks'],
        after['deep_segs'] - before['deep_segs'], after['bytes'] - before['bytes']))
    if errs:
        print('\n!!! 自检失败 %d 项:' % len(errs))
        for e in errs:
            print('   -', e)
        sys.exit(1)
    print('\n自检全部通过 ✅  幂等 ✅  deep 无 None ✅  结构完整 ✅')

    if GO:
        with open(P, 'w', encoding='utf-8') as f:
            json.dump(d2, f, ensure_ascii=False, indent=1)
        print('已写回 %s' % P)
    else:
        print('（干跑模式，未写文件。加 --go 写回）')


if __name__ == '__main__':
    main()
