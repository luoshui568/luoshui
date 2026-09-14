# -*- coding: utf-8 -*-
"""批量导入「真落库」端到端验收（真机 Edge + 真云端数据库）。

背景：`App.doImport()` 曾经把新标的只 `S.stocks.push(row)` —— 只进内存和 localStorage，
从不入队 POST。界面弹「新增 N 只 · 正在拉取数据…」的成功提示，刷新后全没、库里查不到。
本探针专门盯这条链路：
  ① 导入两个**全新代码** → 断言 PENDING 里确实排了 POST / wb_stocks（本地可证）
  ② 等队列排空 → 断言没有任何失败残留
  ③ 从**库外**（Python 直连 PostgREST）查这两个代码 → 断言真的躺在 wb_stocks 里
  ④ 断言 pushQuotes 不再被 Cloud.state='err' 挡住（历史上就是这么永久静默的）
  ⑤ 清理：用 wb_admin_delete_row 删掉测试行，并复核已删干净

⚠️ 会真的往线上库写 2 行临时数据，跑完必删；代码用 999997 / 999998（非法代码段，不会与真标的重名）。
"""
# ── 管理员口令不入库：优先 build/_secret.py（已 gitignore），其次环境变量 WB_PW ──
import os as _os
try:
    from _secret import PW
except Exception:
    PW = _os.environ.get('WB_PW', '')
if not PW:
    raise SystemExit('缺少管理员口令：请创建 build/_secret.py（PW = "…"）或设 WB_PW 环境变量')
import http.server
import json
import os
import re
import socketserver
import subprocess
import threading
import time
import urllib.error
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUT = os.path.join(BASE, 'build', '_probe_imp.html')
PORT = 8917
CODES = ['999998', '999997']

