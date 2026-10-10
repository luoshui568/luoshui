# -*- coding: utf-8 -*-
"""把 _sc_test.py 在 10 家上挨个跑一遍，汇总「通过/失败 + 断言条数」。

★ 只跑一家会漏掉「这家特有形态」的问题（600456 的笔误、各家不同的分数分布都踩过），
  所以固定全量跑。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']

tot_ok = tot_bad = 0
fails = []
for code in ALL:
    r = subprocess.run([PY, '-u', os.path.join(HERE, '_sc_test.py'), '--code', code],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    ok = out.count('✓')
    bad = out.count('✗')
    tot_ok += ok
    tot_bad += bad
    verdict = '✅' if (bad == 0 and '全部通过' in out) else '❌'
    if verdict == '❌':
        fails.append(code)
    warn = ''
    m = re.search(r'⚠ (.+)', out)
    if m and 'sc-val' in m.group(1):
        warn = '  ⚠ 取值来源改判'
    print('%s %-7s 断言 %2d 通过 / %d 失败%s' % (verdict, code, ok, bad, warn))
    if bad:
        for line in out.split('\n'):
            if '✗' in line:
                print('        %s' % line.strip())

print()
print('合计：%d 条通过 / %d 条失败' % (tot_ok, tot_bad))
if fails:
    print('未通过：%s' % ' '.join(fails))
    sys.exit(1)
print('10 家全部通过 ✅')
