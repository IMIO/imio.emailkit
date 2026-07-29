Test suite for Phase 2's API, written from SPEC §6.2/§6.3: recipient resolution (string,
member, userid, mixed and nested iterables, duplicates, `RecipientError`), every
attachment source and its filename/mimetype inference, per-language sending (one message
per group, each with its own subject translation and its own rendered body), the subject
default and both override forms, the `multipart/alternative` shape, and §7's named
transaction-abort test. `imio.emailkit.testing` now ships
`install_recording_mailhost()`, a MailHost double that replaces `_makeMailer` rather than
`_send` so a queued delivery can be told apart from an immediate one — which is what
makes "abort → queue empty" a real assertion instead of a constant.