cfg = json.load(open(os.path.join(BASE, 'build', 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
AUTH = {'Authorization': 'Bearer ' + cfg['key'], 'Accept': 'application/json'}


def call(method, path, body=None, headers=None):
    h = dict(AUTH, **{'Content-Type': 'application/json'})
    if headers:
        h.update(headers)
    d = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(REST + path, data=d, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', 'replace')
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300]


PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function codesQ(){ return S.stocks.map(function(x){ return x.code; }); }
  function pend(){ return PENDING.map(function(j){ return j.m + ' ' + j.t + (j.b && j.b.code ? ' code=' + j.b.code : ''); }); }

  setTimeout(function(){
    try{
      R.restOn = !!REST;
      R.bootState = Cloud.state;
      try{ App.gateHide(); }catch(e){}
      var realSync = window.syncQuotes;
      window.syncQuotes = function(){ R.syncStub = true; return Promise.resolve({ok:0}); };

      /* 从干净状态开始，避免动到用户真实标的 */
      S.stocks = []; PENDING.length = 0;

      App.go('stock');
      App.stockImportDlg();
      R.dlgOpen = !!document.getElementById('s-bulk');
      document.getElementById('s-bulk').value = '999998 测试甲\n999997 测试乙\n';
      document.getElementById('s-grp-new').value = '';
      R.countTxt = ((document.getElementById('s-count')||{}).textContent || '').replace(/\s+/g,' ').trim();

      App.doImport(window.PASS_OK || {});
      R.localCodes = codesQ();
      R.localIds = S.stocks.map(function(x){ return x.id; });
      R.pendingAfter = pend();
      R.toastHint = ((document.getElementById('toast')||{}).textContent || '').replace(/\s+/g,' ').trim().slice(0,80);

      /* 轮询等队列排空（flushQueue 串行）。
         ⚠️ 用「轮次上限」而不是 wall-clock：headless 的 --virtual-time-budget 会把
         setTimeout 快进，用 Date.now() 计时会在真实网络还在飞的时候就判定超时。 */
      var ticks = 0;
      (function tick(){
        ticks++;
        if(!PENDING.length || ticks > 120){
          R.pendingLeft = PENDING.length;
          R.pendingLeftDetail = pend();
          R.cloudStateAfter = Cloud.state;
          R.cloudMsgAfter = String(Cloud.msg || '').slice(0, 120);
          R.parse = null;

          /* ★ pushQuotes 不能被 Cloud.state 挡住（历史病根：一次网络抖动 → 本次会话永久静默） */
          var cap = 0, realApi = window.api;
          window.api = function(){ cap++; return Promise.resolve(null); };
          Cloud.state = 'err';
          try{ pushQuotes(S.stocks.slice(0, 1)); }catch(e){ R.pushErr = String(e.message || e); }
          window.api = realApi;
          R.pushQuotesWithErrState = cap;

          window.syncQuotes = realSync;
          R.stage = 'done';
          out();
          return;
        }
        setTimeout(tick, 500);
      })();
    }catch(e){
      R.err = String(e && e.message || e);
      R.stage = 'exception';
      out();
    }
  }, 400);
})();
</script>
'''

js = PROBE
s = open(SRC, encoding='utf-8').read()

# ★ 必须先注入 window.__R 和 window.onerror，否则探针里 `var R = window.__R` 直接抛错，
#   页面看起来正常渲染、但 probeOut 永远是空的（本轮就踩了一次，白跑 30 秒）。
onerr = ('<script>window.__R={err:[],stage:"init"};'
         'window.onerror=function(m,u,l,c,e){window.__R.err.push(String(m)+" @"+l);};'
         '</script>')
assert '<head>' in s
s = s.replace('<head>', '<head>\n' + onerr, 1)

assert '</body>' in s
s = s.replace('</body>', js + '\n</body>', 1)
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))

# 注入脚本先过语法关（语法错会静默不执行）
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
_core = js.split('<script>')[1].split('</script>')[0]
open(os.path.join(BASE, 'build', '_tmp_imp.js'), 'w', encoding='utf-8').write(_core)
_c = subprocess.run([NODE, '--check', os.path.join(BASE, 'build', '_tmp_imp.js')],
                    capture_output=True, text=True)
if _c.returncode != 0:
    print('[1b] 注入脚本语法错误：\n' + (_c.stderr or '')[-1200:])
    raise SystemExit(1)
print('[1b] 注入脚本 node --check 通过')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(os.path.join(BASE, 'build'))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('[2] 本地 http：http://127.0.0.1:%d/' % PORT)

edge = None
for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
          r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
    if os.path.exists(c):
        edge = c
        break
assert edge, '找不到 msedge.exe'
print('[3] Edge：%s' % edge)

prof = os.path.join(BASE, 'build', '_probe_profile_imp')
os.makedirs(prof, exist_ok=True)          # 不删目录，规避 safe-delete 拦截
url = 'http://127.0.0.1:%d/_probe_imp.html' % PORT
print('[4] 启动 headless Edge（真发云端请求）…')
r = subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                    '--user-data-dir=' + prof, '--virtual-time-budget=45000', '--dump-dom', url],
                   capture_output=True, timeout=300)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))

m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)
ok = fail = 0


def chk(name, cond, extra=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK]   ' + name)
    else:
        fail += 1
        print('  [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


print('\n' + '=' * 78)
print('批量导入「真落库」端到端验收')
print('=' * 78)

d = json.loads(m.group(1)) if m else {}
if not m:
    open(os.path.join(BASE, 'build', '_probe_imp_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('[FAIL] 探针没有回传结果，DOM 已存 build/_probe_imp_dom.txt')

if m:
    print('阶段：%s   JS 错误：%s' % (d.get('stage'), d.get('err') or '无'))
    print('导入后本地：%s' % d.get('localCodes'))
    print('入队记录：%s' % d.get('pendingAfter'))
    chk('页面确实开了云端 REST', d.get('restOn') is True)
    chk('JS 零错误', not d.get('err'), d.get('err'))
    chk('两个新代码都进了本地池', sorted(d.get('localCodes') or []) == sorted(CODES), d.get('localCodes'))
    chk('★ 每个新代码都排了 POST 到 wb_stocks（曾经的病根所在）',
        sorted([x.split('code=')[-1] for x in (d.get('pendingAfter') or []) if x.startswith('POST wb_stocks')]) == sorted(CODES),
        d.get('pendingAfter'))
    chk('入队的是 POST 而不是 PATCH（新建必须 POST）',
        all(x.startswith('POST') for x in (d.get('pendingAfter') or [])), d.get('pendingAfter'))
    chk('队列已排空（没有卡住的写入）', d.get('pendingLeft') == 0,
        '剩余 %s 条：%s' % (d.get('pendingLeft'), d.get('pendingLeftDetail')))
    chk('★ 行情回写不再被 Cloud.state 挡住', (d.get('pushQuotesWithErrState') or 0) > 0,
        'Cloud.state=err 时 pushQuotes 实际发起 %s 次请求' % d.get('pushQuotesWithErrState'))
    print('排空后 Cloud.state=%s msg=%s' % (d.get('cloudStateAfter'), d.get('cloudMsgAfter')))

# ---------- 库外核对：真的落库了吗 ----------
print('\n── 库外核对（Python 直连 PostgREST）──')
found = []
for i in range(20):
    st, rows = call('GET', 'wb_stocks?code=in.(%s)&select=id,code,name,grp' % ','.join(CODES))
    if st == 200 and isinstance(rows, list) and len(rows) == len(CODES):
        found = rows
        break
    time.sleep(1)
chk('★ 两个新代码真的躺在 wb_stocks 里', len(found) == len(CODES),
    '查到 %d 行：%s' % (len(found), found))
chk('库里的主键与本地一致', sorted(x['id'] for x in found) == sorted('st_' + c for c in CODES),
    found)

# ---------- 清理 ----------
print('\n── 清理测试数据 ──')
st, tok = call('POST', 'rpc/wb_admin_login',
               {'p_user': 'luoshui', 'p_pass': PW, 'p_device': 'imp-probe', 'p_days': 1})
TOK = tok.get('token') if isinstance(tok, dict) else ''
chk('拿到超管令牌（用于清理）', bool(TOK))
for c in CODES:
    st, res = call('POST', 'rpc/wb_admin_delete_row',
                   {'p_token': TOK, 'p_kind': 'stocks', 'p_id': 'st_' + c, 'p_pass': PW})
    print('   删 st_%s → %s' % (c, json.dumps(res, ensure_ascii=False)[:90] if isinstance(res, dict) else res))

left = []
for i in range(10):
    st, rows = call('GET', 'wb_stocks?code=in.(%s)&select=id' % ','.join(CODES))
    left = rows if isinstance(rows, list) else []
    if not left:
        break
    time.sleep(1)
chk('★ 测试行已彻底删除', not left, left)

st, allrows = call('GET', 'wb_stocks?select=code&limit=1000')
print('   清理后 wb_stocks 总行数：%s' % (len(allrows) if isinstance(allrows, list) else allrows))

httpd.shutdown()
print('\n' + '=' * 78)
print('结果：%d 通过 / %d 失败' % (ok, fail))
print('=' * 78)
raise SystemExit(0 if fail == 0 else 1)
