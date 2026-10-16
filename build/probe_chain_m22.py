# -*- coding: utf-8 -*-
"""研报页 m22「产业链全景图」探针（宝钛 600456 首例）。

用法：
  RPT_SRC=/tmp/livepatch/report.html python3 build/probe_chain_m22.py 600456
  RPT_SRC=/tmp/livepatch/report.html python3 build/probe_chain_m22.py 600456 --w=820
  REPORT_SRC=deploy/report.html python3 build/probe_chain_m22.py 600456 --noshot

★ 为什么要把云配置清空：
  report.html 的模块正文是从**数据库**拉的，seed 只是兜底。要验「我写进 seed 的
  新版模块 22」就必须让它走 seed；更关键的是——探针**绝不许写生产表**，
  清空 envId 后 `REST=''`，页面 `load()` 直接 `useSeed()`，一个请求都不发。
  （注入点必须在 `var CFG = window.RPT_CFG` 前面，RPT_CFG 那行之前。）

量什么（几何求真，不靠肉眼）：
  1. 骨架：.ln 泳道 3 条 / .nd 节点 8 个 / .cp 比例条 8 个 / .if-lg 图例 4 项
  2. 文字溢出：每个 <text> 的 bbox 是否超出它所属节点的 rect（标题/副行都会被逐字量）
  3. 相撞：比例条「名称」与「占比」两个 text 的水平间距；相邻比例条的纵向间隙；
            节点徽章与其标题的相交
  4. 出界：泳道内所有图元的并集 bbox 是否越出 viewBox；节点是否越出自己那条泳道
  5. 分组比例尺：3 组 × 每组每行「条宽 %」与「数值文案」是否自洽；行内文字是否被裁
  6. 显示功能：悬停高亮规则是否真的在样式表里（含 hover 后的态）；
              @media print 是否有还原规则；窄屏是否给出横向滚动
  7. 截图（默认两条宽度）
"""
import io, json, os, re, socket, subprocess, sys, tempfile, threading, time
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, 'deploy', 'report.html')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

KILL_CFG = "<script>window.RPT_CFG={envId:'',key:''};</script>\n"

