#!/usr/bin/env bash
# Install whalemail's launchd jobs (user agents) on macOS:
#   com.openwhale.whalemail.once      every STEP minutes in the active window: --once (fetch, classify, 🔴 alerts)
#   com.openwhale.whalemail.heartbeat every HB hours after the digest: --heartbeat (silent summary, latest only)
#   com.openwhale.whalemail.digest    at the digest hour: --digest (morning digest to Telegram)
#   com.openwhale.whalemail.bot       always on: the Telegram bot
#   Schedule parameters are read from .env (see "schedule" below; defaults 7–23 / 10 min / 2 h / digest at start).
#
# Usage (from the repository):
#   bash scripts/install-whalemail-launchd.sh             # install / reinstall
#   bash scripts/install-whalemail-launchd.sh --uninstall # remove
#
# The jobs carry no proxy variables; if you need a proxy, set it system-wide or add it here.
# Credentials are read from .env and config/ at run time, never written into the plists.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
DOMAIN="gui/$(id -u)"
LA="$HOME/Library/LaunchAgents"

uninstall() {
  for L in once digest heartbeat bot; do
    launchctl bootout "$DOMAIN/com.openwhale.whalemail.$L" 2>/dev/null || true
    rm -f "$LA/com.openwhale.whalemail.$L.plist"
  done
  echo "whalemail launchd jobs removed."
}

if [[ "${1:-}" == "--uninstall" ]]; then uninstall; exit 0; fi

[[ -x "$PY" ]] || { echo "missing interpreter: $PY. Create .venv in $REPO and install dependencies first." >&2; exit 1; }
mkdir -p "$REPO/data/runtime" "$LA"

# ---- schedule: read from .env (defaults below). To change times, edit .env and re-run this script ----
env_cfg() {
  local v=""
  if [[ -f "$REPO/.env" ]]; then
    v="$(grep -E "^${1}=" "$REPO/.env" | tail -1 | cut -d= -f2- || true)"
  fi
  echo "${v:-$2}"
}
AS="$(env_cfg WHALEMAIL_ACTIVE_START 7)"      # active window start (same key the runtime uses)
AE="$(env_cfg WHALEMAIL_ACTIVE_END 23)"       # active window end (one final --once at AE:00)
STEP="$(env_cfg WHALEMAIL_ONCE_STEP_MIN 10)"  # --once interval (minutes)
HB="$(env_cfg WHALEMAIL_HEARTBEAT_EVERY 2)"   # heartbeat interval (hours; run.py reads the same key)
DH="$(env_cfg WHALEMAIL_DIGEST_HOUR "$AS")"   # digest hour (default: window start, covering the night)

# once: AS:00–AE:00, with a single closing run at AE:00
ONCE_INTERVALS=""
for h in $(seq "$AS" "$AE"); do
  if [[ "$h" -eq "$AE" ]]; then mins="0"; else mins="$(seq 0 "$STEP" 59)"; fi
  for m in $mins; do
    ONCE_INTERVALS+="    <dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>$m</integer></dict>
"
  done
done
DIGEST_INTERVALS="    <dict><key>Hour</key><integer>$DH</integer><key>Minute</key><integer>0</integer></dict>
"

write_plist() {
  local label="$1" arg="$2" intervals="$3"
  local log="$REPO/data/runtime/${label##*.}.log"
  cat > "$LA/$label.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$REPO/run.py</string>
    <string>$arg</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>
$intervals  </array>
  <key>RunAtLoad</key><false/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$log</string>
  <key>StandardErrorPath</key><string>$log</string>
</dict>
</plist>
PLIST
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$LA/$label.plist"
  launchctl enable "$DOMAIN/$label"
  echo "✅ installed $label"
}

write_plist "com.openwhale.whalemail.once" "--once" "$ONCE_INTERVALS"
write_plist "com.openwhale.whalemail.digest" "--digest" "$DIGEST_INTERVALS"

# heartbeat: every HB hours after the digest (first at DH+HB; last before AE-1)
HEARTBEAT_INTERVALS=""
for h in $(seq "$((DH + HB))" "$HB" "$((AE - 1))"); do
  HEARTBEAT_INTERVALS+="    <dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>0</integer></dict>
"
done
write_plist "com.openwhale.whalemail.heartbeat" "--heartbeat" "$HEARTBEAT_INTERVALS"

# bot: always-on long poll (KeepAlive). Requires WHALEMAIL_BOT_TOKEN in .env.
BOT_LABEL="com.openwhale.whalemail.bot"
cat > "$LA/${BOT_LABEL}.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${BOT_LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$REPO/run.py</string><string>--bot</string></array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$REPO/data/runtime/bot.log</string>
  <key>StandardErrorPath</key><string>$REPO/data/runtime/bot.log</string>
</dict>
</plist>
PLIST
# Restart semantics: already loaded → kickstart -k (restarts the process with the new code);
# not loaded → bootstrap. kickstart does not reload the plist: after editing the bot plist,
# bootout + bootstrap on the machine itself.
if launchctl print "$DOMAIN/${BOT_LABEL}" >/dev/null 2>&1; then
  launchctl kickstart -k "$DOMAIN/${BOT_LABEL}"
  echo "✅ restarted ${BOT_LABEL} (kickstart -k)"
else
  launchctl bootstrap "$DOMAIN" "$LA/${BOT_LABEL}.plist"
  launchctl enable "$DOMAIN/${BOT_LABEL}"
  echo "✅ installed ${BOT_LABEL} (first bootstrap)"
fi

echo
echo "status:  launchctl print $DOMAIN/com.openwhale.whalemail.once | grep -iE 'state|runs|next'"
echo "run now: launchctl kickstart -k $DOMAIN/com.openwhale.whalemail.digest"
echo "logs:    tail -f $REPO/data/runtime/once.log $REPO/data/runtime/digest.log"
echo "remove:  bash scripts/install-whalemail-launchd.sh --uninstall"
