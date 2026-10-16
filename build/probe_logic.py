# -*- coding: utf-8 -*-
"""研报页「解读块（.logic）默认隐藏 + 点击就地展开/收起」端到端探针（只读）。

背景：用户截图（齐翔腾达 m12「剪刀差解读」）先要求「隐藏 + 点击弹窗」，
      随即改口「**不要弹窗**，改成点击展开和隐藏，默认全部隐藏」。
      页面侧实现：折叠/展开**完全由 CSS 负责**（report_theme.css 的 .logic 段 ——
      `.lv{display:none}`，加 `.on` 类即 display:block），模板里只有一支事件委托
      切类（`logicToggle`）。全站 389 个解读块，**库里一个字都没改**
      ⇒ 必须证明「隐藏 ≠ 丢内容」，且展开后正文真的落在标题下方、不被裁。

断言（屏幕模式，全程真实 `.click()`）：
  1. 默认态：页面上**全部** `.lv` 都是 display:none（真·默认全部隐藏）
  2. 隐藏时 `.lv` 仍在 DOM、非空，且每个块 `.lt`/`.lv` 各 1 个（结构没被破坏）
  3. 折叠条高度小（≤70px）、标题不横向溢出、右侧「展开」胶囊可见
  4. DOM 里的解读块数量 = 库里该模块 `class="logic"` 的个数
  5. 页面里**不存在**解读弹窗 `#rptLMask`（已改为就地展开，弹窗必须消失）
  6. 点第 k 条 → `.logic` 带 `on`；`.lv` display:block；正文可见且未被裁
  7. 正文**落在标题下方**（几何：lv.top ≥ lt.bottom）且不横向溢出
  8. 展开后的可见文本长度 = 隐藏时记录的文本长度（一字不少）
  9. 胶囊文案变成「收起」
 10. 再点一次 → 收起（`on` 消失、`.lv` 回到 display:none、折叠条恢复矮小）
 11. 两个块可以同时展开、且互不影响（关掉第 0 条时第 1 条仍开着）
打印模式（`--print`，把 @media print 换成 all 的副本）：
 12. `#rptLMask` 不存在；`.lv` 全部还原为 display:block、`.lt` 没被藏、正文未被裁、
     `::after` 胶囊隐藏、正文有实际高度、块数与库一致、没有残留的 `on` 态。
     —— PDF 点不动，只藏不还 = 直接把正文印丢。

用法：
  python3 build/probe_logic.py 002408 --mod=12            # 默认第 0 条
  python3 build/probe_logic.py 002408 --mod=12 --k=1
  RPT_SRC=/tmp/live.html python3 build/probe_logic.py 002408 --mod=12    # 验线上字节
  python3 build/probe_logic.py 002408 --mod=12 --print --noshot
"""
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, 'deploy', 'report.html')
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

