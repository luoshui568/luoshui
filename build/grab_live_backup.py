# -*- coding: utf-8 -*-
"""上线前：把**线上现状**三页抓到本地备份（二进制写盘，保真 CRLF）。"""
import hashlib, io, os, time, urllib.request

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DOM = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com'
ts = time.strftime('%Y%m%d-%H%M%S')
DST = os.path.join(ROOT, 'build', 'backup_hosting_pre_' + ts)
os.makedirs(DST, exist_ok=True)


def get(url):
    r = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'})
    with urllib.request.urlopen(r, timeout=90) as f:
        return f.read()


# 首页文档已是 index.html：抓域名根就等于抓 index.html，带 cache-buster 防 CDN 脏读
TARGETS = [
    ('index.html', DOM + '/?t=%d' % int(time.time())),
    ('report.html', DOM + '/report.html?t=%d' % int(time.time())),
    ('research.html', DOM + '/research.html?t=%d' % int(time.time())),
]

print('备份目录：%s' % DST)
print()
total = 0
for name, url in TARGETS:
    try:
        b = get(url)
    except Exception as e:
        print('  %-14s ❌ %s' % (name, e))
        continue
    p = os.path.join(DST, name)
    with open(p, 'wb') as f:
        f.write(b)
    total += len(b)
    print('  %-14s %9d B  md5 %s' % (name, len(b), hashlib.md5(b).hexdigest()[:12]))

print()
print('合计 %d B' % total)

# 与本机 deploy/ 比一比，看清「本次要改的是什么」
print()
print('--- 与本机 deploy/ 对比（线上 vs 本机）---')
for name, _ in TARGETS:
    lp = os.path.join(ROOT, 'deploy', name)
    op = os.path.join(DST, name)
    if not os.path.exists(op):
        continue
    lb = io.open(lp, 'rb').read()
    ob = io.open(op, 'rb').read()
    same = hashlib.md5(lb).hexdigest() == hashlib.md5(ob).hexdigest()
    print('  %-14s %s   本机 %8d B / 线上 %8d B' % (name, '一致' if same else '有差异', len(lb), len(ob)))
