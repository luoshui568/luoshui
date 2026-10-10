# -*- coding: utf-8 -*-
"""「💾 提交到数据库」按钮 —— 全链端到端验证（**线上零写入**）

────────────────────────────────────────────────────────────────────────
链路：改分 → 按钮出现 → 点它 → scCommit 校验/拼 HTML → Rpt.commitScore（RGATE 密码门）
      → Rpt.patch('wb_report_mods', '?id=eq.<id>', {...})
`_sc_test.py` 只抽了 scoreLive 那一段 JS 来跑，够不着 Rpt / RGATE / 真壳的启动流程，
所以这里用**完整的 deploy/report.html**（本地 http 托管、数据照旧从线上库拉）来跑一遍。

【怎么做到「真跑但不写库」】
  · 把 `Rpt.patch` 换成桩：记下 (table, query, body) 后直接 resolve —— 传输层被截断；
  · 密码门走**票据直通**那条路（`rTickIssue('commitScore')`，等价于用户刚输过密码、
    15/30 分钟内的免重复输入），既不弹框也不需要真密码；
  · 跑完再回读线上那一行 —— 必须逐字节不变，这才证明「桩真的拦住了」。

用法：python _btn_e2e.py 002408
"""
import base64
import functools
import http.server
import io
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import _score_patch as SP                                          # noqa: E402
from _apply_score import req, NO                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(os.path.dirname(HERE), 'deploy')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 8901
WIN = '1440,1800'

