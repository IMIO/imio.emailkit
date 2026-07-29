"""SPEC §8.3's content-rule action, and nothing else.

> **Content rules:** a new action type *"Send styled email"* -- edit form offers
> the registered template names (vocabulary from discovery) + recipient sources;
> executor delegates to ``Email(...)``. The stock mail action is left untouched.

One module, :mod:`imio.emailkit.contentrules.mail`, holding the four pieces
``plone.contentrules`` asks for: the configuration schema, the data object stored
in the rule, the executor, and the add/edit forms.

**This package is a caller of §6.2, not a part of it.** The executor's whole body
is "build an ``Email``, hand it the recipients and the context, call ``.send()``";
everything that can go wrong -- an unknown template, an unresolvable recipient, a
missing sender -- is already a loud error inside the builder, and the executor's
job is to not get in the way of it. Nothing here adds a builder method, and
nothing here catches an exception without re-raising it.

**Everything is registered in ZCML, and there is no GenericSetup step.** The
element, the executor adapter and the two forms all come from
``contentrules/configure.zcml``, which is how every ``plone.contentrules`` action
in the Plone ecosystem is registered. So the action type exists in any site the egg
is installed in, including one that applied ``imio.emailkit:base`` -- and that is
right, not an oversight: §8.2's opt-out is about not restyling Plone's *stock
mails*, and an action type is inert until somebody creates a rule that uses it.
``configure.zcml`` says so at the registration site.
"""
