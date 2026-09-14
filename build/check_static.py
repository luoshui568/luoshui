# -*- coding: utf-8 -*-
"""抠出产物里每个 <script> 块，逐个 node --check；并查标签配对。"""
import io, os, re, subprocess, sys, tempfile

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'

ok_all = True
for f in ['deploy/index.html', 'deploy/report.html', 'deploy/research.html']:
    p = os.path.join(ROOT, f)
    s = io.open(p, encoding='utf-8').read()
    blocks = re.findall(r'<script[^>]*>([\s\S]*?)</script>', s)
    print('==== %s  %d 个 script 块' % (f, len(blocks)))
    for i, b in enumerate(blocks):
        tmp = os.path.join(ROOT, 'build', '_chk.js')
        io.open(tmp, 'w', encoding='utf-8').write(b)
        r = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
        # 不删：文件名固定，下轮直接覆盖即可。
        # 环境的 safe-delete 守卫按「整轮累计删除数」拦截（阈值 50，Edge 启动也会 churn），
        # 自己再删就是白送人头 —— 曾把截图脚本卡在第 3 张图上。
        status = 'OK' if r.returncode == 0 else 'FAIL'
        if r.returncode != 0:
            ok_all = False
            print('  [%d] %s len=%d\n%s' % (i, status, len(b), r.stderr[:600]))
        else:
            print('  [%d] %s len=%d' % (i, status, len(b)))
    # 标签配对
    for tag in ['script', 'section', 'div', 'textarea', 'table', 'details']:
        o = len(re.findall(r'<' + tag + r'[\s>]', s))
        c = len(re.findall(r'</' + tag + r'>', s))
        if o != c:
            ok_all = False
            print('  !! <%s> 开 %d / 闭 %d 不配对' % (tag, o, c))
        else:
            print('  <%s> %d 配对 OK' % (tag, o))

    if f != 'deploy/index.html':
        continue

    # ⚠️ 规则 A：不许绕过 insertRow 直接改本地数组
    #    「按主键新建记录」必须走 insertRow（落本地 + enqueue POST 推云端）。
    #    曾出现 `S.stocks.push(row)` —— 界面提示成功、刷新后全没、库里查不到。
    #    ★ 先剥掉注释与反引号里的举例，否则注释里写的反面教材会把规则自己判红。
    js = '\n'.join(blocks)
    js = re.sub(r'/\*[\s\S]*?\*/', ' ', js)
    js = re.sub(r'//[^\n]*', ' ', js)
    js = re.sub(r'`[^`]*`', ' ', js)
    ALLOW = [
        'S[kind].unshift(row); saveLocal();',                                   # insertRow 本体
        "arr.forEach(function(r){ S[kind].push(defaults(kind, JSON.parse(JSON.stringify(r)))); });",  # seedFrom（本地演示数据）
        'S[kind].push(backup); sortState(); saveLocal();',                      # deleteRow 失败回滚
    ]
    PAT_A = re.compile(r'S\s*(?:\[[^\]]+\]|\.[a-zA-Z]+)\s*\.\s*(?:push|unshift|splice)\s*\(')
    bad_a = []
    for ln in js.split('\n'):
        t = ln.strip()
        if PAT_A.search(t) and t not in ALLOW:
            bad_a.append(t[:110])
    print('  规则A 绕过入队直接改本地数组: %s' % ('OK' if not bad_a else 'FAIL'))
    if bad_a:
        ok_all = False
        for t in bad_a:
            print('     !! ' + t)

    # ⚠️ 规则 B：禁止把 Cloud.state 当放行条件（只能靠成功回调修的状态 = 静默丢数据）
    PAT_B1 = re.compile(r"Cloud\.state\s*!==?\s*'on'")
    PAT_B2 = re.compile(r'Cloud\.state[^\n]*\breturn\b')
    bad_b = [ln.strip()[:110] for ln in js.split('\n') if PAT_B1.search(ln) or PAT_B2.search(ln)]
    print('  规则B Cloud.state 当放行条件: %s' % ('OK' if not bad_b else 'FAIL'))
    if bad_b:
        ok_all = False
        for t in bad_b:
            print('     !! ' + t)

    # ⚠️ 规则 C：登录门两个视图必须靠 display 互斥（注册表单比登录表单高）
    for need in ['id="g-login"', 'id="g-reg"', 'id="g-regbtn"', 'App.doRegister']:
        if need not in s:
            ok_all = False
            print('  !! 登录门缺少 %s' % need)
    print('  规则C 登录/注册 双视图齐全: OK')

print()
print('EXIT=' + ('0 全部通过' if ok_all else '1 有问题'))
sys.exit(0 if ok_all else 1)
