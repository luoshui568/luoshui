# -*- coding: utf-8 -*-
"""通用前端脚本体检：抠出每个 <script> 内联块 → node --check；同时统计标签配对。

用法： python build/jscheck.py [deploy/xxx.html ...]
默认检查 deploy/ 下三页。
⚠️ 本机 coreutils 全缺（ls/cat/grep/head/tail/dirname 都没有）→ 一律用绝对路径的
   Python / Node，别在 shell 里拼管道。
"""
import os, re, subprocess, sys, tempfile

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
DEF = ['deploy/index.html', 'deploy/report.html', 'deploy/research.html']

SCRIPT = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S | re.I)
PAIR = ['div', 'p', 'table', 'tr', 'td', 'th', 'ul', 'ol', 'li', 'span', 'h3', 'svg',
        'section', 'article', 'figure', 'button', 'select', 'textarea', 'style', 'script']


def check_pair(src, tag):
    o = len(re.findall(r'<%s\b' % tag, src, re.I))
    c = len(re.findall(r'</%s\s*>' % tag, src, re.I))
    return o, c


def main(paths):
    bad = 0
    for rel in paths:
        p = os.path.join(ROOT, rel) if not os.path.isabs(rel) else rel
        if not os.path.exists(p):
            print('MISS %s' % rel)
            bad += 1
            continue
        src = open(p, encoding='utf-8').read()
        print('=' * 66)
        print('【%s】 %d 字符' % (rel, len(src)))
        n_js = n_json = 0
        for idx, (attrs, body) in enumerate(SCRIPT.findall(src), 1):
            if 'src=' in attrs.lower():
                continue
            if 'application/json' in attrs.lower() or 'ld+json' in attrs.lower():
                n_json += 1
                continue
            n_js += 1
            tf = os.path.join(tempfile.gettempdir(), '_jscheck_%d_%d.js' % (os.getpid(), idx))
            open(tf, 'w', encoding='utf-8').write(body)
            r = subprocess.run([NODE, '--check', tf], capture_output=True, text=True)
            os.remove(tf)
            if r.returncode != 0:
                bad += 1
                print('  ❌ script#%d 语法错：%s' % (idx, (r.stderr or '').strip().splitlines()[:3]))
            else:
                print('  ✅ script#%d  %d 字符' % (idx, len(body)))
        miss = []
        # ⚠️ 统计标签配对前必须掏空两处「合法含标签名」的地方：
        #    ① 脚本块 —— JS 里大量出现 '<p ...>' / '<span ...>' 字符串模板；
        #    ② HTML 注释 —— 注释里写明「文字要裹在 span 里」这类说明会被当成开标签。
        #    漏了这两条就会假报（2026-09-17 白排查两轮）：p 开95/闭72、span 开1/闭0。
        plain = SCRIPT.sub(lambda m: '<script%s></script>' % m.group(1), src)
        plain = re.sub(r'<!--.*?-->', '', plain, flags=re.S)
        for t in PAIR:
            o, c = check_pair(plain, t)
            if o != c:
                miss.append('%s 开%d/闭%d' % (t, o, c))
        # ⚠️ 配对检查只作**提示**，不计入失败：p / li / td 等标签在 HTML 里允许省略
        #    闭合标签，手工统计必然有偏差；真正的硬判据是上面的 node --check 与
        #    check_static.py。别让这条假红挡住上线（2026-09-17 教训）。
        if miss:
            print('  脚本块 %d 个（json %d）· ℹ️ 标签配对（仅提示）：%s' % (n_js, n_json, '; '.join(miss)))
        else:
            print('  脚本块 %d 个（json %d）· ✅ 标签配对' % (n_js, n_json))
    print('=' * 66)
    print('结论：%s' % ('全部通过 ✅' if bad == 0 else '有 %d 处问题 ❌' % bad))
    return bad


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1:] or DEF) else 0)
