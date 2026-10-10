# -*- coding: utf-8 -*-
"""摘除「估值敏感性」小节 —— 用户 2026-09-21 指令：「估值敏感性，把所有这块都去掉」。

★ 母本 600456 的槽 28 本来就只有「可比公司 + 情景推演」两块、**没有敏感性**
  ⇒ 本次是向母本形态对齐，不是新发明。

三条路径（按各家的槽 28 是「渲染器产的」还是「手写的」分流）：

| 公司 | 槽 28 来源 | 处理方式 |
|---|---|---|
| 600459 贵研 / 002237 恒邦 | 可被 `RENDER[28]` **逐字节复现** | **重渲染**（渲染器已摘除 m27 段） |
| 000731 美丰 / 000830 鲁西 | 手写 html（重渲染只剩 1,458 字，会丢内容） | **手术切除** 块区间 |

切除区间 = `<h3>估值敏感性</h3>` … `<h3>区间股价表现</h3>`（不含后者）。
块内含：引言段 + `目标价敏感性` 小标题 + 矩阵表 + `chartSens` 热力图 + 安全边际 logic + 其 src。

★ 连带清理（否则留下指向已删内容的悬空引用）：
  600459 槽 10 / 槽 31 各有一句引述「M27 敏感性矩阵」⇒ 改写为「估值与目标价分析」。
  ⚠️ 必须 **html 与 data_v31 双侧同步**：只改 html 的话，将来任何一次重渲染都会把它改回来。

★ 源头上还改了三处渲染器（report_build_v31.py）：
  m_val 摘掉 m27 段 / m26 的 logic 去掉指向 / chart_opts 停用 chartSens
  —— 只删调用不改 option，会让线上库留下没人引用的孤儿图。

只 PATCH 被改的那几个槽，**不重跑 push_reports_v31.py**（避免无谓重写另外 30 行、避免踩并发会话）。

用法：
    python _drop_sens.py                 # 干跑（只打印，不落盘、不联网）
    python _drop_sens.py --dump          # 把算好的新值落盘到 _ds_new/（仍不联网）
    python _drop_sens.py --apply         # 读 _ds_new/ → 漂移闸 → PATCH 线上 → 写本地 seed

★ 为什么拆成 --dump / --apply（2026-09-21 实测教训）：
  本环境的出网**间歇性不可用**（同一段代码同一秒跑，一次 SSL UNEXPECTED_EOF、一次 HTTP 200；
  有一次连续 8 次重试跨 84 秒全败，隔一分钟又全通）。实测已用 A/B 对照排除代码因素
  （独立小脚本 / `import` 本模块 / 读 4 份大 JSON / 渲染 4 次 —— 均与联网成败无关）。
  ⇒ 把「耗时的计算」与「联网写库」分开：算一次落盘，写库阶段只做 REST，
    失败重跑成本从 ~1 分钟降到 ~2 秒。
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import report_build_v31 as B                                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
BAK = os.path.join(HERE, 'backup')
DUMP = os.path.join(HERE, '_ds_new')
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudgateway.com/v1/rdb/rest/' % CFG['envId']

# 只把重渲染的槽 28 交给渲染器；手术的槽由 cut_block 处理。
RENDERED = ('600459', '002237')     # 槽 28 走重渲染
SURGERY = ('000731', '000830')      # 槽 28 走手术切除
CODES = RENDERED + SURGERY

# ── 跨槽悬空引用改写：(槽号, 旧串, 新串)。html 侧用文本替换。─────────────
TEXT_FIXES = {
    '600459': [
        ('10', 'M27 敏感性矩阵的基准为 ', '估值与目标价分析的基准为 '),
        ('31', '用于 M27 敏感性矩阵基准', '用于估值与目标价分析的基准'),
    ],
}

# ── data_v31 侧同样要改（否则重渲染会把引用带回来）。递归替换所有字符串值。──
DATA_FIXES = {
    '600459': [
        ('M27 敏感性矩阵的基准为 ', '估值与目标价分析的基准为 '),
        ('当前价 19.09 元对应 PE(TTM) 23.62 倍，'
         '落在 M27 敏感性矩阵的「PE 25x / 净利 -15%」与「PE 25x / 基准」之间（18.1~21.3 元）—— ',
         '当前价 19.09 元对应 PE(TTM) 23.62 倍 —— '),
        ('用于 M27 敏感性矩阵基准', '用于估值与目标价分析的基准'),
    ],
}

# 允许保留「敏感性」字样的槽（不是估值敏感性，是本模块自己的价格敏感测算）
KEEP_SENS_SLOTS = {'002237': {'12'}}

HEAD = '<h3>估值敏感性</h3>'
TAIL = '<h3>区间股价表现</h3>'


# ─────────────────────────────── 工具 ───────────────────────────────
def req(path, method='GET', body=None, tries=8):
    """REST 调用。★ 必须带重试：本轮实测沙箱侧网络**间歇性不可用**，
    同一段代码同一秒跑，一次 `SSL: UNEXPECTED_EOF_WHILE_READING`、一次 HTTP 200；
    有一次连续 5 次重试（跨约 30 秒）全败，隔一分钟又全通 ——
    属环境抖动，不是代码问题（已用 A/B 对照实验排除：独立脚本 / import / 渲染 / 读 JSON 均无关）。
    重试窗口 ≈ 3+6+9+12+15+18+21 = 84 秒，足以跨过短时抖动。
    PATCH 写的是**同一个值**，天然幂等，所以重试安全。"""
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    hdr = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
           'Accept': 'application/json', 'Content-Type': 'application/json'}
    last = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(BASE + path, data=data, headers=hdr, method=method)
            with urllib.request.urlopen(rq, timeout=120) as r:
                raw = r.read().decode('utf-8')
            return json.loads(raw) if raw.strip() else None
        except Exception as e:                                   # noqa: BLE001
            last = e
            wait = 3 * (i + 1)
            print('      · 请求失败（第 %d/%d 次）%s —— %ds 后重试'
                  % (i + 1, tries, type(e).__name__, wait))
            time.sleep(wait)
    raise SystemExit('✗ REST 连续 %d 次失败，放弃：%s' % (tries, last))


def apply_text_fixes(s, pairs, strict=True):
    """按 (旧, 新) 列表替换。幂等：旧串不在但新串在 ⇒ 视为已改过，跳过。

    ⚠️ strict 只对「整份文档级」调用成立（如单槽 html——旧串必须恰好出现过）。
       **递归遍历 data 时必须 strict=False**：data 里有几百个字符串，
       绝大多数自然不含目标串，逐个断言「必须命中」会立刻假失败。
       计数交给外层的 count_pairs()。
    """
    out = s
    for old, new in pairs:
        if old in out:
            out = out.replace(old, new)
        elif strict and new not in out:
            raise SystemExit('✗ 既找不到旧串也找不到新串，结构变了，停手：%r' % old[:60])
    return out


def walk_fix(obj, pairs):
    """递归替换 dict/list 里所有字符串值（不改键名）。宽松模式，不做命中断言。"""
    if isinstance(obj, dict):
        return {k: walk_fix(v, pairs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk_fix(v, pairs) for v in obj]
    if isinstance(obj, str):
        return apply_text_fixes(obj, pairs, strict=False)
    return obj


def count_pairs(obj, pairs):
    """统计 obj 里各「旧串」改前的命中次数（用于断言确实改到了东西）。"""
    texts = []

    def _w(o):
        if isinstance(o, dict):
            for v in o.values():
                _w(v)
        elif isinstance(o, list):
            for v in o:
                _w(v)
        elif isinstance(o, str):
            texts.append(o)
    _w(obj)
    blob = '\n'.join(texts)
    return {old: blob.count(old) for old, _new in pairs}


def cut_block(h):
    """切除「估值敏感性」块。幂等：标题已不在 ⇒ 原样返回。"""
    if HEAD not in h:
        return h                                     # ← 幂等早退（必须在断言之前）
    n = h.count(HEAD)
    if n != 1:
        raise SystemExit('✗「估值敏感性」标题出现 %d 次，应为 1 —— 停手' % n)
    s = h.find(HEAD)
    e = h.find(TAIL, s)
    if e < 0:
        raise SystemExit('✗ 找不到块尾「区间股价表现」—— 结构变了，停手')
    while s > 0 and h[s - 1] in ' \t\n':
        s -= 1
    while e > 0 and h[e - 1] in ' \t\n':
        e -= 1
    return h[:s] + '\n    ' + h[e:]


# ─────────────────────────────── 计划 ───────────────────────────────
def plan(code):
    """算出这家要写成什么。返回 (seed, data, new_mods, notes)。new_mods: {no: html}"""
    seed_p = os.path.join(SEED, 'report_%s.json' % code)
    data_p = os.path.join(SEED, 'data_v31_%s.json' % code)
    seed = json.load(io.open(seed_p, encoding='utf-8'))
    data = json.load(io.open(data_p, encoding='utf-8'))
    mods = {str(m['no']): m for m in seed['mods']}

    notes = []
    # 1) data 侧替换（幂等）
    if code in DATA_FIXES:
        cnt = count_pairs(data, DATA_FIXES[code])
        new_data = walk_fix(data, DATA_FIXES[code])
        if json.dumps(new_data, ensure_ascii=False, sort_keys=True) != \
           json.dumps(data, ensure_ascii=False, sort_keys=True):
            notes.append('data_v31：改写 %d 处悬空引用（%s）'
                         % (sum(cnt.values()),
                            '，'.join('%s×%d' % (o[:12], v) for o, v in cnt.items() if v)))
            data = new_data
        else:
            notes.append('data_v31：引用已就位（幂等）')

    new_mods = {}

    # 2) 槽 28
    h0 = mods['28']['html'] or ''
    if code in RENDERED:
        h1 = B.RENDER[28](data)
        notes.append('槽 28：重渲染（渲染器已摘除 m27 段）')
    else:
        h1 = cut_block(h0)
        notes.append('槽 28：手术切除「估值敏感性」块')
    if h1 != h0:
        new_mods['28'] = h1

    # 3) 跨槽引用改写
    for no, _old, _new in TEXT_FIXES.get(code, []):
        h = mods[no]['html'] or ''
        h2 = apply_text_fixes(h, [(o, n) for nn, o, n in TEXT_FIXES[code] if nn == no])
        if h2 != h:
            new_mods[no] = h2

    return seed, data, new_mods, notes


# ─────────────────────────────── 自检 ───────────────────────────────
def selfcheck(code, seed, data, new_mods, h_old28):
    errs = []
    mods = {str(m['no']): m for m in seed['mods']}
    h28 = new_mods.get('28', mods['28']['html'] or '')

    # ① 编号 1..31 完整
    nos = sorted(int(k) for k in mods)
    if nos != list(range(1, 32)):
        errs.append('模块编号不是 1..31：%s' % nos)

    # ② 槽 28 里不得再有敏感性内容 / chartSens 引用
    if '敏感性' in h28:
        errs.append('槽 28 仍含「敏感性」%d 处' % h28.count('敏感性'))
    if 'chartSens' in h28:
        errs.append('槽 28 仍引用 chartSens')

    # ③ 全报告：不得再有「敏感性矩阵」这个已删概念；
    #    「敏感性」只允许留在白名单槽（如 002237 槽 12 的价格敏感测算）
    whole = []
    for k in sorted(mods, key=lambda x: int(x)):
        h = new_mods.get(k, mods[k]['html'] or '')
        if '敏感性矩阵' in h:
            errs.append('槽 %s 仍有悬空引用「敏感性矩阵」' % k)
        if '敏感性' in h and k not in KEEP_SENS_SLOTS.get(code, set()):
            errs.append('槽 %s 仍含「敏感性」（不在白名单）' % k)
    #    data 侧也要干净
    ds = json.dumps(data, ensure_ascii=False)
    if '敏感性矩阵' in ds:
        errs.append('data_v31 仍有「敏感性矩阵」：%d 处' % ds.count('敏感性矩阵'))

    # ④ 槽 28 必须是「变小」的（摘除内容），且不能塌成空
    if len(h28) >= len(h_old28):
        errs.append('槽 28 没变短（%d → %d）—— 手术没生效？' % (len(h_old28), len(h28)))
    if len(h28) < 800:
        errs.append('槽 28 只剩 %d 字符，疑似把不该删的也删了' % len(h28))

    # ⑤ 幂等：同一份输入再来一次，结果必须一致
    if code in RENDERED:
        again = B.RENDER[28](data)
        if again != h28:
            errs.append('重渲染不幂等')
    else:
        if cut_block(h28) != h28:
            errs.append('cut_block 不幂等')

    # ⑥ 只动了预期的那几个槽
    allowed = {'28'} | {no for no, _o, _n in TEXT_FIXES.get(code, [])}
    stray = set(new_mods) - allowed
    if stray:
        errs.append('改到了预期外的槽：%s' % sorted(stray))
    return errs


# ─────────────────────────────── 主流程 ───────────────────────────────
def main():
    dump = '--dump' in sys.argv
    print('=' * 96)
    print('摘除「估值敏感性」小节 · 模式 = %s'
          % ('落盘到 _ds_new/（不联网）' if dump else '干跑（只打印）'))
    print('=' * 96)
    allerrs = {}
    plans = {}
    for code in CODES:
        seed, data, new_mods, notes = plan(code)
        h_old = {str(m['no']): m['html'] or '' for m in seed['mods']}['28']
        errs = selfcheck(code, seed, data, new_mods, h_old)
        allerrs[code] = errs
        plans[code] = (seed, data, new_mods)

        delta = sum(len(v) - len({str(m['no']): m['html'] or '' for m in seed['mods']}[k])
                    for k, v in new_mods.items())
        print()
        print('【%s】改动 %d 个槽 · 合计 %+d 字符' % (code, len(new_mods), delta))
        for no in sorted(new_mods, key=lambda x: int(x)):
            old_h = {str(m['no']): m['html'] or '' for m in seed['mods']}[no]
            print('   槽%-3s %5d → %5d 字符 (%+d)' % (no, len(old_h), len(new_mods[no]),
                                                      len(new_mods[no]) - len(old_h)))
        for n in notes:
            print('   · %s' % n)
        if new_mods.get('28'):
            print('   槽28 新首 130 字：%s' % new_mods['28'][:130].replace('\n', ' '))
            print('   槽28 新尾 130 字：%s' % new_mods['28'][-130:].replace('\n', ' '))
        print('   自检：%s' % ('✅ 全过' if not errs else '❌ ' + ' ／ '.join(errs)))

    bad = [c for c in CODES if allerrs[c]]
    if bad:
        print()
        print('=' * 96)
        print('✗ 有自检失败，不写盘：%s' % bad)
        return 1

    print()
    print('=' * 96)
    print('✓ 四家自检全过')

    if dump:
        os.makedirs(DUMP, exist_ok=True)
        for code in CODES:
            seed, data, new_mods = plans[code]
            old_mods = [{'no': m['no'], 'html': m['html'] or ''} for m in seed['mods']]
            for m in seed['mods']:
                k = str(m['no'])
                if k in new_mods:
                    m['html'] = new_mods[k]
            p = os.path.join(DUMP, '%s.json' % code)
            io.open(p, 'w', encoding='utf-8').write(json.dumps(
                {'code': code, 'mods': new_mods, 'seed_old_mods': old_mods,
                 'seed': seed, 'data': data}, ensure_ascii=False))
            print('  dump → %-18s（%d 个槽待写）'
                  % (os.path.basename(p), len(new_mods)))
        print()
        print('下一步：python _ds_apply.py            # 联网写库（只做 REST，秒级）')
    print('=' * 96)
    print('完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
