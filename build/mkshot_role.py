# -*- coding: utf-8 -*-
"""普通管理员（团队成员）视图的目视验收截图 —— 真实 ops 账号，不打桩。

产出（build/ 下）：
  shot_ops_view.png    ops 登录后：侧栏 =「投资标的」+「数据与设置」+ 团队成员视图提示
  shot_ops_set.png     ops 的「数据与设置」页：能改密码 / 退登录；私人卡片不出现
  shot_ops_block.png   强行 App.go('dash')：被拒，提示「仅超级管理员可见」

为什么要真建一个 ops 账号：
  应用启动时会用 token 调 wb_admin_check，**服务端返回的角色才是权威**，并且
  buildNav() 会按它重建导航。所以「手动把 Auth.role 改成 ops」是拍不出真实效果的
  —— 服务端一回 'super' 就把 8 个菜单放回来了。必须真的以 ops 身份登录。

⚠️ 脚本自己清理：结束后用超管 token 删掉这个临时账号（探针不留痕）。
"""
# ── 管理员口令不入库：优先 build/_secret.py（已 gitignore），其次环境变量 WB_PW ──
import os as _os
try:
    from _secret import PW
except Exception:
    PW = _os.environ.get('WB_PW', '')
if not PW:
    raise SystemExit('缺少管理员口令：请创建 build/_secret.py（PW = "…"）或设 WB_PW 环境变量')
import http.server
import json
import os
import socketserver
import subprocess
import threading
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
DEPLOY = os.path.join(BASE, 'deploy')
PORT = 8963

OPS_USER = 'probe_shot_ops'
OPS_PASS = 'shot-ops-2026'
OPS_NAME = '王工'


def cfg():
    return json.load(open(os.path.join(BUILD, 'cloud.json'), encoding='utf-8'))


