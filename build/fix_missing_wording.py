#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清掉 m31 里「提及 MISSING 这个词」的文案，让 [MISSING] 计数回归「真缺口」语义。

背景：`report_build_v31.py` 的免责声明**早已**改成
      「未取到的字段一律标注为 MISSING 占位并在跟踪清单中列出补齐路径」（**不带方括号**），
      但早先渲染的 7 份报告库里存的仍是旧句「一律标 [MISSING] 并在跟踪清单中列出补齐路径」。
      于是 `[MISSING]` 这几个字**出现在正文里**，被探针当成数据缺口统计 —— 属误报。

⚠️ 只动 m31，且**只替换句式**；m25 表格单元格里的 `<td>[MISSING]</td>`、
   m8 的真缺口标记一律**不动**（那些是「确实没取到数」的正确标注）。

用法：
    python3 fix_missing_wording.py            # 干跑，列出将要改的
    python3 fix_missing_wording.py --go       # 写库
"""
import io, json, os, re, sys, urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}
GO = '--go' in sys.argv

#: 精确替换表 —— 「提到 MISSING 这个词」的句式 → 不带方括号的说法
RULES = [
    ('一律标 [MISSING] 并在跟踪清单中列出补齐路径',
     '一律标注为 MISSING 占位并在跟踪清单中列出补齐路径'),
    ('一律标 [MISSING] 并', '一律标注为 MISSING 占位并'),
    ('标记为 [MISSING] 并从评分分母中剔除',
     '标记为 MISSING 占位并从评分分母中剔除'),
    ('标记为 [MISSING]', '标记为 MISSING 占位'),
    ('标为 [MISSING]', '标为 MISSING 占位'),
]


def get(path):
    rq = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(rq, timeout=120) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def patch_mod(code, html):
    body = json.dumps({'html': html}, ensure_ascii=False).encode('utf-8')
    rq = urllib.request.Request(BASE + 'wb_report_mods?id=eq.%s_m31' % code,
                                data=body, headers=HDR, method='PATCH')
    with urllib.request.urlopen(rq, timeout=120) as r:
        return r.status


def main():
    seed_dir = os.path.join(B, 'seed')
    codes = sorted({f[7:13] for f in os.listdir(seed_dir)
                    if f.startswith('report_') and f.endswith('.json')
                    and not f.endswith('_v23.json') and f[7:13].isdigit()})
    print('扫描 %d 份的 m31 ……\n' % len(codes))
    n_fix = 0
    for code in codes:
        rows = get('wb_report_mods?report_id=eq.%s&no=eq.31&select=html' % code)
        if not rows:
            print('  %-8s 无 m31' % code)
            continue
        h = rows[0]['html'] or ''
        new, hits = h, []
        for a, b in RULES:
            if a in new:
                hits.append(a)
                new = new.replace(a, b)
        if not hits:
            print('  %-8s m31 无「提及 MISSING」的文案（[MISSING] 计数 %d —— 若有则都是真缺口）'
                  % (code, h.count('[MISSING]')))
            continue
        print('  %-8s 命中 %d 条规则 ｜ [MISSING] %d → %d'
              % (code, len(hits), h.count('[MISSING]'), new.count('[MISSING]')))
        for a in hits:
            print('         · %s' % a)
        if GO:
            st = patch_mod(code, new)
            back = get('wb_report_mods?report_id=eq.%s&no=eq.31&select=html' % code)[0]['html']
            ok = ('[MISSING]' not in back and 'MISSING 占位' in back)
            print('         写库 HTTP %s ｜ 回读校验 %s' % (st, '✅' if ok else '❌ 仍含 [MISSING]'))
            if not ok:
                continue
        n_fix += 1
    print()
    print('%s：共 %d 份需要改' % ('已写库' if GO else '干跑（加 --go 写库）', n_fix))


if __name__ == '__main__':
    main()
