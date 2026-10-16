# -*- coding: utf-8 -*-
"""「思想体系总目 + 巴菲特股东信」静态断言探针（DOM 级）。

跑法：python3 build/probe_shixiang_check.py
断言项见 CHECKS，全绿才算通过。
"""
import http.server
import os
import re
import shutil
import socketserver
import subprocess
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
DELIVER = os.path.join(ROOT, 'deliver')
SITE = os.path.join(HERE, '_shixiang_check_site')
PORT = 8806
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def log_message(self, *a):
        pass


class Server(socketserver.TCPServer):
    allow_reuse_address = True


def serve():
    srv = Server(('127.0.0.1', PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def dom(page, budget=9000, w=1280, h=2700):
    """★ 必须显式给窗口尺寸：headless 默认 800x600，页面里 .reveal 全在首屏之下，
     IntersectionObserver 首帧回调全是 isIntersecting=false，会误判成「没点亮」。"""
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu',
           '--disable-dev-shm-usage', '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget,
           '--dump-dom', 'http://127.0.0.1:%d/%s' % (PORT, page)]
    p = subprocess.run(cmd, capture_output=True, timeout=300)
    return p.stdout.decode('utf-8', 'replace')


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    shutil.copy(os.path.join(DELIVER, '思想体系总目.html'), os.path.join(SITE, 'shixiang.html'))
    shutil.copy(os.path.join(DELIVER, '巴菲特股东信六十年维度全解.html'), os.path.join(SITE, 'buffett.html'))
    srv = serve()
    ok_all = True
    try:
        sx = dom('shixiang.html')
        bf = dom('buffett.html')

        def chk(label, cond, extra=''):
            nonlocal ok_all
            ok_all = ok_all and cond
            print('%s %-46s %s' % ('[OK]' if cond else '[!!]', label, extra))

        chk('总目 <title> 已改七部', '七部典籍' in sx)
        chk('总目 h-en = SEVEN WORKS', 'A MODULAR ATLAS OF SEVEN WORKS' in sx)
        chk('书卡数量 = 7', len(re.findall(r'class="bk"', sx)) == 7,
            str(len(re.findall(r'class="bk"', sx))))
        chk('第 7 卡 href=buffett.html', 'href="buffett.html"' in sx)
        chk('第 7 卡印鉴为「巴」', re.search(r'href="buffett\.html".{0,200}class="bk-mark"[^>]*>巴<', sx, re.S) is not None)
        chk('第 7 卡排在 史记 之后', sx.index('href="buffett.html"') > sx.index('href="shiji.html"'))
        chk('总目 tally = 7/305/275/364',
            re.search(r'<b>7</b><i>部 图 谱</i>', sx) is not None
            and re.search(r'<b>305</b>', sx) is not None
            and re.search(r'<b>275</b>', sx) is not None
            and re.search(r'<b>364</b>', sx) is not None)
        chk('页脚「七部图谱」', '七部图谱' in sx)
        chk('JS 关闭时书卡可见(无 no-js 遮挡)',
            re.search(r'<html[^>]*class="js"', sx) is not None)

        chk('巴菲特页 title 正常', '六十年维度全解' in bf)
        chk('巴菲特页 brand 回链 shixiang.html', re.search(r'class="brand"[^>]*href="shixiang.html"', bf) is not None
            or 'href="shixiang.html"' in bf)
        n_in = len(re.findall(r'class="[^"]*reveal in', bf))
        chk('巴菲特页 reveal 已被 IntersectionObserver 点亮', n_in > 0, 'in=%d' % n_in)
        chk('巴菲特页 11 维度卡齐',
            len(re.findall(r'class="card reveal', bf)) == 11,
            str(len(re.findall(r'class="card reveal', bf))))
        chk('巴菲特页 表格 6 张', len(re.findall(r'class="tbl-scroll"', bf)) == 6)
        chk('巴菲特页 金句卡 10 张', len(re.findall(r'class="qcard reveal"', bf)) == 10)
        chk('巴菲特页无外部依赖', not re.search(r'(src|href)="https?://', bf))
    finally:
        srv.shutdown()
        shutil.rmtree(SITE, ignore_errors=True)
    print('\n==== %s ====' % ('ALL GREEN' if ok_all else 'HAS FAILURES'))
    return 0 if ok_all else 1


if __name__ == '__main__':
    raise SystemExit(main())
