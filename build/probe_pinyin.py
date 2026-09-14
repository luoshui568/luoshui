# -*- coding: utf-8 -*-
"""拼音首字母搜索的验收探针（纯只读，不写库）。

验什么：
  ① 页面里的 **PY_OK 自检**是否通过（环境不支持 zh 排序时必须自动禁用，而不是给错结果）；
  ② 把项目真实数据里的**每个汉字**丢进页面的 `pyCh()`，与 pypinyin 的答案逐字对照 —— 要求 0 不一致；
  ③ `pyInit()` 对整串的输出（如 贵研铂业 → gyby）；
  ④ **真搜一遍**：研报库搜索框输入每份研报名称的首字母，对应的卡片必须出现；
     再输一个不可能的首字母，必须出空态。

⚠️ 全部跑在 `deploy/research.html`（构建产物）自己的实现上，不是复刻一份 —— 
   复刻的测试只能证明「我抄对了」，证明不了「线上那份是对的」。

用法：python build/probe_pinyin.py
"""
import http.server
import io
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
DEPLOY = os.path.join(BASE, 'deploy')
OUT = os.path.join(DEPLOY, '_probe_py.html')

PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = {checks: [], errs: [], diag: {}};
  function log(n, ok, x){ R.checks.push({n: n, ok: !!ok, x: (x === undefined ? '' : String(x))}); }
  window.addEventListener('error', function(e){ R.errs.push(String(e.message)); });
  window.addEventListener('unhandledrejection', function(e){
    R.errs.push('rej:' + String((e.reason && e.reason.message) || e.reason)); });

  log('★ 拼音自检 PY_OK（环境支持 zh 排序）', PY_OK === true, 'PY_OK=' + PY_OK);
  log('锚点表自洽（23 个声母 · 字母与锚点等长）',
      PY_A.length === PY_L.length && PY_L.length === 23, PY_L.length + '/' + PY_A.length);

  /* ---- ① 逐字对照 ---- */
  var CH = __CHARS__, EX = __EXPECT__;
  var bad = [], n = 0;
  for(var i = 0; i < CH.length; i++){
    n++;
    var got = pyCh(CH.charAt(i));
    if(got !== EX.charAt(i)) bad.push(CH.charAt(i) + '→' + got + '(应' + EX.charAt(i) + ')');
  }
  log('★★ 项目数据 ' + n + ' 个汉字逐字对照 pypinyin', bad.length === 0,
      bad.length ? bad.slice(0, 20).join(' ') : '全部一致');

  /* ---- ② 整串 ---- */
  var CASES = __CASES__;
  var bad2 = [];
  for(var k = 0; k < CASES.length; k++){
    var g = pyInit(CASES[k][0]);
    if(g !== CASES[k][1]) bad2.push(CASES[k][0] + '→' + g + '(应' + CASES[k][1] + ')');
  }
  log('★ pyInit 整串（' + CASES.length + ' 例）', bad2.length === 0,
      bad2.length ? bad2.join(' ') : CASES.map(function(c){ return c[0] + '→' + c[1]; }).join(' '));

  /* ---- ③④ 真搜：必须等页面把云端研报拉回来 ----
     ⚠️ 探针是同步注入的，比 fetch 早；不等数据就搜 ⇒ 卡片数恒为 0，
        会把「搜不到」误判成功能坏了（第一次就是这么白跑一轮的）。
        这里用**轮次上限**等，不用 Date.now()（headless 的 --virtual-time-budget 会快进 timer）。 */
  var REPS = __REPS__;
  var T = 0;
  (function waitData(){
    T++;
    var names = (window.L && L.rows) ? L.rows.length : 0;
    if(names === 0 && T < 400){ setTimeout(waitData, 120); return; }
    R.diag.rows = names;
    R.diag.rounds = T;
    if(names === 0){
      log('研报数据已到达（准备好搜索）', false, '等了 ' + T + ' 轮仍是 0 条');
      return finish();
    }
    log('研报数据已到达（准备好搜索）', true, names + ' 条');

    var miss = [], wrong = [];
    for(var j = 0; j < REPS.length; j++){
      Lib.setQ(REPS[j][2]);
      var cards = document.querySelectorAll('#grid a.card');
      var codes = [];
      for(var c = 0; c < cards.length; c++){
        codes.push(decodeURIComponent(String(cards[c].getAttribute('href') || '').replace(/^.*code=/, '')));
      }
      if(codes.indexOf(REPS[j][0]) < 0) miss.push(REPS[j][1] + '(' + REPS[j][2] + ')');
      if(codes.length !== 1) wrong.push(REPS[j][2] + '命中' + codes.length + '条');
    }
    log('★★ 按名称首字母搜：每份研报都能被自己搜到', miss.length === 0,
        miss.length ? miss.join(' ') : REPS.length + ' 份全部命中');
    log('★ 首字母搜索精确（每例只命中 1 条）', wrong.length === 0,
        wrong.length ? wrong.join(' ') : 'OK');

    Lib.setQ('zzzzzz');
    log('★ 乱输首字母 → 空态（不会误命中）',
        document.querySelectorAll('#grid a.card').length === 0 &&
        getComputedStyle(document.getElementById('empty')).display !== 'none',
        'cards=' + document.querySelectorAll('#grid a.card').length);

    /* 关掉拼音时不能误伤汉字原文搜索 */
    var wasOk = PY_OK;
    PY_OK = false;
    Lib.setQ('贵研');
    var n1 = document.querySelectorAll('#grid a.card').length;
    Lib.setQ('鲁西');
    var n1b = document.querySelectorAll('#grid a.card').length;
    PY_OK = wasOk;
    Lib.setQ('贵研');
    var n2 = document.querySelectorAll('#grid a.card').length;
    Lib.setQ('鲁西');
    var n2b = document.querySelectorAll('#grid a.card').length;
    log('★ 拼音开关不影响汉字原文搜索', n1 === n2 && n1b === n2b && n1 > 0 && n1b > 0,
        '关=' + n1 + '/' + n1b + ' 开=' + n2 + '/' + n2b);
    Lib.setQ('');
    finish();
  })();

  function finish(){
    R.diag.perChar = n;
    R.diag.pyOk = PY_OK;
    R.diag.anchors = PY_A;
    R.diag.letters = PY_L;
    R.stage = 'done';
    document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R);
  }
})();
</script>
'''


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
    sys.path.insert(0, os.path.join(BUILD))
    sys.path.insert(0, r'C:/Users/50522/.workbuddy/binaries/python/envs/default/Lib/site-packages')
    import _calib_pinyin as C
    from pypinyin import pinyin, Style

    common = sorted(C.common_chars())
    truth = {}
    for cp in common:
        ch = chr(cp)
        try:
            got = pinyin(ch, style=Style.FIRST_LETTER, errors='ignore')
        except Exception:
            continue
        if got and got[0] and got[0][0]:
            L = got[0][0][0].lower()
            if L in C.LETTERS:
                truth[ch] = L
    chars = ''.join(sorted(truth))
    expect = ''.join(truth[c] for c in sorted(truth))
    print('参与逐字对照的汉字：%d 个' % len(chars))

    def initials(s):
        out = ''
        for ch in s:
            out += truth.get(ch, '')
        return out

    cases = [['贵研铂业', 'gyby'], ['宝钛股份', 'btgf'], ['四川美丰', 'scmf'],
             ['鲁西化工', 'lxhg'], ['恒邦股份', 'hbgf'], ['山东黄金', 'sdhj'],
             ['西藏矿业', 'xcky'], ['三一重工', 'syzg']]
    # 用参考实现校正上面这几例（避免手写期望值出错）
    cases = [[s, initials(s)] for s, _ in cases]

    # 云端研报列表 → 每份的名称首字母
    cfg = json.load(io.open(os.path.join(BUILD, 'cloud.json'), encoding='utf-8'))
    base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    req = urllib.request.Request(base + 'wb_reports?select=code,name',
                                 headers={'apikey': cfg['key'],
                                          'Authorization': 'Bearer ' + cfg['key']})
    reps = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))
    rep3 = [[str(r.get('code') or ''), str(r.get('name') or ''), initials(str(r.get('name') or ''))]
            for r in reps]
    print('云端研报 %d 份，首字母：%s' % (len(rep3), ' '.join(x[1] + '=' + x[2] for x in rep3)))

    src = io.open(os.path.join(DEPLOY, 'research.html'), encoding='utf-8').read()
    assert 'PY_A' in src, '构建产物里没有拼音表 —— 先跑 build.py'
    i = src.rfind('</body>')
    page = (src[:i]
            .replace('</head>', '</head>', 1))
    probe = (PROBE.replace('__CHARS__', json.dumps(chars))
                  .replace('__EXPECT__', json.dumps(expect))
                  .replace('__CASES__', json.dumps(cases, ensure_ascii=False))
                  .replace('__REPS__', json.dumps(rep3, ensure_ascii=False)))
    io.open(OUT, 'w', encoding='utf-8').write(src[:i] + probe + src[i:])

    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', port), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    prof = os.path.join(BUILD, '_prof_py')
    os.makedirs(prof, exist_ok=True)
    try:
        r = subprocess.run([edge(), '--headless=new', '--disable-gpu', '--no-sandbox',
                            '--hide-scrollbars', '--window-size=1680,1200',
                            '--user-data-dir=' + prof, '--virtual-time-budget=60000',
                            '--dump-dom', 'http://127.0.0.1:%d/_probe_py.html' % port],
                           capture_output=True, timeout=900)
        dom = r.stdout.decode('utf-8', 'replace')
    finally:
        httpd.shutdown()
        try:
            io.open(OUT, 'w', encoding='utf-8').close()   # 就地清空，不删
        except OSError:
            pass

    m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S)
    if not m:
        print('!! 没抓到探针结果，dom 长度 =', len(dom))
        raise SystemExit(1)
    d = json.loads(m.group(1))
    ok = bad = 0
    print('\n===== 拼音首字母搜索 =====')
    for c in d['checks']:
        if c['ok']:
            ok += 1
            print('  [OK]   %s%s' % (c['n'], ('  ← ' + c['x']) if c['x'] else ''))
        else:
            bad += 1
            print('  [FAIL] %s%s' % (c['n'], ('  ← ' + c['x']) if c['x'] else ''))
    for e in d.get('errs') or []:
        bad += 1
        print('  !! JS: %s' % e)
    print('\n通过 %d / 失败 %d' % (ok, bad))
    raise SystemExit(0 if bad == 0 else 1)


if __name__ == '__main__':
    main()
