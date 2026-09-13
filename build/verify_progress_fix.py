# -*- coding: utf-8 -*-
"""进度显示修复 · 静态校验
1) 提取所有 <script> 块 → node --check 语法校验
2) 标签配对
3) effProgress / progressForStatus 定义与调用点核对
4) 关键 CSS 类与文案存在性
"""
import os, re, subprocess, sys, tempfile

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
HTML = os.path.join(ROOT, 'deploy', 'index.html')
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'

s = open(HTML, encoding='utf-8').read()
ok = True

def rep(tag, good, extra=''):
    global ok
    if not good:
        ok = False
    print(('[OK]  ' if good else '[FAIL]') + ' ' + tag + ('  ' + extra if extra else ''))

# ---------- 1. script 语法 ----------
blocks = re.findall(r'<script[^>]*>(.*?)</script>', s, re.S)
print('script 块数:', len(blocks))
for i, b in enumerate(blocks):
    if len(b.strip()) < 20:
        continue
    p = os.path.join(tempfile.gettempdir(), 'chk_%d.js' % i)
    open(p, 'w', encoding='utf-8').write(b)
    r = subprocess.run([NODE, '--check', p], capture_output=True, text=True)
    rep('script#%d node --check' % i, r.returncode == 0, (r.stderr or '').strip()[:200])
    os.remove(p)

# ---------- 2. 标签配对 ----------
for t in ['script', 'section', 'div', 'table']:
    o = len(re.findall(r'<%s[\s>]' % t, s))
    c = len(re.findall(r'</%s>' % t, s))
    rep('标签 <%s> 配对' % t, o == c, '%d / %d' % (o, c))

# ---------- 3. 新函数 ----------
rep('定义 effProgress', bool(re.search(r'\nfunction effProgress\(w\)', s)))
rep('定义 progressForStatus', bool(re.search(r'\nfunction progressForStatus\(st, cur\)', s)))

calls_eff = len(re.findall(r'effProgress\(', s))
rep('effProgress 被调用', calls_eff >= 4, '出现 %d 次（含定义 1 次）' % calls_eff)

# horizonStats 里应用了 effProgress 且过滤 drop
m = re.search(r'function horizonStats\(k\)\{(.*?)\n\}', s, re.S)
rep('horizonStats 走 effProgress', bool(m and 'effProgress' in m.group(1)))
rep('horizonStats 过滤 drop', bool(m and "!=='drop'" in m.group(1)))

# workRowHTML 用 pr 变量渲染宽度
m2 = re.search(r'function workRowHTML\(w\)\{(.*?)\n\}', s, re.S)
body = m2.group(1) if m2 else ''
rep('workRowHTML 用 effProgress', 'effProgress(w)' in body)
rep('workRowHTML 进度条写 pr', "'<div class=\"bar'+barCls+'\"><i style=\"width:'+pr+'%\"></i></div>'" in body)
rep('workRowHTML 不再直读 w.progress 做宽度', "Math.min(100,+w.progress||0))+'%'" not in body)
rep('workRowHTML 有 drop 状态类', "st==='drop'?'drop':''" in body)

# workCycle / saveWork 走 progressForStatus
rep('workCycle 走 progressForStatus', bool(re.search(r'workCycle:function\(id\)\{(.*?)progressForStatus\(nt, w\.progress\)', s, re.S)))
rep('saveWork 走 progressForStatus', bool(re.search(r'saveWork:function\(id\)\{(.*?)progressForStatus\(st, prog\)', s, re.S)))
rep('旧的 done 硬编码已移除', "if(nt==='done') patch.progress = 100;" not in s)

# 导出 CSV
rep('CSV 用 effProgress', 'WORK_STATUS_TXT[w.status]||w.status,effProgress(w),w.owner' in s)

# 完成度分母
rep('完成度不含已放弃', 'pct(doneN,liveN)' in s)

# ---------- 4. CSS ----------
rep('CSS .wcrd.drop', '.wcrd.drop{opacity:.6}' in s)
rep('CSS .bar-done', '.wcrd .bar.bar-done i{' in s)
rep('CSS .bar-drop', '.wcrd .bar.bar-drop{' in s)

# ---------- 5. 文案 ----------
rep('卡片文案 已放弃（进度不计）', '🚫 已放弃（进度不计）' in s)
rep('卡片文案 已完成', "'✅ 已完成'" in s or '✅ 已完成' in s)
rep('编辑弹窗提示', '状态与进度自动对齐' in s)

# ---------- 6. 状态下拉中文 ----------
rep('sel 支持 labelMap', 'function sel(label, id, val, opts, labelMap)' in s)
rep('新增 TASK_STATUS_TXT 常量', 'var TASK_STATUS_TXT = {todo:' in s)
rep('w-status 传中文映射', "sel('状态','w-status', w?w.status:'todo', WORK_STATUS, WORK_STATUS_TXT)" in s)
rep('f-status 传中文映射', "sel('状态','f-status', t?t.status:'todo', ['todo','doing','done','skip'], TASK_STATUS_TXT)" in s)
rep('无残留内联状态映射', "{doing:'进行中',done:'已完成',skip:'已跳过'}" not in s)

# ---------- 7. 回归：上一轮的服务端认证未被破坏 ----------
rep('回归 · 明文密码 0 次', s.count('981208') == 0, '出现 %d 次' % s.count('981208'))
rep('回归 · passHash 0 次', s.count('passHash') == 0)
rep('回归 · 退出按钮在位', s.count('setLogout') >= 2)
rep('回归 · RPC 删除在位', 'wb_admin_delete_row' in s)

print()
print('=' * 46)
print('全部通过' if ok else '存在失败项，见上')
print('=' * 46)
sys.exit(0 if ok else 1)