INJECT = r"""
<script>
(function(){
  var out = {w: window.innerWidth};
  var tries = 0;
  function rc(el){ var r = el.getBoundingClientRect();
    return {t:+r.top.toFixed(1), b:+r.bottom.toFixed(1), l:+r.left.toFixed(1), r:+r.right.toFixed(1),
            w:+r.width.toFixed(1), h:+r.height.toFixed(1)}; }
  function bb(el){ try{ var b = el.getBBox();
    return {x:+b.x.toFixed(2), y:+b.y.toFixed(2), w:+b.width.toFixed(2), h:+b.height.toFixed(2),
            r:+(b.x+b.width).toFixed(2), b2:+(b.y+b.height).toFixed(2)}; }catch(e){ return null; } }
  function inter(a,b){ return !(a.r <= b.x || b.r <= a.x || a.b2 <= b.y || b.b2 <= a.y); }
  function go(){
    tries++;
    if(!(window.St && St.rep && St.rep.code)) return setTimeout(go, 250);
    var keep = null, cards = document.querySelectorAll('#mods > .card');
    for(var i=0;i<cards.length;i++){ if(cards[i].id === 'm__NO__') keep = cards[i]; }
    if(!keep){ if(tries < 60) return setTimeout(go, 250); out.err='找不到 m__NO__（模块数 '+cards.length+'）'; post(); return; }
    out.code = St.rep.code; out.name = St.rep.name; out.src = St.src;
    out.cards = cards.length; out.mods = (St.mods||[]).length;
    setTimeout(function(){ measure(keep); }, 900);
  }
  function measure(keep){
    var ttl = keep.querySelector('.mt,.m-title,.modtitle') || keep;
    out.modTitle = (keep.querySelector('h2,h3') || {}).textContent || '';
    var flow = keep.querySelector('.iflow');
    if(!flow){ out.err = '没找到 .iflow'; post(); return; }

    /* --- 1 骨架 --------------------------------------------------------- */
    out.legend = [];
    var lgs = flow.querySelectorAll('.if-lg');
    for(var i=0;i<lgs.length;i++) out.legend.push({cls: lgs[i].className, txt: lgs[i].textContent.trim()});
    var svg = flow.querySelector('svg.if-svg');
    out.svg = svg ? svg.getAttribute('viewBox') : null;
    out.ln = [], out.nd = [], out.cp = [];
    var nLn = flow.querySelectorAll('.ln'), nNd = flow.querySelectorAll('.nd'), nCp = flow.querySelectorAll('.cp');
    out.nLn = nLn.length; out.nNd = nNd.length; out.nCp = nCp.length;
    var sc = flow.querySelector('.if-scroll');
    out.scroll = sc ? {cw: sc.clientWidth, sw: sc.scrollWidth, over: sc.scrollWidth - sc.clientWidth} : null;
    out.svgBox = svg ? rc(svg) : null;

    /* --- 2/3/4 几何 ------------------------------------------------------ */
    var vb = (out.svg || '').split(/\s+/).map(Number);        /* [0,0,W,H] */
    /* 泳道＝顶部那条带燕尾的横幅，只用来定「横向归属」；节点是挂在横幅下面的，
       所以只能比 x 范围，不能拿横幅的 y 去卡节点。 */
    var laneX = {};
    for(var i=0;i<nLn.length;i++){
      var m = /ln-(\w+)/.exec(nLn[i].getAttribute('class') || '');
      laneX[m ? m[1] : ('k'+i)] = bb(nLn[i]);
      out.ln.push({cls: nLn[i].className, box: bb(nLn[i])});
    }
    var worstNodeOver = 0, worstChipGap = 999, worstChipLab = 999, lo = 1e9, hi = -1e9, top = 1e9, bot = -1e9;
    var acc = [];
    for(var i=0;i<nNd.length;i++){
      var g = nNd[i], rs = g.querySelectorAll('rect'), ts = g.querySelectorAll('text');
      var r0 = rs.length ? bb(rs[0]) : null;
      /* 真·徽章＝挂在节点框**下面**的那个 rect（BADGE_DY>0，是设计如此） */
      var badge = rs.length > 1 ? bb(rs[1]) : null;
      if(badge && r0 && badge.y < r0.b2 - 0.5) badge = null;
      var over = 0, hits = [];
      if(r0){
        for(var j=0;j<ts.length;j++){
          var tb = bb(ts[j]);
          if(!tb) continue;
          if(badge && tb.y >= r0.b2 - 0.5) continue;     /* 徽章文字允许在框外 */
          if(tb.x < r0.x + 1) over = Math.max(over, +(r0.x + 1 - tb.x).toFixed(2));
          if(tb.r > r0.r - 1) over = Math.max(over, +(tb.r - (r0.r - 1)).toFixed(2));
          if(tb.b2 > r0.b2 - 0.5) over = Math.max(over, +(tb.b2 - (r0.b2 - 0.5)).toFixed(2));
          if(tb.y < r0.y + 0.5) over = Math.max(over, +(r0.y + 0.5 - tb.y).toFixed(2));
        }
      }
      /* 徽章必须贴着节点横向居中，且不与别的东西相撞（相撞由跨组检测兜） */
      var badgeOff = 0;
      if(badge && r0) badgeOff = Math.max(0, +(r0.x - 6 - badge.x).toFixed(2), +(badge.r - r0.r - 6).toFixed(2));
      var lane = laneX[(/nd-(\w+)/.exec(g.getAttribute('class')||'') || [])[1]];
      var laneOut = 0;
      if(lane && r0) laneOut = Math.max(0, +(lane.x - 2 - r0.x).toFixed(2), +(r0.r - lane.r - 2).toFixed(2));
      if(r0){ lo = Math.min(lo, r0.x); hi = Math.max(hi, r0.r); top = Math.min(top, r0.y); bot = Math.max(bot, r0.b2); }
      if(badge){ lo = Math.min(lo, badge.x); hi = Math.max(hi, badge.r); bot = Math.max(bot, badge.b2); }
      worstNodeOver = Math.max(worstNodeOver, over);
      out.nd.push({id: g.getAttribute('data-id'), rect: r0, badge: badge, txtOver: +over.toFixed(2),
                   badgeOff: +badgeOff.toFixed(2), laneOut: laneOut,
                   tip: (g.querySelector('title')||{}).textContent ? 1 : 0,
                   inner: [].map.call(ts, function(t){ return t.textContent; })});
      if(r0) acc.push({id: g.getAttribute('data-id'), b: r0});
    }
    var cpList = [];
    for(var i=0;i<nCp.length;i++){
      var g = nCp[i], rs = g.querySelectorAll('rect'), ts = g.querySelectorAll('text');
      var r0 = rs.length ? bb(rs[0]) : null;
      var lab = ts.length ? bb(ts[0]) : null, val = ts.length > 1 ? bb(ts[1]) : null;
      var gap = (lab && val) ? +(val.x - lab.r).toFixed(2) : null;
      if(gap !== null) worstChipLab = Math.min(worstChipLab, gap);
      var over = 0;
      if(r0){ lo = Math.min(lo, r0.x); hi = Math.max(hi, r0.r); top = Math.min(top, r0.y); bot = Math.max(bot, r0.b2); }
      if(r0 && lab && lab.x < r0.x + 1) over = Math.max(over, 1 - (lab.x - r0.x));
      if(r0 && val && val.r > r0.r - 1) over = Math.max(over, val.r - (r0.r - 1));
      cpList.push({id: g.getAttribute('data-id'), y: r0 ? r0.y : null, b: r0, rect: r0,
                   label: ts.length ? ts[0].textContent : '', value: ts.length > 1 ? ts[1].textContent : '',
                   tip: (g.querySelector('title')||{}).textContent ? 1 : 0, gap: gap, over: +over.toFixed(2),
                   cardHit: null});
      if(r0) acc.push({id: 'cp:' + g.getAttribute('data-id'), b: r0});
    }
    cpList.sort(function(a,b){ return a.y - b.y; });
    for(var i=1;i<cpList.length;i++){
      if(cpList[i].rect && cpList[i-1].rect)
        worstChipGap = Math.min(worstChipGap, +(cpList[i].rect.y - cpList[i-1].b.b2).toFixed(2));
    }
    /* 跨组相撞：任意两个「不同 id」的 text 框是否相交 */
    var allT = [], coll = 0;
    var gs = flow.querySelectorAll('.nd,.cp');
    for(var i=0;i<gs.length;i++){
      var ts = gs[i].querySelectorAll('text');
      for(var j=0;j<ts.length;j++){ var b = bb(ts[j]); if(b) allT.push({g: gs[i].getAttribute('data-id'), b: b,
          t: ts[j].textContent.slice(0,14)}); }
    }
    for(var i=0;i<allT.length;i++) for(var j=i+1;j<allT.length;j++)
      if(allT[i].g !== allT[j].g && inter(allT[i].b, allT[j].b))
        { coll++; if(coll <= 6) out.collide = (out.collide||[]).concat([allT[i].id+'|'+allT[i].t+' × '+allT[j].t]); }
    out.nText = allT.length; out.collideN = coll;
    out.chipGap = worstChipGap === 999 ? null : worstChipGap;
    out.chipLabGap = worstChipLab === 999 ? null : worstChipLab;
    out.cp = cpList;
    out.nodeTxtOver = +worstNodeOver.toFixed(2);
    out.badgeOff = +(out.nd.reduce(function(a,n){ return Math.max(a, n.badgeOff||0); }, 0)).toFixed(2);
    out.laneOut = +(out.nd.reduce(function(a,n){ return Math.max(a, n.laneOut||0); }, 0)).toFixed(2);
    out.ink = {l: +lo.toFixed(2), r: +hi.toFixed(2), t: +top.toFixed(2), b: +bot.toFixed(2)};
    out.outOfVB = [ +(0 - lo).toFixed(2), +(hi - vb[2]).toFixed(2),
                    +(0 - top).toFixed(2), +(bot - vb[3]).toFixed(2) ].map(function(v){ return Math.max(0, v); });

    /* --- 5 比例尺 -------------------------------------------------------- */
    out.bars = [];
    var bs = keep.querySelectorAll('.ifb');              /* ★ .ifbars 是 .iflow 的兄弟节点 */
    for(var i=0;i<bs.length;i++){
      var h = bs[i].querySelector('.ifb-h'), rows = bs[i].querySelectorAll('.ifb-r'), rr = [];
      for(var j=0;j<rows.length;j++){
        var l = rows[j].querySelector('.ifb-l'), t = rows[j].querySelector('.ifb-t > i'), v = rows[j].querySelector('.ifb-v');
        rr.push({label: l ? l.textContent : '', pct: t ? t.style.width : '', value: v ? v.textContent : '',
                 labOver: l ? (l.scrollWidth - l.clientWidth) : null,
                 fill: t ? +(t.getBoundingClientRect().width / (t.parentNode.getBoundingClientRect().width || 1) * 100).toFixed(1) : null});
      }
      out.bars.push({cls: bs[i].className, head: h ? h.textContent : '', rows: rr});
    }
    var nEl = keep.querySelector('.if-note');
    out.note = nEl ? nEl.textContent : null;
    out.noteLen = out.note ? out.note.length : 0;

    /* --- 6 显示功能（样式表里求真） -------------------------------------- */
    out.css = {hoverNd: 0, hoverCp: 0, dim: 0, print: [], anim: 0};
    for(var s=0;s<document.styleSheets.length;s++){
      var rules; try{ rules = document.styleSheets[s].cssRules; }catch(e){ continue; }
      if(!rules) continue;
      for(var i=0;i<rules.length;i++){
        var r = rules[i];
        if(r.type === 4 || r.media){       /* @media */
          var mt = (r.conditionText || (r.media && r.media.mediaText) || '');
          if(mt.indexOf('print') >= 0 && r.cssRules)
            for(var k=0;k<r.cssRules.length;k++){
              var sel = r.cssRules[k].selectorText || '';
              if(sel.indexOf('.if') >= 0) out.css.print.push(sel.slice(0, 70) + ' → ' + (r.cssRules[k].style.cssText||'').slice(0,60));
            }
          if(mt.indexOf('860') >= 0 && r.cssRules)
            for(var k=0;k<r.cssRules.length;k++)
              if((r.cssRules[k].selectorText||'').indexOf('.if') >= 0) out.css.anim++;
        }
        var sel = r.selectorText || '';
        if(!sel) continue;
        if(/\.iflow:hover/.test(sel)){
          if(/\.nd/.test(sel)) { out.css.hoverNd++; out.css.hoverNdDecl = r.style.cssText.slice(0, 90); }
          if(/\.cp/.test(sel)) { out.css.hoverCp++; out.css.hoverCpDecl = r.style.cssText.slice(0, 90); }
          if(/opacity/.test(r.style.cssText)) { out.css.dim++; out.css.dimDecl = r.style.cssText.slice(0, 90); }
        }
      }
    }
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
    if(!cards.length){ if(tries < 60) return setTimeout(go, 250); return; }
    for(var i=0;i<cards.length;i++){ if(cards[i].id !== 'm__NO__') cards[i].style.display = 'none'; }
    setTimeout(function(){
      var c = document.getElementById('m22');
      if(c) window.scrollTo(0, Math.max(0, c.getBoundingClientRect().top + window.scrollY - 6));
    }, 700);
  }
  setTimeout(go, 300);
})();
</script>
</body>
"""


