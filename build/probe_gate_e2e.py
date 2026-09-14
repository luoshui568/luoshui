# -*- coding: utf-8 -*-
"""写操作密码门禁的端到端验收（真机 Edge + 真云端数据库）。

要验的六件事（每一条都对应一个会让人白干半天的坑）：
  1) 覆盖清单 —— 两页所有会改数据的入口都被门禁包装过（用方法上的 __gated 标记反查）；
  2) 未确认不落库 —— 弹出密码层后点「取消」，数据库里的记录一个字节都不该变；
  3) 错误密码被拒 —— 拒绝后仍停在密码层、且数据库未变；
  4) 正确密码放行 —— 放行后数据库确实变了（真的写进去了）；
  5) ★ 密码层不覆盖表单 —— 保存按钮就在表单弹窗里，确认时必须用独立遮罩，
     否则用户刚填的内容会被 innerHTML 覆盖清空（这是上一版最容易踩的坑）；
  6) 危险操作不给「免重复输入」—— 删除 / 覆盖导入永远要输密码。

用法：python build/probe_gate_e2e.py
密码与 token 只经命令行传入，探针页验完立即删除；不写入任何落盘文件。
"""
# ── 管理员口令不入库：优先 build/_secret.py（已 gitignore），其次环境变量 WB_PW ──
import os as _os
try:
    from _secret import PW
except Exception:
    PW = _os.environ.get('WB_PW', '')
if not PW:
    raise SystemExit('缺少管理员口令：请创建 build/_secret.py（PW = "…"）或设 WB_PW 环境变量')
import html as _h
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
DEPLOY = os.path.join(BASE, 'deploy')
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
RPT_CODE = '600456'

OK = [0]
FAIL = [0]


def chk(name, cond, extra=''):
    if cond:
        OK[0] += 1
        print('  [OK]   ' + name)
    else:
        FAIL[0] += 1
        print('  [FAIL] ' + name + ('   -> ' + str(extra) if extra != '' else ''))


