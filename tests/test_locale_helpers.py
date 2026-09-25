"""Locale-aware formatting helpers.

Every test compares FR and EN output, since a helper that ignores its
language argument still returns a plausible string for either.
"""

from datetime import date
from datetime import datetime

import pytest
import support


support.require_runtime()

format_date, format_datetime, format_number = support.require_contract(
    "imio.emailkit.helpers",
    "the locale-helpers contract",
    "format_date",
    "format_datetime",
    "format_number",
)

from imio.emailkit import render  # noqa: E402


#: 12 August: unambiguous between day-first and month-first locales.
PROBE_DATE = date(2026, 8, 12)
PROBE_DATETIME = datetime(2026, 8, 12, 17, 30, 0)
PROBE_NUMBER = 1234.5

LANGUAGES = ("fr", "nl", "en")


class TestFormatDate:
    def test_fr_and_en_differ(self, integration):
        assert format_date(PROBE_DATE, "fr") != format_date(PROBE_DATE, "en")

    def test_fr_puts_the_day_before_the_month(self, integration):
        """Checked as ordering, not position, since a long format spells
        the month as a word."""
        formatted = format_date(PROBE_DATE, "fr")
        day, month = _positions(formatted, "12", ("08", "8", "août", "aout"))

        assert day is not None, f"no day in {formatted!r}"
        assert month is not None, f"no month in {formatted!r}"
        assert day < month, f"French date is not day-first: {formatted!r}"

    def test_en_puts_the_month_before_the_day(self, integration):
        formatted = format_date(PROBE_DATE, "en")
        day, month = _positions(formatted, "12", ("08", "8", "August", "Aug"))

        assert day is not None, f"no day in {formatted!r}"
        assert month is not None, f"no month in {formatted!r}"
        assert month < day, f"English date is not month-first: {formatted!r}"

    def test_the_month_name_itself_is_localised(self, integration):
        """An English month name in a French mail is the most visible
        failure a locale-aware helper can have."""
        fr = format_date(PROBE_DATE, "fr")
        en = format_date(PROBE_DATE, "en")

        if not any(token in en for token in ("August", "Aug")):
            pytest.skip(
                f"the helper's default length is numeric ({en!r}), so no month "
                "name is emitted to check. Ordering is covered above."
            )

        assert "August" not in fr, f"English month name in a French date: {fr!r}"

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_every_shipped_language_formats(self, integration, language):
        """A raise here turns a translated mail into a server error."""
        assert format_date(PROBE_DATE, language)

    def test_de_is_supported(self, integration):
        assert format_date(PROBE_DATE, "de")


class TestFormatDatetime:
    def test_fr_and_en_differ(self, integration):
        assert format_datetime(PROBE_DATETIME, "fr") != format_datetime(
            PROBE_DATETIME, "en"
        )

    def test_fr_uses_a_24_hour_clock_and_en_does_not(self, integration):
        """17:30 vs 5:30 PM."""
        fr = format_datetime(PROBE_DATETIME, "fr")
        en = format_datetime(PROBE_DATETIME, "en")

        assert "17" in fr, f"French datetime is not 24-hour: {fr!r}"
        assert "PM" in en.upper() or "17" not in en, (
            f"English datetime looks 24-hour: {en!r}"
        )


class TestFormatNumber:
    def test_fr_and_en_differ(self, integration):
        assert format_number(PROBE_NUMBER, "fr") != format_number(PROBE_NUMBER, "en")

    def test_fr_uses_a_comma_decimal_separator(self, integration):
        formatted = format_number(PROBE_NUMBER, "fr")

        assert "1234,5" in formatted.replace(" ", "").replace("\xa0", "").replace(
            " ", ""
        ), f"French number does not use a decimal comma: {formatted!r}"

    def test_en_uses_a_point_decimal_separator(self, integration):
        formatted = format_number(PROBE_NUMBER, "en")

        assert "1,234.5" in formatted or "1234.5" in formatted, (
            f"English number does not use a decimal point: {formatted!r}"
        )


class TestHelpersAreBoundToTheRenderLanguage:
    """A correct helper and a render that hands it the right language are
    two independent things; this checks the second one."""

    TEMPLATE = support.NOTIFICATION

    def test_a_formatted_datetime_follows_the_render_language(self, integration):
        context = support.load_fixture(self.TEMPLATE)
        expires = context.get("expires") or PROBE_DATETIME

        html_fr, _ = render(
            support.qualified(self.TEMPLATE), context=dict(context), language="fr"
        )
        html_en, _ = render(
            support.qualified(self.TEMPLATE), context=dict(context), language="en"
        )

        fr_expected = format_datetime(expires, "fr")
        en_expected = format_datetime(expires, "en")

        if fr_expected not in html_fr and en_expected not in html_en:
            pytest.skip(
                f"{self.TEMPLATE} does not format {expires!r} through "
                "format_datetime, so the binding is not observable through a "
                "render. The helpers themselves are covered above; this gap is "
                "an authoring choice in the template, reported rather than "
                "asserted away."
            )

        assert fr_expected in html_fr
        assert en_expected in html_en


def _positions(text, day_token, month_tokens):
    """Return the index of the day and of the earliest month token found."""
    day = text.find(day_token)
    found = [text.find(token) for token in month_tokens if text.find(token) != -1]
    return (day if day != -1 else None), (min(found) if found else None)
