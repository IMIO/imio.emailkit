<script setup>
/**
 * The username-reminder mail sent by the login-help form's *"Get your username"*
 * button.
 *
 * ---------------------------------------------------------------------------
 * This is a NORMAL template, and that is the interesting part
 * ---------------------------------------------------------------------------
 * `mail_password_template.vue` and `registered_notify_template.vue` restyle two
 * stock Plone mails that stock Plone *has* templates for. This one restyles a
 * stock Plone mail that has none.
 *
 * Plone's version is `SEND_USERNAME_TEMPLATE`, a module-level i18n string at
 * `Products/CMFPlone/browser/login/login_help.py:33`, declared `text/plain`,
 * interpolated with `str.format()` and handed straight to `MailHost` by
 * `RequestUsername.send_username()`. There is no file, so there is nothing for
 * `z3c.jbot` to key on. `imio.emailkit` therefore overrides the *view* instead
 * (`browser/login_help.py`), and the mail goes out through the `Email` builder
 * like any other.
 *
 * Which means this file gets the better deal, not the worse one:
 *
 *   - flat context from `render()` — `${login}`, no `options/`, no `python:`
 *   - no `useDoctype()` header block: `Email` owns the headers, and the subject
 *     is an ordinary registration msgid rather than a `Subject:` line smuggled
 *     through the document
 *   - no `useOutputPath()`: `output.path` is already right, because this is a
 *     discovered template and not a jbot override
 *   - discovered, so it is golden-tested, previewable through
 *     `@@emailkit-preview` and reachable from `make preview-emails`
 *
 * Context it expects (see `tests/fixtures/get_username.py`):
 *   fullname     -- the recipient's full name
 *   login        -- the username being reminded; the entire payload of this mail
 *   site_name    -- navigation root title
 *   login_url    -- where the button goes
 *   client_addr  -- request origin, from `request.getClientAddr()`
 *
 * The title is a `#title` slot rather than a context name, because it is wording
 * and not data: a slot is the only shape that can carry `i18n:translate`. The
 * subtitle is `${site_name}`, which is data, so it goes in the slot as a plain
 * placeholder — the v2 banner's second line exists to say *which site* is
 * writing to you, and this mail knows.
 */
</script>

<template>
  <KitMain>
    <template #pill>
      <KitPill tone="info">
        <span i18n:translate="email_pill_your_account" tal:omit-tag="">Your account</span>
      </KitPill>
    </template>

    <template #title>
      <span i18n:translate="email_get_username_title" tal:omit-tag="">Your username</span>
    </template>
    <template #subtitle>${site_name}</template>

    <p i18n:translate="email_get_username_greeting" class="m-0 mb-4 text-[15px] leading-6 text-imio-black">
      Dear <span i18n:name="fullname" tal:omit-tag="" tal:content="fullname">Name</span>,
    </p>

    <p i18n:translate="email_get_username_lead" class="m-0 text-[15px] leading-6 text-imio-grey-dark">
      You asked to be reminded of your username for
      <span i18n:name="site_name" tal:omit-tag="" tal:content="site_name">the site</span>.
    </p>

    <!--
      The username in the rail card, not inline in the lead sentence. This mail
      has exactly one payload and the recipient has to be able to find it while
      skimming, then retype it. The rail card is the v2 design's "here is the
      thing this message is about" block, and a username is as literally that as
      it gets.
    -->
    <KitCard>
      <!--
        The overline is the field name, not "Your username" again: the banner
        two blocks up already says that, and a card whose overline repeats the
        title it sits under wastes the one line the reader uses to work out what
        they are looking at. The plaintext twin has no banner, so it keeps
        `email_get_username_label` there.
      -->
      <template #overline>
        <span i18n:translate="email_field_username" tal:omit-tag="">Username</span>
      </template>
      <template #title>${login}</template>
    </KitCard>

    <KitButton href="${login_url}" align="center">
      <span i18n:translate="email_get_username_cta" tal:omit-tag="">Log in</span>
    </KitButton>

    <!--
      Mirrors `mail_password_template.vue`'s closing notice so the two login-help
      mails read as siblings. The IP is `client_addr`, computed by the view with
      `request.getClientAddr()`; stock Plone's
      `request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR` renders EMPTY whenever
      no `X-Forwarded-For` header is present, because `HTTPRequest.get()` returns
      `''` for a missing `HTTP_` key instead of raising and TAL's `|` only falls
      through on an error. `TestClientAddressSemantics` in the test suite pins this.
    -->
    <KitPanel>
      <template #overline>
        <span i18n:translate="email_callout_not_you" tal:omit-tag="">Not you?</span>
      </template>
      <p i18n:translate="email_get_username_tracking" class="m-0 text-sm leading-[22px] text-imio-black">
        If you did not ask for this, simply ignore this message. The request came from the IP address
        <span i18n:name="ipaddress" tal:omit-tag="" tal:content="client_addr">0.0.0.0</span>.
      </p>
    </KitPanel>
  </KitMain>
</template>
