# -*- coding: utf-8 -*-
"""端到端：真实点一次研报库页脚的「友情链接」，看是否落到牛熊全史页。

为什么走本地：
  线上默认测试域名在 headless 里会被腾讯云拦成「页面访问提示」页（已截图确认），
  自定义域名同理。而 deliver/ 里的两个文件与线上**逐字节一致**（md5 已核），
  且同目录相对路径互跳 —— 本地能跳通 ⇒ 线上就能跳通。

做法：造临时副本（不动交付文件），注入脚本把 target 去掉再 .click()，
      让导航发生在同一文档里，这样 --dump-dom 抓得到落地页。

用法：python build/_e2e_jump.py
"""
import hashlib
import io
import os
import subprocess
import sys

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
SRC = os.path.join(ROOT, 'deliver', 'research.html')
TGT = os.path.join(ROOT, 'deliver', 'market-history.html')
TMP = os.path.join(ROOT, 'deliver', '_e2e_jump.html')

print('=== 前置 ===')
print('  源页存在 :', os.path.exists(SRC))
print('  目标页存在:', os.path.exists(TGT), os.path.getsize(TGT), 'B')

h = io.open(SRC, encoding='utf-8').read()
INJECT = """
<script>
/* 端到端探针：把 target 抹掉再点，保证导航在当前文档内发生 */
window.addEventListener('DOMContentLoaded', function(){
  setTimeout(function(){
    var a = document.querySelector('.frd-a');
    if(!a){ document.title = 'E2E:NO_ANCHOR'; return; }
    a.removeAttribute('target');
    a.click();
  }, 400);
});
</script>
"""
h2 = h.replace('</body>', INJECT + '</body>', 1)
assert h2 != h
io.open(TMP, 'w', encoding='utf-8', newline='').write(h2)

cmd = [EDGE, '--headless=new', '--disable-gpu', '--hide-scrollbars',
       '--window-size=1360,900', '--virtual-time-budget=20000',
       '--dump-dom', 'file:///' + TMP.replace('\\', '/')]
print('\n=== 点击跳转 ===')
r = subprocess.run(cmd, capture_output=True)
dom = r.stdout.decode('utf-8', 'replace')
print('  edge exit =', r.returncode, ' dump 长度 =', len(dom))

# 牛熊全史页的特征串（都在正文里，research.html 里绝不会有）
MARKS = ['中国股市牛熊全史', '二十九轮', '复盘注解', '制度大事记', '术语注解']
print('\n=== 落地页判定 ===')
hit = 0
for m in MARKS:
    ok = m in dom
    hit += ok
    print('  %-16s %s' % (m, '✓' if ok else '✗'))
still = '研究报告库' in dom and '友情链接' in dom
print('  仍停在研究库页  :', '是 ✗' if still else '否 ✓')

ok = hit >= 3 and not still
print('\n结论：', '✓ 跳转链路通' if ok else '✗ 跳转未生效')

os.remove(TMP) if os.path.exists(TMP) else None
print('（临时副本已清理）')
sys.exit(0 if ok else 1)
