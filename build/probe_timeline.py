# -*- coding: utf-8 -*-
"""研报页 m2「公司历史沿革」时间轴 · 溢出/遮挡探针

用法：
  python3 build/probe_timeline.py 603599              # 量 + 截图
  python3 build/probe_timeline.py 603599 --noshot
  python3 build/probe_timeline.py 603599 --w=1080,900
  RPT_SRC=/tmp/live_rep.html python3 build/probe_timeline.py 603599     # 跑线上字节

做什么（只读）：
  1. 复制 deploy/report.html 到临时目录，注入测量脚本
  2. http://127.0.0.1:<port>/report.html?code=xxx 打开（必须 http：要连云数据库取真实研报）
  3. 把 m2 以外的模块全部隐藏，只留时间轴，然后测：
     · .h-nodes 是否真的走了 grid/subgrid（computed grid-template-rows）
     · 每张 .h-card 的四条边是否落在 .hist 的 padding box 内（超出 = 被 overflow:hidden 裁掉）
     · .h-card 顶部是否顶穿 .h-head 底边（= 遮挡标题）
     · .h-txt 的 scrollHeight 是否 > clientHeight（= 正文被截断）
     · 上排卡片之间是否有横向重叠
  4. 截图（裁到时间轴那块）

为什么不用 file://：`Origin: null` 被数据网关 403，会退化成 600456 的内置副本，
量到的不是目标研报。
"""
import io, json, os, shutil, socket, subprocess, sys, tempfile, threading, time
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
  function go(){
    tries++;
    if(!(window.St && St.rep && St.rep.code)){ return setTimeout(go, 250); }
    var target = 'm__NO__';
    /* ⚠️ St.rep 到位 ≠ 模块已渲染：renderMods 排在数据之后。
       不等到 #mods 里真有卡就算，会拿 0 张卡、静默量到空。 */
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length){
      if(tries < 80){ return setTimeout(go, 250); }
      out.err = '模块未渲染（#mods 空）'; post(); return;
    }
    var keep = null;
    for(var i=0;i<cards.length;i++){
      if(cards[i].id === target){ keep = cards[i]; }
      else { cards[i].style.display = 'none'; }
    }
    out.code = St.rep.code; out.name = St.rep.name; out.src = St.src;
    out.mod_cards = cards.length;
    out.found = !!keep;
    if(!keep){
      out.ids = [].slice.call(cards).map(function(e){return e.id;}).slice(0,40);
      post(); return;
    }
    /* 关掉动效：--virtual-time-budget 下 animation 不推进，位置会量偏 */
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);

    setTimeout(function(){
      var hist = keep.querySelector('.hist');
      if(!hist){ out.err='no .hist'; post(); return; }
      var head = hist.querySelector('.h-head');
      var track = hist.querySelector('.h-track');
      var nodes = hist.querySelector('.h-nodes');
      var cards = hist.querySelectorAll('.h-card');
      var hr = hist.getBoundingClientRect();
      var hcs = getComputedStyle(hist), tcs = getComputedStyle(track), ncs = getComputedStyle(nodes);
      var headB = head ? head.getBoundingClientRect().bottom : 0;
      var padT = parseFloat(hcs.paddingTop)||0, padB = parseFloat(hcs.paddingBottom)||0;
      var padL = parseFloat(hcs.paddingLeft)||0, padR = parseFloat(hcs.paddingRight)||0;
      /* 纵向判据用 .h-track（overflow-y:hidden，真正裁卡片的是它）+ .hist 两道取紧的那道 */
      var tk_client = track.clientWidth;
      var tr = track.getBoundingClientRect();
      var boxT = Math.max(hr.top + padT, tr.top), boxB = Math.min(hr.bottom - padB, tr.bottom);
      var boxL = hr.left + padL, boxR = hr.right - padR;
      /* ★ 横向判据必须用「滚动内容宽」而不是 .hist 的可视宽：
         .h-track 现在是个横向滚动容器，卡片排在视口右侧是**正常**的，
         只有超出 .h-nodes 自身内容宽才算真的溢出（放不进去）。 */
      var nr = nodes.getBoundingClientRect();
      var contentLeft = nr.left, contentRight = nr.left + nodes.scrollWidth;

      var list = [], clipTop=0, clipBot=0, clipH=0, trunc=0, overTitle=0;
      var prevRight = -1e9, overlapX = 0;
      var maxCardH = 0;
      var vw = window.innerWidth;
      for(var i=0;i<cards.length;i++){
        var c = cards[i];
        var r = c.getBoundingClientRect();
        var txt = c.querySelector('.h-txt');
        var tr = txt ? txt.getBoundingClientRect() : r;
        var year = c.querySelector('.h-year');
        var yr = year ? year.getBoundingClientRect() : null;
        var oc = r.top < boxT - 0.5;          /* 戳出上边界（含 padding 区）*/
        var ob = r.bottom > boxB + 0.5;       /* 戳出下边界 */
        var ol = r.left < contentLeft - 0.5, orr = r.right > contentRight + 0.5;
        var isTrunc = txt ? (txt.scrollHeight - txt.clientHeight) > 1 : false;
        /* 只有上排（odd）才可能压标题：odd 卡片在 dot 上方 */
        var topSide = r.bottom <= (hr.top + hr.height/2 + 1) || (yr && yr.bottom <= hr.top + hr.height/2);
        var hitsTitle = yr ? (yr.top < headB - 0.5) : false;
        if(oc) clipTop++;
        if(ob) clipBot++;
        if(ol||orr) clipH++;
        if(isTrunc) trunc++;
        if(hitsTitle) overTitle++;
        if(r.right > prevRight + 0.5 && r.left < prevRight - 0.5) overlapX++;
        if(i === 0 || true){} /* 每列独立，不做跨列判断 */
        maxCardH = Math.max(maxCardH, r.height);
        list.push({i:i, year: (year?year.textContent:'').trim(),
                   top:+r.top.toFixed(1), bottom:+r.bottom.toFixed(1),
                   left:+r.left.toFixed(1), right:+r.right.toFixed(1),
                   h:+r.height.toFixed(1), w:+r.width.toFixed(1),
                   txtH: txt?+(txt.scrollHeight).toFixed(1):0, txtVisible: txt?+(txt.clientHeight).toFixed(1):0,
                   truncated: isTrunc, overTitle: hitsTitle, clipTop: oc, clipBot: ob, clipH: (ol||orr)});
      }
      out.vw = vw;
      out.tlw = {trackClientW: tk_client, nodesScrollW: nodes.scrollWidth,
                 cssVar: getComputedStyle(hist).getPropertyValue('--tl-w').trim(),
                 scrolls: hist.className.indexOf('tl-scroll') >= 0};
      out.hist = {top:+hr.top.toFixed(1), bottom:+hr.bottom.toFixed(1),
                  left:+hr.left.toFixed(1), right:+hr.right.toFixed(1),
                  w:+hr.width.toFixed(1), h:+hr.height.toFixed(1),
                  scrollH: hist.scrollHeight, clientH: hist.clientHeight,
                  overflowY: getComputedStyle(hist).overflow};
      out.head = {bottom:+headB.toFixed(1)};
      out.track = {h:+track.getBoundingClientRect().height.toFixed(1),
                   styleH: track.getAttribute('style'),
                   computedH: tcs.height};
      out.nodes = {display: ncs.display, gtr: ncs.gridTemplateRows,
                   gac: ncs.gridAutoColumns, gaf: ncs.gridAutoFlow};
      out.subgridSupported = (window.CSS && CSS.supports && CSS.supports('grid-template-rows','subgrid'));
      out.counts = {n: cards.length, clipTop: clipTop, clipBot: clipBot, clipH: clipH,
                    truncated: trunc, overTitle: overTitle, maxCardH:+maxCardH.toFixed(1),
                    needTrackH: +(hr.height).toFixed(1)};
      out.cards = list;
      out.gapHeadToCards = null;
      post();
    }, 700);
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


