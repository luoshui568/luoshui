# -*- coding: utf-8 -*-
"""核心结论「版式」预览 + 校验探针（只读，绝不写库）。

为什么要有它：
  verdict_std.py 只是把 HTML 写进 wb_reports，页面还要过 `renderVerdict()`
  才落到 `#verdict` 里，再被 report_theme.css 的 `.verdict` 段排版。
  「脚本里看着对」不等于「页面上排得舒服」。本探针把新版正文**只在浏览器
  内存里**塞给 `St.rep.verdict_html`，用页面自己的渲染管线出图，从而在不脏库、
  不动线上的前提下验证：

    1. 语义块都真的渲染出来了（.vlead / .vlist(dt) / .vrisk / .vtrack）
    2. **没有横向溢出**（长数字、长英文词把卡片顶出去）
    3. **没有文字被裁**（行高/内边距不够时 overflow:hidden 会切掉字）
    4. 行距与留白是否舒服（量 .vc 的行高、块间距、卡片高度）
    5. 文字总量没变（渲染后 innerText 长度 ≈ 原文，防 JS 把内容吃掉）
    6. 顺手拍一张真实截图，人眼过一遍

用法：
  python3 build/probe_verdict.py 002408
  python3 build/probe_verdict.py --all
  python3 build/probe_verdict.py 601958 --w=1180,1500
  RPT_SRC=/tmp/live_now.html python3 build/probe_verdict.py 002408   # 量线上字节
"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verdict_std  # noqa: E402  （只用它的 NEW 字典）

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, 'deploy', 'report.html')
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  var NEW = __NEW__, CODE = "__CODE__", LIVE = __LIVE__;
  var out = {code: CODE, live: !!LIVE};
  function go(){
    if(!(window.St && St.rep && St.rep.code)) return setTimeout(go, 250);
    if(!document.querySelector('#verdict .verdict')) return setTimeout(go, 250);
    var host = document.getElementById('verdict');
    if(!host) { out.err = '没有 #verdict'; return post(); }
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);
    /* 只留核心结论：从 #verdict 往上，每层隐藏其它兄弟 */
    (function(n){
      while(n && n.parentNode && n.parentNode !== document.documentElement){
        var k = n.parentNode.children;
        for(var i=0;i<k.length;i++){ if(k[i] !== n) k[i].style.display = 'none'; }
        n = n.parentNode;
      }
    })(host);

    setTimeout(function(){
      try{
        out.srcCode = St.rep.code; out.srcName = St.rep.name;
        /* ---- LIVE：不替换，直接量页面从库里读出来渲染的那份（上线验收用）
                否则：换上新版正文，走页面自己的渲染 ---- */
        if(!LIVE){ St.rep.verdict_html = NEW; renderVerdict(); }

        var v = host.querySelector('.verdict');
        if(!v){ out.err = 'renderVerdict 没产出 .verdict'; return post(); }
        var vc = v.querySelector('.vc');
        var r = v.getBoundingClientRect();
        out.box = {w:+r.width.toFixed(1), h:+r.height.toFixed(1),
                   t:+r.top.toFixed(1), l:+r.left.toFixed(1)};
        out.verdict = {
          blocks: {
            vlead: v.querySelectorAll('.vlead').length,
            vkey:  v.querySelectorAll('.vkey').length,
            vlist: v.querySelectorAll('.vlist').length,
            vlistLi: v.querySelectorAll('.vlist > li').length,
            vrisk: v.querySelectorAll('.vrisk').length,
            vriskLi: v.querySelectorAll('.vrisk li').length,
            vtrack: v.querySelectorAll('.vtrack').length,
            p: v.querySelectorAll('.vc > p').length
          },
          /* 横向溢出：卡片自身 / 内容盒 */
          overX: {
            card: v.scrollWidth - v.clientWidth,
            vc: vc ? vc.scrollWidth - vc.clientWidth : 0,
            worst: 0, worstEl: ''
          },
          /* 文字被裁：逐个块比 scrollHeight 与 clientHeight */
          clipped: [],
          textLen: (vc ? (vc.innerText || '').replace(/\s+/g, '').length : 0),
          styles: {}
        };
        var all = v.querySelectorAll('.vc *');
        for(var i=0;i<all.length;i++){
          var e = all[i];
          if(e.children.length) continue;              /* 只看叶子 */
          if(e.scrollWidth - e.clientWidth > out.verdict.overX.worst){
            out.verdict.overX.worst = e.scrollWidth - e.clientWidth;
            out.verdict.overX.worstEl = e.className || e.tagName;
          }
        }
        ['.vc', '.vlead', '.vkey', '.vlist > li', '.vrisk', '.vtrack'].forEach(function(sel){
          var e = v.querySelector(sel);
          if(!e) return;
          var cs = getComputedStyle(e);
          out.verdict.styles[sel] = {
            fs: parseFloat(cs.fontSize), lh: parseFloat(cs.lineHeight),
            padL: parseFloat(cs.paddingLeft), padT: parseFloat(cs.paddingTop),
            mb: parseFloat(cs.marginBottom), h: +e.getBoundingClientRect().height.toFixed(1)
          };
        });
        var lis = v.querySelectorAll('.vlist > li, .vrisk li');
        for(var j=0;j<lis.length;j++){
          if(lis[j].scrollHeight > lis[j].clientHeight + 1)
            out.verdict.clipped.push('li:' + (lis[j].innerText || '').slice(0, 16));
        }
        /* 块间竖距：相邻块 bottom→next top */
        var blocks = [];
        ['.vlead', '.vkey', '.vlist', '.vrisk', '.vtrack'].forEach(function(sel){
          var e = v.querySelector(sel);
          if(e) blocks.push(e);
        });
        blocks.sort(function(a, b){
          return a.getBoundingClientRect().top - b.getBoundingClientRect().top;
        });
        out.gaps = [];
        for(var g2=1;g2<blocks.length;g2++){
          out.gaps.push(+(blocks[g2].getBoundingClientRect().top -
                          blocks[g2-1].getBoundingClientRect().bottom).toFixed(1));
        }
        out.blockH = blocks.map(function(b){
          return +(b.getBoundingClientRect().height).toFixed(1);
        });
        out.ok = true;
      }catch(e){ out.err = 'ERR ' + (e && e.message || e); }
      post();
    }, 400);
  }
  function post(){
    try{ fetch('http://127.0.0.1:__PORT__/m', {method:'POST', body: JSON.stringify(out)}); }catch(e){}
  }
  setTimeout(go, 300);
})();
</script>
</body>
"""


