# -*- coding: utf-8 -*-
"""对「线上那份字节」跑「分组管理 + 导入面板分组列」E2E。

从 liuchaowang.cn 抓 commodity-daily.html → 注入探针 → localhost 跑同一套断言，
证明**线上代码本身**（而不是本地构建产物）分组功能可用、且一张生产表都不写。

★ 复用 probe_grp_e2e.py 的全部断言与框架，只把源页换成线上抓取的那一份。
  ★ SITE / XLSX / PORT 都是模块顶层常量，monkeypatch 时必须一并覆盖（踩过坑）。

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python probe_grp_live.py
"""
import hashlib
import io
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import probe_grp_e2e as E  # noqa: E402

LIVE = 'https://liuchaowang.cn/commodity-daily.html'
TMP_SRC = os.path.join(HERE, '_grp_live_src.html')
LOCAL = os.path.join(E.ROOT, 'deploy_site', 'commodity-daily.html')

# 线上那份必须能在源码里找到的记号
NEED = [
    (b'wb_c100_groups',        '分组云表名'),
    (b'openGrpMgr',            '分组管理面板'),
    (b'groupStats',            '分组统计'),
    (b'renameGroup',           '分组改名'),
    (b'deleteGroup',           '分组删除'),
    (b'newGroup',              '新建分组'),
    (b'groupOpts',             '导入面板分组下拉'),
    (b'applyTagDefault',       '默认分组自动跟随'),
    (b'applyTagAll',           '套用到所有行'),
    (b'data-tg=',              '逐行分组控件'),
    (b'up-tagall',             '套用按钮'),
    (b'mg-grp',                '管理面板入口'),
    (b'gm-add',                '新建分组按钮'),
]
MUST_NOT = [
    (b'"c":"gold"',            '旧的内置数据（应已摘除）'),
]


def main():
    print('=' * 78)
    print('线上实机验证 · %s' % LIVE)
    print('=' * 78)
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
    print('线上形态    :', '含内置数据' if b'"groups":[{' in data or b'"groups": [{' in data else '✓ 无内置数据（groups 为空）')
    print()
    print('线上内容抽查：')
    for needle, label in NEED:
        print('  %-24s %s' % (label, '✓ 在' if needle in data else '✗ 不在'))
    for needle, label in MUST_NOT:
        print('  %-24s %s' % (label, '✗ 仍在！' if needle in data else '✓ 不在'))
    print()

    E.SITE = os.path.join(HERE, '_grp_live_site')
    E.SRC_PAGE = TMP_SRC
    E.XLSX = os.path.join(E.SITE, E.XLSX_NAME)
    E.PORT = 8810
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
