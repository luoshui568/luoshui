# -*- coding: utf-8 -*-
"""给管理面板拍图：① 模块编辑（可视化正文）② 页眉与结论（核心结论/一句话本质/页脚也是可视化）

用法：python build/_shot_mod.py
"""
import http.server, os, shutil, socketserver, subprocess, threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DEPLOY = os.path.join(BASE, 'deploy')
PORT = 8932
CODE = '600456'

TPL = r'''
<div id="probeOut" style="display:none"></div>
<script>
window.__E = [];
window.onerror = function(m,u,l){ window.__E.push(String(m) + ' @' + l); };
var CSSKILL = document.createElement('style');
CSSKILL.textContent = '*{animation:none !important;transition:none !important}'
  + '.rpt-mask{backdrop-filter:none !important;background:rgba(70,10,20,.55) !important}'
  + '.page{max-width:1500px !important}';
document.head.appendChild(CSSKILL);
function go(){
  try{
    var cd = (window.St && St.code) ? St.code : '600456';
    if(__TAB__ === 'head'){
      Rpt.openDrawer('head', false);
    } else {
      Rpt.openDrawer('mods', false);
      Rpt.openMod(cd + '_m12');
    }
    var b = document.getElementById('rptBody');
    if(b) b.scrollTop = 0;
    document.getElementById('probeOut').textContent = 'INFO:{"ok":1,"tab":"__TAB__"}';
  }catch(e){ document.getElementById('probeOut').textContent = 'INFO:{"err":"' + e.message + '"}'; }
  document.title = 'SHOT_READY';
}
setTimeout(go, 4200);
</script>
'''


def edge():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('no edge')


src = open(os.path.join(DEPLOY, 'report.html'), encoding='utf-8').read()
e = edge()
prof = os.path.join(BASE, 'build', '_prof_shot')
os.chdir(DEPLOY)


class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


httpd = socketserver.TCPServer(('127.0.0.1', PORT), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

for tab, name in [('head', 'v6_head_rte.png'), ('mod', 'v6_mod_rte.png')]:
    out = os.path.join(DEPLOY, '_shot_%s.html' % tab)
    i = src.rfind('</body>')
    # ⚠️ 替代值必须自带引号：占位符出现在 JS 比较式里（if(__TAB__ === 'head')），
    #    只塞裸标识符会变成 `if(head === 'head')` → ReferenceError。
    open(out, 'w', encoding='utf-8').write(
        src[:i] + TPL.replace('__TAB__', '"' + tab + '"') + src[i:])
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    png = os.path.join(BASE, 'build', name)
    cmd = [e, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=1680,1180', '--user-data-dir=' + prof,
           '--virtual-time-budget=26000', '--screenshot=' + png,
           'http://127.0.0.1:%d/_shot_%s.html?code=%s' % (PORT, tab, CODE)]
    r = subprocess.run(cmd, capture_output=True, timeout=420)
    print('%-16s exit=%s  %s 字节' % (name, r.returncode, os.path.getsize(png) if os.path.exists(png) else 'MISSING'))
    cmd2 = [e, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
            '--window-size=1680,1180', '--user-data-dir=' + prof,
            '--virtual-time-budget=26000', '--dump-dom',
            'http://127.0.0.1:%d/_shot_%s.html?code=%s' % (PORT, tab, CODE)]
    r2 = subprocess.run(cmd2, capture_output=True, timeout=420)
    dom = r2.stdout.decode('utf-8', 'ignore')
    k = dom.find('INFO:')
    print('                 INFO =', (dom[k:k + 260].split('</div>')[0] if k >= 0 else '(未取到)'))
    print('                 drawer =', 'rpt-mask on' in dom, '· 有 m-edit =', 'id="m-edit"' in dom,
          '· 有 h-vc =', 'id="h-vc"' in dom)
    os.remove(out)

httpd.shutdown()
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)