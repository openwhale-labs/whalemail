"""String table: both languages cover the same keys; unknown language falls back to English."""

from digest import i18n


def test_languages_have_identical_keys():
    assert set(i18n.STRINGS["en"]) == set(i18n.STRINGS["zh"])


def test_unknown_language_falls_back_to_english(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_LANGUAGE", "fr")
    assert i18n.t("bucket.action") == "Action needed"
    monkeypatch.setenv("WHALEMAIL_LANGUAGE", "zh")
    assert i18n.t("bucket.action") == "要去操作"


def test_every_string_formats_with_its_placeholders():
    import string

    fmt = string.Formatter()
    for lang, table in i18n.STRINGS.items():
        for key, s in table.items():
            fields = {f for _, f, _, _ in fmt.parse(s) if f}
            s.format(**{f: "x" for f in fields})
