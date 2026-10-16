#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「回忆录」截图探针：本机模式 + 预置样例数据 → 出 3 张图到 deliver/。

跑法：/Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python build/probe_memoir_shot.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'deploy', 'memoir.html')
OUT = os.path.join(ROOT, 'deliver')
SITE = os.path.join(HERE, '_mem_shot')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
W, H = 1560, 940          # 桌面
MW, MH = 500, 900         # 手机（窄屏 < 900 → 左栏走抽屉；Chromium 无头最小窗口约 500 宽）

NOW = int(time.time() * 1000)
DAY = 86400000


def seed():
    notes = [
        {"id": "n_demo1", "title": "1998 年冬天，父亲的那辆二八自行车",
         "body": "<div>那年我十一岁。父亲每天骑车四十里地去县城上班，后座上绑着一个铁皮饭盒。</div>"
                 "<div>有一回下大雪，他把我裹进一件军大衣里，说：<b>别怕，路滑就慢点走</b>。</div>"
                 "<div><br></div>"
                 "<div>很多年以后我才明白，他那句话说的不只是自行车。</div>"
                 "<div><br></div>"
                 "<blockquote>慢一点没关系，别停下来。</blockquote>"
                 "<div><span style=\"font-size:24px;color:#c0392b\">慢，就是快。</span></div>",
         "book": "家庭与来处", "tags": ["父亲", "记忆"], "color": "#c0392b", "pin": True,
         "is_del": False, "words": 96, "owner": "", "up": NOW - 2 * 3600 * 1000, "t": NOW - 40 * DAY},
        {"id": "n_demo2", "title": "复盘的三个层次：事、人、己",
         "body": "<div>第一层是<b>事</b>：这笔交易哪里做对了，哪里做错了。</div>"
                 "<div>第二层是<b>人</b>：当时是谁在场，谁的一句话改变了我的判断。</div>"
                 "<div>第三层是<b>己</b>：我为什么会在那个时刻做出那样的选择。</div>"
                 "<div><br></div>"
                 "<div>前两层一年能有长进，第三层要十年。</div>"
                 "<div class=\"todo\"><span class=\"bx\">☑</span><span>把去年四季度的复盘重读一遍</span></div>"
                 "<div class=\"todo\"><span class=\"bx\">☐</span><span>写一份「当时的我为什么这么想」</span></div>",
         "book": "投资与修行", "tags": ["复盘", "方法论"], "color": "#c9a227", "pin": True,
         "is_del": False, "words": 132, "owner": "", "up": NOW - 26 * 3600 * 1000, "t": NOW - 12 * DAY},
        {"id": "n_demo3", "title": "厄尔尼诺与南美铜矿：一次事后复盘",
         "body": "<div>2024 年那波，我判断对了方向却做错了节奏。</div>"
                 "<div><br></div>"
                 "<div>教训是：<mark>气候因子传导到价格有 6～18 个月的滞后</mark>，"
                 "我用季度思维去做一个年度级别的变量。</div>"
                 "<div><br></div>"
                 "<div>下次遇到同类变量，先问三个问题：</div>"
                 "<ol><li>历史样本有多少个？</li><li>这一次的初始条件哪里不同？</li>"
                 "<li>如果方向对了但节奏错了，仓位能不能扛住？</li></ol>",
         "book": "投资与修行", "tags": ["贵金属", "大宗", "复盘"], "color": "#2f8f9d", "pin": False,
         "is_del": False, "words": 148, "owner": "", "up": NOW - 3 * DAY, "t": NOW - 30 * DAY},
        {"id": "n_demo4", "title": "写给三年后的自己",
         "body": "<div>如果三年后你读到这里，希望下面这几件事已经做到了：</div>"
                 "<div><br></div>"
                 "<ul><li>把那本一直想写的笔记写完</li>"
                 "<li>每周至少一次，和父母吃一顿不看手机的饭</li>"
                 "<li>不再用忙碌来解释没做的重要的事</li></ul>"
                 "<div><br></div>"
                 "<hr>"
                 "<div><span style=\"font-size:13px;color:#8a7f72\">写于一个不知道前路的夜里</span></div>",
         "book": "信件与独白", "tags": ["自省"], "color": "#7b5ea7", "pin": False,
         "is_del": False, "words": 88, "owner": "", "up": NOW - 9 * DAY, "t": NOW - 9 * DAY},
        {"id": "n_demo5", "title": "读《资治通鉴》卷第一 摘录",
         "body": "<div>「才者，德之资也；德者，才之帅也。」</div>"
                 "<div><br></div>"
                 "<div>司马光把人分成四等：圣人、君子、小人、愚人。"
                 "他的结论是<u>宁取愚人，不取小人</u>。</div>"
                 "<div><br></div>"
                 "<pre>才德全尽谓之圣人，才德兼亡谓之愚人，\n德胜才谓之君子，才胜德谓之小人。</pre>",
         "book": "", "tags": ["读书", "通鉴"], "color": "", "pin": False,
         "is_del": False, "words": 76, "owner": "", "up": NOW - 20 * DAY, "t": NOW - 20 * DAY},
        {"id": "n_demo6", "title": "关于「耐心」的一句旧话",
         "body": "<div>爷爷说：<i>种树的人，是吃不到自己种的果子的人里，最心甘情愿的那一个。</i></div>",
         "book": "家庭与来处", "tags": ["记忆"], "color": "#5f8f45", "pin": False,
         "is_del": True, "words": 34, "owner": "", "up": NOW - 6 * DAY, "t": NOW - 60 * DAY},
    ]
    books = [
        {"id": "b_1", "name": "家庭与来处", "color": "#c0392b", "sort": 1, "owner": "", "is_del": False, "up": NOW - 40 * DAY},
        {"id": "b_2", "name": "投资与修行", "color": "#c9a227", "sort": 2, "owner": "", "is_del": False, "up": NOW - 30 * DAY},
        {"id": "b_3", "name": "信件与独白", "color": "#7b5ea7", "sort": 3, "owner": "", "is_del": False, "up": NOW - 9 * DAY},
    ]
    return notes, books


