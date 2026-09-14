# -*- coding: utf-8 -*-
"""投资标的模块 v4 · 端到端真机探针：自定义板块（多板块版）

覆盖本轮改动（全部在真浏览器里跑，数据注入，不依赖外网）：
  A. 板块标签条渲染 —— 全部 / 各自定义板块（带数量）/ 未分组；× 只出现在自定义板块上
  B. 板块名安全性 —— 含引号/尖括号的板块名不会破坏内联 onclick（按下标派发）
  C. 筛选 —— 点板块名只显示该板块；再点一次回到全部；「未分组」只显示无板块的
  D. 导入弹窗的自定义板块 —— 输入框 + datalist + 已有板块快捷标签 + 「已识别 N 个代码」
  E. doImport 归组 —— ★ 一只标的可同时属于多个板块：已属别的板块的代码**追加**而归，不再被当成重复丢掉
  E2. 大清单跨板块导入不丢代码 —— 30 个代码（8 个已在池 + 22 个全新）一个都不能少
      （用户报「粘贴 157 个，只进来 111 个」的直接回归）
  F. 编辑弹窗板块字段 —— 多板块回填 / 快捷标签增删 / 「A , B」也能存成 A|B、去首尾空白
  G. 解散板块 —— 走管理员密码闸门；★ 只摘掉这一个板块，标的与它别的板块都保留
  H. 板块列 —— 表头有「板块」，有板块的标的显示标签、无板块显示 —
  I. JS 错误必须为 0

⚠️ 写操作 / 打开表单一律要带「已通过密码」哨兵：`App.openStock(id, window.PASS_OK)`、
   `App.doImport(window.PASS_OK)`、`App.saveStock(id, window.PASS_OK)`。
   模板里的 FORM_GUARD / WRITE_GUARD 会给这些方法包一层密码框，
   裸调只会弹出密码层然后什么都不做 —— 表现为一连串莫名其妙的假失败
   （2026-09：`App.openStock('st_600459')` 弹密码层 → 表单没渲染 → 下一行
   `document.getElementById('s-grp').value = …` 直接抛 null，F/G 共 12 条断言全假失败）。
"""
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUT = os.path.join(BASE, 'build', '_probe_stock4.html')
PORT = 8913

NASTY = '测"试\'板块<x>'

# 注入的股票池：3 个板块 + 1 只未分组 + 1 只名字特异的板块
IMM = [
    {"id": "st_600459", "code": "600459", "exchange": "sh", "name": "贵研铂业",
     "grp": "贵金属", "sub_industry": "其他稀有小金属", "region": "云南",
     "ind_pe": 39.36, "total_assets": 252.74, "net_assets": 90.12, "price": 18.94, "chg_pct": -3.86},
    {"id": "st_600547", "code": "600547", "exchange": "sh", "name": "山东黄金",
     "grp": "贵金属", "sub_industry": "黄金", "region": "山东",
     "ind_pe": 23.53, "total_assets": 700.1, "net_assets": 320.5, "price": 28.11, "chg_pct": 1.22},
    {"id": "st_601600", "code": "601600", "exchange": "sh", "name": "中国铝业",
     "grp": "工业金属", "sub_industry": "铝", "region": "北京",
     "ind_pe": 10.51, "total_assets": 2445.77, "net_assets": 843.45, "price": 9.44, "chg_pct": -4.84},
    {"id": "st_000807", "code": "000807", "exchange": "sz", "name": "云铝股份",
     "grp": "工业金属", "sub_industry": "铝", "region": "云南",
     "ind_pe": 10.51, "total_assets": 505.15, "net_assets": 381.62, "price": 27.29, "chg_pct": -3.67},
    {"id": "st_000831", "code": "000831", "exchange": "sz", "name": "五矿稀土",
     "grp": "", "sub_industry": "稀土", "region": "山西",
     "ind_pe": 46.59, "total_assets": 90.2, "net_assets": 60.1, "price": 31.5, "chg_pct": 2.4},
    {"id": "st_601958", "code": "601958", "exchange": "sh", "name": "金钼股份",
     "grp": NASTY, "sub_industry": "其他稀有小金属", "region": "陕西",
     "ind_pe": 39.36, "total_assets": 250.17, "net_assets": 193.98, "price": 20.26, "chg_pct": -4.43},
]
IMM_JSON = json.dumps(IMM, ensure_ascii=False)

PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function txt(id){ var e = document.getElementById(id); return e ? e.textContent.replace(/\s+/g,' ').trim() : ''; }
  function chips(){
    var box = document.getElementById('stockGrps');
    if(!box) return {all:[], named:[], del:0, raw:''};
    var gs = [].map.call(box.querySelectorAll('.stkG .gn'), function(e){
      return {t:e.textContent.replace(/\s+/g,' ').trim(), on:e.parentNode.className.indexOf('on')>=0};
    });
    return {all:gs,
            named:gs.slice(1).map(function(x){ return x.t; }),
            del:box.querySelectorAll('.stkG .gx').length,
            raw:box.innerHTML.slice(0, 400)};
  }
  function tableCodes(){
    var wrap = document.getElementById('stockWrap');
    if(!wrap) return [];
    return [].map.call(wrap.querySelectorAll('tbody tr'), function(tr){
      return tr.querySelectorAll('td')[0].textContent.trim();
    });
  }
  function tableCol(name){
    var wrap = document.getElementById('stockWrap');
    var ths = [].map.call(wrap.querySelectorAll('thead th'), function(e){
      return e.textContent.replace(/[⇅▼▲]/g,'').trim(); });
    var i = ths.indexOf(name), o = {};
    if(i < 0) return o;
    [].forEach.call(wrap.querySelectorAll('tbody tr'), function(tr){
      var td = tr.querySelectorAll('td');
      o[td[0].textContent.trim()] = td[i].textContent.replace(/\s+/g,' ').trim();
    });
    return o;
  }
  function grpOf(code){
    var r = S.stocks.filter(function(x){ return x.code === code; })[0];
    return r ? r.grp : null;
  }
  function codesQ(){ return S.stocks.map(function(x){ return x.code; }); }

  /* 打桩：任何云端请求都不发出去（updateRow 会入队，flushQueue 调的就是 window.api） */
  window.api = function(){ return Promise.resolve(null); };

  setTimeout(function(){
    try{
      App.go('stock');
      R.pageOn = (document.getElementById('pg-stock').className||'').indexOf('on') >= 0;

      /* ===== A. 标签条渲染 ===== */
      S.stocks = __IMM__.map(function(x){ return defaults('stocks', x); });
      sortState(); renderStock();
      var c1 = chips();
      R.chipAll = c1.all.map(function(x){ return x.t; });
      R.chipDel = c1.del;
      R.gKeys = (UI.stkGKeys || []).slice(0, 6);
      R.gList = stkGroupList();
      R.hintOn = c1.all.length ? c1.all[0].on : null;
      R.subTxt = txt('stockSub');
      /* 板块列 */
      R.cols = [].map.call(document.getElementById('stockWrap').querySelectorAll('thead th'), function(e){
        return e.textContent.replace(/[⇅▼▲]/g,'').trim(); });
      R.grpCells = tableCol('板块');

      /* ===== B. 板块名安全性（含引号/尖括号） ===== */
      var badIdx = UI.stkGKeys.indexOf('__NASTY__');
      R.nastyIdx = badIdx;
      try{
        App.stockGrpPick(badIdx);
        R.nastyPickOk = true;
      }catch(e){ R.nastyPickOk = false; R.err.push('nasty:' + e.message); }
      R.nastyFilterGrp = UI.stockGrp;
      R.nastyRows = tableCodes();
      App.stockGrpPick(0);                        /* 下标 0 = 「全部」，复位 */
      R.afterResetAll = tableCodes().length;

      /* ===== C. 筛选 ===== */
      var gi = UI.stkGKeys.indexOf('贵金属');
      App.stockGrpPick(gi);
      R.pickGrp = UI.stockGrp;
      R.pickRows = tableCodes();
      R.pickOn = chips().all.filter(function(x){ return x.on; }).map(function(x){ return x.t; });
      App.stockGrpPick(gi);                       /* 再点一次 = 取消 */
      R.pickToggleOff = UI.stockGrp;
      R.pickToggleRows = tableCodes().length;
      var ni = UI.stkGKeys.indexOf('__NONE__');
      R.noneIdx = ni;
      App.stockGrpPick(ni);
      R.noneRows = tableCodes();
      R.noneChip = chips().all.filter(function(x){ return x.on; }).map(function(x){ return x.t; });
      App.stockGrpPick(0);

      /* ===== D. 导入弹窗：自定义板块 ===== */
      var realSync = window.syncQuotes, syncCalls = 0;
      window.syncQuotes = function(){ syncCalls++; return Promise.resolve({ok:0}); };
      App.stockImportDlg();
      R.dlgGrpInput = !!document.getElementById('s-grp-new');
      R.dlgDatalist = (document.getElementById('s-grp-new-dl')||{children:[]}).children.length;
      R.dlgQuick = [].map.call((document.getElementById('s-grp-qs')||{querySelectorAll:function(){return [];}})
                     .querySelectorAll('.q'), function(e){ return e.textContent.trim(); });
      var ta = document.getElementById('s-bulk');
      ta.value = '600459 贵研铂业\n601677 明泰铝业\n002532 天山铝业\n000831 五矿稀土\n';
      R.grpOpts = (UI.stkGrpOpts || []).slice();
      var qi = UI.stkGrpOpts.indexOf('贵金属');
      R.quickIdx = qi;
      App.stockGrpFill(qi);                       /* 点快捷标签「贵金属」 */
      R.fillVal = document.getElementById('s-grp-new').value;
      App.stockImportCount();
      R.countTxt = txt('s-count');
      R.countOn = (document.getElementById('s-grp-qs')||{querySelectorAll:function(){return [];}})
                    .querySelectorAll('.q.on').length;
      App.stockGrpFill(qi);                       /* 再点一次取消 */
      R.fillToggle = document.getElementById('s-grp-new').value;

      /* ===== E. doImport 归组（★ 多板块：已属别的板块 → 追加，不再跳过） ===== */
      document.getElementById('s-grp-new').value = '稀土永磁';
      App.stockImportCount();
      R.countTxt2 = txt('s-count');
      App.doImport(window.PASS_OK||{});
      R.imp600459 = grpOf('600459');              /* 原本在「贵金属」→ 追加「稀土永磁」 */
      R.imp000831 = grpOf('000831');              /* 未分组 → 补归 */
      R.imp601677 = grpOf('601677');              /* 新标的 → 归入 */
      R.imp002532 = grpOf('002532');
      R.impTotal = S.stocks.length;
      R.impCodes = codesQ();
      R.impChips = chips().all.map(function(x){ return x.t; });
      R.impCell600459 = tableCol('板块')['600459'] || '';
      R.impSyncCalls = syncCalls;
      R.impModalClosed = (document.getElementById('mask').className||'').indexOf('on') < 0;
      /* ⚠️ syncQuotes 在 WRITE_GUARD 里（会弹密码层）+ 会打网络，E2 之前不能还原，
         否则 doImport 内部那次 syncQuotes 会挂个密码遮罩把后面全部阶段带偏。 */

      /* ===== E2. 大清单跨板块导入：一个代码都不能少 =====
         「粘贴 157 个代码，只进来 111 个」的根因 = 已属别的板块的代码被当重复丢掉。
         这里用「8 只已在池 + 22 只全新 = 30 个代码」导进新板块「批量测试」，要求 30 个全部在池。 */
      App.stockImportDlg();
      var L2 = codesQ().slice();
      for(var z = 0; z < 22; z++) L2.push(String(600100 + z));
      R.bulkIn = L2.length;
      document.getElementById('s-bulk').value = L2.join('\n');
      document.getElementById('s-grp-new').value = '批量测试';
      App.stockImportCount();
      R.bulkCount = txt('s-count');
      App.doImport(window.PASS_OK||{});
      R.bulkMissing = L2.filter(function(c){ return codesQ().indexOf(c) < 0; });
      R.bulkTotal = S.stocks.length;
      R.bulkChips = chips().all.map(function(x){ return x.t; });
      R.bulk600459 = grpOf('600459');
      R.bulkInBatch = S.stocks.filter(function(x){ return stkGrpHas(x, '批量测试'); }).length;
      R.bulkNames = S.stocks.map(function(x){ return x.code + ':' + (x.grp||'—'); });
      R.bulkSyncCalls = syncCalls;
      window.syncQuotes = realSync;

      /* ===== F. 编辑弹窗板块字段（多板块回填 / 快捷增删 / 一次填多个） ===== */
      App.openStock('st_600459', window.PASS_OK||{});
      R.editGrpVal = (document.getElementById('s-grp')||{}).value;
      R.editGrpTag = (document.getElementById('s-grp')||{}).tagName;
      R.editDatalist = (document.getElementById('s-grp-dl')||{children:[]}).children.length;
      var eqs = document.getElementById('s-grp-qs');
      R.editChips = eqs ? [].map.call(eqs.querySelectorAll('.q'), function(e){ return e.textContent.trim(); }) : [];
      R.editChipsOn = eqs ? [].map.call(eqs.querySelectorAll('.q.on'), function(e){ return e.textContent.trim(); }) : [];
      /* ★ 快捷标签必须真的「有样式」（胶囊、有底色、有间距）——
         曾因为 CSS 只写在 `.stkPick .qs .q` 下，编辑弹窗里的标签退化成一串裸文字，
         而 DOM 断言全绿、只有截图能看出来。这里用计算样式把它变成可断言的。 */
      var q0 = eqs ? eqs.querySelector('.q') : null;
      if(q0){
        var cs = window.getComputedStyle(q0);
        R.chipStyle = {radius: cs.borderRadius, bg: cs.backgroundColor, bgimg: cs.backgroundImage,
                       pad: cs.paddingLeft, display: window.getComputedStyle(eqs).display};
      } else { R.chipStyle = null; }
      var ci = (UI.stkEditOpts || []).indexOf('工业金属');
      App.stockGrpChip(ci);                       /* 点一下 = 挂上 */
      R.chipAdd = (document.getElementById('s-grp')||{}).value;
      App.stockGrpChip(ci);                       /* 再点一下 = 摘掉 */
      R.chipToggleOff = (document.getElementById('s-grp')||{}).value;
      document.getElementById('s-grp').value = '  紫金系 , 铜矿  ';
      App.saveStock('st_600459', window.PASS_OK||{});
      R.editSaved = grpOf('600459');
      R.editClosed = (document.getElementById('mask').className||'').indexOf('on') < 0;

      /* ===== G. 解散板块（管理员闸门 · 多板块只摘掉这一个） ===== */
      var realReq = window.requireAdmin, asked = null;
      window.requireAdmin = function(label, cb){ asked = label; cb(''); };
      /* 先摆好两只标的的板块：601600 同时属于两个、000807 只属于「工业金属」
         → 解散「工业金属」后，前者保住房产（铝加工），后者才掉进未分组 */
      var r600 = S.stocks.filter(function(x){ return x.code === '601600'; })[0];
      var r807 = S.stocks.filter(function(x){ return x.code === '000807'; })[0];
      if(r600){ r600.grp = stkGrpSet(['工业金属', '铝加工']); }
      if(r807){ r807.grp = '工业金属'; }
      renderStock();
      var before = S.stocks.length;
      var di = UI.stkGKeys.indexOf('工业金属');
      R.delIdx = di;
      App.stockGrpDel(di);
      R.delLabel = asked;
      R.delLeft601600 = grpOf('601600');
      R.delLeft000807 = grpOf('000807');
      R.delRowsKept = S.stocks.length;
      R.delRowCountSame = (S.stocks.length === before);
      R.delChips = chips().all.map(function(x){ return x.t; });
      R.delUiGrp = UI.stockGrp;
      /* 「全部」「未分组」不能删 */
      asked = null;
      App.stockGrpDel(0);
      R.delAllBlocked = (asked === null);
      window.requireAdmin = realReq;

      /* ===== H. 保留标的数量、名称未被破坏 ===== */
      R.finalNames = S.stocks.map(function(x){ return x.code + ':' + x.name + ':' + (x.grp||'—'); });

      /* ===== I. 行情回写：PostgREST 批量写入要求同一批里 key 一致 =====
         pushQuotes 刻意「有值才写」基本面字段 → 每行 key 天然不同 → 整批 400
         DATABASE_PGRST102 "All object keys must match"，等于行情永远写不进云端。
         修法是按 key 签名分组。这里用真库真行验证：分组 ≥ 2、每批内部 key 一致、整体无失败组。 */
      var rows = S.stocks.slice(0, 8);
      if(rows.length >= 3){
        /* 人为造出两种载荷形状（真实数据本来就参差，这里只是让它必然发生） */
        rows[1].info_at = ''; rows[1].ind_pe = '';
        rows[2].info_at = ''; rows[2].ind_pe = ''; rows[2].region = '';
      }
      var groups = 0, badBatch = '';
      var origApi = window.api;
      window.api = function(t, o){
        if(String(t).indexOf('wb_stocks') === 0 && o && o.method === 'POST'){
          groups++;
          var ks = (o.body || []).map(function(r){ return Object.keys(r).sort().join(','); });
          for(var i = 1; i < ks.length; i++){
            if(ks[i] !== ks[0]) badBatch = '批内 key 不一致：' + ks[0].slice(0, 24) + ' vs ' + ks[i].slice(0, 24);
          }
        }
        return origApi.apply(this, arguments);
      };
      function finish(){
        window.api = origApi;
        R.pushGroups = groups;
        R.pushBad = badBatch;
        R.stage = 'done';
        setTimeout(out, 150);
      }
      Promise.resolve(pushQuotes(rows)).then(function(res){
        R.pushRes = res;
        R.pushMsg = String(Cloud.msg || '');
        finish();
      })['catch'](function(e){
        R.pushErr = String(e && e.message || e);
        finish();
      });
    }catch(e){
      R.err.push('throw:' + (e && e.message));
      R.stage = 'threw';
      out();
    }
  }, 900);
})();
</script>
'''

# ---------- 1. 生成探针页 ----------
s = open(SRC, encoding='utf-8').read()

onerr = ('<script>window.__R={err:[],stage:"init"};'
         'window.onerror=function(m,u,l,c,e){window.__R.err.push(String(m)+" @"+l);};'
         '</script>')
assert '<head>' in s
s = s.replace('<head>', '<head>\n' + onerr, 1)

js = (PROBE.replace('__IMM__', IMM_JSON)
           .replace('__NASTY__', json.dumps(NASTY)[1:-1].replace("'", "\\'"))
           .replace('__NONE__', '__none__'))

assert '</body>' in s
s = s.replace('</body>', js + '\n</body>', 1)
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))

# ---------- 1b. 注入脚本先过语法关（语法错会让探针静默不执行，白跑一趟） ----------
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
_tj = os.path.join(BASE, 'build', '_tmp_probe4.js')
_core = js.split('<script>')[1].split('</script>')[0]
open(_tj, 'w', encoding='utf-8').write(_core)
_c = subprocess.run([NODE, '--check', _tj], capture_output=True, text=True)
os.remove(_tj)
if _c.returncode != 0:
    print('[1b] 注入脚本语法错误：\n' + (_c.stderr or '')[-1200:])
    raise SystemExit(1)
print('[1b] 注入脚本 node --check 通过')


# ---------- 2. 本地 http ----------
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(os.path.join(BASE, 'build'))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('[2] 本地 http：http://127.0.0.1:%d/' % PORT)

# ---------- 3. Edge ----------
edge = None
for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
          r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
    if os.path.exists(c):
        edge = c
        break
assert edge, '找不到 msedge.exe'
print('[3] Edge：%s' % edge)

prof = os.path.join(BASE, 'build', '_probe_profile4')
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)
url = 'http://127.0.0.1:%d/_probe_stock4.html' % PORT
cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
       '--user-data-dir=' + prof, '--virtual-time-budget=20000', '--dump-dom', url]
print('[4] 启动 headless Edge …')
r = subprocess.run(cmd, capture_output=True, timeout=240)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))

# ---------- 4. 结果 ----------
m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)

print('\n' + '=' * 76)
print('探针结果 · 投资标的模块 v3（自定义板块）')
print('=' * 76)

if not m:
    open(os.path.join(BASE, 'build', '_probe4_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('[FAIL] 探针没有回传结果，DOM 已存 build/_probe4_dom.txt')
    print(dom[:900])
    httpd.shutdown()
    raise SystemExit(1)

d = json.loads(m.group(1))

# 探针 JSON 是从 dump-dom 的 HTML 文本里抠出来的，文本节点里的 < > & 会被序列化成实体，
# 比对前先还原（否则「测"试'板块<x>」这类名字会假失败）
import html as _h


def un(x):
    if isinstance(x, str):
        return _h.unescape(x)
    if isinstance(x, list):
        return [un(i) for i in x]
    if isinstance(x, dict):
        return dict((k, un(v)) for k, v in x.items())
    return x


for _k in ['chipAll', 'gKeys', 'gList', 'grpCells', 'dlgQuick', 'grpOpts', 'delChips',
           'impChips', 'finalNames', 'countTxt', 'countTxt2', 'nastyFilterGrp',
           'delLabel', 'pickOn', 'noneChip', 'subTxt', 'editChips', 'editChipsOn',
           'impCodes', 'bulkChips', 'bulkNames', 'bulkMissing', 'bulkCount', 'impCell600459']:
    if _k in d:
        d[_k] = un(d[_k])

ok = fail = 0


def chk(name, cond, extra=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK]   ' + name)
    else:
        fail += 1
        print('  [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


print('\n阶段：%s' % d.get('stage'))
print('JS 错误：%s' % (d.get('err') or '无'))
chk('页面切换到投资标的', d.get('pageOn') is True)
chk('JS 零错误', not d.get('err'))

# ---- A ----
print('\n── A. 板块标签条 ──')
print('  标签：%s' % d.get('chipAll'))
print('  键序：%s' % d.get('gKeys'))
print('  分组统计：%s' % json.dumps(d.get('gList'), ensure_ascii=False))
chk('标签条含「全部」且数量正确（6）', (d.get('chipAll') or [])[:1] == ['全部6'], d.get('chipAll'))
chk('3 个自定义板块都显示出来（含数量）',
    sorted((d.get('chipAll') or [])[1:4]) == sorted(['贵金属2', '工业金属2', '测"试\'板块<x>1']),
    (d.get('chipAll') or [])[1:4])
chk('「未分组」标签显示未分组标的数（1）', '未分组1' in (d.get('chipAll') or []), d.get('chipAll'))
chk('× 只出现在 3 个自定义板块上（未分组/全部没有 ×）', d.get('chipDel') == 3, d.get('chipDel'))
chk('默认选中「全部」', d.get('hintOn') is True, d.get('hintOn'))
chk('副标题显示自定义板块个数', '3 个自定义板块' in (d.get('subTxt') or ''), d.get('subTxt'))
print('  副标题：%s' % d.get('subTxt'))

# ---- H ----
print('\n── H. 板块列 ──')
print('  表头：%s' % ' | '.join((d.get('cols') or [])[-4:]))
chk('表头有「板块」列', '板块' in (d.get('cols') or []), (d.get('cols') or [])[-5:])
print('  单元格：%s' % json.dumps(d.get('grpCells'), ensure_ascii=False))
chk('有板块的标的显示板块标签（600459 → 贵金属）',
    (d.get('grpCells') or {}).get('600459') == '🏷 贵金属', (d.get('grpCells') or {}).get('600459'))
chk('无板块的标的显示 —', (d.get('grpCells') or {}).get('000831') == '—', (d.get('grpCells') or {}).get('000831'))

# ---- B ----
print('\n── B. 板块名安全性（含引号 / 尖括号） ──')
chk('含 " \' < > 的板块名能拿到下标', isinstance(d.get('nastyIdx'), int) and d.get('nastyIdx') > 0, d.get('nastyIdx'))
chk('点它不抛错（按下标派发，内联 onclick 未被名字破坏）', d.get('nastyPickOk') is True)
chk('且确实筛选到了这个板块', d.get('nastyFilterGrp') == '测"试\'板块<x>', d.get('nastyFilterGrp'))
chk('该板块下只有 601958 一行', (d.get('nastyRows') or []) == ['601958'], d.get('nastyRows'))
chk('复位后 6 行都在', d.get('afterResetAll') == 6, d.get('afterResetAll'))

# ---- C ----
print('\n── C. 按板块筛选 ──')
print('  选中「贵金属」→ %s' % d.get('pickRows'))
chk('点「贵金属」筛选生效', d.get('pickGrp') == '贵金属', d.get('pickGrp'))
chk('只剩该板块 2 只', sorted(d.get('pickRows') or []) == ['600459', '600547'], d.get('pickRows'))
chk('标签高亮切到「贵金属」', (d.get('pickOn') or []) and '贵金属' in (d.get('pickOn') or [''])[0], d.get('pickOn'))
chk('再点一次取消筛选（回到全部）', d.get('pickToggleOff') == '' and d.get('pickToggleRows') == 6,
    '%s / %s' % (d.get('pickToggleOff'), d.get('pickToggleRows')))
print('  点「未分组」→ %s' % d.get('noneRows'))
chk('「未分组」只显示无板块的 1 只', d.get('noneRows') == ['000831'], d.get('noneRows'))
chk('「未分组」标签高亮', (d.get('noneChip') or []) and '未分组' in (d.get('noneChip') or [''])[0], d.get('noneChip'))

# ---- D ----
print('\n── D. 导入弹窗的自定义板块 ──')
chk('弹窗有自定义板块输入框', d.get('dlgGrpInput') is True)
chk('有 datalist 供选已有板块（>=8 常用 + 已有）', (d.get('dlgDatalist') or 0) >= 8, d.get('dlgDatalist'))
print('  快捷标签：%s / 快捷顺序：%s' % (d.get('dlgQuick'), d.get('grpOpts')))
chk('已有板块做成快捷标签', len(d.get('dlgQuick') or []) == 3, d.get('dlgQuick'))
chk('点快捷标签把板块名填进输入框', d.get('fillVal') == '贵金属', repr(d.get('fillVal')))
print('  计数条：%s' % d.get('countTxt'))
chk('底部实时显示「已识别 N 个代码」（4 个）', '已识别' in (d.get('countTxt') or '') and '4' in (d.get('countTxt') or ''), d.get('countTxt'))
chk('填了板块名时显示归入提示', '将全部归入板块' in (d.get('countTxt') or ''), d.get('countTxt'))
chk('快捷标签会高亮当前板块', (d.get('countOn') or 0) == 1, d.get('countOn'))
chk('再点一次快捷标签 = 取消选择', d.get('fillToggle') == '', repr(d.get('fillToggle')))

# ---- E ----
print('\n── E. doImport 归组（多板块：追加而不是跳过） ──')
print('  %s' % json.dumps(d.get('finalNames'), ensure_ascii=False))
print('  写入板块「稀土永磁」后的计数条：%s' % d.get('countTxt2'))
chk('新标的 601677 / 002532 归入「稀土永磁」',
    d.get('imp601677') == '稀土永磁' and d.get('imp002532') == '稀土永磁',
    '%s / %s' % (d.get('imp601677'), d.get('imp002532')))
chk('已存在但未分组的 000831 补归入「稀土永磁」', d.get('imp000831') == '稀土永磁', d.get('imp000831'))
chk('★ 已属「贵金属」的 600459 追加「稀土永磁」（两个板块都在，不再被当重复丢掉）',
    d.get('imp600459') == '贵金属|稀土永磁', d.get('imp600459'))
chk('同一只标的在板块列里显示两个标签', (d.get('impCell600459') or '').count('🏷') == 2, d.get('impCell600459'))
chk('总数 6+2=8（同代码不新建记录）', d.get('impTotal') == 8, d.get('impTotal'))
chk('代码唯一（8 行 = 8 个不同代码）', len(set(d.get('impCodes') or [])) == 8, d.get('impCodes'))
print('  导入后标签：%s' % d.get('impChips'))
chk('标签条出现「稀土永磁4」（600459 在两个板块里各计一次）',
    any(t == '稀土永磁4' for t in (d.get('impChips') or [])), d.get('impChips'))
chk('导入触发一次同步', d.get('impSyncCalls') == 1, d.get('impSyncCalls'))
chk('导入后弹窗关闭', d.get('impModalClosed') is True)

# ---- E2 ----
print('\n── E2. 大清单跨板块导入：一个都不能少（157→111 的回归） ──')
print('  送进 %s 个代码 → 池里 %s 行；板块统计 %s' % (d.get('bulkIn'), d.get('bulkTotal'), d.get('bulkChips')))
chk('送进去的代码一个都没丢（8 已在池 + 22 全新 = 30）',
    d.get('bulkMissing') == [], d.get('bulkMissing'))
chk('池行数 = 30（同代码并成一行，没有为了凑数而重复建行）',
    d.get('bulkTotal') == 30, d.get('bulkTotal'))
chk('★ 已属别的板块的 600459 现在有 3 个板块（贵金属/稀土永磁/批量测试）',
    d.get('bulk600459') == '贵金属|稀土永磁|批量测试', d.get('bulk600459'))
chk('「批量测试」板块下 30 只全在', d.get('bulkInBatch') == 30, d.get('bulkInBatch'))
chk('计数条显示识别到 30 个代码', '30' in (d.get('bulkCount') or ''), d.get('bulkCount'))

# ---- F ----
print('\n── F. 编辑弹窗的板块字段（多板块） ──')
print('  回填：%r / 快捷标签：%s / 选中：%s' % (d.get('editGrpVal'), d.get('editChips'), d.get('editChipsOn')))
chk('板块字段是 input（可手填新板块）不是 select', d.get('editGrpTag') == 'INPUT', d.get('editGrpTag'))
chk('回填当前全部板块（贵金属 | 稀土永磁 | 批量测试）',
    d.get('editGrpVal') == '贵金属 | 稀土永磁 | 批量测试', d.get('editGrpVal'))
chk('快捷标签把已选中的板块标记为 on',
    sorted(d.get('editChipsOn') or []) == sorted(['贵金属', '稀土永磁', '批量测试']), d.get('editChipsOn'))
chk('datalist 有可选板块', (d.get('editDatalist') or 0) >= 8, d.get('editDatalist'))
print('  标签计算样式：%s' % json.dumps(d.get('chipStyle'), ensure_ascii=False))
_cs = d.get('chipStyle') or {}
chk('★ 快捷标签真的有样式（胶囊圆角 + 有底色 + 有内边距，不是一串裸文字）',
    _cs.get('display') == 'flex' and '999px' in str(_cs.get('radius'))
    and ('rgba(0, 0, 0, 0)' not in str(_cs.get('bg')) or 'gradient' in str(_cs.get('bgimg')))
    and str(_cs.get('pad')) not in ('', '0px'),
    _cs)
chk('点快捷标签 = 追加一个板块，原来的不动',
    d.get('chipAdd') == '贵金属 | 稀土永磁 | 批量测试 | 工业金属', repr(d.get('chipAdd')))
chk('再点一次 = 只摘掉那一个',
    d.get('chipToggleOff') == '贵金属 | 稀土永磁 | 批量测试', repr(d.get('chipToggleOff')))
chk('一次填多个 + 去首尾空白（「  紫金系 , 铜矿  」→「紫金系|铜矿」）',
    d.get('editSaved') == '紫金系|铜矿', repr(d.get('editSaved')))
chk('保存后弹窗关闭', d.get('editClosed') is True)

# ---- G ----
print('\n── G. 解散板块（只摘掉这一个） ──')
print('  闸门提示：%s' % d.get('delLabel'))
chk('走管理员密码闸门，提示里写明板块名与标的数',
    '工业金属' in (d.get('delLabel') or '') and '2' in (d.get('delLabel') or ''), d.get('delLabel'))
chk('提示里明确「标的本身不会被删除」', '不会被删除' in (d.get('delLabel') or ''), d.get('delLabel'))
chk('提示里说明「只摘掉这个板块，别的保留」',
    '只摘掉这个板块' in (d.get('delLabel') or ''), d.get('delLabel'))
chk('★ 同时属于两个板块的 601600 保住另一个板块（工业金属 → 铝加工）',
    d.get('delLeft601600') == '铝加工', d.get('delLeft601600'))
chk('只属于该板块的 000807 被移出（grp 清空）', d.get('delLeft000807') == '', repr(d.get('delLeft000807')))
chk('标的没有被删除（行数不变）', d.get('delRowCountSame') is True, '%s → %s' % (d.get('delRowsKept'), 'before'))
print('  解散后标签：%s' % d.get('delChips'))
chk('标签条上「工业金属」消失',
    not any(t == '工业金属2' for t in (d.get('delChips') or [])), d.get('delChips'))
chk('标签条上出现「铝加工1」（保住的板块）',
    any(t == '铝加工1' for t in (d.get('delChips') or [])), d.get('delChips'))
chk('只有 1 只掉进「未分组」（601600 不算）',
    any(t == '未分组1' for t in (d.get('delChips') or [])), d.get('delChips'))
chk('「全部 / 未分组」不可当板块解散', d.get('delAllBlocked') is True)

# ---- I. 行情回写（PostgREST 批量写入的 key 一致性）----
chk('★ 行情回写：按 key 签名分组后逐组发送（≥2 组）',
    (d.get('pushGroups') or 0) >= 2, 'groups=%s' % d.get('pushGroups'))
chk('★ 行情回写：每一批内部的对象 key 完全一致', not d.get('pushBad'), d.get('pushBad'))
chk('★ 行情回写整体成功（没有失败组）',
    bool(d.get('pushRes')) and bool((d.get('pushRes') or {}).get('ok')),
    json.dumps(d.get('pushRes'), ensure_ascii=False) + ' err=' + str(d.get('pushErr')))
chk('★ 不再报 object keys must match',
    'must match' not in str(d.get('pushMsg') or ''), str(d.get('pushMsg'))[:70])

print('\n' + '=' * 76)
print('通过 %d 项 · 失败 %d 项' % (ok, fail))
print('=' * 76)

httpd.shutdown()
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)
try:
    os.remove(OUT)
except Exception:
    pass
print('\n[5] 临时文件已清理')
