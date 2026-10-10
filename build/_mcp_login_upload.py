# -*- coding: utf-8 -*-
"""登录 cloudbase（设备码）→ 自查托管 → 上传 `deploy/report.html` → 复验。

为什么需要它：本会话的工具清单里**没有** cloudbase MCP（连接器被标 disabled），
但服务本身是好的；而托管上传是**管理侧**操作，`build/cloud.json` 那把 key 只是
前端匿名 JWT（只能打 PostgREST）⇒ 只能靠 MCP 的 device 登录态。

★ 一个进程里做完全部步骤：device 登录态是否落盘未知，跨进程可能丢，
  所以「拿码 → 等授权 → 上传」必须在同一个 stdio 会话里完成。

用法（建议后台跑，超时给足）：
    LOGIN_WAIT=900 python build/_mcp_login_upload.py
输出里会有一行 `>>> 授权码 …` 与一行 `>>> 授权网址 …`，把这两样给用户。
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mcp_upload import MCP                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = float(os.environ.get('LOGIN_WAIT', '900'))
UPLOAD = os.environ.get('DO_UPLOAD', '1') == '1'


def text_of(res):
    for c in ((res or {}).get('result') or res or {}).get('content', []) or []:
        if c.get('type') == 'text':
            return c['text']
    return json.dumps(res, ensure_ascii=False)


def status(m, rid):
    r = m.call(rid, 'tools/call', {'name': 'auth', 'arguments': {'action': 'status'}})
    t = text_of(r)
    try:
        return json.loads(t)
    except Exception:                                              # noqa: BLE001
        return {'raw': t}


def main():
    m = MCP()
    m.call(1, 'initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                             'clientInfo': {'name': 'workbuddy-driver', 'version': '1.0'}})
    m.send({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}})
    print('[1] 列工具')
    names = [t['name'] for t in m.call(2, 'tools/list').get('result', {}).get('tools', [])]
    print('    共 %d 个；manageHosting=%s queryHosting=%s'
          % (len(names), 'manageHosting' in names, 'queryHosting' in names))

    print('[2] auth(status)')
    st = status(m, 3)
    print('    auth_status =', st.get('auth_status'))
    if st.get('auth_status') != 'LOGGED_IN':
        print('[3] 发起设备码登录')
        r = m.call(4, 'tools/call', {'name': 'auth',
                                     'arguments': {'action': 'start_auth',
                                                   'authMode': 'device'}})
        print('    start_auth →', text_of(r)[:1200])
        # 从返回里抠出用户码 / 网址（字段名各版本不一，全打出来给用户）
        for k in ('user_code', 'usercode', 'code', 'verification_uri',
                  'verification_url', 'verificationUri', 'url'):
            v = (r.get('result') or {}).get(k)
            if v:
                print('>>> %s … %s' % (k, v))
        print('    ⏳ 等待授权（最多 %d 秒）…' % WAIT)
        end = time.time() + WAIT
        i = 10
        while time.time() < end:
            time.sleep(5)
            st = status(m, i)
            i += 1
            a = st.get('auth_status')
            if a == 'LOGGED_IN':
                print('    ✓ 已登录')
                break
            if i % 12 == 0:
                print('    … 仍在等（%s）' % a)
        else:
            print('    ✗ 超时未登录')
            return 1
        print('    env:', st.get('current_env_id'), st.get('env_status'))

    print('[4] queryHosting（写前先看线上现状）')
    q = m.call(500, 'tools/call', {'name': 'queryHosting', 'arguments': {}})
    print(text_of(q)[:1500])

    if not UPLOAD:
        print('（DO_UPLOAD=0，只登录不传）')
        return 0

    print('[5] manageHosting upload report.html')
    body = {'action': 'upload', 'files': [
        {'localPath': os.path.join(ROOT, 'deploy', 'report.html'),
         'cloudPath': '/report.html'}]}
    r = m.call(600, 'tools/call', {'name': 'manageHosting', 'arguments': body})
    print(text_of(r)[:1500])

    print('[6] 复验')
    q = m.call(700, 'tools/call', {'name': 'queryHosting', 'arguments': {}})
    print(text_of(q)[:1500])
    return 0


if __name__ == '__main__':
    sys.exit(main())
