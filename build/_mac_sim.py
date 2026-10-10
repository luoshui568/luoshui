# -*- coding: utf-8 -*-
"""端到端模拟：解包 → 铺开 → 路径改写 → 独立复核。

要点：模拟工作区**不能**放在含 'C:\\Users\\50522' 的路径下，否则替换出的
新路径又会命中正则（自指），把模拟搅乱。这里刻意选 C:\\Users\\Public 下，
并注入 Mac 侧的可执行文件路径，尽量贴近真机行为。
"""
import os, sys, io, re, tarfile, shutil, tempfile, subprocess
from pathlib import Path

R    = str(Path(__file__).resolve().parent.parent)
OUT  = os.path.join(R, 'deliver', 'mac-mini')
MAIN = os.path.join(OUT, 'luoshui-workspace.tar.gz')
PY   = sys.executable

BASE = os.path.join('C:\\Users\\Public', 'macsim_' + next(tempfile._get_candidate_names()))
TMP      = BASE
SIM_WS   = os.path.join(BASE, 'WorkBuddy', 'luoshui')   # 模拟 Mac 工作区
SIM_HOME = os.path.join(BASE, 'home', 'luoshui')        # 模拟 Mac 家目录
os.makedirs(SIM_WS, exist_ok=True)
os.makedirs(SIM_HOME, exist_ok=True)

def hr(t):
    print('\n' + '=' * 68); print(t); print('=' * 68)

hr('端到端模拟：像新机器一样走一遍')
print('  模拟根目录  %s' % BASE)
print('  模拟工作区  %s' % SIM_WS)
print('  模拟家目录  %s' % SIM_HOME)

# ── 1. 解包（等同 bootstrap.sh 第 3 步） ──────────────────────
hr('【1】解包并铺开')
with tarfile.open(MAIN, 'r:gz') as t:
    t.extractall(BASE)
for item in os.listdir(os.path.join(BASE, 'workspace')):
    s, d = os.path.join(BASE, 'workspace', item), os.path.join(SIM_WS, item)
    shutil.copytree(s, d, dirs_exist_ok=True) if os.path.isdir(s) else shutil.copy2(s, d)
for item in os.listdir(os.path.join(BASE, 'home')):
    s, d = os.path.join(BASE, 'home', item), os.path.join(SIM_HOME, item)
    shutil.copytree(s, d, dirs_exist_ok=True) if os.path.isdir(s) else shutil.copy2(s, d)
print('  workspace/ → %d 个文件' % sum(len(f) for _, _, f in os.walk(SIM_WS)))
print('  home/      → %d 个文件' % sum(len(f) for _, _, f in os.walk(SIM_HOME)))

# 补几个「由 git clone 提供」的脚本，测它们也在改写范围内
# 注意：样本本身必须是**合法** Python，否则语法体检会被样本自身污染。
clone_files = {
    'chartmap.py':         "ROOT = r'C:\\Users\\50522\\WorkBuddy\\2026-09-10-14-50-38'\n"
                           "SEED = 'C:\\\\Users\\\\50522\\\\WorkBuddy\\\\2026-09-10-14-50-38\\\\build\\\\seed'\n",
    'live_check_v4.py':    "PY = r'C:\\Users\\50522\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe'\n"
                           "GIT = 'C:/Users/50522/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd/git.exe'\n",
    'grab_live_backup.py': "E = r'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'\n"
                           "OUT = r'C:\\Users\\50522\\WorkBuddy\\2026-09-10-14-50-38\\build\\backup'\n",
}
for name, body in clone_files.items():
    io.open(os.path.join(SIM_WS, 'build', name), 'w', encoding='utf-8', newline='').write(body)
print('  另放入 3 个「git clone 提供」的脚本（含 5 种路径形态）✓')

# ── 2. 改写前扫描 ─────────────────────────────────────────────
env = dict(os.environ)
env.pop('PORT_PATHS_LIB', None)
env.update({
    'PORT_WS':     SIM_WS,
    'PORT_HOME':   SIM_HOME,
    'PORT_PYTHON': '/usr/local/bin/python3',
    'PORT_GIT':    '/usr/bin/git',
    'PORT_NODE':   '/usr/local/bin/node',
    'PORT_CHROME': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
})

