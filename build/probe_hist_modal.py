# -*- coding: utf-8 -*-
"""研报页 m2 时间轴「全屏详情弹窗」端到端探针（只读）。

背景：用户截图2 要求「文字很多的年份只显示一部分 → 做一个点击全屏详细显示，样式好看一点」。
      页面侧的实现是 `.h-card` 点击 → `#rptHMask`（`Rpt.hist/histNav/closeHist`），
      但**没有人端到端验过**：弹窗会不会开、正文是不是完整、翻页/键盘能不能用、Esc 关不关得掉。

本探针全程用**真实点击 / 真实键盘事件**（不直接调 Rpt.* 函数），依次断言：
  1. 初始态没有弹窗
  2. 点第 N 张卡 → `.rpt-hmask.on` 出现，`.hd .yr` 年份、`.pg` 页码正确
  3. 弹窗正文 = 该卡 `.h-txt` 的 innerHTML（**一字不差**），且没有被裁
     （scrollHeight ≤ clientHeight + 1）—— 这正是「只显示一部分」的反例
  4. 点「下一条」按钮 → 页码 +1
  5. 按 → 键 → 页码再 +1（键盘导航）
  6. 按 Esc → 弹窗关闭
  7. 弹窗整体不出屏（左右上下都落在视口内）
截图单独跑一次：打开弹窗后**保持不关**，用于目视「样式好不好看」。

用法：
  python3 build/probe_hist_modal.py 603599
  RPT_LIVE=/tmp/live_rep.html python3 build/probe_hist_modal.py 603599     # 验线上字节
  python3 build/probe_hist_modal.py 603599 --noshot --idx=2
"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []
SRC = os.environ.get('RPT_LIVE') or os.environ.get('RPT_SRC') or os.path.join(ROOT, 'deploy', 'report.html')
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  var IDX = __IDX__, HOLD = __HOLD__;
  var out = {steps: []};
  function log(s, extra){ out.steps.push(s); if(extra) out['v_' + s] = extra; }
  function mask(){ return document.getElementById('rptHMask'); }
  function on(){ var m = mask(); return !!m && m.className.indexOf('on') >= 0; }
  function pg(){ var m = mask(); var e = m && m.querySelector('.pg'); return e ? e.textContent.trim() : ''; }
  function yr(){ var m = mask(); var e = m && m.querySelector('.hd .yr'); return e ? e.textContent.trim() : ''; }
  function bd(){ var m = mask(); var e = m && m.querySelector('.bd'); return e ? e : null; }
  function key(k){
    document.dispatchEvent(new KeyboardEvent('keydown',
      {key:k, code:k, bubbles:true, cancelable:true}));
  }
  function go(){
    if(!(window.St && St.rep && St.rep.code)) return setTimeout(go, 250);
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length) return setTimeout(go, 250);
    for(var i=0;i<cards.length;i++){
      if(cards[i].id !== 'm11' && cards[i].id !== 'm2'){ cards[i].style.display = 'none'; }
    }
    var hcs = document.querySelectorAll('#mods .hist .h-card');
    if(!hcs.length){ out.err = '页面里没有时间轴卡片（该研报可能没有 .hist）'; return post(); }
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);
    out.code = St.rep.code; out.name = St.rep.name; out.src = St.src; out.n = hcs.length;

    setTimeout(function(){
      var target = hcs[Math.min(IDX, hcs.length - 1)];
      var wantYr = (function(){ var y = target.querySelector('.h-year'); return y ? y.textContent.trim() : ''; })();
      var wantTxt = (function(){ var t = target.querySelector('.h-txt'); return t ? t.innerHTML : ''; })();
      var hasMore = !!target.querySelector('.h-more');
      var clamped = (function(){
        var t = target.querySelector('.h-txt');
        return t ? (t.scrollHeight - t.clientHeight) > 1 : false;
      })();

      log('初始态无弹窗', !on());
      /* ---- 真实点击卡片 ---- */
      target.click();
      var opened = on();
      log('点击卡片后弹窗打开', opened);
      if(!opened){ out.err = '点击 .h-card 没有弹出 #rptHMask'; return post(); }
      out.clicked = {idx: IDX, year: wantYr, clampedUntilClick: clamped, hasMoreBadge: hasMore};

      var gotYr = yr(), gotPg = pg(), b = bd();
      out.modal = {year: gotYr, page: gotPg};
      log('年份与卡片一致', gotYr === wantYr);
      log('页码正确', gotPg === (Math.min(IDX, hcs.length - 1) + 1) + ' / ' + hcs.length);
      var same = !!b && b.innerHTML.trim() === wantTxt.trim();
      log('正文与卡片一字不差', same);
      if(b){
        var clipped = (b.scrollHeight - b.clientHeight) > 1;
        out.body = {len: b.textContent.trim().length, scrollH: b.scrollHeight,
                    clientH: b.clientHeight, clipped: clipped,
                    overflow: getComputedStyle(b).overflow};
        log('弹窗正文未被裁', !clipped);
      }
      /* ---- 弹窗本体不出屏 ---- */
      var box = mask().querySelector('.rpt-hbox');
      if(box){
        var r = box.getBoundingClientRect();
        out.box = {t:+r.top.toFixed(1), l:+r.left.toFixed(1),
                   w:+r.width.toFixed(1), h:+r.height.toFixed(1),
                   vw: innerWidth, vh: innerHeight};
        log('弹窗整体在视口内', r.top >= -1 && r.left >= -1 &&
                               r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1);
      }
      /* ---- 真实点击「下一条」按钮 ---- */
      var nx = mask().querySelectorAll('.ft .rbtn')[1];
      var pg0 = pg();
      if(nx && !nx.disabled){ nx.click(); log('点「下一条」页码+1', pg() !== pg0); out.afterBtn = pg(); }
      else { log('点「下一条」页码+1', null); out.afterBtn = '(按钮不可用)'; }
      /* ---- 真实键盘 → ---- */
      var pg1 = pg();
      key('ArrowRight');
      log('按 ArrowRight 页码+1', pg() !== pg1);
      out.afterKey = pg();
      /* ---- 真实键盘 Esc ---- */
      if(HOLD){ out.held = true; return post(); }
      key('Escape');
      log('按 Escape 关闭', !on());
      /* ---- 点遮罩空白处也应关闭 ---- */
      target.click(); var reopened = on();
      if(reopened){
        var mk = mask(); mk.dispatchEvent(new MouseEvent('click', {bubbles:true}));
        log('点遮罩关闭', !on());
      } else { log('点遮罩关闭', null); }
      post();
    }, 800);
  }
  function post(){
    try{ fetch('http://127.0.0.1:__PORT__/m', {method:'POST', body: JSON.stringify(out)}); }catch(e){}
  }
  setTimeout(go, 300);
})();
</script>
</body>
"""


