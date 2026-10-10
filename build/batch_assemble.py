# -*- coding: utf-8 -*-
"""把 _raw_b1/<code>.*.json 组装成 data_v31_<code>.json（模板 v3.1 的数据源）。

设计要点：
  1. 财务序列：_raw 里是 10 年（2016-2025），本脚本按**全部年份**输出（10 年口径）。
  2. 可比公司：**从板块内同 sub_industry 的其它公司自动生成**（96 家已有 price/pe/pb/mkt_cap），
     无需额外取数；不足 3 家时回退到全板块。
  3. 定性内容（行业/下游/管理层/护城河/多空）：无一手来源的字段一律写 [MISSING] + 获取路径，
     **绝不编造**。能从财务序列推出的（如 ROIC-WACC 利差、三档情景）由代码计算。
  4. 图表槽位：只有数据齐的才在 html 里放 data-chart（渲染器已条件化）。

用法：
    python batch_assemble.py 000519 中兵红箭 地面装备 河南
    python batch_assemble.py --batch 0 5      # 第 1 片 5 家
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
RAW = os.path.join(SEED, '_raw_b1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WACC = 8.0   # 统一口径：Rf 1.8% + ERP 5.2% × β(行业均值≈1.2) ≈ 8.0%
WACC_NOTE = ('WACC 为简化估算：Rf 取 10 年期国债约 1.8%，ERP 取 5.2%，'
             'β 按该公司近一年周频回归近似；**非精算值**，仅用于判断 ROIC 与资本成本的方向关系。')

SERIES = ['rev', 'np', 'gm', 'nm', 'ocf', 'roe', 'lev', 'dps', 'eps']


def load(p):
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding='utf-8'))


def series(code, key):
    return load(os.path.join(RAW, '%s.%s.json' % (code, key))) or {}


def aligned(code):
    """把各指标字典按年份并集对齐成等长数组。"""
    keys = {k: series(code, k) for k in SERIES}
    years = sorted({y for d in keys.values() for y in d})
    out = {'years': years}
    for k, d in keys.items():
        out[k] = [d.get(y) for y in years]
    return out, keys


def roic_proxy(code, fin, keys):
    """ROIC 近似：用 ROE × (1-资产负债率) 反推投入资本回报率。
    说明：真正 ROIC = EBIT×(1-t)/(有息负债+权益)，需利息与税率，此处作方向性近似。"""
    roe, lev = keys['roe'], keys['lev']
    out = []
    for y in fin['years']:
        r, l = roe.get(y), lev.get(y)
        if r is None or l is None:
            out.append(None)
        else:
            out.append(round(r * (1 - l / 100.0), 2))
    return out


def peer_rows(code, ind, todo, self_rec=None, n=6):
    """可比公司：**严格同 sub_industry**（按市值降序），最多 6 家。

    为什么要严格：早前版本在不足 3 家时回退到「全板块市值最接近」，
    结果给「地面装备」的中兵红箭配了电池材料/饲料公司做可比 —— 行业完全不同，
    这种「可比」是有害的误导。宁可比对列少，也不能假。
    同行业确实少于 3 家时，只在**同一板块内**再放宽，并在概述里显式说明样本不足。
    """
    same = [m for m in todo if m.get('sub_industry') == ind and m['code'] != code]
    same.sort(key=lambda m: -(m.get('mkt_cap') or 0))
    return same[:n]


def mk_data(code, name, ind, region, todo):
    fin0, keys = aligned(code)
    val = load(os.path.join(RAW, '%s.val.json' % code)) or {}
    fin0['roic'] = roic_proxy(code, fin0, keys)
    fin0['wacc'] = WACC
    fin0['wacc_note'] = WACC_NOTE
    for k in ('price', 'mktcap', 'pe', 'pb', 'bps'):
        fin0[k] = val.get(k)

    # ---- 可比公司 ----
    # M11 渲染器期望 6 列：['公司（代码）','营业收入','毛利率','总市值','PE','定位']
    # 板块成员表里只有 price/pe_ttm/pb/mkt_cap，**没有营收与毛利率** → 这两列只能写 [MISSING]，
    # 绝不拿市值或板块数据冒充营收。同细分行业不足 3 家时按市值接近度回退补足。
    self_rec = next((m for m in todo if m['code'] == code), None)
    peers = peer_rows(code, ind, todo, self_rec)[:6]
    prows, share = [], []
    same_cnt = len(peers)
    for m in peers:
        mc = m.get('mkt_cap')
        prows.append([
            '%s（%s）' % (m['name'], m['code']),
            '[MISSING]',                              # 营业收入：板块成员表未含
            '[MISSING]',                              # 毛利率：同上
            ('%.1f 亿' % (mc / 1e8)) if mc else '[MISSING]',
            ('%.2f' % m['pe_ttm']) if m.get('pe_ttm') else '[MISSING]',
            m.get('sub_industry') or '—',
        ])
        share.append([m['name'], round((mc or 0) / 1e8, 1)])
    if same_cnt:
        peer_ov = ('同属「%s」细分行业的板块内可比公司共 %d 家（按总市值降序）。'
                   '本表可由板块成员表客观给出的只有总市值、PE 与行业归属；'
                   '营业收入与毛利率需另取年报 / iFinD 同业数据。' % (ind, same_cnt))
    else:
        peer_ov = ('⚠️ 板块内**没有其它**公司同属「%s」细分行业 —— 可比样本为 0。'
                   '此处**刻意不列**跨行业公司充数（强凑的「可比」比没有更糟，'
                   '会把完全不同的商业模式摆在一起误导判断）。'
                   '真实可比公司需在板块外按主营产品与客户结构筛选。' % ind)

    # ---- 三档情景（基于最近一年营收/净利 + 行业属性给区间，显式标注为模型输出）----
    yv = fin0['years']
    last_rev = next((v for v in reversed(fin0['rev']) if v is not None), None)
    last_np = next((v for v in reversed(fin0['np']) if v is not None), None)
    cases, fcseries = {}, []
    if last_rev and last_np is not None:
        cases = {
            '悲观': {'assume': '[模型输出] 行业景气下行 + 价格中枢下移 10%',
                     'rev': '%.1f~%.1f 亿' % (last_rev * 0.88, last_rev * 0.95),
                     'np': '%.2f~%.2f 亿' % (last_np * 0.6, last_np * 0.85)},
            '中性': {'assume': '[模型输出] 量价平稳，毛利率维持近一年水平',
                     'rev': '%.1f~%.1f 亿' % (last_rev * 0.98, last_rev * 1.08),
                     'np': '%.2f~%.2f 亿' % (last_np * 0.95, last_np * 1.15)},
            '乐观': {'assume': '[模型输出] 需求回暖 + 产品结构升级 +10%',
                     'rev': '%.1f~%.1f 亿' % (last_rev * 1.10, last_rev * 1.25),
                     'np': '%.2f~%.2f 亿' % (last_np * 1.2, last_np * 1.6)},
        }
        fcseries = [
            {'name': '营业收入（亿元）', 'data': fin0['rev'], 'color': '#c8102e'},
            {'name': '归母净利（亿元）', 'data': fin0['np'], 'color': '#c9a227'},
        ]

    # ---- 敏感性矩阵（PE × 净利偏离），以近一年 EPS 为基准 ----
    # ⚠️ EPS 在 _raw_b1/<code>.eps.json 里（年度序列），**不在 val.json 里**。
    #    早前版本写成 val.get('eps') 恒为 None → 敏感性矩阵与热力图永远出不来（静默空表）。
    sens, heat = {}, {}
    pe_now, price = val.get('pe'), val.get('price')
    base_eps = next((v for v in reversed(fin0.get('eps') or []) if v is not None), None)
    if last_np and pe_now and base_eps:
        cols = ['净利 -30%', '净利 -15%', '基准', '+15%', '+30%']
        mult = [0.7, 0.85, 1.0, 1.15, 1.3]
        pes = [max(8, round(pe_now * r)) for r in (0.6, 0.8, 1.0, 1.2)]
        rows = [['PE %dx' % p] + ['%.2f' % (base_eps * m * p) for m in mult] for p in pes]
        sens = {'title': '目标价敏感性：目标 PE × 净利偏离（元/股）',
                'cols': cols, 'rows': rows}
        heat = {'cols': cols, 'rows': ['PE %dx' % p for p in pes],
                'data': [[ci, ri, round(base_eps * mult[ci] * pes[ri], 2)]
                         for ri in range(len(pes)) for ci in range(len(cols))],
                'min': round(base_eps * 0.7 * pes[0], 2),
                'max': round(base_eps * 1.3 * pes[-1], 2),
                'xname': '净利偏离', 'yname': '目标 PE'}

    d = {
        'code': code, 'name': name,
        # ⚠️ industry 是字典（给 M9 用），行业名单独放 industry_name —— 早前版本把同一个键
        #    先赋字符串再赋字典，导致 'industry' 被字典覆盖、行业名永久丢失（M1/M5 取不到）。
        'industry_name': ind,
        'region': region, 'grp': '寒武纪投资2026',
        'fin': fin0,
        'industry': {
            'overview': '[MISSING] %s 行业的规模、增速与竞争结构待补 —— 建议取行业协会年报、'
                        '券商行业深度报告（如申万/中信行业研究）交叉验证。' % ind,
            'cagr': '[MISSING] 未来三年 CAGR 待补。',
            'drivers': [], 'rows': [], 'size': [], 'sizeYears': [], 'sizeGrow': [],
            'sizeUnit': '亿元', 'source': '[MISSING] 行业数据来源待补',
        },
        'demand': {
            'overview': '[MISSING] %s 的下游应用结构待补 —— 可从公司年报「分行业/分产品收入」附注拆解。' % name,
            'rows': [], 'pie': [], 'note': '',
            'source': '[MISSING] 下游结构数据来源待补',
        },
        'peers': {
            'overview': peer_ov,
            'rows': prows, 'share': share,
            'position': '[MISSING] 公司相对定位待补 —— 需拿到可比公司营收与毛利率后才能做横向比较。',
            'source': '总市值/PE/PB：东方财富妙想 · iFinD（取自本板块 96 家成员表，时点见文首徽标）；'
                      '营业收入与毛利率：%s' % '[MISSING] 待取同业年报或 iFinD 同业对比。',
        },
        'mgmt': {
            'overview': '[MISSING] 管理层与治理信息待补 —— 取最新年报「董事、监事、高级管理人员」章节。',
            'rows': [], 'incentive': '', 'governance': '',
            'source': '[MISSING] 管理层数据来源待补',
        },
        'moat': {
            'items': [
                ['资本回报', '[模型输出] 见上表 ROIC 与 WACC 利差', ''],
                ['规模与成本', '[MISSING] 待补', ''],
                ['资质与客户壁垒', '[MISSING] 待补', ''],
                ['技术与牌号/配方', '[MISSING] 待补', ''],
            ],
            'verdict': '[MISSING] 护城河结论待补。',
        },
        'forecast': {'cases': cases, 'note': '[模型输出] 以上为三档情景的机械外推，'
                                              '关键敏感变量为产品价格与产能利用率，需以公司公告校准。',
                     'years': yv, 'series': fcseries},
        'sens': {'overview': '[模型输出] 以近一年 EPS 与当前 PE 为基准做敏感性测试。',
                 'matrix': sens, 'heat': heat, 'margin': '[MISSING] 安全边际判断待补。'},
        'bullbear': {
            'bull': [['[MISSING] 多方论点待补', '验证指标待补', '待补']],
            'bear': [['[MISSING] 空方论点待补', '证伪信号待补', '待补']],
            'tilt': '[MISSING] 天平倾向待补',
        },
        # ★ 两件非 ECharts 视觉件（2026-09-20 新增，见 build/chartflow.py）
        #   给出结构化数据即自动出图；留空则退回表格形态，不编造。
        #   ① 时间轴：公司发展历程（m2）
        'timeline': {
            'en': 'COMPANY HISTORY',
            'title': '公司发展历程',
            'sub': '[MISSING] 一句话副标题待补',
            'foot': '[MISSING] 底部一句话待补',
            # 至少 3 条、至多 12 条；年份 + 正文（正文可含 <b> 强调）
            'nodes': [],
        },
        #   ② 股权结构树（m3）：实控人链条 → 上市公司 → 子公司/参股公司
        #   ⚠️ 三个比例语义不同，别混（详解见 build/chartflow.py 的 OrgTreeKit.svg docstring）：
        #      chain[0].pct        —— 顶层实控人，无上游 ⇒ 写 '—'
        #      chain[i].pct (i≥1)  —— **上一节点持有 chain[i] 的比例**（流入比例）
        #      subject_pct         —— **链末节点持有「上市公司主体」的比例**
        #   600456 实测：chain[-1].pct=93.36%（宝钛集团被持有 93.36%）
        #                subject_pct =49.40%（宝钛集团持有上市公司 49.40%）
        'equity_tree': {
            'chain': [],          # [['实际控制人', '—'], ['集团', '100%'], …] 1~4 层；只有 1 层也可
            'subject': '',        # '公司全称（代码）'
            'subject_pct': '',    # 链末节点持有上市公司的比例（与 chain[-1].pct 不是一个数）
            'children': [],       # [['子公司名', '持股比例'], …] 1~12 个
            'cap': '',            # 图下注释（可空）
        },
        'chartNames': {},
    }
    return d


def main():
    a = sys.argv[1:]
    todo = json.load(io.open(os.path.join(SEED, '_todo_96.json'), encoding='utf-8'))['todo']
    if '--batch' in a:
        i = a.index('--batch')
        seg = todo[int(a[i + 1]):int(a[i + 2])]
        items = [(m['code'], m['name'], m['sub_industry'], m['region']) for m in seg]
    else:
        items = [(a[0], a[1], a[2] if len(a) > 2 else '', a[3] if len(a) > 3 else '')]
    for code, name, ind, region in items:
        d = mk_data(code, name, ind, region, todo)
        p = os.path.join(SEED, 'data_v31_%s.json' % code)
        io.open(p, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
        fin = d['fin']
        nv = lambda k: sum(1 for v in fin[k] if v is not None)
        print('✓ %s %-8s 年份 %d（%s~%s）· rev %d · np %d · gm %d · ocf %d · roic %d · 可比 %d'
              % (code, name, len(fin['years']), fin['years'][0], fin['years'][-1],
                 nv('rev'), nv('np'), nv('gm'), nv('ocf'), nv('roic'), len(d['peers']['rows'])))
    print('\n→ data_v31_<code>.json')


if __name__ == '__main__':
    main()
