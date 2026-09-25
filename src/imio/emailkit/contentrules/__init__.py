"""The *"Send styled email"* content-rule action.

One module, :mod:`imio.emailkit.contentrules.mail`, holding the four pieces
``plone.contentrules`` asks for: the configuration schema, the data object
stored in the rule, the executor, and the add/edit forms.

The executor is a caller of the builder, not a part of it: it builds an
``Email``, hands it the recipients and the context, and calls ``.send()``.
Every failure mode is already a loud error inside the builder.

Everything is registered in ZCML; there is no GenericSetup step. The action
type therefore exists in any site the egg is installed in, including one that
applied ``imio.emailkit:base``: an action type is inert until a rule uses it.
"""
