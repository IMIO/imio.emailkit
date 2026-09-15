"""Attachment sources -- polymorphic in, ``(bytes, filename, type)`` out.

``.attach(source, filename=None, mimetype=None)`` takes "raw ``bytes``, a filesystem
path (``str``/``Path``), an open binary file object, a ``NamedBlobFile``/``NamedFile``
value, or a Plone File/Image content object". The builder stores those three values
verbatim; this module turns them into something
:meth:`email.message.EmailMessage.add_attachment` accepts, at ``.send()`` time.

Like recipients, and for the same reason, failures are **collected** and raised
once as :class:`~imio.emailkit.interfaces.AttachmentError`.

Any Plone-version-specific branch is isolated here rather
than in the builder. :func:`read_source` is that seam: it is the only function that
knows what a source can be.
"""

from dataclasses import dataclass
from imio.emailkit.interfaces import AttachmentError
from pathlib import Path
from plone.namedfile.interfaces import INamed
from plone.rfc822.interfaces import IPrimaryFieldInfo

import mimetypes
import os


@dataclass(frozen=True)
class Attachment:
    """One resolved attachment, in exactly the shape ``add_attachment`` wants."""

    data: bytes
    filename: str
    maintype: str
    subtype: str


def resolve(specs):
    """Resolve every ``(source, filename, mimetype)`` spec the builder collected.

    :param specs: iterable of the 3-tuples ``.attach()`` recorded, in order
    :returns: list of :class:`Attachment`, same order
    :raises AttachmentError: listing every spec that could not be resolved

    Order is preserved because it is the order the parts appear in the message, and
    that is the order a mail client lists them in.
    """
    attachments = []
    problems = []
    for source, filename, mimetype in specs:
        try:
            attachments.append(resolve_one(source, filename, mimetype))
        except AttachmentError as error:
            problems.extend(error.problems)
    if problems:
        raise AttachmentError(problems)
    return attachments


def resolve_one(source, filename=None, mimetype=None):
    """Resolve one attachment spec, raising :class:`AttachmentError` on failure.

    Precedence for both metadata values: what the caller passed wins, then what
    the source carries, then -- for the mimetype only -- what
    :func:`mimetypes.guess_type` makes of the filename. Both are
    inferred "where the source carries them" and both are required for ``bytes``;
    an explicit argument overriding a blob's own ``contentType`` is the point of
    having the arguments at all.
    """
    data, source_filename, source_mimetype = read_source(source)
    filename = (filename or source_filename or "").strip()
    if not filename:
        raise AttachmentError([
            f"{describe(source)} carries no filename, so `filename=` is required"
        ])
    mimetype = (mimetype or source_mimetype or guess_mimetype(filename) or "").strip()
    if not mimetype:
        raise AttachmentError([
            f"{describe(source)} (filename {filename!r}) carries no mimetype and "
            f"none could be guessed from the extension, so `mimetype=` is required"
        ])
    maintype, subtype = split_mimetype(mimetype, source, filename)
    return Attachment(data=data, filename=filename, maintype=maintype, subtype=subtype)


def read_source(source):
    """Return ``(data, filename, mimetype)`` for one ``.attach()`` source.

    ``filename`` and ``mimetype`` are ``None`` when the source does not carry them,
    which is the caller's cue that the corresponding argument was mandatory.

    The order of the tests is load-bearing:

    * ``bytes`` first, because it is the one source that carries nothing at all;
    * ``INamed`` before the path test, because a blob value is not a path but the
      *content object* tests below would happily try to adapt one;
    * the path test before the file-object test, because ``str``/``Path`` have no
      ``read`` but the reverse order would make the ``read`` duck-type the
      catch-all it must not be;
    * ``IPrimaryFieldInfo`` last of the real branches, because it is a component
      lookup and everything above it is a cheap type check.
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source), None, None

    if INamed.providedBy(source):
        # NamedFile / NamedImage / NamedBlobFile / NamedBlobImage all expose these
        # three; `contentType` may legitimately be empty, in which case the
        # filename's extension gets a turn.
        return (
            bytes(source.data or b""),
            getattr(source, "filename", None),
            getattr(source, "contentType", None) or None,
        )

    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        try:
            data = path.read_bytes()
        except OSError as error:
            raise AttachmentError([
                f"{str(path)!r} could not be read: {error}"
            ]) from None
        return data, path.name, None

    if hasattr(source, "read"):
        try:
            data = source.read()
        except Exception as error:
            raise AttachmentError([
                f"{describe(source)} could not be read: {error}"
            ]) from None
        if not isinstance(data, bytes):
            raise AttachmentError([
                f"{describe(source)} is not open in binary mode; it read "
                f"{type(data).__name__}, not bytes"
            ])
        # An open file's `name` is the path it was opened with -- but it is an int
        # for a file opened from a descriptor, and absent for BytesIO.
        name = getattr(source, "name", None)
        filename = Path(name).name if isinstance(name, (str, os.PathLike)) else None
        return data, filename, None

    # A Plone File or Image content object. `IPrimaryFieldInfo` is the boring Plone
    # way to ask "which field is the payload" -- it answers `file` for File and
    # `image` for Image without this module knowing either name, and it answers for
    # any consumer's own content type that marks a primary field.
    info = IPrimaryFieldInfo(source, None)
    if info is not None and info.value is not None:
        return read_source(info.value)

    raise AttachmentError([
        f"{describe(source)} is not a supported attachment source. Supported "
        f"sources are bytes, a filesystem path, an open binary file, a NamedFile/"
        f"NamedBlobFile value, or a Plone File/Image content object"
    ])


def guess_mimetype(filename):
    """``mimetypes.guess_type`` on the filename alone, or ``None``."""
    return mimetypes.guess_type(filename)[0]


def split_mimetype(mimetype, source, filename):
    """Split ``"application/pdf"`` into ``("application", "pdf")``.

    A mimetype without a slash cannot be split, and guessing which half was meant
    would put the wrong ``Content-Type`` on a real mail, so it is an error like any
    other missing metadata.
    """
    maintype, _, subtype = mimetype.partition("/")
    # A stray charset or boundary parameter is the caller's, not ours to keep: it
    # would end up duplicated once `add_attachment` writes its own.
    subtype = subtype.split(";")[0].strip()
    if not maintype or not subtype:
        raise AttachmentError([
            f"{describe(source)} (filename {filename!r}) has the unusable "
            f"mimetype {mimetype!r}; it needs the form 'maintype/subtype'"
        ])
    return maintype, subtype


def describe(source):
    """A short rendering of a source, for error messages."""
    if isinstance(source, (bytes, bytearray, memoryview)):
        return f"{len(source)} raw bytes"
    if isinstance(source, (str, os.PathLike)):
        return repr(str(source))
    filename = getattr(source, "filename", None)
    if filename:
        return f"{type(source).__name__} {filename!r}"
    return f"{type(source).__name__} instance"
