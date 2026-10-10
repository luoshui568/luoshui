# -*- coding: utf-8 -*-
"""把 600459 第 29 槽的 ⑦行业地位 / ⑧管理层与治理 / ⑩估值吸引力 置为空白。

★ 依据：该槽**自己的引言**就写着
    「必须依赖一手来源（行业地位、治理、估值分位）的项目标 [MISSING] 并**从分母中剔除**」
  ⇒ 当前填了分反而是**自相矛盾**。改成空白 = 让文档与它自己声明的规则一致，
  同时与 002237（已经是空白状态，用户认可）形态统一。

★ 为什么不走 push_reports_v31.py：改单模块只 PATCH `wb_report_mods`，
  避免把另外 30 行无谓地重写一遍（并发会话可能正在改别家）。

自检：
  ① 三个目标行各只匹配 1 次（匹配数不是 1 就直接 SystemExit）
  ② 变换幂等：build(build(x)) == build(x)
  ③ 除这三个行 + 合计行外，其余字符**逐字节不变**
  ④ 变换后 [MISSING] 计数 == 7（与 002237 同型：三行×2 + 引言 1）
  ⑤ 写前：线上 html 必须与本地 seed 一字不差（漂移闸）
  ⑥ 写后回读：线上 html == 新值

用法：
    python _blank29.py            # 干跑
    python _blank29.py --go       # 备份 + PATCH 线上 + 写回本地 seed
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
CODE = '600459'
NO = '29'
SPAN = '<span style="color:#a3122a">[MISSING]</span>'
# ⚠️ 只用编号当锚点会撞车：本槽还有第二张表「十项选股原则适用性」，
#    里面也有 ①..⑩（如「⑦ 总市值 < 200 亿」）。⇒ 必须「编号 + 项名」双锚点。
LABELS = ('⑦ 行业地位', '⑧ 管理层与治理', '⑩ 估值吸引力')


def req(path, method='GET', body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    rq = urllib.request.Request(BASE + path, data=data, headers=HDR, method=method)
    with urllib.request.urlopen(rq, timeout=120) as r:
        raw = r.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else None


def build(h):
    """把三行置空 + 修合计行。纯函数、幂等。"""
    out = h
    for lab in LABELS:
        pat = re.compile(r'(<tr><td>' + lab + r'[^<]*</td><td>[^<]*</td>)'
                         r'<td>.*?</td><td>.*?</td>(</tr>)', re.S)
        n = len(pat.findall(out))
        if n != 1:
            raise SystemExit('✗ 槽 %s 的「%s」行匹配 %d 次，应为 1 —— 结构变了，停手'
                             % (NO, lab, n))
        out = pat.sub(lambda m: m.group(1)
                      + '<td>%s</td><td>%s</td>' % (SPAN, SPAN) + m.group(2), out)
    # 合计行：分母 98 → 68（剔除三项×10），未计分 0 → 3
    old = '<b>已计分项合计：60 / 98 = 61.2%</b>（折算百分制 61.2）。未计分 0 项'
    new = '<b>已计分项合计：60 / 68 = 88.2%</b>（折算百分制 88.2）。未计分 3 项'
    if old in out:
        out = out.replace(old, new)
    elif new not in out:
        raise SystemExit('✗ 合计行既不是旧值也不是新值 —— 停手（人工看一眼）')
    return out


def main():
    go = '--go' in sys.argv
    seed_p = os.path.join(SEED, 'report_%s.json' % CODE)
    seed = json.load(io.open(seed_p, encoding='utf-8'))
    mods = {str(m['no']): m for m in seed['mods']}
    h0 = mods[NO]['html']
    h1 = build(h0)

    errs = []
    # ② 幂等
    if build(h1) != h1:
        errs.append('变换不幂等')
    # ④ MISSING 计数
    if h1.count('[MISSING]') != 7:
        errs.append('[MISSING] 计数 %d，应为 7（三行×2 + 引言 1）' % h1.count('[MISSING]'))
    # ③ 其余字符不变：把被替换的三个行与合计行抠掉后比长度
    def strip(h):
        s = re.sub(r'<tr><td>[⑦⑧⑩][^<]*</td>.*?</tr>', '<tr/>', h, flags=re.S)
        s = re.sub(r'已计分项合计：\d+ / \d+ = [\d.]+%</b>（折算百分制 [\d.]+）。未计分 \d+ 项',
                   'TOTAL', s)
        return s
    if strip(h0) != strip(h1):
        errs.append('替换范围超出了「三个目标行 + 合计行」')

    print('=' * 74)
    print('%s 槽 %s ｜ %d → %d 字符 ｜ [MISSING] %d → %d'
          % (CODE, NO, len(h0), len(h1), h0.count('[MISSING]'), h1.count('[MISSING]')))
    for lab in LABELS:
        old = re.search(r'<tr><td>' + lab + r'[^<]*</td>.*?</tr>', h0, re.S).group(0)
        new = re.search(r'<tr><td>' + lab + r'[^<]*</td>.*?</tr>', h1, re.S).group(0)
        print('  %s 行：%s' % (lab, new.replace('\n', ' ')[:170]))
    print('  合计行：%s' % re.search(r'<b>已计分项合计[^<]*</b>[^<]*。未计分[^；]*；', h1,
                                    re.S).group(0))

    # ⑤ 漂移闸：线上必须与本地一字不差
    live = req('wb_report_mods?select=html,up&report_id=eq.%s&no=eq.%s' % (CODE, NO))
    if not live:
        errs.append('线上读不到 %s 的第 %s 模块' % (CODE, NO))
    elif (live[0].get('html') or '') != h0:
        errs.append('★ 漂移：线上 html 与本地 seed 不一致（长度 %d vs %d）—— 拒绝覆盖'
                    % (len(live[0].get('html') or ''), len(h0)))
    else:
        print('  漂移闸：线上 == 本地 seed（%d 字符）· 线上 up=%s'
              % (len(h0), live[0].get('up')))

    if errs:
        print('  ✗ 自检失败：')
        for e in errs:
            print('     - %s' % e)
        print('=' * 74)
        return 1
    print('  ✓ 自检全过（三行各命中 1 次 · 幂等 · 替换范围精确 · MISSING=7 · 无漂移）')

    if go:
        os.makedirs(BAK, exist_ok=True)
        ts = time.strftime('%Y%m%d-%H%M%S')
        b = os.path.join(BAK, 'report_%s_pre_blank29_%s.json' % (CODE, ts))
        shutil.copy2(seed_p, b)
        print('  备份 → %s' % os.path.basename(b))
        mods[NO]['html'] = h1
        seed['mods'] = [mods[str(m['no'])] for m in seed['mods']]
        r = req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (CODE, NO), 'PATCH',
                {'html': h1, 'up': int(time.time() * 1000)})
        print('  PATCH 线上：影响 %d 行' % (len(r) if isinstance(r, list) else -1))
        io.open(seed_p, 'w', encoding='utf-8').write(json.dumps(seed, ensure_ascii=False))
        print('  写回本地 seed/report_%s.json（%s）'
              % (CODE, hashlib.md5(io.open(seed_p, 'rb').read()).hexdigest()[:12]))
        back = req('wb_report_mods?select=html&report_id=eq.%s&no=eq.%s' % (CODE, NO))
        ok = (back[0].get('html') or '') == h1
        print('  回读核对：线上 == 新值 → %s' % ('✓' if ok else '✗'))
        if not ok:
            print('=' * 74)
            return 1
    print('=' * 74)
    print('模式：%s' % ('写盘' if go else '干跑'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
