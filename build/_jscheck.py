# -*- coding: utf-8 -*-
"""HTML 里的 <script> 块 → 逐个 `node --check`（语法闸）。

为什么需要它：这几个页面是「单文件 + 内联脚本」，Python 侧没有语法校验手段；
真跑起来才知道错的话，一次构建 + 上传就白搭了（上传是覆盖式、没有历史）。
`node --check` 只做语法（不执行、不需要 DOM），正好卡在「写完 → 构建 → 上线」之间。

用法： python _jscheck.py <html> [<html> ...]
"""
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
NODE = r'C:/Users/50522/.workbuddy/binaries/node/versions/22.22.2-3/node.exe'

#: 跳过带 src 的外链脚本（页面里没有，留个保险）
BLOCK = re.compile(r'<script([^>]*)>(.*?)</script>', re.S | re.I)


def blocks(html):
    out = []
    for i, (attrs, body) in enumerate(BLOCK.findall(html)):
        if 'src=' in attrs.lower():
            continue
        if not body.strip():
            continue
        out.append((i, body))
    return out


def main(paths):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if not os.path.exists(NODE):
        sys.exit('找不到 node：%s' % NODE)
    bad = 0
    for p in paths:
        html = io.open(p, encoding='utf-8').read()
        bl = blocks(html)
        print('=== %s（%d 个内联 script 块，%d 字节）'
              % (os.path.relpath(p, HERE), len(bl), len(html)))
        for idx, body in bl:
            fd, tmp = tempfile.mkstemp(suffix='.js', dir=HERE)
            os.close(fd)
            io.open(tmp, 'w', encoding='utf-8').write(body)
            r = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
            os.remove(tmp)
            tag = '块 #%d（%d 字节）' % (idx, len(body))
            if r.returncode == 0:
                print('  ✓ %s 语法通过' % tag)
            else:
                bad += 1
                print('  ✗ %s 语法错误：' % tag)
                print((r.stderr or r.stdout).strip()[:1500])
    print('结论：%s' % ('全部通过' if not bad else '%d 个块有问题' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['../deploy/report.template.html']))
