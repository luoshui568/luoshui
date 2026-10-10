#!/usr/bin/env bash
# ==============================================================================
#  luoshui 工作区 · macOS 引导脚本
#
#  作用：把 GitHub 仓库 + 迁移包，在一台全新的 Mac 上还原成可工作的研报工作台。
#
#  用法：
#     bash bootstrap.sh                    # 默认装到 ~/WorkBuddy/luoshui
#     DEST=~/dev/luoshui bash bootstrap.sh # 自定义位置
#     REPO=git@github.com:luoshui568/luoshui.git bash bootstrap.sh
#
#  前提：脚本与 luoshui-workspace.tar.gz 放在同一目录。
# ==============================================================================
set -euo pipefail

REPO="${REPO:-https://github.com/luoshui568/luoshui.git}"
DEST="${DEST:-$HOME/WorkBuddy/luoshui}"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_PKG="$PKG_DIR/luoshui-workspace.tar.gz"
SEC_PKG="$PKG_DIR/luoshui-secrets.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

bold(){ printf '\033[1m%s\033[0m\n' "$*"; }
ok(){   printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn(){ printf '  \033[33m!\033[0m %s\n' "$*"; }
err(){  printf '  \033[31m✗\033[0m %s\n' "$*"; }

echo
bold "════════════════════════════════════════════════════════════"
bold "  luoshui 工作区 · macOS 引导"
bold "════════════════════════════════════════════════════════════"
echo "  仓库    $REPO"
echo "  装到    $DEST"
echo "  迁移包  $PKG_DIR"
echo

# ── 1. 环境检查 ────────────────────────────────────────────────
bold "【1/6】环境检查"

if ! xcode-select -p >/dev/null 2>&1; then
  err "缺少 Xcode 命令行工具（git 依赖它）"
  echo "      运行： xcode-select --install"
  exit 1
fi
ok "Xcode 命令行工具"

command -v git >/dev/null 2>&1 || { err "找不到 git"; exit 1; }
ok "git $(git --version | awk '{print $3}')"

PY=""
for c in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
done
[ -n "$PY" ] || { err "找不到 python3。运行： brew install python@3.12"; exit 1; }
ok "python3 $("$PY" -V 2>&1 | awk '{print $2}')  →  $PY"

if command -v node >/dev/null 2>&1; then
  ok "node $(node -v)"
else
  warn "没装 node —— 语法校验（node --check）会跳过；brew install node 可补"
fi

BROWSER=""
for b in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
         "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
  [ -x "$b" ] && BROWSER="$b" && break
done
if [ -n "$BROWSER" ]; then
  ok "无头浏览器 $(basename "$(dirname "$(dirname "$(dirname "$BROWSER")")")")"
else
  warn "没找到 Chrome/Edge —— 截图验收会不可用（brew install --cask google-chrome）"
fi
echo

# ── 2. 取仓库 ──────────────────────────────────────────────────
bold "【2/6】取 GitHub 仓库"
mkdir -p "$(dirname "$DEST")"
if [ -d "$DEST/.git" ]; then
  ok "已存在，执行 git pull"
  git -C "$DEST" pull --ff-only || warn "pull 失败（本地有改动？）请手动处理"
else
  git clone "$REPO" "$DEST"
  ok "已 clone 到 $DEST"
fi
echo "  当前提交： $(git -C "$DEST" rev-parse --short HEAD)  $(git -C "$DEST" log -1 --format=%s | cut -c1-50)"
echo

# ── 3. 解迁移包 ────────────────────────────────────────────────
bold "【3/6】解开迁移包"
if [ ! -f "$MAIN_PKG" ]; then
  err "找不到 $MAIN_PKG"
  echo "      请把 luoshui-workspace.tar.gz 与本脚本放同一目录。"
  exit 1
fi
tar -xzf "$MAIN_PKG" -C "$TMP"
NS=$(find "$TMP/workspace" -type f 2>/dev/null | wc -l | tr -d ' ')
# 工作区：覆盖式（这些就是本项目的文件）
cp -R "$TMP/workspace/." "$DEST/"
ok "工作区还原 $NS 个文件（脚本 / 记忆 / seed）"
# 家目录：不覆盖式，保留 Mac 上已有的技能
mkdir -p "$HOME/.workbuddy"
if [ -d "$TMP/home" ]; then
  cp -Rn "$TMP/home/." "$HOME/.workbuddy/"
  NSN=$(find "$TMP/home" -type f | wc -l | tr -d ' ')
  ok "家目录还原 $NSN 个文件到 ~/.workbuddy（已存在的同名文件不覆盖）"
fi
echo

# ── 4. 密钥（可选） ────────────────────────────────────────────
bold "【4/6】密钥包（含 API Key，可选）"
if [ -f "$SEC_PKG" ]; then
  warn "含发现报告 key / 同花顺 token / 微信 bot token —— 仅在可信机器上解包"
  printf "  现在解包吗？[y/N] "
  read -r ans </dev/tty || ans=n
  if [ "${ans:-n}" = "y" ] || [ "${ans:-n}" = "Y" ]; then
    mkdir -p "$TMP/sec"
    tar -xzf "$SEC_PKG" -C "$TMP/sec"
    cp -Rn "$TMP/sec/home/." "$HOME/.workbuddy/"
    ok "已还原 mcp.json / settings.json"
    warn "重启 WorkBuddy 后，到「连接器管理」把新出现的服务点一次 Trust"
  else
    warn "跳过。以后可手动解包，或直接照手册在界面里重配"
  fi
else
  warn "同目录没有密钥包，跳过"
fi
echo

# ── 5. Python 环境 ────────────────────────────────────────────
bold "【5/6】Python 依赖"
VENV="$HOME/.workbuddy/binaries/python/envs/default"
if [ ! -x "$VENV/bin/python" ]; then
  mkdir -p "$(dirname "$VENV")"
  "$PY" -m venv "$VENV"
  ok "已建 venv：$VENV"
else
  ok "venv 已存在"
fi
if [ -f "$PKG_DIR/requirements.txt" ]; then
  "$VENV/bin/python" -m pip install -q --upgrade pip
  "$VENV/bin/python" -m pip install -q -r "$PKG_DIR/requirements.txt"
  ok "已装： $(tr '\n' ' ' < "$PKG_DIR/requirements.txt" | grep -v '^#' | cut -c1-70)"
else
  warn "没有 requirements.txt，跳过"
fi
echo

# ── 6. 路径改写（干跑） ────────────────────────────────────────
bold "【6/6】把脚本里的 Windows 路径改成本机路径"
PORT="$DEST/build/_port_paths.py"
if [ -f "$PORT" ]; then
  "$VENV/bin/python" "$PORT" | sed -n '1,14p'
  echo
  warn "上面是干跑。确认无误后执行实际改写："
  echo "      $VENV/bin/python $DEST/build/_port_paths.py --go"
  echo "      （每个文件会备份为 *.winbak，可用 --rollback 整批还原）"
else
  err "找不到 build/_port_paths.py"
fi
echo

bold "════════════════════════════════════════════════════════════"
bold "  脚本能做的到此为止。剩下必须你手动做的："
bold "════════════════════════════════════════════════════════════"
cat <<EOF

  1) 装 WorkBuddy macOS 版，登录同一账号
     —— 云记忆、专家、连接器都跟账号走，登录后自动回来。

  2) 用 WorkBuddy 打开工作区：$DEST

  3) 连接器重新授权（管理凭据在登录态里，搬不过来）：
     · CloudBase（腾讯云开发）—— 必须重做一次设备授权，600 秒内点确认
     · 通达信 / 腾讯自选股 / 同花顺 iFinD —— 逐个连接并 Trust

  4) 设一个环境变量（上传/删行脚本要用）：
       echo 'export WB_ADMIN_PASS=<你的口令>' >> ~/.zshrc && source ~/.zshrc

  5) 验证：
       cd $DEST && $VENV/bin/python build/live_check_v4.py

  详细步骤见同目录的《迁移手册.md》
EOF
echo
