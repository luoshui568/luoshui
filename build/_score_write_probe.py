# -*- coding: utf-8 -*-
"""槽 29 落库通道 —— 线上端到端写入验证（**零业务内容变更**）

────────────────────────────────────────────────────────────────────────
【为什么不能只写「完全一样的内容」就完事】
`Prefer: return=minimal` 的 PATCH 回 204，**无论更新了 1 行还是 0 行都回 204**。
所以「写回原文 + 读回原文」这种探针有个致命盲点：
    「RLS 的 USING 把这一行滤掉了 ⇒ 0 行被更新」与「更新了 1 行但值没变」
    在回读时长得一模一样。
⇒ 判据必须换成 **`Prefer: return=representation`** —— 让 PostgREST 把**受影响的行**回显出来：
    返回 `[]`      ⇒ 一行都没命中（写通道实际不通）
    返回 1 行      ⇒ 真的更新到了那一行（这才是「通了」的证据）

【为什么可用「写回原文」而不是改一个真分值】
写回原文 ⇒ 业务内容零变更（分数、总分、评级、KPI、逐项说明全不动），
但上面那条 `return=representation` 仍然给出「命中 1 行」的确证。
两全：既有证据，又不碰用户看得见的数据。

【判据清单（任何一条不过就报错，不掩盖）】
  ① PATCH 回显 = 1 行，且该行 html 与原文**逐字节相同**
  ② 回读该槽：html / no / title / seq / t / up **全部不变**（零副作用）
  ③ 该报告其余 30 个模块的 (id, md5) **一个不变**（只碰了这一槽）
  ④ 另外 9 家的槽 29 html md5 全不变（没误伤）
  ⑤ 写完再跑一次「原分手术」：产出仍与线上逐字节相同（幂等未被破坏）

用法：
    python _score_write_probe.py 002408          # 只读干跑（默认）
    python _score_write_probe.py 002408 --go     # 真打一次 PATCH（内容不变）
"""
import hashlib
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import _score_patch as SP                                          # noqa: E402
from _apply_score import req, BAK, NO                              # noqa: E402

ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']


def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:12]


def snapshot(code):
    """该报告全部模块的 (no → md5(html)) —— 用来证明「只动了目标那一槽」。"""
    rows = req('wb_report_mods?report_id=eq.%s&select=no,html' % code)
    return {str(r['no']): md5(r.get('html') or '') for r in rows}


def main(argv):
    code = next((a for a in argv if a.isdigit() and len(a) == 6), '002408')
    go = '--go' in argv
    bad = []

    def chk(okc, msg):
        print('  %s %s' % ('✅' if okc else '❌', msg))
        if not okc:
            bad.append(msg)

    print('槽 29 落库通道 · 线上写入验证 ｜ 模式：%s ｜ 目标 %s'
          % ('真写一次（内容不变）' if go else '只读干跑', code))
    print('判据：Prefer: return=representation 回显受影响行 —— 写通道真的通才回得来\n')

    before = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=*' % (code, NO))
    if not before:
        print('✗ 线上没有 %s 的槽 %s' % (code, NO))
        return 1
    b = before[0]
    h0 = b.get('html') or ''
    others0 = snapshot(code)
    peers0 = {c: md5((req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=html'
                          % (c, NO)) or [{}])[0].get('html') or '') for c in ALL}
    print('① 取原文：id=%s ｜ html %d 字节 md5=%s ｜ no=%s seq=%s'
          % (b.get('id'), len(h0), md5(h0), b.get('no'), b.get('seq')))
    print('   该报告共 %d 个模块；t=%s up=%s\n' % (len(others0), b.get('t'), b.get('up')))

    if not go:
        print('（干跑：不发 PATCH。加 --go 才真打一次「内容不变」的写）')
        return 0

    # —— 真打一次：内容原样回写，要回显受影响行 ——
    t0 = time.strftime('%Y%m%d_%H%M%S')
    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    bp = os.path.join(BAK, 'm29_%s_PRE_WRITEPROBE_%s.html' % (code, t0))
    io.open(bp, 'w', encoding='utf-8', newline='').write(h0)
    print('② 备份原文 → %s' % os.path.basename(bp))

    echo = req('wb_report_mods?id=eq.%s' % b['id'], 'PATCH',
               {'html': h0}, prefer='return=representation')
    n_echo = len(echo) if isinstance(echo, list) else -1
    chk(n_echo == 1,
        '③ PATCH 回显受影响行数 = %s（必须 1：0 表示 RLS 把这一行滤掉了、写通道其实不通）'
        % n_echo)
    if n_echo == 1:
        chk((echo[0].get('html') or '') == h0,
            '④ 回显行的 html 与原文逐字节相同（%s）' % md5(echo[0].get('html') or ''))

    # —— 回读：零副作用 ——
    after = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=*' % (code, NO))[0]
    h1 = after.get('html') or ''
    chk(h1 == h0, '⑤ 回读 html 逐字节不变（%d → %d 字节）' % (len(h0), len(h1)))
    for k in ('id', 'no', 'title', 'seq', 'report_id', 'code', 't', 'up'):
        chk(after.get(k) == b.get(k),
            '⑥ 字段 %s 未被动过（%r）' % (k, str(after.get(k))[:40]))

    # —— 只动这一槽 ——
    others1 = snapshot(code)
    diff_keys = [k for k in set(list(others0) + list(others1))
                 if others0.get(k) != others1.get(k)]
    chk(not diff_keys,
        '⑦ 该报告其余 %d 个模块一个字节没动（差异槽：%s）'
        % (len(others0) - 1, diff_keys or '无'))

    # —— 没误伤别的报告 ——
    peers1 = {c: md5((req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=html'
                          % (c, NO)) or [{}])[0].get('html') or '') for c in ALL}
    hurt = [c for c in ALL if peers0[c] != peers1[c]]
    chk(not hurt, '⑧ 另外 9 家槽 29 全不变（被误伤：%s）' % (hurt or '无'))

    # —— 幂等未被破坏 ——
    sc, src, w = SP.parse_scores(h1)
    made, meta = SP.apply_scores(h1, sc)
    chk(made == h1, '⑨ 写完仍满足「原分手术逐字节幂等」（总分 %s / %s）'
        % (meta['total'], meta['rating']))

    print('\n结论：%s' % ('写入通道端到端通过 ✅（内容零变更）' if not bad else '有不通过项，见上 ❌'))
    for x in bad:
        print('  ✗ %s' % x)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
