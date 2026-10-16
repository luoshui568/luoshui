# -*- coding: utf-8 -*-
"""单份研报（线上真字节）的 headless 体检 —— macOS / Edge。

**为什么不用 `probe_render.py`**：那份硬编码 Windows 的 msedge 路径与 `deploy/report.html`，
本机跑不了。这里改成「抓线上真字节 → 注入探针 → 起 127.0.0.1 → Edge --headless=new」。

踩过的坑（勿简化）：
  * 必须 `--user-data-dir`（否则 profile 锁冲突）、`--no-sandbox`（不加直接崩）、
    `--no-proxy-server`（不加会把 127.0.0.1 当外网）、显式 `--window-size`；
  * 页面走 `http://127.0.0.1:<port>` 而不是 `file://`（`Origin: null` 被网关 403）；
  * 注入位置用 `html.rfind('</body>')`（报告页有 **2 个** `</body>`，第一个在 JS 字符串里）；
  * 注入前先关掉 animation/transition，否则虚拟时钟停在入场帧，`display` 读数不可信；
  * 判 CSS 有没有收掉元素要量 `getComputedStyle(el).display`，**不是** `offsetWidth`。

用法：python3 build/probe_report_mac.py <code> [--shot out.png]
只读，不写任何生产表。
"""
import http.server
import io
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SITE = 'https://liuchaowang.cn/report.html'

CODE = (sys.argv[1] if len(sys.argv) > 1 else '600456').strip()
SHOT = None
if '--shot' in sys.argv:
    SHOT = sys.argv[sys.argv.index('--shot') + 1]
PORT = 8900 + (abs(hash(CODE)) % 90)