CASES = {
    # 默认打开一篇笔记 = 阅读模式（正文只读、工具条收起）
    '回忆录-阅读模式.png': ('', W, H),
    # 点右上角「✎ 编辑」= 编辑模式（工具条出现、正文可写）
    '回忆录-编辑模式.png': ("toggleEdit();", W, H),
    '回忆录-富文本工具条.png': ("toggleEdit();"
                          "(function(){"
                          "document.getElementById('ddSize').classList.add('open');"
                          "document.getElementById('ddColor').classList.add('open');"
                          "document.getElementById('ddHilite').classList.add('open');"
                          "})();", W, H),
    # 左栏右侧手柄：收起整个笔记本栏
    # ⚠️ --virtual-time-budget 下 CSS transition 不推进（截图会停在起始帧），
    #    所以先在页面里掐掉过渡，再切状态。
    '回忆录-左栏折叠.png': ("(function(){var s=document.createElement('style');"
                      "s.textContent='*{transition:none!important;animation:none!important}';"
                      "document.head.appendChild(s);})();toggleRail();", W, H),
    '回忆录-回收站.png': ("setView('trash');", W, H),
    # 手机尺寸（窄屏）：左栏变抽屉，手柄跟着抽屉走
    '回忆录-手机阅读.png': ('', MW, MH),
    '回忆录-手机抽屉.png': ("toggleDrawer();", MW, MH),
}


def build_page(path, tail):
    src = io.open(SRC, encoding='utf-8').read()
    src, c = re.subn(r'var DEV_MODE = false;', 'var DEV_MODE = true;', src)
    assert c == 1
    i = src.find('<body')
    j = src.find('>', i)
    pre = ('<script>try{localStorage.setItem("wb_memoir_v1",%s);'
           'localStorage.setItem("wb_memoir_books_v1",%s);'
           'localStorage.removeItem("wb_memoir_ui_v1");'
           'localStorage.removeItem("wb_memoir_rail_v1");}catch(e){}</script>'
           '<script>window.addEventListener("load",function(){setTimeout(function(){%s},900);});</script>'
           % (json.dumps(json.dumps(seed()[0], ensure_ascii=False), ensure_ascii=False),
              json.dumps(json.dumps(seed()[1], ensure_ascii=False), ensure_ascii=False),
              tail))
    io.open(path, 'w', encoding='utf-8').write(src[:j + 1] + pre + src[j + 1:])


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    from http.server import SimpleHTTPRequestHandler
    from socketserver import TCPServer
    import functools
    import threading

    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    TCPServer.allow_reuse_address = True
    httpd = TCPServer(('127.0.0.1', 8845), functools.partial(Q, directory=SITE))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    for name, spec in CASES.items():
        tail, w, h = spec
        p = os.path.join(SITE, name + '.html')
        build_page(p, tail)
        shot = os.path.join(OUT, name)
        subprocess.run([EDGE, '--headless=new', '--no-sandbox', '--disable-gpu',
                        '--disable-dev-shm-usage', '--hide-scrollbars',
                        '--window-size=%d,%d' % (w, h),
                        '--virtual-time-budget=6000',
                        '--screenshot=' + shot,
                        'http://127.0.0.1:8845/' + name + '.html'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        ok = os.path.exists(shot) and os.path.getsize(shot) > 8000
        print('%-28s %s  %d bytes' % (name, 'OK ' if ok else 'FAIL', os.path.getsize(shot) if os.path.exists(shot) else 0))
    httpd.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('截图输出目录：%s' % OUT)


if __name__ == '__main__':
    main()
