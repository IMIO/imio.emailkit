"""``imio.emailkit``'s own binding of the shipped golden harness.

The harness itself now lives in the egg, at :mod:`imio.emailkit.golden`, because
the package promises consumers "a provided test base class" and a base class
nobody can import is not provided (Phase 4). This
module is
what is left: the four lines that bind it to *this* package's suite.

Keeping the shim rather than editing every subclass is deliberate -- it is the
proof that exporting the class was a **move** and not a fork. ``tests/test_golden.py``
is unchanged, and its subclasses still read ``golden_harness.GoldenTemplateTests``.

For a consumer add-on the equivalent of this file does not exist: they subclass
:class:`imio.emailkit.golden.GoldenTemplateTests` directly and set ``package`` and
``templates``. See ``tests/dummies/`` for two worked examples.
"""

from imio.emailkit.golden import diff  # noqa: F401  (re-exported; used by tests)
from imio.emailkit.golden import GoldenTemplateTests as ShippedGoldenTemplateTests

import support


class GoldenTemplateTests(ShippedGoldenTemplateTests):
    """The shipped harness, bound to ``imio.emailkit``'s own paths and languages.

    Every value below happens to equal the shipped default -- ``tests/test_golden.py``
    sits next to ``tests/fixtures/`` and ``tests/golden/``, which is exactly the
    shipped layout. They are stated anyway, because ``tests/support.py`` is where this suite
    keeps the contract it was written against, and a default that silently starts
    resolving somewhere else should show up as a diff here.
    """

    package = support.PACKAGE_NAME
    languages = support.GOLDEN_LANGUAGES
    fixtures_dir = support.FIXTURES_DIR
    golden_dir = support.GOLDEN_DIR

    def assert_clean(self, rendered, label):
        """Use this suite's own audit, which is stricter than the shipped one.

        ``support.assert_render_is_clean`` is the same check plus whatever else
        this package has learned to look for; the shipped default is the subset
        every consumer needs.
        """
        support.assert_render_is_clean(rendered, label)
