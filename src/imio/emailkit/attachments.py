"""Attachment sources: resolve one of several input kinds to bytes.

``.attach()`` accepts raw bytes, a filesystem path, an open binary file, a
``NamedFile``/``NamedBlobFile`` value, or a Plone File/Image content object.
Failures are collected and raised once, as
:class:`~imio.emailkit.interfaces.AttachmentError`.
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
    """Resolve every ``(source, filename, mimetype)`` spec into an :class:`Attachment`.

    :param specs: the 3-tuples ``.attach()`` recorded, in order
    :returns: list of :class:`Attachment`, in the same order
    :raises AttachmentError: lists every spec that could not be resolved
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

    Precedence for ``filename``/``mimetype``: the caller's argument, then
    the source, then a guessed mimetype. Both are required for raw ``bytes``.
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

    ``filename``/``mimetype`` are ``None`` when the source lacks them.

    Check order: ``bytes`` first (carries neither); ``INamed`` before path
    (a blob is not a path); path before file-object (``str``/``Path`` have
    no ``read``); ``IPrimaryFieldInfo`` last (a slower component lookup).
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source), None, None

    if INamed.providedBy(source):
        # All Named* types expose these three; `contentType` may be empty.
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
        # `name` is a path, an int (file descriptor), or absent (BytesIO).
        name = getattr(source, "name", None)
        filename = Path(name).name if isinstance(name, (str, os.PathLike)) else None
        return data, filename, None

    # A Plone File/Image object; IPrimaryFieldInfo finds the payload field.
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

    Raises when there is no slash: guessing the missing half risks the
    wrong ``Content-Type``.
    """
    maintype, _, subtype = mimetype.partition("/")
    # Drop a charset or boundary parameter: add_attachment writes its own.
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