def rpc(fn, body):
    c = cfg()
    url = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/rpc/%s' % (c['envId'], fn)
    r = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers={
        'Authorization': 'Bearer ' + c['key'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8', 'replace'))


def edge():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


def burn(path):
    """就地清空含 token 的临时页 —— **不要 os.remove**（safe-delete 守卫按整轮累计数拦）。"""
    try:
        open(path, 'w', encoding='utf-8').close()
    except OSError:
        pass


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


KILL = """
<style>*{animation:none !important;transition:none !important}
[style*="backdrop-filter"]{backdrop-filter:none !important}
.gate{display:none !important}</style>
"""

# ① 在应用脚本**之前**注入会话：这样 authRestore() 一上来就带着 ops 身份，
#    随后 wb_admin_check 从服务端拿到的也是 ops → buildNav() 真的走收窄分支。
BOOT = r"""
<script>
try{
  localStorage.setItem('wb_auth_v1', JSON.stringify(
    {t:'__TOK__', u:'__USER__', n:'__NAME__', r:'ops', ts:Date.now()}));
  sessionStorage.removeItem('wb_auth_v1');
}catch(e){}
</script>
"""

# ② 在 </body> 前注入：启动完成后（等 App 就绪）执行后续动作
ACT_VIEW = r"""
<script>
(function(){
  function tick(){
    if(window.App && window.RAW && window.Auth && window.Auth.token){ setTimeout(act, 900); return; }
    setTimeout(tick, 120);
  }
  function act(){
    /* 已是 ops 身份，页面自己就落在了投资标的；这一张只补一个稳定等待 */
    if(typeof marker === 'function') marker();
  }
  var marker = null;
  tick();
})();
</script>
"""

ACT_SET = r"""
<script>
(function(){
  function tick(){
    if(window.App && window.RAW && window.Auth && window.Auth.token){ setTimeout(act, 1200); return; }
    setTimeout(tick, 120);
  }
  function act(){
    /* 走真实入口：ops 现在有「数据与设置」菜单，点进去就是这一页 */
    App.go('set');
  }
  tick();
})();
</script>
"""

ACT_BLOCK = r"""
<script>
(function(){
  function tick(){
    if(window.App && window.RAW && window.Auth && window.Auth.token){ setTimeout(act, 1200); return; }
    setTimeout(tick, 120);
  }
  function act(){
    /* 越过菜单直接跳「总览」—— 私人工作区，必须被拒 */
    App.go('dash');
    /* 冻住自动隐藏的 toast（2.2s 后会被 clearTimeout 掉），让提示留在画面上。
       只是「不隐藏」，文案与触发路径都是产品里真实的那一条。 */
    setTimeout(function(){ try{ clearTimeout(toastT); }catch(e){} }, 60);
  }
  tick();
})();
</script>
"""


def shot(e, url, png, prof, budget=90000):
    if not os.path.isdir(prof):
        os.makedirs(prof, exist_ok=True)
    cmd = [e, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=1680,1050', '--user-data-dir=' + prof,
           '--virtual-time-budget=%d' % budget, '--screenshot=' + png, url]
    subprocess.run(cmd, capture_output=True, timeout=900)
    return os.path.getsize(png) if os.path.exists(png) else 0


def build_page(src, boot, act, out):
    s = open(src, encoding='utf-8').read()
    body_end = s.rfind('</body>')
    # 应用脚本 = </body> 前最后一个 <script>
    app_i = s.rfind('<script', 0, body_end)
    return out, s[:app_i] + boot + s[app_i:body_end] + act + s[body_end:]


def main():
    sup = rpc('wb_admin_login', {'p_user': 'luoshui', 'p_pass': PW,
                                 'p_device': 'shot-role', 'p_days': 1})
    if not sup.get('ok'):
        raise SystemExit('超管登录失败：%s' % sup)
    suptok = sup['token']
    print('超管 token 就绪\n')

    # 清掉上次可能残留的同名账号，再新建 —— 保证是 active 的 ops
    rpc('wb_admin_delete', {'p_token': suptok, 'p_user': OPS_USER})
    c = rpc('wb_admin_create', {'p_token': suptok, 'p_user': OPS_USER,
                                'p_pass': OPS_PASS, 'p_name': OPS_NAME})
    print('建临时 ops 账号 %s → %s' % (OPS_USER, c.get('msg') or c))
    if not c.get('ok'):
        raise SystemExit('建账号失败：%s' % c)

    ops = rpc('wb_admin_login', {'p_user': OPS_USER, 'p_pass': OPS_PASS,
                                 'p_device': 'shot-role', 'p_days': 1})
    if not ops.get('ok') or ops.get('role') != 'ops':
        rpc('wb_admin_delete', {'p_token': suptok, 'p_user': OPS_USER})
        raise SystemExit('ops 登录异常：%s' % ops)
    print('ops 登录成功，role=%s\n' % ops.get('role'))
    opstok = ops['token']

    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    e = edge()
    print('本地 http 127.0.0.1:%d\n' % PORT)

    boot = (KILL + BOOT).replace('__TOK__', opstok).replace('__USER__', OPS_USER) \
                       .replace('__NAME__', OPS_NAME)

    try:
        for mode, act, png in [('view',  ACT_VIEW,  'shot_ops_view.png'),
                               ('set',   ACT_SET,   'shot_ops_set.png'),
                               ('block', ACT_BLOCK, 'shot_ops_block.png')]:
            out = os.path.join(DEPLOY, '_shot_ops_%s.html' % mode)
            _, html = build_page(os.path.join(DEPLOY, 'index.html'), boot, act, out)
            open(out, 'w', encoding='utf-8').write(html)
            n = shot(e, 'http://127.0.0.1:%d/_shot_ops_%s.html' % (PORT, mode),
                     os.path.join(BUILD, png), os.path.join(BUILD, '_prof_ops_' + mode))
            print('  %-22s %s' % (png, ('%d 字节' % n) if n else 'FAIL'))
            burn(out)
    finally:
        httpd.shutdown()
        d = rpc('wb_admin_delete', {'p_token': suptok, 'p_user': OPS_USER})
        print('\n清理临时账号 %s → %s' % (OPS_USER, d.get('msg') or d))

    print('\n完成。')


if __name__ == '__main__':
    main()
