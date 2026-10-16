# -*- coding: utf-8 -*-
"""研报页「ⓘ 报告说明」弹窗 · 端到端探针

用法：
  python3 build/probe_report_notes.py [code=002237]

做什么（全部只读，不改仓库文件）：
  1. 把 deploy/report.html 复制到临时目录并注入一段检查脚本
  2. 用 http://127.0.0.1:<port>/report.html?code=xxx 打开 —— **必须走 http 而不是 file://**，
     因为页面要直连云数据库取真实研报（file:// 的 Origin 为 null，会被网关 403 挡掉，
     只会退化成 600456 的内置副本）
  3. 断言：① 页头有「ⓘ 报告说明」入口 ② 点开有弹窗、分节 ≥2 ③ 核心结论里不再有注解
     ④ 指标口径小字已从正文消失 ⑤ 打印副本 #printNotes 有内容
  4. 顺带截两张图：弹窗打开 / 弹窗关闭（看页头入口）

为什么不用 --dump-dom：报告页 1.8MB，dump 出来还要解析；POST 回传更干净。
"""
import io, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []                      # 探针回传的测量结果（Handler 里 append，主线程里读）
# 默认测本地产物；设 RPT_SRC=/tmp/live.html 即可改成「抓下来的线上字节」
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, "deploy", "report.html")
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  var out = {}, OPEN = __OPEN__;
  function $(id){ return document.getElementById(id); }
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g,' ').trim() : ''; }
  function go(){
    if(!(window.Rpt && window.St && St.rep && St.rep.code)){ return setTimeout(go, 250); }
    var r = St.rep;
    out.code = r.code; out.name = r.name; out.src = St.src;
    out.verdict_len = (r.verdict_html || '').length;
    out.notice_len  = (r.notice_html  || '').length;
    out.kpi_note_len = (r.kpi_note   || '').length;
    out.mods = (St.mods || []).length;

    var hero = $('hero'), btn = hero ? hero.querySelector('.notebtn') : null;
    out.hero_has_btn = !!btn;
    out.hero_btn_text = txt(btn);

    var n = $('kpiNote');
    out.kpiNote = n ? {len:(n.innerHTML || '').length, display:getComputedStyle(n).display} : null;
    out.printNotes_len = $('printNotes') ? ($('printNotes').innerHTML || '').length : -1;

    var vtxt = txt($('verdict'));
    out.verdict_len_text = vtxt.length;
    out.verdict_anno_left = ['标准模板建档','不给出评级','MISSING','模型输出','数据口径']
      .filter(function(k){ return vtxt.indexOf(k) >= 0; });
    out.verdict_head = vtxt.slice(0, 60);

    if(!btn){ post(); return; }
    if(!OPEN){ setTimeout(post, 300); return; }
    /* ⚠️ --virtual-time-budget 下 CSS 动画/过渡不推进，弹窗会停在入场动画的中间帧
       （rptSlide），量出来的位置是偏的。所以测量前先把动效关掉。 */
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);
    btn.click();
    setTimeout(function(){
      var nm = $('rptNMask');
      out.modal_on = nm ? nm.className.indexOf('on') >= 0 : false;
      var box = nm ? nm.querySelector('.rpt-nbox') : null;
      if(box){
        var b = box.getBoundingClientRect();
        out.modal_w = +b.width.toFixed(1); out.modal_h = +b.height.toFixed(1);
        var bd = box.querySelector('.bd');
        out.modal_scrollable = bd ? (bd.scrollHeight - bd.clientHeight) : null;
        var mbox = box.getBoundingClientRect();
        out.modal_inside_viewport = (mbox.left >= -0.5 && mbox.right <= window.innerWidth + 0.5 &&
                                     mbox.top >= -0.5 && mbox.bottom <= window.innerHeight + 0.5);
      }
      out.modal_sections = nm ? nm.querySelectorAll('.rpt-nbox .ns').length : 0;
      out.modal_titles = [].slice.call(nm ? nm.querySelectorAll('.rpt-nbox .ns .nt') : [])
        .map(function(e){ return txt(e); });
      out.modal_body_len = nm ? txt(nm.querySelector('.rpt-nbox .bd')).length : 0;
      out.modal_has_legend = nm ? !!nm.querySelector('.legend .lg') : false;
      post();
    }, 450);
  }
  function post(){
    document.title = 'PROBE ' + JSON.stringify({code:out.code, sections:out.modal_sections});
    try{ fetch('http://127.0.0.1:__PORT__/m', {method:'POST', body: JSON.stringify(out)}); }catch(e){}
  }
  setTimeout(go, 300);
})();
</script>
</body>
"""


def inject(html, js):
    """把脚本插到**最后一个** </body> 之前。

    ⚠️ 报告页里 `</body>` 出现两次：第一次在 JS 字符串里（打印预览那段的
    `... /></body>`），用 replace(..., 1) 会把脚本塞进那个字符串里 —— 结果是
    既不改页面、也不报错。必须按 rfind 定位。
    """
    i = html.rfind('</body>')
    assert i > 0, '找不到 </body>'
    return html[:i] + js + '\n' + html[i:]


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    noshot = '--noshot' in sys.argv
    code = args[0] if args else '002237'
    win = '1500,1600'
    for a in sys.argv[1:]:
        if a.startswith('--w='):
            win = a[4:]
    tmp = tempfile.mkdtemp(prefix='_rptprobe_')
    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    port = free_port()

    def mk(name, opened):
        io.open(os.path.join(tmp, name), 'w', encoding='utf-8').write(
            inject(html, INJECT.replace('__PORT__', str(port)).replace('__OPEN__', opened)))

    mk('report.html', '1')

    # 同一个端口既发静态页、也收 POST
    # （不要用 functools.partial 当基类 —— 它不是类，会报 metaclass conflict）
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            kw['directory'] = tmp
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

    srv = HTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)
    print('=' * 92)
    print('研报页「报告说明」弹窗 · 端到端检查    %s   [%s]' % (url, win))
    print('=' * 92)

    GOT.clear()
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                          '--window-size=' + win, '--virtual-time-budget=30000', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 90 and not GOT:
        time.sleep(0.25)
    try:
        p.kill()
    except Exception:
        pass

    if not GOT:
        print('✗ 未回传 —— 渲染超时或脚本未执行')
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    m = GOT[0]

    checks = [
        ('取到线上研报（非内置副本）', m.get('src') == 'cloud', 'src=%s code=%s %s' % (m.get('src'), m.get('code'), m.get('name'))),
        ('页头有「ⓘ 报告说明」入口', bool(m.get('hero_has_btn')), m.get('hero_btn_text', '')),
        ('弹窗可打开', bool(m.get('modal_on')), 'on=%s' % m.get('modal_on')),
        ('弹窗有分节（口径/图例/说明）', (m.get('modal_sections') or 0) >= 1,
         '分节=%s %s' % (m.get('modal_sections'), '｜'.join(m.get('modal_titles') or []))),
        ('弹窗在视口内', bool(m.get('modal_inside_viewport')),
         '尺寸 %.0f×%.0f' % (m.get('modal_w') or 0, m.get('modal_h') or 0)),
        ('核心结论里不再有注解', not (m.get('verdict_anno_left') or []),
         '残留=%s' % (m.get('verdict_anno_left') or '无')),
        ('指标口径小字已离开正文', (m.get('kpiNote') or {}).get('len', 1) == 0 and (m.get('kpiNote') or {}).get('display') == 'none',
         'len=%s display=%s' % ((m.get('kpiNote') or {}).get('len'), (m.get('kpiNote') or {}).get('display'))),
        ('打印副本 #printNotes 有内容', (m.get('printNotes_len') or 0) > 100, '%s 字符' % m.get('printNotes_len')),
    ]
    bad = 0
    for name, ok, detail in checks:
        bad += 0 if ok else 1
        print('%s %-26s %s' % ('✅' if ok else '❌', name, detail))
    print('-' * 92)
    print('结论 %d 字 / 说明 %d 字 / 口径 %d 字 / 模块 %d 个'
          % (m.get('verdict_len', 0), m.get('notice_len', 0), m.get('kpi_note_len', 0), m.get('mods', 0)))
    print('结论开头：%s' % m.get('verdict_head', ''))
    print('异常项：%d / %d' % (bad, len(checks)))
    print(json.dumps(m, ensure_ascii=False, indent=1)[:2600])

    # ---- 截图：弹窗打开 / 关闭（服务要先关掉，所以放最后） ----
    if not noshot:
        mk('shot_open.html', '1')
        mk('shot_closed.html', '0')
        for tag, f in [('open', 'shot_open.html'), ('closed', 'shot_closed.html')]:
            out = '/tmp/rpt_notes_%s.png' % tag
            if os.path.exists(out):
                os.remove(out)
            subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                            '--window-size=' + (win if win != '1500,1600' else '1500,1500'), '--virtual-time-budget=25000',
                            '--screenshot=' + out,
                            'http://127.0.0.1:%d/%s?code=%s' % (port, f, code)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print('截图：/tmp/rpt_notes_open.png , /tmp/rpt_notes_closed.png')
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
