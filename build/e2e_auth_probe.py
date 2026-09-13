# -*- coding: utf-8 -*-
"""真实环境端到端：起本地 http 服务 → headless 浏览器跑完整登录/删除/退出链路"""
import io, os, json, subprocess, threading, http.server, socketserver, functools, shutil, re, sys

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
    document.getElementById('g-pass').value = '981208';
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
    document.getElementById('del-pass').value = '981208';
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
    App.saveAdmCreate();
    setTimeout(__s6, 3000);
  }catch(e){ document.title='E5|'+e.message+'@@'+JSON.stringify(__out); }
}

function __s6(){
  try{
    __out.admRows = document.querySelectorAll('#admList .admRow').length;
    __out.hasProbeAcct = document.getElementById('admList').textContent.indexOf('zz_ops_probe')>=0;
    App.admDelete('zz_ops_probe');
    document.getElementById('del-pass').value = '981208';
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

io.open(PROBE, 'w', encoding='utf-8').write(s.replace('</body>', PROBE_JS + '\n</body>'))

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DEPLOY)
class Q(socketserver.TCPServer):
    allow_reuse_address = True
httpd = Q(('127.0.0.1', PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('本地服务已启动: http://127.0.0.1:%d/' % PORT)

prof = os.path.join(BUILD, '_prof_auth')
if os.path.isdir(prof):
    shutil.rmtree(prof, ignore_errors=True)
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
