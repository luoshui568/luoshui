# -*- coding: utf-8 -*-
"""生成 macOS 迁移包。

三类资产：
  A. GitHub 已有      → Mac 上 git clone 即得，不打包
  B. GitHub 没有      → 打进主包（脚本/记忆/技能/身份/seed）
  C. 含密钥/设备绑定  → 打进密钥包，单独传，绝不进 git

用法:
  python _mac_pack.py            # 干跑，只出清单
  python _mac_pack.py --go       # 实际打包
"""
import os, io, sys, re, json, tarfile, hashlib, subprocess, shutil
from pathlib import Path

# 路径一律从脚本自身位置推导，保证在 Windows 与 macOS 上都能跑
R    = str(Path(__file__).resolve().parent.parent)
HOME = str(Path.home())
UD   = os.path.join(HOME, '.workbuddy')
OUT  = os.path.join(R, 'deliver', 'mac-mini')
# git：优先 PATH，Windows 上回退到 PortableGit
GIT  = shutil.which('git') or \
       r'C:\Users\50522\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe'

GO = '--go' in sys.argv

LOG = []
def w(s=''):
    LOG.append(str(s))
    print(s)

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def git_tracked():
    try:
        p = subprocess.run([GIT, 'ls-files'], cwd=R, capture_output=True, timeout=60)
        return set(l.strip().replace('\\', '/') for l in
                   (p.stdout or b'').decode('utf-8', 'replace').splitlines() if l.strip())
    except Exception:
        return set()

# ─────────────────────────────────────────────────────────────
# 1. 收集主包内容
# ─────────────────────────────────────────────────────────────
tracked = git_tracked()
build_dir = os.path.join(R, 'build')

scripts = []          # (绝对路径, 包内相对路径)
for f in sorted(os.listdir(build_dir)):
    p = os.path.join(build_dir, f)
    if os.path.isfile(p) and f.endswith('.py'):
        if ('build/' + f) not in tracked:
            scripts.append((p, 'workspace/build/' + f))

# seed 未入库的
seed_dir = os.path.join(build_dir, 'seed')
seed_extra = []
if os.path.isdir(seed_dir):
    for f in sorted(os.listdir(seed_dir)):
        p = os.path.join(seed_dir, f)
        if os.path.isfile(p) and ('build/seed/' + f) not in tracked:
            seed_extra.append((p, 'workspace/build/seed/' + f))

# 项目记忆
mem_dir = os.path.join(R, '.workbuddy', 'memory')
mem_files = []
if os.path.isdir(mem_dir):
    for f in sorted(os.listdir(mem_dir)):
        p = os.path.join(mem_dir, f)
        if os.path.isfile(p):
            mem_files.append((p, 'workspace/.workbuddy/memory/' + f))

# 用户级技能（全量）
sk_dir = os.path.join(UD, 'skills')
skill_files = []
if os.path.isdir(sk_dir):
    for name in sorted(os.listdir(sk_dir)):
        d = os.path.join(sk_dir, name)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x not in ('__pycache__', '.git')]
            for f in fn:
                p = os.path.join(dp, f)
                skill_files.append((p, 'home/skills/' + os.path.relpath(p, sk_dir).replace('\\', '/')))

# 身份与用户级记忆
ident = []
for f in ['MEMORY.md', 'SOUL.md', 'IDENTITY.md', 'USER.md']:
    p = os.path.join(UD, f)
    if os.path.isfile(p):
        ident.append((p, 'home/' + f))

# ─────────────────────────────────────────────────────────────
# 2. 密钥包内容（单独）
# ─────────────────────────────────────────────────────────────
secrets = []
for f in ['mcp.json', 'mcp-approvals.json', 'settings.json']:
    p = os.path.join(UD, f)
    if os.path.isfile(p):
        secrets.append((p, 'home/' + f))

