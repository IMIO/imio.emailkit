Open `README.md` with a rendered mail. A package whose whole subject is what an
email looks like began with a title and eleven badges; the banner is a real render
of the notification template in the v3 design. The image is referenced by absolute
`raw.githubusercontent.com` URL, because the README is also the PyPI long
description and PyPI resolves no relative links, and it lives in `docs/` — which
`MANIFEST.in` does not graft, so it never reaches the sdist or the wheel.
