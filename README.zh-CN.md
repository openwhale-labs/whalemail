# whalemail

一个 Gmail 收件箱的分流工具。（[English](README.md)）

whalemail 读取你的 Gmail，用 LLM 把每封邮件归入五个桶之一，再推到一个 Telegram 群：要紧的来一封推一封，其余攒到每天早上的晨报。同一个群里还有一个小 agent，能搜邮件、起草回复。它自己从不发信。

它跑在你自己的机器上，直连 Gmail 和 LLM，数据不经过任何第三方。

## 五个桶

| | 桶 | 含义 | 推送 |
|---|---|---|---|
| 🔴 | action | 不处理会断服务、丢钱、坏系统 | 活跃时段实时推 |
| 🟡 | decision | 续不续、要不要，通常有时限 | 晨报 |
| 🔵 | fyi | 已成定局、无需操作，但你想知道 | 晨报，一行一封 |
| 🔐 | verify | 涉钱涉账户且像钓鱼 | 晨报，附「去官方渠道核实」 |
| ⚪ | noise | 订阅、促销、验证码 | 晨报只报数量 |

规则在 [rules.md](rules.md)，它就是系统提示词，改它就是改分类器。只和你自己邮箱有关的东西（你的 label 名、你的银行、你的服务商）写进 `rules.local.md`，运行时拼接到提示词后面，不进仓库。

## 怎么跑起来

需要：Python 3.11+、一个 Google Cloud 项目、一个 OpenAI 兼容的 LLM 接口、一个 Telegram bot。

```bash
git clone https://github.com/openwhale-labs/whalemail && cd whalemail
python -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env
cp config/gmail-allowlist.example.json config/gmail-allowlist.json
```

1. **Gmail**：在 Google Cloud 启用 Gmail API，新建一个「桌面应用」类型的 OAuth 客户端，把 JSON 下载到 `config/client_secret.json`，跑一次 `python scripts/oauth_setup.py`。浏览器登录后 token 存到 `config/token.json`，之后自动刷新。
2. **LLM**：在 `.env` 里填 `WHALEMAIL_LLM_BASE_URL`、`WHALEMAIL_LLM_API_KEY`、`WHALEMAIL_CLASSIFY_MODEL`。任何提供 `/chat/completions` 的接口都行，默认指向 OpenRouter 的一个便宜小模型，做分类够用。
3. **Telegram**：找 @BotFather 建 bot，拉进群，把 token 和群 id 填进 `.env`（话题群的写法见文件里的注释）。
4. **语言和时区**：`WHALEMAIL_LANGUAGE=zh` 让 Telegram 消息和 LLM 摘要都用中文；`WHALEMAIL_TZ=Asia/Shanghai`。

然后：

```bash
python run.py --test-last 20     # 拉最近 20 封分类并打印，不推送
python run.py --once             # 拉新邮件、分类、活跃时段推 🔴
python run.py --digest           # 现在出一份晨报
python run.py --heartbeat        # 推静音的两小时简报，替换掉上一条
python run.py --ask "找 Cloudflare 最近一张发票，起草一封要税号的回复"
python run.py --bot              # 前台跑 Telegram bot
```

macOS 上用 `scripts/install-whalemail-launchd.sh` 装成 launchd 定时任务，时间参数读 `.env`，改完重跑脚本即可。Linux 用 cron 或 systemd timer 跑同样的命令。

## 三个有意为之的取舍

- **宁多报，不漏报。** 模型没答或答错的一律进 fyi，从不进 noise；涉钱涉账户的拿不准就往上抬一档。
- **agent 只起草，人来发。** `draft_reply` 只写进 Gmail 草稿箱；bot 随后发一张审批卡，点 ✅ 才真正调用发送接口。发不发始终是人的决定。
- **OAuth 只要够用的权限。** 用 `gmail.modify` 和 `gmail.settings.basic`，不用 `https://mail.google.com/` 完全权限。token 就算泄露也删不掉邮件。

## 许可证

Apache License 2.0，见 [LICENSE](LICENSE)。
