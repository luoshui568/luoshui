# -*- coding: utf-8 -*-
"""5 份研报 · 真机端到端验收探针（每份一次真实页面导航，数据取自**真云端数据库**）

为什么不用桩数据：
  单元级的「库↔seed 一致性」由 verify_report_db.py 负责；本探针只回答一个问题——
  **用户真的用浏览器打开 report.html?code=xxx 时，看到的是不是 23 个模块 + N 张图**。

每份研报断言（全部在真浏览器里、真网关拉数）：
  1. 页面零 JS 错误；St.src === 'cloud' 且 loadErr 为空（真从库里读到，不是内置副本）
  2. 研报代号/名称/标题正确；标题栏显示「N 个模块 · M 张图表」
  3. 模块 23 个、编号 1..23 齐、DOM 里 23 张卡片且 id = m1..m23
  4. KPI 8 项；目录条数与库一致；hero / 结论 / 页脚都有内容
  5. 图表：库内 M 张 ↔ 模块内 [data-chart] 图位 M 个 ↔ echarts 实例 M 个 ↔ canvas M 个
     （四个数字必须相等，且没有 .rpt-chartmiss 占位）；每个 canvas 尺寸 > 200×120
  6. option 里的 {{fn:}} 具名标记 0 处残留、函数已全部还原成真 function
  7. 模块正文没有 {{ / undefined / NaN / [object Object] 这类坏内容
  8. 顶栏出现研报切换下拉（5 份研报 → 5 个选项，当前项 selected 指向自己）

用法：python build/probe_reports_all_e2e.py [code ...]
"""
import html as _h
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DEPLOY = os.path.join(BASE, 'deploy')
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
PORT = 8931

# 期望值：直接由 seed 推导，避免「写死宝钛口径」的老问题
SEED = os.path.join(BASE, 'build', 'seed')
EXPECT = {}
for _f in sorted(os.listdir(SEED)):
    if _f.startswith('report_') and _f.endswith('.json'):
        _j = json.load(open(os.path.join(SEED, _f), encoding='utf-8'))
        EXPECT[_j['report']['code']] = {
            'name': _j['report']['name'],
            'mods': len(_j['mods']),
            'charts': len(_j['charts']),
            'kpis': len(_j['report'].get('kpis') or []),
            'toc': len(_j['report'].get('toc') or []),
            'keys': sorted(c['id'] for c in _j['charts']),
            'markers': json.dumps([c['opt'] for c in _j['charts']],
                                  ensure_ascii=False).count('{{fn:'),
        }
NREP = len(EXPECT)

OUT = os.path.join(DEPLOY, '_probe_rpt_all.html')

