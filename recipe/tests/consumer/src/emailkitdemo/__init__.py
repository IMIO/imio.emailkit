"""Registration lives in ``configure.zcml``, not here.

Kept deliberately empty: the recipe's buildout-time collector greps ZCML on
disk and never imports this module, and the generated scripts' real scan
(``imio.emailkit.scan.scan_package``) executes the ZCML directly. A real
addon's ``__init__`` has no reason to know about templates at all any more.
"""
