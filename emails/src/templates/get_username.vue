<script setup>
/**
 * The username-reminder mail sent by the login-help form's *"Get your username"*
 * button.
 *
 * ---------------------------------------------------------------------------
 * This is a NORMAL template, and that is the interesting part
 * ---------------------------------------------------------------------------
 * `mail_password.vue` and `registered_notify.vue` are the two documented
 * exceptions to the authoring rules, because a *stock Plone view* renders them.
 * This one is not an exception, even though it restyles a stock Plone mail —
 * because stock Plone has no template for it to override.
 *
 * Plone's version is `SEND_USERNAME_TEMPLATE`, a module-level i18n string at
 * `Products/CMFPlone/browser/login/login_help.py:33`, declared `text/plain`,
 * interpolated with `str.format()` and handed straight to `MailHost` by
 * `RequestUsername.send_username()`. There is no file, so there is nothing for
 * `z3c.jbot` to key on. `imio.emailkit` therefore overrides the *view* instead
 * (`browser/login_help.py`), and the mail goes out through the `Email` builder
 * builder like any other.
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
 */
</script>

<template>
  <KitMain>
    <p i18n:translate="email_get_username_greeting" class="m-0 mb-4 text-sm leading-6 text-imio-black">
      Dear <span i18n:name="fullname" tal:omit-tag="" tal:content="fullname">Name</span>,
    </p>

    <p i18n:translate="email_get_username_lead" class="m-0 mb-4 text-sm leading-6 text-imio-black">
      You asked to be reminded of your username for
      <span i18n:name="site_name" tal:omit-tag="" tal:content="site_name">the site</span>.
    </p>

    <!--
      The username in a panel rather than inline in the lead sentence. This mail
      has exactly one payload and the recipient has to be able to find it while
      skimming, then retype it. `accent` is the kit's "must not miss" tone and
      this is the one place in the mail that earns it.
    -->
    <KitPanel tone="accent">
      <p i18n:translate="email_get_username_label" class="m-0 mb-1 text-xs uppercase leading-5 text-imio-grey-dark">
        Your username
      </p>
      <p class="m-0 font-display text-lg font-bold leading-7 text-imio-black">${login}</p>
    </KitPanel>

    <KitButton href="${login_url}" align="center">
      <span i18n:translate="email_get_username_cta" tal:omit-tag="">Log in</span>
    </KitButton>

    <!--
      Mirrors `mail_password.vue`'s closing notice so the two login-help mails
      read as siblings. The IP is `client_addr`, computed by the view with
      `request.getClientAddr()`; stock Plone's
      `request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR` renders EMPTY whenever
      no `X-Forwarded-For` header is present, because `HTTPRequest.get()` returns
      `''` for a missing `HTTP_` key instead of raising and TAL's `|` only falls
      through on an error. `TestClientAddressSemantics` in the test suite pins this.
    -->
    <KitPanel>
      <p i18n:translate="email_get_username_tracking" class="m-0 text-sm leading-6 text-imio-black">
        If you did not ask for this, simply ignore this message. The request came from the IP address
        <span i18n:name="ipaddress" tal:omit-tag="" tal:content="client_addr">0.0.0.0</span>.
      </p>
    </KitPanel>
  </KitMain>
</template>
