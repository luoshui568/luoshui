# -*- coding: utf-8 -*-
"""走服务端管理员函数删除记录（业务表已收回 DELETE，只能走 RPC）。

用法：
    WB_ADMIN_PASS=你的密码 python build/admin_delete.py reportmod 600459_m24
    WB_ADMIN_PASS=... python build/admin_delete.py --user luoshui report 999999

⚠️ 密码只从环境变量 WB_ADMIN_PASS 读，不落盘、不打印、不提交。
   kind 取值：tasks / permits / milestones / watch / contacts / logs / works /
             stocks / report / reportmod / reportchart
   kind=report 会连带删掉该研报的模块与图表。
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']


def rpc(fn, args):
    req = urllib.request.Request(
        REST + 'rpc/' + fn,
        data=json.dumps(args, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + CFG['key'],
                 'Content-Type': 'application/json',
                 'User-Agent': 'wb'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:400]


def main():
    a = sys.argv[1:]
    user = 'luoshui'
    if '--user' in a:
        i = a.index('--user')
        user = a[i + 1]
        a = a[:i] + a[i + 2:]
    if len(a) < 2:
        print(__doc__)
        return 2
    kind, ids = a[0], a[1:]
    pwd = os.environ.get('WB_ADMIN_PASS', '').strip()
    if not pwd:
        print('✗ 环境变量 WB_ADMIN_PASS 为空')
        return 3

    st, r = rpc('wb_admin_login', {'p_user': user, 'p_pass': pwd, 'p_device': 'build-script'})
    if not isinstance(r, dict) or not r.get('ok'):
        print('✗ 登入失败', st, r)
        return 4
    tok = r.get('token')
    print('登入成功：%s（%s）' % (r.get('user'), r.get('name')))

    bad = 0
    for rid in ids:
        st, r = rpc('wb_admin_delete_row',
                    {'p_token': tok, 'p_kind': kind, 'p_id': rid, 'p_pass': pwd})
        ok = isinstance(r, dict) and r.get('ok')
        print('  %-24s %s %s' % (rid, '✅' if ok else '✗', r))
        if not ok:
            bad += 1

    rpc('wb_admin_logout', {'p_token': tok})
    print('\n完成：成功 %d / 失败 %d' % (len(ids) - bad, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