INJECT = r"""
<script>
(function(){
  var MOD = "__MOD__", K = __K__, EXP = __EXPN__;
  var out = {steps: [], mod: MOD, k: K, expN: EXP};
  function log(s, v){ out.steps.push(s); out['v_' + s] = v; }
  function txt(el){ return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function disp(el){ return el ? getComputedStyle(el).display : '(无)'; }
  /* ⚠️ 判伪元素是否隐藏必须看 display，不能看 content：
     display:none 的伪元素，getComputedStyle(el,'::after').content 依然返回那句文案。 */
  function hint(el){
    if(!el) return '';
    if(getComputedStyle(el, '::after').display === 'none') return '(隐藏)';
    return getComputedStyle(el, '::after').content || '';
  }
  function go(){
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length) return setTimeout(go, 250);
    var card = document.getElementById('m' + MOD);
    if(!card){ out.err = '页面里没有模块 m' + MOD; return post(); }
    for(var i = 0; i < cards.length; i++) if(cards[i] !== card) cards[i].style.display = 'none';
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);

    var bs = card.querySelectorAll('.logic');
    if(!bs.length){ out.err = '该模块里没有 .logic 解读块'; return post(); }
    out.code = St.rep.code; out.name = St.rep.name; out.src = St.src;
    out.n = bs.length; out.modTitle = txt(card.querySelector('h2'));

    /* ---- 1/2 默认全部隐藏 + 内容仍在 DOM ---- */
    var all = document.querySelectorAll('#mods .logic');
    var hiddenAll = true, kept = 0, pairMismatch = 0;
    for(var a = 0; a < all.length; a++){
      var lv = all[a].querySelector('.lv'), lt = all[a].querySelector('.lt');
      if(!lv || !lt) continue;
      if(disp(lv) !== 'none') hiddenAll = false;
      if(txt(lv).length > 0) kept++;
      if(all[a].querySelectorAll('.lt').length !== 1 ||
         all[a].querySelectorAll('.lv').length !== 1) pairMismatch++;
    }
    out.allBlocks = all.length; out.allKept = kept;
    log('页面上全部 ' + all.length + ' 个 .lv 都默认隐藏', hiddenAll);
    log('隐藏时内容仍在 DOM（' + kept + ' 个非空）', kept === all.length);
    log('每个块的 .lt/.lv 各 1 个（结构未破）', pairMismatch === 0);

    /* ---- 3 折叠条形态 ---- */
    var heights = [], overflow = [];
    for(var b = 0; b < bs.length; b++){
      var lt0 = bs[b].querySelector('.lt');
      heights.push(+bs[b].getBoundingClientRect().height.toFixed(1));
      if(lt0 && lt0.scrollWidth > lt0.clientWidth + 1) overflow.push(b);
    }
    var hmax = Math.max.apply(null, heights);
    out.heights = heights; out.hmax = hmax; out.overflow = overflow;
    log('折叠条都很矮（最高 ' + hmax + 'px ≤ 70）', hmax <= 70);
    log('标题没有横向溢出（越界 ' + overflow.length + ' 个）', overflow.length === 0);
    out.hint0 = hint(bs[0]);
    log('右侧胶囊写着「展开」（' + out.hint0 + '）', String(out.hint0).indexOf('展开') >= 0);

    /* ---- 4 与库对比 ---- */
    log('解读块个数与库里一致（DOM ' + bs.length + ' / 库 ' + EXP + '）', bs.length === EXP);
    /* ---- 5 弹窗必须已经拆掉 ---- */
    log('页面里没有解读弹窗 #rptLMask', !document.getElementById('rptLMask'));
    log('页面里没有 .rpt-lbox / .rpt-lmask 残留',
        document.querySelectorAll('.rpt-lbox,.rpt-lmask').length === 0);

    /* ---- 6 点第 K 条 → 就地展开 ---- */
    var kk = Math.min(K, bs.length - 1);
    var target = bs[kk];
    var lt = target.querySelector('.lt'), lv = target.querySelector('.lv');
    var wantLen = txt(lv).length;
    out.clicked = {k: kk, title: txt(lt), bodyLen: wantLen};
    target.click();
    log('点击后 .logic 带上 on', target.className.indexOf('on') >= 0);
    log('.lv 就地展开（display=' + disp(lv) + '）', disp(lv) === 'block');
    log('展开后正文未被裁（高 ' + lv.clientHeight + ' / 内容 ' + lv.scrollHeight + '）',
        (lv.scrollHeight - lv.clientHeight) <= 1);
    log('展开后的可见文本一字不少（' + txt(lv).length + ' 字）',
        txt(lv).length === wantLen && wantLen > 0);
    var rt = lt.getBoundingClientRect(), rv = lv.getBoundingClientRect();
    out.geom = {ltBottom: +rt.bottom.toFixed(1), lvTop: +rv.top.toFixed(1),
                lvW: +rv.width.toFixed(1), lvH: +rv.height.toFixed(1)};
    log('正文落在标题下方（lv.top ' + out.geom.lvTop + ' ≥ lt.bottom ' + out.geom.ltBottom + '）',
        rv.top >= rt.bottom - 1);
    log('展开后正文有实际高度（' + out.geom.lvH + 'px）', rv.height > 0);
    log('展开后正文不横向溢出', lv.scrollWidth <= lv.clientWidth + 1);
    out.hint1 = hint(target);
    log('胶囊变成「收起」（' + out.hint1 + '）', String(out.hint1).indexOf('收起') >= 0);

    /* ---- 11 多块可同时展开、互不影响 ---- */
    var other = bs[kk === 0 ? Math.min(1, bs.length - 1) : 0];
    if(other !== target){
      other.click();
      log('两条可以同时展开', target.className.indexOf('on') >= 0 &&
                              other.className.indexOf('on') >= 0);
      other.click();
      log('关掉另一条不影响本条', target.className.indexOf('on') >= 0 &&
                                  other.className.indexOf('on') < 0);
    } else {
      log('该模块只有 1 条解读，跳过「双开」检查', null);
    }

    /* ---- 10 再点一次收起 ---- */
    target.click();
    log('再点一次已收起（display=' + disp(lv) + '）', disp(lv) === 'none');
    log('收起后 on 类已移除', target.className.indexOf('on') < 0);
    log('收起后折叠条恢复矮小（' + target.getBoundingClientRect().height.toFixed(1) + 'px）',
        target.getBoundingClientRect().height <= 70);
    post();
  }
  function post(){
    try{ fetch('http://127.0.0.1:__PORT__/m', {method:'POST', body: JSON.stringify(out)}); }catch(e){}
  }
  setTimeout(go, 300);
})();
</script>
</body>
"""

