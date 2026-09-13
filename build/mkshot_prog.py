# -*- coding: utf-8 -*-
"""进度显示修复 · 截图目视
生成两张图：1) 三种状态的卡片对比  2) 编辑弹窗里的状态/进度联动提示
"""
import os, re, subprocess, tempfile, shutil

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(ROOT, 'deploy', 'index.html')
OUT = os.path.join(ROOT, 'build')
PROBE = os.path.join(OUT, 'probe_shot.html')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

SEED = r'''
S.works = [
  {id:'s1',horizon:'今天',title:'今天完成投研框架的Web页面框架架构',status:'drop',progress:100,
   priority:'P0',category:'其他',detail:'完成框架结构模版，并且测试添加一个公司',
   start_date:'2026-09-13',due_date:'2026-09-13',sort:1},
  {id:'s2',horizon:'今天',title:'完成首矿交割的全部前置法务核查',status:'done',progress:100,
   priority:'P0',category:'战略',detail:'交割前把权属、环保、税务三项核查一次性做完',
   start_date:'2026-09-10',due_date:'2026-09-12',sort:2},
  {id:'s3',horizon:'今天',title:'搭建标的筛选打分模型 v1',status:'doing',progress:40,
   priority:'P1',category:'研究',detail:'先用已有的 12 个标的跑通权重与打分口径',
   start_date:'2026-09-12',due_date:'2026-09-18',sort:3},
  {id:'s4',horizon:'今天',title:'拟定与矿权方的第一次正式会谈议题',status:'todo',progress:0,
   priority:'P2',category:'人脉',start_date:'2026-09-14',due_date:'2026-09-20',sort:4}
];
'''

CSS_HACK = r'''
  <style id="shot-hack">
    #pg-dash,#pg-plan,#pg-permit,#pg-res,#pg-log,#pg-set{display:none!important}
    .localBar{display:none!important}
    .gate{display:none!important}
  </style>
'''

s = open(SRC, encoding='utf-8').read()
s = s.replace('backdrop-filter:', 'backdrop-filter-disabled:', 1)  # 关掉唯一的模糊，headless 下会糊

def build(mode, extra_js):
    h = s.replace('</head>', CSS_HACK + '</head>', 1)
    h = h.replace('</body>', '<script>setTimeout(function(){try{' + SEED + extra_js +
                  '}catch(e){document.title="ERR"+e.message;}},1000);</script>\n</body>', 1)
    open(PROBE, 'w', encoding='utf-8').write(h)

def shot(mode, js, png, w, hh):
    build(mode, js)
    prof = tempfile.mkdtemp(prefix='shot_prof_')
    try:
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--user-data-dir=' + prof, '--window-size=%d,%d' % (w, hh),
                        '--virtual-time-budget=6000',
                        '--screenshot=' + os.path.join(OUT, png),
                        'file:///' + PROBE.replace('\\', '/')],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    p = os.path.join(OUT, png)
    print(('[OK]  ' if os.path.exists(p) else '[FAIL]') + ' ' + png +
          ('  %d KB' % (os.path.getsize(p) // 1024) if os.path.exists(p) else ''))

# 1) 卡片对比
shot('list',
     "App.go('work'); UI.workTab='horizon'; UI.workHz='今天'; renderWork();"
     "document.querySelectorAll('.wrap,.main,.content').forEach(function(e){e.style.maxWidth='1180px';e.style.margin='0 auto';});",
     'v_prog_list.png', 1420, 1080)

# 2) 编辑弹窗（用超高视口一次截全，让「状态 / 进度 %」字段可见）
shot('modal',
     "App.go('work'); UI.workTab='horizon'; UI.workHz='今天'; renderWork(); App.openWork('s1');"
     "var md=document.getElementById('modal');"
     "md.style.maxHeight='none'; md.style.overflow='visible';"
     "var mk=document.getElementById('mask'); mk.style.alignItems='flex-start'; mk.style.paddingTop='16px';",
     'v_prog_modal.png', 1420, 2500)