def inject(html, js):
    i = html.rfind('</body>')
    assert i > 0, '找不到 </body>'
    return html[:i] + js + '\n' + html[i:]


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        kw['directory'] = kw.pop('directory', '/tmp')
        super().__init__(*a, **kw)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n)
        try:
            GOT.append(json.loads(body.decode('utf-8')))
        except Exception:
            pass
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *a):
        pass


def run(code, new_html, win, tmp, port, html, shot, live=False):
    js = (INJECT
          .replace('__PORT__', str(port))
          .replace('__CODE__', code)
          .replace('__NEW__', json.dumps(new_html, ensure_ascii=False))
          .replace('__LIVE__', '1' if live else '0'))
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(inject(html, js))
    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)
    GOT.clear()
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                          '--no-proxy-server', '--hide-scrollbars',
                          '--window-size=' + win, '--virtual-time-budget=25000', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 90 and not GOT:
        time.sleep(0.2)
    try:
        p.kill()
    except Exception:
        pass
    m = GOT[0] if GOT else None
    if shot and m and m.get('ok'):
        if os.path.exists(shot):
            os.remove(shot)
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--no-proxy-server', '--window-size=' + win,
                        '--virtual-time-budget=20000', '--screenshot=' + shot, url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        m['shot'] = shot
    return m


EXPECT_BLOCKS = {'vlead': 1}


