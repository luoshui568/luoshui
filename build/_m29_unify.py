# -*- coding: utf-8 -*-
"""把四家的槽 29 统一成母本（宝钛 600456）的 A 形，并按用户指令把分值留空。

【用户指令】2026-09-21
  「换」   → 贵研 / 恒邦的槽 29 换成母本那种 A 形（环形总分卡 + 十项选股原则明细）
  「是的」 → 美丰 / 鲁西那两个由流水线自动生成的分数也留空
             （用户原话：「需要我自己填的地方留空就行，例如企业评分这种」）

【现状（线上库实测，非本地缓存）】
  600456 母本 = A 形（EPS 图 + 技术解读 + 环形卡 + 十项 sc-note 明细 + 评分说明 + 口径说明）
  600459 贵研 = m29 渲染器产出的十项表 + 手写「为什么不用十项原则」自辩
  002237 恒邦 = 仅 m29 渲染器的十项表（1618 字，7 处 MISSING —— 最薄）
  000731 美丰 = A 形（69.9，无逐项说明）
  000830 鲁西 = A 形（65.6，无逐项说明）

【关键发现】600459 / 002237 在旧 v23 版（23 模块）里**本来就有 A 形**
  （贵研 66.1 / 恒邦 61.8），是升级 31 模块时丢掉的 ⇒ 从 v23 搬回来，
  正文一字不改，只把分值留空（与 §8「_goldify 搬家」同一思路）。

【留空形态】环形卡改灰空环 + 「—/100」+ 徽标「待评分」；十项 sc-val 改「—」、
  进度条归零；总分条改「—」；评分说明整段换成「填写说明」。

【为什么不走 push_reports_v31.py】改单模块只 PATCH `wb_report_mods`，
  避免把另外 30 行重写一遍（并发会话可能正在改别家）。※ 复用 _blank29.py 的框架。

自检（缺一即停）：
  ① 幂等：build(build(x)) == build(x)
  ② 结构：环形卡 1 个 / sc-line 10 条 / sc-total 1 个 / 无残留分值
  ③ 缺分断言：变换后不得再有 `sc-val">数字` 与 `gauge-num">数字`
  ④ 漂移闸：写前线上 html 必须 == 本地 seed（一字不差）
  ⑤ 写后回读：线上 html == 新值

用法：
    python _m29_unify.py            # 干跑
    python _m29_unify.py --go       # 备份 + PATCH 线上 + 写回本地 seed
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
BAK = os.path.join(HERE, 'backup')
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Accept': 'application/json', 'Content-Type': 'application/json'}
NO = '29'

FILL_SRC = (
    '<p class="src" style="margin-top:12px;"><b>填写说明：</b>本项为企业评分'
    '（十项选股原则 · 单项满分 10 分 · 满分 100）。<b>本轮分数留空、待填写</b>。'
    '计算口径：总分 = Σ（单项评分 × 权重）× 10 —— 把十项得分填入后，'
    '环形卡刻度与「加权总分」同步更新。<b>项名与权重按母本（宝钛股份 600456）固定，请勿改动</b>；'
    '客观指标见上方指标卡，财务与行情口径见对应模块。'
    '评分属定性判断，仅供参考，<b>不构成投资建议</b>。</p>'
)


def req(path, method='GET', body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    rq = urllib.request.Request(BASE + path, data=data, headers=HDR, method=method)
    with urllib.request.urlopen(rq, timeout=120) as r:
        raw = r.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else None


# ─────────────────────────── 去分（留空）───────────────────────────
def norm_bar(h):
    """清空进度条填充 —— 幂等，且能修复上一版留下的写法。

    ★ 坑（2026-09-21 实测）：不能把填充写成 `<i class="mid" style="width:0%">`！
      壳里有 `.sc-line:has(.sc-bar i.mid) .sc-val::after{width:14px;height:2px;
      background:linear-gradient(...红...)}` —— 只要 class 是 mid 就会命中，
      在数值右侧多画一条 14×2px 的红色装饰线（「空进度条」却留着红点）。
      正确做法：整个删掉 `<i>`，`.sc-bar` 只剩灰轨道。
    """
    return re.sub(r'<div class="sc-bar">(?:<i class="\w+" style="width:\d+%;"></i>)?</div>',
                  '<div class="sc-bar"></div>', h)


def norm_md(h):
    """把残留的 Markdown 粗体 `**x**` 转成 <b>x</b>。

    ★ 背景：600459 槽 29 里从旧版搬来的三张表有 12 处 `**不适用**` / `**合计**`
      这类写法，浏览器不解析，页面上显示成**字面星号**。母本 600456 是 0 处。
    """
    return re.sub(r'\*\*([^*\n]{1,60})\*\*', r'<b>\1</b>', h)


def blank_A(h):
    """把 A 形里所有分值位清空。幂等：已是留空态则只做规范化后返回。"""
    out = norm_bar(h)
    if '<div class="gauge-badge">待评分</div>' in out:
        return out
    # 1) 环形卡红色扇区 → 灰色空环
    n = len(re.findall(r'conic-gradient\(#c8[0-9a-fA-F]* 0 [\d.]+%, #f6e6e9 [\d.]+% 100%\)', out))
    if n != 1:
        raise SystemExit('✗ 环形卡 conic-gradient 匹配 %d 次，应为 1 —— 结构变了，停手' % n)
    out = re.sub(r'conic-gradient\(#c8[0-9a-fA-F]* 0 [\d.]+%, #f6e6e9 [\d.]+% 100%\)',
                 'conic-gradient(#e6e5e3 0 100%)', out)
    # 2) 大号总分数字
    out, k = re.subn(r'(<div class="gauge-num">)[\d.]+(<small>)', r'\1—\2', out)
    assert k == 1, 'gauge-num 替换 %d 次' % k
    # 3) 评级徽标
    out, k = re.subn(r'<div class="gauge-badge">[^<]*</div>',
                     '<div class="gauge-badge">待评分</div>', out)
    assert k == 1, 'gauge-badge 替换 %d 次' % k
    # 4) 十项分值（进度条已由 norm_bar 处理）
    out, k = re.subn(r'<div class="sc-val">\d+</div>', '<div class="sc-val">—</div>', out)
    assert k == 10, 'sc-val 替换 %d 次，应为 10' % k
    # 5) 底部总分条
    out, k = re.subn(r'(<span class="tn">)[\d.]+(</span>)', r'\1—\2', out)
    assert k == 1, 'sc-total 数字替换 %d 次' % k
    out, k = re.subn(r'<span class="tt">[^<]*</span>', '<span class="tt">待评分</span>', out)
    assert k == 1, 'sc-total 档位替换 %d 次' % k
    # 6) 副标题加「评分待填写」
    out = out.replace('<div class="g-sub">', '<div class="g-sub">评分待填写 · ', 1)
    return out


def swap_fill_src(h):
    """把「评分说明」整段换成「填写说明」。"""
    if FILL_SRC in h:
        return h
    pat = re.compile(r'<p class="src" style="margin-top:12px;">\s*<b>评分说明：</b>.*?</p>', re.S)
    n = len(pat.findall(h))
    if n != 1:
        raise SystemExit('✗ 「评分说明」段匹配 %d 次，应为 1 —— 停手' % n)
    return pat.sub(lambda m: FILL_SRC, h)


# ─────────────────────── 四家的组装（各自来源不同）───────────────────────
def v23_A(code):
    """从旧 v23 版取 A 形（正文一字不改）。"""
    d = json.load(io.open(os.path.join(SEED, 'report_%s_v23.json' % code), encoding='utf-8'))
    hits = [m['html'] for m in d['mods'] if 'score-hero' in (m.get('html') or '')]
    if len(hits) != 1:
        raise SystemExit('✗ %s 的 v23 里 A 形有 %d 份，应为 1' % (code, len(hits)))
    return hits[0]


def build_600459(cur, v23):
    """贵研：换成 A 形（去分）+ 保留原有的「适用性说明」与「四维对照」。

    ★ 幂等早退必须放在最前：main() 会二次调用本函数验幂等，
      而二次时 cur 里已无「为什么本报告不用…」锚点，会误报「找不到」。
    """
    if '<h3>十项原则对贵研的适用性说明</h3>' in cur:
        return cur
    i = cur.find('<h3>为什么本报告不用「十项选股原则」打分</h3>')
    if i < 0:
        raise SystemExit('✗ 600459 找不到「为什么本报告不用…」小节 —— 结构变了，停手')
    tail = cur[i:]
    tail = tail.replace('<h3>为什么本报告不用「十项选股原则」打分</h3>',
                        '<h3>十项原则对贵研的适用性说明</h3>')
    tail = tail.replace('<b>本报告（贵研）不给总分</b>',
                        '<b>本报告的评分待填写</b>')
    tail = tail.replace('<div class="lt">替代方案：只给「可客观量化」的四维评分</div>',
                        '<div class="lt">补充：四维财务质量评分（可客观量化对照）</div>')
    tail = tail.replace('本报告改为<b>四维财务质量评分（满分 40）</b>',
                        '另附<b>四维财务质量评分（满分 40）</b>')
    return swap_fill_src(blank_A(v23)) + '\n    ' + tail


def build_002237(cur, v23):
    """恒邦：换成 A 形（去分）。原 m29 表格与 A 形重复（两套尺子），不再保留。"""
    if 'class="score-hero"' in cur and '<div class="gauge-badge">待评分</div>' in cur:
        return cur                      # 幂等早退
    return swap_fill_src(blank_A(v23))


def build_731_830(cur):
    """美丰 / 鲁西：已是 A 形，仅去分 + 消除带分值的叙述。"""
    out = blank_A(cur)
    fixes = [
        # 000731
        ('十项原则中得分最高的三项（第 7-10 项）全部属于<strong>「低市值 + 底部形态 + 量能」的技术性指标</strong>，'
         '而两项基本面指标（产品价格、扣非净利）均为 3 分。这说明该股属于',
         '十项原则中偏技术面的三项（第 8-10 项：股价盘整、月线底部、量能）与偏基本面的两项'
         '（第 3 项产品价格、第 4 项扣非净利）指向相反 —— 前者给出「底部」信号，后者仍在负增长，'
         '属<strong>「技术面强、基本面弱」</strong>的组合：'),
        # 000830
        ('但按十项加权得分 65.6 落入「观察」档位，且<strong>现价 12.02 元已高于底稿买入区间 10-11 元</strong>。',
         '但十项加权结果需待填写后再定档；<strong>现价 12.02 元已高于底稿买入区间 10-11 元</strong>，安全边际收窄。'),
        # 000731 的旧句式（若上一轮替换未生效则命中）
        ('而两项基本面指标（产品价格、扣非净利）均为 3 分。这说明该股属于<strong>「技术面强、基本面弱」</strong>的组合：',
         '而两项基本面指标（第 3 项产品价格、第 4 项扣非净利）仍在负增长：'),
    ]
    for old, new in fixes:
        if old in out:
            out = out.replace(old, new)
    return swap_fill_src(out)


def make_new(code, cur):
    # ★ norm_bar 放在最外层：这样即便 build_xxx 走了幂等早退（cur 已是留空态），
    #   上一版遗留的 `<i class="mid" width:0%>` 写法也能被修掉。
    if code in ('600459', '002237'):
        f = build_600459 if code == '600459' else build_002237
        return norm_md(norm_bar(f(cur, v23_A(code))))
    return norm_md(norm_bar(build_731_830(cur)))


# ───────────────────────────── 自检 ─────────────────────────────
def selfcheck(code, h):
    errs = []
    if h.count('class="score-hero"') != 1:
        errs.append('score-hero %d 个' % h.count('class="score-hero"'))
    if h.count('class="sc-line"') != 10:
        errs.append('sc-line %d 条，应为 10' % h.count('class="sc-line"'))
    if h.count('class="sc-total"') != 1:
        errs.append('sc-total %d 个' % h.count('class="sc-total"'))
    if re.search(r'<div class="sc-val">\d+</div>', h):
        errs.append('仍有残留分值：%s' % re.findall(r'<div class="sc-val">(\d+)</div>', h)[:5])
    if h.count('<div class="sc-bar"></div>') != 10:
        errs.append('空进度条 %d 个，应为 10' % h.count('<div class="sc-bar"></div>'))
    if re.search(r'<div class="sc-bar">\s*<i', h):
        errs.append('进度条里仍有 <i> —— 会命中 .sc-line:has(.sc-bar i.mid) 的红色装饰线')
    if '**' in h:
        errs.append('仍有未解析的 Markdown 粗体：%s' % re.findall(r'\*\*[^*]{1,30}\*\*', h)[:5])
    if re.search(r'<div class="gauge-num">\d', h):
        errs.append('环形卡仍是数字')
    if 'conic-gradient(#e6e5e3 0 100%)' not in h:
        errs.append('环形卡不是灰空环')
    if '待评分' not in h:
        errs.append('缺「待评分」标记')
    if FILL_SRC not in h:
        errs.append('缺「填写说明」段')
    if h.count('[MISSING]') != 0:
        errs.append('MISSING %d 处（应为 0）' % h.count('[MISSING]'))
    return errs


def main():
    go = '--go' in sys.argv
    stamp = time.strftime('%Y%m%d-%H%M%S')
    bad = 0
    plan = {}
    for code in ['600459', '002237', '000731', '000830']:
        seed_p = os.path.join(SEED, 'report_%s.json' % code)
        seed = json.load(io.open(seed_p, encoding='utf-8'))
        mods = {str(m['no']): m for m in seed['mods']}
        if NO not in mods:
            print('✗ %s 本地 seed 无槽 %s' % (code, NO))
            bad += 1
            continue
        cur = mods[NO]['html'] or ''
        # 幂等：先看 build 是否稳定
        new = make_new(code, cur)
        if make_new(code, new) != new:
            print('✗ %s 变换不幂等' % code)
            bad += 1
            continue
        errs = selfcheck(code, new)
        print('=' * 92)
        print('【%s】槽 %s  %d → %d 字符 · MISSING %d → %d'
              % (code, NO, len(cur), len(new), cur.count('[MISSING]'), new.count('[MISSING]')))
        print('  来源：%s' % ('旧 v23 版 A 形（搬家，正文不改）' if code in ('600459', '002237')
                             else '现 A 形（仅去分）'))
        if errs:
            print('  ✗ 自检：')
            for e in errs:
                print('     - %s' % e)
            bad += 1
        else:
            print('  ✓ 自检通过（环形卡 1 / sc-line 10 / 无残留分值 / 0 MISSING / 幂等）')
        # 漂移闸
        live = req('wb_report_mods?select=html,up&report_id=eq.%s&no=eq.%s' % (code, NO))
        if not live:
            print('  ✗ 线上读不到该模块')
            bad += 1
        elif (live[0].get('html') or '') != cur:
            print('  ✗ 漂移：线上 %d 字符 ≠ 本地 %d —— 拒绝覆盖'
                  % (len(live[0].get('html') or ''), len(cur)))
            bad += 1
        else:
            print('  ✓ 漂移闸：线上 == 本地（%d 字符）· 线上 up=%s' % (len(cur), live[0].get('up')))
        plan[code] = (seed_p, seed, mods, new, cur)

    print('=' * 92)
    if bad:
        print('✗ 有 %d 家未通过，未做任何写入' % bad)
        return 1
    print('✓ 四家自检 + 漂移闸全过')

    if not go:
        print('模式：干跑（加 --go 写盘）')
        return 0

    os.makedirs(BAK, exist_ok=True)
    for code, (seed_p, seed, mods, new, cur) in plan.items():
        b = os.path.join(BAK, 'report_%s_pre_m29unify_%s.json' % (code, stamp))
        shutil.copy2(seed_p, b)
        mods[NO]['html'] = new
        seed['mods'] = [mods[str(m['no'])] for m in seed['mods']]
        r = req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (code, NO), 'PATCH',
                {'html': new, 'up': int(time.time() * 1000)})
        io.open(seed_p, 'w', encoding='utf-8').write(json.dumps(seed, ensure_ascii=False))
        back = req('wb_report_mods?select=html&report_id=eq.%s&no=eq.%s' % (code, NO))
        ok = (back[0].get('html') or '') == new
        print('【%s】备份 %s · PATCH %d 行 · 本地 md5 %s · 回读 %s'
              % (code, os.path.basename(b), len(r) if isinstance(r, list) else -1,
                 hashlib.md5(io.open(seed_p, 'rb').read()).hexdigest()[:12],
                 '✓' if ok else '✗'))
    print('模式：写盘')
    return 0


if __name__ == '__main__':
    sys.exit(main())
