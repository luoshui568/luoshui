# -*- coding: utf-8 -*-
"""上传 deploy/report.html 到 CloudBase 静态托管（管理侧，走 MCP 的 device 登录态）。

与 `_mcp_login_upload.py` 的区别：**不发起登录**，只做「确认已登录 → 看线上现状 →
上传 → 复验」。因为 auth 已经落盘（`auth_status: READY` + 环境自动绑定），
跨进程可复用，不必把「拿码-等授权-上传」挤在一个进程里。

用法：
    python build/_do_upload.py            # 干跑：只查状态、不传（默认 report.html）
    python build/_do_upload.py --go       # 真传
    python build/_do_upload.py --files deploy/index.html:/index.html --go
                                          # 指定文件（逗号分隔可多个，逐文件复验）
"""
import hashlib
import io
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mcp_upload import MCP                                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = '--go' in sys.argv
ORIGIN = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com'


def _parse_files():
    """--files a/b.html:/b.html,c/d.html:/d.html ；缺省只传 report.html。"""
    if '--files' in sys.argv:
        i = sys.argv.index('--files')
        if i + 1 < len(sys.argv):
            out = []
            for it in sys.argv[i + 1].split(','):
                it = it.strip()
                if not it:
                    continue
                rel, cp = it.split(':')
                out.append((rel.strip(), cp.strip()))
            if out:
                return out
    return [('deploy/report.html', '/report.html')]


FILES = _parse_files()


def text_of(res):
    r = res.get('result', res)
    for c in (r.get('content') or []):
        if c.get('type') == 'text':
            return c['text']
    return json.dumps(r, ensure_ascii=False)


def live_md5(cloud='report.html'):
    """线上某文件的 md5；抓不到返回 None（不来就说明网络抖动，重试一次）。"""
    site = ORIGIN + '/' + cloud.lstrip('/')
    for i in range(3):
        try:
            rq = urllib.request.Request(site, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 Chrome/126 Safari/537.36'})
            with urllib.request.urlopen(rq, timeout=90) as r:
                b = r.read()
            return len(b), hashlib.md5(b).hexdigest()[:12]
        except Exception as e:                                     # noqa: BLE001
            print('    （第 %d 次抓线上失败：%s）' % (i + 1, str(e)[:90]))
    return None


def main():
    print('=== 本机文件 ===')
    plan = []
    for rel, cp in FILES:
        p = os.path.join(ROOT, rel.replace('/', os.sep))
        b = io.open(p, 'rb').read()
        h = hashlib.md5(b).hexdigest()[:12]
        plan.append((p, cp))
        print('  %-22s %9d B  md5=%s' % (rel, len(b), h))

    lm = live_md5(FILES[0][1])
    print('  线上 %-16s' % FILES[0][1], ('%9d B  md5=%s' % lm) if lm else '（抓不到）')

    m = MCP()
    m.call(1, 'initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                             'clientInfo': {'name': 'workbuddy-driver', 'version': '1.0'}})
    m.send({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}})
    print('\n=== auth(status) ===')
    a = m.call(2, 'tools/call', {'name': 'auth', 'arguments': {'action': 'status'}})
    t = text_of(a)
    try:
        d = json.loads(t)
        print('  auth_status = %s | env = %s (%s) | %s'
              % (d.get('auth_status'), d.get('current_env_id'),
                 d.get('env_status'), str(d.get('message'))[:60]))
        if d.get('auth_status') not in ('READY', 'LOGGED_IN'):
            print('✗ 未登录，先走 auth(start_auth)')
            return 2
    except Exception:                                              # noqa: BLE001
        print(t[:600])

    # queryHosting 的 action 是**必填**（enum: websiteConfig/status/findFiles/
    # listFiles/domainStatus）—— 不传会直接 -32602。
    print('\n=== 上传前 queryHosting(findFiles prefix=report) ===')
    print(text_of(m.call(3, 'tools/call', {
        'name': 'queryHosting',
        'arguments': {'action': 'findFiles', 'prefix': 'report'}}))[:900])

    if not GO:
        print('\n（干跑，未上传；加 --go 才真传）')
        return 0

    print('\n=== manageHosting upload ===')
    body = {'action': 'upload',
            'files': [{'localPath': p, 'cloudPath': cp} for p, cp in plan]}
    print('  args =', json.dumps(body, ensure_ascii=False))
    r = m.call(10, 'tools/call', {'name': 'manageHosting', 'arguments': body})
    print(text_of(r)[:1800])

    print('\n=== 上传后 queryHosting(findFiles prefix=report) ===')
    print(text_of(m.call(20, 'tools/call', {
        'name': 'queryHosting',
        'arguments': {'action': 'findFiles', 'prefix': 'report'}}))[:1200])

    print('\n=== 复验线上 md5 ===')
    okall = True
    for p, cp in plan:
        want = hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]
        lm2 = live_md5(cp)
        same = bool(lm2 and lm2[1] == want)
        okall = okall and same
        print('  %-22s → %-16s 本机 %s / 线上 %s  %s'
              % (os.path.basename(p), cp, want,
                 lm2[1] if lm2 else '抓不到', '✓ 一致' if same else '✗ 不一致'))
    print('  结论：', '✓ 全部一致' if okall else '✗ 有不一致（可能 CDN 缓存，稍后重试）')
    return 0 if okall else 1


if __name__ == '__main__':
    sys.exit(main())
