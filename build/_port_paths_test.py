# -*- coding: utf-8 -*-
"""模拟 macOS 环境，验证 _port_paths.py 的替换逻辑。

在 Windows 上跑（我们的开发机），但把 PORT_WS / PORT_HOME 指到假想的 Mac 路径，
从而在没有 Mac 的情况下先把替换规则测通。
"""
import os, sys, io

os.environ['PORT_PATHS_LIB'] = '1'
os.environ['PORT_WS']   = '/Users/luoshui/WorkBuddy/luoshui'
os.environ['PORT_HOME'] = '/Users/luoshui'
sys.path.insert(0, r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build')
import _port_paths as PP

# 本机(Windows)的 sys.executable 恰好也含 C:\Users\50522\...，会让
# 「运行时二进制」用例出现假幂等失败。注入一个真实的 Mac 解释器路径来测。
PP.BIN_MAP['.workbuddy/binaries/python'] = '/usr/local/bin/python3'
PP.BIN_MAP['.workbuddy/binaries/portablegit'] = '/usr/bin/git'
PP.CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

CASES = [
    # (说明, 输入字节, 期望输出字节)
    ('Python raw 字符串',
     rb"R = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'",
     b"R = r'/Users/luoshui/WorkBuddy/luoshui'"),

    ('Python 转义字符串',
     rb"R = 'C:\\Users\\50522\\WorkBuddy\\2026-09-10-14-50-38\\build\\seed'",
     b"R = '/Users/luoshui/WorkBuddy/luoshui/build/seed'"),

    ('正斜杠写法',
     rb"p = 'C:/Users/50522/WorkBuddy/2026-09-10-14-50-38/deliver'",
     b"p = '/Users/luoshui/WorkBuddy/luoshui/deliver'"),

    ('小写盘符',
     rb"p = r'c:\users\50522\WorkBuddy\2026-09-10-14-50-38'",
     b"p = r'/Users/luoshui/WorkBuddy/luoshui'"),

    ('HOME 下的 .workbuddy（非工作区）',
     rb"m = r'C:\Users\50522\.workbuddy\memory\MEMORY.md'",
     b"m = r'/Users/luoshui/.workbuddy/memory/MEMORY.md'"),

    ('HOME 下的技能目录',
     rb"s = 'C:\\Users\\50522\\.workbuddy\\skills\\repo-github-sync'",
     b"s = '/Users/luoshui/.workbuddy/skills/repo-github-sync'"),

    ('运行时 python.exe → 本机解释器（r 前缀保留）',
     rb"PY = r'C:\Users\50522\.workbuddy\binaries\python\versions\3.13.12\python.exe'",
     b"PY = r'/usr/local/bin/python3'"),

    ('JS 里的裸反斜杠路径',
     b'var p = "C:\\\\Users\\\\50522\\\\WorkBuddy\\\\2026-09-10-14-50-38\\\\deploy";',
     b'var p = "/Users/luoshui/WorkBuddy/luoshui/deploy";'),

    ('Edge 路径 → Chrome（r 前缀保留）',
     rb"E = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'",
     b"E = r'" + PP.CHROME.encode() + b"'"),

    ('无关内容不得改动',
     b"x = 1\ny = 'hello'\nprint(x)",
     b"x = 1\ny = 'hello'\nprint(x)"),

    ('CRLF 必须原样保留（不得归一成 LF）',
     b"a = r'C:\\Users\\50522\\WorkBuddy\\2026-09-10-14-50-38'\r\nb = 2\r\n",
     b"a = r'/Users/luoshui/WorkBuddy/luoshui'\r\nb = 2\r\n"),
]

ok = bad = 0
log = []
for name, src, want in CASES:
    got, n = PP.rewrite(src)
    pass_ = (got == want)
    ok += pass_; bad += (not pass_)
    log.append('%s %s  (替换 %d 处)' % ('✅' if pass_ else '❌', name, n))
    if not pass_:
        log.append('     输入: %r' % src)
        log.append('     得到: %r' % got)
        log.append('     期望: %r' % want)

# 幂等性：对已替换过的内容再跑一次，应当 0 改动
idem_fail = []
for name, src, want in CASES:
    got, _ = PP.rewrite(src)
    again, n2 = PP.rewrite(got)
    if n2 != 0 or again != got:
        idem_fail.append('%s（第二遍又改了 %d 处）' % (name, n2))

log.append('')
log.append('通过 %d / %d' % (ok, ok + bad))
log.append('幂等检查：%s' % ('全部通过' if not idem_fail else '；'.join(idem_fail)))

print('\n'.join(log))
