# -*- coding: utf-8 -*-
"""「思想体系总目」新增第 7 张书卡（巴菲特股东信）后的渲染截图。

只读 deliver/ 下的两份源文件，拷进临时目录跑，跑完自清，不碰 deploy_site/。
"""
import http.server
import os
import shutil
import socketserver
import subprocess
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
DELIVER = os.path.join(ROOT, 'deliver')
SITE = os.path.join(HERE, '_shixiang_site')
OUT = DELIVER
PORT = 8805
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


def shot(page, out, w, h, budget=9000):
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu',
           '--disable-dev-shm-usage', '--hide-scrollbars',
           '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget, '--screenshot=' + out,
           'http://127.0.0.1:%d/%s' % (PORT, page)]
    subprocess.run(cmd, capture_output=True, timeout=300)
    return os.path.exists(out), (os.path.getsize(out) if os.path.exists(out) else 0)


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    shutil.copy(os.path.join(DELIVER, '思想体系总目.html'), os.path.join(SITE, 'shixiang.html'))
    shutil.copy(os.path.join(DELIVER, '巴菲特股东信六十年维度全解.html'), os.path.join(SITE, 'buffett.html'))
    srv = serve()
    try:
        for name, page, w, h in [
            ('验证-总目七卡.png', 'shixiang.html', 1280, 2760),
            ('验证-巴菲特页顶.png', 'buffett.html', 1280, 2600),
        ]:
            out = os.path.join(OUT, name)
            ok, size = shot(page, out, w, h)
            print('%-22s ok=%s size=%d' % (name, ok, size))
    finally:
        srv.shutdown()
        shutil.rmtree(SITE, ignore_errors=True)


if __name__ == '__main__':
    main()