INJECT_PRINT = r"""
<script>
(function(){
  var MOD = "__MOD__", K = __K__, EXP = __EXPN__;
  var out = {steps: [], mod: MOD, print: true};
  function log(s, v){ out.steps.push(s); out['v_' + s] = v; }
  function txt(el){ return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function go(){
    var cards = document.querySelectorAll('#mods > .card');
    if(!cards.length) return setTimeout(go, 250);
    var card = document.getElementById('m' + MOD);
    if(!card){ out.err = '页面里没有模块 m' + MOD; return post(); }
    for(var i = 0; i < cards.length; i++) if(cards[i] !== card) cards[i].style.display = 'none';
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);
    var bs = card.querySelectorAll('.logic');
    if(!bs.length){ out.err = '该模块里没有 .logic 解读块'; return post(); }
    out.code = St.rep.code; out.n = bs.length;
    log('解读块个数与库里一致（DOM ' + bs.length + ' / 库 ' + EXP + '）', bs.length === EXP);
    log('打印时没有解读弹窗 #rptLMask', !document.getElementById('rptLMask'));
    var shown = 0, none = 0, cut = 0, opened = 0;
    for(var b = 0; b < bs.length; b++){
      var lv = bs[b].querySelector('.lv'), lt = bs[b].querySelector('.lt');
      if(lv && getComputedStyle(lv).display !== 'none') shown++;
      if(lv && (lv.scrollHeight - lv.clientHeight) > 1) cut++;
      if(lt && getComputedStyle(lt).display === 'none') none++;
      if(bs[b].className.indexOf('on') >= 0) opened++;
    }
    out.print = {shown: shown, n: bs.length, cut: cut, titleHidden: none, opened: opened};
    log('打印时 ' + shown + '/' + bs.length + ' 条正文已全部还原为可见', shown === bs.length);
    log('打印时没有残留的 on 态（' + opened + ' 个）', opened === 0);
    log('打印时标题没有被藏起来（' + none + ' 个被藏）', none === 0);
    log('打印时正文没有被裁（' + cut + ' 条被裁）', cut === 0);
    var hd = getComputedStyle(bs[0], '::after').display;
    out.hintDisplay = hd;
    log('打印时「展开/收起」胶囊已隐藏（display=' + hd + '）', hd === 'none');
    var lv0 = bs[0].querySelector('.lv');
    out.lvH = lv0 ? +lv0.getBoundingClientRect().height.toFixed(1) : 0;
    log('打印态正文有实际高度（' + out.lvH + 'px）', out.lvH > 0);
    post();
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


def db_logic_count(code, mod):
    """库里该模块 `class="logic"` 的个数（只读；用于「DOM 与库一致」这条断言）。"""
    cfg = json.load(io.open(os.path.join(ROOT, 'build', 'cloud.json'), encoding='utf-8'))
    rest = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    hdr = {'Authorization': 'Bearer ' + cfg['key']}

    def get(p):
        r = urllib.request.Request(rest + p, headers=hdr)
        with urllib.request.urlopen(r, timeout=90) as resp:
            return json.loads(resp.read().decode('utf-8', 'replace'))

    rows = get('wb_report_mods?report_id=eq.%s&no=eq.%s&select=html' % (code, mod))
    if not rows:
        return -1
    return len(re.findall(r'class="logic"', rows[0].get('html') or ''))


def run(kind, code, mod, k, exp, win, tmp, port, html, shot):
    tpl = INJECT_PRINT if kind == 'print' else INJECT
    js = (tpl.replace('__PORT__', str(port))
             .replace('__MOD__', str(mod))
             .replace('__K__', str(k))
             .replace('__EXPN__', str(exp)))
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(inject(html, js))
    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)
    GOT.clear()
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                          '--hide-scrollbars', '--window-size=' + win,
                          '--virtual-time-budget=30000', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 90 and not GOT:
        time.sleep(0.2)
    try:
        p.kill()
    except Exception:
        pass
    m = GOT[0] if GOT else None
    if shot:
        if os.path.exists(shot):
            os.remove(shot)
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--hide-scrollbars', '--window-size=' + win,
                        '--virtual-time-budget=20000', '--screenshot=' + shot, url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return m


def report(kind, code, m, shot):
    if not m:
        print('✗ %s %s 未回传' % (kind, code)); return 1
    if m.get('err'):
        print('✗ %s %s %s' % (kind, code, m['err'])); return 1
    if kind == 'print':
        print('打印模式 · %s %s · 解读块 %d 个' % (code, m.get('code'), m.get('n') or 0))
        pr = m.get('print') or {}
        print('  还原可见 %s/%s · 正文被裁 %s · 标题被藏 %s · 残留 on 态 %s · 正文高 %spx'
              % (pr.get('shown'), pr.get('n'), pr.get('cut'), pr.get('titleHidden'),
                 pr.get('opened'), m.get('lvH')))
    else:
        print('屏幕模式 · %s %s · 模块 m%s「%s」 · 解读块 %d 个'
              % (code, m.get('code'), m.get('mod'), m.get('modTitle'), m.get('n') or 0))
        c = m.get('clicked') or {}
        print('  第 %s 条：标题「%s」 · 正文 %s 字' % (c.get('k'), c.get('title'), c.get('bodyLen')))
        g = m.get('geom') or {}
        print('  折叠条高度：%s（最高 %s）· 标题横向越界 %s 个'
              % (m.get('heights'), m.get('hmax'), len(m.get('overflow') or [])))
        print('  展开几何：正文顶 %s / 标题底 %s · 正文 %s×%s'
              % (g.get('lvTop'), g.get('ltBottom'), g.get('lvW'), g.get('lvH')))
        print('  胶囊文案：折叠=%s  展开=%s' % (m.get('hint0'), m.get('hint1')))
    print('-' * 104)
    bad = []
    for s in (m.get('steps') or []):
        v = m.get('v_' + s)
        mark = '·' if v is None else ('✓' if v else '✗')
        if v is False:
            bad.append(s)
        print('  %s %s' % (mark, s))
    if shot:
        print('截图：%s' % shot)
    if bad:
        print('✗ %d 项未通过：%s' % (len(bad), '；'.join(bad)))
        return 1
    print('✓ 全部断言通过')
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    code = args[0] if args else '002408'
    mod, k, win = '12', 0, '1500,1200'
    for a in sys.argv[1:]:
        if a.startswith('--mod='): mod = a[6:]
        if a.startswith('--k='): k = int(a[4:])
        if a.startswith('--w='): win = a[4:]
    noshot = '--noshot' in sys.argv
    want_print = '--print' in sys.argv or '--all' in sys.argv

    exp = db_logic_count(code, mod)
    if exp <= 0:
        print('✗ 库里 %s m%s 没有解读块（exp=%s）' % (code, mod, exp)); return 1

    html = io.open(SRC, encoding='utf-8').read()
    assert html.count('<script') == html.count('</script>'), 'script 标签不配对'
    print_html = html.replace('@media print', '@media all') if want_print else None
    tmp = tempfile.mkdtemp(prefix='_lgprobe_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print('=' * 104)
    print('解读块 默认隐藏 + 点击就地展开/收起 · 研报 %s · 模块 m%s · 第 %d 条 · 库里 %d 块 · %s · src=%s'
          % (code, mod, k, exp, win, os.path.basename(SRC)))
    print('=' * 104)
    rc = 0
    shot = None if noshot else '/tmp/lg_%s_m%s.png' % (code, mod)
    m = run('screen', code, mod, k, exp, win, tmp, port, html, shot)
    rc |= report('screen', code, m, shot)
    if want_print:
        print('-' * 104)
        m2 = run('print', code, mod, k, exp, win, tmp, port, print_html, None)
        rc |= report('print', code, m2, None)
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
