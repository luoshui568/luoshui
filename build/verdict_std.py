# -*- coding: utf-8 -*-
"""核心结论版式重做（2026-10-14 用户令）。

用户口径：「核心结论看起来很乱，所有的文字一定要注意排版，要一眼看上去
就很舒服，把所有文字系列排版重做，要求样式要好」。

★ 病根（截图里的齐翔腾达最典型）：11 份研报的 `verdict_html` 都是**一大坨
  连续文本** —— 785 个字、行高不到 1.6、②③ 序号内嵌在长句中间、HTML 里
  还残留 `**加粗**`（页面根本不渲染，直接显示星号）。模板 `renderVerdict()`
  又把它塞进一个横向 flex（标题在左、正文在右），长文只能挤成一条窄柱。

★ 做法：**不改一个字，只重排**。把原文按语义切成层级块，用一套语义类承载：
    .vlead  导语（一句话本质）      —— 浅金底 + 左金条，字号最大
    .vkey   中性强调（核心矛盾/本报告的判读/关键变量）
    .vlist  分点（原文的 ①②③ 拆成独立行，序号交给 CSS 计数器）
    .vrisk  风险块（浅红底 + 红左条）
    .vtrack 核心跟踪（虚线框，压在末尾）
  CSS 见 build/report_theme.css 的「核心结论（2026-10-14 版式重做）」段。

★ 铁律：**正文一字不改**。脚本自带「文字零丢失」断言 —— 把新旧 HTML 都
  去掉标签、`**`、①②③ 序号、⚠ 符号与全部空白后逐字比对，不等就拒绝写库
  并打印差异片段。宁可报错，也不接受把某句话漏掉或改写。

★ 为什么要连 seed 一起改：`report_build_v31.py` 里
  `verdict_html = shell.get('verdict') or (默认模板)`，**只要 seed 没有
  shell.verdict 就会走默认模板**。000731/000830/002237/600456/600459 这五份
  的 seed 原来就没有 shell（直接吃默认），所以本脚本会给它们补上，
  否则下次 push_reports_v31.py 会把这里的排版整段刷回默认版。

用法：
    python3 build/verdict_std.py --dry      # 只校验（文字零丢失 + 幂等）
    python3 build/verdict_std.py            # 写库 + 同步 seed
    python3 build/verdict_std.py --check    # 从库里回读校验
    python3 build/verdict_std.py --no-seed  # 只写库、不动 seed
"""
import difflib
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'],
       'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}
SEEDDIR = os.path.join(HERE, 'seed')

# ======================================================================
# 新版核心结论正文
# ======================================================================
NEW = {}

# ---------------------------------------------------------------- 000731 四川美丰
NEW['000731'] = (
    '<p class="vlead">小市值 + 底部形态驱动股价，但基本面尚未见拐点：</p>'
    '<p>2026H1 营收 <strong>18.91 亿元（+1.72%）</strong>止住跌势，但归母净利 '
    '<strong>-5,345 万元</strong>（上年同期盈利 803 万元）、扣非净利 '
    '<strong>-6,193 万元</strong>，加权 ROE -1.40%；2025 年已亏损 1.22 亿元，'
    '<strong>连续两年未实现盈利</strong>。</p>'
    '<p>核心矛盾在于<strong>产品价格降幅持续超过成本降幅</strong>：销售毛利率由 2021 年的 '
    '29.88% 降至 2025 年的 <strong>8.25%</strong>，尿素单位价差从 2022 年的 1040 元/吨'
    '压缩至 2025 年的 79 元/吨（-92%）。</p>'
    '<p>公司无新增产能规划，成长弹性主要来自车用尿素（单位价差 284 元/吨，为最厚品种）'
    '与 LNG 贸易价差。</p>'
    '<p>当前 PB 1.07 倍、总市值 40.83 亿元，PE(TTM) 为负值不适用；按十项加权得分 '
    '69.9/100（底稿 70 分、评级「推荐」），本文标注「观察」。</p>'
    '<div class="vrisk"><div class="vh">需注意：</div>'
    '<p>现价 7.44 元已较底稿价格 5.28 元上涨约 41%，且高于底稿买入区间 4.8-5 元，'
    '近 60 日涨幅 35.77%，短期上涨主要由低市值与低股价的博弈属性驱动，而非盈利改善。</p></div>'
    '<div class="vtrack"><span class="vk">核心跟踪：</span>'
    '<span>Q3 是否减亏/扭亏、化肥价格、天然气价差、经营现金流。</span></div>'
)

