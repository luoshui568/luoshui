"""仿真 Cloudflare Worker 的反代行为，验证「中间页绕过」方案是否可行。

逻辑：
  1. 收下浏览器请求（浏览器会带 Sec-Fetch-Mode: navigate）
  2. 转发给源站前，剥掉所有 Sec-Fetch-* 头  → 源站按「非导航请求」处理，返回 200 真实内容
  3. 回传给浏览器前，删掉 Content-Disposition → 浏览器正常渲染而不是下载
"""
import http.server
import socketserver
import urllib.request
import sys

ORIGIN = "https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com"
PORT = 8911

STRIP_REQ = ("sec-fetch-mode", "sec-fetch-site", "sec-fetch-user", "sec-fetch-dest", "sec-fetch-storage-access")
STRIP_RESP = ("content-disposition", "content-encoding", "content-length", "transfer-encoding")


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def do_GET(self):
        # ---- 1. 构造上游请求：剥掉 Sec-Fetch-* ----
        req = urllib.request.Request(ORIGIN + self.path)
        for k, v in self.headers.items():
            if k.lower() in STRIP_REQ:
                continue
            if k.lower() in ("host", "connection", "accept-encoding"):
                continue
            req.add_header(k, v)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

        try:
            with urllib.request.urlopen(req, timeout=30) as up:
                status = up.status
                body = up.read()
                rh = dict(up.headers.items())
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read()
            rh = dict(e.headers.items())
        except Exception as ex:
            msg = ("PROXY_ERR: %r" % (ex,)).encode()
            self.send_response(502); self.send_header("Content-Length", str(len(msg)))
            self.end_headers(); self.wfile.write(msg); return

        # ---- 2. 回传：删掉会导致「下载」的响应头 ----
        self.send_response_only(status)
        for k, v in rh.items():
            if k.lower() in STRIP_RESP:
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), H) as srv:
        print("proxy on http://127.0.0.1:%d" % PORT, flush=True)
        srv.serve_forever()