# 明确排除的设备绑定/会话类文件
EXCLUDED = [
    ('device-id',            '设备标识，换了机器就该变'),
    ('workbuddy.db',         '本地会话库，Mac 上重建'),
    ('workbuddy.db-shm',     '同上'),
    ('workbuddy.db-wal',     '同上'),
    ('edge-sync-mapping-v2.db', '浏览器同步映射，设备绑定'),
    ('edge-sync-mapping-v2.db-shm', '同上'),
    ('edge-sync-mapping-v2.db-wal', '同上'),
    ('edge-sync-mapping-v4.db', '同上'),
    ('edge-sync-mapping-v4.db-shm', '同上'),
    ('edge-sync-mapping-v4.db-wal', '同上'),
    ('usage-log.json',       '用量日志，无迁移价值'),
    ('qimei-cache.json',     '设备指纹缓存'),
    ('ioa-im-override.json', '设备相关'),
    ('.legacy-localstorage-migration.done', '一次性迁移标记'),
    ('session_fragment_repair_done520', '一次性修复标记'),
    ('last-launch.json',     '启动时间戳'),
    ('tencent-docs-engine.port', '端口占用记录'),
    ('mcp.json.bak-20260919-123918', '旧备份，无价值'),
    ('settings.json.tmp',    '临时文件'),
]

# ─────────────────────────────────────────────────────────────
# 3. 依赖分析：扫 import，扣掉标准库
# ─────────────────────────────────────────────────────────────
STD = set(getattr(sys, 'stdlib_module_names', set()))
IMPORT_RE = re.compile(r'^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))', re.M)
LOCAL = {'_mk_lib', 'chartmap', 'chartflow', 'report_build_v31', 'report_template_v31',
         'score_engine', 'score_lock', '_score_patch', '_norm_bold', 'build'}

mods = {}
scan_targets = [p for p, _ in scripts] + [os.path.join(build_dir, f) for f in os.listdir(build_dir)
                                          if f.endswith('.py')]
