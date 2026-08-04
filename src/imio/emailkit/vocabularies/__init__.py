"""Named vocabularies over the template registry.

One vocabulary, ``imio.emailkit.templates``, listing every registered template
name. It exists because the content-rule edit form offers the registered
template names, and it is a *named* utility rather than a function the schema
imports so that the form, the schema and any other consumer all reach the same
list by name.

**It reads the discovery registry and nothing else.** That is the same registry
``@@emailkit-preview`` lists and the same one the ``Email`` builder resolves
through, so a template any add-on declares with ``<emailkit:templates>`` shows
up in the form without a line of code changing here. That is the whole point:
the set of templates is a property of the ZCML the instance loaded, and a
hardcoded list in a schema would quietly disagree with it.

**Read live, never copied.** :func:`imio.emailkit.discovery.available_templates`
answers straight from the registry the ``emailkit:templates`` directive fills at
configuration time; there is no cache to go stale, and none is added here. A
list captured at import time in this module would be built before the directives
that fill the registry have run, and would then survive every later change --
an add-on installed in the same process, or a test that registers a throwaway
package -- making the vocabulary the one place in the package that still
believes in a template nobody registers any more.
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
    """Every template the registry knows about, sorted by name.

    Term value, token and title are all the namespaced name
    (``"dummy.complete:convocation"``). Deliberately not prettified: the name is
    the identity of a template, it is what the stored rule holds, it is what
    ``TemplateNotFound`` reports, and its ``<package>:<basename>`` shape is the
    only thing that tells three add-ons' ``notification`` templates apart.
    Sorting is this vocabulary's own doing, so the order a form shows never
    depends on which package's ZCML the instance happened to load first.
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
