"""User-facing text belongs in digest/i18n.py, in both languages.

This guards the common slip of writing a Chinese string straight into code: any CJK character
outside the string table (and the two documented exceptions) fails the suite.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {
    ROOT / "digest" / "i18n.py",
    ROOT / "settings.py",  # language display name
    ROOT / "agent" / "bot.py",  # the Chinese /new alias in _RESET_COMMANDS
}
CJK = re.compile(r"[一-鿿]")


def test_no_cjk_outside_i18n():
    offenders = []
    for path in ROOT.rglob("*.py"):
        if {".venv", "tests", "local"} & set(path.parts) or path in ALLOWED:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CJK.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, "add the string to digest/i18n.py (en and zh) instead:\n" + "\n".join(
        offenders
    )
