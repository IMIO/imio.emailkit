"""Named vocabularies over SPEC §4's entry-point discovery.

One vocabulary, ``imio.emailkit.templates``, listing every registered template
name. It exists because §8.3's content-rule edit form "offers the registered
template names (vocabulary from discovery)", and it is a *named* utility rather
than a function the schema imports so that the form, the schema and any other
consumer all reach the same list by name.

**It reads discovery and nothing else.** ``get_templates()`` is the same call
``@@emailkit-preview`` makes (§6.3) and the same cache the ``Email`` builder
resolves through (§6.2), so a template registered by *any* add-on shows up in
the form without a line of code changing here. That is the whole point: §4 makes
the set of templates a property of the installed distributions, and a hardcoded
list in a schema would quietly disagree with it.

**Not cached here.** :func:`imio.emailkit.discovery.get_templates` already caches
the scan for the life of the process, and it has an ``invalidate_cache()`` that
tests use to install a dummy add-on. A second cache in this module would survive
that invalidation and make the vocabulary the one place in the package that
still believes in a template nobody registers any more.
"""

from imio.emailkit.discovery import available_templates
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


#: The name the ``IVocabularyFactory`` utility is registered under, and the
#: string schemas pass to ``schema.Choice(vocabulary=...)``. Kept here rather
#: than spelled twice: a typo in one of the two places produces
#: ``VocabularyRegistryError`` at *form render* time, which is far away from the
#: schema that caused it.
TEMPLATES = "imio.emailkit.templates"


@implementer(IVocabularyFactory)
class Templates:
    """Every template SPEC §4's discovery knows about, sorted by name.

    Term value, token and title are all the namespaced name
    (``"dummy.complete:convocation"``). Deliberately not prettified: the name is
    what §4 makes the identity of a template, it is what the stored rule holds,
    it is what ``TemplateNotFound`` reports, and its ``<package>:<basename>``
    shape is the only thing that tells three add-ons' ``notification`` templates
    apart.
    """

    def __call__(self, context=None):
        return SimpleVocabulary([
            SimpleTerm(value=name, token=name, title=name)
            for name in available_templates()
        ])


#: The utility instance ``configure.zcml`` registers. A module-level singleton
#: rather than a ``factory=`` registration so the vocabulary object is the same
#: one every lookup gets; it holds no state, so there is nothing to share badly.
templates = Templates()
