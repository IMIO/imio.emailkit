"""Importing this module fails, on purpose.

``configure.zcml`` points a ``browser:page`` at ``Boom`` in here. The scan
swallows that directive without ever resolving its schema, so this module must
stay unimported -- if a scan ever starts loading foreign handlers, the tests
fail here rather than mysteriously somewhere downstream.
"""

raise ImportError("scan must never import what foreign directives point at")
