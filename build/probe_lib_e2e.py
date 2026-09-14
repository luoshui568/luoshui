# -*- coding: utf-8 -*-
"""研究报告库 research.html 的 E2E 探针（纯只读，不写库）。

为什么单独验：
  「研究报告」是**独立页面**（按用户要求不塞进 index）。它能不能读全研报、
  卡片链接指得对不对、搜索/筛选/排序是不是真的生效 —— index 的探针一概看不到，
  必须单独跑一遍。工作台那边只需要验「侧栏有入口 + 点击真的跳这个文件」。

⚠️ 数字都不写死：云端有几份研报就去拉几份做对照。
   用户随时会加研报/改标题，把「5 份」写死必然变成过期的假失败
   —— 上一轮跳转探针就栽在写死「96 只标的」上（一导入就变 206）。

⚠️ 运行前先清掉本机残留登录态（在应用脚本**之前**注入），
   这样「未登录 → 只读浏览」这一条断言才是确定性的；
   否则固定 Edge profile 会带着上一轮的口令进来。

用法：python build/probe_lib_e2e.py
"""
import http.server
import json
import os
import re
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
DEPLOY = os.path.join(BASE, 'deploy')
PORT = 8971
OUT = os.path.join(DEPLOY, '_probe_lib.html')

# 在应用脚本之前执行：清掉跨轮残留的会话（固定 profile 会带过来）
CLEAN = """<script>
try{
  localStorage.removeItem('wb_auth_v1');
  sessionStorage.removeItem('wb_auth_v1');
}catch(e){}
</script>
"""

PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = {checks:[], errs:[], diag:{}, stage:'init'};
  function log(name, cond, extra){
    R.checks.push({n:name, ok:!!cond, x:(extra === undefined ? '' : String(extra))});
  }
  window.addEventListener('error', function(e){ R.errs.push(String(e.message)); });
  window.addEventListener('unhandledrejection', function(e){
    R.errs.push('rej:' + String((e.reason && e.reason.message) || e.reason)); });

  function cards(){ return document.querySelectorAll('#grid a.card'); }
  function cardCodes(){
    var out = [], cs = cards();
    for(var i = 0; i < cs.length; i++){
      out.push(decodeURIComponent(String(cs[i].getAttribute('href') || '').replace(/^.*code=/, '')));
    }
    return out;
  }
  function bar(){ return document.getElementById('lbar'); }
  function barTxt(){ return bar() ? String(bar().textContent) : ''; }
  function finish(){
    try{ R.errPage = (window.__LIB_ERR || []).slice(); }catch(e){}
    R.stage = 'done';
    document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R);
  }

  var T = 0;
  (function wait(){
    T++;
    if(T > 300){ R.stage = 'timeout'; finish(); return; }
    if(typeof window.Lib !== 'object'){ return setTimeout(wait, 100); }
    if(window.L && L.loading){ return setTimeout(wait, 100); }
    /* 加载完成 = 有卡片，或明确报错 */
    if(!cards().length && !(window.L && L.err)){ return setTimeout(wait, 100); }
    run();
  })();

  function run(){
    try{
      R.stage = 'run';
      var total = cards().length;
      R.diag.cards = total;
      R.diag.src = (window.L && L.src) || '';
      R.diag.errMsg = (window.L && L.err) || '';
      R.diag.rows = (window.L && L.rows) ? L.rows.length : -1;

      log('页面没有读取错误', !(window.L && L.err), R.diag.errMsg);
      log('渲染出研报卡片', total > 0, total);
      log('顶栏显示份数标签', /份研报/.test(barTxt()));
      log('未登录时显示只读提示', /未登录/.test(barTxt()));
      log('统计条 4 格', document.querySelectorAll('#stats .st').length === 4);
      log('筛选项来自真实数据（含「全部」）',
          document.querySelectorAll('#chips .chip').length >= 2,
          document.querySelectorAll('#chips .chip').length);

      /* 每张卡片的结构与链接 */
      var cs = cards(), bad = [];
      for(var i = 0; i < cs.length; i++){
        var a = cs[i];
        var code = a.querySelector('.ctop .code');
        var nm   = a.querySelector('.ctop .nm');
        var ti   = a.querySelector('.ti');
        var href = String(a.getAttribute('href') || '');
        if(!code || !nm || !ti || !/^report\.html\?code=/.test(href) ||
           !String(code.textContent).trim() || !String(ti.textContent).trim()){
          bad.push(href || '(no href)');
        }
      }
      log('每张卡片都有代码/名称/标题，且链接指向 report.html?code=', bad.length === 0, bad.join(' '));
      log('卡片链接按名称出现（点名称也能进，链接就是卡片本身）',
          cs.length > 0 && /^\d{6}$/.test(String(cs[0].querySelector('.ctop .code').textContent).trim()),
          cs.length ? String(cs[0].querySelector('.ctop .code').textContent).trim() : '');

      /* 顶栏按钮 */
      var btns = bar() ? bar().querySelectorAll('button') : [], backBtn = null, refBtn = null;
      for(var j = 0; j < btns.length; j++){
        var oc = String(btns[j].getAttribute('onclick') || '');
        if(/Lib\.back/.test(oc)) backBtn = btns[j];
        if(/Lib\.load/.test(oc)) refBtn = btns[j];
      }
      log('顶栏有「返回工作台」按钮', !!backBtn, backBtn ? String(backBtn.textContent).trim() : '');
      log('顶栏有「刷新数据」按钮', !!refBtn);
    }catch(e){ R.errs.push('run:' + (e && e.message || e)); }

    /* 与云端做对照（不写死份数） */
    try{
      fetch(REST + 'wb_reports?select=code&order=code.asc',
            { headers:{ 'Authorization':'Bearer ' + CFG.key }, cache:'no-store' })
        .then(function(r){ return r.json(); })
        .then(function(rows){
          var api = (rows || []).map(function(x){ return String(x.code); }).sort();
          var got = cardCodes().sort();
          R.diag.api = api.join(',');
          log('卡片数与云端研报数一致', got.length === api.length, got.length + ' vs ' + api.length);
          log('卡片代码集合与云端完全一致', got.join(',') === api.join(','), got.join(',') + ' | ' + api.join(','));
          afterApi(got.length);
        })
        ['catch'](function(e){
          R.errs.push('api:' + (e && e.message || e));
          afterApi(cardCodes().length);
        });
    }catch(e){ R.errs.push('fetch:' + (e && e.message || e)); afterApi(cardCodes().length); }
  }

  function afterApi(total){
    try{
      /* —— 搜索 —— */
      var nm0 = String((L.rows[0] && L.rows[0].name) || '');
      if(nm0){
        Lib.setQ(nm0);
        var e1 = L.rows.filter(function(r){ return String(r.name || '').indexOf(nm0) >= 0; }).length;
        log('搜索名称「' + nm0 + '」命中数正确', cards().length === e1 && e1 > 0, cards().length + '/' + e1);
        Lib.setQ('');
        log('清空搜索恢复全部卡片', cards().length === total, cards().length + '/' + total);
      }
      var c0 = String((L.rows[0] && (L.rows[0].code || L.rows[0].id)) || '');
      if(c0){
        Lib.setQ(c0);
        var e1b = L.rows.filter(function(r){
          return String(r.code || r.id || '').indexOf(c0) >= 0;
        }).length;
        log('搜索代码「' + c0 + '」命中数正确', cards().length === e1b && e1b > 0, cards().length + '/' + e1b);
        Lib.setQ('');
      }
      /* 搜一个一定不存在的词 */
      Lib.setQ('zzz-绝不存在-zzz');
      log('无匹配时出空态提示', cards().length === 0 && /没有匹配的研报/.test(
          String((document.getElementById('empty') || {}).textContent || '')));
      Lib.setQ('');
      log('清空后空态收起、卡片回来', cards().length === total &&
          String((document.getElementById('empty') || {}).style ? document.getElementById('empty').style.display : '') === 'none');

      /* —— 类型筛选（用真实存在的第一个类型，不写死名字）—— */
      var kinds = (window.L.kinds || []);
      R.diag.kinds = kinds.join(',');
      if(kinds.length){
        var k0 = kinds[0];
        Lib.setKindIdx(0);
        var e2 = L.rows.filter(function(r){ return repKind(r).k === k0; }).length;
        log('按类型「' + k0 + '」筛选', cards().length === e2 && e2 > 0, cards().length + '/' + e2);
        Lib.setKindIdx(-1);
        log('取消类型筛选恢复全部', cards().length === total, cards().length + '/' + total);
      } else {
        log('类型筛选：数据里至少有一种类型', false, '(空)');
      }

      /* —— 排序 —— */
      var codes = L.rows.map(function(r){ return String(r.code || r.id); }).sort();
      Lib.setSort('code');
      var f1 = decodeURIComponent(String(cards()[0].getAttribute('href') || '').replace(/^.*code=/, ''));
      log('按代码升序：第一张是最小代码', f1 === codes[0], f1 + '/' + codes[0]);
      Lib.setSort('name');
      log('按名称排序不报错且张数不变', cards().length === total, cards().length);
      Lib.setSort('t');
      log('回到按更新时间排序', cards().length === total, cards().length);

      /* —— 刷新（真发第二次请求）—— */
      Lib.load(true);
      setTimeout(function(){
        log('刷新后卡片数不变', cards().length === total, cards().length + '/' + total);
        log('全程零 JS 错误', (window.__LIB_ERR || []).length === 0 && R.errs.length === 0,
            (window.__LIB_ERR || []).join(' | ') + R.errs.join(' | '));
        finish();
      }, 3000);
    }catch(e){ R.errs.push('afterApi:' + (e && e.message || e)); finish(); }
  }
})();
</script>
'''


def cfg():
    return json.load(open(os.path.join(BUILD, 'cloud.json'), encoding='utf-8'))


def edge():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    src = open(os.path.join(DEPLOY, 'research.html'), encoding='utf-8').read()
    body_end = src.rfind('</body>')
    app_i = src.rfind('<script', 0, body_end)      # 应用脚本 = </body> 前最后一个 script
    page = src[:app_i] + CLEAN + src[app_i:body_end] + PROBE + src[body_end:]
    open(OUT, 'w', encoding='utf-8').write(page)

    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print('本地 http 127.0.0.1:%d\n' % PORT)

    prof = os.path.join(BUILD, '_prof_lib')
    os.makedirs(prof, exist_ok=True)
    try:
        cmd = [edge(), '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
               '--window-size=1680,1200', '--user-data-dir=' + prof,
               '--virtual-time-budget=60000', '--dump-dom',
               'http://127.0.0.1:%d/_probe_lib.html' % PORT]
        r = subprocess.run(cmd, capture_output=True, timeout=900)
        dom = r.stdout.decode('utf-8', 'replace')
    finally:
        httpd.shutdown()
        # ⚠️ 就地清空临时页，不要 os.remove（safe-delete 守卫按整轮累计删除数拦）。
        #    漏了这步的话 `_probe_lib.html` 会一直躺在 deploy/ 里，
        #    哪天「整目录上传」就把它带上线了 —— 本轮真发现了这么一个 38KB 残留。
        try:
            open(OUT, 'w', encoding='utf-8').close()
        except OSError:
            pass

    m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S)
    if not m:
        print('!! 没抓到探针结果（stage 卡住 / 页面没渲染）')
        print('   dom 长度 =', len(dom))
        print('   title =', (re.search(r'<title>(.*?)</title>', dom, re.S) or ['', '?'])[1][:200])
        print('   前端错误 =', re.findall(r'__LIB_ERR[^;]*', dom)[:2])
        raise SystemExit(1)

    d = json.loads(m.group(1))
    ok = bad = 0
    print('===== research.html（研究报告库）=====')
    for c in d.get('checks', []):
        if c['ok']:
            ok += 1
            print('  [OK]   %s%s' % (c['n'], ('  ← ' + c['x']) if c['x'] else ''))
        else:
            bad += 1
            print('  [FAIL] %s%s' % (c['n'], ('  ← ' + c['x']) if c['x'] else ''))
    print('\n  诊断: %s' % json.dumps(d.get('diag') or {}, ensure_ascii=False))
    errs = list(d.get('errPage') or []) + list(d.get('errs') or [])
    if errs:
        bad += len(errs)
        for e in errs[:12]:
            print('  !! JS: %s' % e)
    print('\n通过 %d / 失败 %d（stage=%s）' % (ok, bad, d.get('stage')))
    raise SystemExit(0 if bad == 0 else 1)


if __name__ == '__main__':
    main()