# ---------------------------------------------------------------- 000830 鲁西化工
NEW['000830'] = (
    '<p class="vlead">周期底部改善，但安全边际弱于底稿：</p>'
    '<p>2026H1 营收 153.52 亿元（+4.16%）、归母净利 9.75 亿元（+27.64%）、'
    '<strong>扣非净利 9.22 亿元（+34.24%）</strong>，毛利率 14.76%（同比 +1.84pct）、'
    '净利率 6.35%（+1.16pct）；Q2 单季归母净利 5.37 亿元（同比 +53.05%、环比 +22.51%），'
    '<strong>盈利改善在二季度加速</strong>。</p>'
    '<p>增长来源是<strong>己内酰胺·尼龙 6 一期产能释放带来的销量增长</strong>'
    '与产品价格同比回升，而非涨价驱动。</p>'
    '<p>但公司仍面临三重约束：</p>'
    '<ul class="vlist">'
    '<li>归母净利较 2021 年高点 46.19 亿元下滑约 80%，ROE 仅 5.01%；</li>'
    '<li>聚酰胺、聚碳酸酯两大新材料子公司 2025 年分别亏损 5.69 / 1.5 亿元；</li>'
    '<li>2023 年「5·1」双氧水重大事故（10 人死亡）后，园区安全已成为长期治理折价项。</li>'
    '</ul>'
    '<p>当前 PE(TTM) 20.48 倍、PB 1.17 倍处于历史中低位，按十项加权得分 65.6/100'
    '（底稿换算 65 分、评级「推荐」），本文标注「观察」。</p>'
    '<div class="vrisk"><div class="vh">需特别注意：</div>'
    '<p>现价 12.02 元已高于底稿买入区间 10-11 元，年内股价回撤 26.57%。</p></div>'
    '<div class="vtrack"><span class="vk">核心跟踪：</span>'
    '<span>己内酰胺-纯苯价差、有机硅装置达产、在建工程转固节奏、出口延续性。</span></div>'
)

# ---------------------------------------------------------------- 002237 恒邦股份
NEW['002237'] = (
    '<p class="vlead">恒邦股份（002237）是一家「通道型」贵金属冶炼企业 —— '
    '江西铜业控股、江西省国资委实控，主营黄金冶炼'
    '（黄金 109.82 吨 / 白银 1,200 吨 / 电解铜 33.5 万吨产能）。</p>'
    '<p>2025 年营业收入 <strong>1,123.94 亿元</strong>（+48.28%）、归母净利 '
    '<strong>6.38 亿元</strong>（+18.80%），营收规模居可比四家之首，但'
    '<strong>毛利率仅 2.03%、净利率 0.55%</strong>。</p>'
    '<div class="vkey"><div class="vh">核心矛盾是：</div>'
    '<p>它的收入随金价放大，利润却由加工费决定。原料以外购金精矿为主'
    '（自产金备案储量仅 150.10 吨），金价上行只抬高收入基数、并把毛利率被动摊薄 —— '
    '毛利率 2021 年 5.03% → 2025 年 2.03% 单调下行，所以「营收创新高」对恒邦'
    '几乎不含正面信息。</p></div>'
    '<p><strong>护城河不可量化</strong>：ROIC 从 4.24% 降至 3.52%，连续五年低于 7.0% '
    '的资本成本假设，本质是一家赚加工费的通道型企业。</p>'
    '<div class="vrisk"><div class="vh">2026 年的利润质量更需警惕：</div>'
    '<p>Q1 归母净利 1.82 亿元中含减持万国黄金一次性投资收益 3.45 亿元，'
    '剔除后主营实际亏损，同期计提存货跌价 6.24 亿元；2025 年经营现金流 −20.05 亿元、'
    '净现比 −3.14，资产负债率升至 64.00%。</p></div>'
    '<div class="vkey">'
    '<p><strong>唯一能实质改变结论的变量是石坞金矿注入</strong>（承诺已超两年未交割）—— '
    '它是把恒邦从「加工型」重估为「资源型」的唯一路径，'
    '同时改变资源禀赋与同业竞争。</p></div>'
    '<div class="vtrack"><span class="vk">核心跟踪：</span>'
    '<span>石坞金矿交割进度、毛利率能否连续两期站稳 2.4% 以上、经营现金流与存货跌价。</span></div>'
)

