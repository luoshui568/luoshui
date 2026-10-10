# -*- coding: utf-8 -*-
"""侧栏目录「有没有被截断 / 有没有压到正文」的**像素+布局双重取证**。

只看截图是不够的：省略号很小，132px 时代就是靠肉眼漏掉的。
所以这里让页面自己量：每个目录项的 scrollWidth 与 clientWidth 一比，
相等 = 文字完整放下；再量目录右边缘与 .wrap 正文左边缘的间隙。

⚠️ 必须从**已构建的** deploy/report.html 出发（改模板不构建 = 白改）。
⚠️ Edge(Win) 窗口宽有钳制，探针宽度别低于 560。
⚠️ 截图前注入 animation:none（卡片入场从透明开始，会截到空白）。

用法： python build/probe_toc.py [viewport宽] [viewport高]
"""
import io
import os
import re
import subprocess
import sys
from html import unescape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY = os.path.join(ROOT, 'deploy')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PYLIB = r'C:\Users\50522\.workbuddy\binaries\python\envs\default\Scripts\python.exe'

W = int(sys.argv[1]) if len(sys.argv) > 1 else 1600
H = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
CODE = '600456'

PROBE = """
<style id="probe-toc-css">
  *{animation:none!important;transition:none!important}
  .reveal{opacity:1!important;transform:none!important}
  #probeout{display:none}
</style>
<script>
/* 让页面自己量：文字是否完整放下（scrollWidth>clientWidth 就是被省略号截了） */
setTimeout(function(){
  var out = [];
  out.push('clientWidth=' + document.documentElement.clientWidth);
  var nav = document.getElementById('toc');
  var as = nav ? nav.querySelectorAll('a') : [];
  var nr = nav ? nav.getBoundingClientRect() : {left:0,right:0,width:0};
  out.push('nav.width=' + Math.round(nr.width));
  for(var i = 0; i < as.length; i++){
    var a = as[i], cs = getComputedStyle(a);
    out.push('IT' + a.getAttribute('data-i') + '[sw=' + a.scrollWidth + ',cw=' + a.clientWidth
             + ',ovf=' + (a.scrollWidth > a.clientWidth + 0.5 ? 'YES' : 'no')
             + ',fs=' + cs.fontSize + ']' + a.textContent);
  }
  var wrap = document.querySelector('.wrap');
  if(wrap){
    var wr = wrap.getBoundingClientRect();
    var pad = parseFloat(getComputedStyle(wrap).paddingLeft) || 0;
    out.push('wrap.left=' + Math.round(wr.left) + ',content.left=' + Math.round(wr.left + pad));
    out.push('gap=' + Math.round(wr.left + pad - nr.right) + 'px');
  }
  var d = document.createElement('div');
  d.id = 'probeout';
  d.textContent = out.join(' || ');
  document.body.appendChild(d);
}, 2500);
</script>
</html>"""


def main():
    src = io.open(os.path.join(DEPLOY, 'report.html'), encoding='utf-8').read()
    i = src.rfind('</html>')
    assert i > 0, '页面结构异常'
    pv = os.path.join(HERE, '_pv_toc.html')
    io.open(pv, 'w', encoding='utf-8').write(src[:i] + PROBE)
    url = 'file:///' + pv.replace('\\', '/') + '?code=' + CODE

    # ① 布局取证（dump-dom）
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--window-size=%d,%d' % (W, H),
           '--virtual-time-budget=9000', '--dump-dom', url]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    dom = (r.stdout or b'').decode('utf-8', 'replace')
    m = re.search(r'<div id="probeout">(.*?)</div>', dom, re.S)
    print('== 布局取证（viewport %dx%d）' % (W, H))
    print(unescape(m.group(1)) if m else '❌ 探针没跑到，DOM 里没有 #probeout')

    # ② 出图（截图 → 裁侧栏 → 2 倍放大便于肉眼看）
    png = os.path.join(ROOT, 'build', '_pv_toc_%d.png' % W)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--window-size=%d,%d' % (W, H),
           '--virtual-time-budget=9000', '--screenshot=' + png, url]
    r2 = subprocess.run(cmd, capture_output=True, timeout=300)
    print('\n== 截图 rc=%s %s' % (r2.returncode, png if os.path.exists(png) else 'MISSING'))
    if os.path.exists(png) and os.path.exists(PYLIB):
        code = (
            "from PIL import Image\n"
            "im = Image.open(r'%s')\n"
            "W,H = im.size\n"
            "w = 200; h = int(H*0.72); y = int(H*0.10)\n"
            "c = im.crop((0, y, min(w, W), min(y+h, H)))\n"
            "c = c.resize((c.width*2, c.height*2), Image.LANCZOS)\n"
            "c.save(r'%s')\n"
            "print('crop ->', r'%s', c.size)\n" % (png, png.replace('.png', '_crop2x.png'),
                                                 png.replace('.png', '_crop2x.png'))
        )
        r3 = subprocess.run([PYLIB, '-c', code], capture_output=True, timeout=120)
        print((r3.stdout or b'').decode('utf-8', 'replace').strip())
        print((r3.stderr or b'').decode('utf-8', 'replace')[-400:] if r3.returncode else '')


if __name__ == '__main__':
    main()
