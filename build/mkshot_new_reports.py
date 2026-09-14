# -*- coding: utf-8 -*-
"""4 份新研报的目视验收截图（真数据，不打桩网络）。

产出（build/ 下）：
  shot_new_<code>_top.png    顶部：红色 hero + 8 项 KPI + 核心结论
  shot_new_600459_chart.png  贵研铂业 chartRev：验证 idxText 标记真的变成了「-23.4%」文案

要点（踩过的坑，勿简化）：
  * 截图前必须关掉全部 animation/transition，否则 headless 虚拟时钟会把动画截在半透明中间态；
  * `backdrop-filter` 在 headless 下会糊；
  * headless 里 `window.scrollTo` 之后常常拍到空白（合成器没重绘）→ 用「隐藏同门其它节点」
    的办法把目标元素顶到视口里，而不是滚动。
"""
import http.server
import os
import re
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DEPLOY = os.path.join(BASE, 'deploy')
OUTDIR = os.path.join(BASE, 'build')
BUILD = OUTDIR
PORT = 8951
CODES = ['000830', '000731', '002237', '600459']

CSS_KILL = """
<style>
  *{animation:none !important;transition:none !important}
  .page{max-width:1500px !important}
  [style*="backdrop-filter"]{backdrop-filter:none !important}
</style>
"""

TOP_WAIT = CSS_KILL + """
<script>
setTimeout(function(){ document.title = 'SHOT_READY'; }, 2800);
</script>
"""

CHART_ISO = CSS_KILL + """
<script>
(function(){
  var key = '__KEY__';
  setTimeout(function(){
    var el = document.querySelector('[data-chart="' + key + '"]');
    if(el){
      var node = el;
      while(node && node !== document.body){
        var p = node.parentNode;
        if(p){ for(var i = 0; i < p.children.length; i++){
          if(p.children[i] !== node) p.children[i].style.display = 'none'; } }
        node = p;
      }
      var wrap = el.closest ? el.closest('.card') : null;
    }
    document.title = 'SHOT_READY';
  }, 3000);
})();
</script>
"""


def edge():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def inject(src, out, extra):
    s = open(src, encoding='utf-8').read()
    i = s.rfind('</body>')
    open(out, 'w', encoding='utf-8').write(s[:i] + extra + s[i:])


def shot(edge_bin, url, png, prof, w=1680, h=1050):
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    cmd = [edge_bin, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=%d,%d' % (w, h), '--user-data-dir=' + prof,
           '--virtual-time-budget=45000', '--screenshot=' + png, url]
    subprocess.run(cmd, capture_output=True, timeout=900)
    return os.path.exists(png) and os.path.getsize(png)


def main():
    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    e = edge()
    print('本地 http 127.0.0.1:%d · Edge %s\n' % (PORT, e))

    # 顶部图：直接给 report.html 注入「关动画 + 延时改标题」
    top = os.path.join(DEPLOY, '_shot_top.html')
    inject(os.path.join(DEPLOY, 'report.html'), top, TOP_WAIT)

    for c in CODES:
        png = os.path.join(OUTDIR, 'shot_new_%s_top.png' % c)
        n = shot(e, 'http://127.0.0.1:%d/_shot_top.html?code=%s' % (PORT, c),
                 png, os.path.join(BUILD, '_prof_shot_%s' % c))
        print('  %-34s %s' % (os.path.basename(png), ('%d 字节' % n) if n else 'FAIL'))
    os.remove(top)

    # 贵研铂业 chartRev：确认 idxText 还原成 -23.4% 文案
    iso = os.path.join(DEPLOY, '_shot_iso.html')
    inject(os.path.join(DEPLOY, 'report.html'), iso, CHART_ISO.replace('__KEY__', 'chartRev'))
    png = os.path.join(OUTDIR, 'shot_new_600459_chart.png')
    n = shot(e, 'http://127.0.0.1:%d/_shot_iso.html?code=600459' % PORT,
             png, os.path.join(BUILD, '_prof_shot_iso'))
    print('  %-34s %s' % (os.path.basename(png), ('%d 字节' % n) if n else 'FAIL'))
    os.remove(iso)
    httpd.shutdown()
    print('\n完成。')


if __name__ == '__main__':
    main()