# ---------------------------------------------------------------- 002408 齐翔腾达
NEW['002408'] = (
    '<p class="vlead">齐翔腾达是一家「装置规模世界第一、但定价权不在自己手里」的'
    '碳四深加工龙头；它现在的问题不是「能不能赚钱」，而是「这一轮价差能维持多久」。</p>'
    '<p>公司 2025 年营收 237.70 亿元（−5.75%）、归母净利亏损 '
    '<strong>5.75 亿元</strong>（−1767.51%），是上市以来最大年度亏损；毛利率压到 '
    '<strong>3.21%</strong>、低于四项费用率合计的 5.55%，亏损在算术上几乎无法避免。</p>'
    '<p>但 <strong>2026 年上半年出现了明确的拐点，而且集中在一个季度之内</strong>：</p>'
    '<ul class="vlist">'
    '<li>2026Q1 仍亏 0.92 亿元，'
    '<strong>Q2 单季归母净利 2.08 亿元（单季同比 +1072%）</strong>；</li>'
    '<li>2026H1 营收 <strong>156.30 亿元（+28.03%）</strong>、归母 '
    '<strong>1.16 亿元（+402.83%）</strong>；</li>'
    '<li>毛利率从 3.21% 回到 <strong>5.71%</strong>，ROE 由 −5.03% 回到 +1.05%。</li>'
    '</ul>'
    '<p><strong>驱动这一切的不是销量（2025 年销量还在 +2.39%），而是价差：'
    '甲乙酮华东均价 2026-04 冲到 12,559.52 元/吨（较年初 +99.2%）、'
    '顺酐华东均价 2026-03 跳到 7,402.16 元/吨（较 2025-12 +53.6%）。</strong></p>'
    '<div class="vrisk"><div class="vh">风险同样明确：</div><ol>'
    '<li>顺酐行业有效产能已从 2021 年的 140 万吨/年冲到 350 万吨/年以上，'
    '2025 年产能利用率仅约 44.78%~70%（口径差异见第 26 槽），'
    '2026 年新增产能释放只是「放缓」而非「停止」；</li>'
    '<li>全部债务 117.45 亿元、资产负债率 52.35%~56.63%，'
    '财务费用本身就是一个随利率浮动的变量；</li>'
    '<li>现价 PE(TTM) 为负（−31.79 倍），静态 PE 也为负，'
    '任何用估值倍数做的判断在当前年报口径下都失效。</li>'
    '</ol></div>'
)

