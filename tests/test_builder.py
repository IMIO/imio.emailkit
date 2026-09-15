"""The builder holds data and does not grow behaviour.

> The builder is a plain data holder; each method returns ``self``. **It holds
> data, it does not grow behavior** -- no conditionals, no scheduling, no
> retries.

This is restated elsewhere as a boundary rather than a style note:
"Methods, and nothing beyond them [...] A signature change is a decision-log
entry plus approval, never a quiet edit." "No new builder methods beyond the
frozen set" is listed among the non-goals.

A property nobody asserts is a property that erodes. So this module pins three
things a reviewer would otherwise have to notice by eye:

* the **closed set** of nine methods -- the tenth arrives as a red test, with
  a deliberate, recorded decision plus approval as the remedy rather than a
  quiet merge;
* **identity** on chaining, not merely truthiness -- returning a *new* builder
  would keep the chaining example working while silently discarding whatever the
  caller accumulated on a reference they kept;
* **no I/O before ``.send()``**, which is what makes an unsent builder harmless
  and ``render()`` callable exactly once per language group.
"""

import pytest
import support


Email = support.require_builder()
(TemplateNotFound,) = support.require_contract(
    "imio.emailkit.interfaces", "TemplateNotFound's docstring", "TemplateNotFound"
)


@pytest.fixture
def builder(mail):
    return mail()


class TestTheMethodSet:
    def test_every_spec_method_exists(self, builder):
        missing = [
            name for name in support.BUILDER_METHODS if not hasattr(builder, name)
        ]

        assert missing == [], f"builder methods missing from Email: {missing}"

    def test_every_spec_method_is_callable(self, builder):
        not_callable = [
            name
            for name in support.BUILDER_METHODS
            if not callable(getattr(builder, name))
        ]

        assert not_callable == [], f"not callable: {not_callable}"

    def test_there_are_no_methods_beyond_the_spec(self, builder):
        """The anti-drift assertion.

        "No new builder methods beyond the frozen set" is a
        non-goal, and the pressure is anticipated: "``.send()`` grows conditionals
        to handle a real case -- that is the boundary; report instead of
        absorbing it". A ``.schedule()``, a ``.retry()`` or a ``.when()`` is the
        visible form of that pressure, and it is much easier to decline before it
        has callers.

        Read off the *class* rather than the instance, so held data does not look
        like API. A genuinely needed tenth method requires a deliberate, recorded
        decision plus approval -- then this list, and only then.
        """
        public = {
            name
            for name in dir(type(builder))
            if not name.startswith("_") and callable(getattr(type(builder), name, None))
        }

        extra = sorted(public - set(support.BUILDER_METHODS))

        assert extra == [], (
            f"Email grew methods beyond the frozen set: {extra}. "
            "A signature change is a decision-log entry plus approval, "
            "never a quiet edit."
        )


class TestEveryMethodReturnsSelf:
    """ "Each method returns ``self``"."""

    @pytest.mark.parametrize("name", support.CHAINING_METHODS)
    def test_returns_the_same_object(self, builder, fr_member, name, tmp_path):
        arguments = {
            "to": ((support.PLAIN_ADDRESS,), {}),
            "cc": ((support.PLAIN_ADDRESS,), {}),
            "bcc": ((support.PLAIN_ADDRESS,), {}),
            "reply_to": ((support.REPLY_TO,), {}),
            "sender": ((support.OVERRIDE_SENDER,), {}),
            "subject": ((support.LITERAL_SUBJECT,), {}),
            "with_context": ((), {"extra": "value"}),
            "attach": ((b"%PDF-1.7\n",), {"filename": "a.pdf"}),
        }[name]
        args, kwargs = arguments

        result = getattr(builder, name)(*args, **kwargs)

        assert result is builder, (
            f".{name}() returned {result!r} rather than self. A new object here "
            "silently discards everything the caller accumulated on the old one."
        )

    def test_the_spec_example_chains(self, mail, fr_member, tmp_path):
        """The builder's own illustration, method for method, as one expression.

        A formatter once collapsed this exact chain; having it as executable
        code means the shape is pinned somewhere a formatter cannot quietly
        rewrite it.
        """
        pdf = tmp_path / "convocation.pdf"
        pdf.write_bytes(b"%PDF-1.7\n")

        email = (
            mail()
            .to(fr_member)
            .to(support.PLAIN_ADDRESS)
            .cc([support.OTHER_ADDRESS])
            .reply_to(support.REPLY_TO)
            .with_context(item="x", meeting="y")
            .attach(pdf, filename="convocation.pdf")
        )

        assert email is not None
        assert callable(email.send)


