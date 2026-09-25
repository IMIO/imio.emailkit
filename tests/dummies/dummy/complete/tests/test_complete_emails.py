"""``dummy.complete``'s entire email test suite.

Two languages, the shipped default: a second language also pins the locale
helper, since ``format_date(when)`` renders differently in each. Only
``convocation`` is snapshotted, the richer of the two templates; a second
snapshot of ``notification`` would buy nothing.

Regenerate deliberately, never as a side effect of a failure::

    EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
"""

from imio.emailkit.golden import GoldenTemplateTests


class TestEmailGoldens(GoldenTemplateTests):
    package = "dummy.complete"
    templates = ("convocation",)
