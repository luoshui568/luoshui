# -*- coding: utf-8 -*-
"""验研报页 m29「企业评分」模块的**实际 DOM**（不靠截图）。

★ 为什么不用截图：`report.html` 是 `rptSlide` 幻灯片式，模块由 JS 动态注入，
  静态 HTML 里连 `data-no` 都没有 ⇒ 靠 `window.scrollBy` 定位极不可靠
  （实测 `--screenshot` 出来 9516 字节纯白）。量真实 DOM 才靠谱。

判据（回填后必须全中）：
  1. score-hero 存在（环形卡在）
  2. gauge-num 是**真实分数**（不是「—」）
  3. gauge 刻度是红色 conic（不是灰环）
  4. gauge-badge 是「评级 · XX」
  5. sc-line = 10 条
  6. sc-val 十条**全是数字**，且与目标分数逐项一致
  7. 每条进度条宽度 = 分数×10%，且按 ≥8/5–7/≤4 分 hi/mid/low 三档
  8. sc-total 的 tn/tt 与算出来的总分/评级一致
  9. 逐项 notes 仍在（回填不该把实测说明弄丢）
 10. 页面零 JS 报错

用法：
  python3 build/probe_m29_dom.py 000762 8,8,5,5,9,7,8,7,10,10
  python3 build/probe_m29_dom.py 000762          # 不给分数则只做结构体检
"""
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import score_lock as S                                            # noqa: E402

EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
CODE = sys.argv[1]
WANT = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else None
URL = 'https://liuchaowang.cn/report.html?code=' + CODE


def lib_report_date(code):
    """从库里取该研报 m29 的报告日 —— 用作「壳已换成库数据」的就绪判据。"""
    import json as _j
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = _j.load(open(os.path.join(here, 'cloud.json')))
    u = ('https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
         + 'wb_report_mods?select=html&no=eq.29&report_id=eq.' + code)
    rq = urllib.request.Request(u, headers={'Authorization': 'Bearer ' + cfg['key']})
    rows = _j.loads(urllib.request.urlopen(rq, timeout=30).read().decode())
    if not rows:
        return ''
    m = re.search(r'报告日 (\d{4}-\d{2}-\d{2})', rows[0]['html'] or '')
    return m.group(1) if m else ''


REPORT_DATE = lib_report_date(CODE)

GOT = []

JS_HEAD = r"""
<script>
/* ⚠️⚠️ 必须在壳的 `window.RPT_SEED = {...600456 母本...}` **之前** 就把它定义掉。
   壳里那行在 <head> 内（约 L2210），而壳的取数是
     SEED = window.RPT_SEED || null   →   有种子就用种子，不拉库。
   不盖住它 ⇒ 量到的永远是宝钛母本（表现为 总分 70.5、报告日 2026-08-24、
   sc-val 空而进度条满），看起来像"库没生效"，其实是我们看错了对象。
   ★ 所以这里必须插在 <head> 开头，而不是 rfind('</body>')。 */
window.RPT_SEED = null;
</script>
"""