# ---------------------------------------------------------------- 600392 盛和资源
NEW['600392'] = (
    '<p class="vlead"><strong>盛和资源（600392）</strong>是国内稀土行业独具特色的'
    '<strong>混合所有制上市公司</strong>（细分行业：小金属/稀土），'
    '大股东为中国地质科学院矿产综合利用研究所，实际控制人为财政部。</p>'
    '<p>2025 年营业收入 <strong>149.91 亿元</strong>、归母净利 '
    '<strong>8.39 亿元（同比 +304.94%）</strong>；2026 年上半年营收 '
    '<strong>87.59 亿元（+41.76%）</strong>、归母净利 '
    '<strong>8.87 亿元（+135.24%）</strong>，半年度净利已超 2025 年全年。</p>'
    '<div class="vkey"><div class="vh">核心矛盾：</div>'
    '<p>公司具备「轻重稀土兼营 + 控股海外世界级稀土矿 + 锆钛多金属」的稀缺布局，'
    '但近五年 ROIC（2025 年 5.31%）仍低于 7.5% 的 WACC 假设 —— '
    '护城河已具雏形，兑现路径（恩古拉投产后的原料自给）尚未走完。</p></div>'
)

# ---------------------------------------------------------------- 600456 宝钛股份
NEW['600456'] = (
    # ★ 原文这两处用的是 ASCII 直引号 "…"，全站其它研报一律是「…」——
    #   排版一致性上不好看（字宽、字重都跟中文引号对不上），一并换掉。
    '<p class="vlead">中期<strong>条件性偏多</strong>：买宝钛股份本质是买'
    '<strong>「航空航天钛材需求放量 + 产能扩张兑现后的利润弹性」</strong>。</p>'
    '<p>公司是中国钛工业第一股，国企控股（陕西省国资委→陕西有色→宝钛集团49.40%），'
    '拥有海绵钛到加工材的全产业链一体化布局，2023年钛加工材产量占全国约24%。</p>'
    '<p>2026年发行35亿可转债推进三大扩能项目（熔铸+锻造+近净成形），'
    '达产后预计年增利润/节约成本5.83亿元。</p>'
    '<p>但<strong>2025年营收61.2亿（-8.1%）、归母4.0亿（-31%）</strong>，'
    '当前PE 34倍偏贵；盈利修复依赖航空航天需求景气与产能达产进度。</p>'
    '<div class="vtrack">'
    '<span>评分70.5/100，评级「观察」；买入价17-19元，目标价40元，盈利空间约120%。</span></div>'
)

# ---------------------------------------------------------------- 600459 贵研铂业
NEW['600459'] = (
    '<p class="vlead"><strong>贵研铂业（600459）</strong>是国内贵金属新材料领域'
    '不可替代的龙头（2025 年国内第一、全球第五，铂族金属回收市占率 30%+），但'
    '<strong>它的规模扩张长期靠垫资与加杠杆驱动</strong>：</p>'
    '<p>2025 年营业收入 <strong>556.75 亿元</strong>（+17.20%）、归母净利 '
    '<strong>6.41 亿元</strong>（+10.54%），营收是可比公司的 6~27 倍，毛利率却只有 '
    '<strong>2.63%</strong>（四家可比中最低）—— 约七成收入来自'
    '「回收冶炼 + 供给服务」这类赚加工费或贸易价差的低毛利业务。</p>'
    '<p>ROIC 从 6.83%（2021）降至 5.45%（2025），'
    '<strong>连续五年低于 7.3% 的资本成本假设</strong>，技术领先尚未转化为定价权。</p>'
    '<p>2026H1 出现第一个反向信号：<strong>主动砍掉低毛利贸易后营收 −23.36%，'
    '归母净利反而 +7.63%、毛利率翻倍至 4.43%</strong>，'
    '且扣非增速（+12.75%）高于净利增速，说明改善来自主营结构而非一次性损益。</p>'
    '<div class="vkey"><div class="vh">因此当前的投资逻辑只有一条主线：</div>'
    '<p><strong>以毛利率为唯一锚点，验证「技术领先能否转化为定价权」</strong>，'
    '需要连续两个报告期站稳 4%。</p></div>'
    '<div class="vtrack"><span class="vk">核心跟踪：</span>'
    '<span>整体毛利率能否守住 4%、47 项贵研精品加工费同比（2026H1 +12.52%）、'
    '经营现金流（2026H1 +7.17 亿元）与财务费用增速（+149.23%）。</span></div>'
)

