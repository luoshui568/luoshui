# -*- coding: utf-8 -*-
"""真实环境端到端：起本地 http 服务 → headless 浏览器跑完整登录/删除/退出链路

⚠️ **已被取代（2026-09-14 复跑发现失效），保留仅作历史参照。**
   失效点在前半段之后：`App.openAdmCreate()` 现在挂了**写操作门禁**
   （`FORM_GUARD` 名单里有它），调用时先弹密码层、真正的表单还没渲染，
   于是 `document.getElementById('na-user')` 是 null → 探针在 E5 阶段报
   `Cannot set properties of null`。这不是功能坏了，是**旧探针没带哨兵**。
   登录 / 新增任务 / 错误密码被拒 / 正确密码删除这几段仍然有效（本轮已复跑确认）。
   写操作门禁的完整验收请用 `build/probe_gate_e2e.py`（115 项，含「入口层」与「提交层」两层）。
"""
import io, os, json, subprocess, threading, http.server, socketserver, functools, shutil, re, sys

# ── 管理员口令不入库：优先 build/_secret.py（已 gitignore），其次环境变量 WB_PW ──
import os as _os
try:
    from _secret import PW
except Exception:
    PW = _os.environ.get('WB_PW', '')
if not PW:
    raise SystemExit('缺少管理员口令：请创建 build/_secret.py（PW = "…"）或设 WB_PW 环境变量')

BUILD = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.abspath(os.path.join(BUILD, '..', 'deploy'))
INDEX = os.path.join(DEPLOY, 'index.html')
PROBE = os.path.join(DEPLOY, '__tp3.html')
PORT = 8917

s = io.open(INDEX, encoding='utf-8').read()
s = s.replace('<body>',
              '<body>\n<script>window.__E=[];window.onerror=function(m,u,l,c){window.__E.push(String(m)+" @"+l+":"+c);};</script>',
              1)

PROBE_JS = r'''<script>
function __q(){ return document.getElementById('loginGate').className.indexOf('on')>=0; }
var __out = {};
setTimeout(function(){
  try{
    __out.err0 = window.__E.slice();
    __out.gateAtStart = __q();
    __out.authedAtStart = !!Auth.token;
    __out.localBarShown = getComputedStyle(document.getElementById('localBar')).display !== 'none';
    document.getElementById('g-user').value = 'luoshui';
    document.getElementById('g-pass').value = '__PW__';
    App.login();
    setTimeout(__s2, 3500);
  }catch(e){ document.title = 'E1|'+e.message; }
}, 2500);

function __s2(){
  try{
    __out.gateAfterLogin = __q();
    __out.token = (Auth.token||'').slice(0,10);
    __out.user = Auth.user;
    __out.role = Auth.role;
    __out.expire = Auth.expire;
    __out.err1 = window.__E.slice();
    __out.worksBefore = S.works.length;
    var nr = insertRow('works', {horizon:'今天', title:'UI 测试计划（可删）', status:'todo'});
    __out.newId = nr && nr.id;
    __out.newTitle = nr && nr.title;
    setTimeout(__s3, 3000);
  }catch(e){ document.title='E2|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s3(){
  try{
    App.go('work');
    __out.targetTitle = __out.newTitle;
    __out.horizon = '今天';
    App.delWork(__out.newId);
    __out.modalOpen = document.getElementById('mask').className.indexOf('on')>=0;
    document.getElementById('del-pass').value = 'wrong-000';
    App.confirmDelete();
    setTimeout(__s4, 3500);
  }catch(e){ document.title='E3|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s4(){
  try{
    __out.wrongPassModalStillOpen = document.getElementById('mask').className.indexOf('on')>=0;
    __out.worksAfterWrongPass = S.works.length;
    document.getElementById('del-pass').value = '__PW__';
    App.confirmDelete();
    setTimeout(__s5, 3500);
  }catch(e){ document.title='E4|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s5(){
  try{
    __out.worksAfterDelete = S.works.length;
    __out.modalClosed = document.getElementById('mask').className.indexOf('on')<0;
    __out.err2 = window.__E.slice();
    App.openAdmCreate();
    document.getElementById('na-user').value = 'zz_ops_probe';
    document.getElementById('na-name').value = '探针账号';
    document.getElementById('na-pass').value = 'probe-123456';
    App.saveAdmCreate(window.PASS_OK||{});
    setTimeout(__s6, 3000);
  }catch(e){ document.title='E5|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s6(){
  try{
    __out.admRows = document.querySelectorAll('#admList .admRow').length;
    __out.hasProbeAcct = document.getElementById('admList').textContent.indexOf('zz_ops_probe')>=0;
    App.admDelete('zz_ops_probe');
    document.getElementById('del-pass').value = '__PW__';
    App.confirmDelete();
    setTimeout(__s7, 3000);
  }catch(e){ document.title='E6|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s7(){
  try{
    __out.afterClean = document.getElementById('admList').textContent.indexOf('zz_ops_probe')<0;
    __out.err3 = window.__E.slice();
    App.logout();
    setTimeout(__s8, 1500);
  }catch(e){ document.title='E7|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s8(){
  try{
    __out.gateAfterLogout = __q();
    __out.tokenAfterLogout = Auth.token;
    document.title = 'T|' + JSON.stringify(__out);
  }catch(e){ document.title='E8|'+e.message; }
}
</script>'''

io.open(PROBE, 'w', encoding='utf-8').write(s.replace('</body>', PROBE_JS.replace('__PW__', PW) + '\n</body>'))

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DEPLOY)
class Q(socketserver.TCPServer):
    allow_reuse_address = True
httpd = Q(('127.0.0.1', PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('本地服务已启动: http://127.0.0.1:%d/' % PORT)

prof = os.path.join(BUILD, '_prof_auth')
if os.path.isdir(prof):
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox',
       '--user-data-dir=' + prof, '--virtual-time-budget=40000', '--dump-dom',
       'http://127.0.0.1:%d/__tp3.html' % PORT]
try:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=240)
    dom = r.stdout or ''
except subprocess.TimeoutExpired:
    dom = ''
    print('!! Edge 超时')

m = re.search(r'<title>(.*?)</title>', dom, re.S)
t = (m.group(1) if m else 'NO_TITLE').strip()
print('=' * 68)
if t.startswith('T|'):
    print(json.dumps(json.loads(t[2:]), ensure_ascii=False, indent=1))
else:
    print(t)
print('=' * 68)

try:
    os.remove(PROBE)
    print('探针文件已删除')
except Exception:
    pass
try:
    httpd.shutdown()
except Exception:
    pass