PROBE = r"""
<style>*{animation:none !important;transition:none !important}</style>
<script>
setTimeout(function(){
  var out = [];
  function q(sel){ return document.querySelectorAll(sel); }
  var cards = q('#mods .card');
  out.push('title=' + (document.querySelector('#mods h1, .hero .h1, .rpt-title') ?
             document.querySelector('#mods h1, .hero .h1, .rpt-title').textContent.trim().slice(0,60) : '?'));
  out.push('cards=' + cards.length);
  out.push('slots=' + q('#mods [data-chart]').length);
  out.push('canvas=' + q('#mods canvas').length);
  out.push('chartmiss=' + q('#mods .rpt-chartmiss').length);
  out.push('slotgone=' + q('#mods .rpt-slotgone').length);
  /* 模块 3 股东结构（宝钛冻结范例）与模块 22 产业链全景图 */
  out.push('sh3-top=' + q('#mods .sh3-top').length);
  out.push('sh3-donut=' + q('#mods .sh3-donut').length);
  out.push('sh3-tree=' + q('#mods .sh3-tree').length);
  out.push('iflow=' + q('#mods .iflow').length);
  out.push('if-svg=' + q('#mods .iflow svg.if-svg').length);
  out.push('score-hero=' + q('#mods .score-hero').length);
  out.push('sc-line=' + q('#mods .sc-line').length);
  out.push('sc-val-blank=' + (function(){
      var v = q('#mods .sc-val'), n = 0;
      for (var i = 0; i < v.length; i++) if (v[i].textContent.trim() === '—') n++;
      return n; })());
  /* 模块 25 的两张地图：canvas 存在 + tooltip 令牌已下发 */
  out.push('mapcharts=' + q('#mods [data-chart$="WorldMap"], #mods [data-chart$="CNMap"]').length);
  out.push('logic-fold=' + q('#mods .logic').length);
  out.push('logic-open=' + q('#mods .logic.on').length);
  /* 空态与缺字段。
   * ★ 2026-10-15 修正判据：原来量的是 document.body.innerText —— 它把
   *   壳的**静态说明文案**也算进来了：#foot 页脚「标 [MISSING] 的字段为未取到的
   *   一手资料…」+ #printNotes 注解弹窗里的同名说明 + notesModel() 动态生成的
   *   标记图例。这些是「解释 [MISSING] 是什么」的文字，不是数据缺口。
   *   ⇒ 西藏矿业 000762 库里 3 张表已全部 0 处，探针却仍报 MISSING=1，
   *   根因就是这三条静态文案。
   *   正确判据 = 只量**数据模块区**（#mods）里的 [MISSING]。
   *   注：#mods 之外的 .card / .mod 若将来承载真实数据，需同步加入白名单。 */
  out.push('MISSING=' + (function(){
      var root = document.getElementById('mods');
      if (!root) return -1;   // 页面结构变了 ⇒ 显式报错，不要静默返回 0
      var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n = 0;
      while (w.nextNode()) if ((w.currentNode.nodeValue || '').indexOf('[MISSING]') >= 0) n++;
      return n; })());
  /* 壳静态文案里的 [MISSING] 字面数（不是缺口，仅供人工确认判据是否需要更新） */
  out.push('MISSING-shell=' + (function(){
      var n = 0, ids = ['foot', 'printNotes'];
      for (var k = 0; k < ids.length; k++){
        var e = document.getElementById(ids[k]); if (!e) continue;
        var w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
        while (w.nextNode()) if ((w.currentNode.nodeValue || '').indexOf('[MISSING]') >= 0) n++;
      }
      return n; })());
  out.push('MODEL=' + (document.body.innerText.match(/模型输出/g) || []).length);
  /* 溢出：正文是否横向溢出卡片
   * ★ 2026-10-16 增强：原来只给一个计数，定位不到是哪张卡 ⇒ 加 overflow-detail，
   *   输出「卡片序号 : 标题( scrollWidth > clientWidth )」，便于直接改那一张表。 */
  var ovf = 0, ovflist = [];
  for (var i = 0; i < cards.length; i++){
    if (cards[i].scrollWidth > cards[i].clientWidth + 4){
      ovf++;
      var hh = cards[i].querySelector('h2,h3,.mod-no,.no');
      ovflist.push('#' + i + ':' + (hh ? hh.textContent.trim().replace(/\s+/g,' ').slice(0,26) : '?')
                   + '(' + cards[i].scrollWidth + '>' + cards[i].clientWidth + ')');
      /* ★ 再往下一层：列这张卡里「自己就比卡片宽」的后代，直接指出元凶 */
      var wd = [], lim = cards[i].clientWidth + 4;
      var all = cards[i].querySelectorAll('*');
      for (var j = 0; j < all.length && wd.length < 5; j++){
        var e2 = all[j];
        if (!(e2 instanceof HTMLElement)) continue;      // SVG 元素没有 scrollWidth
        if (e2.scrollWidth > lim){
          var cn = (typeof e2.className === 'string') ? e2.className : '';
          wd.push(e2.tagName.toLowerCase() + (cn ? '.' + cn.split(' ')[0] : '')
                  + '[' + e2.scrollWidth + ']');
        }
      }
      if (wd.length) ovflist.push('    └ ' + wd.join(' , '));
    }
  }
  out.push('card-overflow=' + ovf);
  if (ovflist.length) out.push('overflow-detail=' + ovflist.join(' | '));
  var d = document.createElement('div');
  d.id = 'probeout'; d.textContent = out.join('\n');
  document.body.appendChild(d);
  document.title = 'PROBE_DONE';
}, 9000);
</script>
</body>"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


def fetch_live(code):
    # ★ RPT_SRC=<file> 时改测本地字节 —— 默认抓线上，用来量「改前 / 改后」对比。
    #   不加这个开关时，每次量到的都是线上，误以为本地改动没生效（2026-10-15 踩过）。
    src = os.environ.get('RPT_SRC')
    if src:
        with open(src, encoding='utf-8', errors='replace') as f:
            return f.read()
    html = urllib.request.urlopen(SITE + '?code=' + code, timeout=60).read()
    return html.decode('utf-8', 'replace')


def main():
    raw = fetch_live(CODE)
    # 线上页面靠 URL query 取数据；本地起服务后要保留 code 参数
    page = raw.replace('<head>', '<head><base href="https://liuchaowang.cn/">', 1)
    # ⚠️ 不能把 <base> 指到线上，否则 <script src> 相对路径与 fetch 都会被改写；
    # 只补 query：把 code 写进 location.replace 的兜底（页面自身读 location.search）
    inject = PROBE
    k = page.rfind('</body>')
    assert k > 0, '页面里找不到 </body>'
    page = page[:k] + inject + page[k + len('</body>'):]

    tmp = tempfile.mkdtemp(prefix='rptprobe_')
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(page)

    handler = lambda *a, **k: Quiet(*a, directory=tmp, **k)
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), handler)
    httpd.allow_reuse_address = True
    import threading
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    prof = os.path.join(tmp, 'prof')
    cmd = [EDGE, '--headless=new', '--user-data-dir=' + prof, '--no-sandbox',
           '--no-proxy-server', '--disable-gpu', '--window-size=1600,1200',
           '--virtual-time-budget=20000', '--dump-dom',
           'http://127.0.0.1:%d/report.html?code=%s' % (PORT, CODE)]
    p = subprocess.run(cmd, capture_output=True, timeout=180)
    dom = p.stdout.decode('utf-8', 'replace')
    httpd.shutdown()

    m = re.search(r'<div id="probeout">(.*?)</div>', dom, re.S)
    if not m:
        print('✗ 探针没有跑出来（Edge stderr 前 400 字）')
        print(p.stderr.decode('utf-8', 'replace')[:400])
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(2)
    import html as H
    print('=== 线上真字节探针 %s ===' % CODE)
    print(H.unescape(m.group(1)).strip())

    if SHOT:
        cmd2 = [EDGE, '--headless=new', '--user-data-dir=' + prof + '2', '--no-sandbox',
                '--no-proxy-server', '--disable-gpu', '--window-size=1600,4200',
                '--virtual-time-budget=20000', '--screenshot=' + SHOT,
                'http://127.0.0.1:%d/report.html?code=%s' % (PORT, CODE)]
        httpd2 = socketserver.TCPServer(('127.0.0.1', PORT + 1),
                                        lambda *a, **k: Quiet(*a, directory=tmp, **k))
        httpd2.allow_reuse_address = True
        threading.Thread(target=httpd2.serve_forever, daemon=True).start()
        subprocess.run(cmd2, capture_output=True, timeout=180)
        httpd2.shutdown()
        print('截图 → %s（%d 字节）' % (SHOT, os.path.getsize(SHOT)))

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()