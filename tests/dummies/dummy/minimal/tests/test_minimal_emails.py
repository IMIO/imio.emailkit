"""``dummy.minimal``'s entire email test suite.

The file a consumer add-on writes, in full: ``package`` and ``templates``,
nothing else. The base class finds ``fixtures/``/``golden/`` beside this
file and diffs every rendered (template x language x part) against the
committed snapshot.

Named ``test_minimal_emails.py``, not ``test_emails.py`` like a real add-on
would, since ``tests/test_golden.py`` already exists in this package.

Regenerate deliberately, never as a side effect of a failure::

    EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
"""

from imio.emailkit.golden import GoldenTemplateTests


class TestEmailGoldens(GoldenTemplateTests):
    package = "dummy.minimal"
    templates = ("notification",)

    #: One language, since this add-on is the minimum. Default is ``("fr", "en")``.
    languages = ("fr",)
