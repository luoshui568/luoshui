# -*- coding: utf-8 -*-
"""构建后综合校验：语法 / 标签配对 / 未定义引用 / App 方法 / 新功能关键实现"""
import hashlib
import os
import re
import subprocess
import sys

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
P = os.path.join(BASE, 'deploy', 'index.html')
s = open(P, encoding='utf-8').read()
ok, bad = [], []


def chk(cond, name, extra=''):
    (ok if cond else bad).append(name + (('  << ' + str(extra)) if (extra and not cond) else ''))


# ---------- 1. 提取所有 script 块 → node --check ----------
blocks = re.findall(r'<script[^>]*>(.*?)</script>', s, re.S)
chk(len(blocks) >= 2, 'script 块数 >= 2', len(blocks))
tmp = os.path.join(BASE, 'build', '_chk_js')
os.makedirs(tmp, exist_ok=True)
for i, b in enumerate(blocks):
    p = os.path.join(tmp, 'b%d.js' % i)
    open(p, 'w', encoding='utf-8').write(b)
    r = subprocess.run(['node', '--check', p], capture_output=True, text=True,
                       shell=True)
    chk(r.returncode == 0, 'node --check block%d' % i, (r.stderr or '')[:300])

# ---------- 2. 标签配对 ----------
for tag in ['script', 'section', 'div', 'textarea', 'table']:
    o = len(re.findall(r'<%s[\s>]' % tag, s))
    c = len(re.findall(r'</%s>' % tag, s))
    chk(o == c and o > 0, '%s 配对 %d:%d' % (tag, o, c))

# ---------- 3. App.xxx( 调用 vs App 对象键 ----------
m = re.search(r'var App = \{(.*?)\n\};', s, re.S)
appbody = m.group(1)
defs = set(re.findall(r'\n  ([a-zA-Z_]\w*)\s*:', appbody))
calls = set(re.findall(r'App\.([a-zA-Z_]\w*)\s*\(', s))
miss = calls - defs
chk(not miss, 'App 方法零悬空（共 %d 个引用）' % len(calls), sorted(miss))

# ---------- 4. 未定义引用扫描（技能脚本） ----------
scan = os.path.join(os.path.expanduser('~'), '.workbuddy', 'skills',
                    'cloudbase-singlefile-workbench', 'scripts', 'scan_undefined.py')
if os.path.exists(scan):
    r = subprocess.run([sys.executable, scan, P], capture_output=True, text=True)
    out = (r.stdout or '') + (r.stderr or '')
    chk('✅' in out or r.returncode == 0, 'scan_undefined 通过', out[-400:])
else:
    ok.append('scan_undefined 脚本不存在，跳过')

# ---------- 5. 本轮新增功能的关键实现 ----------
feats = {
    '解析函数 parseStockBlob': 'function parseStockBlob(',
    '编码兜底 decodeBuf(gbk)': "new TextDecoder('gbk')",
    '文件读取 readStockFile': 'function readStockFile(',
    '本地去重 dedupeStocks': 'function dedupeStocks(',
    '启动时去重': 'dedupeStocks();',
    '字段锁定 stkLocked': 'function stkLocked(',
    '解锁方法 stockUnlock': 'stockUnlock:function(',
    '锁定字段常量': 'STK_FIELD_TXT',
    '编辑基准快照': 'STK_EDIT_BASE',
    '列来源提示': 'STK_SRC',
    '板块PE表': 'function fetchBoardPE(',
    '公司概况 EM2016': 'RPT_F10_BASIC_ORGINFO',
    '资产负债表': 'RPT_DMSK_FN_BALANCE',
    '基本面编排': 'function syncFundamentals(',
    '基本面并入 syncQuotes': 'syncFundamentals(rows)',
    '拖放处理': 'stockDrop:function(',
    '文件选择处理': 'stockFiles:function(',
    '清空按钮': 'stockClear:function(',
    'ebk 提示': '.ebk',
    'lock_fields 进白名单': "'lock_fields','info_at'",
    'exportJSON 按 KINDS': 'KINDS.forEach(function(k){ data[k] = S[k] || []; })',
    '基本面回写云端': 'if(stkHas(r.ind_pe))        p.ind_pe = r.ind_pe;',
    # —— 自定义板块（2026-09-13 第 6 轮） ——
    '板块标签条渲染': 'function renderStockGrps(',
    '板块统计 stkGroupList': 'function stkGroupList(',
    '板块名归一化 stkGrpName': 'function stkGrpName(',
    '未分组哨兵': "STK_GRP_NONE = '__none__'",
    '板块筛选命中 stkGrpMatch': 'function stkGrpMatch(',
    '按下标点选 stockGrpPick': 'stockGrpPick:function(',
    '解散板块 stockGrpDel': 'stockGrpDel:function(',
    '快捷板块回填 stockGrpFill': 'stockGrpFill:function(',
    '导入计数 stockImportCount': 'stockImportCount:function(',
    '导入弹窗板块输入框': "id=\"s-grp-new\"",
    '导入弹窗板块 datalist': "id=\"s-grp-new-dl\"",
    '导入按板块归组': "if(grpNew) row.grp = grpNew;",
    '已有分组不挪动': '只补名称 / 补空板块',
    '编辑弹窗板块可手填': '<input id="s-grp" list="s-grp-dl"',
    '板块列': "{k:'grp',",
    '板块列样式 tagg': '.stkTab .tagg',
    '解散走管理员闸门': 'requireAdmin(\'解散板块',
}
for k, v in feats.items():
    chk(v in s, '实现：' + k)

# ---------- 6. 回归：旧的不该再出现 ----------
chk(s.count('App.stockImportDlg') >= 2, '导入入口多处可用')
chk('var KINDS' in s and "'stocks'" in s, 'KINDS 含 stocks')
chk(s.count('981208') == 0, '明文密码 0 次', s.count('981208'))
chk(s.count('passHash') == 0, '旧前端哈希 0 次', s.count('passHash'))
chk('wb_admin_delete_row' in s, '服务端删除函数在位')

print('md5 =', hashlib.md5(open(P, 'rb').read()).hexdigest())
print('size =', os.path.getsize(P))
print('\n✅ 通过 %d 项' % len(ok))
for x in ok:
    print('   ', x)
if bad:
    print('\n❌ 失败 %d 项' % len(bad))
    for x in bad:
        print('   ', x)
else:
    print('\n全部通过')
