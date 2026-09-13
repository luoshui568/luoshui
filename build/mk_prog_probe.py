# -*- coding: utf-8 -*-
"""进度显示修复 · 真实渲染探针
把三种状态（已放弃/已完成/推进中）的记录注进工作台，跑真实渲染函数，
再从 headless Edge 的 document.title 读回结果。
"""
import os, re, subprocess, tempfile, json, shutil

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(ROOT, 'deploy', 'index.html')
PROBE = os.path.join(ROOT, 'build', 'probe_prog.html')

EDGES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]

TEST_JS = r'''
setTimeout(function(){
  var R = {};
  try{
    R.eff = [
      effProgress({status:'drop',progress:100}),
      effProgress({status:'done',progress:0}),
      effProgress({status:'doing',progress:100}),
      effProgress({status:'doing',progress:40}),
      effProgress({status:'todo',progress:80}),
      effProgress({status:'hold',progress:60})
    ];
    R.pfs = [
      progressForStatus('drop',100),
      progressForStatus('done',30),
      progressForStatus('doing',100),
      progressForStatus('doing',40),
      progressForStatus('hold',100)
    ];
    S.works = [
      {id:'p1',horizon:'ZZ',title:'ZZTEST_drop',status:'drop',progress:100,priority:'P0',category:'other',start_date:'2026-09-13',due_date:'2026-09-13',sort:1},
      {id:'p2',horizon:'ZZ',title:'ZZTEST_done',status:'done',progress:100,priority:'P1',category:'other',sort:2},
      {id:'p3',horizon:'ZZ',title:'ZZTEST_doing',status:'doing',progress:40,priority:'P1',category:'other',sort:3}
    ];
    UI.workTab='horizon'; UI.workHz='ZZ';
    renderWork();
    var h = $('workBox').innerHTML;
    R.hasDropTxt   = h.indexOf('\u5df2\u653e\u5f03\uff08\u8fdb\u5ea6\u4e0d\u8ba1\uff09')>=0;
    R.hasDoneTxt   = h.indexOf('\u2705 \u5df2\u5b8c\u6210')>=0;
    R.hasDoingTxt  = h.indexOf('\u8fdb\u5ea6 40%')>=0;
    R.hasBarDrop   = h.indexOf('bar bar-drop')>=0;
    R.hasBarDone   = h.indexOf('bar bar-done')>=0;
    R.hasDropCls   = h.indexOf('class="wcrd drop"')>=0;
    R.noStale100   = h.indexOf('\u8fdb\u5ea6 100%')<0;
    /* drop 卡片的进度条宽度必须是 0 */
    var m = h.match(/bar-drop"><i style="width:(\d+)%"/);
    R.dropWidth = m? +m[1] : -1;
    var st = horizonStats('ZZ');
    R.hz = {n:st.n, d:st.d, live:st.live, drop:st.drop, avg:st.avg, pct:st.pct};
    R.workSub = ($('workSub')||{}).textContent || '';
    /* 编辑弹窗里的状态+进度联动 */
    App.openWork('p1');
    R.modalProg  = ($('w-prog')||{}).value;
    R.modalStat  = ($('w-status')||{}).value;
    R.modalOpts  = (function(){ var e=$('w-status'); return e? [].slice.call(e.options).map(function(o){return o.text;}) : []; })();
    R.modalSelTx = (function(){ var e=$('w-status'); if(!e) return ''; for(var i=0;i<e.options.length;i++){ if(e.options[i].selected) return e.options[i].text; } return ''; })();
    App.closeModal();
    /* 课表任务弹窗的状态下拉 */
    if(S.tasks && S.tasks.length){
      App.openTask(S.tasks[0].id);
      R.taskOpts = (function(){ var e=$('f-status'); return e? [].slice.call(e.options).map(function(o){return o.text;}) : []; })();
      App.closeModal();
    }
  }catch(e){ R.err = String((e && e.message) || e); }
  R.jsErr = (window.__err||[]).slice(0,4);
  document.title = 'PROBE' + JSON.stringify(R);
}, 1000);
'''

s = open(SRC, encoding='utf-8').read()