def inject_before(html, needle, js):
    i = html.rfind('<script', 0, html.find(needle))
    assert i > 0, '找不到注入点 ' + needle
    return html[:i] + js + html[i:]


def inject_end(html, js):
    i = html.rfind('</body>')
    assert i > 0, '找不到 </body>'
    return html[:i] + js + '\n' + html[i:]


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Handler(SimpleHTTPRequestHandler):
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
    code = args[0] if args else '600456'
    win = '1500,1600'
    for a in sys.argv[1:]:
        if a.startswith('--w='): win = a[4:]
    scale, sh = '1', '1700'
    for a in sys.argv[1:]:
        if a.startswith('--scale='): scale = a[8:]
        if a.startswith('--sh='): sh = a[5:]
    noshot = '--noshot' in sys.argv
    cloud = '--cloud' in sys.argv      # ★ 不清空云配置：让页面真的从线上库拉数据

    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    tmp = tempfile.mkdtemp(prefix='_chain_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    meas = os.path.join(tmp, 'report.html')
    body = inject_end(html, INJECT.replace('__PORT__', str(port)).replace('__NO__', '22'))
    if not cloud:
        body = inject_before(body, 'var CFG   = window.RPT_CFG', KILL_CFG)
    io.open(meas, 'w', encoding='utf-8').write(body)
    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)

    print('=' * 100)
    print('研报 %s · m22 产业链全景图探针  视口=%s  src=%s' % (code, win, os.path.basename(SRC)))
    print('（%s）' % ('★ 云端模式：从线上库拉真实数据（只读）' if cloud
                    else '已清空云配置 ⇒ 走 seed 渲染，全程零请求、不碰生产表'))
    print('=' * 100)

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

    # ★ ok 必须是可变容器：早先用 `global ok` + 局部 `ok` 同名，判定结果永远丢在模块级，
    #    main 里的 ok 恒为 True ⇒「总分」永远是「全绿」，是个静默假绿。
    red = []
    def chk(cond, msg):
        print('   %s %s' % ('✓' if cond else '✗', msg))
        if not cond: red.append(msg)

    # 节点 / 下游条数量不再写死 8：从该篇的规格 JSON 取真值，缺规格才回落到 600456 的骨架值。
    specp = os.path.join(ROOT, 'build', 'seed', 'chainstd', 'chain_%s.json' % code)
    nExpNd, nExpCp = 8, 8
    if os.path.exists(specp):
        _sp = json.load(io.open(specp, encoding='utf-8'))
        nExpNd, nExpCp = len(_sp['nodes']), len(_sp.get('chips', []))

    print('研报 %s %s  src=%s  渲染模块 %s/%s 卡' % (m['code'], m['name'], m['src'], m['mods'], m['cards']))
    print('viewBox = %s   图例 %d 项' % (m['svg'], len(m['legend'])))
    for l in m['legend']:
        print('   图例 %-28s %s' % (l['cls'], l['txt'][:44]))
    print('— 骨架')
    chk(m['nLn'] == 3, '泳道 3 条（实测 %s）' % m['nLn'])
    chk(m['nNd'] == nExpNd, '节点 %d 个（实测 %s）' % (nExpNd, m['nNd']))
    chk(m['nCp'] == nExpCp, '比例条 %d 个（实测 %s）' % (nExpCp, m['nCp']))
    chk(len(m['legend']) == 4, '图例 4 项')
    chk(all(n['tip'] for n in m['nd']), '节点 tooltip 齐全（%d/%d）'
        % (sum(n['tip'] for n in m['nd']), len(m['nd'])))
    chk(all(n['tip'] for n in m['cp']), '比例条 tooltip 齐全（%d/%d）'
        % (sum(n['tip'] for n in m['cp']), len(m['cp'])))
    print('— 布局（阈值 0 = 严）')
    chk(m['nodeTxtOver'] <= 1.0, '节点框内文字溢出最差 %.2f px' % m['nodeTxtOver'])
    chk(m['badgeOff'] <= 6.0, '徽章相对节点横向偏移最差 %.2f px' % m['badgeOff'])
    chk(m['chipLabGap'] is None or m['chipLabGap'] >= 2.0,
        '比例条「名称↔占比」最小水平间距 %s px' % m['chipLabGap'])
    chk(m['chipGap'] is None or m['chipGap'] >= 1.0, '相邻比例条最小纵向间隙 %s px' % m['chipGap'])
    chk(m['collideN'] == 0, '跨节点文字框相撞 %d 处' % m['collideN'])
    if m.get('collide'): print('      ', m['collide'])
    chk(m['laneOut'] <= 0.5, '节点越出泳道 %.2f px' % m['laneOut'])
    chk(max(m['outOfVB']) <= 0.5, '图元越出 viewBox 上/右/下 = %s' % m['outOfVB'])
    print('— 比例尺')
    for b in m['bars']:
        print('   %s  %s' % (b['cls'], b['head']))
        for r in b['rows']:
            print('      %-22s %-8s %-8s  行内被裁=%s' % (r['label'], r['pct'], r['value'], r['labOver']))
    chk(len(m['bars']) == 3, '分组 3 组（实测 %s）' % len(m['bars']))
    bad = [(b['head'], r['label']) for b in m['bars'] for r in b['rows'] if (r['labOver'] or 0) > 1]
    chk(not bad, '比例尺行内文字无裁切%s' % ('（%s）' % bad if bad else ''))
    print('— 读图说明 %d 字' % m['noteLen'])
    chk(m['noteLen'] > 150, '口径/来源说明在位')
    print('— 显示功能')
    print('   .if-scroll  可视 %s / 内容 %s （窄屏可横滑：溢出 %s px）'
          % (m['scroll']['cw'], m['scroll']['sw'], m['scroll']['over']))
    print('   条内填充实测 %s' % [(r['pct'], r['fill']) for b in m['bars'] for r in b['rows']][:5])
    print('   悬停规则：.iflow:hover .nd ×%s ｜ .iflow:hover .cp ×%s ｜ 含 opacity ×%s'
          % (m['css']['hoverNd'], m['css']['hoverCp'], m['css']['dim']))
    if m['css'].get('dimDecl'): print('      变暗：%s' % m['css']['dimDecl'])
    if m['css'].get('hoverCpDecl'): print('      比例条：%s' % m['css']['hoverCpDecl'])
    chk(m['css']['hoverNd'] >= 1, '悬停高亮规则在样式表里')
    chk(m['css']['hoverCp'] >= 1, '比例条悬停规则在样式表里')
    chk(len(m['css']['print']) >= 1, '@media print 有还原规则（%d 条）' % len(m['css']['print']))
    for s in m['css']['print'][:4]: print('      print: %s' % s)
    chk(m['css']['anim'] >= 1, '窄屏 @media(≤860) 有适配规则（%d 条）' % m['css']['anim'])
    if m['w'] <= 900:
        chk(m['scroll']['over'] > 0, '窄屏确实可横滑（溢出 %s px）' % m['scroll']['over'])
        chk(m['svgBox']['w'] >= 740, '窄屏 svg 保持最小宽 740+（实测 %s）' % m['svgBox']['w'])
    else:
        chk(m['svgBox']['w'] > 900, '宽屏 svg 铺满容器（实测 %s）' % m['svgBox']['w'])

    print('— 节点清单')
    for n in m['nd']:
        print('   %-9s %s  徽章=%s  框内溢出=%.2f  徽章偏心=%.2f  越段=%.2f' %
              (n['id'], n['rect'], '有' if n['badge'] else '无', n['txtOver'], n['badgeOff'], n['laneOut']))
    print()
    print('总分：%s' % ('全绿' if not red else '有 %d 项红 —— 先别上线' % len(red)))
    for r in red:
        print('   ✗ %s' % r)

    if not noshot:
        for w in (win.split(',')[0], '820'):
            f = os.path.join(tmp, 'shot_%s.html' % w)
            body2 = inject_end(html, SHOT_INJECT.replace('__NO__', '22'))
            if not cloud:
                body2 = inject_before(body2, 'var CFG   = window.RPT_CFG', KILL_CFG)
            io.open(f, 'w', encoding='utf-8').write(body2)
            png = '/tmp/chain_%s_w%s.png' % (code, w)
            if os.path.exists(png): os.remove(png)
            subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-proxy-server',
                            '--force-device-scale-factor=' + scale,
                            '--window-size=%s,%s' % (w, sh), '--virtual-time-budget=30000',
                            '--screenshot=' + png,
                            'http://127.0.0.1:%d/shot_%s.html?code=%s' % (port, w, code)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            print('截图：%s' % png)
    srv.shutdown()
    return 0 if not red else 2


if __name__ == '__main__':
    sys.exit(main())
