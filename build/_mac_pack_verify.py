# -*- coding: utf-8 -*-
"""验证迁移包：结构、关键文件、sha256 是否与 MANIFEST 一致。

用法: python _mac_pack_verify.py
"""
import os, io, sys, tarfile, hashlib, tempfile, shutil
from pathlib import Path

R   = str(Path(__file__).resolve().parent.parent)
OUT = os.path.join(R, 'deliver', 'mac-mini')
MAIN = os.path.join(OUT, 'luoshui-workspace.tar.gz')
SEC  = os.path.join(OUT, 'luoshui-secrets.tar.gz')
MAN  = os.path.join(OUT, 'MANIFEST.txt')

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

fails = []
def check(cond, label, extra=''):
    print('  %s %s%s' % ('✅' if cond else '❌', label, ('  ' + extra) if extra else ''))
    if not cond:
        fails.append(label)

print('=' * 68)
print('迁移包验证')
print('=' * 68)

# 1. 文件存在
print('\n【1】包文件')
for p in (MAIN, SEC, MAN, os.path.join(OUT, 'requirements.txt'),
          os.path.join(OUT, 'bootstrap.sh'), os.path.join(OUT, '迁移手册.md')):
    check(os.path.exists(p), os.path.basename(p),
          '%.1f KB' % (os.path.getsize(p) / 1024) if os.path.exists(p) else '缺失')

# 2. 主包结构与关键文件
print('\n【2】主包结构')
with tarfile.open(MAIN, 'r:gz') as t:
    names = [m.name for m in t.getmembers() if m.isfile()]
    top = sorted(set(n.split('/')[0] for n in names))
    print('     顶层目录: %s' % ', '.join(top))
    check('workspace' in top, '含 workspace/')
    check('home' in top, '含 home/')

    # 主包只装「git 之外」的东西。以下文件由 git clone 提供，主包**不应**重复包含。
    must = [
        'workspace/build/_mk_lib.py',            # 建库公共库
        'workspace/build/_fill_deep.py',         # 补深度
        'workspace/build/_goldify.py',           # 模块搬家
        'workspace/build/_score_commit.py',      # 槽29落库
        'workspace/build/_do_upload.py',         # 上传
        'workspace/build/_port_paths.py',        # 路径移植（Mac 上要用）
        'workspace/build/_mac_pack.py',          # 打包器
        'workspace/build/_norm_bold.py',         # 星号归一
        'workspace/.workbuddy/memory/MEMORY.md',
        'home/MEMORY.md',
        'home/USER.md',
        'home/SOUL.md',
    ]
    for m in must:
        check(m in names, m)

    by_clone = [
        'workspace/build/chartmap.py',
        'workspace/build/report_build_v31.py',
        'workspace/build/report_template_v31.py',
        'workspace/build/live_check_v4.py',
        'workspace/build/grab_live_backup.py',
        'workspace/deliver/research.html',
    ]
    for m in by_clone:
        check(m not in names, '%s（由 git clone 提供，主包不重复）' % m)

    # 技能目录数量
    skills = sorted(set(n.split('/')[2] for n in names
                        if n.startswith('home/skills/') and len(n.split('/')) > 3))
    check(len(skills) >= 20, 'home/skills 下技能数 ≥ 20', '实际 %d 个' % len(skills))

    agent_made = 0
    tmproot = tempfile.mkdtemp()
    t.extractall(tmproot)
    skroot = os.path.join(tmproot, 'home', 'skills')
    if os.path.isdir(skroot):
        for d in os.listdir(skroot):
            sm = os.path.join(skroot, d, 'SKILL.md')
            if os.path.exists(sm):
                head = io.open(sm, encoding='utf-8', errors='replace').read(600)
                if 'agent_created: true' in head:
                    agent_made += 1
    check(agent_made >= 10, '自建技能（agent_created）≥ 10', '实际 %d 个' % agent_made)

# 3. 密钥包
print('\n【3】密钥包')
with tarfile.open(SEC, 'r:gz') as t:
    sn = [m.name for m in t.getmembers() if m.isfile()]
    print('     内容: %s' % ', '.join(sn))
    check(any('mcp.json' in n for n in sn), '含 mcp.json')
    check(any('settings.json' in n for n in sn), '含 settings.json')

# 4. 密钥包绝不混入主包
print('\n【4】隔离检查（密钥不得出现在主包）')
for n in names:
    if os.path.basename(n) in ('mcp.json', 'settings.json', 'mcp-approvals.json'):
        fails.append('密钥混入主包: %s' % n)
check(not any(os.path.basename(n) in ('mcp.json', 'settings.json', 'mcp-approvals.json')
              for n in names), '主包内无 mcp.json / settings.json')

# 5. sha256 与 MANIFEST 比对
print('\n【5】sha256 校验')
expect = {}
for line in io.open(MAN, encoding='utf-8'):
    parts = line.split()
    if len(parts) >= 4 and parts[0] in ('MAIN', 'SECRET'):
        expect[parts[3]] = parts[1]
print('     MANIFEST 记录条目数: %d' % len(expect))

with tarfile.open(MAIN, 'r:gz') as t:
    bad = 0
    checked = 0
    for m in t.getmembers():
        if not m.isfile() or m.name not in expect:
            continue
        h = hashlib.sha256(t.extractfile(m).read()).hexdigest()[:16]
        checked += 1
        if h != expect[m.name]:
            bad += 1
            if bad <= 3:
                print('      ✗ %s  MANIFEST=%s  实际=%s' % (m.name, expect[m.name], h))
    check(bad == 0, '主包 %d 个文件 sha256 全部一致' % checked, '不符 %d 个' % bad)

with tarfile.open(SEC, 'r:gz') as t:
    bad = checked = 0
    for m in t.getmembers():
        if not m.isfile() or m.name not in expect:
            continue
        h = hashlib.sha256(t.extractfile(m).read()).hexdigest()[:16]
        checked += 1
        if h != expect[m.name]:
            bad += 1
    check(bad == 0, '密钥包 %d 个文件 sha256 一致' % checked, '不符 %d 个' % bad)

shutil.rmtree(tmproot, ignore_errors=True)

# 6. bootstrap.sh 关键要素
print('\n【6】引导脚本')
sh = io.open(os.path.join(OUT, 'bootstrap.sh'), encoding='utf-8').read()
for token, label in [('git clone', '有 clone 步骤'),
                     ('venv', '建 venv'),
                     ('requirements.txt', '装依赖'),
                     ('_port_paths.py', '调路径移植'),
                     ('--rollback', '提到回滚'),
                     ('CloudBase', '提醒连接器重授权')]:
    check(token in sh, label)

print()
print('=' * 68)
if fails:
    print('❌ 失败 %d 项：' % len(fails))
    for f in fails:
        print('   - %s' % f)
    sys.exit(1)
print('✅ 全部通过')
