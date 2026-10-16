# -*- coding: utf-8 -*-
"""近 14 天任务投入图 · 溢出探针

用法： python3 build/probe_bars_overflow.py [宽度列表，逗号分隔，默认 1600,1440,1280,1100,1024,981,900]

做什么：
  1. 把 deploy/index.html 复制到临时目录，注入一段测量脚本（只读，不改仓库文件）
  2. file:// 打开 —— 走「本机离线模式」，用内置种子数据渲染总览页，绕开登录门
  3. Edge 无头渲染，脚本把测量结果 POST 回本地 server，Python 侧阻塞等
  4. 打印每档宽度下 #barsBox 的 clientWidth / scrollWidth、可见列数、溢出量

为什么不用 --dump-dom：index.html 有 2MB，dump 出来还要解析；POST 回传更干净。
为什么必须显式 --window-size：--dump-dom/默认窗口是 800×600，会命中 .g3 单列媒体查询，
测量结果就全错了。
"""
import io, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "deploy", "index.html")
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  function pick(){
    var box = document.getElementById('barsBox');
    if(!box) return null;
    var card = box.closest('.card');
    var grid = card ? card.parentElement : null;
    var bs = [].slice.call(box.querySelectorAll('.b'));
    var cardRect = card.getBoundingClientRect();
    var cs = getComputedStyle(card);
    /* ⚠️ 裁切边界是 .card 的 padding box（overflow:hidden 按 padding box 裁），
       不是 #barsBox —— 卡片有 24px 内边距，标签溢出 barsBox 一点点根本不会被裁。
       所以要拿卡片边框盒内缩 border 宽度去比。 */
    var clipL = cardRect.left + parseFloat(cs.borderLeftWidth || 0);
    var clipR = cardRect.right - parseFloat(cs.borderRightWidth || 0);

    // 只统计「有字」的标签/数值：空 span 的 getBoundingClientRect 宽度≈0，
    // 会污染相邻间距与裁切判定（第一版探针就是这么误报重叠的）。
    function skel(sel){
      var out = [];
      bs.forEach(function(b, i){
        var el = b.querySelector(sel);
        if(!el || !(el.textContent || '').trim()) return;
        var r = el.getBoundingClientRect();
        out.push({i:i, txt:(el.textContent||'').trim(), w:+r.width.toFixed(1),
                  l:+r.left.toFixed(1), r:+r.right.toFixed(1)});
      });
      return out;
    }
    var labs = skel('span'), vals = skel('em');
    function stats(a){
      var beyondR = 0, beyondL = 0, minGap = 1e9;
      a.forEach(function(x, k){
        beyondR = Math.max(beyondR, x.r - clipR);
        beyondL = Math.max(beyondL, clipL - x.l);
        if(k) minGap = Math.min(minGap, x.l - a[k-1].r);
      });
      return {n:a.length, beyondR:+beyondR.toFixed(1), beyondL:+beyondL.toFixed(1),
              minGap:(a.length>1 ? +minGap.toFixed(1) : null)};
    }
    var L = stats(labs), V = stats(vals);

    // 柱子本身是否完整可见
    var barsIn = 0;
    bs.forEach(function(b){
      var r = b.querySelector('i').getBoundingClientRect();
      if(r.right <= clipR + 0.5 && r.left >= clipL - 0.5) barsIn++;
    });
    return {
      vw: window.innerWidth,
      cardW: +cardRect.width.toFixed(1),
      cardPadInner: +(cardRect.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)).toFixed(1),
      cols: bs.length,
      boxClientW: box.clientWidth,
      boxScrollW: box.scrollWidth,
      overflowPx: box.scrollWidth - box.clientWidth,
      barsFullyInside: barsIn,
      labelsShown: L.n, labelBeyondR: L.beyondR, labelBeyondL: L.beyondL, labelMinGap: L.minGap,
      valsShown: V.n, valBeyondR: V.beyondR, valBeyondL: V.beyondL, valMinGap: V.minGap,
      labelW: labs.length ? labs[0].w : 0,
      step: (function(){ var s=box.querySelector('.b span'); return s?1:-1; })(),
      gridCols: grid ? getComputedStyle(grid).gridTemplateColumns : ''
    };
  }
  function go(){
    var m = pick();
    if(!m){ setTimeout(go, 250); return; }
    try{ document.title = 'MEAS ' + JSON.stringify(m); }catch(e){}
    try{ fetch('http://127.0.0.1:__PORT__/m', {method:'POST', body: JSON.stringify(m)}); }catch(e){}
  }
  setTimeout(go, 900);
})();
</script>
</body>
"""


class Sink(BaseHTTPRequestHandler):
    got = []

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n)
        try:
            Sink.got.append(json.loads(body.decode('utf-8')))
        except Exception:
            pass
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *a):
        pass


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run(width, height, port, src=None):
    tmp = tempfile.mkdtemp(prefix='_barsprobe_')
    try:
        html = io.open(src or SRC, encoding='utf-8').read()
        assert '</body>' in html, 'index.html 里没有 </body>'
        io.open(os.path.join(tmp, 'index.html'), 'w', encoding='utf-8').write(
            html.replace('</body>', INJECT.replace('__PORT__', str(port)), 1))
        Sink.got = []
        cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
               '--hide-scrollbars', '--window-size=%d,%d' % (width, height),
               '--virtual-time-budget=12000',
               'file://' + os.path.join(tmp, 'index.html')]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while time.time() - t0 < 45 and not Sink.got:
            time.sleep(0.2)
        try:
            p.kill()
        except Exception:
            pass
        return Sink.got[0] if Sink.got else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    widths = [int(x) for x in (sys.argv[1].split(',') if len(sys.argv) > 1
                               else '1600,1440,1280,1100,1024,981,900'.split(','))]
    src = sys.argv[2] if len(sys.argv) > 2 else None      # 可选：指定要测的 html（做前后对比）
    if src:
        print('源文件：%s' % src)
    port = free_port()
    srv = HTTPServer(('127.0.0.1', port), Sink)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print('=' * 126)
    print('近 14 天任务投入图 · 溢出测量')
    print('  裁切边界 = .card 的 padding box（overflow:hidden 按 padding box 裁，卡片有 24px 内边距）')
    print('  beyondR/beyondL>0 表示标签真的戳出卡片可见区；minGap<0 表示标签互相压字')
    print('=' * 126)
    print('%-7s %-8s %-8s %-6s %-7s %-8s %-6s %-7s %-8s %-7s %-8s %-7s' % (
        '视口', '卡片宽', '内容宽', '柱完整', 'box溢出', '标签数', '超右', '超左', '标签最小间距',
        '数值数', '数值超右', '数值间距'))
    print('-' * 126)
    rows, bad = [], 0
    for w in widths:
        m = run(w, 1400, port, src)
        if not m:
            print('%-7s  ✗ 未回传（渲染超时或脚本未执行）' % w)
            bad += 1
            continue
        rows.append(m)
        warn = (m['labelBeyondR'] > 0.5 or m['labelBeyondL'] > 0.5 or
                m['valBeyondR'] > 0.5 or m['valBeyondL'] > 0.5 or
                (m['labelMinGap'] is not None and m['labelMinGap'] < -0.5) or
                (m['valMinGap'] is not None and m['valMinGap'] < -0.5))
        bad += 1 if warn else 0
        print('%-7d %-8.1f %-8.1f %-6s %-7d %-8d %-6.1f %-7.1f %-8s %-7d %-8.1f %-7s %s' % (
            m['vw'], m['cardW'], m['cardPadInner'], '%d/%d' % (m['barsFullyInside'], m['cols']),
            m['overflowPx'], m['labelsShown'], m['labelBeyondR'], m['labelBeyondL'],
            ('%.1f' % m['labelMinGap']) if m['labelMinGap'] is not None else '-',
            m['valsShown'], m['valBeyondR'],
            ('%.1f' % m['valMinGap']) if m['valMinGap'] is not None else '-',
            ('⚠️' if warn else 'OK')))
    print('-' * 126)
    print('异常档位：%d / %d' % (bad, len(widths)))
    print(json.dumps(rows, ensure_ascii=False, indent=1)[:4000])
    srv.shutdown()


if __name__ == '__main__':
    main()
