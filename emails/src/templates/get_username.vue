<script setup>
/**
 * The username-reminder mail sent by the login-help form's "Get your
 * username" button.
 *
 * Stock Plone has no template for this mail: `SEND_USERNAME_TEMPLATE` is a
 * plain i18n string sent straight through `MailHost`, with no file for
 * `z3c.jbot` to key on. `imio.emailkit` overrides the view instead
 * (`browser/login_help.py`), and the mail goes out through the `Email`
 * builder like any other, discovered and golden-tested.
 *
 * Context it expects (see `tests/fixtures/get_username.py`):
 *   fullname     the recipient's full name
 *   login        the username being reminded; the entire payload of this
 *                mail
 *   site_name    navigation root title
 *   login_url    where the button goes
 *   client_addr  request origin, from `request.getClientAddr()`
 *
 * The title is a `#title` slot rather than a context name, because it is
 * wording, not data, and only a slot can carry `i18n:translate`. The
 * subtitle is `${site_name}`, which is data, so it goes in the slot as a
 * plain placeholder.
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
      The username sits in the rail card, not inline in the lead sentence:
      the reader has to find it while skimming, then retype it. The rail
      card is the block for "here is the thing this message is about".
    -->
    <KitCard>
      <!--
        The overline names the field, not "Your username" again: the
        banner above already says that. The plaintext twin has no banner,
        so it keeps `email_get_username_label` there.
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
      Mirrors `mail_password_template.vue`'s closing notice. The IP is
      `client_addr`, computed by the view with `request.getClientAddr()`.
      Stock Plone's `request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR`
      renders EMPTY when no `X-Forwarded-For` header is present, because
      `HTTPRequest.get()` returns `''` for a missing key instead of
      raising, and TAL's `|` only falls through on an error.
      `TestClientAddressSemantics` pins this.
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
