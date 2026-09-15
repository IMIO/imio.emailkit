"""Locale-aware formatting helpers, as plain functions.

``render()`` injects these into the template namespace *already bound* to the
render language, which is what lets a template write
``${python: format_date(item/created)}`` without repeating the language on every
call. They live here as free functions taking the language explicitly so they can
be tested, and reused, without a render.

Every pattern comes from the CLDR data ``zope.i18n`` ships, so the answer depends
on the *render* language rather than on the current request. That is the whole
point: per-language sending renders the same template once per language
group, and a helper reading the request would format all of them identically.

Deliberately **not** ``plone.api.portal.get_localized_time``: it formats in the
language the current request negotiated, and needs a request, a portal and the
``translation_service`` tool. All three contradict the "pure function" design, and
none of them can be pointed at another language. The trade-off, worth knowing: a
site's date-format overrides in the Plone control panel do not reach mails.
"""

from zope.i18n.format import NumberFormat
from zope.i18n.locales import locales
from zope.i18n.locales.provider import LoadLocaleError

import datetime
import re


#: Language used when the caller's is unknown to CLDR.
FALLBACK_LANGUAGE = "en"

#: CLDR length used by :func:`format_date` and by :func:`format_datetime`'s date
#: half. ``long`` rather than ``medium`` on purpose: zope.i18n ships old CLDR
#: data whose ``medium`` French and Dutch patterns still carry a two-digit year
#: ("12 mars 26"), which has no place in a transactional mail. ``long`` also
#: spells the month out, which removes the 12/08 ambiguity entirely.
DEFAULT_DATE_LENGTH = "long"

#: CLDR length used by :func:`format_datetime`'s time half. ``short`` drops the
#: seconds and, more importantly, the broken ``+000`` zone that the stale
#: ``long`` time pattern appends.
DEFAULT_TIME_LENGTH = "short"


def format_date(value, language, length=DEFAULT_DATE_LENGTH):
    """Localised date: ``12 août 2026`` (fr), ``August 12, 2026`` (en)."""
    formatter = locale_for(language).dates.getFormatter("date", length)
    return formatter.format(as_datetime(value))


def format_datetime(
    value, language, length=DEFAULT_DATE_LENGTH, time_length=DEFAULT_TIME_LENGTH
):
    """Localised date and time: ``12 août 2026 17:30``, ``August 12, 2026 5:30 PM``.

    Both halves come from CLDR; only the space between them is ours, because
    CLDR's own combining pattern forces the two halves to the same length and the
    stale ``long`` time pattern appends ``+000``.
    """
    dates = locale_for(language).dates
    value = as_datetime(value)
    return "{} {}".format(
        dates.getFormatter("date", length).format(value),
        dates.getFormatter("time", time_length).format(value),
    )


def format_number(value, language, pattern=None):
    """Localised number: ``1 234,5`` (fr), ``1,234.5`` (en).

    ``pattern`` is a CLDR number pattern such as ``"#,##0.00"``; omitted, the
    locale's own decimal pattern applies. Note that zope.i18n applies a pattern's
    minimum fraction digits to floats but not to ``int``, so pass a float when
    you want ``42,00``.
    """
    formatter = locale_for(language).numbers.getFormatter("decimal")
    if pattern is not None:
        formatter = NumberFormat(pattern, formatter.symbols)
    return formatter.format(value)


def locale_for(language):
    """The CLDR locale for ``language``, degrading to the bare language then en.

    Plone hands out codes like ``fr``, ``fr-be`` and ``fr_BE``; zope.i18n ships
    data for only some country variants (``fr_BE`` yes, ``fr_ZZ`` no) and raises
    ``LoadLocaleError`` for the rest. Degrading beats raising: a mail with
    slightly-wrong-locale dates is worth more than no mail at all.
    """
    parts = re.split(r"[-_]", language or "")
    code = (parts[0] or FALLBACK_LANGUAGE).lower()
    country = parts[1].upper() if len(parts) > 1 and parts[1] else None
    for candidate in ((code, country), (code, None), (FALLBACK_LANGUAGE, None)):
        try:
            return locales.getLocale(*candidate)
        except LoadLocaleError:
            continue
    raise LookupError(f"No CLDR locale for {language!r} and none for English")


def as_datetime(value):
    """Coerce what Plone hands templates into something CLDR can format.

    Zope's ``DateTime`` exposes ``year`` as a *method*, so the formatters cannot
    read it; ISO strings show up in fixtures. Anything else passes through
    untouched, and an unparseable value raises rather than formatting to "None".
    """
    if hasattr(value, "asdatetime"):
        return value.asdatetime()
    if isinstance(value, str):
        return datetime.datetime.fromisoformat(value)
    return value


def bind(language):
    """Return the three helpers bound to ``language``, for a template namespace.

    Locale-aware formatting helpers bound to the render language, so no
    template ever reinvents French date formatting.
    """

    def bound_format_date(value, length=DEFAULT_DATE_LENGTH):
        return format_date(value, language, length)

    def bound_format_datetime(
        value, length=DEFAULT_DATE_LENGTH, time_length=DEFAULT_TIME_LENGTH
    ):
        return format_datetime(value, language, length, time_length)

    def bound_format_number(value, pattern=None):
        return format_number(value, language, pattern)

    return {
        "format_date": bound_format_date,
        "format_datetime": bound_format_datetime,
        "format_number": bound_format_number,
    }
