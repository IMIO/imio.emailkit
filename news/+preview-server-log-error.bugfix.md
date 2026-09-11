Stop `bin/preview-emails` from printing a traceback whenever the browser asks for
a file that is not there.

`PreviewHandler.log_message` filtered the live-reload poll out of the access log
by testing `VERSION_PATH not in args[0]`. For an access log `args[0]` is the
request line, but `BaseHTTPRequestHandler.log_error` routes through the same
method and passes an `HTTPStatus`, so the membership test raised
`TypeError: argument of type 'HTTPStatus' is not iterable` inside the handler
thread. Every 404 therefore printed a long traceback about the logging code
rather than a one-line "file not found".

The commonest trigger was `/favicon.ico`, which every browser requests on every
page load; that one is now answered with a 204 rather than left to 404, since the
preview directory holds rendered mails and nothing else.