def report(code, new_html, m, shot):
    if not m:
        print('✗ %-8s 未回传' % code); return 1
    if m.get('err'):
        print('✗ %-8s %s' % (code, m['err'])); return 1
    v = m.get('verdict') or {}
    b = v.get('blocks') or {}
    box = m.get('box') or {}
    ox = v.get('overX') or {}
    st = v.get('styles') or {}
    bad = []

    print('%-8s %s  卡片 %.0f×%.0f' % (code, (m.get('srcName') or '')[:8],
                                       box.get('w') or 0, box.get('h') or 0))
    print('         块：导语 %d · 强调 %d · 分点 %d（%d 条）· 风险 %d（%d 条）· 跟踪 %d · 普通段 %d'
          % (b.get('vlead', 0), b.get('vkey', 0), b.get('vlist', 0), b.get('vlistLi', 0),
             b.get('vrisk', 0), b.get('vriskLi', 0), b.get('vtrack', 0), b.get('p', 0)))
    print('         排版：正文 %s/%s px · 导语 %s/%s px · 分点 %s/%s px   块间竖距 %s   块高 %s'
          % ((st.get('.vc') or {}).get('fs'), (st.get('.vc') or {}).get('lh'),
             (st.get('.vlead') or {}).get('fs'), (st.get('.vlead') or {}).get('lh'),
             (st.get('.vlist > li') or {}).get('fs'), (st.get('.vlist > li') or {}).get('lh'),
             m.get('gaps'), m.get('blockH')))
    print('         横向溢出：卡片 %s · 正文盒 %s · 最差元素 %s（%s）   渲染后文字 %d 字'
          % (ox.get('card'), ox.get('vc'), ox.get('worst'), ox.get('worstEl'),
             v.get('textLen') or 0))

    # ---- 断言 ----
    if not b.get('vlead'):
        bad.append('没有导语块 .vlead（CSS 或结构没生效）')
    if ox.get('card', 0) > 1 or ox.get('vc', 0) > 1:
        bad.append('卡片横向溢出 %s/%s px' % (ox.get('card'), ox.get('vc')))
    if (ox.get('worst') or 0) > 1:
        bad.append('%s 横向溢出 %s px' % (ox.get('worstEl'), ox.get('worst')))
    if v.get('clipped'):
        bad.append('有 %d 处文字被裁：%s' % (len(v['clipped']), '；'.join(v['clipped'][:3])))
    if (box.get('h') or 0) < 120:
        bad.append('卡片高度只有 %s px，像是塌了' % box.get('h'))
    if (box.get('h') or 0) > 1400:
        bad.append('卡片高 %s px，一眼看不完（一段一行了？）' % box.get('h'))
    for g in (m.get('gaps') or []):
        if g < 6:
            bad.append('块间竖距只有 %s px，块会粘在一起' % g)
    # 文字量：新版剥掉标签后的字数（Python 侧算）与渲染后 innerText 字数应接近
    exp = len(verdict_std.norm(new_html))
    got = v.get('textLen') or 0
    if abs(exp - got) > 2:
        bad.append('渲染后文字 %d 字，预期 %d 字（差 %d）' % (got, exp, got - exp))

    if bad:
        print('         ✗ ' + '；'.join(bad))
        return 1
    print('         ✓ 全部断言通过' + ('   截图：%s' % shot if shot else ''))
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    win = '1500,1100'
    for a in sys.argv[1:]:
        if a.startswith('--w='):
            win = a[4:]
    noshot = '--noshot' in sys.argv
    live = '--live' in sys.argv
    codes = sorted(verdict_std.NEW) if ('--all' in sys.argv or not args) else args
    codes = [c for c in codes if c in verdict_std.NEW]
    if not codes:
        print('✗ 没有这些代码：%s' % args); return 1

    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    tmp = tempfile.mkdtemp(prefix='_vprobe_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print('=' * 108)
    print('核心结论版式预览 · %s · 视口 %s' % (os.path.basename(SRC), win))
    print('=' * 108)
    rc = 0
    for code in codes:
        shot = None if noshot else '/tmp/vd_%s_%s.png' % (code, win.replace(',', 'x'))
        m = run(code, verdict_std.NEW[code], win, tmp, port, html, shot, live)
        rc |= report(code, verdict_std.NEW[code], m, shot)
        print('-' * 108)
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
