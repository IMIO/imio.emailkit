"""``dummy.complete``'s entire email test suite (SPEC §7).

Two languages instead of one, and otherwise the same four lines as
``dummy.minimal``. That is the point of a provided base class: the suite does not
grow with the add-on.

``languages = ("fr", "en")`` is the shipped default and is what a real add-on
should keep. Snapshotting a second language is what turns "the translation stopped
resolving" from an invisible regression into a diff -- and here it also pins the
locale helper, because ``${python: format_date(when)}`` renders
``12 août 2026`` in the French snapshot and ``August 12, 2026`` in the English one.
A ``language=`` argument that stopped being honoured would make the two snapshots
identical and fail here. That is the one thing a second language buys that nothing
else in the suite does, which is why it survived the trim below.

**One template, though.** ``notification`` was snapshotted here too, and it bought
nothing ``convocation`` does not: the same layout, the same helpers, one more pair
of files to regenerate every time a shared component moves. ``convocation`` is the
richer of the two and the one that uses this add-on's *own* components, so it is
the one kept. That ``dummy.complete`` registers two templates is still asserted --
in ``test_discovery_dummies.py`` and ``test_consumer_ci.py``, where it belongs,
and without a byte comparison.

Regenerate deliberately, never as a side effect of a failure::

    EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
"""

from imio.emailkit.golden import GoldenTemplateTests


class TestEmailGoldens(GoldenTemplateTests):
    package = "dummy.complete"
    templates = ("convocation",)
