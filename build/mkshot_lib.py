# -*- coding: utf-8 -*-
"""研究报告库 research.html 的目视验收截图（纯只读，不写库）。

产出（build/ 下）：
  shot_lib_top.png      研报库全貌：顶栏 + Hero + 4 格统计 + 搜索/筛选 + 卡片网格
  shot_lib_filter.png   选中「深度研究」类型后的筛选态（能看出 chip 的高亮与卡片收敛）
  shot_lib_pinyin.png   搜索框填 `gyby` 的拼音首字母搜索结果态
  shot_lib_mobile.png   手机宽度（390px）下的单列卡片

不做登录：研报库与研报页一样是**只读开放**的（未登录也能看，只是不能改），
所以不需要建临时账号 —— 直接打开线上同一份 deploy/research.html。

用法：python build/mkshot_lib.py
"""
import http.server
import os
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
DEPLOY = os.path.join(BASE, 'deploy')
PORT = 8977

# 冻住动画：截图要的是稳定的最终态，不是动画中间帧
KILL = """
<style>*{animation:none !important;transition:none !important}
[style*="backdrop-filter"]{backdrop-filter:none !important}</style>
"""

# 等数据渲染完，再按类型筛选一张
ACT_FILTER = r"""
<script>
(function(){
  var T = 0;
  (function wait(){
    T++;
    if(T > 400) return;
    if(typeof window.Lib === 'object' && document.querySelector('#grid a.card') &&
       !(window.L && L.loading)){
      setTimeout(function(){
        var k = (window.L.kinds || []).indexOf('深度研究');
        Lib.setKindIdx(k >= 0 ? k : 0);
      }, 250);
      return;
    }
    setTimeout(wait, 120);
  })();
})();
</script>
"""

# 拼音首字母搜索态：搜索框里填 gyby，应只剩「贵研铂业」一张卡
ACT_PINYIN = r"""
<script>
(function(){
  var T = 0;
  (function wait(){
    T++;
    if(T > 400) return;
    if(typeof window.Lib === 'object' && window.L && L.rows && L.rows.length){
      var el = document.getElementById('q');
      if(el) el.value = 'gyby';        /* 只 setQ 不会把字写进输入框，截图会看着像没搜 */
      Lib.setQ('gyby');
      return;
    }
    setTimeout(wait, 120);
  })();
})();
</script>
"""

# ⚠️ Edge（Windows）**窗口宽度有下限 ≈ 504px**：`--window-size=430` 出来的
#    innerWidth 实测就是 504，再被裁到 430 → 看着像「移动端横向溢出」，其实是截图假象。
#    要真按 390px 排版，就把页面套进一个**宽度写死的 iframe** ——
#    媒体查询是按 iframe 自己的视口算的，这才拿得到真实手机版式。
MOBILE_W = 390
IFRAME_WRAP = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
html,body{margin:0;background:#eef0f4;height:100%%}
body{display:flex;justify-content:center}
iframe{display:block;border:0;width:%dpx;height:%dpx;background:#fff;
  box-shadow:0 0 0 1px rgba(0,0,0,.08),0 8px 30px rgba(0,0,0,.12)}
</style>
</head><body><iframe src="%s"></iframe></body></html>"""

# ⚠️ iframe 是**独立文档**，主框架的 `--virtual-time-budget` 推不动它里面的 CSS 动画
#    （入场动画 `@keyframes up` 从 opacity:0 起，会被拍成半透明糊图）
#    → 内层页面自己也必须注入 KILL 冻帧 CSS。
MOB_INNER = '_shot_lib_in.html'


def edge():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def shot(e, url, png, prof, w, h, budget=45000):
    os.makedirs(prof, exist_ok=True)
    cmd = [e, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=%d,%d' % (w, h), '--user-data-dir=' + prof,
           '--virtual-time-budget=%d' % budget, '--screenshot=' + png, url]
    subprocess.run(cmd, capture_output=True, timeout=900)
    return os.path.getsize(png) if os.path.exists(png) else 0


def main():
    src = open(os.path.join(DEPLOY, 'research.html'), encoding='utf-8').read()
    # 顶部注入冻帧 CSS；</body> 前注入动作脚本
    def variant(act):
        p = src.replace('<body>', '<body>' + KILL, 1)
        i = p.rfind('</body>')
        return p[:i] + act + p[i:]

    tmp = os.path.join(DEPLOY, '_shot_lib.html')
    open(tmp, 'w', encoding='utf-8').write(variant(ACT_FILTER))
    tmp_py = os.path.join(DEPLOY, '_shot_lib_py.html')
    open(tmp_py, 'w', encoding='utf-8').write(variant(ACT_PINYIN))

    # 真手机版式：套 390px 宽的 iframe（见 IFRAME_WRAP 注释）。
    # 内层页面单独写一份冻帧版 —— 别让 iframe 去请求 research.html 本身，
    # 那样入场动画会留着，整张图半透明。
    inner = os.path.join(DEPLOY, MOB_INNER)
    open(inner, 'w', encoding='utf-8').write(src.replace('<body>', '<body>' + KILL, 1))
    mob = os.path.join(DEPLOY, '_shot_lib_mob.html')
    open(mob, 'w', encoding='utf-8').write(
        IFRAME_WRAP % (MOBILE_W, 1520, MOB_INNER))

    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    e = edge()
    print('本地 http 127.0.0.1:%d\n' % PORT)

    try:
        for label, path, w, h, png in [
            ('研报库全貌',   'research.html',      1600, 1420, 'shot_lib_top.png'),
            ('类型筛选态',   '_shot_lib.html',     1600, 1420, 'shot_lib_filter.png'),
            ('拼音搜索 gyby', '_shot_lib_py.html', 1600, 1420, 'shot_lib_pinyin.png'),
            ('手机单列(%dpx)' % MOBILE_W, '_shot_lib_mob.html', 520, 1560, 'shot_lib_mobile.png'),
        ]:
            url = 'http://127.0.0.1:%d/%s' % (PORT, path)
            n = shot(e, url, os.path.join(BUILD, png),
                     os.path.join(BUILD, '_prof_lib_shot_' + png[:14]), w, h)
            print('  %-18s %-22s %s' % (label, png, ('%d 字节' % n) if n else 'FAIL'))
    finally:
        httpd.shutdown()
        for f in (tmp, tmp_py, mob, inner):
            try:
                open(f, 'w', encoding='utf-8').close()    # 就地清空，不删（safe-delete 守卫）
            except OSError:
                pass

    print('\n完成。')


if __name__ == '__main__':
    main()
