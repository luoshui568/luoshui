# -*- coding: utf-8 -*-
"""投资标的模块 · 静态校验"""
import re
import os
import subprocess
import tempfile

HTML = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\deploy\index.html'
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
s = open(HTML, encoding='utf-8').read()
ok = fail = 0


def chk(name, cond, extra=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK]   ' + name)
    else:
        fail += 1
        print('  [FAIL] ' + name + ('   ' + str(extra) if extra else ''))


print('=' * 68)
print('投资标的模块 · 静态校验')
print('=' * 68)

# ---- 1. script 块语法 ----
blocks = re.findall(r'<script[^>]*>(.*?)</script>', s, re.S)
print('\n[1] script 块语法（%d 个）' % len(blocks))
tmp = os.path.join(tempfile.gettempdir(), 'wb_chk.js')
for i, b in enumerate(blocks):
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(b)
    r = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
    chk('script #%d 语法' % (i + 1), r.returncode == 0, (r.stderr or '')[:300])

# ---- 2. 标签配对 ----
print('\n[2] 标签配对')
for tag in ('div', 'section', 'table', 'textarea', 'script', 'select', 'button'):
    o = len(re.findall(r'<%s[\s>]' % tag, s))
    c = len(re.findall(r'</%s>' % tag, s))
    chk('%s 开闭 %d/%d' % (tag, o, c), o == c)

# ---- 3. App 方法引用 ----
print('\n[3] App 方法引用')
m = re.search(r'var App = \{(.*?)\n\};', s, re.S)
body = m.group(1) if m else ''
called = set(re.findall(r'App\.([a-zA-Z_]\w*)\s*\(', s))
defined = set(re.findall(r'\n  ([a-zA-Z_]\w*)\s*:', body))
miss = sorted(called - defined)
chk('App 调用均有定义（调用 %d / 定义 %d）' % (len(called), len(defined)), not miss, '悬空: ' + ', '.join(miss))

# ---- 4. 关键实现 ----
print('\n[4] 关键实现')
for k in ['wb_stocks', 'qt.gtimg.cn', 'TextDecoder', 'renderStockTable', 'syncQuotes',
          'pushQuotes', 'STK_COLS', 'chg_60d', 'div_yield', 'on_conflict=code',
          'merge-duplicates', 'autoSyncIfStale', 'pg-stock', 'cnt-stock', 'fmtCapY',
          'id="stockWrap"', 'id="stockKpi"', 'id="stockBar"', 'stockImportDlg']:
    chk('包含 %s' % k, k in s)

# ---- 5. 数据接线 ----
print('\n[5] 数据接线')
chk("TABLES 含 stocks:'wb_stocks'", "stocks:'wb_stocks'" in s)
chk("KINDS 含 'stocks'", "'works','stocks'" in s)
chk('S 状态含 stocks:[]', 'works:[],stocks:[],profile' in s)
chk('saveLocal 含 stocks', 'works:S.works,stocks:S.stocks' in s)
chk('cleanRow 含 stocks 字段', "'chg_ytd','chg_10d'" in s)
chk('ORD 含 stocks 排序', "stocks:'sort.asc,code.asc'" in s)
chk('PAGES 含 stock 页', "id:'stock'" in s)
chk('go() 含 stock 分支', "id==='stock'" in s)

# ---- 6. 回归检查 ----
print('\n[6] 回归（上一轮成果未被破坏）')
chk('明文密码 981208 出现 0 次', s.count('981208') == 0, s.count('981208'))
chk('旧前端哈希 passHash 0 次', s.count('passHash') == 0, s.count('passHash'))
chk('wb_admin_delete_row 仍在位', 'wb_admin_delete_row' in s)
chk('7 张原业务表仍全部使用', all(t in s for t in ['wb_tasks', 'wb_permits', 'wb_milestones',
                                                'wb_watchlist', 'wb_contacts', 'wb_logs', 'wb_works']))
chk('删除仍走 requireAdmin', s.count('requireAdmin(') >= 8, s.count('requireAdmin('))
chk('setLogout 退出按钮仍在', 'setLogout' in s)

print('\n' + '=' * 68)
print('通过 %d 项 · 失败 %d 项' % (ok, fail))
print('=' * 68)
