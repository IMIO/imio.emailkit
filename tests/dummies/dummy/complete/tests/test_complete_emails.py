"""``dummy.complete``'s entire email test suite (SPEC §7).

Two templates instead of one, two languages instead of one, and otherwise the same
four lines as ``dummy.minimal``. That is the point of a provided base class: the
suite does not grow with the add-on.

``languages = ("fr", "en")`` is the shipped default and is what a real add-on
should keep. Snapshotting a second language is what turns "the translation stopped
resolving" from an invisible regression into a diff -- and here it also pins the
locale helper, because ``${python: format_date(when)}`` renders
``12 août 2026`` in the French snapshot and ``August 12, 2026`` in the English one.
A ``language=`` argument that stopped being honoured would make the two snapshots
identical and fail here.

Regenerate deliberately, never as a side effect of a failure::

    EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
"""

from imio.emailkit.golden import GoldenTemplateTests


class TestEmailGoldens(GoldenTemplateTests):
    package = "dummy.complete"
    templates = ("convocation", "notification")
