# -*- coding: utf-8 -*-
"""生成模块 3 的交付物：整模块预览图 + 股权树特写 + 可离线整页预览 HTML。

用法：
    python make_m3_deliver.py [代码] [公司简称]
    python make_m3_deliver.py 600456 宝钛股份        # 默认值

产出（桌面）：
    <简称>-模块3-股东结构-新版预览-<日期>.png    整模块 1.5x
    <简称>-模块3-股权结构图-<日期>.png           股权树特写 2x（自动定位裁剪）
    <简称>研报-模块3新版-整页预览-<日期>.html    可离线打开的整页（含 31 模块）

前置：先跑 `python shot_mod.py 3`，它会生成 _pv_m3.html 预览页。
"""
import io, os, sys, time, shutil, subprocess
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESK = r'C:/Users/50522/WorkBuddy/2026-09-10-14-50-38/deliver'   # 2026-09-21 起不再落桌面
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

CODE = sys.argv[1] if len(sys.argv) > 1 else '600456'
NAME = sys.argv[2] if len(sys.argv) > 2 else '宝钛股份'
DATE = time.strftime('%Y%m%d')

pv = os.path.join(HERE, '_pv_m3.html')
assert os.path.exists(pv), '先跑 shot_mod.py 3 生成预览页'
url = 'file:///' + pv.replace('\\', '/').replace(' ', '%20') + '?code=' + CODE


def shoot(out, scale, w=1240, h=2450):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--force-device-scale-factor=%s' % scale,
           '--window-size=%d,%d' % (w, h), '--virtual-time-budget=7000',
           '--screenshot=' + out, url]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    print('%-46s rc=%s %s' % (os.path.basename(out), r.returncode,
                              ('%d KB' % (os.path.getsize(out) // 1024)) if os.path.exists(out) else 'MISSING'))
    assert os.path.exists(out), '截图失败：' + out


def crop_tree(png):
    """按红色区块自动定位股权树并裁出特写（不写死坐标）。

    图中红色块自上而下：表格表头 → 省人民政府 → (陕西有色 + 宝钛集团 同排)
    → 父条(宝鸡钛业) → 8 个子盒。取**最后 4 块**即为股权树。
    """
    im = Image.open(png).convert('RGB')
    a = np.asarray(im).astype(np.int16)
    red = (a[:, :, 0] > 150) & (a[:, :, 1] < 70) & (a[:, :, 2] < 90)
    rows = red.sum(axis=1)
    bands, inb = [], False
    for y in range(len(rows)):
        if rows[y] > 300 and not inb:
            inb, y0 = True, y
        elif rows[y] <= 300 and inb:
            inb = False
            if y - y0 > 8:
                bands.append((y0, y))
    assert len(bands) >= 4, '红色区块不足（%d），截图可能未包含股权树' % len(bands)
    tb = bands[-4:]
    bar, kids = tb[-2], tb[-1]
    cols = np.where(red[bar[0]:bar[1]].any(axis=0))[0]
    x0, x1 = int(cols.min()), int(cols.max())
    box = (max(0, x0 - 30), max(0, tb[0][0] - 34),
           min(im.width, x1 + 30), min(im.height, kids[1] + 60))
    out = im.crop(box)
    out.save(png)
    print('  股权树裁剪 %s -> %s  %d KB' % (im.size, out.size, os.path.getsize(png) // 1024))


full = os.path.join(DESK, '%s-模块3-股东结构-新版预览-%s.png' % (NAME, DATE))
tree = os.path.join(DESK, '%s-模块3-股权结构图-%s.png' % (NAME, DATE))
shoot(full, 1.5)
shoot(tree, 2)
crop_tree(tree)

dst = os.path.join(DESK, '%s研报-模块3新版-整页预览-%s.html' % (NAME, DATE))
shutil.copy2(os.path.join(ROOT, 'deploy', 'report.html'), dst)
print('整页预览 ->', dst, os.path.getsize(dst) // 1024, 'KB')
print('DONE')
