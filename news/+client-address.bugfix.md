Fix the empty origin IP in the password-reset mail. The template used
`request/HTTP_X_FORWARDED_FOR | request/REMOTE_ADDR`, copied from stock Plone,
which renders *empty* whenever no `X-Forwarded-For` header is present:
`HTTPRequest.get()` returns `''` for a missing `HTTP_` key instead of raising, and
a TAL `|` chain falls through only on a traversal exception, so the `REMOTE_ADDR`
fallback was unreachable. Both login-help mails now use `request/getClientAddr`.

Deployments behind a reverse proxy must declare it as `trusted-proxy` in
`zope.conf` for the real client address to appear; otherwise Zope correctly
reports the proxy's own address. See the README.
