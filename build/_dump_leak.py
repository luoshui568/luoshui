# -*- coding: utf-8 -*-
"""dump-dom 出模块 25 的渲染结果，硬找 {{fn: 出现的 DOM 位置与元素名。"""
import io, os, re, shutil, subprocess

ROOT = r"C:\Users\50522\WorkBuddy\2026-09-10-14-50-38"
HERE = os.path.join(ROOT, "build")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
pro = os.path.join(HERE, "_eprof_dom")
if os.path.isdir(pro): shutil.rmtree(pro, ignore_errors=True)

pv = os.path.join(HERE, "_pv_m25.html")
url = "file:///" + pv.replace("\\", "/") + "?code=600456"
cmd = [EDGE, "--headless=new", "--disable-gpu", "--user-data-dir=" + pro,
       "--virtual-time-budget=10000", "--dump-dom", url]
r = subprocess.run(cmd, capture_output=True, timeout=240)
dom = r.stdout.decode("utf-8", "replace")
print("DOM %d 字符" % len(dom))

# 找 {{fn: 在 DOM（而非 script 里）的位置
for m in re.finditer(r"\{\{fn:", dom):
    i = m.start()
    ctx = dom[max(0, i - 400):i + 200]
    # 判断是不是在 <script> 里
    before = dom[:i]
    in_script = before.rfind("<script") > before.rfind("</script>")
    tag = "【script 内】" if in_script else "★★★【DOM 元素内】"
    print()
    print("@" + str(i) + "  " + tag)
    print("   …" + ctx.replace("\n", " ")[-460:])
