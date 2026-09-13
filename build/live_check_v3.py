# -*- coding: utf-8 -*-
"""线上产物核对（v3 · 自定义板块）

必须**二进制读**线上文件：文本模式会把 CRLF 归一化，导致 md5 误判「上传没生效」。
"""
import hashlib
import io
import shutil
import urllib.request

L = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\deploy\index.html'
D = r'C:\Users\50522\Desktop\矿产战略执行工作台.html'
URL = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com/index.html'


def md5b(b):
    return hashlib.md5(b).hexdigest()


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'})
            with urllib.request.urlopen(r, timeout=60) as f:
                return f.read()
        except Exception as e:
            last = e
    raise last


local = open(L, 'rb').read()
live = get(URL)
try:
    desk = open(D, 'rb').read()
except Exception:
    desk = None

print('[1] 三方 md5')
print('    本机 deploy/index.html :', md5b(local), len(local), '字节')
print('    线上 index.html        :', md5b(live), len(live), '字节')
print('    桌面单文件副本         :', (md5b(desk), len(desk)) if desk else '(无)')
same = md5b(local) == md5b(live)
print('    本机 == 线上 :', '✅' if same else '❌')

if desk is not None:
    if md5b(desk) != md5b(local):
        shutil.copyfile(L, D)
        desk = open(D, 'rb').read()
        print('    桌面副本已刷新 →', md5b(desk))
    print('    桌面 == 本机 :', '✅' if md5b(desk) == md5b(local) else '❌')

print('\n[2] 线上关键特征串（必须全部命中）')
text = live.decode('utf-8', 'replace')
FEATS = {
    '板块标签条容器': 'id="stockGrps"',
    '板块标签条渲染函数': 'function renderStockGrps(',
    '板块统计 stkGroupList': 'function stkGroupList(',
    '板块名归一化 stkGrpName': 'function stkGrpName(',
    '未分组哨兵 __none__': "STK_GRP_NONE = '__none__'",
    '按下标点选 stockGrpPick': 'stockGrpPick:function(',
    '解散板块 stockGrpDel': 'stockGrpDel:function(',
    '解散走管理员闸门': "requireAdmin('解散板块",
    '快捷板块回填 stockGrpFill': 'stockGrpFill:function(',
    '导入计数 stockImportCount': 'stockImportCount:function(',
    '导入弹窗板块输入框': 'id="s-grp-new"',
    '导入弹窗板块 datalist': 'id="s-grp-new-dl"',
    '导入按板块归组': 'if(grpNew) row.grp = grpNew;',
    '编辑弹窗可手填板块': '<input id="s-grp" list="s-grp-dl"',
    '板块列': "{k:'grp',",
    '板块列样式': '.stkTab .tagg',
    '板块标签条样式': '.stkGrps{',
    '板块选择器样式': '.stkPick{',
    '.ebk 提示': '.ebk',
    '解析函数': 'function parseStockBlob(',
    '本地去重': 'function dedupeStocks(',
    '字段锁定': 'function stkLocked(',
    '基本面编排': 'function syncFundamentals(',
}
bad = 0
for k, v in FEATS.items():
    hit = v in text
    if not hit:
        bad += 1
    print('    %s %s' % ('✅' if hit else '❌', k))
print('    合计 %d/%d 命中' % (len(FEATS) - bad, len(FEATS)))

print('\n[3] 安全回归')
print('    明文密码 981208 出现次数 :', text.count('981208'), '(须为 0)')
print('    旧前端哈希 passHash      :', text.count('passHash'), '(须为 0)')
print('    服务端删除函数           :', 'wb_admin_delete_row' in text)

print('\n' + ('=' * 60))
print('结论：' + ('全部通过 ✅' if (same and bad == 0 and text.count('981208') == 0) else '有项目不通过 ❌'))
print('=' * 60)