class TestHeldData:
    def test_with_context_accumulates(self, mail, deliver, sent, set_default_language):
        """The builder spells it ``with_context(**kw)`` and the example calls it once,
        but a builder assembled across a couple of helper functions calls it
        several times. A second call that replaced the first would drop context
        the template needs -- and the template's ``${}`` would then either raise
        or, on the fallback engine, ship verbatim."""
        set_default_language("fr")
        email = mail().to(support.PLAIN_ADDRESS)

        email.with_context(first="one").with_context(second="two")
        email.send()
        deliver()

        # Neither key is in the template, so the proof that both survived is
        # simply that assembly succeeded with both present -- the assertion that
        # matters is that the *fixture* context, set before these two calls, is
        # still there.
        html = support.html_of(support.sole(sent).message)
        assert support.load_fixture(support.NOTIFICATION)["title"] in html, (
            "a later with_context() dropped the context set earlier"
        )

    def test_two_builders_do_not_share_state(self, mail, deliver, sent):
        """Mutable default arguments and class-level containers are the classic
        way a "plain data holder" acquires memory. The symptom is a mail sent to
        the previous mail's recipients."""
        first = mail().to(support.PLAIN_ADDRESS)
        second = mail().to(support.OTHER_ADDRESS)

        second.send()
        deliver()

        addresses = support.envelope(support.sole(sent))

        assert addresses == [support.OTHER_ADDRESS], (
            f"the second builder inherited the first's recipients: {addresses}"
        )
        assert first is not second

    def test_sending_twice_sends_twice(self, mail, mailhost, deliver):
        """Not a documented feature, but the builder is a data holder, so
        ``.send()`` must be a *read* of that data. A ``.send()`` that consumed or
        cleared its recipients would raise the second time -- and the retry loop
        someone writes around it would silently do nothing."""
        email = mail().to(support.PLAIN_ADDRESS)

        email.send()
        email.send()
        deliver()

        assert len(mailhost.sent) == 2, (
            f"two .send() calls produced {len(mailhost.sent)} message(s)"
        )


class TestNoIoBeforeSend:
    """ "No method does I/O before
    ``.send()``"."""

    def test_an_unknown_template_never_sends_silently(
        self, mailhost, site_sender, deliver
    ):
        """``TemplateNotFound`` has to reach the caller, whether the builder
        checks the name eagerly or at ``.send()``.

        *When* it raises is deliberately not pinned -- either reading is
        defensible and no choice was made between them. What is pinned is that a typo in
        a template name cannot end with a mail going out, or with none going out
        and nobody told.
        """
        with pytest.raises(TemplateNotFound):
            (
                Email(support.qualified("no_such_template_at_all"))
                .to(support.PLAIN_ADDRESS)
                .send()
            )

        deliver()

        assert mailhost.sent == []

    def test_collecting_bad_data_does_not_raise(self, mail):
        """Every deferred failure in one builder, none of them raising until
        ``.send()``. This is what "errors surface together"
        requires of the collection phase."""
        (
            mail()
            .to(support.UNRESOLVABLE)
            .cc(object())
            .bcc(None)
            .attach(object())
            .attach(b"bytes with no filename")
        )

    def test_a_builder_that_is_never_sent_renders_nothing(
        self, mail, monkeypatch, fr_member, deliver
    ):
        """Rendering is the expensive part and, per the builder's contract, it
        happens "once per language group" -- inside ``.send()``.

        The counter goes on **every** already-imported name that is bound to the
        real function, rather than on one chosen module. ``from ... import
        render`` copies the reference, so patching only
        ``imio.emailkit.render.render`` misses a builder that imported it by
        name -- and the first assertion would then pass because nothing was being
        observed at all. (``imio.emailkit.__init__`` also rebinds ``render`` over
        the submodule, a trap ``test_discovery.py`` documents.)

        The trailing assertion is what makes this test able to fail: it proves
        the counter is wired into the path ``.send()`` actually takes.
        """
        import sys

        calls = []
        original = sys.modules["imio.emailkit.render"].render

        def counting(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        patched = []
        for name, module in list(sys.modules.items()):
            if name.startswith("imio.emailkit") and (
                getattr(module, "render", None) is original
            ):
                monkeypatch.setattr(module, "render", counting)
                patched.append(name)

        assert patched, "no imio.emailkit module exposes render() to patch"

        email = mail().to(fr_member).subject(support.LITERAL_SUBJECT)

        assert calls == [], (
            f"{len(calls)} render() call(s) before .send(); the builder holds "
            "data, it does not do work"
        )

        email.send()
        deliver()

        assert calls, (
            "the render() counter never fired, even on .send() -- so this test "
            "cannot observe rendering and its first assertion proved nothing. "
            f"Patched: {patched}. Either .send() does not go through "
            "imio.emailkit.render.render(), or it captured the function before "
            "these patches were installed."
        )
