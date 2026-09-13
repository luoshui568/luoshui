# -*- coding: utf-8 -*-
"""收尾：同步桌面副本 + 三方 md5 复查 + 清理临时文件"""
import hashlib
import os
import shutil

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
DESK = r'C:\Users\50522\Desktop\矿产战略执行工作台.html'


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def size(p):
    return os.path.getsize(p)


print('local :', md5(SRC), size(SRC))
shutil.copy2(SRC, DESK)
print('desk  :', md5(DESK), size(DESK))

ok = md5(SRC) == md5(DESK)
print('本机 == 桌面 :', 'OK' if ok else 'FAIL')

# 清理本轮临时文件
for f in ['_diff.txt', '_shot_list.html', '_shot_modal.html',
          '_probe_out.txt', '_cors_out.txt', '_em_out.txt']:
    p = os.path.join(BASE, 'build', f)
    if os.path.exists(p):
        os.remove(p)
        print('已删除', f)
for d in os.listdir(os.path.join(BASE, 'build')):
    if d.startswith('_shot_prof_'):
        shutil.rmtree(os.path.join(BASE, 'build', d), ignore_errors=True)
        print('已删除目录', d)

# 最终产物清单
print('\n交付截图：')
for f in ['v_stock_list.png', 'v_stock_modal.png']:
    p = os.path.join(BASE, 'build', f)
    print('  %-20s %s' % (f, ('%d KB' % (size(p) // 1024)) if os.path.exists(p) else '缺失'))