def admin_token():
    cfg = json.load(open(os.path.join(BUILD, 'cloud.json'), encoding='utf-8'))
    url = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/rpc/wb_admin_login' % cfg['envId']
    body = json.dumps({'p_user': 'luoshui', 'p_pass': PW,
                       'p_device': 'probe-gate', 'p_days': 1}).encode('utf-8')
    r = urllib.request.Request(url, data=body, headers={
        'Authorization': 'Bearer ' + cfg['key'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=60) as resp:
        d = json.loads(resp.read().decode('utf-8', 'replace'))
    if not d.get('ok'):
        raise SystemExit('登录失败：%s' % d)
    return d.get('token') or d.get('t') or ''


def edge_path():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


def rpc_post(fn, body):
    """直接打 PostgREST 的 /rpc/<fn>，给兜底清理用（不经浏览器）。"""
    cfg = json.load(open(os.path.join(BUILD, 'cloud.json'), encoding='utf-8'))
    url = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/rpc/%s' % (cfg['envId'], fn)
    r = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers={
        'Authorization': 'Bearer ' + cfg['key'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8', 'replace'))


def cleanup_probe_accounts(tok):
    """兜底：探针中途失败会留下 probe_ 开头的待批准账号，这里收拾干净。

    ⚠️ 只删「probe_ 开头 且 状态为 pending」的账号 —— 绝不碰任何正常账号。
    """
    try:
        r = rpc_post('wb_admin_list', {'p_token': tok})
        rows = (r or {}).get('rows') or []
    except Exception as e:
        print('    兜底清理：读取账号列表失败 %s' % e)
        return []
    gone = []
    for x in rows:
        u = str(x.get('user_name') or '')
        if not u.startswith('probe_'):
            continue
        if str(x.get('status')) != 'pending':
            print('    ⚠️ 跳过非 pending 的 %s（状态 %s），请人工确认' % (u, x.get('status')))
            continue
        try:
            res = rpc_post('wb_admin_delete', {'p_token': tok, 'p_user': u})
        except Exception as e:
            print('    删除 %s 失败：%s' % (u, e))
            continue
        if res and res.get('ok'):
            gone.append(u)
    print('    兜底清理 probe_ 待批准账号：%s' % (', '.join(gone) if gone else '无残留'))
    return gone


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


# ============================================================ 工作台探针
WB_COMMON = r'''
  var R = {errs:[], steps:[], diag:{}};
  window.addEventListener('error', function(e){ R.errs.push(String(e.message)); });
  window.addEventListener('unhandledrejection', function(e){
    R.errs.push('rej:' + String((e.reason && e.reason.message) || e.reason)); });
  function q(k){
    var m = new RegExp('[?&]' + k + '=([^&]*)').exec(location.search || '');
    return m ? decodeURIComponent(m[1]) : '';
  }
  var TOK = q('t'), PW = q('p');
  function $(i){ return document.getElementById(i); }
  function hasOn(el){ return !!el && /(^|\s)on(\s|$)/.test(el.className); }
  function pOn(){ return hasOn($('pmask')); }
  function rpOn(){ return hasOn($('rptPMask')); }
  function log(n, ok, x){ R.steps.push({n:n, ok:!!ok, x:String(x === undefined ? '' : x).slice(0, 170)}); }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function waitFor(fn, ms){
    var t0 = Date.now();
    return new Promise(function(res){
      (function p(){
        if(fn()) return res(true);
        if(Date.now() - t0 > (ms || 9000)) return res(false);
        setTimeout(p, 80);
      })();
    });
  }
  function scr(){
    var s = '';
    try{ s += JSON.stringify(localStorage); }catch(e){}
    try{ s += JSON.stringify(sessionStorage); }catch(e){}
    return s;
  }
  /* 队列排空：updateRow 只是 enqueue，真正落库靠 flushQueue 的异步 fetch。
     ⚠️ flushQueue 开头是 `if(flushing || !REST || Cloud.state!=='on' || !PENDING.length) return`
     —— 卡住时「每轮补推一次」也推不动，所以顺带把现场原因带进诊断。 */
  function qdump(){
    try{
      var P = (typeof PENDING !== 'undefined') ? PENDING : null;
      return {
        flushing: !!window.flushing,
        cloud: (window.Cloud || {}).state,
        n: P ? P.length : -1,
        list: P ? P.map(function(x){ return x.m + ' ' + x.t; }).join(' | ') : ''
      };
    }catch(e){ return {err:String(e.message || e)}; }
  }
  function waitDrain(ms){
    var t0 = Date.now();
    return new Promise(function(res){
      (function p(){
        if(typeof PENDING === 'undefined' || !PENDING || !PENDING.length) return res(true);
        if(typeof flushQueue === 'function') flushQueue();
        if(Date.now() - t0 > (ms || 16000)) return res(false);
        setTimeout(p, 250);
      })();
    });
  }
'''

WB_PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
''' + WB_COMMON + r'''
  var TID = '', ORIG = '', TMP = 't_probe_gate_' + Date.now().toString(36);
  var NEWT = 'PROBE-门禁测试标题';
  var TICKT = 'PROBE-票据验证标题';
  var POISON = 'PROBE-毒消息后的正常写入';
  function taskRow(id){
    return api('wb_tasks?id=eq.' + id + '&select=id,title').then(function(r){ return (r && r[0]) || null; });
  }
  /* ★ 不能「发完写就 sleep 一个固定值再读库」—— 写入是异步 fetch，
     固定 sleep 会在虚拟时钟下抢在写之前读，得出「写没生效」的假结论（踩过）。
     一律轮询到期望值出现为止。 */
  function waitRow(id, want, ms){
    var t0 = Date.now();
    return new Promise(function(res){
      (function p(){
        taskRow(id).then(function(r){
          if(r && r.title === want) return res(true);
          if(Date.now() - t0 > (ms || 15000)) return res(false);
          setTimeout(p, 250);
        })['catch'](function(){ setTimeout(p, 250); });
      })();
    });
  }
  function waitRowGone(id, ms){
    var t0 = Date.now();
    return new Promise(function(res){
      (function p(){
        taskRow(id).then(function(r){
          if(!r) return res(true);
          if(Date.now() - t0 > (ms || 15000)) return res(false);
          setTimeout(p, 250);
        })['catch'](function(){ setTimeout(p, 250); });
      })();
    });
  }
  function typePass(v){ var i = $('del-pass'); if(i) i.value = v; App.confirmPass(); }

  /* ---------------- 覆盖清单（不依赖界面，先查） ---------------- */
  function coverage(){
    var names = (window.WRITE_GUARD || []).map(function(x){ return x[0]; });
    R.diag.gateN = names.length;
    var miss = names.filter(function(n){ return !(App[n] && App[n].__gated); });
    log('WRITE_GUARD 全部装上门禁（' + names.length + ' 个写入口）',
        !!names.length && names.length >= 18 && miss.length === 0, miss.join(','));

    /* 反查：App 上还有哪些「名字看着就会写」的方法没被包。
       已经在内部调 requireAdmin 的（删除类等）是允许的。 */
    var ALLOW = ['delTask','delWork','delPermit','delRes','delLog','delStock','admDelete','admToggle',
                 'admReview','doRegister',
                 'stockGrpDel','resetLocal','confirmDelete','confirmPass','cancelDanger','dangerShake'];
    var sus = Object.keys(App).filter(function(n){
      return /^(save|del|do|push|pull|import|seed|flush|recalc|cycle|workCycle|stockUnlock|adm|sync)/.test(n)
             && typeof App[n] === 'function';
    });
    var bad = sus.filter(function(n){ return !App[n].__gated && ALLOW.indexOf(n) < 0; });
    R.diag.ungated = bad;
    log('没有漏网的写方法（内部自带门禁的 ' + ALLOW.length + ' 个已排除）', bad.length === 0, bad.join(','));
    R.diag.gatedList = names.slice();
  }

  /* ---------------- 主流程 ---------------- */
  function main(){
    /* 0) 测试隔离：把上一轮可能残留在本机的待推送队列清掉，并记下初始现场。
       （PENDING 是持久化在 wb_strategy_v1 里的，残留的坏 job 会污染本轮所有写断言） */
    R.diag.isolate = qdump();
    try{ PENDING.length = 0; saveLocal(); }catch(e){}
    /* 0) 登录态 + 拉数据（RAW 直通：探针不代表用户手点） */
    try{
      localStorage.setItem('wb_auth_v1', JSON.stringify({t:TOK, u:'probe', n:'probe', r:'super', ts:Date.now()}));
    }catch(e){}
    Auth.token = TOK; Auth.user = 'probe'; Auth.role = 'super';
    return Promise.resolve(RAW.pullAll(true)).then(function(){
      R.diag.tasks = S.tasks.length;
      coverage();
      if(!S.tasks.length){ log('有可测的任务记录', false, 'S.tasks 为空'); return; }
      TID = S.tasks[0].id; ORIG = String(S.tasks[0].title || '');
      R.diag.target = TID + ' / ' + ORIG;
      App.go('plan');
      return step1();
    });
  }

  /* 1) 保存 → 弹密码层；表单不能丢；取消 → 库不变 */
  function step1(){
    App.openTask(TID, window.PASS_OK);   /* 哨兵直通：这里只测「保存」那一层的门禁 */
    $('f-title').value = NEWT;
    App.saveTask(TID);
    return waitFor(pOn, 6000).then(function(opened){
      log('点「保存」后弹出密码确认层', opened);
      var kept = !!$('f-title') && String($('f-title').value) === NEWT;
      R.diag.modalKept = kept;
      log('★ 密码层用独立遮罩，底下的表单没被清空（#modal 里的输入值还在）', kept,
          $('f-title') ? String($('f-title').value).slice(0, 40) : '输入框已被摧毁');
      R.diag.cancelBtn = !!$('dangerGo');
      App.cancelDanger();
      return sleep(600);
    }).then(function(){
      log('取消后密码层已关闭', !pOn());
      return taskRow(TID);
    }).then(function(row){
      log('取消后数据库未变（标题仍是原值）', row && row.title === ORIG, row && row.title);
      return step2();
    });
  }

  /* 2) 错误密码 → 不放行、库不变 */
  function step2(){
    App.saveTask(TID);
    return waitFor(pOn, 6000).then(function(){
      typePass('__definitely_wrong_pass__');
      return waitFor(function(){ var b = $('dangerGo'); return b && !b.disabled; }, 12000);
    }).then(function(){
      return sleep(500);
    }).then(function(){
      log('错误密码仍停在密码层（未放行）', pOn());
      return taskRow(TID);
    }).then(function(row){
      log('错误密码 → 数据库未变', row && row.title === ORIG, row && row.title);
      App.cancelDanger();
      return sleep(400);
    }).then(step3);
  }

  /* 3) 正确密码 → 写库；并验「免重复输入」勾选框存在 */
  function step3(){
    App.saveTask(TID);
    return waitFor(pOn, 6000).then(function(){
      R.diag.keepBox = !!$('pv-keep');
      log('可逆的「保存」提供「15 分钟内免重复输入」勾选框', !!$('pv-keep'));
      /* ★ 排版回归：label 是 display:flex，flex 会把**每一段文本 / 每一个内联元素**当成
         独立子项横排 —— 若不把整句裹进单个 <span>，就是「…仍需输」+「入」+「）」三列挤成一团，
         括号还飘到下一行。静态检查抓不到，只能在这里断 DOM 结构。 */
      var kl = $('pv-keep') ? $('pv-keep').parentElement : null;
      var kspans = kl ? kl.querySelectorAll(':scope > span') : [];
      var ktxt = kspans.length === 1 ? kspans[0].textContent : '';
      var loose = '';
      if(kl){ for(var ci = 0; ci < kl.childNodes.length; ci++){
        var cn = kl.childNodes[ci];
        if(cn.nodeType === 3 && cn.textContent.trim()) loose += cn.textContent.trim();
      } }
      R.diag.keepWrap = {spans: kspans.length, loose: loose, txt: ktxt.slice(0, 60)};
      log('★ 勾选框文字是整体一项（不会被 flex 拆成三列）',
          kspans.length === 1 && loose === '' &&
          ktxt.indexOf('免重复输入') >= 0 &&
          ktxt.indexOf('删除、覆盖导入仍需输入') >= 0 &&
          ktxt.indexOf('）') >= 0,
          'spans=' + kspans.length + ' loose=[' + loose + ']');
      if($('pv-keep')) $('pv-keep').checked = true;
      typePass(PW);
      return waitFor(function(){ return !pOn(); }, 15000);
    }).then(function(){
      flushQueue();                       /* updateRow 只是排队，这里显式推一次再轮询读库 */
      return waitRow(TID, NEWT, 16000);
    }).then(function(got){
      log('正确密码 → 任务标题真的写进数据库了', got, got ? '' : '轮询 16s 仍读到旧值');
      /* 还原成原值 */
      updateRow('tasks', TID, {title: ORIG});
      flushQueue();
      return waitRow(TID, ORIG, 16000);
    }).then(function(got){
      log('已把标题还原（探针不留痕）', got, got ? '' : '还原未落到库');
      return step4();
    });
  }

  /* 4) 勾了「免重复输入」后再保存 → 不再弹密码层 */
  function step4(){
    App.openTask(TID, window.PASS_OK);
    $('f-title').value = ORIG;
    App.saveTask(TID);
    return sleep(1600).then(function(){
      var still = pOn();
      log('勾选后 15 分钟内再保存不再弹密码层', !still);
      if(still){ App.cancelDanger(); }
      return sleep(300);
    }).then(step5);
  }

  /* 5) 不可逆操作：删除不给勾选框 */
  function step5(){
    App.delTask(TID);
    return waitFor(pOn, 6000).then(function(opened){
      log('「删除」同样弹出密码层', opened);
      var noKeep = !$('pv-keep');
      var go = $('dangerGo') ? String($('dangerGo').textContent) : '';
      R.diag.delBtn = go;
      log('删除是不可逆操作：不提供免重复输入勾选框', noKeep && go.indexOf('删除') >= 0, go);
      App.cancelDanger();
      return sleep(500);
    }).then(function(){
      return taskRow(TID);
    }).then(function(row){
      log('取消删除后记录仍在', !!row);
      return step6();
    });
  }

  /* 6) 造一条一次性记录 → 走完整删除链路（真删真验） */
  function step6(){
    insertRow('tasks', {id:TMP, seq:99999, title:'PROBE 临时任务（可删）',
                        task_date: today(), status:'todo', category:'研究', priority:'P2'});
    flushQueue();
    return waitRow(TMP, 'PROBE 临时任务（可删）', 16000).then(function(got){
      log('临时任务已写入数据库（准备删除）', got, got ? '' : '轮询 16s 仍未读到');
      App.delTask(TMP);
      return waitFor(pOn, 6000);
    }).then(function(){
      typePass(PW);
      return waitFor(function(){ return !pOn(); }, 15000);
    }).then(function(){
      return waitRowGone(TMP, 16000);
    }).then(function(gone){
      log('正确密码 → 临时任务已从数据库真删除', gone, gone ? '' : '轮询 16s 记录仍在');
      return step6b();
    });
  }

  /* 6b) ★ 回归：往队列头塞一条必然失败的「毒消息」。
     修复前 flushQueue 的 catch 会把 Cloud.state 置成 'err'，而重试入口又检查 Cloud.state!=='on'
     → 那次重试被自己挡掉，队列永久卡死：后面所有写入都安静地推不出去，界面还照旧提示「已更新」。
     修复后应：自动退避重试若干次 → 丢弃毒消息 → 队列排空 → 后续写入照常落库。 */
  function step6b(){
    PENDING.length = 0;
    PENDING.push({t:'wb___no_such_table___', m:'PATCH', q:'?id=eq.probe', b:{up:nowTs()}, ts:nowTs()});
    saveLocal();
    Cloud.state = 'on';                        /* 从「在线」开始，模拟真实场景 */
    setTimeout(flushQueue, 20);
    return waitDrain(26000).then(function(drained){
      R.diag.poison = {drained: drained, dump: qdump()};
      log('★ 毒消息不会永久堵住队列（修复前会静默卡死）', drained && !PENDING.length,
          'drained=' + drained + ' · ' + JSON.stringify(qdump()));
      /* 队列通了以后，正常写入必须照常落库 */
      updateRow('tasks', TID, {title: POISON});
      flushQueue();
      return waitRow(TID, POISON, 16000);
    }).then(function(got){
      R.diag.poisonAfter = qdump();
      log('★ 毒消息清理后，后续写入仍然落库', got,
          got ? ('cloud=' + ((window.Cloud || {}).state)) : '轮询 16s 仍读到旧值');
      updateRow('tasks', TID, {title: ORIG});
      flushQueue();
      return waitRow(TID, ORIG, 16000);
    }).then(function(got){
      log('毒消息回归后已把标题还原', got);
      return step7();
    });
  }

  /* 7) 表单入口门禁：点「＋ 新增 / ✏️ 编辑」先输密码；
        验过之后同一张表单里的「保存」凭票直通 —— 只输一次，但票据不跨表单、不跨入口 */
  function step7(){
    /* 先关掉「免重复输入」窗口，否则入口门禁会被直接放行，下面全是假绿（踩过） */
    try{ sessionStorage.removeItem('wb_pass_fresh_v1'); }catch(e){}

    var fnames = (window.FORM_GUARD || []).map(function(x){ return x[0]; });
    R.diag.formN = fnames.length;
    var fmiss = fnames.filter(function(n){ return !(App[n] && App[n].__gated); });
    log('FORM_GUARD 全部装上门禁（' + fnames.length + ' 个表单入口）',
        !!fnames.length && fnames.length >= 8 && fmiss.length === 0, fmiss.join(','));

    /* 反查：还有哪些 openXxx 没被包。openReport 是跳到研报页（只读），允许不包 */
    var obad = Object.keys(App).filter(function(n){
      return /^open/.test(n) && typeof App[n] === 'function';
    }).filter(function(n){ return !App[n].__gated && n !== 'openReport'; });
    R.diag.openUngated = obad;
    log('没有漏网的表单入口（openReport 是只读跳转，已排除）', obad.length === 0, obad.join(','));

    /* 7a) 新建入口：先弹密码；没验过不给开表单 */
    App.openTask(null);
    return waitFor(pOn, 6000).then(function(opened){
      log('点「＋ 新增任务」先弹密码层（不是直接开表单）', opened);
      /* ⚠️ 不能用 $('f-title') 判「表单没打开」—— closeModal() 只摘 #mask 的 class，
         #modal 里的旧表单 innerHTML 还留着，元素照样查得到。要看 #mask 到底亮没亮。 */
      log('★ 密码未通过时表单没有打开', !hasOn($('mask')));
      var go = $('dangerGo') ? String($('dangerGo').textContent) : '';
      R.diag.formBtn = go;
      log('入口档按钮文案是「确认并打开」（不是「确认新增」）', go.indexOf('打开') >= 0, go);
      App.cancelDanger();
      return sleep(500);
    }).then(function(){
      log('取消后密码层已关闭，也没有开表单', !pOn() && !hasOn($('mask')));
      return sleep(200);
    }).then(function(){
      /* 7b) 编辑入口：正确密码 → 表单打开；同一张表单里保存凭票直通 */
      App.openTask(TID);
      return waitFor(pOn, 6000);
    }).then(function(){
      typePass(PW);
      return waitFor(function(){ return !pOn(); }, 15000);
    }).then(function(){
      return sleep(600);
    }).then(function(){
      var h3 = $('modal') ? String(($('modal').querySelector('h3') || {}).textContent || '') : '';
      R.diag.formOpened = h3;
      log('正确密码 → 编辑表单已打开', h3.indexOf('编辑任务') >= 0 && !!$('f-title'), h3);
      R.diag.tick1 = {
        fresh: (typeof passFresh === 'function') ? passFresh() : 'n/a',
        inVal: $('f-title') ? String($('f-title').value).slice(0, 26) : 'NO-INPUT',
        maskOn: hasOn($('mask')),
        ticks: Object.keys(window.PASS_TICK || {}).join(',')
      };
      if($('f-title')) $('f-title').value = TICKT;
      R.diag.tick1b = qdump();
      App.saveTask(TID);
      return sleep(1500);
    }).then(function(){
      /* ★ updateRow 只是 enqueue 排队，真正落库靠 flushQueue 的异步 fetch。
         虚拟时钟下防抖定时器不可靠 —— 必须显式排空队列再读库，否则会得出「没生效」的假结论。 */
      return waitDrain(16000);
    }).then(function(drained){
      R.diag.drained = drained;
      R.diag.afterSave = qdump();
      var again = pOn();
      R.diag.ticketReuse = !again;
      R.diag.tick2 = {
        mem: (S.tasks.filter(function(t){ return t.id === TID; })[0] || {}).title,
        pend: (typeof PENDING !== 'undefined' && PENDING) ? PENDING.length : -1,
        tick: Object.keys(window.PASS_TICK || {}).join(','),
        mask: hasOn($('mask')),
        toast: (function(){
          var t = document.querySelector('.toast');
          return t ? String(t.textContent).slice(0, 50) : '';
        })()
      };
      log('★ 凭入口票据：同一张表单里点「保存」不再弹第二次', !again);
      if(again){ App.cancelDanger(); }
      return waitRow(TID, TICKT, 16000);
    }).then(function(got){
      log('★ 凭票保存真的写进了数据库', got,
          got ? '' : ('轮询 16s 仍读到旧值 · drained=' + R.diag.drained +
                      ' · ' + JSON.stringify(R.diag.afterSave || {})));
      updateRow('tasks', TID, {title: ORIG});
      flushQueue();
      return waitRow(TID, ORIG, 16000);
    }).then(function(got){
      log('已把标题还原（探针不留痕）', got);
      App.closeModal();
      return sleep(500);
    }).then(function(){
      /* 7c) 表单关掉 → 票据作废 */
      App.openTask(null);
      return waitFor(pOn, 6000).then(function(o){
        R.diag.ticketCleared = o;
        log('★ 关闭表单后票据作废：再点「＋ 新增任务」仍要输密码', o);
        if(o){ App.cancelDanger(); }
        return sleep(400);
      });
    }).then(function(){
      /* 7d) 票据不跨入口：验过「新增任务」后，点「＋ 新增计划」仍要输 */
      App.openTask(null);
      return waitFor(pOn, 6000);
    }).then(function(){
      typePass(PW);
      return waitFor(function(){ return !pOn(); }, 15000);
    }).then(function(){
      return sleep(500);
    }).then(function(){
      App.openWork(null);
      return waitFor(pOn, 6000).then(function(o){
        R.diag.ticketCross = o;
        log('★ 票据不跨入口：「新增任务」验过密码后点「＋ 新增计划」仍要输', o);
        if(o){ App.cancelDanger(); }
        return sleep(400);
      });
    }).then(function(){
      App.closeModal();
      return sleep(300);
    }).then(step8).then(step9);
  }

  /* 8) 密码不落盘 + 收尾 */
  function step8(){
    log('密码没有落到 localStorage / sessionStorage', scr().indexOf(PW) < 0);
    log('页面源码里不含密码明文', document.documentElement.outerHTML.indexOf(PW) < 0);
    /* 把「免重复输入」的放行窗口关掉，别给探针留后门 */
    try{ sessionStorage.removeItem('wb_pass_fresh_v1'); }catch(e){}
    /* ★★ 临时任务兜底清理 —— 必须**真删**，不能只改标题「标记一下」。
       业务表已收回 DELETE，页面内的删除走管理员 RPC；改标题只是留个记号，
       结果是垃圾留在用户的工作计划里。2026-09-14 真发生过：
       用户截图里躺着两条「PROBE 兜底删除」，只能手工清库。
       所以这里：① 先查库是否还在；② 在就兜底真删；③ 删不掉报 FAIL，别静默漏掉。 */
    return purgeTmp();
  }
  function purgeTmp(){
    return taskRow(TMP).then(function(r){
      if(!r){
        log('★★ 探针临时任务没有残留（库里查无此记录）', true);
        return null;
      }
      log('★★ 探针临时任务没有残留（库里查无此记录）', false,
          '创建后没删干净，正在兜底删除 ' + TMP);
      return rpc('wb_admin_delete_row',
                 {p_token: Auth.token, p_kind:'tasks', p_id: TMP, p_pass: PW})
        .then(function(res){ R.diag.purge = JSON.stringify(res); })
        .catch(function(e){ R.diag.purge = 'err:' + (e && e.message); })
        .then(function(){ return waitRowGone(TMP, 8000); })
        .then(function(gone){
          log('★★ 兜底删除确实生效（不是只改了个标题）', gone, gone ? '' : R.diag.purge);
        });
    });
  }

  /* 9) 自助注册普通管理员 → 超级管理员批准 → 普通管理员落到「投资标的」
     ⚠️ 这一步会把 Auth 切成新注册的普通管理员，所以必须放在最后。 */
  var REG   = 'probe_' + Date.now().toString(36);
  var REGPW = 'probe-pass-' + Date.now().toString(36);
  var SUPTOK = '', SUPUSER = '';

  function step9(){
    try{ sessionStorage.removeItem('wb_pass_fresh_v1'); }catch(e){}
    R.diag.regUser = REG;
    SUPTOK = Auth.token; SUPUSER = Auth.user; Auth.role = 'super'; authPersist();
    R.diag.supUser = SUPUSER;

    /* 9a) 登录门的注册入口与视图切换 */
    log('登录门有「注册普通管理员」入口',
        !!$('g-regbtn') && String($('g-regbtn').textContent).indexOf('注册') >= 0);
    App.gateToReg();
    log('点注册后切到注册视图（登录表单让位）',
        !!$('g-reg') && $('g-reg').style.display !== 'none' &&
        !!$('g-login') && $('g-login').style.display === 'none');
    App.gateToLogin();
    log('可以从注册视图返回登录视图',
        $('g-login').style.display !== 'none' && $('g-reg').style.display === 'none');

    /* 9b) 本地表单校验：非法输入不发请求、就地给提示 */
    App.gateToReg();
    $('r-user').value = 'Bad User!'; $('r-name').value = '探针测试员';
    $('r-pass').value = '123456';   $('r-pass2').value = '123456';
    App.doRegister();
    var e1 = String($('r-err').textContent);
    log('账号含非法字符被本地拦下', /账号/.test(e1), e1.slice(0, 40));

    $('r-user').value = REG; $('r-pass').value = '123'; $('r-pass2').value = '123';
    App.doRegister();
    var e2 = String($('r-err').textContent);
    log('密码太短被本地拦下', /6\s*位/.test(e2), e2.slice(0, 40));

    $('r-pass').value = REGPW; $('r-pass2').value = REGPW + 'x';
    App.doRegister();
    var e3 = String($('r-err').textContent);
    log('两次密码不一致被本地拦下', /不一致/.test(e3), e3.slice(0, 40));

    /* 9c) 正式提交 → 落库为「待批准」 */
    $('r-pass').value = REGPW; $('r-pass2').value = REGPW;
    $('r-note').value = '探针自测 · 可忽略';
    App.doRegister();
    return waitFor(function(){ return $('r-ok') && /on/.test($('r-ok').className); }, 16000)
      .then(function(ok){
        log('★ 提交注册后界面提示「等待超级管理员批准」', ok,
            $('r-ok') ? String($('r-ok').textContent).replace(/\s+/g, ' ').slice(0, 70) : '');
        return sleep(700);
      })
      .then(function(){ return rpc('wb_admin_list', {p_token:SUPTOK}); })
      .then(function(r){
        var row = ((r && r.rows) || []).filter(function(x){ return x.user_name === REG; })[0];
        R.diag.regRow = row ? (row.status + '/' + row.role) : '(not found)';
        log('★ 注册记录已落库，状态是「待批准」', !!row && row.status === 'pending', R.diag.regRow);
        log('★ 自助注册拿到的角色只能是普通管理员', !!row && row.role === 'ops', row ? row.role : '');
      })
      /* 9d) 未批准前登录被拒 */
      .then(function(){
        App.gateToLogin();
        $('g-user').value = REG; $('g-pass').value = REGPW;
        App.login();
        return waitFor(function(){
          var e = $('g-err'); return e && /批准/.test(String(e.textContent));
        }, 16000);
      }).then(function(shown){
        log('★ 未批准的账号登录被拒，提示等待批准', shown,
            shown ? String($('g-err').textContent).slice(0, 46) : '没出现预期提示');
        log('★ 未批准时没有被放进门', /(^|\s)on(\s|$)/.test($('loginGate').className));
        var p = $('g-pass'); if(p) p.value = '';
      })
      /* 9e) 超级管理员在设置页看到待批申请，走密码层批准 */
      .then(function(){
        Auth.token = SUPTOK; Auth.user = SUPUSER; Auth.role = 'super'; authPersist();
        gateHide(); App.go('set');
        return waitFor(function(){
          var b = $('admPending');
          return !!b && String(b.innerHTML).indexOf(REG) >= 0;
        }, 18000);
      }).then(function(seen){
        log('★ 超级管理员在「设置」看到待批申请', seen);
        /* 反向断言：收窄不能收窄到超管头上 —— 9 个版块一个都不能少
           （新增的「研究报告」也是 ext 项，超管同样只是跳出去） */
        var ids = [].map.call(document.querySelectorAll('#nav button'), function(x){ return x.getAttribute('data-p'); });
        R.diag.supNavN = ids.length;
        log('★ 超级管理员侧栏 9 个版块齐全', ids.length === 9, ids.join(','));
        log('★ 超管侧栏也有「研究报告」', ids.indexOf('research') >= 0, ids.join(','));
        var ohs = $('opsHint');
        log('超级管理员看不到「团队成员视图」提示',
            !ohs || window.getComputedStyle(ohs).display === 'none');
        App.admReview(REG, 'approve');
        return waitFor(pOn, 6000);
      }).then(function(opened){
        log('批准动作要求再输一次管理员密码', opened);
        log('批准不给「免重复输入」勾选框', !$('pv-keep'));
        return sleep(300);
      }).then(function(){
        typePass(PW);
        return waitFor(function(){
          var l = $('admList');
          return !pOn() && !!l && String(l.innerHTML).indexOf(REG) < 0;
        }, 18000);
      }).then(function(){ return rpc('wb_admin_list', {p_token:SUPTOK}); })
      .then(function(r){
        var row = ((r && r.rows) || []).filter(function(x){ return x.user_name === REG; })[0];
        R.diag.regRow2 = row ? row.status : '(not found)';
        log('★ 批准后账号状态变为「正常」', !!row && row.status === 'active', R.diag.regRow2);
      })
      /* 9f) 普通管理员登录 → 直接落在「投资标的」 */
      .then(function(){
        authClear(); gateShow();
        $('g-user').value = REG; $('g-pass').value = REGPW;
        App.login();
        return waitFor(function(){ return !/(^|\s)on(\s|$)/.test($('loginGate').className); }, 18000);
      }).then(function(){
        return sleep(900);
      }).then(function(){
        var pg = $('pg-stock');
        var on = !!pg && /(^|\s)on(\s|$)/.test(pg.className);
        R.diag.landing = on ? 'stock' : 'other';
        log('★ 普通管理员登录后直接落在「投资标的」', on);
        log('身份被识别为普通管理员', Auth.role === 'ops', Auth.role);
        var b = document.querySelector('#nav button[data-p="stock"]');
        log('侧边栏「投资标的」处于选中态', !!b && /(^|\s)on(\s|$)/.test(b.className));
        /* ★ 普通管理员侧栏 = 「投资标的」+「研究报告」+「数据与设置」。
           「研究报告」是团队共用的研报库（独立页面 research.html）；
           「数据与设置」**必须给**：那是唯一能改密码 / 退出登录的入口。 */
        var ids = [].map.call(document.querySelectorAll('#nav button'), function(x){ return x.getAttribute('data-p'); });
        R.diag.navIds = ids.join(',');
        log('★★ 普通管理员侧栏 = 投资标的 + 研究报告 + 数据与设置',
            ids.length === 3 && ids.indexOf('stock') >= 0 &&
            ids.indexOf('research') >= 0 && ids.indexOf('set') >= 0, R.diag.navIds);
        var tbi = [].map.call(document.querySelectorAll('#tabbar button'), function(x){ return x.getAttribute('data-tp'); });
        log('★ 手机底部 tab 同样是这三项',
            tbi.length === 3 && tbi.indexOf('research') >= 0, tbi.join(','));
        /* ★★ 「研究报告」是**独立页面**（用户明确要求「不要都放在 index 里」）：
           侧栏那一项必须渲染成 ext 跳转，而不是页内版块切换 */
        var rb = document.querySelector('#nav button[data-p="research"]');
        var rbo = rb ? String(rb.getAttribute('onclick') || '') : '';
        R.diag.researchBtn = rbo;
        log('★★ 侧栏「研究报告」渲染为独立页面跳转',
            /App\.ext\(['"]research\.html['"]\)/.test(rbo), rbo);
        /* App.go('research') 也必须走同一条跳转路径（console / 手改 hash 都拦得住），
           而不是去切一个不存在的页内 section */
        var hit = '';
        var origExt = App.ext;
        App.ext = function(u){ hit = String(u || ''); };
        try{ App.go('research'); }
        catch(e){ R.errs.push('App.go(research):' + (e && e.message || e)); }
        App.ext = origExt;
        R.diag.extHit = hit;
        log('★★ App.go(\'research\') 也走独立页面跳转', hit === 'research.html', hit);
        log('★ 研报库不在 index 的页内容器里（没有 pg-research 这个 section）', !$('pg-research'));
        var oh = $('opsHint');
        var os = oh ? window.getComputedStyle(oh).display : 'missing';
        R.diag.opsHint = os;
        log('★ 侧栏出现「团队成员视图」提示且可见',
            !!oh && os !== 'none' && String(oh.textContent).indexOf('团队成员') >= 0, os);
      })
      /* 9f2) ★★ 设置页：ops 能用「改密码 / 退出」，但看不到私人面板 */
      .then(function(){
        App.go('set');
        return sleep(700);
      }).then(function(){
        var onSet = /(^|\s)on(\s|$)/.test($('pg-set') ? $('pg-set').className : '');
        R.diag.opsSet = 'set-on=' + onSet;
        log('★ 普通管理员能进「数据与设置」', onSet, R.diag.opsSet);
        var ap = $('adminPanel') ? String($('adminPanel').innerHTML) : '';
        log('★★ 设置页里有「修改我的密码」按钮', ap.indexOf('修改我的密码') >= 0);
        log('★★ 设置页里有「退出登录」按钮', ap.indexOf('退出登录') >= 0);
        /* 私人面板：整卡隐藏 */
        var supCards = [].map.call(document.querySelectorAll('#pg-set [data-sup]'), function(x){
          return window.getComputedStyle(x).display; });
        R.diag.opsSupCards = supCards.join(',');
        log('★ 战略参数 / 数据管理 / 超管说明 三张私人卡全部隐藏',
            supCards.length >= 3 && supCards.every(function(d){ return d === 'none'; }), R.diag.opsSupCards);
        /* 隐藏不够 —— 内容也必须清空，否则 devtools 能读出来 */
        log('★ 私人参数面板的 DOM 已清空（不是只隐藏）',
            String($('profPanel') ? $('profPanel').innerHTML : 'x').trim() === '');
        log('★ 全库统计数据框的 DOM 已清空',
            String($('statBox') ? $('statBox').innerHTML : 'x').trim() === '');
        var so = [].map.call(document.querySelectorAll('#pg-set .supOnly'), function(x){
          return window.getComputedStyle(x).display; });
        log('★「初始化云端数据」按钮对 ops 隐藏（会往云端灌种子数据）',
            so.length >= 1 && so.every(function(d){ return d === 'none'; }), so.join(','));
        var ch = $('cardOpsHelp');
        var chd = ch ? window.getComputedStyle(ch).display : 'missing';
        log('★ 出现「使用说明（团队成员）」卡片', chd !== 'none' && chd !== 'missing', chd);
        var t1 = $('setTitle') ? String($('setTitle').textContent) : '';
        log('★ 页面标题对 ops 改写为「我的账号」', t1.indexOf('账号') >= 0, t1);
        /* 改密码表单真的能打开 */
        try{ App.openChangePass(window.PASS_OK); }catch(e){ R.errs.push('openChangePass:' + String(e && e.message || e)); }
        return sleep(500);
      }).then(function(){
        log('★「修改我的密码」表单能打开（含当前密码 / 新密码 / 确认新密码三个输入框）',
            !!$('cp-old') && !!$('cp-new') && !!$('cp-new2'));
        log('改密码表单里没有把密码明文塞进 DOM 属性',
            !!$('cp-old') && $('cp-old').getAttribute('value') === null);
        try{ App.closeModal(); }catch(e){}
        /* ★ 越权跳转仍然拦住：总览 / 复盘日志都是私人工作区 */
        App.go('dash');
        return sleep(700);
      }).then(function(){
        log('★ App.go(\'dash\') 被拒：总览（私人工作区）不可见',
            !/(^|\s)on(\s|$)/.test($('pg-dash') ? $('pg-dash').className : ''));
        App.go('log');
        return sleep(700);
      }).then(function(){
        log('★ App.go(\'log\') 被拒：复盘日志不可见',
            !/(^|\s)on(\s|$)/.test($('pg-log') ? $('pg-log').className : ''));
        App.go('set');
        return sleep(600);
      }).then(function(){
        /* 纵深防御：就算绕过导航直接渲染设置页，也不该出现超管专属控件 */
        try{ renderAdminPanel(); }catch(e){ R.errs.push('renderAdminPanel(ops):' + String(e && e.message || e)); }
        return sleep(1500);
      }).then(function(){
        var h = $('adminPanel') ? String($('adminPanel').innerHTML) : '';
        log('★ 普通管理员看不到「＋ 新增管理员」按钮', h.indexOf('新增管理员') < 0);
        log('普通管理员的角色显示为「普通管理员」', h.indexOf('普通管理员') >= 0);
        log('普通管理员没有审批区块 #admPending', !$('admPending'));
      })
      /* 9g) 服务端权限闸门：普通管理员提权 / 读待批都该被拒 */
      .then(function(){
        return rpc('wb_admin_create', {p_token:Auth.token, p_user:'probe_shouldfail',
                                       p_pass:'123456', p_name:'x'});
      }).then(function(r){
        R.diag.opsCreate = r ? (r.code || r.msg) : '(null)';
        log('★ 普通管理员调「新增账号」被服务端拒绝',
            !!r && !r.ok && r.code === 'NOPERM', R.diag.opsCreate);
        return rpc('wb_admin_pending_list', {p_token:Auth.token});
      }).then(function(r){
        R.diag.opsPending = r ? (r.code || r.msg) : '(null)';
        log('★ 普通管理员读「待批申请」被服务端拒绝',
            !!r && !r.ok && r.code === 'NOPERM', R.diag.opsPending);
        return rpc('wb_admin_delete', {p_token:Auth.token, p_user:SUPUSER});
      }).then(function(r){
        log('★ 普通管理员调「删除账号」被服务端拒绝',
            !!r && !r.ok && r.code === 'NOPERM', r ? (r.code || r.msg) : '(null)');
        return rpc('wb_admin_list', {p_token:Auth.token});
      }).then(function(r){
        var n = ((r && r.rows) || []).length;
        R.diag.opsListN = n;
        log('★ 普通管理员的账号列表只含自己（看不到其他成员）', n === 1, 'rows=' + n);
      })
      /* 9h) 清理测试账号（用超级管理员会话，探针不留痕） */
      .then(function(){ return rpc('wb_admin_delete', {p_token:SUPTOK, p_user:REG}); })
      .then(function(r){
        R.diag.regClean = r ? (r.ok ? 'ok' : (r.code || r.msg)) : '(null)';
        log('注册流程后密码仍未落到本机存储', scr().indexOf(REGPW) < 0);
        try{ sessionStorage.removeItem('wb_pass_fresh_v1'); }catch(e){}
        R.stage = 'done';
      });
  }

  (function poll(){
    if(window.App && window.RAW && window.WRITE_GUARD){
      R.stage = 'running';
      main()['catch'](function(e){ R.errs.push('main:' + String(e && e.message || e)); R.stage = 'throw'; })
            .then(function(){
              if(R.stage !== 'done') R.stage = R.stage === 'throw' ? 'throw' : 'done';
              $('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R);
            });
      return;
    }
    setTimeout(poll, 120);
  })();
})();
</script>
'''

# ============================================================ 研报页探针
RPT_PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
''' + WB_COMMON + r'''
  var MID = '', ORIG_T = '', NEW_T = 'PROBE-模块标题';
  var NEWID = '', TICKT2 = 'PROBE-票据模块标题';
  function modRow(id){
    return api('wb_report_mods?id=eq.' + encodeURIComponent(id) + '&select=id,title')
      .then(function(r){ return (r && r[0]) || null; });
  }
  /* 写入是异步 fetch：一律轮询到期望值出现，别用固定 sleep 抢跑（踩过） */
  function waitMod(id, want, ms){
    var t0 = Date.now();
    return new Promise(function(res){
      (function p(){
        modRow(id).then(function(r){
          if(r && r.title === want) return res(true);
          if(Date.now() - t0 > (ms || 15000)) return res(false);
          setTimeout(p, 250);
        })['catch'](function(){ setTimeout(p, 250); });
      })();
    });
  }
  function typePass(v){ var i = $('rpPass'); if(i) i.value = v; Rpt.confirmPass(); }

  function coverage(){
    var names = (window.RGATE || []).map(function(x){ return x[0]; });
    R.diag.gateN = names.length;
    var miss = names.filter(function(n){ return !(Rpt[n] && Rpt[n].__gated); });
    log('RGATE 全部装上门禁（' + names.length + ' 个写入口）',
        !!names.length && names.length >= 7 && miss.length === 0, miss.join(','));
    R.diag.gateList = names.slice();
    ['delMod','delChart','delReport'].forEach(function(n){
      log('删除类走原有 askPass（' + n + ' 存在且在 Rpt 上）', typeof Rpt[n] === 'function');
    });
  }

  function main(){
    try{ sessionStorage.removeItem('rpt_pass_fresh_v1'); }catch(e){}   /* profile 复用：先清放行窗口 */
    try{ localStorage.removeItem('wb_pass_h_v1'); }catch(e){}
    Auth.token = TOK; Auth.user = 'probe'; Auth.role = 'super';
    R.diag.code = St.code;
    R.diag.mods = St.mods.length;
    coverage();
    if(!St.mods.length){ log('有可测模块', false, 'St.mods 为空'); return Promise.resolve(); }
    MID = String(St.mods[0].id); ORIG_T = String(St.mods[0].title || '');
    R.diag.target = MID + ' / ' + ORIG_T;
    return step1();
  }

  /* 1) 进入编辑模式要密码；取消 → 仍是只读 */
  function step1(){
    Rpt.toggleEdit();
    return waitFor(rpOn, 6000).then(function(opened){
      log('点「编辑数据」弹出密码层', opened);
      Rpt.cancelPass();
      return sleep(500);
    }).then(function(){
      log('取消后没有进入编辑模式', !St.edit, 'St.edit=' + St.edit);
      return step2();
    });
  }

  /* 2) 正确密码 → 进入编辑模式 */
  function step2(){
    Rpt.toggleEdit();
    return waitFor(rpOn, 6000).then(function(){
      var noKeep = !$('rpKeep');
      log('「进入编辑模式」是开启动作：可勾免重复输入', !noKeep);
      if($('rpKeep')) $('rpKeep').checked = false;   /* 本步不启用免重复，后面要验删除 */
      typePass(PW);
      return waitFor(function(){ return !rpOn(); }, 15000);
    }).then(function(){
      return sleep(600);
    }).then(function(){
      log('正确密码 → 已进入编辑模式', !!St.edit, 'St.edit=' + St.edit);
      return step3();
    });
  }

  /* 3) 保存模块：取消 → 库不变；正确密码 → 库变 */
  function step3(){
    Rpt.openMod(MID);
    return sleep(700).then(function(){
      var t = $('m-title');
      R.diag.hasTitleInput = !!t;
      log('模块编辑表单已打开（#m-title 在位）', !!t);
      if(t) t.value = NEW_T;
      Rpt.svMod();
      return waitFor(rpOn, 6000);
    }).then(function(opened){
      log('点「保存模块」弹出密码层', opened);
      var kept = !!$('m-title') && String($('m-title').value) === NEW_T;
      log('★ 密码层没有清掉抽屉里的表单', kept, $('m-title') ? String($('m-title').value).slice(0, 30) : '没了');
      Rpt.cancelPass();
      return sleep(600);
    }).then(function(){
      return modRow(MID);
    }).then(function(row){
      log('取消后数据库里模块标题未变', row && row.title === ORIG_T, row && row.title);
      /* 再来一次：这次输对 */
      Rpt.svMod();
      return waitFor(rpOn, 6000);
    }).then(function(){
      typePass(PW);
      return waitFor(function(){ return !rpOn(); }, 15000);
    }).then(function(){
      return waitMod(MID, NEW_T, 16000);
    }).then(function(got){
      log('正确密码 → 模块标题真的写进数据库了', got, got ? '' : '轮询 16s 仍读到旧值');
      return step4();
    });
  }

  /* 4) 还原标题 + 删除类不给勾选框 + 密码不落盘 */
  function step4(){
    var t = $('m-title');
    if(t) t.value = ORIG_T;
    Rpt.svMod();
    return waitFor(rpOn, 6000).then(function(){
      var keepBox = !!$('rpKeep');
      var go = $('rpGo') ? String($('rpGo').textContent) : '';
      log('可逆的「保存模块」提供免重复输入勾选框', keepBox && go.indexOf('保存') >= 0, go);
      /* ★ 排版回归（研报页同款）：文字必须在单个 <span> 里，否则被 flex 拆成三列 */
      var rl = $('rpKeep') ? $('rpKeep').parentElement : null;
      var rspans = rl ? rl.querySelectorAll(':scope > span') : [];
      var rtxt = rspans.length === 1 ? rspans[0].textContent : '';
      var rloose = '';
      if(rl){ for(var ci = 0; ci < rl.childNodes.length; ci++){
        var cn = rl.childNodes[ci];
        if(cn.nodeType === 3 && cn.textContent.trim()) rloose += cn.textContent.trim();
      } }
      R.diag.keepWrap = {spans: rspans.length, loose: rloose, txt: rtxt.slice(0, 60)};
      log('★ 研报页勾选框文字是整体一项（不会被 flex 拆成三列）',
          rspans.length === 1 && rloose === '' &&
          rtxt.indexOf('免重复输入') >= 0 &&
          rtxt.indexOf('删除、覆盖导入仍需输入') >= 0 &&
          rtxt.indexOf('）') >= 0,
          'spans=' + rspans.length + ' loose=[' + rloose + ']');
      typePass(PW);
      return waitFor(function(){ return !rpOn(); }, 15000);
    }).then(function(){
      return waitMod(MID, ORIG_T, 16000);
    }).then(function(got){
      log('模块标题已还原（探针不留痕）', got, got ? '' : '轮询 16s 未落到库');
      /* 删除模块：不可逆 → 不该有免重复输入勾选框 */
      Rpt.delMod(MID);
      return waitFor(rpOn, 6000);
    }).then(function(opened){
      log('「删除模块」弹出密码层', opened);
      var noKeep = !$('rpKeep');
      var go = $('rpGo') ? String($('rpGo').textContent) : '';
      R.diag.delBtn = go;
      log('删除不可逆：不提供免重复输入勾选框', noKeep && go.indexOf('删除') >= 0, go);
      Rpt.cancelPass();
      return sleep(500);
    }).then(function(){
      return modRow(MID);
    }).then(function(row){
      log('取消删除后模块仍在', !!row);
      return step5();
    });
  }

  /* 5) 入口票据：＋新增模块 验过密码后，同一抽屉里的「保存模块」不再弹第二次；
        抽屉一关票据作废；探测完把这个探针模块真删掉，不留痕。 */
  function step5(){
    try{ sessionStorage.removeItem('rpt_pass_fresh_v1'); }catch(e){}   /* 排除免重复窗口造成假绿 */
    var before = St.mods.length;
    R.diag.modsBefore = before;
    Rpt.addMod();
    return waitFor(rpOn, 6000).then(function(opened){
      log('点「＋ 新增模块」先弹密码层（不是直接新建）', opened);
      Rpt.cancelPass();
      return sleep(600);
    }).then(function(){
      var noNew = St.mods.length === before;
      log('★ 密码未通过时不新建模块', noNew, 'mods=' + St.mods.length);
      Rpt.addMod();
      return waitFor(rpOn, 6000);
    }).then(function(){
      typePass(PW);
      return waitFor(function(){ return !rpOn(); }, 15000);
    }).then(function(){
      return waitFor(function(){ return !!UI.selMod && !!$('m-title'); }, 9000);
    }).then(function(){
      var ok = !!UI.selMod && !!$('m-title');
      NEWID = String(UI.selMod || '');
      R.diag.tickMod = {sel: NEWID, has: !!$('m-title'),
                        ticks: Object.keys(window.RTICK || {}).join(',')};
      log('正确密码 → 新模块已建立并打开抽屉', ok, NEWID);
      if($('m-title')) $('m-title').value = TICKT2;
      Rpt.svMod();
      return sleep(1600);
    }).then(function(){
      var again = rpOn();
      R.diag.ticketReuse = !again;
      R.diag.tickMod2 = {again: again, ticks: Object.keys(window.RTICK || {}).join(',')};
      log('★ 凭入口票据：同一张抽屉里点「保存模块」不再弹第二次', !again);
      if(again) Rpt.cancelPass();
      return waitMod(NEWID, TICKT2, 16000);
    }).then(function(got){
      log('★ 凭票保存真的写进了数据库', got, got ? '' : '轮询 16s 仍读到旧值');
      Rpt.closeDrawer();                       /* 关抽屉 → 票据作废 */
      return sleep(500);
    }).then(function(){
      Rpt.addMod();
      return waitFor(rpOn, 6000).then(function(o){
        R.diag.ticketCleared = o;
        log('★ 关闭抽屉后票据作废：再点「＋ 新增模块」仍要输密码', o);
        if(o) Rpt.cancelPass();
      });
    }).then(function(){
      return sleep(400);
    }).then(function(){
      /* 收尾：把刚才凭票保存的那个探针模块真删掉（顺带验一次完整删除链路） */
      Rpt.delMod(NEWID);
      return waitFor(rpOn, 6000);
    }).then(function(o){
      log('删除探针模块：弹出密码层', o);
      typePass(PW);
      return waitFor(function(){ return !rpOn(); }, 15000);
    }).then(function(){
      return waitFor(function(){ return St.mods.length === before; }, 12000);
    }).then(function(gone){
      log('探针模块已清除（内存与数据库都回到 ' + before + ' 个）', gone, 'mods=' + St.mods.length);
      log('密码没有落到 localStorage / sessionStorage', scr().indexOf(PW) < 0);
      log('页面源码里不含密码明文', document.documentElement.outerHTML.indexOf(PW) < 0);
      try{ sessionStorage.removeItem('rpt_pass_fresh_v1'); }catch(e){}
      R.stage = 'done';
    });
  }

  (function poll(){
    if(window.Rpt && window.RGATE && window.St && St.code){
      R.stage = 'running';
      main()['catch'](function(e){ R.errs.push('main:' + String(e && e.message || e)); R.stage = 'throw'; })
            .then(function(){
              if(R.stage !== 'done') R.stage = R.stage === 'throw' ? 'throw' : 'done';
              $('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R);
            });
      return;
    }
    setTimeout(poll, 120);
  })();
})();
</script>
'''


def node_check(probe, tag):
    a = probe.index('<script>') + 8
    core = probe[a:probe.index('</script>', a)]
    tmp = os.path.join(BUILD, '_tmp_gate.js')
    open(tmp, 'w', encoding='utf-8').write(core)
    c = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
    # 不删：文件名固定，下轮覆盖。删除会累计触发 safe-delete 守卫。详见 check_static.py 注释。
    if c.returncode:
        print('探针语法错误 [%s]：\n%s' % (tag, (c.stderr or '')[-1500:]))
        return False
    return True


def run(page, probe, prof_name, port, tok, pwd, budget, extra=''):
    src = open(os.path.join(DEPLOY, page), encoding='utf-8').read()
    body_end = src.rfind('</body>')
    app_i = src.rfind('<script', 0, body_end)
    # ★ 预注入（必须在应用脚本**之前**）：固定 profile 会残留上一轮的登录态，
    #   而上一轮结尾以「已被删除的临时 ops 账号」的 token 收尾 —— 那个 token 必然失效。
    #   启动校验回 not-ok → forceRelogin() → 把探针随后设好的 Auth 一并清掉，
    #   症状是「密码怎么输都说不通过」→ 票据不开、写入被拦 → 成片假失败（26 项，踩过两次）。
    #   让页面从「未登录」这个干净状态起步，探针再自己设 token，跑多少轮结果都一样。
    pre = ("<script>try{localStorage.removeItem('wb_auth_v1');"
           "sessionStorage.removeItem('wb_auth_v1');}catch(e){}</script>\n")
    src = src[:app_i] + pre + src[app_i:body_end] + probe + '\n' + src[body_end:]
    out = os.path.join(DEPLOY, '_probe_gate_%s.html' % prof_name)
    open(out, 'w', encoding='utf-8').write(src)

    os.chdir(DEPLOY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', port), Quiet)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    prof = os.path.join(BUILD, '_prof_gate_' + prof_name)
    # ⚠️ 不删 profile 目录：批量删除会被环境的 safe-delete 守卫拦下。
    #    改成「复用固定 profile + 探针开头主动清掉遗留状态」，效果等价。
    if not os.path.isdir(prof):
        os.makedirs(prof, exist_ok=True)
    url = ('http://127.0.0.1:%d/_probe_gate_%s.html?t=%s&p=%s%s'
           % (port, prof_name, tok, pwd, extra))
    cmd = [edge_path(), '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=1680,1050', '--user-data-dir=' + prof,
           '--virtual-time-budget=%d' % budget, '--dump-dom', url]
    r = subprocess.run(cmd, capture_output=True, timeout=1200)
    httpd.shutdown()
    # ★ 不删探针页，就地清空：token 在文件里，清空即可达到同样的安全性，
    #   而删除会累计触发 safe-delete 守卫（见 check_static.py 注释）。
    try:
        open(out, 'w', encoding='utf-8').close()
    except OSError:
        pass
    dom = r.stdout.decode('utf-8', 'ignore')
    m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)
    if not m:
        # 落盘前先把密码/token 抹掉，避免把敏感串写进文件
        safe = dom.replace(pwd, '***').replace(tok, '***')
        p = os.path.join(BUILD, '_probe_gate_%s_dom.txt' % prof_name)
        open(p, 'w', encoding='utf-8').write(safe)
        print('[FAIL] %s 探针没回传，DOM 存 %s' % (page, p))
        return None
    return json.loads(_h.unescape(m.group(1)))


def report(d, title):
    print('\n  -- %s 诊断 --' % title)
    print('     diag: %s' % json.dumps(d.get('diag') or {}, ensure_ascii=False)[:2200])
    if d.get('errs'):
        print('     ⚠️ JS 错误 %d 条：%s' % (len(d['errs']), d['errs'][:4]))
    for s in d.get('steps', []):
        chk(s['n'], s['ok'], s['x'] if not s['ok'] else '')
    chk('%s 零 JS 错误' % title, not d.get('errs'), (d.get('errs') or [])[:3])
    return d.get('stage') == 'done'


def main():
    print('[1] 取服务端会话 token …')
    tok = admin_token()
    print('    token 前缀 %s…（长度 %d）' % (tok[:8], len(tok)))
    pwd = PW

    allok = True
    for page, probe, tag, port, budget in [
            ('index.html', WB_PROBE, 'wb', 8951, 240000),
            ('report.html', RPT_PROBE, 'rpt', 8952, 240000)]:
        if not node_check(probe, tag):
            return 1
        extra = ('&code=' + RPT_CODE) if tag == 'rpt' else ''
        print('\n[2] 跑 %s%s …（探针已清空、node --check 通过）' % (page, extra))
        d = run(page, probe, tag, port, tok, pwd, budget, extra)
        if d is None:
            allok = False
            print('    ✗ %s 没有回传结果' % page)
            continue
        if not report(d, tag):
            allok = False

    # 兜底：探针若在注册流程中途失败，会留下 probe_ 开头的待批准账号
    print('\n[3] 兜底清理探针残留账号 …')
    cleanup_probe_accounts(tok)

    print('\n' + '=' * 78)
    print('通过 %d 项 · 失败 %d 项' % (OK[0], FAIL[0]))
    print('=' * 78)
    return 0 if (FAIL[0] == 0 and allok) else 1


if __name__ == '__main__':
    sys.exit(main())
