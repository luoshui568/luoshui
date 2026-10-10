# -*- coding: utf-8 -*-
"""
600456 修正：把「并入 m25 的对象」从「风险矩阵」换回「行业总览与市场空间」
-------------------------------------------------------------------
背景
  用户原意：把 **「行业总览与市场空间」** 并入 **「钛行业介绍与市场规模」**
            （他当时看的页面上，前者编号 19、后者编号 25）。
  上一轮误把 **「风险矩阵」**（移位后恰好是 m19）当成了源模块并进去。

本次要做的（编号结构不变，仍是 30 模块 / 十段目录）
  1. m19  : 「行业总览与市场空间」 → 还原为 **「风险矩阵」**（正文取合并前快照）
  2. m24  : 「钛行业介绍与市场规模」正文 = 该模块**原始正文**
            + `<h3>行业总览与市场空间</h3>` + 「行业总览」**原始正文**
            （两段 src 来源注统一挪到最末）
  3. toc  : 「公司链条」锚点 m19 → m20
            （风险矩阵归回公司投资段尾，公司链条段首变为 m20）

为什么只需动这三处
  回滚态（31 模块）删掉「行业总览与市场空间」后，模块标题序列与**当前状态完全一致**
  ⇒ 其余 28 个模块的 title / html / 编号 / 交叉引用**一个字节都不用改**。

用法
  python build/fix_merge_600456.py           # 干跑，只打印计划
  python build/fix_merge_600456.py --go      # 真正写库
"""
import json, io, os, re, sys, time, urllib.request

CODE = '600456'
SNAP = 'build/backup/600456_pre_merge_m19_into_m25_20260920-172248.json'
GO = '--go' in sys.argv