# window.onerror 必须注入到 <head>（否则注册晚于主脚本，拿到的是假绿）
s = s.replace('</head>', '<script>window.__err=[];window.onerror=function(m,u,l,c,e){window.__err.push(String(m)+" @"+l+":"+c);};</script>\n</head>', 1)
s = s.replace('</body>', '<script>' + TEST_JS + '</script>\n</body>', 1)
open(PROBE, 'w', encoding='utf-8').write(s)

edge = next((e for e in EDGES if os.path.exists(e)), None)
if not edge:
    raise SystemExit('找不到 msedge.exe')

prof = tempfile.mkdtemp(prefix='prog_prof_')
try:
    r = subprocess.run([
        edge, '--headless=new', '--disable-gpu', '--no-sandbox',
        '--user-data-dir=' + prof, '--virtual-time-budget=9000',
        '--dump-dom', 'file:///' + PROBE.replace('\\', '/')
    ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    m = re.search(r'<title>PROBE(.*?)</title>', r.stdout or '', re.S)
    if not m:
        print('未取到探针结果，dom 前 600 字：')
        print((r.stdout or '')[:600])
        raise SystemExit(1)
    d = json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&'))

    exp_eff = [0, 100, 90, 40, 0, 60]
    exp_pfs = [0, 100, 90, None, 90]
    ok = True

    def chk(tag, good, got=''):
        global ok
        if not good:
            ok = False
        print(('[OK]  ' if good else '[FAIL]') + ' ' + tag + (('   got=' + str(got)) if got != '' else ''))

    chk('effProgress 映射正确', d.get('eff') == exp_eff, d.get('eff'))
    chk('progressForStatus 映射正确', d.get('pfs') == exp_pfs, d.get('pfs'))
    chk('卡片改「已放弃（进度不计）」', d.get('hasDropTxt'), d.get('hasDropTxt'))
    chk('卡片保留「已完成」', d.get('hasDoneTxt'), d.get('hasDoneTxt'))
    chk('推进中仍显示「进度 40%」', d.get('hasDoingTxt'), d.get('hasDoingTxt'))
    chk('drop 卡走灰色进度条', d.get('hasBarDrop'), d.get('hasBarDrop'))
    chk('done 卡走绿色进度条', d.get('hasBarDone'), d.get('hasBarDone'))
    chk('drop 卡有 drop 类（灰化）', d.get('hasDropCls'), d.get('hasDropCls'))
    chk('★ 全页不再出现「进度 100%」', d.get('noStale100'), d.get('noStale100'))
    chk('★ drop 进度条宽度 = 0', d.get('dropWidth') == 0, d.get('dropWidth'))
    hz = d.get('hz') or {}
    chk('统计 n=3 / 完成 1 / 有效 2 / 放弃 1', (hz.get('n'), hz.get('d'), hz.get('live'), hz.get('drop')) == (3, 1, 2, 1), hz)
    chk('平均进度 = 70（(100+40)/2，放弃不计）', hz.get('avg') == 70, hz.get('avg'))
    chk('完成率 = 50%（1/2，放弃不计）', hz.get('pct') == 50, hz.get('pct'))
    chk('副标题含「已放弃 1 项」', '已放弃 1 项' in (d.get('workSub') or ''), d.get('workSub'))
    chk('编辑弹窗读到状态 drop', d.get('modalStat') == 'drop', d.get('modalStat'))
    chk('★ 弹窗状态下拉显示「已放弃」', d.get('modalSelTx') == '已放弃', d.get('modalSelTx'))
    chk('★ 弹窗状态下拉选项全中文', d.get('modalOpts') == ['待启动', '推进中', '已完成', '挂起', '已放弃'], d.get('modalOpts'))
    chk('★ 课表状态下拉选项全中文', d.get('taskOpts') == ['待办', '进行中', '已完成', '已跳过'], d.get('taskOpts'))
    chk('JS 运行无报错', not d.get('err') and not d.get('jsErr'), str(d.get('err')) + str(d.get('jsErr')))
    print()
    print('=' * 46)
    print('全部通过' if ok else '存在失败项')
    print('=' * 46)
finally:
    shutil.rmtree(prof, ignore_errors=True)
