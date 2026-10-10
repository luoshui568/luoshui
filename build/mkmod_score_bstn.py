# -*- coding: utf-8 -*-
"""600456 宝钛股份 · 「企业评分（选股原则 10 项）」模块 —— 给每条原则补一行简明分析。

背景（2026-09-20 用户要求）：
    「在中间的空白列，按这种简明扼要的分析帮我补全」
评分行原本是 `28px | 1fr | 46px | 150px | 36px` —— 原则名只占中间那列左边一小截，
右边一大片全空着。本次在**同一个格子里**、原则名下方补一行 `sc-note`：带具体数字、
点明该原则成不成立，2 行以内。

★★★ 认标题不认编号 —— 这个模块今天已经挪了三次位置 ★★★
    2026-09-20 里，另一个并发会话先把「风险矩阵」并入行业分析（31→30），
    18:14 又插入 m25「产量储量分布及价格分析」，把所有后续模块 +1 ——
    评分模块从 m27 一路滑到 **m29**。
    所以本脚本用 **正文里的「十项选股」** 作主键解析编号，PATCH 前还会核对
    线上同一位置行的标题里也有「选股原则」，两边都对上才写。

★ 只改这一件事：分数、权重、进度条、加权总分一律不动（没要求重评分）。
★ 取数截至 2026-09-18（最近交易日），而评分与上方估值锚点仍是报告日
  2026-08-24 收盘 27.35 元 —— 两套口径在文末「口径说明」里显式写明，不混用。
  为什么不顺手把锚点刷新到 09-18：模块 26 / 27 都写死了「股价与市值按
  2026-08-24 收盘固定，与模块 27 / 模块 28 评分卡同源」，单改一处会让三处打架。

★ 数据出处：
  行情 / 量能      通达信（tdx_quotes、tdx_kline 日线与月线，不复权）
  海绵钛价格       同花顺 iFinD「市场价:海绵钛(1#):不限地区:平均价」（万元/吨，日频）
  财务 / 扣非      东方财富 mx_ashare_finance_data（2026 中报 + 2023—2025 年报）
  股本 / 每股净资产 通达信 CwInfo（总股本 47,777.75 万股、每股净资产 15.046 元）
  收入结构         本报告模块「公司产品收入与毛利结构」（2025 年报主营构成）

用法：
    python build/mkmod_score_bstn.py                # 干跑：体检 + 新旧对照，不写任何地方
    python build/mkmod_score_bstn.py --go           # 只写本地 seed（先渲染验证）
    python build/mkmod_score_bstn.py --go --push    # 写本地 seed + 推云端
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(BASE, 'seed', 'report_600456.json')
BAK = os.path.join(BASE, 'backup')

RID = '600456'
KEY = '十项选股'                  # 正文主键：认它，不认编号
TITLE_KEY = '选股原则'             # 线上同位置行的标题里应当也有它
BASELINE = os.path.join(BAK, 'modScore_%s_baseline.html' % RID)

CFG = json.load(io.open(os.path.join(BASE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'resolution=merge-duplicates,return=minimal'}

# ---------------------------------------------------------------------------
# 十项原则：(序号, 原则名, 是否加分项, 权重%, 得分, 分析)
# 权重与得分照抄报告现状，一个字不改。
# ---------------------------------------------------------------------------
ITEMS = [
    (1, '股东，央企或省国资委', True, 10, 9,
     '最终控制人为陕西省人民政府：陕西有色金属集团持宝钛集团 93.36%，宝钛集团持本公司 49.40%；'
     '省属国资背景使其在军工资质、航天认证与资源获取上具备天然优势，可转债转股后的持股稀释需跟踪。'),

    (2, '独一无二，资本别无选择', True, 14, 9,
     '国内唯一贯通「海绵钛—铸锭—锻造—板带管棒丝」全流程的钛材企业，拥有 4 万吨铸锭 / 3 万吨加工材产能'
     '与十大生产系统，牌号覆盖最全；已进入波音、空客供应体系，军工认证的切换成本高。'),

    (3, '产品持续大涨 &gt; 100%', False, 13, 5,
     '未出现 100% 级涨价，方向仍向下：海绵钛(1#)全国均价 2026-09-20 为 4.35 万元/吨、同比 -9.4%，'
     '较 6 月高点 4.75 万元再跌 8.4%；公司 2025 年钛产品销售均价 17.89 万元/吨、同比 -4.7%。'),

    (4, '扣非净利润持续大涨 &gt; 60%', False, 14, 5,
     '方向相反：扣非归母净利润 2023 / 2024 年为 4.75 / 4.99 亿元，2025 年降至 3.17 亿元（-36.6%），'
     '2026 年上半年 1.221 亿元（-29.3%），同期营收 30.02 亿元仅增 1.2%；连续两期负增长，拐点未现。'),

    (5, '主营集中 &gt; 75%', True, 9, 10,
     '高度集中：2025 年钛产品收入占营业收入 85.99%、毛利占比 102%（其他金属产品毛利为负，-2.12%），'
     '钛产品与其他金属产品合计占收入 93.8%；公司业绩几乎就是钛价的函数。'),

    (6, '盈利模式简单清晰', False, 8, 9,
     '卖钛材赚加工费，变量只有产量、销售均价与原料成本三项：2025 年销售均价 17.89 万元/吨、'
     '成本 13.68 万元/吨，单吨毛利 4.21 万元、毛利率 19.85%，模型一眼可算。'),

    (7, '总市值 &lt; 200 亿', False, 8, 6,
     '2026-09-18 收盘 25.25 元，总市值 120.64 亿元，低于 200 亿元门槛；但市值已从 2026 年 2 月高点'
     '缩水 44%，「小」更多来自盈利与钛价双降，而非单纯的估值便宜。'),

    (8, '股价盘整 2-3 年充分吸收', False, 9, 6,
     '2023-03 至 2025-11 共 33 个月，收盘价在 24.19~35.62 元箱体内反复消化；2025-12 至 2026-02 一度'
     '放量冲高至 45.40 元，2026-03 起单边回落，现价 25.25 元重回箱体下沿，上沿突破失败后筹码需重新沉淀。'),

    (9, '股价位于月线底部区域', False, 9, 6,
     'PB 1.678 倍（25.25 元 ÷ 每股净资产 15.046 元），处报告口径 1.2~5.7 倍历史区间的低位；'
     '2026-09-17 盘中 25.00 元创近一年新低，距 2024-02 月线低点 20.70 元仍有 22% 空间——属底部区域，未到绝对低位。'),

    (10, '底部成交量开始显著放大', False, 6, 6,
     '尚未放量：近 20 个交易日（08-24~09-18）日均成交 4.72 万手，较此前 20 日（07-27~08-21）的'
     '6.10 万手再缩 22.6%；月度量能从 2026 年 1 月的 559 万手降至 8 月的 127 万手，底部换手信号未出现。'),
]

SRC_NEW = (
    '<p class="src" style="margin-top:12px;"><b>评分说明：</b>总分 = Σ（单项评分 × 权重）× 10，满分 100。'
    '主要得分项为<strong>国资控股（第 1 项，9 分）、全产业链独一无二（第 2 项，9 分）、'
    '主营集中度（钛产品 86%，第 5 项，10 分）、盈利模式清晰（第 6 项，9 分）</strong>；'
    '主要扣分项为<strong>产品价格未持续大涨（第 3 项，5 分）、扣非净利未持续大涨（第 4 项，5 分）</strong>。'
    '评分基于公开信息定性判断，非量化模型输出，<b>仅供参考，不构成投资建议</b>。</p>\n'
    '    <p class="src" style="margin-top:6px;"><b>口径说明：</b>各原则下方的分析文字取数截至 '
    '<b>2026-09-18</b>（最近交易日：收盘 25.25 元 / 总市值 120.64 亿元 / PB 1.678 倍 / PE(TTM) 35.37 倍），'
    '行情与量能来自通达信，海绵钛价格来自同花顺 iFinD「市场价:海绵钛(1#):不限地区:平均价」，'
    '财务数据来自 2026 年半年报及 2023—2025 年年报；'
    '<b>评分与上方估值锚点仍为报告日 2026-08-24 收盘价 27.35 元</b>（与盈利预测模型 / 估值分析两模块同源），'
    '两套口径不可直接相减。第 3 项所引为海绵钛全国均价，与「上游原料价格」模块的价格走势口径可能存在差异，'
    '以原始指标名称为准。</p>'
)


def req(path, method='GET', body=None):
    # ⚠️ body 必须走 Request(data=...)；直接 **init 传 body 会 TypeError
    #    （2026-09-20 踩过，这个坑在 patch_toc_labels.py 里也犯过一次）。
    init = {'method': method, 'headers': dict(HDR)}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    try:
        with urllib.request.urlopen(
                urllib.request.Request(REST + path, data=data, **init), timeout=90) as f:
            t = f.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    return 200, (json.loads(t) if t.strip() else None)


def load_seed():
    return json.load(io.open(SEED, encoding='utf-8'))


def resolve(seed):
    """按正文主键解析评分模块，返回 (模块字典, 编号)。编号会漂，认标题。"""
    hits = [m for m in seed['mods'] if KEY in (m.get('html') or '')]
    assert len(hits) == 1, '正文含「%s」的模块有 %d 个，无法唯一定位' % (KEY, len(hits))
    return hits[0], int(hits[0]['no'])


def bar_class(score):
    return 'hi' if score >= 9 else ('mid' if score >= 5 else 'low')


def render_rows():
    """每行 6 空格缩进；行间用 \\n 连接，**不带尾随空白** —— 空白由 build() 统一控制，
    否则「head 末尾的缩进 + 行首缩进」会一遍比一遍多 6 个空格（幂等自检当场报错）。"""
    out = []
    for (no, name, bonus, weight, score, note) in ITEMS:
        em = '<em class="pos-em">加分项</em>' if bonus else ''
        out.append(
            '      <div class="sc-line"><div class="sc-no">%d</div>'
            '<div class="sc-name">%s%s</div>'
            '<div class="sc-note">%s</div>'
            '<div class="sc-w">%d%%</div>'
            '<div class="sc-bar"><i class="%s" style="width:%d%%;"></i></div>'
            '<div class="sc-val">%d</div></div>'
            % (no, name, em, note, weight, bar_class(score), score * 10, score))
    return '\n'.join(out)


def build(old_html):
    # —— 幂等化：先摘掉上一版插进去的「口径说明」段 ——
    # 没有这一步，第二次跑（--go --push）会把口径说明再追加一遍。
    cl = old_html.find('<p class="src" style="margin-top:6px;">')
    if cl > 0 and '口径说明' in old_html[cl:cl + 90]:
        cl_end = old_html.find('</p>', cl) + 4
        assert cl_end > cl, '口径说明段不完整'
        old_html = old_html[:cl] + old_html[cl_end:]

    i0 = old_html.find('<div class="criteria">')
    irow = old_html.find('<div class="sc-line">')
    itot = old_html.find('<div class="sc-total">')
    isrc = old_html.find('<p class="src" style="margin-top:12px;">')
    assert i0 > 0 and irow > i0 and itot > irow and isrc > itot, '评分模块结构不符合预期，中止'
    isrc_end = old_html.find('</p>', isrc) + 4

    head = old_html[i0:irow].rstrip('\r\n \t') + '\n'   # criteria 容器 + criteria-head
    total = old_html[itot:isrc]                          # sc-total + criteria 收尾
    rows = render_rows()
    # 尾部：若「评分说明」之后只剩空白就归零。否则第二遍跑时会多留一截
    # 段落之间的缩进空白（第一遍没有），幂等自检会当场报错。
    tail = old_html[isrc_end:]
    if not tail.strip():
        tail = ''
    new = old_html[:i0] + head + rows + '\n    ' + total + SRC_NEW + tail

    rep = {
        '旧行数': old_html.count('<div class="sc-line">'),
        '新行数': new.count('<div class="sc-line">'),
        '新 note 数': new.count('<div class="sc-note">'),
        '加权总分未变': '70.5' in new and '评级：观察' in new,
        '旧长度': len(old_html), '新长度': len(new),
    }
    return new, rep


def main():
    go = '--go' in sys.argv
    push = '--push' in sys.argv
    force = '--force' in sys.argv

    seed = load_seed()
    tgt, no = resolve(seed)
    modid = '%s_m%d' % (RID, no)
    old_mod = tgt['html']

    print('=' * 82)
    print('本地 seed：模块 %d 个 / 图表 %d 张，seed mtime %s'
          % (len(seed['mods']), len(seed['charts']),
             time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(SEED)))))
    print('评分模块定位 → m%d《%s》%d 字符（id=%s）' % (no, tgt.get('title'), len(old_mod), modid))

    st, r = req('wb_report_mods?id=eq.%s&select=html,title,no,up' % modid)
    live = r[0] if (st == 200 and r) else None
    if live:
        print('线上 %s《%s》%d 字符  up=%s' % (modid, live.get('title'), len(live['html'] or ''),
              time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(live['up']) / 1000)) if live.get('up') else '-'))
        assert TITLE_KEY in (live.get('title') or ''), \
            '线上 %s 的标题里没有「%s」—— 编号又漂了，先重新定位再跑' % (modid, TITLE_KEY)
        print('线上同位置行标题核对：含「%s」✓  线上 == 本地 seed：%s'
              % (TITLE_KEY, (live['html'] or '') == old_mod))
    else:
        print('线上 %s：读不到（未登录 / 无此行）' % modid)

    # ---- 漂移闸：基准只落盘一次（第一次跑时的线上快照），此后不再改写 ----
    os.makedirs(BAK, exist_ok=True)
    if not os.path.exists(BASELINE):
        io.open(BASELINE, 'w', encoding='utf-8').write((live or {}).get('html') or old_mod)
        print('[基线] 已落盘审核基准 → %s' % os.path.basename(BASELINE))
    base = io.open(BASELINE, encoding='utf-8').read()
    if live and (live['html'] or '') != base and not force:
        print('\n[中止] 线上 %s 与审核基准不一致（疑似并发会话改过）；确认后用 --force。' % modid)
        print('       基准 %d 字符 / 线上 %d 字符' % (len(base), len(live['html'] or '')))
        return
    print('漂移闸：线上 %s == 审核基准 ✓' % modid)

    new_mod, rep = build(old_mod)
    # 幂等自检：对本脚本自己的输出再跑一次，必须逐字节相同。
    # （否则「先 --go 看渲染、再 --go --push」这条常规路径会二义性地改内容。）
    new_again, _ = build(new_mod)
    assert new_again == new_mod, '非幂等：重复运行会改变内容，中止'
    for k, v in rep.items():
        print('  %-14s %s' % (k, v))
    print('  %-14s %s' % ('幂等自检', 'OK（输出再跑一次逐字节相同）'))
    assert rep['旧行数'] == rep['新行数'] == 10, '行数异常'
    assert rep['新 note 数'] == 10, 'note 数异常'
    assert rep['加权总分未变'], '总分/评级被改动'
    for bad in ['<style', '<script', '<link', '<style ']:
        assert bad not in new_mod, '新正文含会被白名单剥掉的标签：%s' % bad

    print('\n--- 新旧对照（第 1-3 条）---')
    for row in re.findall(r'<div class="sc-line">.*?</div></div>', new_mod)[:3]:
        print('  ', re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' | ', row)).strip()[:230])

    if not go:
        print('\n[dry-run] 未写任何地方。加 --go 写入本地 seed。')
        return

    ts = time.strftime('%Y%m%d-%H%M%S')
    bp = os.path.join(BAK, 'modScore_%s_pre_note_%s.json' % (RID, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'rid': RID, 'no': no, 'modid': modid, 'live': live}, ensure_ascii=False))
    print('\n=== 4) 备份线上现状 → %s ===' % os.path.basename(bp))

    # ---- 写本地前重新读盘，确认没人动过这一格（并发会话防护）----
    print('=== 5) 写本地 seed ===')
    fresh = load_seed()
    tgt2, no2 = resolve(fresh)
    assert no2 == no, '写盘前编号又变了（%d → %d），中止' % (no, no2)
    assert tgt2['html'] == old_mod, '写盘前该模块已被其他会话改动，中止'
    n_before = len(fresh['mods'])
    tgt2['html'] = new_mod
    io.open(SEED, 'w', encoding='utf-8').write(json.dumps(fresh, ensure_ascii=False, indent=1))
    chk = load_seed()
    tgt3, no3 = resolve(chk)
    print('  已写 %s（模块 %d 个 / 图表 %d 张）' % (os.path.basename(SEED), len(chk['mods']), len(chk['charts'])))
    print('  回读：模块数 %d→%d，评分模块仍唯一（m%d），正文一致：%s'
          % (n_before, len(chk['mods']), no3, tgt3['html'] == new_mod))

    if not push:
        print('\n[未推库] 本地 seed 已就绪，确认渲染无误后再加 --push。')
        return

    print('=== 6) 推云端 ===')
    now = int(time.time() * 1000)
    st, r = req('wb_report_mods?id=eq.%s' % modid, 'PATCH', {'html': new_mod, 'up': now})
    print('  PATCH %s：%s %s' % (modid, st, '' if st < 400 else r))
    assert st < 400, '模块写入失败'

    print('=== 7) 回读核对 ===')
    st, rb = req('wb_report_mods?id=eq.%s&select=html,no,title' % modid)
    ok_mod = (st == 200 and rb and rb[0]['html'] == new_mod)
    print('  %s 正文逐字节一致：%s' % (modid, ok_mod))
    st, cnt2 = req('wb_report_mods?report_id=eq.%s&select=id' % RID)
    st, cnt = req('wb_report_charts?report_id=eq.%s&select=id' % RID)
    print('  600456 模块 %d 个（本地 %d）/ 图表 %d 张（本地 %d）'
          % (len(cnt2), len(seed['mods']), len(cnt), len(seed['charts'])))
    ok = ok_mod and len(cnt2) == len(seed['mods']) and len(cnt) == len(seed['charts'])
    print('\n%s' % ('全部通过 ✓' if ok else '⚠ 存在未通过项'))


if __name__ == '__main__':
    main()
