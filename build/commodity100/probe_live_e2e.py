# -*- coding: utf-8 -*-
"""
线上实机验证：把 liuchaowang.cn 上那份 commodity-daily.html 的**真实字节**抓下来，
注入探针脚本后在 localhost 跑交互断言。

与 probe_v2_e2e.py 的区别：那边的 SRC_PAGE 是本地构建产物；这里是从线上抓的。
两者 md5 应一致（部署时已核对），本脚本用于「验的就是线上那份」的收口证明。

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python probe_live_e2e.py
"""
import hashlib
import io
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import probe_v2_e2e as P  # noqa: E402  （复用它的 DBG / xlsx 生成 / 断言 / 服务框架）

LIVE = 'https://liuchaowang.cn/commodity-daily.html'
TMP_SRC = os.path.join(HERE, '_live_src.html')
LOCAL = os.path.join(P.ROOT, 'deploy_site', 'commodity-daily.html')


def fetch_live():
    req = urllib.request.Request(LIVE, headers={
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WorkBuddy-Probe',
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        code = r.status
        data = r.read()
    io.open(TMP_SRC, 'wb').write(data)
    return code, data


def main():
    print('=' * 74)
    print('线上实机验证 · %s' % LIVE)
    print('=' * 74)
    code, data = fetch_live()
    print('HTTP           :', code)
    print('线上字节       :', len(data))
    print('线上 sha256    :', hashlib.sha256(data).hexdigest()[:24])
    if os.path.exists(LOCAL):
        lb = io.open(LOCAL, 'rb').read()
        print('本地 sha256    :', hashlib.sha256(lb).hexdigest()[:24])
        print('逐字节一致     :', '✓ 是' if lb == data else '✗ 否（注意 CDN 缓存）')
    print()

    # 让探针用「线上字节」当源页。
    # 注意：SITE / XLSX / PORT 都在模块顶层算好了，必须一并覆盖（XLSX 依赖 SITE）。
    P.SITE = os.path.join(HERE, '_live_site')
    P.XLSX = os.path.join(P.SITE, '_v2_wide.xlsx')
    P.SRC_PAGE = TMP_SRC
    P.PORT = 8796
    try:
        rc = P.main()
    finally:
        try:
            os.remove(TMP_SRC)
        except OSError:
            pass
    print('\n（已清理线上抓取临时文件 %s）' % os.path.basename(TMP_SRC))
    return rc


if __name__ == '__main__':
    sys.exit(main())