# ---------------------------------------------------------------- 601118 海南橡胶
NEW['601118'] = (
    '<p class="vlead"><strong>海南橡胶（601118）</strong>是海南省农垦投资控股集团持股 '
    '<strong>64.35%</strong> 的国有上市平台，也是'
    '<strong>中国资本市场唯一的天然橡胶全产业链上市公司</strong>。</p>'
    '<p>2025 年营业收入 <strong>422.37 亿元</strong>（同比 +0.55%）、利润总额 '
    '<strong>−1.29 亿元</strong>、归母净利 <strong>−1.0303 亿元</strong>'
    '（同比 −199.65%）。</p>'
    '<div class="vkey"><div class="vh">本报告的判读是：</div>'
    '<p><strong>这是一家「资源属性极强、盈利能力极弱」的公司，'
    '两者的落差就是它全部的投资特征</strong>。</p></div>'
    '<p><strong>资源端</strong>：截至 2025 年末，公司在全球经营管理土地 '
    '<strong>490 万亩</strong>、其中胶园土地 <strong>380 万亩</strong>，'
    '境内外天然橡胶种植基地 30 家、在产橡胶初加工厂 61 家，年加工产能约 235 万吨、'
    '年销售贸易量 337 万吨（约占全球消费量的 25%）。</p>'
    '<p><strong>盈利端</strong>：五年毛利率从未超过 4.15%、ROIC 有四年低于 2.3%'
    '（另一年为负）、资产负债率从 49.96% 升至 70.29%、2025 年由盈转亏。</p>'
    '<p><strong>两句话必须同时成立，才能理解这家公司</strong>：</p>'
    '<ul class="vlist">'
    '<li><strong>它的收入规模是「贸易量」撑起来的，不是「自产胶」</strong>'
    '（2025 年自产橡胶仅 10.42 万吨、同比 −14.1%）；</li>'
    '<li><strong>它的估值锚不在利润表，而在 380 万亩胶园与 490 万亩经营土地</strong>'
    '（当前 PB 约 2.7 倍，而五年 ROE 平均不足 1.5%）。</li>'
    '</ul>'
)

# ---------------------------------------------------------------- 601958 金钼股份
NEW['601958'] = (
    '<p class="vlead"><strong>金钼股份（601958）</strong>是陕西省国资体系下、'
    '由金堆城钼业集团持股 <strong>72.36%</strong> 的国有矿业公司，也是 '
    '<strong>A 股首家钼产业上市公司</strong>与全球钼行业最具影响力的钼专业供应商之一。</p>'
    '<p>2025 年营业收入 <strong>138.34 亿元</strong>（同比 +1.94%）、利润总额 '
    '<strong>41.12 亿元</strong>、归母净利 <strong>31.55 亿元</strong>（同比 +5.77%），'
    '<strong>创上市以来最好水平</strong>。</p>'
    '<div class="vkey"><div class="vh">本报告的判读是：</div>'
    '<p><strong>这是一家「资源自给率 100%、资产结构极度干净、'
    '但盈利完全由钼价决定」的资源型公司</strong>。</p></div>'
    '<p><strong>资源端</strong>：自有矿山包括世界六大原生钼矿床之一的'
    '<strong>陕西金堆城钼矿</strong>（矿石储量约 2.30 亿吨、平均品位 0.112%，权益 100%）'
    '与<strong>河南汝阳东沟钼矿</strong>（矿石储量约 2.60 亿吨、平均品位 0.120%，'
    '权益 65%），<strong>矿山自给率 100%、钼资源储量约 150 万吨</strong>；'
    '2026 年完成对金沙钼业 24% 股权的收购（对价 17.31 亿元），持股增至 34%，'
    '<strong>从而参股全球储量最大的单体钼矿 —— 安徽金寨沙坪沟钼矿'
    '（钼金属资源量约 210 万吨）</strong>。</p>'
    '<p><strong>财务端</strong>：五年毛利率 21.95% → 41.13%、'
    'ROIC 4.49% → 18.01%（五年中四年高于 7.2% 的 WACC 假设）、'
    '资产负债率仅 11.50%、2025 年每 10 股派现 4 元（分红率约 40.8%）。</p>'
    '<p><strong>但两条约束必须同时看清</strong>：</p>'
    '<ul class="vlist">'
    '<li><strong>它的利润是「钼价的函数」，不是「成长的函数」</strong> —— '
    '五年营收复合 14.75%，而利润的跃迁集中在 2023 年一年，此后三年横盘；</li>'
    '<li><strong>2025 年经营现金流 −56.21%（16.28 亿元）与利润创新高方向相反</strong>，'
    '性质待 2026 年验证。</li>'
    '</ul>'
)

