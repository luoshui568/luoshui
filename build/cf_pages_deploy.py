# -*- coding: utf-8 -*-
"""把 deploy/ 的上线产物发布到 Cloudflare Pages（直传模式，不依赖 GitHub 集成）

用法：
    export CF_API_TOKEN=xxxxx            # 或 Windows: set CF_API_TOKEN=xxxxx
    python build/cf_pages_deploy.py                  # 检查 + 部署
    python build/cf_pages_deploy.py --check-only     # 只校验 Token 与项目，不部署

⚠️ Token 只从环境变量读取，本脚本**不写盘、不打印、不提交**。
⚠️ 只上传 deploy/index.html 与 deploy/report.html —— 模板与构建脚本属于源码，不进 Pages。

需要 Token 权限：Account → Cloudflare Pages → Edit
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

API = 'https://api.cloudflare.com/client/v4'
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY = os.path.join(ROOT, 'deploy')

# Pages 上要发布的文件（相对 deploy/）
PUBLISH = ['index.html', 'report.html']

PROXY = os.environ.get('CF_PROXY', 'http://127.0.0.1:7892')
NODE_DIR = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3'
NODE_WS = r'C:\Users\50522\.workbuddy\binaries\node\workspace'


def opener():
    """所有出网请求都走本机代理：沙箱代理只放行 api.github.com，Cloudflare 必须走 7892。"""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({'https': PROXY, 'http': PROXY}))


def cf(path, method='GET', body=None, token=None):
    url = API + path
    data = None
    headers = {'Authorization': 'Bearer ' + token, 'User-Agent': 'wb-cf-pages/1.0'}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener().open(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {'errors': [{'message': 'unparsable body'}]}
    except Exception as e:
        return -1, {'errors': [{'message': str(e)}]}


def err_text(j, n=3):
    out = []
    for e in (j or {}).get('errors', [])[:n]:
        out.append('%s (code %s)' % (e.get('message'), e.get('code')))
    return ' / '.join(out) or json.dumps(j, ensure_ascii=False)[:220]


def main():
    check_only = '--check-only' in sys.argv
    token = os.environ.get('CF_API_TOKEN', '').strip()
    project = 'luoshui'
    for i, a in enumerate(sys.argv):
        if a == '--project' and i + 1 < len(sys.argv):
            project = sys.argv[i + 1]

    print('=' * 74)
    print('Cloudflare Pages 发布 · 项目 %s' % project)
    print('=' * 74)

    # ---------- 0) Token ----------
    if not token:
        print('✗ 环境变量 CF_API_TOKEN 为空。')
        print('   PowerShell : $env:CF_API_TOKEN="你的token"; python build/cf_pages_deploy.py')
        print('   CMD        : set CF_API_TOKEN=你的token && python build/cf_pages_deploy.py')
        return 2

    st, j = cf('/user/tokens/verify', token=token)
    if st != 200 or not j.get('success'):
        print('✗ Token 校验失败 [HTTP %s] %s' % (st, err_text(j)))
        return 3
    print('[1] Token 校验通过 · 状态 = %s' % (j.get('result') or {}).get('status'))

    # ---------- 1) 账号 ----------
    st, j = cf('/accounts', token=token)
    if st != 200 or not j.get('success'):
        print('✗ 取账号失败 [HTTP %s] %s（Token 可能缺少 Pages:Edit 所属的账户范围）' % (st, err_text(j)))
        return 4
    accts = j.get('result') or []
    if not accts:
        print('✗ 该 Token 下没有任何账号。')
        return 4
    acct = accts[0]
    aid = acct['id']
    print('[2] 账号 = %s (%s) · 共 %d 个' % (acct.get('name'), aid, len(accts)))

    # ---------- 2) 项目 ----------
    st, j = cf('/accounts/%s/pages/projects/%s' % (aid, project), token=token)
    if st == 200 and j.get('success'):
        pr = j['result']
        print('[3] 项目已存在 · 生产分支 = %s · 子域 = %s.pages.dev'
              % (pr.get('production_branch'), pr.get('subdomain') or project))
    else:
        st2, j2 = cf('/accounts/%s/pages/projects' % aid, 'POST',
                     {'name': project, 'production_branch': 'main'}, token=token)
        if st2 not in (200, 201) or not j2.get('success'):
            print('✗ 建项目失败 [HTTP %s] %s' % (st2, err_text(j2)))
            return 5
        pr = j2['result']
        print('[3] 项目已创建 · 子域 = %s.pages.dev' % (pr.get('subdomain') or project))

    # ---------- 3) 待发布文件清单 ----------
    files = []
    for rel in PUBLISH:
        fp = os.path.join(DEPLOY, rel)
        if not os.path.exists(fp):
            print('✗ 缺少产物 %s —— 先跑 python build/build.py' % fp)
            return 6
        files.append((rel, fp, os.path.getsize(fp)))
    for rel, fp, sz in files:
        print('    · %-14s %9d B' % (rel, sz))

    if check_only:
        print()
        print('[check-only] 未执行部署。去掉 --check-only 即可发布。')
        return 0

    # ---------- 4) 暂存目录（只放产物）----------
    stage = tempfile.mkdtemp(prefix='cfpages_')
    try:
        for rel, fp, _ in files:
            shutil.copy2(fp, os.path.join(stage, rel))
        # Pages 默认把根当静态目录；Spa 不需要。加一个 404 兜底指向工作台。
        with io.open(os.path.join(stage, '404.html'), 'w', encoding='utf-8') as f:
            f.write('<!doctype html><meta charset="utf-8">'
                    '<meta http-equiv="refresh" content="0;url=/index.html">'
                    '<title>跳转中…</title><a href="/index.html">回到工作台</a>')

        # ---------- 5) 调 wrangler 直传 ----------
        wrangler = os.path.join(NODE_WS, 'node_modules', 'wrangler', 'bin', 'wrangler.js')
        if not os.path.exists(wrangler):
            print('✗ 未找到 wrangler（%s）' % wrangler)
            print('  先执行：cd %s && npm install wrangler' % NODE_WS)
            return 7

        env = dict(os.environ)
        env.update({
            'CLOUDFLARE_API_TOKEN': token,
            'CLOUDFLARE_ACCOUNT_ID': aid,
            'HTTPS_PROXY': PROXY, 'HTTP_PROXY': PROXY,
            'NO_COLOR': '1', 'CI': '1',
        })
        cmd = [os.path.join(NODE_DIR, 'node.exe'), wrangler,
               'pages', 'deploy', stage,
               '--project-name', project,
               '--branch', 'main',
               '--commit-dirty=true']
        print('[4] 上传中（wrangler direct upload）…')
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                           encoding='utf-8', errors='replace', env=env, cwd=NODE_WS)
        out = (p.stdout or '') + (p.stderr or '')
        for line in out.splitlines():
            if line.strip():
                print('    | ' + line.strip()[:180])
        if p.returncode != 0:
            print('✗ 部署失败（exit %d）' % p.returncode)
            return 8
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    # ---------- 6) 收尾 ----------
    st, j = cf('/accounts/%s/pages/projects/%s' % (aid, project), token=token)
    sub = project
    if st == 200 and j.get('success'):
        sub = j['result'].get('subdomain') or project
    print()
    print('=' * 74)
    print('✓ 发布完成')
    print('=' * 74)
    print('  工作台 : https://%s.pages.dev/index.html' % sub)
    print('  研报页 : https://%s.pages.dev/report.html?code=600456' % sub)
    print('  控制台 : https://dash.cloudflare.com/%s/pages/view/%s' % (aid, project))
    return 0


if __name__ == '__main__':
    sys.exit(main())
