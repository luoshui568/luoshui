# -*- coding: utf-8 -*-
"""表格「真实溢出 + 行高 + 竖排」体检（macOS / Edge）。

★ 为什么重写：旧判据 `t.scrollWidth > t.clientWidth` **测不出真溢出** ——
  表格 box 被容器约束到 1058，内容 min-content 1070 时会「内容画到 box 外面」，
  此时 scrollWidth 1070 / clientWidth 1058 恰好能报；但当表格 box 本身就是
  1070（容器 1058）时，scrollWidth == clientWidth == 1070 ⇒ 静默漏报。
  正确判据 = **表右边界 vs 含块内容框右边界**。

用法：
  python3 build/probe_table_fit.py <code> [--win=1100,1600] [--shot=/tmp/x.png] [--all]
  RPT_SRC=/path/to/report.html python3 build/probe_table_fit.py 600456   # 测本地产物
只读，不写任何生产表。
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

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
CODE = (ARGS[0] if ARGS else '600456').strip()


def opt(name, default=None):
    for a in sys.argv[1:]:
        if a.startswith('--' + name + '='):
            return a.split('=', 1)[1]
    return default


WIN = opt('win', os.environ.get('WIN', '1440,1600'))
SHOT = opt('shot') or os.environ.get('SHOT')
SHOW_ALL = '--all' in sys.argv
SRC = os.environ.get('RPT_SRC')
PORT = 8960 + (abs(hash(CODE + WIN)) % 60)

PROBE = r"""
<style>*{animation:none !important;transition:none !important}</style>
<script>
var RPT_OUT = [];
var SHOWALL = __SHOWALL__;
function rp(s){ RPT_OUT.push(s); }
function lh(el){ var v = parseFloat(getComputedStyle(el).lineHeight); return isNaN(v) ? 20 : v; }
function lines(el){ return Math.round(el.getBoundingClientRect().height / lh(el)); }
/* ★ 真实文本行数（Range 逐行框）——单元格 box 高度 = 行高，不能当文本行数用 */
function textLines(el){
  try{
    var r = document.createRange(); r.selectNodeContents(el);
    var rects = r.getClientRects(); var tops = {};
    for(var i = 0; i < rects.length; i++){
      if(rects[i].height < 1 || rects[i].width < 1) continue;
      tops[Math.round(rects[i].top)] = 1;
    }
    var n = Object.keys(tops).length;
    return n || 1;
  }catch(e){ return -1; }
}
function minW(tb){
  /* 表的最小内容宽度：塞进 width:min-content 的绝对定位壳里量 */
  var c = tb.cloneNode(true), d = document.createElement('div');
  d.style.cssText = 'position:absolute;left:-99999px;top:0;width:min-content;visibility:hidden;';
  d.appendChild(c); document.body.appendChild(d);
  var w = c.getBoundingClientRect().width; d.parentNode.removeChild(d);
  return Math.round(w);
}
function ctitle(t){
  var card = t.closest('.card') || t.parentNode;
  var h = card.querySelector('h2,.mt,.card-t,h3');
  return h ? String(h.textContent).trim().slice(0, 18) : '?';
}
setTimeout(function(){
  var mods = document.getElementById('mods');
  if(!mods){ document.title = '###NO_MODS'; return; }

  /* ---------- ① 全部表格：真实溢出 ---------- */
  var tabs = [].slice.call(mods.querySelectorAll('table'));
  var bad = 0, rows = [];
  tabs.forEach(function(t, i){
    var p = t.parentElement, ps = getComputedStyle(p);
    var pr = p.getBoundingClientRect();
    var cL = pr.left + (parseFloat(ps.paddingLeft) || 0);
    var cR = pr.right - (parseFloat(ps.paddingRight) || 0);
    var tr = t.getBoundingClientRect();
    var ofR = Math.round(tr.right - cR), ofL = Math.round(cL - tr.left);
    /* 格内被裁（内容超出格子） */
    var cut = 0, cutMax = 0, cutList = [];
    t.querySelectorAll('th,td').forEach(function(c){
      var d = c.scrollWidth - c.clientWidth;
      if(d > 1){
        cut++; if(d > cutMax) cutMax = d;
        if(cutList.length < 6){
          cutList.push('«' + (c.textContent || '').trim().slice(0, 20) + '»+' + d + 'px');
        }
      }
    });
    var ncol = (t.querySelector('tr') || {children: []}).children.length;
    if(ofR > 1 || ofL > 1 || cut > 0){
      bad++;
      rows.push('#' + i + ' «' + ctitle(t) + '» ' + ncol + '列 表宽' + Math.round(tr.width) +
                ' 容器' + Math.round(cR - cL) + ' 右溢' + ofR + ' 左溢' + ofL +
                ' 格内裁' + cut + (cutMax ? '(max' + cutMax + 'px)' : '') +
                ' min' + minW(t) + ' layout=' + getComputedStyle(t).tableLayout);
      cutList.forEach(function(s){ rows.push('      裁:' + s); });
    }
  });
  rp('T-bad=' + bad + '/' + tabs.length);
  rows.forEach(function(s){
    if(SHOWALL || RPT_OUT.length < 16) rp('  T-' + s);
  });

  /* ---------- ② 竖排检测：短文本占 ≥3 行 ---------- */
  var vs = [], vsn = 0;
  mods.querySelectorAll('td,th').forEach(function(c){
    var txt = (c.textContent || '').trim();
    var han = (txt.match(/[\u4e00-\u9fa5]/g) || []).length;
    var n = textLines(c);
    if(han >= 1 && han <= 9 && txt.length <= 12 && n >= 3){
      vsn++;
      if(vs.length < 10){
        vs.push('«' + txt + '»' + n + '行/宽' + Math.round(c.getBoundingClientRect().width));
      }
    }
  });
  rp('T-vstack=' + vsn + (vs.length ? ' [' + vs.join(' ; ') + ']' : ''));

  /* ---------- ③ 行高 TOP ---------- */
  var hs = [];
  mods.querySelectorAll('tr').forEach(function(r){
    var f = r.querySelector('td,th');
    hs.push([Math.round(r.getBoundingClientRect().height), f ? (f.textContent || '').trim().slice(0, 8) : '']);
  });
  hs.sort(function(a, b){ return b[0] - a[0]; });
  rp('T-rowtop=' + hs.slice(0, 8).map(function(x){ return x[0] + 'px«' + x[1] + '»'; }).join(' '));

  /* ---------- ④ 指定表详情（三大募投详细对照）---------- */
  var target = null;
  mods.querySelectorAll('h3,h2').forEach(function(h){
    if(h.textContent.indexOf('三大募投项目详细对照') >= 0) target = h;
  });
  if(target){
    var tb = target.parentElement.querySelector('table');
    if(tb){
      var ps = getComputedStyle(tb.parentElement);
      var pr = tb.parentElement.getBoundingClientRect();
      var cR = pr.right - (parseFloat(ps.paddingRight) || 0);
      var tr2 = tb.getBoundingClientRect();
      var ths = tb.querySelectorAll('thead th');
      var ws = [].map.call(ths, function(th, i){
        return 'c' + i + '=' + Math.round(th.getBoundingClientRect().width);
      });
      rp('MI-列宽 ' + ws.join(' '));
      rp('MI-表宽=' + Math.round(tr2.width) + ' 容器内容宽=' + Math.round(cR - (pr.left + (parseFloat(ps.paddingLeft) || 0))) +
         ' 右溢=' + Math.round(tr2.right - cR) + ' min内容宽=' + minW(tb) +
         ' layout=' + getComputedStyle(tb).tableLayout);
      var rhs = [], fl = [];
      tb.querySelectorAll('tbody tr').forEach(function(r){
        rhs.push(Math.round(r.getBoundingClientRect().height));
        var c = r.querySelector('td');
        fl.push(c ? textLines(c) : -1);
      });
      rp('MI-行高 ' + rhs.join(',') + '  合计' + rhs.reduce(function(a, b){ return a + b; }, 0) + 'px');
      rp('MI-首列行数 ' + fl.join(','));
      /* 每格行数矩阵（看哪列撑高） */
      var mx = [];
      tb.querySelectorAll('tbody tr').forEach(function(r, ri){
        var a = [];
        r.querySelectorAll('td').forEach(function(c){ a.push(textLines(c)); });
        mx.push('r' + ri + ':' + a.join('/'));
      });
      rp('MI-行内格行数 ' + mx.join(' '));
      /* 每行右溢（哪一格顶出去） */
      var ov = [];
      tb.querySelectorAll('tbody tr').forEach(function(r, ri){
        var o = [];
        r.querySelectorAll('td').forEach(function(c){
          var d = Math.round(c.getBoundingClientRect().right - cR);
          if(d > 1) o.push('r' + ri + '右溢' + d);
        });
        if(o.length) ov.push(o.join(','));
      });
      rp('MI-溢出行 ' + (ov.length ? ov.join(' ; ') : '无'));
    }
  }

  /* ---------- ⑥ 卡片级横向溢出（与 probe_report_mac 的 card-overflow 对齐）---------- */
  var covf = [], co = 0;
  mods.querySelectorAll('.card').forEach(function(c, i){
    if(c.scrollWidth > c.clientWidth + 4){
      co++;
      var ttl = (c.querySelector('h2,.mt,.card-t,h3') || {}).textContent || '';
      /* 找撑破它的后代：右边界超过卡片内容框最多的那个 */
      var cR = c.getBoundingClientRect().right -
               (parseFloat(getComputedStyle(c).paddingRight) || 0);
      var worst = null, wd = 0;
      c.querySelectorAll('*').forEach(function(e){
        var d = e.getBoundingClientRect().right - cR;
        if(d > wd && e.children.length < 40){ wd = d; worst = e; }
      });
      covf.push('card#' + i + ' «' + String(ttl).trim().slice(0, 14) + '» ' +
                c.scrollWidth + '/' + c.clientWidth +
                ' 越界+' + Math.round(wd) +
                ' ov=' + getComputedStyle(c).overflowX +
                (worst ? ' 元凶=' + worst.tagName + '.' + (worst.className || '(无类)') +
                         ' «' + (worst.textContent || '').trim().slice(0, 16) + '»' : ''));
    }
  });
  rp('T-cardoverflow=' + co);
  covf.slice(0, 6).forEach(function(s){ rp('  C-' + s); });

  /* ---------- ⑤ 本页视口信息 ---------- */
  rp('T-viewport=' + window.innerWidth + 'x' + window.innerHeight +
     ' dpr=' + (window.devicePixelRatio || 1) +
     ' body=' + Math.round(document.body.getBoundingClientRect().width));
  var m = mods.getBoundingClientRect(), mp = getComputedStyle(mods);
  rp('T-mods宽=' + Math.round(m.width) + ' padding=' + mp.paddingLeft + '/' + mp.paddingRight);

  function final(){ document.title = '###' + RPT_OUT.join('\n'); }
  final();
}, 4200);
setTimeout(function(){ if(document.title.indexOf('###') !== 0){ document.title = '###' + RPT_OUT.join('\n'); } }, 6000);
</script>
"""

SHOT_JS = r"""
<style>*{animation:none !important;transition:none !important}</style>
<script>
setTimeout(function(){
  /* ★ 截图要点（踩过两个坑）：
     ① 不能 `document.body.innerHTML = 目标` —— 目标会**失去 `.card` 祖先**，
        `.card .mi-card > table` 这类后代选择器不匹配 ⇒ 「修复前/后」两张图一样（假象）。
     ② headless 的 `--screenshot` **不吃 scroll**（滚到目标再截 = 白图 5888B）。
     ⇒ 正确做法：**沿祖先链向上逐层删掉不在链上的兄弟节点**。
        类名层级全保留（CSS 上下文不变），目标自然落到页面顶部，可直接截图。 */
  var want = null;
  document.querySelectorAll('h3,h2').forEach(function(h){
    if(h.textContent.indexOf('__KEY__') >= 0) want = h;
  });
  if(!want){ document.title = '###NOKEY'; return; }
  var host = want.closest('.mi-card') || want.closest('.card') || want;
  var node = host;
  while(node && node.parentElement && node.parentElement !== document.documentElement){
    var p = node.parentElement;
    for(var i = p.children.length - 1; i >= 0; i--){
      var c = p.children[i];
      if(c !== node) p.removeChild(c);
    }
    if(p === document.body) break;
    node = p;
  }
  document.documentElement.style.overflow = 'visible';
  document.body.style.overflow = 'visible';
  document.body.style.margin = '0';
  window.scrollTo(0, 0);
  document.title = '###SHOT h=' + Math.round(host.getBoundingClientRect().height);
}, 3000);
</script>
"""


def inject(raw, js):
    i = raw.rfind('</body>')
    return raw[:i] + js + raw[i:]


def main():
    if SRC:
        raw = open(SRC, encoding='utf-8').read()
        print('[本地字节] %s  %d 字符' % (SRC, len(raw)))
    else:
        raw = urllib.request.urlopen(SITE + '?code=' + CODE, timeout=90).read().decode('utf-8', 'replace')
        print('[线上字节] %s  %d 字符' % (SITE, len(raw)))
    tmp = tempfile.mkdtemp(prefix='tf_')
    key = opt('key', '三大募投项目详细对照')

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

    with open(os.path.join(tmp, 'r.html'), 'w', encoding='utf-8') as f:
        f.write(inject(raw, PROBE.replace('__SHOWALL__', 'true' if SHOW_ALL else 'false')))

    cmd = [EDGE, '--headless=new', '--user-data-dir=' + os.path.join(tmp, 'prof'),
           '--no-sandbox', '--no-proxy-server', '--disable-gpu',
           '--window-size=' + WIN, '--virtual-time-budget=14000',
           '--dump-dom', 'http://127.0.0.1:%d/r.html?code=%s' % (PORT, CODE)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    m = re.search(r'<title>###(.*?)</title>', r.stdout, re.S)
    if m:
        for ln in m.group(1).split('\\n'):
            print(ln)
    else:
        print('!! 没抓到 title')
        ti = r.stdout.find('<title>')
        print(r.stdout[ti:ti + 1200])

    if SHOT:
        with open(os.path.join(tmp, 's.html'), 'w', encoding='utf-8') as f:
            f.write(inject(raw, SHOT_JS.replace('__KEY__', key)))
        if os.path.exists(SHOT):
            os.remove(SHOT)
        subprocess.run([EDGE, '--headless=new', '--user-data-dir=' + os.path.join(tmp, 'prof2'),
                        '--no-sandbox', '--no-proxy-server', '--disable-gpu', '--hide-scrollbars',
                        '--window-size=' + WIN, '--virtual-time-budget=14000',
                        '--screenshot=' + SHOT, 'http://127.0.0.1:%d/s.html?code=%s' % (PORT, CODE)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
        print('[截图] %s %s' % (SHOT, os.path.getsize(SHOT) if os.path.exists(SHOT) else '失败'))

    srv.shutdown()


if __name__ == '__main__':
    main()