RPT_PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = {errs:[], stage:'init'};
  window.addEventListener('error', function(e){ R.errs.push(String(e.message)); });
  window.addEventListener('unhandledrejection', function(e){
    R.errs.push('rej:' + String((e.reason && e.reason.message) || e.reason));
  });
  function txt(id){ var e=document.getElementById(id); return e ? e.textContent.replace(/\s+/g,' ').trim() : ''; }
  function scan(o, fn){
    if(!o || typeof o !== 'object') return;
    for(var k in o){
      var v = o[k];
      if(v && typeof v === 'object') scan(v, fn);
      else fn(v);
    }
  }
  function num(a){ return a.length; }
  function collect(){
    try{
      R.code = St.code; R.src = St.src; R.loadErr = St.loadErr || '';
      var r = St.rep || {};
      R.repCode = r.code; R.repName = r.name; R.repTitle = r.title; R.repKicker = r.kicker;
      /* 模块 */
      R.modN = St.mods.length;
      R.modSeq = St.mods.map(function(m){ return +m.seq; }).sort(function(a,b){ return a-b; });
      R.modNo  = St.mods.map(function(m){ return String(m.no); });
      R.modTitles = St.mods.map(function(m){ return String(m.no) + ':' + String(m.title||''); });
      R.cardN = num(document.querySelectorAll('#mods > .card'));
      R.cardIds = (function(){ var a=[], c=document.querySelectorAll('#mods > .card[id]');
        for(var i=0;i<c.length;i++) a.push(c[i].id); return a; })();
      /* 壳 */
      R.kpiN = num((r.kpis||[])); R.kpiDom = num(document.querySelectorAll('#kpis .stat'));
      R.tocN = num((r.toc||[]));  R.tocDom = num(document.querySelectorAll('#toc a'));
      R.heroLen = txt('hero').length; R.verdictLen = txt('verdict').length; R.footLen = txt('foot').length;
      R.essenceInMods = /class="essence"/.test(document.getElementById('mods').innerHTML);
      R.barTxt = txt('rbar');
      /* 图表：库 / 图位 / 实例 / canvas 四个口径 */
      R.chartN = St.chartKeys.length; R.chartKeys = St.chartKeys.slice();
      R.slotDomN = num(document.querySelectorAll('[data-chart]'));
      R.slotDomKeys = (function(){ var a=[], s=document.querySelectorAll('[data-chart]');
        for(var i=0;i<s.length;i++) a.push(s[i].getAttribute('data-chart')); return a; })();
      R.instKeys = Object.keys(St.inst || {});
      R.canvasN = num(document.querySelectorAll('#mods canvas'));
      R.canvasBox = (function(){ var a=[], c=document.querySelectorAll('#mods canvas');
        for(var i=0;i<c.length;i++){ var b=c[i].getBoundingClientRect();
          a.push([Math.round(b.width), Math.round(b.height)]); } return a; })();
      R.miss = (function(){ var a=[], m=document.querySelectorAll('.rpt-chartmiss');
        for(var i=0;i<m.length;i++) a.push(m[i].textContent.replace(/\s+/g,' ').trim().slice(0,90)); return a; })();
      /* 标记 / 函数还原
         ⚠️ St.charts[k].opt 是**库内原始值**（页面刻意不就地改写它，renderCharts 是
            revive(copy(opt), copy(opt)) 出副本再交给 echarts）。所以：
              · 原始值里的 {{fn:}} 数量 == 库里存的标记数（应当 > 0，说明标记没被提前破坏）
              · 副本里必须 0 处标记、且真的还原出 function（这才是「图表能画出来」的前提）*/
      R.markRaw = 0; R.markN = 0; R.fnN = 0; R.revErr = [];
      Object.keys(St.charts || {}).forEach(function(k){
        var raw = St.charts[k] && St.charts[k].opt;
        var sraw = JSON.stringify(raw) || '';
        var mr = sraw.match(/\{\{fn:/g); if(mr) R.markRaw += mr.length;
        var rv;
        try{ rv = revive(copy(raw), copy(raw)); }
        catch(e){ R.revErr.push(k + ':' + String(e && e.message || e)); return; }
        scan(rv, function(v){ if(typeof v === 'function') R.fnN++; });
        var sr = JSON.stringify(rv, function(kk, vv){ return typeof vv === 'function' ? '[FN]' : vv; }) || '';
        var m2 = sr.match(/\{\{fn:/g); if(m2) R.markN += m2.length;
      });
      R.optKeys = Object.keys(St.charts || {});
      /* ★ 占位符泄漏检查（贵研铂业 chartRev 踩过）：
         ECharts 只在 formatter 是**字符串模板**时替换 {a}/{b}/{c}；formatter 是函数时
         返回值原样输出。所以「函数形式」的 formatter 一旦返回字面量 '{c}'，图上就会
         把 "{c}" 画出来 —— canvas 里看不出来，只能这样喂假参数验返回值。 */
      R.phBad = []; R.phN = 0; R.fmtSample = [];
      Object.keys(St.charts || {}).forEach(function(k){
        var rec = St.charts[k]; if(!rec) return;
        var rv; try{ rv = revive(copy(rec.opt), copy(rec.opt)); }catch(e){ return; }
        var cnt = catCount(rv) || 8;
        (rv.series || []).forEach(function(s, si){
          if(!s) return;
          var fs = [];
          if(s.label && typeof s.label.formatter === 'function') fs.push(['label', s.label.formatter]);
          if(s.itemStyle && s.itemStyle.color && typeof s.itemStyle.color === 'function') return;
          fs.forEach(function(pair){
            R.phN++;
            for(var i = 0; i < cnt; i++){
              var out;
              try{
                out = pair[1]({dataIndex:i, value:(s.data && s.data[i] != null ? s.data[i] : 1),
                               seriesIndex:si, name:s.name});
              }catch(e){ return; }
              if(typeof out === 'string' && /\{[abc]\}/.test(out))
                R.phBad.push(k + '.s' + si + '.' + pair[0] + '@' + i + '=' + out);
              if(R.fmtSample.length < 40)
                R.fmtSample.push(k + '.s' + si + '[' + i + ']→' + String(out));
            }
          });
        });
      });
      /* 逐条诊断：把库里每个带 {{fn:}} 的字符串单独丢给页面真实的 revive，
         看它到底有没有被还原成函数（不还原的真因只有这里能看清） */
      R.mkDiag = [];
      Object.keys(St.charts || {}).forEach(function(k){
        var opt = St.charts[k] && St.charts[k].opt;
        (function walk(o, path){
          if(!o || typeof o !== 'object') return;
          Object.keys(o).forEach(function(key){
            var v = o[key], p = path + '.' + key;
            if(typeof v === 'string'){
              if(v.indexOf('{{fn:') >= 0){
                var rv;
                try{ rv = revive(v, opt); }catch(e){ rv = 'ERR:' + (e && e.message); }
                R.mkDiag.push({ k:k, p:p, raw:v, got:(typeof rv),
                                out:(typeof rv === 'string' ? rv : '') });
              }
            } else if(v && typeof v === 'object') walk(v, p);
          });
        })(opt, '');
      });
      /* 坏内容扫描（模块正文） */
      var H = document.getElementById('mods').innerHTML;
      R.badMod = [];
      var BAD = ['{{', 'undefined', 'NaN', '[object Object]', '&lt;span', 'rpt-chartmiss'];
      for(var i=0;i<BAD.length;i++) if(H.indexOf(BAD[i]) >= 0) R.badMod.push(BAD[i]);
      /* 顶栏切换器 */
      var sel = document.querySelector('select.rsel');
      R.hasSel = !!sel;
      R.selN = sel ? sel.options.length : 0;
      R.selTxt = sel ? (function(){ var a=[]; for(var i=0;i<sel.options.length;i++)
        a.push(sel.options[i].textContent.replace(/\s+/g,' ').trim()); return a; })() : [];
      R.selVal = sel ? sel.value : '';
      R.selHit = sel ? (String(sel.value) === String(r.id)) : false;
      R.allN = (St.all||[]).length;
      R.allCodes = (St.all||[]).map(function(x){ return String(x.code); });
      R.rptErr = String(window.__RPT_ERR || '');
      R.chartsHook = window.__RPT_CHARTS;
      R.docTitle = document.title;
      R.makeDiag = (R.mkDiag || []).slice();
      R.stage = 'done';
    }catch(e){ R.errs.push('collect:' + (e && e.message || e)); R.stage = 'throw'; }
    document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R);
  }
  var t0 = Date.now();
  (function poll(){
    var el = function(){ return document.getElementById('probeOut'); };
    var insts = Object.keys(St.inst || {}).length;
    var ready = St.mods.length > 0 && St.rep && insts > 0 && (St.all || []).length > 1;
    if(ready || Date.now() - t0 > 45000){ setTimeout(collect, 600); return; }
    setTimeout(poll, 250);
  })();
})();
</script>
'''


def inject(src, out, js, tag):
    s = open(src, encoding='utf-8').read()
    onerr = ('<script>window.__RPT_ERR=window.__RPT_ERR||"";'
             'window.onerror=function(m,u,l,c,e){window.__RPT_ERR=String(m)+" @"+l;};</script>')
    assert '<head>' in s
    s = s.replace('<head>', '<head>\n' + onerr, 1)
    # ⚠️ 必须用**最后**一处 </body>（ECharts 压缩库里含 `</body>` 字符串）
    i = s.rfind('</body>')
    assert i > 0
    s = s[:i] + js + '\n' + s[i:]
    open(out, 'w', encoding='utf-8').write(s)
    a = js.index('<script>') + len('<script>')
    core = js[a:js.index('</script>', a)]
    tmp = os.path.join(BASE, 'build', '_tmp_all_%s.js' % tag)
    open(tmp, 'w', encoding='utf-8').write(core)
    c = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
    # 不删：文件名固定，下轮覆盖。删除会累计触发环境的 safe-delete 守卫（见 check_static.py 注释）。
    if c.returncode:
        print('%s 探针语法错误：\n%s' % (tag, (c.stderr or '')[-1500:]))
        raise SystemExit(1)
    print('[1] 探针注入 %s（%d 字节；node --check 通过）' % (os.path.basename(out), os.path.getsize(out)))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def edge_path():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


def run_one(edge, code, res):
    prof = os.path.join(BASE, 'build', '_prof_all_%s' % code)
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    url = 'http://127.0.0.1:%d/_probe_rpt_all.html?code=%s' % (PORT, code)
    cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=1680,1050', '--user-data-dir=' + prof,
           '--virtual-time-budget=120000', '--dump-dom', url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=900)
    except subprocess.TimeoutExpired:
        res[code] = ('TIMEOUT', None, '')
        return
    dom = r.stdout.decode('utf-8', 'ignore')
    m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)
    if not m:
        p = os.path.join(BASE, 'build', '_probe_all_%s_dom.txt' % code)
        open(p, 'w', encoding='utf-8').write(dom)
        res[code] = ('NODATA', None, p)
        return
    res[code] = ('OK', json.loads(_h.unescape(m.group(1))), '')


OK = [0]
FAIL = [0]


def chk(name, cond, extra=''):
    if cond:
        OK[0] += 1
        print('   [OK]   ' + name)
    else:
        FAIL[0] += 1
        print('   [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


def main():
    codes = [a for a in os_argv() if a in EXPECT] or sorted(EXPECT)
    print('=' * 78)
    print('5 份研报 · 真机 E2E 验收（真浏览器 + 真云端数据库）  共 %d 份' % len(codes))
    print('=' * 78)
    inject(os.path.join(DEPLOY, 'report.html'), OUT, RPT_PROBE, 'rpt')

    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print('[2] 本地 http 127.0.0.1:%d（根目录 deploy/，多线程）' % PORT)

    edge = edge_path()
    print('[3] Edge：%s\n' % edge)

    print('[4] 并行启动 %d 个 headless 实例…' % len(codes))
    res = {}
    ths = []
    for c in codes:
        t = threading.Thread(target=run_one, args=(edge, c, res))
        t.start()
        ths.append(t)
    # 全部结束后统一打印，避免日志交错
    for t in ths:
        t.join()
    httpd.shutdown()
    print('[5] 全部实例返回\n')

    for c in codes:
        st, d, extra = res.get(c, ('MISSING', None, ''))
        e = EXPECT[c]
        print('-' * 78)
        print('【%s %s】' % (c, e['name']))
        print('-' * 78)
        if st != 'OK':
            chk('探针回传结果', False, '%s %s' % (st, extra))
            continue
        print('   来源=%s 代码=%s 名称=%s' % (d.get('src'), d.get('repCode'), d.get('repName')))
        print('   标题=%s' % d.get('repTitle'))
        print('   模块 %s / 图位 %s / 实例 %s / canvas %s · 标记残留 %s · 还原函数 %s'
              % (d.get('modN'), d.get('slotDomN'), len(d.get('instKeys') or []),
                 d.get('canvasN'), d.get('markN'), d.get('fnN')))
        print('   顶栏：%s' % (d.get('barTxt') or '')[:110])
        print('   切换器：%s 个选项 %s' % (d.get('selN'), d.get('selTxt')))
        if d.get('errs'):
            print('   ⚠️ JS 错误：%s' % d['errs'][:6])

        if d.get('makeDiag'):
            for x in d['makeDiag']:
                print('   · %s%s' % (x['k'], x['p']))
                print('       库里 : %s' % x['raw'][:120])
                print('       revive→ %s %s' % (x['got'], x['out'][:80]))
        if d.get('fmtSample'):
            print('   formatter 实际输出（前 %d 条）：' % len(d['fmtSample']))
            for s in d['fmtSample'][:24]:
                print('      %s' % s)
        chk('页面零 JS 错误', not d.get('errs'), d.get('errs'))
        chk('数据来自云端数据库', d.get('src') == 'cloud', d.get('src'))
        chk('没有加载错误', not d.get('loadErr'), d.get('loadErr'))
        chk('研报代号 = %s' % c, str(d.get('repCode')) == c, d.get('repCode'))
        chk('研报名称 = %s' % e['name'], d.get('repName') == e['name'], d.get('repName'))
        chk('文档标题含公司名', e['name'] in (d.get('docTitle') or ''), d.get('docTitle'))
        chk('模块 %d 个' % e['mods'], d.get('modN') == e['mods'], d.get('modN'))
        chk('模块编号 1..%d 齐' % e['mods'],
            d.get('modSeq') == list(range(1, e['mods'] + 1)), d.get('modSeq'))
        chk('DOM 里 %d 张模块卡片' % e['mods'], d.get('cardN') == e['mods'], d.get('cardN'))
        chk('卡片锚点 m1..m%d 齐' % e['mods'],
            d.get('cardIds') == ['m%d' % i for i in range(1, e['mods'] + 1)], d.get('cardIds'))
        chk('KPI %d 项（库与 DOM 一致）' % e['kpis'],
            d.get('kpiN') == e['kpis'] and d.get('kpiDom') == e['kpis'],
            '%s / %s' % (d.get('kpiN'), d.get('kpiDom')))
        chk('目录 %d 条（库与 DOM 一致）' % e['toc'],
            d.get('tocN') == e['toc'] and d.get('tocDom') == e['toc'],
            '%s / %s' % (d.get('tocN'), d.get('tocDom')))
        chk('hero / 核心结论 / 页脚都有内容',
            d.get('heroLen', 0) > 20 and d.get('verdictLen', 0) > 50 and d.get('footLen', 0) > 50,
            '%s / %s / %s' % (d.get('heroLen'), d.get('verdictLen'), d.get('footLen')))
        chk('「一句话本质」渲染在模块流里', d.get('essenceInMods') is True, d.get('essenceInMods'))
        # ---- 图表四个口径一致 ----
        chk('库内图表 %d 张' % e['charts'], d.get('chartN') == e['charts'], d.get('chartN'))
        chk('库内图表 key 与 seed 一致', sorted(d.get('chartKeys') or []) == e['keys'],
            d.get('chartKeys'))
        chk('模块里 %d 个图位' % e['charts'], d.get('slotDomN') == e['charts'], d.get('slotDomN'))
        chk('图位 key 与库内图表一一对应',
            sorted(d.get('slotDomKeys') or []) == sorted(d.get('optKeys') or []) == e['keys'],
            '%s vs %s' % (sorted(d.get('slotDomKeys') or []), sorted(d.get('optKeys') or [])))
        chk('echarts 实例 %d 个' % e['charts'],
            len(d.get('instKeys') or []) == e['charts'], d.get('instKeys'))
        chk('渲染出 %d 个 canvas' % e['charts'], d.get('canvasN') == e['charts'], d.get('canvasN'))
        chk('没有「图表暂无数据 / 渲染失败」占位', not d.get('miss'), d.get('miss'))
        boxes = d.get('canvasBox') or []
        chk('每个 canvas 尺寸都正常（>200×120）',
            len(boxes) == e['charts'] and all(b[0] > 200 and b[1] > 120 for b in boxes),
            boxes[:6])
        # ---- 标记 / 坏内容 ----
        chk('库内原始值保留 %d 处 {{fn:}} 标记（标记未被提前破坏）' % e['markers'],
            d.get('markRaw') == e['markers'], '%s vs %s' % (d.get('markRaw'), e['markers']))
        chk('revive 出的副本 0 处标记残留', d.get('markN') == 0, d.get('markN'))
        chk('revive 全程无异常', not d.get('revErr'), d.get('revErr'))
        # 没有标记的研报（option 里全是字面量）→ 还原函数数理应为 0；
        # 有标记的 → 每处标记都必须变成真 function（数量只能多不能少）
        chk('映射函数还原数 == 标记数（%d）' % e['markers'],
            (d.get('fnN') or 0) >= e['markers']
            and ((d.get('fnN') or 0) > 0) == (e['markers'] > 0),
            '%s vs 标记 %s' % (d.get('fnN'), e['markers']))
        chk('formatter 返回值无 {a}/{b}/{c} 占位符泄漏（验了 %s 个）' % d.get('phN'),
            not d.get('phBad'), (d.get('phBad') or [])[:4])
        chk('模块正文无 {{ / undefined / NaN / 渲染失败',
            not d.get('badMod'), d.get('badMod'))
        # ---- 切换器 ----
        chk('顶栏出现 %d 份研报的切换下拉' % NREP, d.get('hasSel') is True, d.get('hasSel'))
        chk('下拉 %d 个选项' % NREP, d.get('selN') == NREP, d.get('selN'))
        chk('下拉当前项指向本研报', d.get('selHit') is True,
            '%s vs %s' % (d.get('selVal'), d.get('repCode')))
        chk('下拉选项含全部 5 个代码',
            sorted(d.get('allCodes') or []) == sorted(EXPECT), d.get('allCodes'))
        print('')

    print('=' * 78)
    print('通过 %d 项 · 失败 %d 项' % (OK[0], FAIL[0]))
    print('=' * 78)
    return 1 if FAIL[0] else 0


def os_argv():
    import sys
    return sys.argv[1:]


if __name__ == '__main__':
    import sys
    # ★ 无论成功失败都要清掉 deploy/_probe_rpt_all.html —— 那里面**带着会话 token**。
    #   用「清空」而不是 os.remove：删除会累计触发环境的 safe-delete 守卫（阈值 50），
    #   而清空对「token 不留在盘上」完全等价。（这个文件曾被遗漏，在 deploy/ 里留了 1.2 MB 带 token 的页）
    try:
        rc = main()
    finally:
        try:
            open(OUT, 'w', encoding='utf-8').close()
        except OSError:
            pass
    sys.exit(rc)
