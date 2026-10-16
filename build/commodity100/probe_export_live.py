# -*- coding: utf-8 -*-
"""对「线上那份字节」跑导出/识别 E2E：从 liuchaowang.cn 抓 commodity-daily.html，
注入探针后在 localhost 跑同一套断言，证明线上代码本身能把导出的宽表识别成 31 列。

复用 probe_export_e2e.py 的全部断言与框架，只把源页换成线上抓取的那一份。

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python probe_export_live.py
"""
import hashlib
import io
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import probe_export_e2e as E  # noqa: E402

LIVE = 'https://liuchaowang.cn/commodity-daily.html'
TMP_SRC = os.path.join(HERE, '_export_live_src.html')
LOCAL = os.path.join(E.ROOT, 'deploy_site', 'commodity-daily.html')


def main():
    print('=' * 76)
    print('线上实机验证 · %s' % LIVE)
    print('=' * 76)
    req = urllib.request.Request(LIVE, headers={
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WorkBuddy-Probe',
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        code = r.status
        data = r.read()
    io.open(TMP_SRC, 'wb').write(data)
    print('HTTP        :', code)
    print('线上字节    :', len(data))
    print('线上 sha256 :', hashlib.sha256(data).hexdigest()[:24])
    if os.path.exists(LOCAL):
        lb = io.open(LOCAL, 'rb').read()
        print('本地 sha256 :', hashlib.sha256(lb).hexdigest()[:24])
        print('逐字节一致  :', '✓ 是' if lb == data else '✗ 否（注意 CDN 缓存）')
    print()

    E.SITE = os.path.join(HERE, '_export_live_site')
    E.SRC_PAGE = TMP_SRC
    E.PORT = 8808
    try:
        rc = E.main()
    finally:
        try:
            os.remove(TMP_SRC)
        except OSError:
            pass
    print('\n（已清理线上抓取临时文件）')
    return rc


if __name__ == '__main__':
    sys.exit(main())
