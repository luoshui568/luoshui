#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用写库前的备份（backup/report_<code>_pre_v31_<ts>.json）**逐字回滚**模块。

★ 为什么必须用备份、不能用 report_build_v31.py 重建 ——
  实测（2026-10-15 回滚）：600456 线上备份 43 张表，而从 data seed 重建只有 21 张。
  原因：**线上的模块 HTML 早就跟 data seed 脱钩了**（m3/m22 等经 mkmod3_std /
  mkchain_std 等后处理脚本改写，另有大量手工版式调整）。
  ⇒ 「重建 seed 再推」会把这些后处理成果**全部抹掉**，那才是真正的破坏。
  回滚只有一个正确姿势：**把备份里的 wb_report_mods 原文 PATCH 回库**。

用法：
    python3 build/rollback_from_backup.py600456            # 该code 最新一份 pre_v31 备份
    python3 build/rollback_from_backup.py --all# 全部 12 份
    python3 build/rollback_from_backup.py --list# 只列出可用备份
"""
import glob
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, 'backup')


def req(method, path, body=None):
    cfg = json.load(open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
    base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method, headers={
        'Authorization': 'Bearer ' + cfg['key'],
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'})
    with urllib.request.urlopen(r) as f:
        return f.status


def latest_backup(code):
    """该code 最新的 pre_v31 备份。"""
    fs = glob.glob(os.path.join(BACKUP, 'report_%s_pre_v31_*.json' % code))
    if not fs:
        return None
    return max(fs, key=os.path.getmtime)


def list_all():
    seen = {}
    for f in glob.glob(os.path.join(BACKUP, 'report_*_pre_v31_*.json')):
        code = os.path.basename(f).split('_')[1]
        if code not in seen or os.path.getmtime(f) > os.path.getmtime(seen[code]):
            seen[code] = f
    for c in sorted(seen):
        d = json.load(open(seen[c], encoding='utf-8'))
        mods = d.get('wb_report_mods') or []
        nt = sum((m.get('html') or '').count('<table') for m in mods)
        print('  %s  mods=%2d  表=%3d  %s' %
              (c, len(mods), nt, os.path.basename(seen[c])))
    return seen


def rollback(code, dry=False):
    f = latest_backup(code)
    if not f:
        print('  %s 无备份，跳过' % code)
        return False
    d = json.load(open(f, encoding='utf-8'))
    mods = d.get('wb_report_mods') or []
    if not mods:
        print('  %s 备份为空，跳过' % code)
        return False
    nt = sum((m.get('html') or '').count('<table') for m in mods)
    print('  %s ← %s（%d 模块 / %d 表）' % (code, os.path.basename(f), len(mods), nt))
    if dry:
        return True
    ok = 0
    for m in mods:
        # ★ 只 PATCH html，不动 no/seq/title —— 避免连带覆盖别的字段
        st = req('PATCH', 'wb_report_mods?id=eq.%s' % urllib.parse.quote(str(m['id'])),
                 {'html': m['html']})
        if st < 400:
            ok += 1
        else:
            print('    !! 模块 %s PATCH %s' % (m.get('no'), st))
    print('    回滚 %d/%d 模块' % (ok, len(mods)))
    return ok == len(mods)


def verify(code):
    """回读核对：与备份逐字比对。"""
    f = latest_backup(code)
    if not f:
        return False
    d = json.load(open(f, encoding='utf-8'))
    want = {str(m['no']): m['html'] for m in (d.get('wb_report_mods') or [])}
    cfg = json.load(open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
    base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    r = urllib.request.Request(
        base + 'wb_report_mods?report_id=eq.%s&select=no,html&order=seq.asc' % code,
        headers={'Authorization': 'Bearer ' + cfg['key']})
    with urllib.request.urlopen(r) as f:
        got = {str(m['no']): m['html'] for m in json.loads(f.read())}
    same = sum(1 for n in want if got.get(n) == want[n])
    nt = sum(v.count('<table') for v in got.values())
    print('    核对 %d/%d 一致，线上现表数 %d' % (same, len(want), nt))
    return same == len(want)


if __name__ == '__main__':
    import urllib.parse
    args = sys.argv[1:]
    if '--list' in args:
        print('可用备份：')
        list_all()
        raise SystemExit
    codes = (['000731', '000762', '000830', '002237', '002408', '600392',
              '600456', '600459', '601118', '601958', '603599', '603977']
             if '--all' in args else args)
    print('=== 回滚 %d 份 ===' % len(codes))
    for c in codes:
        rollback(c)
    print('=== 回读核对 ===')
    for c in codes:
        print('  %s' % c)
        verify(c)