# ---------------------------------------------------------------- 603599 广信股份
NEW['603599'] = (
    '<p class="vlead"><b>广信股份是一家「用稀缺的光气配额换成本优势」的农药一体化公司，'
    '而它现在的估值，是在按「周期底部 + 治理瑕疵」双打折。</b></p>'
    '<p>公司 2025 年营收 35.32 亿元（−23.92%）、归母净利 6.57 亿元（−15.64%），'
    '营收创 2020 年以来新低、利润连续三年下滑。</p>'
    '<p>但 <b>2026 年上半年出现了三个方向相反的信号</b>：</p>'
    '<ul class="vlist">'
    '<li>归母净利 3.57 亿元、<b>同比转正（+1.84%）</b>；</li>'
    '<li>毛利率从 32.36% 跃升到 <b>41.23%</b>、净利率从 18.60% 升到 <b>22.08%</b>；</li>'
    '<li><b>对硝基氯化苯价格从 2026 年初约 4,300 元/吨涨到 4–7 月的 14,000 元/吨以上'
    '（累计涨幅超 200%）</b>，而公司拥有 20 万吨/年的对（邻）硝基氯化苯产能。</li>'
    '</ul>'
    '<div class="vkey"><div class="vh">本报告的核心判断是：</div>'
    '<p>广信股份的利润弹性不在「量」，而在「价差」—— '
    '而它的价差锚（对邻硝 vs 纯苯）在 2026 年 3 月才真正张开。</p></div>'
    '<div class="vrisk"><div class="vh">风险同样明确：</div>'
    '<p><b>2026 年 4 月 30 日，控股股东广信集团因涉嫌持股变动信息披露违法违规'
    '被中国证监会立案</b>，至今（2026-09-22）无结论；叠加股价 '
    '<b>已跌破每股净资产（PB 0.96 倍）</b>，市场给的是「净资产打折」的定价。</p></div>'
)

