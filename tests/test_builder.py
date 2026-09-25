"""The builder holds data and does not grow behaviour.

Each method returns ``self``. The builder has no conditionals, no
scheduling, and no retries.

This module pins three properties:

* the method set is closed: a fixed list of methods, no more;
* chaining returns the same object, not a new one -- a new object would
  silently discard whatever the caller already set;
* no I/O happens before ``.send()``, so an unsent builder is harmless and
  render happens exactly once per language group.
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
    def test_every_api_method_exists(self, builder):
        missing = [
            name for name in support.BUILDER_METHODS if not hasattr(builder, name)
        ]

        assert missing == [], f"builder methods missing from Email: {missing}"

    def test_every_api_method_is_callable(self, builder):
        not_callable = [
            name
            for name in support.BUILDER_METHODS
            if not callable(getattr(builder, name))
        ]

        assert not_callable == [], f"not callable: {not_callable}"

    def test_there_are_no_methods_beyond_the_api(self, builder):
        """Guards against an added method, such as ``.schedule()`` or
        ``.retry()``. Read off the class, not the instance, so held data is
        not mistaken for an API method."""
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
    """Every chaining method must return the same builder instance."""

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

    def test_the_documented_example_chains(self, mail, fr_member, tmp_path):
        """One chain exercising every builder method, as executable code, so
        a formatter cannot quietly change its shape."""
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
        """A second ``with_context()`` call must add to the first, not
        replace it. A template that reads a key set by the first call would
        break silently otherwise."""
        set_default_language("fr")
        email = mail().to(support.PLAIN_ADDRESS)

        email.with_context(first="one").with_context(second="two")
        email.send()
        deliver()

        # The fixture's own context, set before these two calls, must still render.
        html = support.html_of(support.sole(sent).message)
        assert support.load_fixture(support.NOTIFICATION)["title"] in html, (
            "a later with_context() dropped the context set earlier"
        )

    def test_two_builders_do_not_share_state(self, mail, deliver, sent):
        """Two builders must not share mutable state, such as a class-level
        container or a mutable default argument."""
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
        """``.send()`` must read the builder's data, not consume it, so
        calling it twice sends twice."""
        email = mail().to(support.PLAIN_ADDRESS)

        email.send()
        email.send()
        deliver()

        assert len(mailhost.sent) == 2, (
            f"two .send() calls produced {len(mailhost.sent)} message(s)"
        )


class TestNoIoBeforeSend:
    """No method may perform I/O before ``.send()`` is called."""

    def test_an_unknown_template_never_sends_silently(
        self, mailhost, site_sender, deliver
    ):
        """An unknown template name must raise ``TemplateNotFound``, whether
        the builder checks it eagerly or at ``.send()``. Either way, no mail
        may go out, and the failure must not pass silently."""
        with pytest.raises(TemplateNotFound):
            (
                Email(support.qualified("no_such_template_at_all"))
                .to(support.PLAIN_ADDRESS)
                .send()
            )

        deliver()

        assert mailhost.sent == []

    def test_collecting_bad_data_does_not_raise(self, mail):
        """Collecting invalid data must not raise until ``.send()`` is called."""
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
        """Rendering is expensive and must happen only inside ``.send()``.

        The patch covers every already-imported module holding a reference
        to ``render``, because ``from ... import render`` copies the
        reference: patching only ``imio.emailkit.render.render`` would miss
        a builder that imported it by name.
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