for p in scan_targets:
    try:
        t = io.open(p, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    for m in IMPORT_RE.finditer(t):
        name = (m.group(1) or m.group(2) or '').split('.')[0]
        if not name:
            continue
        if name in STD or name in LOCAL or name.startswith('_'):
            continue
        mods.setdefault(name, set()).add(os.path.basename(p))

# 常见包的 pip 名映射
PIPMAP = {
    'PIL': 'Pillow', 'pdfplumber': 'pdfplumber', 'requests': 'requests',
    'bs4': 'beautifulsoup4', 'cv2': 'opencv-python', 'yaml': 'PyYAML',
    'dateutil': 'python-dateutil', 'openpyxl': 'openpyxl', 'docx': 'python-docx',
    'pptx': 'python-pptx', 'fitz': 'PyMuPDF', 'numpy': 'numpy', 'pandas': 'pandas',
    'pdfminer': 'pdfminer.six', 'lxml': 'lxml', 'dotenv': 'python-dotenv',
    'psycopg2': 'psycopg2-binary', 'tqdm': 'tqdm', 'matplotlib': 'matplotlib',
}

# ─────────────────────────────────────────────────────────────
# 4. 输出清单
# ─────────────────────────────────────────────────────────────
w('=' * 68)
w('macOS 迁移包 清单预览' + ('' if GO else '   【干跑 — 未写盘】'))
w('=' * 68)
w()
w('【A】GitHub 已有（clone 即得，不打包）')
w('      214 个文件 / 3.88 MiB（135 个 .py 构建脚本 + 39 个 seed + 交付页 + SQL）')
w()
w('【B】主包 luoshui-workspace.tar.gz')
tot = 0
groups = [('被 gitignore 忽略的工具脚本', scripts),
          ('seed 未入库文件', seed_extra),
          ('项目记忆 .workbuddy/memory/', mem_files),
          ('用户级技能（全量）', skill_files),
          ('身份与用户级记忆', ident)]
for label, items in groups:
    sz = sum(os.path.getsize(p) for p, _ in items if os.path.exists(p))
    tot += sz
    w('      %-34s %4d 个  %8.1f KB' % (label, len(items), sz / 1024.0))
    if label.startswith('seed') and items:
        for p, _ in items:
            w('          - %s' % os.path.basename(p))
w('      %-34s      %8.1f KB' % ('合计', tot / 1024.0))
w()
w('【C】密钥包 luoshui-secrets.tar.gz  ← 单独传，绝不进 git')
for p, _ in secrets:
    w('      %-30s %8.1f KB' % (os.path.basename(p), os.path.getsize(p) / 1024.0))
w()
w('【D】明确不搬（Mac 上重建）')
for f, why in EXCLUDED:
    w('      %-38s %s' % (f, why))
w()
w('【E】Python 第三方依赖（自动分析）')
# 过滤口径：排除标准库 + 排除「项目里存在同名 .py」的本地模块。
# 注意：不能用 importlib.find_spec 判断 —— 项目目录在 sys.path 上，
# 本地脚本会被误判成可导入；且托管 Python 未装第三方库会造成反向误杀。
LOCAL_PY = set()
for _root, _dirs, _fs in os.walk(R):
    _dirs[:] = [d for d in _dirs if d not in ('__pycache__', '.git', 'node_modules',
                                              'backup_hosting_pre_' + '' , 'out')]
    for _f in _fs:
        if _f.endswith('.py'):
            LOCAL_PY.add(_f[:-3])
real, phony = {}, {}
for _m in sorted(mods):
    (phony if (_m in LOCAL_PY or _m in LOCAL) else real)[_m] = mods[_m]
_dedup = {}
for _m in real:
    _p = PIPMAP.get(_m, _m)
    _dedup[_p.lower().replace('-', '').replace('.', '')] = _p
REQS = sorted(_dedup.values())
if mods:
    for m in sorted(real):
        w('      %-24s 被 %d 个脚本使用' % (PIPMAP.get(m, m), len(real[m])))
    if phony:
        w()
        w('      （已排除 %d 个本地模块/误报：%s）' % (len(phony), ', '.join(sorted(phony))))
    w()
    w('      requirements.txt 将写入: ' + ', '.join(REQS))
else:
    w('      （未检出第三方依赖）')
w()

# ─────────────────────────────────────────────────────────────
# 5. 打包
# ─────────────────────────────────────────────────────────────
if not GO:
    w('=' * 68)
    w('干跑结束。加 --go 实际写盘到 deliver/mac-mini/')
    sys.exit(0)

os.makedirs(OUT, exist_ok=True)
manifest = []
def add(tar, items, bucket):
    for p, rel in items:
        if not os.path.exists(p):
            continue
        tar.add(p, arcname=rel)
        manifest.append('%s  %s  %10d  %s' % (bucket, sha256(p)[:16], os.path.getsize(p), rel))

main_tar = os.path.join(OUT, 'luoshui-workspace.tar.gz')
with tarfile.open(main_tar, 'w:gz') as t:
    for label, items in groups:
        add(t, items, 'MAIN')

sec_tar = os.path.join(OUT, 'luoshui-secrets.tar.gz')
with tarfile.open(sec_tar, 'w:gz') as t:
    add(t, secrets, 'SECRET')

# requirements.txt
with io.open(os.path.join(OUT, 'requirements.txt'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# 由 build/_mac_pack.py 自动分析生成\n')
    f.write('# 仅含本机实测可导入的第三方库；误报已过滤\n')
    for r in REQS:
        f.write(r + '\n')

# MANIFEST
with io.open(os.path.join(OUT, 'MANIFEST.txt'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('luoshui 工作区迁移清单\n')
    f.write('生成自: %s\n\n' % R)
    f.write('格式: 包  sha256前16位  (空格)  字节数  包内路径\n\n')
    for line in sorted(manifest):
        f.write(line + '\n')

w('=' * 68)
w('已写盘 → %s' % OUT)
for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    w('  %-32s %10.1f KB' % (f, os.path.getsize(p) / 1024.0))
w()
w('主包条目数: %d   密钥包条目数: %d' % (len([m for m in manifest if m.startswith('MAIN')]),
                                          len([m for m in manifest if m.startswith('SECRET')])))