DRIVER = r"""
<script>
(function(){
  var OUT = {errors: []};
  var card = null, btn = null, cap = [], rawPatch = null;
  function b64(str){
    var bytes = new TextEncoder().encode(str), bin = '';
    for(var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }
  /* 每个阶段都回写一次 —— 挂住了也能看到卡在哪一步（第一次就是「什么都不输出」查不出原因） */
  function finish(){
    var pre = document.getElementById('btn-e2e-out');
    if(!pre){
      pre = document.createElement('pre');
      pre.id = 'btn-e2e-out';
      document.body.appendChild(pre);
    }
    pre.textContent = JSON.stringify(OUT);
  }
  OUT.step = 'started';
  finish();
  var tries = 0;
  /* ★ 全程只走 DOM：`St.mods[i]` 是**库记录**（只有 id/no/title/html），
     `cur/bases/items/btnSave` 挂在 scWire 新建的**运行时对象**上且没外露 ——
     驱动没必要去碰它。按钮、分数框、条宽都能从 DOM 读到，落库原文从库里那份取。 */
  function wait(){
    tries++;
    OUT.tries = tries;
    OUT.hasSt = !!window.St;
    OUT.nMods = (window.St && window.St.mods) ? window.St.mods.length : -1;
    var c = document.querySelector('[data-mod="' + (window.St && window.St.code) + '_m29"]');
    if(!c){
      var cards = document.querySelectorAll('.card[data-mod]');
      for(var k = 0; k < cards.length; k++){
        var h2 = cards[k].querySelector('h2 .no');
        if(h2 && String(h2.textContent).trim() === '29'){ c = cards[k]; break; }
      }
    }
    if(!(window.St && window.St.mods && window.St.mods.length && c)){
      if(tries > 250){ OUT.errors.push('未等到评分卡'); finish(); return; }
      finish();
      setTimeout(wait, 40);
      return;
    }
    OUT.step = 'ready';
    finish();
    run(c);
  }
  function run(c){
    try{
      OUT.step = 'run';
      card = c;
      OUT.modId = card.getAttribute('data-mod');
      OUT.cardNo = (card.querySelector('h2 .no') || {}).textContent;
      OUT.wired = card.querySelector('.criteria').getAttribute('data-sc-wired');
      OUT.lines = card.querySelectorAll('.sc-line').length;
      btn = card.querySelector('.lv-save');
      OUT.btnExists = !!btn;
      OUT.btnHiddenInit = btn ? (btn.style.display === 'none') : null;
      OUT.gateWired = !!(window.Rpt && Rpt.commitScore && Rpt.commitScore.__gated);
      OUT.gateAct = (window.Rpt && Rpt.commitScore) ? Rpt.commitScore.__act : null;
      OUT.resetHiddenInit = (function(){
        var b = card.querySelector('.lv-reset'); return b ? (b.style.display === 'none') : null;
      })();
      OUT.baseScores = [];
      var ins = card.querySelectorAll('.sc-inp');
      for(var i = 0; i < ins.length; i++) OUT.baseScores.push(ins[i].value);

      /* —— 探一探 St.mods 里的记录长什么样（scCommit 报「拿不到模块原文」时必须能定位）—— */
      OUT.stCode = window.St.code;
      OUT.stModsN = window.St.mods.length;
      var rec = null, withHtml = 0, keysOf = null, ids = [];
      for(var j = 0; j < window.St.mods.length; j++){
        var r0 = window.St.mods[j];
        if(String(r0.no) === '29'){ rec = r0; }
        if(typeof r0.html === 'string' && r0.html.length > 0) withHtml++;
        if(ids.length < 4) ids.push(String(r0.id));
      }
      OUT.withHtml = withHtml;
      OUT.sampleIds = ids.join(' | ');
      OUT.modIdFromCard = card.getAttribute('data-mod');
      /* ★ scWire 里是 `var card = crit.parentNode;` —— 真壳里 .criteria 外面还包了一层，
         取 parentNode 会拿不到 data-mod ⇒ mod.html 为空。这里把两层都记下来。 */
      var cr = card.querySelector('.criteria');
      OUT.critParentTag = cr ? cr.parentNode.tagName : null;
      OUT.critParentClass = cr ? String(cr.parentNode.className || '').slice(0, 60) : null;
      OUT.critParentDataMod = cr ? cr.parentNode.getAttribute('data-mod') : null;
      OUT.closestCardDataMod = cr ? (function(){
        var n = cr; while(n && n !== document.body){
          if(n.getAttribute && n.getAttribute('data-mod')) return n.getAttribute('data-mod');
          n = n.parentNode;
        }
        return null;
      })() : null;
      OUT.critParentChain = cr ? (function(){
        var n = cr, out = [], k = 0;
        while(n && k < 4){ out.push(n.tagName + '.' + String(n.className || '').split(' ')[0]); n = n.parentNode; k++; }
        return out.join(' < ');
      })() : null;
      if(rec){
        try{ keysOf = Object.keys(rec); }catch(e){ keysOf = null; }
        OUT.recKeys = keysOf ? keysOf.join(',') : null;
        OUT.recId = String(rec.id);
        OUT.recHtmlType = typeof rec.html;
        OUT.recHtmlLen = (typeof rec.html === 'string') ? rec.html.length : -1;
      } else {
        OUT.recKeys = '(St.mods 里没有 no=29 的记录)';
      }
      /* 有没有别的键装着正文？ */
      try{
        var k2 = keysOf || [];
        for(var y = 0; y < k2.length; y++){
          var v = rec[k2[y]];
          if(typeof v === 'string' && v.length > 500){ OUT['big_' + k2[y]] = v.length; }
        }
      }catch(e){}

      /* 改第 1 项，保证与当前值不同（相同的话 scCommit 会走「无需提交」直接早退） */
      var inp = ins[0];
      var old = parseInt(inp.value, 10);
      var tv = (old === 10 ? 4 : 10);
      OUT.editFrom = old; OUT.editTo = tv;
      inp.value = String(tv);
      inp.dispatchEvent(new Event('input', {bubbles: true}));
      inp.dispatchEvent(new Event('change', {bubbles: true}));
      OUT.btnShownAfterEdit = btn ? (btn.style.display !== 'none') : null;
      OUT.dirtyChipAfterEdit = (function(){
        var b = card.querySelector('.lv-dirty'); return b ? (b.style.display !== 'none') : null;
      })();
      OUT.numAfterEdit = (card.querySelector('.gauge-num') || {}).textContent;
      finish();

      /* 截断传输层：桩掉 Rpt.patch */
      rawPatch = Rpt.patch;
      Rpt.patch = function(tbl, q, body, label){
        cap.push({table: tbl, query: q, body: body, label: label});
        return Promise.resolve([]);
      };
      /* 诊断钩子：点击后走到哪一步（toast 文案 / commitScore 是否被调 / 页面报错） */
      var rawToast = window.toast;
      window.toast = function(m, k){
        OUT.toasts = (OUT.toasts || []).concat([String(m).slice(0, 70)]);
        return rawToast ? rawToast.apply(null, arguments) : undefined;
      };
      var rawCS = Rpt.commitScore;
      Rpt.commitScore = function(){
        OUT.csCalled = (OUT.csCalled || 0) + 1;
        OUT.csArgs = [].slice.call(arguments).map(function(x){
          return (typeof x === 'string') ? x.slice(0, 24) : (x && x.__rpassOk ? 'RPASS_OK' : typeof x);
        });
        return rawCS.apply(Rpt, arguments);
      };
      window.addEventListener('error', function(ev){
        OUT.winErrors = (OUT.winErrors || []).concat([String(ev.message).slice(0, 120)]);
      });
      /* 票据直通密码门（等价于「刚输过密码」） */
      rTickIssue('commitScore');
      OUT.tick = rTickHas('commitScore');
      OUT.step = 'click';
      finish();
      btn.click();

      setTimeout(function(){
        OUT.step = 'afterClick';
        OUT.patchCalls = cap.length;
        if(cap.length){
          var c2 = cap[0];
          OUT.p_table = c2.table;
          OUT.p_query = c2.query;
          OUT.p_no = c2.body ? c2.body.no : null;
          OUT.p_report = c2.body ? c2.body.report_id : null;
          OUT.p_code = c2.body ? c2.body.code : null;
          OUT.p_seq = c2.body ? c2.body.seq : null;
          OUT.p_title = c2.body ? c2.body.title : null;
          OUT.p_len = (c2.body && c2.body.html) ? c2.body.html.length : -1;
          OUT.p_kv = (c2.body && c2.body.html) ? (c2.body.html.split('class="kv"').length - 1) : -1;
          var m = /<span class="tn">([^<]*)</.exec((c2.body && c2.body.html) || '');
          OUT.p_tn = m ? m[1] : null;
          var vals = (c2.body && c2.body.html || '').match(/<div class="sc-val">([^<]*)<\/div>/g) || [];
          OUT.p_val0 = vals.length ? vals[0].replace(/<[^>]+>/g, '') : null;
          OUT.p_html_b64 = b64(c2.body.html);
        }
        Rpt.patch = rawPatch;
        finish();
      }, 600);
    }catch(e){
      OUT.errors.push('run: ' + (e && e.message));
      OUT.step = 'runError';
      finish();
    }
  }
  wait();
})();
</script>
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def dump(url, budget=60000):
    """★ 每次用**全新 profile**：共用 profile 时上一次跑留在 localStorage 里的
    「本地调整记录」（wb.sc.<code>.m29）会被这次加载恢复出来 ⇒ 一进来就是 dirty、
    按钮初始可见、初评分数也被顶掉，断言全乱（第一次跑就踩了）。"""
    out = os.path.join(tempfile.gettempdir(), '_btn_out.html')
    prof = os.path.join(tempfile.gettempdir(), '_btn_prof_%d_%d' % (os.getpid(), time.time_ns()))
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--hide-scrollbars', '--force-device-scale-factor=1',
           '--window-size=' + WIN, '--virtual-time-budget=%d' % budget,
           '--user-data-dir=' + prof, '--dump-dom', url]
    try:
        with open(out, 'wb') as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL, timeout=300)
        return io.open(out, 'rb').read().decode('utf-8', 'replace')
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def serve_dir(tmp):
    socketserver.TCPServer.allow_reuse_address = True
    h = functools.partial(Quiet, directory=tmp)
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def one(code, base, quiet=False):
    """跑一家报告的全链验证。返回失败项列表（空 = 全绿）。"""
    bad = []

    def chk(okc, msg):
        if (not quiet) or (not okc):
            print('  %s %s' % ('✅' if okc else '❌', msg))
        if not okc:
            bad.append(msg)

    live0 = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=id,title,html' % (code, NO))[0]
    h0 = live0.get('html') or ''
    dom = dump(base + '/report.html?code=' + code)

    m = re.search(r'<pre id="btn-e2e-out">(.*?)</pre>', dom, re.S)
    if not m:
        print('✗ 没拿到探针输出（页面没跑起来？）')
        t = re.search(r'<title>(.*?)</title>', dom, re.S)
        print('  title = %s' % (t.group(1).strip() if t else '(无)'))
        print('  dom %d 字节' % len(dom))
        return 1
    raw = m.group(1)
    raw = raw.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    R = json.loads(raw)
    if not quiet:
        print('  （驱动诊断：step=%s tries=%s nMods=%s）'
              % (R.get('step'), R.get('tries'), R.get('nMods')))
    if R.get('patchCalls') in (0, None):
        print('  （诊断明细）tick=%s csCalled=%s csArgs=%s numAfterEdit=%s'
              % (R.get('tick'), R.get('csCalled'), R.get('csArgs'), R.get('numAfterEdit')))
        print('  （toast）%s' % (R.get('toasts') or '无'))
        print('  （页面报错）%s' % (R.get('winErrors') or '无'))
        print('  （St.code=%s ｜ St.mods %s 条 ｜ 带 html 的 %s 条 ｜ 样例 id：%s）'
              % (R.get('stCode'), R.get('stModsN'), R.get('withHtml'), R.get('sampleIds')))
        print('  （卡片 data-mod=%s ｜ St.mods 里 no=29 的 id=%s）'
              % (R.get('modIdFromCard'), R.get('recId')))
        print('  （no=29 记录的键：%s ｜ html 类型=%s 长度=%s）'
              % (R.get('recKeys'), R.get('recHtmlType'), R.get('recHtmlLen')))
        bigs = {k: v for k, v in R.items() if k.startswith('big_')}
        print('  （记录里的长字符串字段：%s）' % (bigs or '无'))
        print('  （.criteria 的祖先链：%s）' % R.get('critParentChain'))
        print('  （parentNode 的 data-mod = %r ｜ 向上找到卡片 data-mod = %r）'
              % (R.get('critParentDataMod'), R.get('closestCardDataMod')))
    if R.get('errors'):
        for e in R['errors']:
            print('  ⚠ 驱动报错：%s' % e)

    chk(R.get('cardNo') == '29' and R.get('wired') == '1' and R.get('lines') == 10,
        '页面里找到了槽 29 的评分卡并已接管（id=%s · 十行）' % R.get('modId'))
    chk(R.get('baseScores') == [str(x) for x in SP.parse_scores(h0)[0]],
        '页面初评分数与库里一致（%s）' % R.get('baseScores'))
    chk(R.get('btnExists'), '「💾 提交到数据库」按钮存在')
    chk(R.get('btnHiddenInit') is True and R.get('resetHiddenInit') is True,
        '未改动时按钮是隐藏的（没得提交就别摆出来）')
    chk(R.get('gateWired') is True and R.get('gateAct') == '提交',
        '该按钮已挂密码门（Rpt.commitScore.__gated=True / act=提交）')
    chk(R.get('btnShownAfterEdit') is True and R.get('dirtyChipAfterEdit') is True,
        '改分后按钮出现 + 「已调整」chip 亮起（第 1 项 %s → %s）'
        % (R.get('editFrom'), R.get('editTo')))
    chk(R.get('patchCalls') == 1, '点一次按钮 ⇒ 恰好发出 1 次写请求（实测 %s）' % R.get('patchCalls'))
    chk(R.get('csCalled') == 1, '走的是 Rpt.commitScore（被调 %s 次）' % R.get('csCalled'))

    chk(R.get('p_table') == 'wb_report_mods', '写的是 wb_report_mods（%s）' % R.get('p_table'))
    chk(R.get('p_query') == '?id=eq.' + str(R.get('modId')),
        '按主键精确改一行（%s）' % R.get('p_query'))
    chk(str(R.get('p_no')) == NO and R.get('p_report') == code,
        'no / report_id 原样回填（no=%s report_id=%s）' % (R.get('p_no'), R.get('p_report')))
    chk(R.get('p_kv') == h0.count('class="kv"'),
        'KPI 格数原样（%s，原文 %s）' % (R.get('p_kv'), h0.count('class="kv"')))

    # ★ 关键：页面交出去的 HTML，必须与后端脚本 apply_scores 的产出逐字节相同
    p_html = None
    if R.get('p_html_b64'):
        try:
            p_html = base64.b64decode(R['p_html_b64']).decode('utf-8')
        except Exception as e:
            print('      ✗ base64 解不开：%s' % e)
    base_scores, src, warn = SP.parse_scores(h0)
    want_scores = list(base_scores)
    want_scores[0] = int(R.get('editTo'))
    want, meta = SP.apply_scores(h0, want_scores)
    if p_html:
        chk(p_html == want,
            '★ 页面按钮交出的 HTML == 后端落库脚本的产出（%d vs %d 字节 · 总分 %s）'
            % (len(p_html), len(want), meta['total']))
        if p_html != want:
            at = SP.first_diff(want, p_html)
            print('        后端 …%s…' % want[max(0, at - 60):at + 60].replace('\n', '⏎'))
            print('        页面 …%s…' % p_html[max(0, at - 60):at + 60].replace('\n', '⏎'))
    chk(R.get('p_tn') == SP.f1(meta['total']),
        '底部总分 = %s' % R.get('p_tn'))
    chk(R.get('p_val0') == str(want_scores[0]), '第 1 项分数框 = %s' % R.get('p_val0'))

    # ★ 「桩真的拦住了」的证据：线上那一行必须一个字节没变
    live1 = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=id,title,html' % (code, NO))[0]
    chk((live1.get('html') or '') == h0,
        '★ 线上那一行逐字节未变（桩拦住了，没真写库；%d 字节）' % len(h0))

    return bad


def main(argv):
    codes = [a for a in argv if a.isdigit() and len(a) == 6]
    if not codes:
        codes = ['600456', '600459', '002237', '000731', '000830',
                 '603977', '601118', '601958', '603599', '002408']
    tmp = tempfile.mkdtemp(prefix='_btn_e2e_')
    src = io.open(os.path.join(DEPLOY, 'report.html'), encoding='utf-8').read()
    # 注入点必须用**最后一个** `</body>`：内联 ECharts 库里也有一处 `'<body style=...'`
    # 字面量（偏移约 84.7 万），按第一个注入会把驱动器塞进库代码里 —— 踩过。
    AT = src.rfind('</body>')
    assert AT > 0, 'report.html 里找不到 </body>'
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(
        src[:AT] + DRIVER + '\n' + src[AT:])
    httpd = serve_dir(tmp)
    base = 'http://127.0.0.1:%d' % PORT
    print('「💾 提交到数据库」全链验证 ｜ %d 家 ｜ 全程桩掉传输层，线上零写入' % len(codes))
    print('链路：改分 → 按钮出现 → 点击 → scCommit 校验/拼 HTML → RGATE 密码门'
          ' → Rpt.commitScore → Rpt.patch\n')
    res = {}
    try:
        for code in codes:
            b = one(code, base, quiet=True)
            res[code] = b
            print('  %s %s（失败 %d 项）'
                  % ('✅' if not b else '❌', code, len(b)))
            for x in b:
                print('      ✗ %s' % x)
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    nbad = [c for c in codes if res.get(c)]
    print('\n合计：%d 家通过 / %d 家失败 %s'
          % (len(codes) - len(nbad), len(nbad),
             '✅ 全部通过' if not nbad else '❌ ' + ' '.join(nbad)))
    return 1 if nbad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
