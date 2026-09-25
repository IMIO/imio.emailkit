"""``imio.emailkit``'s own binding of the shipped golden harness.

The harness lives in :mod:`imio.emailkit.golden`; this module binds it to
this package's own paths and languages. A consumer add-on subclasses the
shipped class directly instead; see ``tests/dummies/`` for examples.
"""

from imio.emailkit.golden import diff  # noqa: F401  (re-exported)
from imio.emailkit.golden import GoldenTemplateTests as ShippedGoldenTemplateTests

import support


class GoldenTemplateTests(ShippedGoldenTemplateTests):
    """The shipped harness, bound to ``imio.emailkit``'s own paths and languages.

    Every value equals the shipped default; stated explicitly so a change in
    the default shows up as a diff here.
    """

    package = support.PACKAGE_NAME
    languages = support.GOLDEN_LANGUAGES
    fixtures_dir = support.FIXTURES_DIR
    golden_dir = support.GOLDEN_DIR

    def assert_clean(self, rendered, label):
        """Use this suite's own audit: the shipped check plus this package's extras."""
        support.assert_render_is_clean(rendered, label)
