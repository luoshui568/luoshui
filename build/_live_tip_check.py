# -*- coding: utf-8 -*-
"""线上壳的功能终验：抓线上 report.html → 抽 FNS.mapTip / mapCnTip → 喂**线上库里**
的真实令牌与真实 opt → 打印实际悬浮文案。

为什么必须这样验：上传成功 ≠ 功能正确。这两个函数原先把「钛铁矿 / 万吨 / 69000」
写死在源码里，若上传没生效（或 CDN 缓存），悬浮会显示成「钛铁矿储量 万吨 占全球 xx%」。
本脚本直接在**线上壳源码**上执行，绕开一切推测。

签名：`FNS.mapTip(a, opt)` / `FNS.mapCnTip(a, opt)` → 返回 `function(p)`，
`p` 是 ECharts 的 params 对象。百分比在 `mapCnTip` 里由 `opt.series[].data` 求和得出
⇒ 必须传**真实 opt**，不能只传令牌。
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
SITE = ('https://fdels568-d7g1d8o3y90a80cd7-1483776268'
        '.tcloudbaseapp.com/report.html')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

# (公司, 图槽, 函数, 悬停区域, 期望里必须出现 / 绝不出现)
CASES = [
    ('600459', 'chartPgmWorldMap', 'mapTip', 'South Africa', '铂族', ['钛铁矿', '万吨']),
    ('600459', 'chartPgmWorldMap', 'mapTip', 'Germany', '暂无', []),
    ('600459', 'chartPgmCNMap', 'mapCnTip', '甘肃', '铂族', ['钛铁矿']),
    ('002237', 'chartAuWorldMap', 'mapTip', 'Australia', '黄金', ['钛铁矿', '万吨']),
    ('002237', 'chartAuCNMap', 'mapCnTip', '山东', '金矿', ['钛铁矿']),
    ('600456', 'chartTiWorldMap', 'mapTip', 'South Africa', '钛铁矿', []),   # 存量回归
    ('600456', 'chartTiCNMap', 'mapCnTip', '四川', '钛铁矿', []),            # 存量回归
]


def fetch(url):
    rq = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(rq, timeout=120) as r:
        return r.read()


def grab_fn(src, key):
    """抠出 `key: function(...){...}` 的完整源码（大括号配对）。"""
    i = src.index(key + ': function')
    j = src.index('{', i)
    d = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            d += 1
        elif src[k] == '}':
            d -= 1
            if d == 0:
                return src[i:k + 1]
    raise SystemExit('✗ 没找到 %s 的结尾' % key)


def pg(path):
    cfg = json.load(io.open(os.path.join(ROOT, 'build', 'cloud.json'),
                            encoding='utf-8'))
    base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    h = {'apikey': cfg['key'], 'Authorization': 'Bearer ' + cfg['key'],
         'Accept': 'application/json'}
    rq = urllib.request.Request(base + path, headers=h)
    with urllib.request.urlopen(rq, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def run(js):
    p = os.path.join(ROOT, 'build', '_ltc.js')
    io.open(p, 'w', encoding='utf-8').write(js)
    r = subprocess.run([NODE, p], capture_output=True)
    return (r.stdout.decode('utf-8', 'replace')
            + (('\nERR ' + r.stderr.decode('utf-8', 'replace')[:300])
               if r.stderr.strip() else ''))


TOKEN_CACHE = {}


def token_and_opt(code, slot):
    k = (code, slot)
    if k in TOKEN_CACHE:
        return TOKEN_CACHE[k]
    rows = pg('wb_report_charts?report_id=eq.%s&select=id,opt&limit=80' % code)
    out = (None, None)
    for r in rows:
        cid = r['id']
        name = cid[len(code) + 1:] if cid.startswith(code + '_') else cid
        if name == slot:
            o = r['opt']
            o = json.loads(o) if isinstance(o, str) else o
            out = (((o or {}).get('tooltip') or {}).get('formatter'), o)
            break
    TOKEN_CACHE[k] = out
    return out


def main():
    print('=== 抓线上 report.html ===')
    b = fetch(SITE)
    live = b.decode('utf-8')
    lp = os.path.join(ROOT, 'deploy', 'report.html')
    # ★★★ 必须**二进制读**：文本模式会把 CRLF 归一化成 LF，
    #     re-encode 后与线上差「行数」个字节 ⇒ 曾算出「不一致」的假象。
    lb = io.open(lp, 'rb').read()
    local = lb.decode('utf-8')
    m5 = hashlib.md5(b).hexdigest()
    print('  线上 %d B  md5=%s' % (len(b), m5[:12]))
    print('  本机 %d B  md5=%s' % (len(lb), hashlib.md5(lb).hexdigest()[:12]))
    print('  与 deploy/ 一致：%s' % ('✅' if m5 == hashlib.md5(lb).hexdigest()
                                    else '❌'))

    print('\n=== 两个 FNS 函数：线上 vs 本机 源码逐字节 ===')
    src = {}
    for key in ('mapTip', 'mapCnTip'):
        a = grab_fn(live, key)
        c = grab_fn(local, key)
        src[key] = a
        print('  %-10s 线上 %5d / 本机 %5d → %s'
              % (key, len(a), len(c), '一致 ✅' if a == c else '不一致 ❌'))

    print('\n=== 用线上壳跑线上库的真实令牌 ===')
    bad = []
    for code, slot, fn, region, must, mustnot in CASES:
        tok, opt = token_and_opt(code, slot)
        if tok is None:
            print('  %-8s %-20s ✗ 线上没有这个图行' % (code, slot))
            bad.append((code, slot, '缺图行'))
            continue
        arg = tok[len('{{fn:' + fn + ':'):-2] if tok.startswith('{{fn:') else tok
        body = src[fn][src[fn].index('function'):]
        js = ('var f=%s;\nvar fmt=f(%s,%s);\nvar r=fmt({name:%s});\n'
              'console.log(String(r).replace(/<[^>]+>/g,"|").replace(/\\|+/g,"|"));\n'
              % (body, json.dumps(arg, ensure_ascii=False),
                 json.dumps(opt, ensure_ascii=False), json.dumps(region)))
        out = run(js).strip().replace('\n', ' ')
        ok = (must in out) and not any(x in out for x in mustnot)
        if not ok:
            bad.append((code, slot, out[:120]))
        print('  %-8s %-20s %-14s %s %s'
              % (code, slot, region, '✅' if ok else '❌', out[:120]))

    print('\n=== 结论 ===')
    if bad:
        print('  ✗ %d 项不符：' % len(bad))
        for x in bad:
            print('     ', x)
    else:
        print('  ✅ 全部通过：新矿种显示自己的指标名/单位/分母，存量钛铁矿一字未变')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
