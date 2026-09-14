"""User-facing strings for Telegram messages, in English and Chinese.

Selected by WHALEMAIL_LANGUAGE (see settings.language). Keys missing from a
language fall back to English.
"""

from __future__ import annotations

import settings

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "bucket.action": "Action needed",
        "bucket.decision": "Decision",
        "bucket.fyi": "FYI",
        "bucket.verify": "Verify",
        "bucket.noise": "Noise",
        "item": "• {time} {summary} ({sender})",
        "item.action": "\n  → {action}",
        "alerts.header": "🔴 Mail alert · needs attention",
        "digest.header": "📬 Morning digest · {date} · {total} emails",
        "digest.section": "\n{emoji} {label} ({n})",
        "digest.action_suffix": " — {action}",
        "digest.verify_warn": "  ⚠️ Verify with the sender directly; do not click links in the email",
        "digest.fyi_item": "• {time} {summary}",
        "digest.noise": "\n⚪ {n} noise emails archived (not listed)",
        "digest.empty": "📭 Morning digest: no new email.",
        "heartbeat.header": "🐋 Last {hours}h: {n} emails",
        "heartbeat.section": "{emoji} {label} ({n})",
        "auth.failed": (
            "⚠️ whalemail: Gmail authorization expired, fetching is paused.\n"
            "Run `python scripts/oauth_setup.py` on the host to re-authorize.\n"
            "({err})"
        ),
        "bot.ack": "🐳 Got it, working…",
        "bot.new_topic": "🆕 New topic (context cleared)",
        "bot.error": "⚠️ Error: {err}",
        "bot.approval": "📝 Draft ready — sent only after you confirm\nTo: {to}\nSubject: {subject}\n\n{body}",
        "bot.btn_send": "✅ Send",
        "bot.btn_cancel": "❌ Cancel",
        "bot.sent_toast": "Sent ✅",
        "bot.sent": "✅ Sent",
        "bot.send_failed": "Send failed: {err}",
        "bot.cancelled_toast": "Cancelled",
        "bot.cancelled": "❌ Cancelled (draft kept in Gmail)",
        "agent.no_output": "(no output)",
        "agent.step_limit": "(step limit reached before finishing; narrow the task or retry)",
        "tool.no_threads": "no matching threads",
        "tool.draft_created": "draft created (not sent)",
    },
    "zh": {
        "bucket.action": "要去操作",
        "bucket.decision": "要做决定",
        "bucket.fyi": "知道就行",
        "bucket.verify": "核实真伪",
        "bucket.noise": "噪声",
        "item": "• {time} {summary}（{sender}）",
        "item.action": "\n  → {action}",
        "alerts.header": "🔴 邮件提醒 · 要处理",
        "digest.header": "📬 邮件晨报 · {date} · 共 {total} 封",
        "digest.section": "\n{emoji} {label}（{n}）",
        "digest.action_suffix": " — {action}",
        "digest.verify_warn": "  ⚠️ 亲自核实，勿点信中链接",
        "digest.fyi_item": "• {time} {summary}",
        "digest.noise": "\n⚪ 噪声 {n} 封已归档（不展开）",
        "digest.empty": "📭 邮件晨报：过去一段无新邮件。",
        "heartbeat.header": "🐋 过去 {hours}h {n} 封",
        "heartbeat.section": "{emoji} {label}（{n}）",
        "auth.failed": (
            "⚠️ whalemail：Gmail 授权失效，邮件抓取已暂停。\n"
            "请在运行 whalemail 的机器上跑 `python scripts/oauth_setup.py` 重新授权。\n"
            "（{err}）"
        ),
        "bot.ack": "🐳 收到，处理中…",
        "bot.new_topic": "🆕 已开新话题（清空上下文）",
        "bot.error": "⚠️ 处理出错：{err}",
        "bot.approval": "📝 草稿待发送 — 确认后才发\n收件人: {to}\n主题: {subject}\n\n{body}",
        "bot.btn_send": "✅ 发送",
        "bot.btn_cancel": "❌ 取消",
        "bot.sent_toast": "已发送 ✅",
        "bot.sent": "✅ 已发送",
        "bot.send_failed": "发送失败: {err}",
        "bot.cancelled_toast": "已取消",
        "bot.cancelled": "❌ 已取消（草稿留在 Gmail）",
        "agent.no_output": "(无输出)",
        "agent.step_limit": "(达到最大步数仍未完成，请缩小任务或重试)",
        "tool.no_threads": "无匹配会话",
        "tool.draft_created": "草稿已建(未发送)",
    },
}


def t(key: str, **kw) -> str:
    """Look up a string for the current language and format it."""
    table = STRINGS.get(settings.language(), STRINGS["en"])
    s = table.get(key) or STRINGS["en"][key]
    return s.format(**kw) if kw else s