# ---------------------------------------------------------------- 603977 国泰集团
NEW['603977'] = (
    '<p class="vlead"><strong>国泰集团（603977）</strong>是江西省国资委旗下、'
    '由江西省军工控股集团持股 47.08% 的<strong>民爆一体化平台</strong>，'
    '全国民爆行业前八强，也是江西省内唯一的民爆上市平台。</p>'
    '<p>2025 年营业收入 <strong>23.61 亿元</strong>（同比 +0.26%）、归母净利 '
    '<strong>2.52 亿元</strong>（同比 <strong>+39.55%</strong>）、'
    '扣非净利 2.20 亿元（+55.60%）。</p>'
    '<div class="vkey"><div class="vh">本报告的判读是：</div>'
    '<p><strong>公司 2025 年的利润增长来自「结构」而不是「规模」</strong>——'
    '民爆一体化的毛利率上台阶（+2.41pct 至 42.66%）、军工新材料放量（+46.42%）、'
    '轨交恢复（+22.62%），三个板块的收入占比已经形成'
    '「民爆 65.5% / 军工 16.7% / 轨交 7.5%」的新结构，其中'
    '<strong>军工新材料已在 2025 年超越轨交，成为第二大收入支柱</strong>。</p></div>'
    '<p><strong>但两条负面证据必须同时摆在桌上</strong>：</p>'
    '<ul class="vlist">'
    '<li><strong>ROIC 五年全部低于 7.2% 的 WACC 假设</strong>'
    '（2025 年 5.20%，利差 −2.00pct），账面 ROE 7.62% 部分由'
    '资产负债率升至 42.72% 的杠杆托住；</li>'
    '<li><strong>净现比从 2021 年的 1.30 降至 2025 年的 0.77</strong>，'
    '利润没有同步变现。</li>'
    '</ul>'
)

# ======================================================================
# 「文字零丢失」校验
# ======================================================================
TAG_RE = re.compile(r'<[^>]+>')
CIRCLE_RE = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]')


def norm(s):
    """把 HTML 归一成「纯文字」，用于逐字比对。

    ★ 允许的差异只有四类，其余一律视为「改动了正文」：
      ① HTML 标签（<b>/<strong> 互换成标签、<li> 换行都无所谓）；
      ② markdown 残留 `**`（原文里根本没被渲染，纯属噪声）；
      ③ ①②③ 序号（新版交给 CSS 计数器画圆形徽章，字符本身不再需要）；
      ④ ⚠ / ⚠️ 符号（新版用 CSS 三角 + 红底表达风险，不再用 emoji）；
      ⑤ 全部空白（换行、缩进 —— 600456 的原文带 6 空格缩进）；
      ⑥ 引号形态（600456 原文里的 ASCII 直引号统一成「」，见其条目注释）。
    """
    s = TAG_RE.sub('', s or '')
    s = s.replace('**', '')
    # 引号只做形态归一：开闭引号一律折成同一个哨兵字符，
    # 否则 ASCII 的 "A" 折成「A「 与中文的「A」折成「A」对不上。
    s = re.sub(r'["\u201c\u201d\u2018\u2019\u300c\u300d]', '\x01', s)
    s = CIRCLE_RE.sub('', s)
    s = s.replace('⚠️', '').replace('⚠', '')
    s = re.sub(r'\s+', '', s)
    return s


def diff_show(old, new):
    a, b = norm(old), norm(new)
    sm = difflib.SequenceMatcher(None, a, b)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        ctx = a[max(0, i1 - 14):i1]
        out.append('  %-9s 原「%s」→ 新「%s」   （…%s）'
                   % (tag, a[i1:i2][:60], b[j1:j2][:60], ctx[-14:]))
    return '\n'.join(out[:12])


def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=HDR, method=method)
    with urllib.request.urlopen(r, timeout=180) as resp:
        raw = resp.read().decode('utf-8', 'replace')
        return json.loads(raw) if raw.strip() else None


def _save(p, d):
    io.open(p, 'w', encoding='utf-8').write(
        json.dumps(d, ensure_ascii=False, indent=1) + '\n')


