# -*- coding: utf-8 -*-
"""m11「同心双环」预览 + 校验探针（只读，绝不写库）。

为什么要有它：
  mkmod11_ring.py 写进库的是**裸 JSON**，页面渲染前还要过两道工厂
  （revive 还原 {{fn:…}} 令牌 → beauty 统一美化）。所以「脚本输出看起来对」
  不等于「页面上画得对」。本探针把待写入的 opt **只在浏览器内存里**替换掉库里的那份，
  用页面自己的 revive/beauty 渲染，从而在不脏库的前提下验证：

    1. 用了真实槽位（`#mods .card#m11 [data-chart=KEY]`）的真实宽高 —— 半径百分比是否放得下
    2. revive 之后 tooltip.formatter 真的是函数（不是空串 —— 那说明 FNS 里没有 ringTip）
    3. 画布墨迹的四条边有没有贴到画布边缘（贴边 = 标签被裁掉）
    4. 同一份 opt 用 SVG 渲染器再画一遍，数 <path> 与 fill="url(#…)"：
       扇区总数应等于内外环项数之和；斜纹格数应等于负值项数（canvas 里数不出 pattern）

用法：
  python3 build/probe_ring_m11.py 600456                 # 预览+校验 600456
  python3 build/probe_ring_m11.py 600456 601958 002408
  python3 build/probe_ring_m11.py --all                  # 全部 8 份
  python3 build/probe_ring_m11.py 600456 --noshot
  载荷来自 mkmod11_ring.py --emit /tmp/ring_payload.json（默认路径就是这个）
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
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, 'deploy', 'report.html')
# 上线验收用：先 curl 一份线上字节到 /tmp/live_rep.html，再用 --live 跑
LIVE_SRC = os.environ.get('RPT_LIVE') or '/tmp/live_rep.html'
PAYLOAD = os.environ.get('RING_PAYLOAD') or '/tmp/ring_payload.json'
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  var KEY = "__KEY__", NEW = __NEW__, EXP_N = __EXPN__, EXP_NEG = __EXPNEG__;
  var LIVE = __LIVE__;      /* LIVE=1：不覆盖，直接量页面从库里读出来渲染的那份（上线后验收用） */
  var out = {key: KEY, expSeries: EXP_N, expNeg: EXP_NEG, live: !!LIVE};
  function go(){
    if(!(window.St && St.rep && St.rep.code)) return setTimeout(go, 250);
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length) return setTimeout(go, 250);
    var keep = null;
    for(var i=0;i<cards.length;i++){
      if(cards[i].id === 'm11'){ keep = cards[i]; } else { cards[i].style.display = 'none'; }
    }
    if(!keep){ out.err = '找不到 m11 模块卡'; return post(); }
    var slot = keep.querySelector('[data-chart="' + KEY + '"]');
    if(!slot){ out.err = '找不到槽位 data-chart=' + KEY; return post(); }
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);
    out.code = St.rep.code; out.name = St.rep.name; out.src = St.src;

    setTimeout(function(){
      try{
        /* ---- 1. 真实槽位 ----
           LIVE：页面自己 renderCharts() 已经把库里的 opt 画上去了，原样取用；
           否则：把库里的 opt 换成本地载荷，用页面自己的 revive+beauty 渲染。 */
        var old = echarts.getInstanceByDom(slot);
        var opt;
        if(LIVE){
          if(!old){ out.err = '槽位没被 renderCharts 渲染（库里可能没这条图表）'; return post(); }
          opt = old.getOption();
          var tt = opt.tooltip;
          if(Array.isArray(tt)) tt = tt[0] || {};
          out.tooltipIsFn = (typeof (tt || {}).formatter === 'function');
        }else{
          /* ★ old 必须先置 null：dispose() 之后实例已销毁，getModel() 返回 null，
             再 `inst = old` 就会炸在 `model.getSeries()` 上（未置 null 的版本必崩）。 */
          if(old){ old.dispose(); old = null; }
          if(St.charts[KEY]) St.charts[KEY].opt = NEW;
          opt = revive(copy(NEW), copy(NEW));
          out.tooltipIsFn = (typeof ((opt.tooltip || {}).formatter) === 'function');
          beauty(opt, KEY);
        }
        var inst = old || echarts.init(slot, THEME);
        if(!LIVE) inst.setOption(opt, true);

        var sr = slot.getBoundingClientRect();
        out.slot = {w:+sr.width.toFixed(1), h:+sr.height.toFixed(1), t:+sr.top.toFixed(1),
                    l:+sr.left.toFixed(1), cls: slot.className,
                    parent: (slot.parentNode.className||'')};
        var cv = slot.querySelector('canvas');
        out.canvas = cv ? cv.width : 0;
        var cvh = cv ? cv.height : 0;

        /* ---- 2. 墨迹包围盒：贴边 = 标签被裁 ---- */
        if(cv){
          var g = cv.getContext('2d');
          var d = g.getImageData(0, 0, cv.width, cvh).data;
          var L = 1e9, R = -1, T = 1e9, B = -1;
          for(var y = 0; y < cvh; y++){
            for(var x = 0; x < cv.width; x++){
              if(d[(y * cv.width + x) * 4 + 3] <= 8) continue;
              if(x < L) L = x; if(x > R) R = x;
              if(y < T) T = y; if(y > B) B = y;
            }
          }
          out.ink = (R < 0) ? null : {L:L, R:R, T:T, B:B,
                                      mL:L, mR:cv.width-1-R, mT:T, mB:cvh-1-B};
        }

        /* ---- 3. 半径实际像素 + 扇区数（从渲染后的模型取） ---- */
        var model = inst.getModel();
        var ms = model.getSeries();
        var R2 = [];
        for(var i2=0;i2<ms.length;i2++){
          var mm = ms[i2];
          var rad = mm.get('radius'), op = mm.option;
          var n = 0;
          try{
            var dat = mm.getData();
            n = dat.count();
          }catch(e){}
          /* 百分比半径 → 像素：ECharts 饼图以 min(w,h)/2 为基准 */
          var minSide = Math.min(cv.width, cvh);
          function toPx(r){
            if(typeof r === 'string' && r.indexOf('%') > 0) return +(parseFloat(r)/100*minSide/2).toFixed(1);
            return r;
          }
          R2.push({name: op.name, type: op.type, radius: rad,
                   radiusPx: [toPx(rad[0]), toPx(rad[1])], n: n,
                   hasFnLabel: (typeof (op.label||{}).formatter === 'function'),
                   labelFormatter: (typeof (op.label||{}).formatter === 'string' ? op.label.formatter : '(fn)'),
                   colors: (op.color || []).length});
        }
        out.series = R2;
        /* 库里的数据项是否带上了自定义字段（tip / decal）—— 渲染后仍应原样保留 */
        out.tips = (opt.series || []).map(function(s){
          return (s.data || []).map(function(d){
            return {n: d.name, v: d.value, tip: (d.tip === undefined ? null : d.tip),
                    decal: !!(d.itemStyle && d.itemStyle.decal)};
          });
        });

        /* ---- 4. 负值斜纹：canvas 里数不出 pattern ⇒ 同尺寸再画一张 SVG ---- */
        var host = document.createElement('div');
        host.style.cssText = 'position:absolute;left:-9999px;top:0;width:' + cv.width +
                             'px;height:' + cvh + 'px;';
        document.body.appendChild(host);
        var si = echarts.init(host, null, {renderer:'svg'});
        si.setOption(opt, true);
        var svg = host.querySelector('svg');
        var paths = svg ? svg.querySelectorAll('path') : [];
        var patterned = 0, colors = {};
        for(var p2=0;p2<paths.length;p2++){
          var f = paths[p2].getAttribute('fill') || '';
          if(f.indexOf('url(') === 0) patterned++;
          colors[f] = (colors[f] || 0) + 1;
        }
        out.svg = {paths: paths.length, patterned: patterned,
                   patterns: svg ? svg.querySelectorAll('pattern').length : 0,
                   fills: colors};
        out.legend = (inst.getOption().legend || []).map(function(l){
          return {bottom: l.bottom, top: l.top, data: (l.data || []).length};
        });
        out.ok = true;
      }catch(e){ out.err = 'ERR ' + (e && e.message || e); }
      post();
    }, 600);
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


def run(code, spec, win, tmp, port, html, shot, live=False):
    js = (INJECT
          .replace('__PORT__', str(port))
          .replace('__KEY__', spec['chart'])
          .replace('__NEW__', json.dumps(spec['opt'], ensure_ascii=False))
          .replace('__EXPN__', str(len(spec['opt']['series'])))
          .replace('__LIVE__', '1' if live else '0')
          .replace('__EXPNEG__', str(sum(1 for s in spec['opt']['series']
                                            for d in s['data'] if 'itemStyle' in d))))
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
        # 高度给足：m11 的图排在很长的表格后面，1500 高根本拍不到（其他模块已隐藏）。
        # 宽度才是布局变量，高度不影响几何测量。
        sw = win.split(',')[0] + ',3400'
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--hide-scrollbars', '--window-size=' + sw,
                        '--virtual-time-budget=25000', '--screenshot=' + shot, url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return m


def report(code, spec, m, shot):
    if not m:
        print('✗ %s 未回传' % code); return 1
    if m.get('err'):
        print('✗ %s %s' % (code, m['err'])); return 1
    print('%-8s %s  槽位 %.0f×%.0f @y=%.0f（class=%s）'
          % (code, m.get('name') or '', (m.get('slot') or {}).get('w') or 0,
             (m.get('slot') or {}).get('h') or 0, (m.get('slot') or {}).get('t') or 0,
             (m.get('slot') or {}).get('cls')))
    bad = []
    if not m.get('tooltipIsFn'):
        bad.append('tooltip.formatter 不是函数（ringTip 未在 FNS 里？）')
    svg = m.get('svg') or {}
    ink = m.get('ink') or {}
    n_tip = n_decal = 0
    for si, arr in enumerate(m.get('tips') or []):
        for d in arr:
            if d.get('tip'):
                n_tip += 1
            if d.get('decal'):
                n_decal += 1
    print('         数据项 %d 个 · 带 tip %d 个 · 带斜纹 %d 个'
          % (sum(len(a) for a in (m.get('tips') or [])), n_tip, n_decal))
    for s in (m.get('series') or []):
        print('         · %-6s radius=%s → %s px   扇区 %d   配色 %d 色'
              % (s['name'], s['radius'], s['radiusPx'], s['n'], s['colors']))
    print('         墨迹 s=%.0f~%.0f  y=%.0f~%.0f   左留白 %s 右留白 %s 上留白 %s 下留白 %s'
          % (ink.get('L') or 0, ink.get('R') or 0, ink.get('T') or 0, ink.get('B') or 0,
             ink.get('mL'), ink.get('mR'), ink.get('mT'), ink.get('mB')))
    print('         SVG：path %d 个 · 斜纹（fill=url(…)) %d 个 · pattern %d 个 · legend %s'
          % (svg.get('paths') or 0, svg.get('patterned') or 0, svg.get('patterns') or 0,
             json.dumps(m.get('legend'), ensure_ascii=False)))
    # ---- 断言 ----
    if n_decal != (m.get('expNeg') or 0):
        bad.append('带斜纹的数据项 %s ≠ 预期负值项数 %s' % (n_decal, m.get('expNeg')))
    if n_tip != sum(len(a) for a in (m.get('tips') or [])):
        bad.append('有数据项没带 tip（tooltip 会退化成默认文案）')
    exp_paths_min = sum(s['n'] for s in (m.get('series') or []))
    if (svg.get('paths') or 0) < exp_paths_min:
        bad.append('SVG 扇区路径 %s < 数据项 %s' % (svg.get('paths'), exp_paths_min))
    for k in ('mL', 'mR', 'mT', 'mB'):
        if ink.get(k) is not None and ink.get(k) <= 1:
            bad.append('墨迹贴到画布%s边（标签可能被裁）' % k[1])
    if (svg.get('patterns') or 0) != (m.get('expNeg') or 0) and not m.get('live'):
        bad.append('SVG 斜纹格数 %s ≠ 预期负值项数 %s' % (svg.get('patterns'), m.get('expNeg')))
    if bad:
        print('         ✗ ' + '；'.join(bad))
        return 1
    print('         ✓ 全部断言通过' + ('   截图：%s' % shot if shot else ''))
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    win = '1500,1600'
    for a in sys.argv[1:]:
        if a.startswith('--w='):
            win = a[4:]
    noshot = '--noshot' in sys.argv
    live = '--live' in sys.argv
    src = LIVE_SRC if live else SRC
    payload = json.load(io.open(PAYLOAD, encoding='utf-8'))
    codes = sorted(payload) if ('--all' in sys.argv or not args) else args
    codes = [c for c in codes if c in payload]
    if not codes:
        print('✗ 载荷里没有这些代码：%s' % args); return 1

    html = io.open(src, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    tmp = tempfile.mkdtemp(prefix='_ringprobe_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print('=' * 104)
    print('m11 %s · %s · 画布 %s · 载荷 %s'
          % ('上线验收（直接量库里读出来的那份）' if live else '同心双环预览',
             os.path.basename(src), win, os.path.basename(PAYLOAD)))
    print('=' * 104)
    rc = 0
    for code in codes:
        shot = None if noshot else '/tmp/ring_%s_%s.png' % (code, win.replace(',', 'x'))
        m = run(code, payload[code], win, tmp, port, html, shot, live)
        rc |= report(code, payload[code], m, shot)
        print('-' * 104)
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
