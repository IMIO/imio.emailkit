"""``dummy.minimal``'s entire email test suite.

This is the file a consumer add-on writes, in full. Two class attributes, no
imports beyond the base class, no harness of its own:

* ``package`` -- the package whose ZCML registers the templates, i.e. the lookup
  namespace.
* ``templates`` -- the basenames, which the base class namespaces for you.

The base class finds ``fixtures/`` and ``golden/`` beside this file, renders every
(template x language x part) through ``render()`` and diffs against the
committed snapshot. It also audits the *committed* snapshot for unresolved
``${...}`` -- a snapshot taken while the render engine was broken would otherwise
be confirmed for ever.

Two things are different here from a real add-on, both artefacts of living inside
``imio.emailkit``'s own test tree:

1. **The filename.** In a real add-on this is ``tests/test_emails.py``. pytest
   requires unique test-module basenames within one rootdir when the directories
   are not packages, and ``tests/test_golden.py`` already exists here.
2. **Registration.** A real add-on is pip-installed, so Zope's autoinclude runs its
   ``configure.zcml`` for it. ``tests/dummies/conftest.py`` puts these two on
   ``sys.path`` and executes their ZCML itself instead; see
   ``tests/dummies/README.md``.

Regenerating snapshots is deliberate and never a side effect of a failure::

    EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
"""

from imio.emailkit.golden import GoldenTemplateTests


class TestEmailGoldens(GoldenTemplateTests):
    package = "dummy.minimal"
    templates = ("notification",)

    #: One language, because this add-on is the minimum. The default is
    #: ``("fr", "en")`` and a real add-on serving FR/NL communes should keep both
    #: -- a translation that stops resolving then shows up as a diff rather than
    #: as nothing at all.
    languages = ("fr",)
