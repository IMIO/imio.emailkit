from imio.emailkit.interfaces import IEmailkitLayer


class ISiteLayer(IEmailkitLayer):
    """A site package's own browser layer, *extending* ours.

    The extension is load bearing, not decoration -- see the package docstring.
    """
