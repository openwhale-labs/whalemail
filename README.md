# whalemail

Gmail triage for one inbox. ([中文说明](README.zh-CN.md))

whalemail reads your Gmail, sorts every email into one of five buckets with an LLM, and pushes what matters to a Telegram group: urgent items as they arrive, everything else in a morning digest. A small agent in the same group can search your mail and draft replies. It never sends anything on its own.

It runs on a machine you own, talks to Gmail and the LLM directly, and keeps no data anywhere else.

## The five buckets

| | Bucket | Meaning | Delivery |
|---|---|---|---|
| 🔴 | action | Do something or a service stops, money is lost, a system breaks | Pushed immediately during the active window |
| 🟡 | decision | Renew or not, accept or not, usually with a deadline | Morning digest |
| 🔵 | fyi | Settled, nothing to do, worth knowing | Morning digest, one line each |
| 🔐 | verify | Money or account related and reads like phishing | Morning digest, with a "check through official channels" note |
| ⚪ | noise | Newsletters, promotions, one-time codes | Counted in the digest, never listed |

The rules are in [rules.md](rules.md). It is the system prompt, so editing it changes the classifier. Anything specific to your inbox (your label names, your banks, your vendors) goes in `rules.local.md`, which is appended to the prompt and never committed.

## How it works

```
Gmail API ──► adapters/gmail   fetch new mail, cursor, normalize → Event (jsonl)
                  │
                  ▼
              triage           LLM: bucket + one-sentence summary + action
                  │
                  ▼
              digest           🔴 alerts as they arrive · heartbeat every 2 h · digest every morning
                  │
                  ▼
              Telegram group ◄── agent/bot: "find the invoice from X", "draft a reply" → draft + approval card
```

Three things are deliberate:

- **Over-report rather than miss.** An unknown or missing classification falls to fyi, never to noise. Anything about money or accounts moves one bucket up when in doubt.
- **The agent drafts, you send.** `draft_reply` writes to the Gmail Drafts folder. The bot then posts an approval card; only tapping ✅ calls `drafts.send`. The send decision stays with a person.
- **Narrow OAuth scopes.** `gmail.modify` and `gmail.settings.basic`, not `https://mail.google.com/`. A leaked token cannot permanently delete mail.

## Setup

Requirements: Python 3.11+, a Google Cloud project, an OpenAI-compatible LLM endpoint, a Telegram bot.

```bash
git clone https://github.com/openwhale-labs/whalemail && cd whalemail
python -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env
cp config/gmail-allowlist.example.json config/gmail-allowlist.json
```

1. **Gmail.** In Google Cloud, enable the Gmail API and create an OAuth client of type *Desktop app*. Download its JSON to `config/client_secret.json`, then run `python scripts/oauth_setup.py` once. It opens a browser, you sign in, and the token is saved to `config/token.json` and refreshed automatically from then on.
2. **LLM.** Set `WHALEMAIL_LLM_BASE_URL`, `WHALEMAIL_LLM_API_KEY` and `WHALEMAIL_CLASSIFY_MODEL` in `.env`. Any endpoint that speaks `/chat/completions` works; the default points at OpenRouter with a small, cheap model, which is enough for classification.
3. **Telegram.** Create a bot with @BotFather, add it to a group, and put the token and the group id in `.env` (see the comments there for forum topics).
4. **Language and timezone.** `WHALEMAIL_LANGUAGE` is `en` or `zh` and controls both the Telegram messages and the language the LLM writes summaries in. `WHALEMAIL_TZ` is an IANA name.

Then:

```bash
python run.py --test-last 20     # classify the last 20 emails and print them; pushes nothing
python run.py --once             # fetch new mail, classify, push 🔴 alerts (active window only)
python run.py --digest           # push the morning digest now
python run.py --heartbeat        # push the silent 2-hour summary, replacing the previous one
python run.py --ask "find the last invoice from Cloudflare and draft a reply asking for a VAT number"
python run.py --bot              # run the Telegram bot in the foreground
```

### Scheduling on macOS

`scripts/install-whalemail-launchd.sh` installs launchd agents for `--once` (every 10 minutes in the active window), `--heartbeat`, `--digest` and the bot, reading the times from `.env`. Re-run it after changing any schedule value. `--uninstall` removes them. On Linux, the same commands map onto cron or systemd timers.

### Fetch scope

`config/gmail-allowlist.json` decides what is fetched. The default query is everything received, which includes mail that a filter archived past the inbox. `exclude_labels` lists label ids that are skipped entirely, for example a label you already use for "not important".

## Configuration

| Variable | Purpose |
|---|---|
| `WHALEMAIL_LLM_BASE_URL`, `WHALEMAIL_LLM_API_KEY`, `WHALEMAIL_CLASSIFY_MODEL` | Classification endpoint and model |
| `WHALEMAIL_AGENT_MODEL` | Model for the agent; defaults to the classification model |
| `WHALEMAIL_GMAIL_ACCOUNT`, `WHALEMAIL_GMAIL_CLIENT_SECRET`, `WHALEMAIL_GMAIL_TOKEN` | The inbox and the OAuth files |
| `WHALEMAIL_BOT_TOKEN`, `WHALEMAIL_TG_CHANNEL`, `WHALEMAIL_TG_THREAD` | Telegram bot, group, optional forum topic |
| `WHALEMAIL_LANGUAGE`, `WHALEMAIL_OWNER_NAME`, `WHALEMAIL_TZ` | `en`/`zh`, how the agent refers to you, IANA timezone |
| `WHALEMAIL_ACTIVE_START`, `WHALEMAIL_ACTIVE_END` | Hours between which 🔴 alerts are pushed immediately |
| `WHALEMAIL_ONCE_STEP_MIN`, `WHALEMAIL_HEARTBEAT_EVERY`, `WHALEMAIL_DIGEST_HOUR` | Schedule for the launchd installer |
| `WHALEMAIL_CONV_BUDGET`, `WHALEMAIL_CONV_KEEP` | Bot conversation token budget and how many recent turns survive compaction |

Everything sensitive lives in `.env` and `config/`, both git-ignored. Runtime data (`data/`) contains your email metadata and is git-ignored too.

## Development

```bash
.venv/bin/pip install pytest ruff
pytest
ruff check . && ruff format .
```

Tests cover rendering, classification mapping, conversation compaction and normalization; none of them touch the network.

## License

Apache License 2.0. See [LICENSE](LICENSE).
