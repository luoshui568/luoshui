# -*- coding: utf-8 -*-
"""上线后「验线上那一份」：抓 liuchaowang.cn 真实字节 → 喂给同一套断言 + 截图。

坑：probe_shixiang_check 的 DELIVER 是模块顶层常量，monkeypatch 必须一并覆盖
    probe_shixiang_shot 的 DELIVER（截图脚本自己也要重读一遍源文件）。
"""
import importlib.util
import os
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, '..'))
HOST = 'https://liuchaowang.cn'

LIVE = {
    '思想体系总目.html': HOST + '/shixiang.html',
    '巴菲特股东信六十年维度全解.html': HOST + '/buffett.html',
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    tmp = tempfile.mkdtemp(prefix='_live_')
    for fn, url in LIVE.items():
        req = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'wb-probe'})
        data = urllib.request.urlopen(req, timeout=60).read()
        with open(os.path.join(tmp, fn), 'wb') as f:
            f.write(data)
        print('fetched %-34s %7d bytes' % (fn, len(data)))

    chk = load('chk', os.path.join(HERE, 'probe_shixiang_check.py'))
    chk.DELIVER = tmp
    rc = chk.main()

    shot = load('shot', os.path.join(HERE, 'probe_shixiang_shot.py'))
    shot.DELIVER = tmp
    shot.OUT = os.path.join(BASE, 'deliver')
    shot.main()
    print('\n线上字节断言 rc=%d（0=ALL GREEN）' % rc)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
