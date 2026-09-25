"""Locale-aware formatting helpers, as plain functions.

``render()`` binds these to the render language and injects them into
the template namespace, so a template writes
``${python: format_date(item/created)}`` without passing the language.

Formats using CLDR data from ``zope.i18n``, keyed on the render
language, not the current request.
"""

from zope.i18n.format import NumberFormat
from zope.i18n.locales import locales
from zope.i18n.locales.provider import LoadLocaleError

import datetime
import re


#: Language used when the caller's is unknown to CLDR.
FALLBACK_LANGUAGE = "en"

#: Date length for :func:`format_date`/:func:`format_datetime`. ``long``
#: avoids the two-digit year in zope.i18n's ``medium`` fr/nl patterns.
DEFAULT_DATE_LENGTH = "long"

#: Time length for :func:`format_datetime`. ``short`` drops the broken
#: ``+000`` zone the ``long`` pattern appends.
DEFAULT_TIME_LENGTH = "short"


def format_date(value, language, length=DEFAULT_DATE_LENGTH):
    """Localised date: ``12 août 2026`` (fr), ``August 12, 2026`` (en)."""
    formatter = locale_for(language).dates.getFormatter("date", length)
    return formatter.format(as_datetime(value))


def format_datetime(
    value, language, length=DEFAULT_DATE_LENGTH, time_length=DEFAULT_TIME_LENGTH
):
    """Localised date and time: ``12 août 2026 17:30``, ``August 12, 2026 5:30 PM``.

    Joins the two CLDR halves with a plain space.
    """
    dates = locale_for(language).dates
    value = as_datetime(value)
    return "{} {}".format(
        dates.getFormatter("date", length).format(value),
        dates.getFormatter("time", time_length).format(value),
    )


def format_number(value, language, pattern=None):
    """Localised number: ``1 234,5`` (fr), ``1,234.5`` (en).

    Pass a float, not ``int``, for minimum fraction digits such as ``42,00``.
    """
    formatter = locale_for(language).numbers.getFormatter("decimal")
    if pattern is not None:
        formatter = NumberFormat(pattern, formatter.symbols)
    return formatter.format(value)


def locale_for(language):
    """The CLDR locale for ``language``, degrading to the bare language, then en.

    Degrading beats raising ``LoadLocaleError``: a mail with a
    slightly-wrong locale beats no mail.
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

    Zope's ``DateTime`` exposes ``year`` as a method, unreadable by CLDR.
    """
    if hasattr(value, "asdatetime"):
        return value.asdatetime()
    if isinstance(value, str):
        return datetime.datetime.fromisoformat(value)
    return value


def bind(language):
    """Return the three helpers bound to ``language``, for a template namespace."""

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