def sync_seed(code, html, dry=True):
    """把新版核心结论同步进**两处** seed —— 少一处都会在下次构建/推送时被刷回。

    ① `seed/data_v31_<code>.json` 的 `shell.verdict`
        ← push_reports_v31.py 建库用；`build/report_build_v31.py` 里
          `verdict_html = shell.get('verdict') or 默认模板`，所以**没有 shell
          的五份必须补上**，否则下次 push 直接吃默认模板。
    ② `seed/report_<code>.json` 的 `report.verdict_html`
        ← build.py 的 `build_report()` 把它序列化成 report.html 里的
          `window.RPT_SEED` 兜底副本（REST 拉不到研报时兜底）。
          ⚠️ 它跟 ① 是**两个文件**，改了一个不改另一个，兜底副本会一直是旧正文。
    """
    out = []
    p = os.path.join(SEEDDIR, 'data_v31_%s.json' % code)
    if os.path.exists(p):
        d = json.loads(io.open(p, encoding='utf-8').read())
        cur = (d.get('shell') or {}).get('verdict')
        if cur != html:
            if not dry:
                d.setdefault('shell', {})['verdict'] = html
                _save(p, d)
            out.append('建档 seed：' + ('补 shell.verdict（原来没有）' if not cur
                                     else '更新 shell.verdict'))
    q = os.path.join(SEEDDIR, 'report_%s.json' % code)
    if os.path.exists(q):
        d2 = json.loads(io.open(q, encoding='utf-8').read())
        cur2 = (d2.get('report') or {}).get('verdict_html')
        if cur2 != html:
            if not dry:
                d2['report']['verdict_html'] = html
                _save(q, d2)
            out.append('兜底副本：更新 verdict_html')
    return ' · '.join(out) if out else 'seed 已一致'


def main():
    mode = 'apply'
    if '--dry' in sys.argv:
        mode = 'dry'
    elif '--check' in sys.argv:
        mode = 'check'
    no_seed = '--no-seed' in sys.argv

    # ★ --seed-only：只把新版写进 seed（不碰库）。
    #   用途：report.html 里内嵌着 600456 的 RPT_SEED 兜底副本，
    #   「先发新样式、再切库数据」时，兜底副本要先跟着更新，
    #   否则线上会短暂出现「新 CSS + 旧正文」的中间态。
    if '--seed-only' in sys.argv:
        for code, new in NEW.items():
            print('%-8s %s' % (code, sync_seed(code, new, dry=False)))
        return 0

    rows = req('GET', 'wb_reports?select=id,code,name,verdict_html&order=code.asc')
    by = {r['code']: r for r in rows}

    print('=' * 100)
    print('核心结论版式重做 · %s' % {'dry': '校验（不写库）',
                                      'check': '回读校验', 'apply': '写入'}[mode])
    print('=' * 100)
    ok = bad = 0
    for code, new in NEW.items():
        r = by.get(code)
        if not r:
            print('✗ %s 库里没有这份研报' % code); bad += 1; continue
        cur = r.get('verdict_html') or ''
        if mode == 'check':
            if norm(cur) != norm(new):
                print('✗ %-8s %-8s 库里的版本不是新版' % (code, r.get('name') or ''))
                bad += 1
            elif 'vlead' not in cur:
                print('✗ %-8s 库里没有新版标记类' % code); bad += 1
            else:
                print('✓ %-8s %-8s 已是新版（%d 字）'
                      % (code, (r.get('name') or '')[:8], len(cur))); ok += 1
            continue

        n_old, n_new = norm(cur), norm(new)
        if n_old != n_new:
            print('✗ %-8s %-8s 文字对不上，拒绝写库：' % (code, r.get('name') or ''))
            print(diff_show(cur, new))
            bad += 1
            continue
        if cur == new:
            print('✓ %-8s %-8s 已是新版（幂等，不动）'
                  % (code, (r.get('name') or '')[:8])); ok += 1
            continue
        tail = ''
        if not no_seed:
            tail = ' · ' + sync_seed(code, new, dry=(mode == 'dry'))
        print('✓ %-8s %-8s 文字零丢失 · %d → %d 字%s'
              % (code, (r.get('name') or '')[:8], len(cur), len(new), tail))
        if mode != 'dry':
            req('PATCH', 'wb_reports?id=eq.%s' % r['id'], {'verdict_html': new})
        ok += 1

    print('-' * 100)
    print('通过 %d 份，失败 %d 份%s' % (ok, bad, '（未写库）' if mode == 'dry' else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
