# -*- coding: utf-8 -*-
"""只截「某个模块」的预览图：从已构建的 deploy/report.html 出发，隐藏其余卡片。

用法：
    python build/shot_mod.py 11          # 截模块 11，宽 1240，高 3000
    python build/shot_mod.py 11 1400     # 指定视口宽度
    python build/shot_mod.py 25 1240 4600  # 指定视口高度

⚠️ 必须注入 `animation:none` —— 卡片入场动画从 opacity:0 开始，
   截图恰好落在动画首帧的话会得到一张全白图（踩过）。
⚠️ 高度别省：窗口高度就是截图高度，卡片比它高就**直接截断**（无声无息，
   看起来像「模块只有这么长」）。内容长的模块记得传第三个参数放大高度。
"""
import io, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY = os.path.join(ROOT, 'deploy')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

NO = sys.argv[1] if len(sys.argv) > 1 else '3'
W = sys.argv[2] if len(sys.argv) > 2 else '1240'
H = sys.argv[3] if len(sys.argv) > 3 else '3000'
OUT = os.path.join(HERE, '_shot_m%s.png' % NO)

src = io.open(os.path.join(DEPLOY, 'report.html'), encoding='utf-8').read()
PROBE = """
<style id="probe-one-mod">
  *,*::before,*::after{animation:none!important;transition:none!important;opacity:1!important}
  .wrap > *:not(#mods){display:none!important}
  #mods > *:not(.card){display:none!important}
  #mods .card{display:none;opacity:1!important;transform:none!important}
  #mods .card#m__NO__{display:block;opacity:1!important}
  .rpt-ops{display:none!important}
  .wrap{padding-top:8px}
  body{background:#fafafa}
</style>
</html>"""
i = src.rfind('</html>')
assert i > 0 and 'id="mods"' in src, '页面结构异常'
out = (src[:i] + PROBE).replace('__NO__', NO)
pv = os.path.join(HERE, '_pv_m%s.html' % NO)
io.open(pv, 'w', encoding='utf-8').write(out)
print('预览页 ->', pv)

url = 'file:///' + pv.replace('\\', '/').replace(' ', '%20') + '?code=600456'
cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
       '--force-device-scale-factor=1',
       '--window-size=%s,%s' % (W, H),
       '--virtual-time-budget=9000',
       '--screenshot=' + OUT, url]
r = subprocess.run(cmd, capture_output=True, timeout=300)
print('rc =', r.returncode, 'size =', os.path.getsize(OUT) if os.path.exists(OUT) else 'MISSING')
print((r.stderr or b'').decode('utf-8', 'replace')[-800:])
