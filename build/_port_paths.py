#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把工作区里硬编码的 Windows 路径改写成当前机器（macOS）的实际路径。

设计要点
--------
1. 新路径**自动探测**，不写死：
     工作区 = 本脚本所在目录的上一级（build/ 的父目录）
     家目录 = Path.home()
2. **字节级二进制读写**，只替换路径、绝不触碰行尾（产物多为纯 CRLF，
   一旦按文本读写会被归一成 LF，造成大面积假差异）。
3. 只改文件名/内容属于代码与记忆的文件，不碰交付物 HTML。
4. 每个文件先备份 <name>.winbak，可整批回滚。
5. 幂等：跑第二遍应当 0 处改动。

用法
----
    python3 build/_port_paths.py            # 干跑，只报告将改什么
    python3 build/_port_paths.py --go       # 实际改写（自动备份）
    python3 build/_port_paths.py --rollback # 从 .winbak 还原
"""
import os, re, sys, shutil, subprocess
from pathlib import Path

# 从 __file__ 推导时才 resolve；环境变量覆盖时原样采用
# （否则在 Windows 上做模拟测试时，'/Users/x' 会被 resolve 成 'C:\\Users\\x'）
_ws_env, _hm_env = os.environ.get('PORT_WS'), os.environ.get('PORT_HOME')
WS   = Path(_ws_env) if _ws_env else Path(__file__).resolve().parent.parent
HOME = Path(_hm_env) if _hm_env else Path.home()

GO       = '--go' in sys.argv
ROLLBACK = '--rollback' in sys.argv

# ── 目标路径探测 ────────────────────────────────────────────
def which(*cands):
    for c in cands:
        p = shutil.which(c)
        if p:
            return p
    return None

def first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[0] if paths else ''

def env_or(key, *fallbacks):
    """环境变量优先（供模拟测试注入），否则按顺序取第一个非空值。"""
    v = os.environ.get(key)
    if v:
        return v
    for f in fallbacks:
        if f:
            return f
    return ''

PYTHON = env_or('PORT_PYTHON', sys.executable, which('python3', 'python'), '/usr/bin/python3')
GIT    = env_or('PORT_GIT',    which('git'), '/usr/bin/git')
NODE   = env_or('PORT_NODE',   which('node'), '/usr/local/bin/node')
# 无头截图用：Chrome 优先，其次 Edge（macOS 上两者都走 --headless=new）
CHROME = env_or('PORT_CHROME', which('google-chrome', 'chromium'), first_existing(
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
))

OLD_HOME = r'C:\Users\50522'
OLD_WS   = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'

OUT = []
def w(s=''):
    OUT.append(str(s)); print(s)

# ── 需扫描的文件 ────────────────────────────────────────────
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'out', 'fxbg', '_raw_b1',
             '_edgeprof', 'verify', 'backup_hosting_pre_x'}
EXTS = {'.py', '.js', '.mjs', '.sh', '.json', '.md', '.txt', '.css', '.html'}

# ⚠️ 绝不能改写这两个文件：它们体内的 Windows 路径是「匹配规则」与「测试样本」，
#    改掉就等于自毁规则（下次运行再也匹配不到任何东西）。
SELF_SKIP = {'_port_paths.py', '_port_paths_test.py'}

def iter_files():
    for root, dirs, files in os.walk(WS):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not d.startswith('backup_hosting_pre_')]
        for f in files:
            if f in SELF_SKIP:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in EXTS or f.endswith('.winbak') or f.endswith('.db'):
                continue
            p = Path(root) / f
            try:
                if p.stat().st_size > 8 * 1024 * 1024:      # 超大文件跳过（内联库）
                    continue
            except OSError:
                continue
            yield p, os.path.relpath(p, WS).replace('\\', '/')

# ── 替换规则 ────────────────────────────────────────────────
# 三种书写形态，各自捕获「C:\Users\50522」之后的那一段。
#
# ⚠️ 关键设计：用**单条 alternation 正则 + finditer 手工拼接**，只扫一遍原文。
#    绝不能写成 RE_ESC.sub() → RE_RAW.sub() → RE_FWD.sub() 三轮串行 ——
#    第一轮的产物会被后两轮再次匹配（若新路径里恰好还有 'C:' 字样就会
#    无限增殖）。这个问题是端到端模拟跑出来的，不是推测。
RE_ALL = re.compile(
    rb'c:\\\\users\\\\50522((?:\\\\[^\\\'"\s<>|,;)\]}]+)*)'   # 'C:\\Users\\50522\\...'
    rb'|'
    rb'c:\\users\\50522((?:\\[^\\\'"\s<>|,;)\]}]+)*)'         # r'C:\Users\50522\...'
    rb'|'
    rb'c:/users/50522((?:/[^\'"\s<>|,;)\]}]+)*)',             # 'C:/Users/50522/...'
    re.I)

WS_TAIL = '/WorkBuddy/2026-09-10-14-50-38'      # 归一化后的工作区尾部
BIN_MAP = {                                     # 运行时二进制 → 本机可执行文件
    '.workbuddy/binaries/python':       PYTHON,
    '.workbuddy/binaries/portablegit':  GIT,
    '.workbuddy/binaries/git':          GIT,
    '.workbuddy/binaries/node':         NODE,
}

# 含空格的固定路径（不在用户目录下，上面的正则覆盖不到）
LITERALS = []
for _e in (r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
           r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
           r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
           r'C:/Program Files/Microsoft/Edge/Application/msedge.exe'):
    LITERALS.append((_e.encode(), CHROME.encode()))
    LITERALS.append((_e.replace('\\', '\\\\').encode(), CHROME.encode()))

def to_posix(tail_b: bytes) -> str:
    """捕获片段（含转义反斜杠）→ posix 路径片段。"""
    s = tail_b.decode('utf-8', 'replace')
    return s.replace('\\\\', '/').replace('\\', '/')

def map_one(tail: str) -> bytes:
    """把'旧家目录之后的那一段'翻译成本机绝对路径。"""
    low = tail.lower()
    for k, v in BIN_MAP.items():
        if k in low:
            return v.encode()
    if low.startswith(WS_TAIL.lower()):
        rest = tail[len(WS_TAIL):]
        return (WS.as_posix().rstrip('/') + rest).encode()
    return (HOME.as_posix().rstrip('/') + tail).encode()

def rewrite(data: bytes):
    """返回 (新数据, 改动次数)。单遍扫描原文，替换结果不再被扫描。"""
    n = 0
    out, last = bytearray(), 0
    for m in RE_ALL.finditer(data):
        tail = m.group(1) or m.group(2) or m.group(3) or b''
        out += data[last:m.start()]
        out += map_one(to_posix(tail))
        last = m.end()
        n += 1
    out += data[last:]
    data = bytes(out)
    # 固定路径字面替换放在之后：它们的产物不含新路径，不会自我匹配
    for old, new in LITERALS:
        c = data.count(old)
        if c:
            data = data.replace(old, new)
            n += c
    return data, n

def scan(data: bytes) -> int:
    return len(RE_ALL.findall(data))

# ── 主流程 ──────────────────────────────────────────────────
def main():
    if ROLLBACK:
        cnt = 0
        for p, _ in iter_files():
            b = Path(str(p) + '.winbak')
            if b.exists():
                shutil.move(str(b), str(p)); cnt += 1
        w('回滚完成：还原 %d 个文件' % cnt)
        return

    w('=' * 70)
    w('macOS 路径移植' + ('   【实际改写】' if GO else '   【干跑 — 只报告】'))
    w('=' * 70)
    w('  探测到的目标路径：')
    w('    工作区  %s' % WS)
    w('    家目录  %s' % HOME)
    w('    python  %s' % PYTHON)
    w('    git     %s' % GIT)
    w('    node    %s' % NODE)
    w('    chrome  %s  %s' % (CHROME, '（存在）' if os.path.exists(CHROME) else '（未找到，截图功能将不可用）'))
    w()

    hits, total = [], 0
    for p, rel in iter_files():
        try:
            c = scan(p.read_bytes())
        except OSError:
            continue
        if c:
            hits.append((c, p, rel)); total += c

    hits.sort(key=lambda x: -x[0])
    w('  命中 %d 个文件，共 %d 处 Windows 路径' % (len(hits), total))
    w()
    for c, p, rel in hits[:40]:
        w('    %4d 处  %s' % (c, rel))
    if len(hits) > 40:
        w('    ... 其余 %d 个文件' % (len(hits) - 40))
    w()

    if not GO:
        w('=' * 70)
        w('干跑结束。加 --go 实际改写（每个文件自动备份为 *.winbak）')
        return

    # 改写前的语法基线：工作区里有几个历史遗留的坏脚本，
    # 不能把它们算作「本轮改写造成的损坏」。
    def syntax_bad():
        badset = set()
        for _p, _rel in iter_files():
            if _p.suffix != '.py':
                continue
            try:
                compile(_p.read_bytes(), str(_p), 'exec')
            except Exception:
                badset.add(_rel)
        return badset

    pre_bad = syntax_bad()

    changed, skipped = 0, 0
    for c, p, rel in hits:
        data = p.read_bytes()
        new, n = rewrite(data)
        if new == data:
            skipped += 1
            continue
        shutil.copy2(p, str(p) + '.winbak')
        p.write_bytes(new)
        changed += 1

    w('=' * 70)
    w('已改写 %d 个文件（%d 个匹配到但内容无变化），备份后缀 .winbak' % (changed, skipped))
    w('回滚：python3 build/_port_paths.py --rollback')

    left = sum(scan(p.read_bytes()) for p, _ in iter_files() if p.exists())
    w()
    w('自检：改写后残留 %d 处 —— %s' % (left, '通过' if left == 0 else '仍有残留，请检查'))

    # 语法体检只关心「本轮新增」的错误
    post_bad = syntax_bad()
    new_bad = sorted(post_bad - pre_bad)
    npy = sum(1 for p, _ in iter_files() if p.suffix == '.py')
    w('语法体检：%d 个 .py 文件' % npy)
    if pre_bad:
        w('    改写前就已损坏 %d 个（历史遗留，非本轮造成）：%s'
          % (len(pre_bad), ', '.join(sorted(pre_bad)[:5])))
    if new_bad:
        w('    ❌ 本轮新增语法错误 %d 个：' % len(new_bad))
        for v in new_bad[:10]:
            w('        ✗ %s' % v)
    else:
        w('    ✅ 本轮未引入任何语法错误')

    # 报告落在 build/ 下（该目录的 _* 已被 .gitignore 忽略，不污染仓库）
    (WS / 'build' / '_port_paths_report.txt').write_text('\n'.join(OUT), encoding='utf-8')


if __name__ == '__main__' and not os.environ.get('PORT_PATHS_LIB'):
    main()
