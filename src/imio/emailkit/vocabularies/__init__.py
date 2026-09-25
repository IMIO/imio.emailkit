"""Named vocabularies over the template registry.

One vocabulary, ``imio.emailkit.templates``, lists every registered template
name. The content-rule edit form offers these names, and this is a named
utility rather than a function the schema imports, so every consumer reaches
the same list by name.

It reads the discovery registry and nothing else: the same registry
``@@emailkit-preview`` lists, and the same one the ``Email`` builder resolves
through. A template any add-on declares with ``<emailkit:templates>`` shows up
here without any code change.

:func:`imio.emailkit.discovery.available_templates` is called live, never
cached. A list captured at import time would be built before the ZCML
directives that fill the registry have run.
"""

from imio.emailkit.discovery import available_templates
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


#: The name the ``IVocabularyFactory`` utility is registered under, and the
#: string schemas pass to ``schema.Choice(vocabulary=...)``. Kept here, not
#: spelled twice, so a typo cannot produce a ``VocabularyRegistryError`` far
#: from the schema that caused it.
TEMPLATES = "imio.emailkit.templates"


@implementer(IVocabularyFactory)
class Templates:
    """Every template the registry knows about, sorted by name.

    Term value, token and title are all the namespaced name, not prettified:
    it is the template's identity, what the stored rule holds, and what
    ``TemplateNotFound`` reports. Sorting here keeps the order stable no
    matter which package's ZCML loaded first.
    """

    def __call__(self, context=None):
        return SimpleVocabulary([
            SimpleTerm(value=name, token=name, title=name)
            for name in available_templates()
        ])


#: The utility instance ``configure.zcml`` registers. A module-level
#: singleton, so every lookup gets the same object; it holds no state.
templates = Templates()