def run(code, mod, win, tmp, port, html, shot=None):
    fname = 'report.html'
    io.open(os.path.join(tmp, fname), 'w', encoding='utf-8').write(
        inject(html, INJECT.replace('__PORT__', str(port)).replace('__NO__', mod)))
    url = 'http://127.0.0.1:%d/%s?code=%s' % (port, fname, code)
    GOT.clear()
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                          '--window-size=' + win, '--virtual-time-budget=30000', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 90 and not GOT:
        time.sleep(0.2)
    try:
        p.kill()
    except Exception:
        pass
    m = GOT[0] if GOT else None

    # --- 截图单独跑一次并等它自然退出 ---
    # ⚠️ 不能和测量共用一次进程：测量一收到回传就 kill，Edge 还没落盘 png。
    if shot:
        if os.path.exists(shot):
            os.remove(shot)
        # 高度给足：其他模块已被隐藏，整块时间轴要一屏拍全（宽度才是布局变量，高度不影响测量）
        sw = win.split(',')[0] + ',2600'
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                        '--window-size=' + sw, '--virtual-time-budget=25000',
                        '--screenshot=' + shot, url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return m


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    code = args[0] if args else '603599'
    mod = '2'          # 只给编号：注入处是 'm__NO__'
    win = '1500,1600'
    for a in sys.argv[1:]:
        if a.startswith('--w='):
            win = a[4:]
        if a.startswith('--mod='):
            mod = a[5:]
    noshot = '--noshot' in sys.argv

    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    tmp = tempfile.mkdtemp(prefix='_tlprobe_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print('=' * 104)
    print('研报 %s · 模块 %s 时间轴布局测量   [%s]   src=%s' % (code, mod, win, os.path.basename(SRC)))
    print('=' * 104)

    shot = None if noshot else '/tmp/tl_%s_%s.png' % (code, win.replace(',', 'x'))
    m = run(code, mod, win, tmp, port, html, shot)
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

    if not m:
        print('✗ 未回传'); return 1
    if m.get('err'):
        print('✗', m['err']); return 1
    if not m.get('found'):
        print('✗ 找不到模块卡 %s；页面上的 id 有：%s' % (mod, m.get('ids')))
        print(json.dumps(m, ensure_ascii=False)[:1200])
        return 1
    c = m.get('counts') or {}
    print('取数 src=%s code=%s %s  模块卡 %s 个' % (m.get('src'), m.get('code'), m.get('name'), m.get('mod_cards')))
    print('subgrid 支持 = %s' % m.get('subgridSupported'))
    print('.h-nodes display=%s  grid-template-rows=%s  auto-flow=%s  auto-cols=%s'
          % ((m.get('nodes') or {}).get('display'), (m.get('nodes') or {}).get('gtr'),
             (m.get('nodes') or {}).get('gaf'), (m.get('nodes') or {}).get('gac')))
    print('.h-track  inline=%s  computed=%s  实际=%.1f   可视宽=%s  内容宽=%s  --tl-w=%s  滑动=%s'
          % ((m.get('track') or {}).get('styleH'), (m.get('track') or {}).get('computedH'),
             (m.get('track') or {}).get('h') or 0,
             (m.get('tlw') or {}).get('trackClientW'), (m.get('tlw') or {}).get('nodesScrollW'),
             (m.get('tlw') or {}).get('cssVar'), (m.get('tlw') or {}).get('scrolls')))
    print('.hist  高=%.1f  内容高=%s  可视高=%s  overflow=%s'
          % ((m.get('hist') or {}).get('h') or 0, (m.get('hist') or {}).get('scrollH'),
             (m.get('hist') or {}).get('clientH'), (m.get('hist') or {}).get('overflowY')))
    print('-' * 104)
    print('%3s %-6s %8s %8s %8s %8s %8s %8s  %s'
          % ('#', '年', 'top', 'bottom', 'left', 'right', '高', '文内高/可视', '标记'))
    for r in (m.get('cards') or []):
        flag = []
        if r['clipTop']: flag.append('戳上')
        if r['clipBot']: flag.append('戳下')
        if r['clipH']: flag.append('横向溢出')
        if r['truncated']: flag.append('正文截断')
        if r['overTitle']: flag.append('压标题')
        print('%3d %-6s %8.1f %8.1f %8.1f %8.1f %8.1f %6.1f/%-6.1f  %s'
              % (r['i'], r['year'], r['top'], r['bottom'], r['left'], r['right'],
                 r['h'], r['txtH'], r['txtVisible'], ' '.join(flag) or 'ok'))
    print('-' * 104)
    print('汇总：戳上=%s 戳下=%s 横向溢出=%s 正文截断=%s 压标题=%s  最高卡片=%.1f'
          % (c.get('clipTop'), c.get('clipBot'), c.get('clipH'), c.get('truncated'),
             c.get('overTitle'), c.get('maxCardH') or 0))
    if shot:
        print('截图：%s' % shot)
    return 0


if __name__ == '__main__':
    sys.exit(main())
