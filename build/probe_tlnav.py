# -*- coding: utf-8 -*-
"""研报页 m2 时间轴 · 左右导航箭头 + 滚动条隐藏 探针（2026-10-14 第四轮口径）

用法：
  RPT_SRC=/tmp/out_report.html python3 build/probe_tlnav.py 603599
  RPT_SRC=/tmp/out_report.html python3 build/probe_tlnav.py 603599 --w=800,1600    # 窄屏
  RPT_SRC=/tmp/out_report.html python3 build/probe_tlnav.py 600456                # 不滚的研报

做什么（只读，绝不写库）：
  1. 量箭头本身：数量 / display / opacity / 相对 .hist 的几何 / 是否压在卡片上
  2. 量箭头纵向是否**对准 dot 行**（用户口径：1、2 位置＝轨道两端，高度在圆点那一排）
  3. 量 .h-track 的滚动条**是否已隐藏**：占位 offsetHeight-clientHeight < 1px
     且 computed scrollbar-width = none
     （第三轮曾要求「看得见」，第四轮用户改口「滚动条不要显示」⇒ 判据已反转）
  4. 真点箭头：next → scrollLeft 增大；连点到最右 → next 变 disabled、prev 可用；
     再点 prev → 回退。全程用 element.click()，不直接调函数。
"""
import io, json, os, socket, subprocess, sys, tempfile, threading, time
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, "deploy", "report.html")
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  var out = {};
  var tries = 0;
  function rect(el){ var r = el.getBoundingClientRect();
    return {t:+r.top.toFixed(1), b:+r.bottom.toFixed(1), l:+r.left.toFixed(1), r:+r.right.toFixed(1),
            w:+r.width.toFixed(1), h:+r.height.toFixed(1)}; }
  function go(){
    tries++;
    if(!(window.St && St.rep && St.rep.code)){ return setTimeout(go, 250); }
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length){ if(tries < 80) return setTimeout(go, 250); out.err = '模块未渲染'; post(); return; }
    var keep = null;
    for(var i=0;i<cards.length;i++){
      if(cards[i].id === 'm__NO__'){ keep = cards[i]; } else { cards[i].style.display = 'none'; }
    }
    if(!keep){ out.err = '找不到 m__NO__'; post(); return; }
    setTimeout(function(){ step1(keep); }, 800);
  }
  function step1(keep){
    var hist = keep.querySelector('.hist'), tk = hist.querySelector('.h-track');
    var dot = hist.querySelector('.h-dot'), hr = hist.getBoundingClientRect();
    var navs = hist.querySelectorAll('.tl-nav'), cards = hist.querySelectorAll('.h-card');
    out.code = St.rep.code; out.name = St.rep.name; out.vw = window.innerWidth;
    out.scrolls = hist.className.indexOf('tl-scroll') >= 0;
    out.navCount = navs.length;
    /* 滚动条（2026-10-14 第四轮口径：**必须不显示**）——
       ① taken：经典（非 overlay）滚动条会占掉 offsetHeight - clientHeight 的空间；
       ② cssW：computed scrollbar-width（Chromium 121+ / Firefox 可读，旧内核拿不到就 unknown）。
       两条都为「无」才算隐藏成功。 */
    out.sb = {offsetH: tk.offsetHeight, clientH: tk.clientHeight,
              taken: Math.round((tk.offsetHeight - tk.clientHeight) * 10) / 10,
              cssW: (getComputedStyle(tk).scrollbarWidth || 'unknown')};
    out.trackW = {client: tk.clientWidth, scroll: tk.scrollWidth};
    out.dotMidY = +(dot.getBoundingClientRect().top + dot.getBoundingClientRect().height/2 - hr.top).toFixed(1);
    out.cssMid = (hist.style.getPropertyValue('--tl-mid') || '').trim() || '(未写，CSS 兜底 240px)';
    out.hint = (hist.querySelector('.tl-hint') || {}).textContent || null;
    out.navs = []; out.navHitsCard = [];
    for(var i=0;i<navs.length;i++){
      var n = navs[i], cs = getComputedStyle(n), r = n.getBoundingClientRect();
      var cnt = 0;
      for(var j=0;j<cards.length;j++){
        var cr = cards[j].getBoundingClientRect();
        if(r.left < cr.right - 0.5 && r.right > cr.left + 0.5 &&
           r.top < cr.bottom - 0.5 && r.bottom > cr.top + 0.5) cnt++;
      }
      out.navs.push({cls: n.className, rect: rect(n), opacity: cs.opacity,
                     display: cs.display, disabled: n.disabled, hitCards: cnt});
      out.navHitsCard.push(cnt);
    }
    step2(keep);
  }
  function step2(keep){
    var hist = keep.querySelector('.hist'), tk = hist.querySelector('.h-track');
    out.t0 = {scrollLeft: Math.round(tk.scrollLeft), max: tk.scrollWidth - tk.clientWidth};
    /* 自检两条：① 直接赋 scrollLeft 能不能动（滚动条容器本身可滚）；② API 在不在。
       只有这两条都成立，「点了没动」才真的是箭头的问题。 */
    var bak = tk.scrollLeft;
    tk.scrollLeft = 200;
    out.assignTest = Math.round(tk.scrollLeft);
    tk.scrollLeft = bak;
    out.sbApi = {scrollBy: typeof tk.scrollBy};
    var next = hist.querySelector('.tl-nav.next');
    if(next && !next.disabled) next.click();
    setTimeout(function(){ step3(keep); }, 1200);
  }
  function step3(keep){
    var hist = keep.querySelector('.hist'), tk = hist.querySelector('.h-track');
    var next = hist.querySelector('.tl-nav.next'), prev = hist.querySelector('.tl-nav.prev');
    out.afterNext = {scrollLeft: Math.round(tk.scrollLeft),
                     prevDisabled: prev ? prev.disabled : null, nextDisabled: next ? next.disabled : null};
    for(var i=0;i<8;i++){ if(next && !next.disabled) next.click(); }
    setTimeout(function(){ step4(keep); }, 2400);
  }
  function step4(keep){
    var hist = keep.querySelector('.hist'), tk = hist.querySelector('.h-track');
    var next = hist.querySelector('.tl-nav.next'), prev = hist.querySelector('.tl-nav.prev');
    out.atRight = {scrollLeft: Math.round(tk.scrollLeft), max: tk.scrollWidth - tk.clientWidth,
                   prevDisabled: prev ? prev.disabled : null, nextDisabled: next ? next.disabled : null};
    if(prev) prev.click();
    setTimeout(function(){ step5(keep); }, 1200);
  }
  function step5(keep){
    var hist = keep.querySelector('.hist'), tk = hist.querySelector('.h-track');
    var next = hist.querySelector('.tl-nav.next'), prev = hist.querySelector('.tl-nav.prev');
    out.afterPrev = {scrollLeft: Math.round(tk.scrollLeft),
                     prevDisabled: prev ? prev.disabled : null, nextDisabled: next ? next.disabled : null};
    post();
  }
  function post(){ try{ fetch('http://127.0.0.1:__PORT__/m', {method:'POST', body: JSON.stringify(out)}); }catch(e){} }
  setTimeout(go, 300);
})();
</script>
</body>
"""

SHOT_INJECT = r"""
<script>
(function(){
  var tries = 0;
  function go(){
    tries++;
    if(!(window.St && St.rep && St.rep.code)) return setTimeout(go, 250);
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length){ if(tries < 80) return setTimeout(go, 250); return; }
    for(var i=0;i<cards.length;i++){
      if(cards[i].id !== 'm__NO__') cards[i].style.display = 'none';
    }
    var n = parseInt((location.search.match(/tlclick=(\d+)/) || [0, 0])[1], 10);
    setTimeout(function(){
      var hist = document.querySelector('#mods .hist');
      var tk = hist && hist.querySelector('.h-track');
      var next = hist && hist.querySelector('.tl-nav.next');
      if(tk && n){
        /* 真点：证明按钮不是死的、点击链路成立（disabled 态也随之刷新）。
           ⚠️ 但 --virtual-time-budget 下**带 options 的 scrollBy 一律不推进**
              （连 behavior:'auto' 也一样 —— 它仍走一次 scroll-animation 队列，
              而虚拟时间不驱动该队列；实测点完 scrollLeft 恒为 0）。
              所以画面位移改用与生产代码**同一个算式**直接写 scrollLeft：
              这样截图落在「点完应该看到的位置」。位移链路本身由主探针
              （真实时间 + Popen 轮询）负责验证 —— 两边互补，不是替代。 */
        var w = parseFloat(getComputedStyle(hist).getPropertyValue('--tl-w')) || 152;
        var step = Math.max(180, w * 3);
        for(var k=0;k<n;k++){
          if(next && !next.disabled) next.click();
          tk.scrollLeft += step;
        }
        /* 派真实 scroll 事件让生产代码刷新箭头 disabled（不是直接调它的函数） */
        tk.dispatchEvent(new Event('scroll', {bubbles: true}));
      }
      /* 松开 hover：箭头在鼠标悬停下会变亮，截图要拍「静止态」的淡度 */
      if(document.activeElement && document.activeElement.blur) document.activeElement.blur();
      var mo = new MouseEvent('mousemove', {clientX: 5, clientY: 5, bubbles: true});
      document.dispatchEvent(mo);
    }, 900);
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
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        kw['directory'] = kw.pop('directory', '/tmp')
        super().__init__(*a, **kw)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            GOT.append(json.loads(self.rfile.read(n).decode('utf-8')))
        except Exception:
            pass
        self.send_response(200); self.send_header('Content-Length', '2'); self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *a):
        pass


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    code = args[0] if args else '603599'
    mod, win = '2', '1500,1600'
    for a in sys.argv[1:]:
        if a.startswith('--w='): win = a[4:]
        if a.startswith('--mod='): mod = a[5:]
    noshot = '--noshot' in sys.argv

    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    tmp = tempfile.mkdtemp(prefix='_tlnav_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    meas = os.path.join(tmp, 'report.html')
    io.open(meas, 'w', encoding='utf-8').write(
        inject(html, INJECT.replace('__PORT__', str(port)).replace('__NO__', mod)))
    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)

    print('=' * 100)
    print('研报 %s · m%s 时间轴「左右箭头 + 滚动条」探针   [%s]   src=%s'
          % (code, mod, win, os.path.basename(SRC)))
    print('=' * 100)

    # ★ 测量必须走**真实时间**：--virtual-time-budget 下 smooth scroll 的动画由 compositor
    #   驱动、不随虚拟时间推进（实测点完箭头 scrollLeft 恒为 0，会误判成「点了没反应」）。
    #   所以 Popen 起来 + 轮询回传，收到就 kill（同 probe_timeline.py 的做法）。
    GOT.clear()
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-proxy-server',
                          '--window-size=' + win, url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 180 and not GOT:
        time.sleep(0.3)
    try:
        p.kill()
    except Exception:
        pass
    m = GOT[0] if GOT else None
    if not m:
        print('✗ 未回传'); srv.shutdown(); return 1
    if m.get('err'):
        print('✗', m['err']); srv.shutdown(); return 1

    print('研报 %s %s  视口宽=%s' % (m.get('code'), m.get('name'), m.get('vw')))
    print('滑动模式 .tl-scroll=%s   箭头数=%s   轨道 client=%s / scroll=%s'
          % (m.get('scrolls'), m.get('navCount'), m.get('trackW', {}).get('client'),
             m.get('trackW', {}).get('scroll')))
    sb = m.get('sb') or {}
    _taken = sb.get('taken') or 0
    _cssw = sb.get('cssW')
    _hid = _taken < 1 and _cssw in ('none', 'unknown')
    print('★ 滚动条应「不显示」：占位 = offsetH(%s) - clientH(%s) = %s px（要求 <1）；'
          'computed scrollbar-width=%s   %s'
          % (sb.get('offsetH'), sb.get('clientH'), _taken, _cssw,
             '✅ 已隐藏' if _hid else '❌ 仍然可见'))
    print('★ dot 行中心（相对 .hist）= %s   CSS --tl-mid = %s' % (m.get('dotMidY'), m.get('cssMid')))
    for n in (m.get('navs') or []):
        r = n['rect']
        print('   箭头 %-14s display=%-5s opacity=%-5s disabled=%-5s  %sx%s @(%s,%s)  压到的卡片数=%s'
              % (n['cls'], n['display'], n['opacity'], n['disabled'], r['w'], r['h'], r['l'], r['t'],
                 n['hitCards']))
    for k, lab in (('t0', '初始'), ('afterNext', '点一次 ›'), ('atRight', '连点到最右'),
                   ('afterPrev', '再点一次 ‹')):
        d = m.get(k) or {}
        print('   %-12s scrollLeft=%-7s (max=%s)  prev.disabled=%-5s next.disabled=%-5s'
              % (lab, d.get('scrollLeft'), d.get('max') or (m.get('t0') or {}).get('max'),
                 d.get('prevDisabled'), d.get('nextDisabled')))
    print('   自检：scrollLeft 直接赋值(期望 200) → %s ；scrollBy 类型 = %s'
          % (m.get('assignTest'), (m.get('sbApi') or {}).get('scrollBy')))
    print('   提示文案：%s' % (m.get('hint') or '(无)'))

    if not noshot:
        shotjs = SHOT_INJECT.replace('__NO__', mod)
        for clicks, tag in ((0, 'a_idle'), (1, 'b_clicked')):
            f = os.path.join(tmp, 'shot_%s.html' % tag)
            io.open(f, 'w', encoding='utf-8').write(inject(html, shotjs))
            png = '/tmp/tlnav_%s_%s_%s.png' % (code, win.split(',')[0], tag)
            if os.path.exists(png):
                os.remove(png)
            # 2026-10-14 第四轮起滚动条已隐藏，加不加 --hide-scrollbars 都不影响
            # （留着不加，万一哪天样式回退，截图里能直接看出来）
            subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-proxy-server',
                            '--window-size=%s,2400' % win.split(',')[0], '--virtual-time-budget=30000',
                            '--screenshot=' + png,
                            'http://127.0.0.1:%d/shot_%s.html?code=%s&tlclick=%d' % (port, tag, code, clicks)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            print('截图：%s' % png)
    srv.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
