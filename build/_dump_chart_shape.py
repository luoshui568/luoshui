# -*- coding: utf-8 -*-
import http.server, os, re, socketserver, subprocess, threading
REPO='/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui'; DEPLOY=os.path.join(REPO,'deploy')
EDGE='/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'; PORT=8997
DUMP = """
setTimeout(function(){
  var out=[];
  try{
    var inst = St.inst['chartRev'];
    var dl = inst.getZr().storage.getDisplayList();
    for(var i=0;i<dl.length;i++){
      var el=dl[i], sh=el.shape;
      if(!sh||sh.width===undefined||sh.height===undefined) continue;
      var eck=null; for(var kk in el){ if(kk.indexOf('__ec_inner')===0){ eck=el[kk]; break; } }
      if(!eck||eck.dataIndex===undefined) continue;
      out.push({type: el.type, di: eck.dataIndex, si: eck.seriesIndex,
                shape: sh, r: sh.r, keys: Object.keys(sh)});
      if(out.length>=6) break;
    }
  }catch(e){ out={err:''+e}; }
  var pre=document.createElement('pre'); pre.id='ZD';
  pre.textContent='ZS'+JSON.stringify(out)+'ZE'; document.body.appendChild(pre);
}, 3600);
"""
SERVE='/tmp/dumpshape'
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**k): super().__init__(*a, directory=SERVE, **k)
    def log_message(self,*a): pass
os.makedirs(SERVE, exist_ok=True)
real=os.environ.get('REPORT_SRC','/tmp/livepatch2/report.html')
html=open(real,encoding='utf-8',errors='replace').read()
i=html.rfind('</body>')
open(os.path.join(SERVE,'report.html'),'w',encoding='utf-8').write(html[:i]+'<script>'+DUMP+'<'+'/script>'+html[i:])
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(('127.0.0.1',PORT),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
r=subprocess.run([EDGE,'--headless=new','--no-sandbox','--disable-gpu','--hide-scrollbars','--no-proxy-server',
   '--user-data-dir=/tmp/edgeprof_ds','--window-size=1400,900','--virtual-time-budget=26000','--dump-dom',
   'http://localhost:%d/report.html?code=002408'%PORT],capture_output=True,timeout=240)
dom=r.stdout.decode('utf-8','replace')
m=re.findall(r'ZS(\{.*?\}|\[.*?\])ZE', dom, re.S)
print('\n'.join(m[-1].split('},{')[:6]).replace('\\"','"') if m else '没拿到')
srv.shutdown()
