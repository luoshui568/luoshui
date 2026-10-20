# -*- coding: utf-8 -*-
"""第五版目录：多档截图 + 左栏特写（含 hover 模拟，headless 无法真 hover）。"""
import io
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SRC = os.path.join(ROOT, '_work/p5_prev.html')
OUT = os.path.join(ROOT, '_verify')
UD = os.path.join(ROOT, '_work/edge-profile')

os.makedirs(OUT, exist_ok=True)


def shot(src, w, h, png, scale=2):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--no-proxy-server', '--user-data-dir=' + UD,
           '--force-device-scale-factor=%d' % scale,
           '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=6000',
           '--screenshot=' + png, 'file://' + src]
    subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(png):
        print('❌ 截图失败', png)
        return False
    print('   %s  %d KB' % (os.path.basename(png), os.path.getsize(png) // 1024))
    return True


# hover 模拟：把第 3 条按 :hover 的最终值钉死
hsrc = os.path.join(ROOT, '_work/p5_hover.html')
s = io.open(SRC, encoding='utf-8').read()
sim = """<style>
nav.toc a[data-i="3"]{background-size:calc(100% - 24px) 2px,100% 100% !important;color:#14100e !important;
  box-shadow:inset 3px 0 0 -1px rgba(201,162,39,.55),0 3px 12px -6px rgba(20,16,14,.24) !important;}
nav.toc a[data-i="3"]::before{color:#b08a1f !important;transform:translateY(-50%) scale(1.12) !important;}
</style>"""
io.open(hsrc, 'w', encoding='utf-8').write(s.replace('</head>', sim + '</head>'))

print('① 1440 宽')
shot(SRC, 1440, 900, os.path.join(OUT, 'toc5_1440.png'))
print('② 1440 宽 hover 模拟')
shot(hsrc, 1440, 900, os.path.join(OUT, 'toc5_hover.png'))
print('③ 1200 宽（胶囊态）')
shot(SRC, 1200, 900, os.path.join(OUT, 'toc5_1200.png'))
print('④ 390 宽（底部横排）')
shot(SRC, 390, 844, os.path.join(OUT, 'toc5_390.png'))

from PIL import Image  # noqa: E402
for n, box in [('toc5_1440', (20, 240, 420, 1560)),
               ('toc5_hover', (20, 240, 420, 1560)),
               ('toc5_1200', (0, 240, 260, 1400))]:
    Image.open(os.path.join(OUT, n + '.png')).crop(box).save(
        os.path.join(OUT, n + '_close.png'))
print('特写裁切完成')
