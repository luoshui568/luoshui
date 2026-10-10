# -*- coding: utf-8 -*-
"""上线后回读复验：默认域名 + 自定义域名，两个文件各比一次 md5。

★ 必须**二进制读** —— 文本模式会把 CRLF 归一化，导致 md5 假性不符。
★ 走 urllib 而不是 headless：线上自定义域名在无头浏览器里会被拦成「风险提醒」页，
  但 urllib 直取拿到的是真文件（已在记忆里立过铁律）。
"""
import hashlib
import io
import os
import sys
import time
import urllib.request

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOSTS = [
    ('默认域名', 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com'),
    ('自定义域名', 'https://liuchaowang.cn'),
]
FILES = [
    ('research.html', os.path.join(ROOT, 'deploy', 'research.html')),
    ('market-history.html', os.path.join(ROOT, 'deploy', 'market-history.html')),
]
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(url, headers={'User-Agent': UA,
                                                      'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(rq, timeout=120) as f:
                return f.read()
        except Exception as e:                                     # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise last


def main():
    print('=== 本机基准 ===')
    want = {}
    for name, p in FILES:
        h = hashlib.md5(io.open(p, 'rb').read()).hexdigest()
        want[name] = h
        print('  %-22s %9d B  md5 %s' % (name, os.path.getsize(p), h[:12]))

    allok = True
    for host_name, host in HOSTS:
        print('\n=== %s  %s ===' % (host_name, host))
        for name, _ in FILES:
            url = '%s/%s?t=%d' % (host, name, int(time.time()))
            try:
                b = get(url)
            except Exception as e:                                 # noqa: BLE001
                print('  %-22s ❌ 抓取失败 %s' % (name, str(e)[:110]))
                allok = False
                continue
            h = hashlib.md5(b).hexdigest()
            ok = (h == want[name])
            allok = allok and ok
            tip = ''
            if not ok and len(b) < 30000 and len(want[name]) and '</html>' not in b.decode('utf-8', 'ignore')[-500:]:
                tip = '  ⚠️ 像个「风险提醒」拦截页'
            print('  %-22s %9d B  md5 %s  %s%s'
                  % (name, len(b), h[:12], '✓ 一致' if ok else '✗ 不一致', tip))

    # ---- 内容断言 ----
    print('\n=== 内容断言（线上 research.html 正文）===')
    try:
        b = get('%s/research.html?t=%d' % (HOSTS[0][1], int(time.time())))
        h = b.decode('utf-8')
        checks = {
            '含友情链接区块':   '<b>友情链接</b>' in h,
            '指向 market-history.html': 'href="market-history.html"' in h,
            '目标页标题文案':   '中国股市牛熊全史 · 1990—2026' in h,
            '免责声明仍在':     '免责声明' in h,
            '旧行为未被破坏（拼音表）': 'PY_OK' in h,
            '旧行为未被破坏（鉴权）':   'wb_auth_v1' in h,
            '旧的研报跳转仍在':  "report.html?code=" in h,
        }
        for k, v in checks.items():
            print('  %-28s %s' % (k, '✓' if v else '✗'))
            allok = allok and v
    except Exception as e:                                          # noqa: BLE001
        print('  ❌ 抓取失败', e)
        allok = False

    print('\n结论：', '✓ 全部通过' if allok else '✗ 有问题，见上')
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
