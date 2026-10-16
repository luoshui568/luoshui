# 怎么让「洛水研报模版」出现在技能市场里搜到

**结论先说：那个搜索框搜的是「市场（SkillHub）」，不搜本机。** 所以自己的 skill 搜不到是正常的 ——
它只会出现在 **「已安装」** 里。想让它在市场里被搜到，**必须把 skill 上架到腾讯 SkillHub（skillhub.cn）**，
WorkBuddy 客户端本身**没有发布入口**（我把客户端代码翻了一遍：只有 `skillhubSearch` / `skillhubInstall`
这类搜索与安装能力，没有任何发布 / 上架 / 审核的字样；本机也没有 `skillhub` CLI）。

---

## 一、上架路径（网页端，推荐）

| 步 | 操作 |
|---|---|
| 1 | 浏览器打开 **skillhub.cn**，登录（公开发布通常需先完成**开发者注册 / 实名**） |
| 2 | 右上角点 **「发布团队 skill」** |
| 3 | 选发布类型（免费版即可） |
| 4 | **上传技能包** ＋ 填写基本信息（名称 / 描述 / 分类 / 标签；页面通常有 AI 辅助补全） |
| 5 | 提交 → **平台安全审核**（企业账号还会多一道管理员审核） |
| 6 | 审核通过后，进 **【技能列表】→ 点「上架」** |
| 7 | ⇒ 之后在 WorkBuddy 的「技能」入口搜名字，就能搜到了 |

> **可见性**：SkillHub 支持 `--visibility`（CLI 参数），网页端也有发布范围选项。
> 你这种「只给团队用」的场景，**建议选团队可见、不要公开** —— 理由见下面第三节。

---

## 二、上架前检查清单（我们已经逐项对过）

| 项 | 要求 | 我们的状态 |
|---|---|---|
| **目录名 = `name` 字段** | 必须**完全一致**，否则技能列表里看不到 | ✓ 都是 `luoshui-report-template` |
| `SKILL.md` 在包内 | 根目录或子目录都行 | ✓ `luoshui-report-template/SKILL.md` |
| frontmatter 能过 YAML | 值里不能有「英文冒号 + 空格」 | ✓ 真 YAML 解析通过 |
| 包内无垃圾文件 | 不要带 `.git` / `.DS_Store` / `LICENSE` 等 | ✓ 已清 |
| 无硬编码凭证 | 敏感信息走环境变量 | ✓ 无密钥、无密码 |
| slug 小写 + 短横线 | ClawHub / SkillHub 硬性要求 | ✓ |
| 本地已实测 | 能正常触发与运行 | ✓ 你已用了一段时间 |
| 体积 | 客户端出现过 10 MB 量级限制 | ✓ 82 KB |

**自检命令**（改完包随时复跑）：

```bash
python3 build/verify_skill_package.py            # 复刻客户端的三条导入规则
```

---

## 三、上架前得先想清楚一件事：**要不要脱敏 / 要不要公开**

包里有三样「指向你自己的东西」，公开上架前建议处理：

| 内容 | 出现位置 | 建议 |
|---|---|---|
| CloudBase envId `fdels568-…` | `SKILL.md`「★ 环境配置」表 · `pipeline.md` · `deploy-verify.md` · `check_env.py` | 公开版换成 `<你的 envId>` |
| 域名 `liuchaowang.cn` | 同上 + `hard-rules.md` | 公开版换成 `<你的域名>` |
| 仓库名 `luoshui568/luoshui` | `INSTALL.md` | 公开版换成 `<你的仓库>` |

**这些不是密钥**（真正的写权限 key 在仓库的 `build/cloud.json`，不在包里），泄漏风险很低；
但**公开上架等于把你的整套研报方法论（71 条硬性要求 + 31 模块蓝图）摊开给所有人看**，
而且这个 skill **对别人其实没用** —— 它依赖你的私有仓库。

⇒ **两条路选一条**：

- **只给团队 / 自己用** ⇒ 选「团队可见」，**不用脱敏**，直接传现在的包。
- **要公开上架** ⇒ 我可以生成一个**脱敏版**（把上面三样换成占位符），单独出一份 `-public.zip`。

---

## 四、另一条路：官方 CLI（本机还没装）

SkillHub 有 CLI，装好后可以脚本化发布：

```bash
skillhub login                                  # 浏览器 OAuth，凭证落 ~/.skillhub/auth.json
skillhub init --name luoshui-report-template --category 数据分析
skillhub push
skillhub publish --visibility public            # 版本号写在 SKILL.md 的 version
```

> ⚠️ **本机现在没有这个 CLI**：`~/.workbuddy/bin/skillhub` 与
> `~/.workbuddy/skills/.skillhub-cli/` 都不存在。要装得先去 skillhub.cn 拿。
> 我**没有**装它 —— 装了会改本机环境，需要你点头。

另外 SkillHub 上有个官方发布助手 skill（`@user_a95aac1d/skillhub-publish`），
能把「七维审计 → 脱敏 → 生成 README → 打包」自动化。需要的话我可以搜出来给你看。

---

## 五、我已经做完的 / 还需要你做的

**我做完的**：

1. 把 `SKILL.md` 的 frontmatter **升级成「上架形态」** —— 补上平台必填字段：
   `display_name` / `display_name_en` / `description_zh` / `description_en` / `version` / `author` / `category`，
   并加 `compatibility` 说明「依赖项目仓库」。
   （对照样本：本机从 SkillHub 装的 `费曼教学教练`，它的 frontmatter 就是上架后的样子。）
2. 核对「目录名 = name 字段」✓、YAML 可解析 ✓、包内无垃圾文件 ✓。
3. 重新打包为 `deliver/luoshui-report-template.zip`（＋同内容 `.skill`），两道校验全绿。

**还需要你做的**（都涉及登录 / 实名 / 点确认，我做不了）：

1. 去 **skillhub.cn** 登录（首次要开发者注册 / 实名）
2. 点 **「发布团队 skill」** → 上传 `deliver/luoshui-report-template.zip`
3. 填分类 / 标签 → 提交审核 → 通过后点 **「上架」**
4. 告诉我一句：**要不要出脱敏版**（涉及是否公开）

---

*生成于 2026-10-16。本轮只改了 skill 的 frontmatter 与文档，**未动线上、未动数据库**。*
