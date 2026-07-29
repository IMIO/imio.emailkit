"""SPEC §4's registration, in the smallest form that is still real.

Deliberately importable without Plone: the recipe's generated scripts load this
module to read the ``directory`` key, and a build tool should not need a CMS to
find out where to put a file. A real addon's ``__init__`` would use
``zope.i18nmessageid.MessageFactory`` for the msgids; a plain string is enough
here, and ``render()`` translates a plain string to itself.
"""

emailkit = {
    "directory": "templates",
    "templates": {
        "demo": {
            "subject": "email_subject_demo",
            "preheader": "email_preheader_demo",
        },
    },
}
