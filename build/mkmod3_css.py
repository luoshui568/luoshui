# -*- coding: utf-8 -*-
"""把模块 3「股东结构」的样式追加进 build/report_theme.css（幂等，用标记块替换）。"""
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
CSSP = os.path.join(HERE, 'report_theme.css')

MARK = '/* ===== 模块3 · 股东结构（环形占比 + 股权树） ===== */'

BLOCK = MARK + """
  /* 环形占比：中间镂空放公司 logo */
  .sh3-top{display:grid;grid-template-columns:1.02fr 1fr;gap:20px;align-items:start;}
  .sh3-donut{position:relative;width:100%;max-width:316px;margin:4px auto 0;}
  .sh3-donut svg{display:block;width:100%;height:auto;}
  .sh3-hole{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
    width:47%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;}
  .sh3-hole img{width:60%;max-width:78px;height:auto;display:block;margin:0 0 2px;}
  .sh3-hole .nm{font-size:14.5px;font-weight:800;color:#2b161a;letter-spacing:.6px;line-height:1.12;}
  .sh3-hole .cd{font-size:10.5px;color:#9a7d82;letter-spacing:.9px;margin-top:2px;}
  /* 图例 */
  .sh3-leg{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;}
  .sh3-leg .it{border:1px solid #f2dfe2;border-radius:12px;padding:9px 12px;
    background:linear-gradient(160deg,#fff,#fffafb);}
  .sh3-leg .hd{display:flex;align-items:center;gap:6px;font-size:12.5px;color:#5b3a40;line-height:1.3;}
  .sh3-leg .dot{width:10px;height:10px;border-radius:3px;flex:none;}
  .sh3-leg .big{font-size:19px;font-weight:800;margin-top:4px;letter-spacing:.5px;}
  .sh3-leg .big small{font-size:11.5px;font-weight:600;color:#9a7d82;margin-left:3px;}
  .sh3-leg .sub{font-size:11.5px;color:#9a7d82;margin-top:1px;}
  /* 关键持股指标 */
  .sh3-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 4px;}
  .sh3-stats .it{border:1px solid #f2dfe2;border-radius:12px;padding:10px 12px;
    background:linear-gradient(160deg,#fff,#fffafb);}
  .sh3-stats .it .k{font-size:12px;color:#9a7d82;}
  .sh3-stats .it .v{font-size:17px;font-weight:800;color:#2b161a;margin-top:3px;letter-spacing:.3px;}
  .sh3-stats .it .v small{font-size:11.5px;font-weight:600;color:#9a7d82;margin-left:2px;}
  .sh3-stats .it.gold{background:linear-gradient(160deg,#fffdf6,#fdf5e4);border-color:#f0e0b8;}
  .sh3-stats .it.gold .v{color:#8a6a12;}
  .sh3-ul{margin:2px 0 0 18px;font-size:13.5px;line-height:1.85;}
  .sh3-ul li{margin-bottom:3px;}
  /* 股权结构树 */
  .sh3-tree{margin:12px 0 6px;border:1px solid #f7eaec;border-radius:14px;
    padding:16px 12px 10px;background:linear-gradient(180deg,#fffbfc,#fff);}
  .sh3-tree svg{display:block;width:100%;height:auto;}
  .sh3-tree .cap{margin:6px 0 0;text-align:center;font-size:11.5px;color:#9a7d82;line-height:1.7;}
  @media(max-width:860px){ .sh3-top{grid-template-columns:1fr;} }
"""

s = io.open(CSSP, encoding='utf-8').read()
i = s.find(MARK)
if i >= 0:
    s = s[:i].rstrip() + '\n'
    print('已移除旧样式块，重新追加')
s = s.rstrip() + '\n\n' + BLOCK
io.open(CSSP, 'w', encoding='utf-8').write(s)
print('report_theme.css -> %d bytes, 标记块 %s' % (os.path.getsize(CSSP), 'ok'))