JS = r"""
<script>
/* 等壳真的把库里的 m29 换上去：判据 = 环形卡上的报告日等于目标研报的报告日。
   ⚠️ 别用「sc-val 非空」当就绪判据 —— 壳的 scoreLive 会重写这些格。
   死等固定秒数则会在慢网下量到中间态（这坑踩过一次）。 */
var __tries = 0;
function __ready(){
  var n = document.querySelector('.gauge-num');
  var s = document.querySelector('.score-hero .g-sub');
  var num = n ? n.textContent.replace(/\s+/g,'') : '';
  var sub = s ? s.textContent : '';
  /* ★★ 还要等 CSS 过渡跑完：`.criteria.sc-live .sc-bar i{transition:width .16s}`
     （壳里 L930），`scPaint` 是入场就设 width 的 ⇒ 过渡未结束时去读 style
     会读到**动画中途**的值（实测 10 分/100% 被读成 90% ⇒ 总分 74.1 变 72.6）。
     判据：连读两次条宽，间隔 400ms 都相同才采信。 */
  var bars = document.querySelectorAll('.sc-bar i');
  var sig = [];
  for(var i=0;i<bars.length;i++) sig.push(bars[i].style.width);
  var s2 = (window.__sig2 || []).join('|');
  if(window.__sig1 === sig.join('|')){
    return /\/100/.test(num) && sub.indexOf('__DATE__') >= 0 && sig.length === 10;
  }
window.__sig1 = sig.join('|');
    setTimeout(__go, 400);
    return false;
}
function __go(){
  __tries++;
  if(__ready() || __tries > 100){
    setTimeout(function(){ collect(); }, 800);
    return;
  }
  setTimeout(__go, 400);
}
function collect(){
  var out = { err: (window.__RPT_ERR || []).slice(0, 8), tries: __tries };
  try{
    var hero = document.querySelector('.score-hero');
    out.hasHero = !!hero;
    if(hero){
      var g = hero.querySelector('.gauge');
      out.ring   = g ? (g.getAttribute('style')||'') : '';
      var n = hero.querySelector('.gauge-num');
      out.num    = n ? n.textContent.replace(/\s+/g,' ').trim() : '';
      var b = hero.querySelector('.gauge-badge');
      out.badge  = b ? b.textContent.trim() : '';
      out.sub    = (function(){ var s = hero.querySelector('.g-sub'); return s?s.textContent.trim():''; })();
    }
    var lines = document.querySelectorAll('.sc-line');
    out.lines = lines.length;
    out.items = [];
    for(var i=0;i<lines.length;i++){
      var L = lines[i];
      function t(sel){ var e = L.querySelector(sel); return e ? e.textContent.trim() : ''; }
      var bar = L.querySelector('.sc-bar i');
      /* ★★ 壳的 scoreLive 会把 `.sc-val` 的文字**换成 <input type=number>**（L3220
         `it.val.textContent=''` 然后 appendChild(inp)）⇒ 量 textContent 永远是空！
         真实分数在 input.value 里。这是设计不是 bug。
         ⇒ 必须先取 input.value，取不到再退回 textContent。 */
      var vp = L.querySelector('.sc-val input');
      var vtext = t('.sc-val');
      out.items.push({
        no:   t('.sc-no'),
        name: t('.sc-name'),
        w:    L.getAttribute('data-w') || t('.sc-w'),
        val:  (vp && vp.value !== '') ? vp.value : vtext,
        viaInput: !!(vp && vp.value !== ''),
        cls:  bar ? bar.className : '',
        wid:  bar ? (bar.getAttribute('style')||'') : '',
        note: (L.querySelector('.sc-note') || {textContent:''}).textContent.trim().length
      });
    }
    var tot = document.querySelector('.sc-total');
    if(tot){
      out.tn = (tot.querySelector('.tn')||{textContent:''}).textContent.trim();
      out.tt = (tot.querySelector('.tt')||{textContent:''}).textContent.trim();
    }
    var src = document.querySelector('.criteria') ;
    out.criteriaHead = src ? (src.querySelector('.criteria-head')||{textContent:''}).textContent.replace(/\s+/g,' ').trim() : '';
  }catch(e){ out.err.push('collect: ' + String(e && e.message || e)); }
  fetch('http://127.0.0.1:__PORT__/done', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify(out)})
    .catch(function(e){ });
}
setTimeout(__go, 1200);
</script>
"""


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def main():
    r = subprocess.run(['curl', '-s', '-H', 'Cache-Control: no-cache', URL],
                       capture_output=True, text=True, timeout=120)
    html = r.stdout
    if len(html) < 100000:
        print('✗ 抓页面失败 %d 字节' % len(html)); return 1

    tmp = tempfile.mkdtemp(prefix='_m29p_')
    port = free_port()
    # ★ 注入点必须是 `window.RPT_SEED = {...}` 那一行**之前**，且要在**它所属 script 块之前**。
    #   实测位置：`</head>` 在 1524916，而 RPT_SEED 在 1527397 —— SEED 在 body 里、不在 head，
    #   所以插 `</head>` 前无效（插太早），插 `</body>` 前也无效（插太晚，壳已赋值）。
    #   正确做法：找 RPT_SEED 的下标，回退到它所属 <script> 的开头插。
    j = html.rfind('</body>')
    si = html.find('window.RPT_SEED =')
    # ★★ 直接把壳里那行 `window.RPT_SEED = {...600456 母本...}` **整行替换成 null**。
    #   实测（L2282~2283）：`<script>window.RPT_CFG = {...}` 与 `window.RPT_SEED = {...}</script>`
    #   在**同一个脚本块**里，消费点是 L2292 `var SEED = window.RPT_SEED || null`。
    #   ⇒ 在前面另插 `window.RPT_SEED = null` **没用**（会被后面那行整个覆盖）——
    #     这就是之前一直量到母本（总分 70.5 / 报告日 2026-08-24）的原因。
    #   踩过的两个错路也别再走：
    #     · 插 `</head>` 前 → SEED 实测在 body 里，太早无效；
    #     · 往那行前面插字符串 → 落进跨 17 万字符的脚本块内部，SyntaxError 整壳瘫（@2092）。
    end = html.find('</script>', si)
    line_end = html.find('\n', si)
    cut_end = end if (0 <= end - si < len(html) - si) else line_end
    out = html[:si] + 'window.RPT_SEED = null;' + html[cut_end:j] + \
          JS.replace('__PORT__', str(port)).replace('__DATE__', REPORT_DATE) + html[j:]
    io.open(os.path.join(tmp, 'p.html'), 'w', encoding='utf-8').write(out)
    print('SEED 赋值 char %d..%d 已替换为 null（壳里消费点 L2292）' % (si, cut_end))

    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            try: GOT.append(json.loads(self.rfile.read(n).decode('utf-8')))
            except Exception as e: GOT.append({'err': ['bad: %s' % e]})
            self.send_response(204); self.end_headers()

    srv = HTTPServer(('127.0.0.1', port),
                     lambda *a, **kw: H(*a, directory=tmp, **kw))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # ★ 必须带 ?code=：壳 L2448 是 `var code = qs('code') || (SEED && …)`，
    #   打了种子就必须同时给 code，否则 code 为空 ⇒ 什么都不渲染。
    #   （之前量不到目标研报，就是「只打了种子、没给 code」这个组合。）
    url = 'http://127.0.0.1:%d/p.html?code=%s' % (port, CODE)
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                          '--no-proxy-server', '--hide-scrollbars', '--no-first-run',
                          '--no-default-browser-check', '--disable-breakpad',
                          '--window-size=1400,1200',
                          '--user-data-dir=' + tempfile.mkdtemp(prefix='_m29pe_'),
                          url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 120 and not GOT:
        time.sleep(0.3)
    p.terminate()
    try: p.wait(timeout=10)
    except Exception: p.kill()
    srv.shutdown()

    if not GOT:
        print('✗ 页面没回传（%ds）' % (time.time() - t0)); return 1
    m = GOT[0]

    ok, red = 0, []
    def chk(name, cond, detail=''):
        nonlocal ok
        print('  %s %-42s %s' % ('✅' if cond else '❌', name, detail))
        if cond: ok += 1
        else: red.append(name)

    print('=' * 92)
    print('m29 DOM 体检  code=%s  mode=%s' % (CODE, '对分回填' if WANT else '结构体检'))
    print('=' * 92)
    print('环形: %s   徽章: %s' % (m.get('num'), m.get('badge')))
    print('子说明: %s' % m.get('sub'))
    print('总分位 tn=%r  评级 tt=%r' % (m.get('tn'), m.get('tt')))
    print('\n---- 逐项（分数取自 .sc-val input，壳把文字换成了输入框）----')
    for it in m.get('items') or []:
        print('  %2s %-26s w=%-4s val=%-4s(%s) bar=%-4s %-24s note=%d字'
              % (it['no'], it['name'][:26], it['w'], it['val'],
                 'input' if it.get('viaInput') else 'text',
                 it['cls'], it['wid'], it['note']))

    print('\n---- 判据 ----')
    chk('页面零 JS 报错', not m.get('err'), str(m.get('err'))[:80])
    chk('score-hero 在', m.get('hasHero'))
    chk('sc-line = 10 条', m.get('lines') == 10, '%s 条' % m.get('lines'))

    num = (m.get('num') or '').replace('/100', '').strip()
    isblank = (num in ('—', '', '-'))
    chk('gauge-num 是真实分数', not isblank, repr(num))
    chk('环形是红色刻度（非灰环）', '#c8102e' in (m.get('ring') or ''), (m.get('ring') or '')[:56])
    chk('徽章是「评级 · XX」', (m.get('badge') or '').startswith('评级 · '), repr(m.get('badge')))

    vals = [(it.get('val') or '') for it in (m.get('items') or [])]
    allnum = all(re.fullmatch(r'\d+', v or '') for v in vals)
    chk('十条 sc-val 全是数字', allnum, ' / '.join(vals))
    chk('sc-val 无「—」', '—' not in vals)

    if WANT:
        got = [int(v) for v in vals] if allnum else []
        chk('逐项与目标分数一致', got == WANT, '目标 %s' % WANT)
        tot = S.total_of(WANT)
        rate = S.grade_of(tot)
        chk('总分 = total_of(scores)', (m.get('tn') or '') == ('%g' % tot), '%s vs %s' % (m.get('tn'), tot))
        chk('评级 = grade_of(总分)', (m.get('tt') or '') == ('评级：' + rate), '%s vs 评级：%s' % (m.get('tt'), rate))
        # 进度条：宽度 = 分数×10%，档位 ≥8 hi / 5-7 mid / ≤4 low
        bad = []
        for it, w in zip(m.get('items') or [], WANT):
            wid = re.search(r'width:\s*(\d+)%', it.get('wid') or '')
            cls = it.get('cls') or ''
            want_cls = 'hi' if w >= 8 else ('mid' if w >= 5 else 'low')
            if not wid or int(wid.group(1)) != w * 10 or want_cls not in cls:
                bad.append('第%s项 w=%s cls=%s (应 %d%%/%s)' % (it['no'], wid.group(1) if wid else '?', cls, w*10, want_cls))
        chk('进度条宽度与档位', not bad, bad[0] if bad else '10/10 正确')

    notes_n = sum(1 for it in (m.get('items') or []) if (it.get('note') or 0) > 0)
    chk('逐项实测说明仍在', notes_n == 10, '%d/10 条' % notes_n)

    print('\n结论: %d 项通过, %d 项失败' % (ok, len(red)))
    if red:
        print('失败项: %s' % red); return 1
    print('✅ 全绿')
    return 0


raise SystemExit(main())