hr('【2】改写前扫描')
p = subprocess.run([PY, os.path.join(SIM_WS, 'build', '_port_paths.py')],
                   env=env, capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
for line in (p.stdout or '').split('\n'):
    if any(k in line for k in ('命中', '工作区 ', '家目录 ', 'python ', 'chrome ')):
        print('  ' + line.strip())

# ── 3. 实际改写 ───────────────────────────────────────────────
hr('【3】执行改写 (--go)')
p = subprocess.run([PY, os.path.join(SIM_WS, 'build', '_port_paths.py'), '--go'],
                   env=env, capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
for line in (p.stdout or '').split('\n'):
    if any(k in line for k in ('已改写', '自检', '语法体检', '✗', '回滚')):
        print('  ' + line.strip())

# ── 4. 独立复核（另起进程，不信工具自己的结论） ───────────────
hr('【4】独立复核')
# 只认「真正的旧路径残留」。不能用宽泛的 [Cc]:[\\/] —— 模拟工作区本身
# 就在 C 盘，新路径 `C:/Users/Public/...` 会被宽泛正则误判成残留。
RE = re.compile(rb'[Cc]:[\\/]{1,2}users[\\/]{1,2}50522', re.I)
left_files, left_hits = [], 0
for root, dirs, files in os.walk(SIM_WS):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.winbak') or f in ('_port_paths.py', '_port_paths_test.py'):
            continue
        fp = os.path.join(root, f)
        try:
            data = io.open(fp, 'rb').read()
        except OSError:
            continue
        n = len(RE.findall(data))
        if n:
            left_files.append((n, os.path.relpath(fp, SIM_WS))); left_hits += n
print('  工作区残留 Windows 路径：%d 处 / %d 个文件' % (left_hits, len(left_files)))
for n, f in sorted(left_files, reverse=True)[:8]:
    print('      %3d 处  %s' % (n, f))

print('\n  抽查改写结果：')
for name in ('chartmap.py', 'live_check_v4.py', 'grab_live_backup.py'):
    fp = os.path.join(SIM_WS, 'build', name)
    if not os.path.exists(fp):
        continue
    print('    ── %s' % name)
    for line in io.open(fp, encoding='utf-8').read().rstrip().split('\n'):
        print('       %s' % line)

mem = os.path.join(SIM_HOME, 'MEMORY.md')
sk  = os.path.join(SIM_HOME, 'skills')
print()
print('  家目录 MEMORY.md : %s%s' % ('在  %d KB' % (os.path.getsize(mem) // 1024)
                                      if os.path.exists(mem) else '缺失', ''))
print('  家目录 skills/   : %s' % ('%d 个技能' % len(os.listdir(sk)) if os.path.isdir(sk) else '缺失'))

# ── 5. 语法体检（独立跑；区分「历史遗留」与「本轮新增」） ─────
hr('【5】语法体检（独立执行）')
def syntax_scan(root):
    bad = {}
    n = 0
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py') and not f.endswith('.winbak'):
                n += 1
                fp = os.path.join(r, f)
                try:
                    compile(io.open(fp, 'rb').read(), fp, 'exec')
                except SyntaxError as e:
                    bad[f] = 'line %s: %s' % (e.lineno, (e.msg or '')[:50])
                except Exception as e:
                    bad[f] = str(e)[:60]
    return n, bad

npy, post_bad = syntax_scan(SIM_WS)
# 基线：把改写前的备份（*.py.winbak）编译一遍，得出「本来就有问题」的集合。
# 只认 .py.winbak —— .md.winbak 之类也会被编译失败，那是噪音不是基线。
pre_bad = {}
for r, dirs, files in os.walk(SIM_WS):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py.winbak'):
            fp = os.path.join(r, f)
            try:
                compile(io.open(fp, 'rb').read(), fp, 'exec')
            except Exception as e:
                pre_bad[f[:-7]] = str(e)[:60]

new_bad = {k: v for k, v in post_bad.items() if k not in pre_bad}
print('  %d 个 .py 文件' % npy)
if pre_bad:
    print('  改写前就已损坏 %d 个（历史遗留，非本轮造成）：%s'
          % (len(pre_bad), ', '.join(sorted(pre_bad))))
print('  本轮新增语法错误：%s' % ('0 个 ✅' if not new_bad
                                  else '%d 个 ❌' % len(new_bad)))
for f, e in list(new_bad.items())[:5]:
    print('      ✗ %s  %s' % (f, e))

# ── 6. 幂等复跑 ───────────────────────────────────────────────
hr('【6】幂等复跑（应当 0 改动）')
p = subprocess.run([PY, os.path.join(SIM_WS, 'build', '_port_paths.py'), '--go'],
                   env=env, capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
idem = ''
for line in (p.stdout or '').split('\n'):
    if '已改写' in line:
        idem = line.strip(); print('  ' + idem)

# ── 7. 回滚演练 ───────────────────────────────────────────────
hr('【7】回滚演练')
before = io.open(os.path.join(SIM_WS, 'build', 'chartmap.py'), encoding='utf-8').read()
p = subprocess.run([PY, os.path.join(SIM_WS, 'build', '_port_paths.py'), '--rollback'],
                   env=env, capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
for line in (p.stdout or '').split('\n'):
    if '回滚完成' in line:
        print('  ' + line.strip())
after = io.open(os.path.join(SIM_WS, 'build', 'chartmap.py'), encoding='utf-8').read()
print('  chartmap.py 已还原为原始 Windows 路径：%s' % ('是' if 'C:\\Users\\50522' in after else '否'))

hr('结论')
ok = (left_hits == 0) and (not new_bad) and ('已改写 0' in idem) and ('C:\\Users\\50522' in after)
print('  残留            %d 处' % left_hits)
print('  本轮新增语法错误 %d 个' % len(new_bad))
print('  幂等复跑        %s' % ('通过（0 改动）' if '已改写 0' in idem else '失败'))
print('  回滚            %s' % ('有效' if 'C:\\Users\\50522' in after else '无效'))
print('  总体：%s' % ('✅ 模拟通过' if ok else '❌ 仍有问题'))
print('  模拟目录 %s（看完可删）' % BASE)
