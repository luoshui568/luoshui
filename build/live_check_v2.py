# -*- coding: utf-8 -*-
"""线上产物三方核对：本机 index.html == 桌面副本 == 线上（二进制 md5）+ 关键特征串"""
import hashlib
import io
import os
import shutil
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
LOCAL = os.path.join(BASE, 'deploy', 'index.html')
DESK = r'C:\Users\50522\Desktop\矿产战略执行工作台.html'
URL = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com/index.html'

# 1) 本机 → 桌面
shutil.copyfile(LOCAL, DESK)
print('[1] 已复制到桌面：%s' % DESK)


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


# 2) 线上（裸请求：不带 Sec-Fetch-Mode: navigate，避开「访问提示中间页」）
req = urllib.request.Request(URL, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*',
})
with urllib.request.urlopen(req, timeout=60) as r:
    live = r.read()
    hdr = dict(r.headers)
print('[2] 线上 HTTP 200，收到 %d 字节（本地 %d 字节）' % (len(live), os.path.getsize(LOCAL)))
print('    Content-Type: %s' % hdr.get('Content-Type'))
print('    Content-Disposition: %s' % hdr.get('Content-Disposition'))

LIVE = os.path.join(BASE, 'build', '_live_index.html')
open(LIVE, 'wb').write(live)

m_local, m_desk, m_live = md5(LOCAL), md5(DESK), md5(LIVE)
print()
print('  本机  %s' % m_local)
print('  桌面  %s' % m_desk)
print('  线上  %s' % m_live)
print('  三方一致：%s' % ('✅ 是' if m_local == m_desk == m_live else '❌ 否'))

# 3) 线上关键特征串
s = live.decode('utf-8', 'ignore')
FEATS = {
    '文本/.ebk 解析 parseStockBlob': 'function parseStockBlob(',
    'GBK 解码兜底': "new TextDecoder('gbk')",
    '本地去重 dedupeStocks': 'function dedupeStocks(',
    '去重保留最新（up/t/info_at 最大值）': 'Math.max(parseFloat(x.up) || 0',
    '字段锁定 stkLocked': 'function stkLocked(',
    '解锁 stockUnlock': 'stockUnlock:function(',
    '拖放区 .stkDrop': '.stkDrop{',
    'accept 含 .ebk': 'accept=".ebk,.txt,.csv,.blk,.sel,.lst,.ini,text/plain"',
    '板块 PE（push2delay）': 'push2delay.eastmoney.com',
    '公司概况 EM2016': 'RPT_F10_BASIC_ORGINFO',
    '资产负债表 TOTAL_ASSETS': 'RPT_DMSK_FN_BALANCE',
    '基本面编排 syncFundamentals': 'function syncFundamentals(',
    '基本面并入 syncQuotes': 'syncFundamentals(rows)',
    '列来源提示 STK_SRC': 'STK_SRC',
    'lock_fields 写入 payload': 'lock_fields: r.lock_fields',
    '.ebk 7 位市场位校验（只认 0/1）': "d.charAt(0) === '0' || d.charAt(0) === '1'",
    '.ebk 整行 7 位规则': "if((m = ln.match(/^([01])([0-9]{6})$/)))",
    '多代码行不被误当名称': '!/^[0-9]/.test(rest)',
}
print()
print('[3] 线上特征串：')
bad = 0
for k, v in FEATS.items():
    hit = v in s
    if not hit:
        bad += 1
    print('   %s %s' % ('✅' if hit else '❌', k))

# 4) 不该再出现的
print()
print('[4] 陈旧/敏感串应为 0：')
for k, v in {'明文密码 981208': '981208', '旧前端哈希 passHash': 'passHash'}.items():
    n = s.count(v)
    if n:
        bad += 1
    print('   %s %s 出现 %d 次' % ('✅' if n == 0 else '❌', k, n))

print()
print('结论：%s' % ('✅ 线上产物即最新版，三方一致，特征齐全' if bad == 0 and m_local == m_live else '❌ 有 %d 项异常' % bad))
os.remove(LIVE)
