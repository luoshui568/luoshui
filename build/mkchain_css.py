# -*- coding: utf-8 -*-
"""把「产业链全景图」的样式追加进 build/report_theme.css（幂等，用标记块替换）。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSSP = os.path.join(HERE, 'report_theme.css')

MARK = '/* ===== 产业链全景图（上中下游泳道 + 比例尺） ===== */'

BLOCK = MARK + """
  /* 容器 */
  .iflow{margin:12px 0 8px;border:1px solid #f7eaec;border-radius:14px;
    padding:12px 12px 8px;background:linear-gradient(180deg,#fffbfc,#fff);}
  .if-legend{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px;}
  .if-lg{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:#5b3a40;
    border:1px solid #f2dfe2;border-radius:999px;padding:4px 10px;background:#fffafb;line-height:1.4;}
  .if-lg b{font-weight:800;color:#a3122a;}
  .if-lg-up{border-color:#f0ccd2;background:#fdf3f4;}
  .if-lg-mid{border-color:#e8c6cc;background:#fbeef0;}
  .if-lg-down{border-color:#dfc0c6;background:#f9e9ec;}
  .if-lg-hint{margin-left:auto;color:#9c9ca1;border-style:dashed;}
  .if-scroll{overflow-x:auto;overflow-y:hidden;}
  .if-svg{display:block;width:100%;min-width:740px;height:auto;}

  /* 悬停聚焦：进入图内先把所有环节压暗，指向谁谁亮起 */
  .iflow .nd,.iflow .cp,.iflow .ln{transition:opacity .18s ease,filter .18s ease;}
  .iflow:hover .nd,.iflow:hover .cp{opacity:.55;}
  .iflow .nd:hover,.iflow .cp:hover{opacity:1;
    filter:drop-shadow(0 5px 12px rgba(200,16,46,.30));}
  .iflow .nd,.iflow .cp{cursor:help;}

  /* 三段比例尺 */
  .ifbars{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0 6px;}
  .ifb{border:1px solid #f2dfe2;border-radius:12px;padding:11px 13px 12px;
    background:linear-gradient(160deg,#fff,#fffafb);min-width:0;}
  .ifb-h{font-size:12.5px;font-weight:800;color:#a3122a;margin-bottom:9px;
    padding-bottom:7px;border-bottom:1px dashed #f2dfe2;line-height:1.4;}
  /* 轨道给到 84px：占比小的项（如宝钛 16%）才不会缩成一个小圆点，还看得出是「条」 */
  .ifb-r{display:grid;grid-template-columns:minmax(0,1fr) 84px 54px;gap:9px;
    align-items:center;margin-bottom:8px;}
  .ifb-r:last-child{margin-bottom:0;}
  .ifb-l{font-size:11.5px;color:#5b3a40;line-height:1.35;min-width:0;}
  /* 圆角用 3px 不用 4px：短条（16%）在小圆角下仍然读作「条」，读不成「点」 */
  .ifb-t{display:block;height:8px;border-radius:3px;background:#f6e7ea;overflow:hidden;}
  .ifb-t i{display:block;height:100%;min-width:3px;border-radius:3px;
    background:linear-gradient(90deg,#e2495c,#c8102e);}
  .ifb-v{font-size:12px;font-weight:800;color:#8c0a20;text-align:right;letter-spacing:.2px;}
  .ifb-down .ifb-t i{background:linear-gradient(90deg,#d98a97,#a3122a);}
  .if-note{margin:8px 0 4px;font-size:12px;line-height:1.85;color:#6b6b70;
    border-left:3px solid #f0dfe2;padding-left:10px;}
  .if-note b{color:#a3122a;}

  @media(max-width:860px){
    .ifbars{grid-template-columns:1fr;}
    .if-lg-hint{display:none;}
  }
  @media print{
    .if-scroll{overflow:visible;}
    .if-svg{min-width:0;}
    .iflow,.ifb{break-inside:avoid;}
  }
"""

s = io.open(CSSP, encoding='utf-8').read()
i = s.find(MARK)
if i >= 0:
    s = s[:i].rstrip() + '\n'
    print('已移除旧样式块，重新追加')
s = s.rstrip() + '\n\n' + BLOCK
io.open(CSSP, 'w', encoding='utf-8').write(s)
print('report_theme.css -> %d bytes，标记块 ok' % os.path.getsize(CSSP))
