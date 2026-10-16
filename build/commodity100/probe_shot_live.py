# -*- coding: utf-8 -*-
"""
对「线上那份字节」出功能面板截图：从 liuchaowang.cn 抓 commodity-daily.html，
注入交互脚本后截「多列批量导入」与「内置序列编辑」两个面板。

复用 probe_shot2.py 的注入脚本与截图框架，只把源页换成线上抓取的那一份。

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python probe_shot_live.py
"""
import io
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import probe_shot2 as S  # noqa: E402

LIVE = 'https://liuchaowang.cn/commodity-daily.html'
TMP_SRC = os.path.join(HERE, '_live_src2.html')


def main():
    req = urllib.request.Request(LIVE, headers={
        'Cache-Control': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WorkBuddy-Probe',
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    io.open(TMP_SRC, 'wb').write(data)
    print('线上字节:', len(data))

    S.SITE = os.path.join(HERE, '_shot_live_site')
    S.XLSX = os.path.join(S.SITE, '_shot_wide.xlsx')
    S.SRC_PAGE = TMP_SRC
    S.PORT = 8798
    S.SHOTS = [
        ('上线v2-多列批量导入.png', 'shot_up.html', S.S_UP, 1512, 1320),
        ('上线v2-内置序列编辑.png', 'shot_eb.html', S.S_BUILTIN, 1512, 1180),
    ]
    try:
        rc = S.main()
    finally:
        try:
            os.remove(TMP_SRC)
        except OSError:
            pass
    print('（已清理线上抓取临时文件）')
    return rc


if __name__ == '__main__':
    sys.exit(main())