cfg = json.load(io.open('build/cloud.json', encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
KEY = cfg['key']


def req(path, method='GET', body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method, headers={
        'apikey': KEY, 'Authorization': 'Bearer ' + KEY,
        'Accept': 'application/json', 'Content-Type': 'application/json',
        'Prefer': 'return=representation'})
    raw = urllib.request.urlopen(r, timeout=120).read().decode('utf-8')
    return json.loads(raw) if raw.strip() else []


def split_src(html):
    """把末尾的 <p class="src">…</p> 剥出来 → (body, src)。"""
    m = re.search(r'\s*(<p class="src">[\s\S]*?</p>)\s*$', html or '')
    if not m:
        return html or '', ''
    return html[:m.start()], m.group(1)


# ---------------- 原料：全部取自合并前快照 ----------------
snap = json.load(io.open(SNAP, encoding='utf-8'))
sm = {int(x['no']): x for x in snap['mods']}
risk, indover, tiintro = sm[19], sm[20], sm[25]

ti_body, ti_src = split_src(tiintro['html'])
io_body, io_src = split_src(indover['html'])

MERGED_H3 = '行业总览与市场空间'
new_m24 = (ti_body
           + '\n    <h3>%s</h3>\n    ' % MERGED_H3
           + io_body.lstrip()
           + '\n    ' + ti_src
           + '\n    ' + io_src)

# ---------------- 现状核对 ----------------
cur = req('wb_report_mods?code=eq.%s&select=id,no,seq,title,html&limit=500' % CODE)
cur = sorted(cur, key=lambda m: int(m['no']))
cm = {int(m['no']): m for m in cur}
rep = req('wb_reports?code=eq.%s&select=*&limit=5' % CODE)[0]
print('=' * 74)
print('600456 修正计划（把并入对象换回「行业总览与市场空间」）')
print('=' * 74)
print('快照       : %s' % SNAP)
print('当前模块数 : %d' % len(cur))
print()
print('--- ① m19 ---')
print('  改前 : %s   (len=%d)' % (cm[19]['title'], len(cm[19]['html'] or '')))
print('  改后 : %s   (len=%d)  ← 取合并前快照 m19' % (risk['title'], len(risk['html'] or '')))
print()
print('--- ② m24 ---')
print('  改前 : %s   (len=%d)' % (cm[24]['title'], len(cm[24]['html'] or '')))
print('  改后 : 正文 = 钛行业介绍原文(%d) + <h3>%s</h3> + 行业总览原文(%d)'
      % (len(ti_body), MERGED_H3, len(io_body)))
print('         + 来源注 2 段(移到最末)  ⇒ 合计 len=%d' % len(new_m24))
print('  校验 : 「行业总览与市场空间」出现 %d 次；「市场规模与增速」%d 次；src 段 %d 个'
      % (new_m24.count(MERGED_H3), new_m24.count('市场规模与增速'),
         new_m24.count('<p class="src">')))
print()
print('--- ③ toc ---')
oldtoc = rep['toc']
newtoc = []
for x in oldtoc:
    y = dict(x)
    if y.get('text') == '公司链条' and y.get('anchor') == 'm19':
        y['anchor'] = 'm20'
    newtoc.append(y)
for a, b in zip(oldtoc, newtoc):
    mark = '  ← 改' if a != b else ''
    print('  %-8s %-8s %s%s' % (a['anchor'], b['anchor'], b['text'], mark))
assert json.dumps(newtoc, ensure_ascii=False) != json.dumps(oldtoc, ensure_ascii=False), \
    'toc 没有任何变化，检查锚点'
print()
print('--- 不动的东西 ---')
print('  其余 %d 个模块的 title/html/编号 全部不变' % (len(cur) - 2))
print('  交叉引用无需改（编号结构前后一致：都是 30 模块，标题序列相同）')
print('  图表 22 张全部不涉及（m19/m20/m25 正文均无 data-chart）')
print()

if not GO:
    print('【干跑】未写库。确认无误后加 --go 执行。')
    sys.exit(0)

# ---------------- 写库 ----------------
now = int(time.time() * 1000)
print('写入中 …')

r1 = req('wb_report_mods?id=eq.%s_m19' % CODE, 'PATCH',
         {'title': risk['title'], 'html': risk['html'], 'up': now})
print('  ① m19 → %s  (返回 %d 行)' % (risk['title'], len(r1)))

r2 = req('wb_report_mods?id=eq.%s_m24' % CODE, 'PATCH',
         {'html': new_m24, 'up': now})
print('  ② m24 → 已并入「%s」  (返回 %d 行，html=%d 字符)'
      % (MERGED_H3, len(r2), len(r2[0]['html']) if r2 and 'html' in r2[0] else -1))

body = {'toc': newtoc}
if 'up' in rep:
    body['up'] = now
r3 = req('wb_reports?code=eq.%s' % CODE, 'PATCH', body)
print('  ③ toc → 「公司链条」锚点 m20  (返回 %d 行)' % len(r3))

# ---------------- 回读核对 ----------------
print()
print('--- 回读核对 ---')
chk = req('wb_report_mods?code=eq.%s&select=id,no,seq,title,html&limit=500' % CODE)
chk = sorted(chk, key=lambda m: int(m['no']))
ck = {int(m['no']): m for m in chk}
ok = True


def assert_(cond, msg):
    global ok
    print(('  ✅ ' if cond else '  ❌ ') + msg)
    if not cond:
        ok = False


assert_(len(chk) == 30, '模块数 = 30（实际 %d）' % len(chk))
assert_([int(m['no']) for m in chk] == list(range(1, 31)), '编号 1..30 连续')
assert_(ck[19]['title'] == '风险矩阵', 'm19 标题 = 风险矩阵（实际 %s）' % ck[19]['title'])
assert_((ck[19]['html'] or '').count('risk-item') == 5,
        'm19 正文含 5 张风险卡（实际 %d）' % (ck[19]['html'] or '').count('risk-item'))
assert_(ck[24]['title'] == '钛行业介绍与市场规模',
        'm24 标题 = 钛行业介绍与市场规模')
assert_('行业总览与市场空间' in (ck[24]['html'] or ''), 'm24 正文含「行业总览与市场空间」')
assert_('市场规模与增速' in (ck[24]['html'] or ''), 'm24 正文含「市场规模与增速」小节')
assert_('18.3 万吨' in (ck[24]['html'] or ''), 'm24 正文含行业总览的 18.3 万吨数据')
assert_((ck[24]['html'] or '').count('<p class="src">') == 2, 'm24 末尾两段来源注')
assert_('风险矩阵' not in (ck[24]['html'] or ''), 'm24 正文已不含「风险矩阵」')

rep2 = req('wb_reports?code=eq.%s&select=*&limit=5' % CODE)[0]
t2 = {x['text']: x['anchor'] for x in rep2['toc']}
assert_(t2.get('公司链条') == 'm20', 'toc「公司链条」= m20（实际 %s）' % t2.get('公司链条'))
assert_(t2.get('行业分析') == 'm24', 'toc「行业分析」= m24')
assert_(t2.get('供需分析') == 'm25', 'toc「供需分析」= m25')
assert_(t2.get('公司投资') == 'm17', 'toc「公司投资」= m17')

print()
print('结论：' + ('全部通过 ✅' if ok else '存在问题 ❌'))
sys.exit(0 if ok else 1)
