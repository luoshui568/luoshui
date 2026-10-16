# -*- coding: utf-8 -*-
"""三个显示问题的定点体检（macOS / Edge，线上真字节）。

用法：python3 build/probe_three.py <code>
只读，不写任何生产表。

⚠️⚠️ 2026-10-15 起：本脚本的 **P1-table-overflow 判据已过时**。
   它用 `t.scrollWidth > t.clientWidth`，**测不出「表格 box 本身超出容器」那种真溢出**
   （box 比容器宽时 scrollWidth == clientWidth，静默报 0，曾据此把真溢出误判成"观感问题"）。
   量表格溢出/行高/竖排请改用 **build/probe_table_fit.py**（表右边界 vs 含块内容框右边界）。
   本脚本其余部分（P2 工具栏、P3 折叠块）仍可用。
"""
import http.server
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SITE = 'https://liuchaowang.cn/report.html'

CODE = (sys.argv[1] if len(sys.argv) > 1 else '600456').strip()
PORT = 8820 + (abs(hash(CODE)) % 60)

PROBE = r"""
<style>*{animation:none !important;transition:none !important}</style>
<script>
var RPT_OUT = [];
function rp(s){ RPT_OUT.push(s); }
setTimeout(function(){
  function q(sel){ return document.querySelectorAll(sel); }

  /* ---------- 问题 2：区间按钮组重复 ---------- */
  var tb = q('#mods .rpt-toolbar');
  rp('P2-toolbar=' + tb.length);
  var n = 0;
  tb.forEach(function(t){
    var p = t.parentNode;
    var same = p.querySelectorAll(':scope > .rpt-toolbar').length;
    if(same > 1){
      n++;
      var card = p.closest('.card');
      var ttl = card ? (card.querySelector('h2,.mt,.card-t') || {}).textContent : '';
      if(n <= 3){
        rp('P2-dup#' + n + ' parent=' + p.className + ' x' + same +
           ' card=«' + String(ttl||'').trim().slice(0,16) + '»' +
           ' cardCanvas=' + (card ? card.querySelectorAll('canvas').length : '?') +
           ' cardSlot=' + (card ? card.querySelectorAll('[data-chart]').length : '?') +
           ' pCanvas=' + p.querySelectorAll('canvas').length +
           ' pChild=' + p.children.length);
        /* 列出同父的兄弟节点类型 */
        var sib = [];
        for(var i=0;i<p.children.length;i++){
          var c = p.children[i];
          sib.push((c.className||c.tagName) + (c.tagName==='CANVAS'?'['+c.width+'x'+c.height+']':'') +
                   (c.getAttribute && c.getAttribute('data-chart') ? '{'+c.getAttribute('data-chart')+'}' : ''));
        }
        rp('P2-dup#' + n + ' siblings=' + sib.join(' | ').slice(0,300));
      }
    }
  });
  rp('P2-dup-total=' + n);

  /* ---------- 问题 3：折叠块 ---------- */
  var lg = q('#mods .logic');
  rp('P3-logic=' + lg.length);
  var s = lg[0], lt = s.querySelector('.lt'), lv = s.querySelector('.lv');
  function snap(tag, el){
    var cs = getComputedStyle(el);
    return tag + ' display=' + cs.display + ' rows=' + cs.gridTemplateRows +
           ' h=' + el.offsetHeight + ' ovf=' + cs.overflow;
  }
  rp(snap('P3-before', lv));
  /* 展开全部，看展开后高度是否为 0 */
  var opened = 0, zeroOpen = 0, openSample = [];
  lg.forEach(function(x, ix){
    var l = x.querySelector('.lv'); if(!l) return;
    var lt2 = x.querySelector('.lt');
    if(lt2) lt2.click();
  });
  setTimeout(function(){
    lg.forEach(function(x, ix){
      var l = x.querySelector('.lv'); if(!l) return;
      var cs = getComputedStyle(l);
      if(cs.display !== 'none'){
        opened++;
        if(l.offsetHeight === 0) zeroOpen++;
        else if(openSample.length < 5)
          openSample.push('#' + ix + '«' + (x.querySelector('.lt')||{textContent:''}).textContent.trim().slice(0,12) +
                          '»h=' + l.offsetHeight + ' rows=' + cs.gridTemplateRows);
      }
    });
    rp('P3-all-clicked open=' + opened + ' zeroHeight=' + zeroOpen);
    if(openSample.length) rp('P3-open-sample=' + openSample.join(' ; '));
    /* 第一个块展开后的子元素位置 */
    if(lv){
      var kids = lv.children, pos = [];
      for(var i=0;i<kids.length && i<4;i++){
        var k = kids[i], kr = k.getBoundingClientRect();
        pos.push(k.tagName + '.' + (k.className||'').slice(0,14) + '@' + Math.round(kr.top) + 'h' + Math.round(kr.height));
      }
      rp('P3-kids=' + pos.join(' ; '));
      rp('P3-lv-h=' + lv.offsetHeight + ' sw=' + lv.scrollWidth + ' cw=' + lv.clientWidth);
    }
    setTimeout(final, 300);
  }, 800);

  /* ---------- 问题 1：表格溢出 + 长文本居中 ---------- */
  var over = 0, overList = [], longCells = 0, longCenter = 0, longSample = [];
  q('#mods table').forEach(function(t, ti){
    if(t.scrollWidth > t.clientWidth + 2){
      over++;
      if(overList.length < 8){
        var card = t.closest('.card');
        var ttl = card ? (card.querySelector('h2,.mt,.card-t') || {}).textContent : '';
        overList.push('#' + ti + '(' + t.scrollWidth + '/' + t.clientWidth + ') ' +
                      String(ttl || '').trim().slice(0,14));
      }
    }
    t.querySelectorAll('td').forEach(function(td){
      var tx = (td.textContent || '').trim();
      if(tx.length > 24 && !/^[\d.,\s%+-]+$/.test(tx)){
        longCells++;
        var al = getComputedStyle(td).textAlign;
        if(al === 'center'){ longCenter++; }
        else if(longSample.length < 5){
          var r = td.getBoundingClientRect(), pr = td.parentNode.getBoundingClientRect();
          longSample.push('«' + tx.slice(0,12) + '»al=' + al + ' lines=' +
            Math.round(r.height / parseFloat(getComputedStyle(td).lineHeight || 20)) +
            ' 右溢出' + Math.round(r.right - pr.right));
        }
      }
    });
  });
  rp('P1-table-overflow=' + over + (overList.length ? ' [' + overList.join(' ; ') + ']' : ''));
  rp('P1-long-cells=' + longCells + ' centered=' + longCenter);
  if(longSample.length) rp('P1-sample=' + longSample.join(' ;; '));

  function final(){ document.title = '###' + RPT_OUT.join('\n'); }
}, 4200);
</script>
"""


def main():
    raw = urllib.request.urlopen(SITE, timeout=60).read().decode('utf-8', 'replace')
    i = raw.rfind('</body>')
    html = raw[:i] + PROBE + raw[i:]
    tmp = tempfile.mkdtemp(prefix='p3_')
    with open(os.path.join(tmp, 'r.html'), 'w', encoding='utf-8') as f:
        f.write(html)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    cmd = [EDGE, '--headless=new', '--user-data-dir=' + os.path.join(tmp, 'prof'),
           '--no-sandbox', '--no-proxy-server', '--disable-gpu',
           '--window-size=1440,1200', '--virtual-time-budget=12000',
           '--dump-dom', 'http://127.0.0.1:%d/r.html' % PORT]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
    m = re.search(r'<title>###(.*?)</title>', r.stdout, re.S)
    if m:
        for ln in m.group(1).split('\\n'):
            print(ln)
    else:
        print('!! 没抓到 title')
        ti = r.stdout.find('<title>')
        print(r.stdout[ti:ti + 1500])
    srv.shutdown()


if __name__ == '__main__':
    main()
