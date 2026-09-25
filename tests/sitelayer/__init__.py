"""A stand-in for a site/client package that overrides our overrides.

Test support for a site replacing template markup via a jbot directory on a
*more specific* browser layer. "More specific" only means something for a
layer that extends ``IEmailkitLayer``; a sibling layer's precedence is
arbitrary. So this package extends it.
"""
