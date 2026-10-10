# -*- coding: utf-8 -*-
"""回读 ~/.workbuddy/mcp.json，对每个服务做 initialize + tools/list，验真实产物"""
import io, json, os, ssl, sys, urllib.request, urllib.error

CFG = r'C:\Users\50522\.workbuddy\mcp.json'

def post(url, body, headers, sess=None):
    h = dict(headers)
    h.setdefault('Content-Type', 'application/json')
    h.setdefault('Accept', 'application/json, text/event-stream')
    h.setdefault('MCP-Protocol-Version', '2025-06-18')
    if sess:
        h['mcp-session-id'] = sess
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=h, method='POST')
    try:
        r = urllib.request.urlopen(req, timeout=35, context=ssl.create_default_context())
        return r.status, dict(r.headers), r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8', 'replace')
    except Exception as e:
        return -1, {}, '%s: %s' % (type(e).__name__, str(e)[:200])

def sse(raw):
    ls = [l[5:].strip() for l in raw.splitlines() if l.startswith('data:')]
    return '\n'.join(ls) if ls else raw

def main():
    cfg = json.load(io.open(CFG, encoding='utf-8'))
    ok = bad = 0
    for name, v in cfg.get('mcpServers', {}).items():
        url = v.get('url')
        hdrs = v.get('headers') or {}
        auth = hdrs.get('Authorization', '')
        print('=== %s' % name)
        print('    url  %s' % url)
        print('    auth %s%s' % (auth[:26], '...(len=%d)' % len(auth)))
        if not url:
            print('    [SKIP] 无 url（非 HTTP 型）'); print(); continue
        st, hdr, raw = post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "wb-verify", "version": "1"}}},
                            hdrs)
        sess = hdr.get('mcp-session-id')
        body = sse(raw)
        good = st == 200 and '"result"' in body
        print('    initialize http=%s %s' % (st, 'OK ✅' if good else 'FAIL ❌'))
        if not good:
            print('      %s' % body.replace('\n', ' ')[:220]); bad += 1; print(); continue
        post(url, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, hdrs, sess)
        st2, _, raw2 = post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, hdrs, sess)
        b2 = sse(raw2)
        try:
            tools = json.loads(b2).get('result', {}).get('tools', [])
            print('    tools/list  http=%s  工具 %d 个 ✅' % (st2, len(tools)))
            print('      %s' % ', '.join(t.get('name') for t in tools))
            ok += 1
        except Exception:
            print('    tools/list  http=%s  ❌ %s' % (st2, b2.replace('\n', ' ')[:220]))
            bad += 1
        print()
    print('===== 结论：可用 %d / 失败 %d，共 %d 个服务 =====' % (ok, bad, ok + bad))
    return 0 if bad == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
