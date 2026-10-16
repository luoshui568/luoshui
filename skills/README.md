# skills/ —— skill 源的**只读备份**

## 这里放的是什么

`skills/luoshui-report-template/` 是「**洛水研报模版**」skill 的**可编辑源**在仓库里的一份备份。
放进仓库的理由：换机后能直接 `git clone` 拿到源并继续编辑，还能看 git 历史。
（此前源只存在于本机 `~/.workbuddy/skills/luoshui-report-template/`，打包件 `deliver/*.skill`
虽然也在仓库里，但那是二进制分发件，改不了。）

## ★★ 方向铁律：**本机 → 仓库，单向**

| | 路径 | 角色 |
|---|---|---|
| **权威源** | `~/.workbuddy/skills/luoshui-report-template/` | **真正生效的那份**。WorkBuddy 加载的就是它。 |
| 只读备份 | `skills/luoshui-report-template/`（本目录） | 仓库副本。**不要在这里改** —— 改了不影响实际加载的 skill。 |

改了本机源之后，用脚本同步过来：

```bash
python3 build/sync_skill_src.py          # 干跑：只看差异，不写文件
python3 build/sync_skill_src.py --go     # 真同步到仓库副本
```

脚本**不会**反向覆盖（没有 `--reverse`）：本机那份永远是权威。
若副本里的文件在源里已被删，脚本只提示、不自动删 —— 手动 `git rm` 后提交。

## 两个校验各管什么

- `python3 build/verify_skill_package.py` —— 校验**打包件**能不能被客户端导入
  （扩展名 / 包内有 SKILL.md / frontmatter 能被 YAML 解析 三道）。
- `python3 build/sync_skill_src.py` —— 校验**源**在不在仓库、跟本机一不一致。

两个一起跑才完整。分发件（`deliver/luoshui-report-template.zip` / `.skill`）由本目录的源打包而来，
改完源记得**重新打包**并再跑一次 `verify_skill_package.py`。

## 敏感信息

本仓库是 **PUBLIC**。改动前先扫一遍敏感串（管理密码、token、私钥）。
当前源已扫描：管理密码 0 命中、无 token / 私钥；文中出现的 `Bearer <key>` 只是文档措辞。