def inject(html, js):
    i = html.rfind('</body>')
    assert i > 0, '找不到 </body>'
    return html[:i] + js + '\n' + html[i:]


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        kw['directory'] = kw.pop('directory', '/tmp')
        super().__init__(*a, **kw)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n)
        try:
            GOT.append(json.loads(body.decode('utf-8')))
        except Exception:
            pass
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *a):
        pass


def run(code, idx, hold, win, tmp, port, html, shot):
    js = (INJECT.replace('__PORT__', str(port))
                .replace('__IDX__', str(idx))
                .replace('__HOLD__', '1' if hold else '0'))
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(inject(html, js))
    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)
    GOT.clear()
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                          '--hide-scrollbars', '--window-size=' + win,
                          '--virtual-time-budget=30000', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 90 and not GOT:
        time.sleep(0.2)
    try:
        p.kill()
    except Exception:
        pass
    m = GOT[0] if GOT else None
    if shot:
        if os.path.exists(shot):
            os.remove(shot)
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--hide-scrollbars', '--window-size=' + win,
                        '--virtual-time-budget=20000', '--screenshot=' + shot, url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return m


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    code = args[0] if args else '603599'
    idx, win = 3, '1500,1200'
    for a in sys.argv[1:]:
        if a.startswith('--idx='):
            idx = int(a[6:])
        if a.startswith('--w='):
            win = a[4:]
    noshot = '--noshot' in sys.argv

    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    tmp = tempfile.mkdtemp(prefix='_hmprobe_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print('=' * 104)
    print('m2 时间轴全屏详情弹窗 · 研报 %s · 卡片 #%d · %s · src=%s'
          % (code, idx, win, os.path.basename(SRC)))
    print('=' * 104)

    shot = None if noshot else '/tmp/hm_%s.png' % code
    m = run(code, idx, False, win, tmp, port, html, None)
    if m and not m.get('err'):
        # 截图单独跑：打开弹窗后保持不关
        run(code, idx, True, win, tmp, port, html, shot)
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

    if not m:
        print('✗ 未回传'); return 1
    if m.get('err'):
        print('✗ %s' % m['err']); return 1
    print('取数 src=%s code=%s %s  时间轴卡片 %d 张'
          % (m.get('src'), m.get('code'), m.get('name'), m.get('n') or 0))
    c = m.get('clicked') or {}
    print('目标卡片：年份 %s · 点击前正文被夹断=%s · 有「展开全文」标记=%s'
          % (c.get('year'), c.get('clampedUntilClick'), c.get('hasMoreBadge')))
    print('弹窗：年份 %s · 页码 %s · 点按钮后 %s · 按 → 后 %s'
          % ((m.get('modal') or {}).get('year'), (m.get('modal') or {}).get('page'),
             m.get('afterBtn'), m.get('afterKey')))
    b = m.get('body') or {}
    print('弹窗正文 %s 字 · 内容高 %s / 可视高 %s · overflow=%s'
          % (b.get('len'), b.get('scrollH'), b.get('clientH'), b.get('overflow')))
    print('-' * 104)
    bad = []
    for s in (m.get('steps') or []):
        v = m.get('v_' + s)
        mark = '·' if v is None else ('✓' if v else '✗')
        if v is False:
            bad.append(s)
        print('  %s %s' % (mark, s))
    print('-' * 104)
    if shot:
        print('截图（弹窗打开状态）：%s' % shot)
    if bad:
        print('✗ %d 项未通过：%s' % (len(bad), '；'.join(bad)))
        return 1
    print('✓ 全部断言通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
