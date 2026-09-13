# -*- coding: utf-8 -*-
"""抠出产物里每个 <script> 块，逐个 node --check；并查标签配对。"""
import io, os, re, subprocess, sys, tempfile

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'

ok_all = True
for f in ['deploy/index.html', 'deploy/report.html']:
    p = os.path.join(ROOT, f)
    s = io.open(p, encoding='utf-8').read()
    blocks = re.findall(r'<script[^>]*>([\s\S]*?)</script>', s)
    print('==== %s  %d 个 script 块' % (f, len(blocks)))
    for i, b in enumerate(blocks):
        tmp = os.path.join(ROOT, 'build', '_chk.js')
        io.open(tmp, 'w', encoding='utf-8').write(b)
        r = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
        os.remove(tmp)
        status = 'OK' if r.returncode == 0 else 'FAIL'
        if r.returncode != 0:
            ok_all = False
            print('  [%d] %s len=%d\n%s' % (i, status, len(b), r.stderr[:600]))
        else:
            print('  [%d] %s len=%d' % (i, status, len(b)))
    # 标签配对
    for tag in ['script', 'section', 'div', 'textarea', 'table', 'details']:
        o = len(re.findall(r'<' + tag + r'[\s>]', s))
        c = len(re.findall(r'</' + tag + r'>', s))
        if o != c:
            ok_all = False
            print('  !! <%s> 开 %d / 闭 %d 不配对' % (tag, o, c))
        else:
            print('  <%s> %d 配对 OK' % (tag, o))

print()
print('EXIT=' + ('0 全部通过' if ok_all else '1 有问题'))
sys.exit(0 if ok_all else 1)
