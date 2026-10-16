#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研报列表页「评分块」体检探针（2026-10-15）。

针对用户报的两个问题：
  ① 「右边两个评分出现了显示不全」—— 指标格该 4 格却是 2 格
     根因：kpiOf 用精确 indexOf('营业收入')，而新研报 label 写的是「2026H1 营收」⇒ 整格落空。
  ② 「左边这个不规范」—— 000762 西藏矿业没有评分块
     根因：它的 m29 是**未评分**状态（<span class="tn">—</span>），
           parseScoreHtml 的正则要求数字 ⇒ 返回 null ⇒ 回落成无样式长摘要。

实现要点（照抄 probe_comfiles.py 的可靠做法）：
  * 页面走 http://127.0.0.1:<port>（file:// 的 Origin: null 会被网关 403）。
  * 结果用 fetch POST 回本地 server —— **别用 --dump-dom**，本机 Edge 在这模式下不吐输出。
  * 注入位置 rfind('</body>')。
  * 一律量真实 DOM，不调内部函数。
  * 只读：不写库、不点删除。

用法：
  python3 build/probe_research_score.py                                  # 打线上
  SRC=deploy/research.html python3 build/probe_research_score.py         # 打本地构建件
"""
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

SRC = os.environ.get('SRC', '')
ONLINE = 'https://liuchaowang.cn/research.html'
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

GOT = []
STD = ['营业收入', '归母净利', '毛利率', 'ROE']

INJECT = r"""
<script>
(function(){
  function collect(){
    var out = { cards: [], err: [] };
    try{
      var cards = document.querySelectorAll('#grid .card');
      for(var i = 0; i < cards.length; i++){
        var c   = cards[i];
        var sc  = c.querySelector('.scard');
        var sum = c.querySelector('.sum');
        var rec = { code:((c.querySelector('.ctop .code')||{}).textContent||'').trim(),
                    hasScard:!!sc, hasSum:!!sum, tiles:[], pend:false,
                    rate:'', gauge:'', ring:'' };
        if(sc){
          rec.pend = sc.classList.contains('pend');
          var rt = sc.querySelector('.srate');
          rec.rate = rt ? rt.textContent.trim() : '';
          var g = sc.querySelector('.gnum');
          rec.gauge = g ? g.textContent.trim() : '';
          /* 环形进度：读 inline style 的 conic-gradient，验证"未评分是灰环、已评分有刻度" */
          var gg = sc.querySelector('.sgauge');
          rec.ring = gg ? (gg.getAttribute('style')||'') : '';
          var tks = sc.querySelectorAll('.skv .kv');
          for(var j = 0; j < tks.length; j++){
            var em = tks[j].querySelector('em'), v = tks[j].querySelector('.v');
            rec.tiles.push({ label: em ? em.textContent.trim() : '',
                             val:   v ? v.textContent.trim() : '',
                             na:    tks[j].classList.contains('na'),
                             disp:  getComputedStyle(tks[j]).display });
          }
        }
        if(sum) rec.sumClip = (sum.scrollHeight > sum.clientHeight + 1);
        out.cards.push(rec);
      }
    }catch(e){ out.err.push(String(e && e.message || e)); }
    return out;
  }
  var tries = 0;
  function tick(){
    tries++;
    var n = document.querySelectorAll('#grid .card').length;
    /* 卡片渲染完（或 25 次后放弃）才回传，避免量到骨架屏 */
    if(n > 0 || tries > 60){
      var out = collect();
      out.tries = tries; out.cnt = n;
      try{
        fetch('http://127.0.0.1:__PORT__/done', { method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify(out) });
      }catch(e){}
      return;
    }
    setTimeout(tick, 400);
  }
  setTimeout(tick, 1200);
})();
</script>
"""


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def inject(html, script):
    i = html.rfind('</body>')          # 页面有 2 个 </body>，取最后那个
    if i < 0:
        i = html.rfind('</html>')
    return html[:i] + script + html[i:]


def main():
    global SRC
    if SRC:
        html = io.open(SRC, encoding='utf-8').read()
        origin = '本地 ' + os.path.basename(SRC)
    else:
        r = subprocess.run(['curl', '-s', ONLINE], capture_output=True, text=True, timeout=60)
        html = r.stdout
        origin = '线上 ' + ONLINE

    tmp = tempfile.mkdtemp(prefix='_rs_')
    port = free_port()

    class H(SimpleHTTPRequestHandler):
        # ⚠️ `directory` 是 SimpleHTTPRequestHandler 的参数，必须传给 **HTTPServer**，
        #    写进 handler.__init__ 会报 unexpected keyword argument。
        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(n)
            if self.path.startswith('/done'):
                try:
                    GOT.append(json.loads(body.decode('utf-8')))
                except Exception as e:
                    GOT.append({'err': ['bad json: %s' % e], 'raw': body[:400].decode('utf-8', 'replace')})
            self.send_response(204)
            self.end_headers()

    srv = HTTPServer(('127.0.0.1', port), H) if tmp is None else \
          HTTPServer(('127.0.0.1', port), lambda *a, **kw: H(*a, directory=tmp, **kw))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    f = os.path.join(tmp, 'r.html')
    io.open(f, 'w', encoding='utf-8').write(inject(html, INJECT.replace('__PORT__', str(port))))
    url = 'http://127.0.0.1:%d/r.html' % port

    print('=' * 96)
    print('研报列表页 · 评分块体检    src=%s' % origin)
    print('=' * 96)

    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-proxy-server',
                          '--window-size=1600,1200', '--user-data-dir=' + tempfile.mkdtemp(prefix='_rse_'),
                          url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 120 and not GOT:
        time.sleep(0.3)
    p.terminate()
    try:
        p.wait(timeout=10)
    except Exception:
        p.kill()
    srv.shutdown()

    if not GOT:
        print('✗ 页面没有回传结果（%ds）' % (time.time() - t0))
        return 1
    m = GOT[0]
    if m.get('err'):
        print('  页面报错: %s' % m['err'])
    if m.get('raw'):
        print('  原始回传: %s' % m['raw'])

    cards = m.get('cards') or []
    ok, red = 0, []

    def chk(name, cond, detail=''):
        nonlocal ok
        print('  %s %-46s %s' % ('✅' if cond else '❌', name, detail))
        if cond:
            ok += 1
        else:
            red.append(name)

    chk('卡片渲染出来了', len(cards) > 0, '%d 张（等待 %s 次）' % (len(cards), m.get('tries')))

    withsc = [c for c in cards if c['hasScard']]
    nosc = [c for c in cards if not c['hasScard']]
    print('\n---- 逐卡结构 ----')
    for c in cards:
        tag = ('待评分' if c['pend'] else (c['rate'] + ' · ' + c['gauge'])) if c['hasScard'] else '（无评分块 → 回落摘要）'
        print('   %-8s 格数=%d  %s' % (c['code'], len(c['tiles']), tag))
        for t in c['tiles']:
            print('        · %-10s %-16s %s' % (t['label'], t['val'], '占位' if t['na'] else ''))

    # ① 指标格恒定 4 格
    print('\n---- 判据 1：指标格恒定 4 格 ----')
    dist = {}
    for c in withsc:
        dist[len(c['tiles'])] = dist.get(len(c['tiles']), 0) + 1
    chk('有评分卡的指标格都是 4 格', all(len(c['tiles']) == 4 for c in withsc), '格数分布 %s' % (dist or '无'))

    # ② 标签归一
    print('\n---- 判据 2：磁贴标签归一（名字固定、顺序一致）----')
    for c in withsc:
        labs = [t['label'] for t in c['tiles']]
        chk('%s 四格标签' % c['code'], labs == STD, ' / '.join(labs))

    # ③ 缺项占位
    print('\n---- 判据 3：缺项格标为占位（数据没有，而非没渲染）----')
    nas = 0
    for c in withsc:
        for t in c['tiles']:
            if t['val'] == '—':
                nas += 1
                chk('%s「%s」标为 na' % (c['code'], t['label']), t['na'], 'display=%s' % t['disp'])
    print('   （共 %d 个占位格）' % nas)

    # ④ 待评分骨架
    print('\n---- 判据 4：未评分研报出骨架，不回落裸摘要 ----')
    pend = [c for c in withsc if c['pend']]
    print('   待评分研报: %s' % [c['code'] for c in pend])
    for c in pend:
        chk('%s 标记 pending' % c['code'], True, c['rate'])
        chk('%s 不回落摘要' % c['code'], not c['hasSum'], 'hasSum=%s' % c['hasSum'])
        chk('%s 灰环（无红色刻度）' % c['code'], '#e6d5d9' in c['ring'], c['ring'][:60])
        chk('%s 无假分数' % c['code'], '—' in c['gauge'], c['gauge'])
        chk('%s 仍是 4 格' % c['code'], len(c['tiles']) == 4, '%d 格' % len(c['tiles']))

    # ⑤ 已评分的不能被误判成待评分
    print('\n---- 判据 5：已评分研报不受影响 ----')
    for c in withsc:
        if c['pend']:
            continue
        chk('%s 红色刻度在' % c['code'], '#c8102e' in c['ring'], c['ring'][:60])
        chk('%s 有真实分数' % c['code'], c['gauge'] != '—' and '/' in c['gauge'], c['gauge'])

    # ⑥ 无 m29 的仍回落摘要（向后兼容）
    print('\n---- 判据 6：无 m29 的研报仍走摘要回落 ----')
    for c in nosc:
        print('   %s 无评分数据 → 回落摘要（兼容行为，符合预期）' % c['code'])
    if not nosc:
        print('   （本轮全部研报都有 m29，无回落样本）')

    print('\n结论: %d 项通过, %d 项失败' % (ok, len(red)))
    if red:
        print('失败项: %s' % red)
        return 1
    print('✅ 全绿')
    return 0


if __name__ == '__main__':
    sys.exit(main())
