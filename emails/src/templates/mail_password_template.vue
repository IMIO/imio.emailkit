<script setup>
/**
 * Plone's password-reset mail, restyled.
 *
 * An ordinary template in the ordinary dialect.
 * `imio.emailkit.browser.default_mails.MailPasswordView` owns the view,
 * builds a flat context and renders through `render()`: no `useDoctype`,
 * no `useOutputPath`, no `#preheader` slot. The subject and the preheader
 * are msgids in this package's `<emailkit:templates>` registration, like
 * every other template.
 *
 * Context keys, all from `MailPasswordView.build_context`: `userid`,
 * `site_name`, `is_anonymous`, `reset_url`, `expiration_hours`,
 * `client_addr`.
 *
 * The title lives in the banner (a `#title` slot, since only a slot can
 * be translated). The validity sentence is a callout with an overline.
 * The copy-this-link fallback lives in the shell's `mentions` region.
 *
 * The pill is `info`. This mail and `get_username` share the same label,
 * "Your account", and a different colour here would tell the reader about
 * a distinction that does not exist. An exclamation mark on a password
 * mail also reads as "something is wrong with your account", which this
 * mail must not imply. The deadline is stated in the callout below, which
 * is the one place that gives the actual date.
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
      <span i18n:translate="email_mail_password_title" tal:omit-tag="">Reset your password</span>
    </template>
    <template #subtitle>${site_name}</template>

    <p
      tal:condition="not:is_anonymous"
      i18n:translate="email_mail_password_admin_request"
      class="m-0 mb-4 text-[15px] leading-6 text-imio-black"
    >
      The site administrator has asked you to reset the password of the account
      <span i18n:name="userid" tal:omit-tag="" tal:content="userid">userid</span>.
      Your previous password no longer works.
    </p>

    <p i18n:translate="email_mail_password_lead" class="m-0 text-[15px] leading-6 text-imio-grey-dark">
      Use the button below to choose a new password for
      <span i18n:name="site_name" tal:omit-tag="" tal:content="site_name">the site</span>.
    </p>

    <KitPanel>
      <template #overline>
        <span i18n:translate="email_callout_link_validity" tal:omit-tag="">Link validity</span>
      </template>
      <p i18n:translate="email_mail_password_expiry" class="m-0 text-sm leading-[22px] text-imio-black">
        This link is valid for
        <span i18n:name="hours" tal:omit-tag="" tal:content="expiration_hours">24</span> hours.
      </p>
    </KitPanel>

    <KitButton href="${reset_url}" align="center">
      <span i18n:translate="email_mail_password_cta" tal:omit-tag="">Choose a new password</span>
    </KitButton>

    <!--
      Only for the anonymous case: someone who asked for this themselves. When an
      administrator triggered the reset, "you can ignore this" is wrong advice,
      because the previous password has already stopped working.
    -->
    <div tal:condition="is_anonymous">
      <KitPanel tone="neutral">
        <template #overline>
          <span i18n:translate="email_callout_not_you" tal:omit-tag="">Not you?</span>
        </template>
        <p i18n:translate="email_mail_password_tracking" class="m-0 text-sm leading-[22px] text-imio-black">
          If you did not ask for this, simply ignore this message: your password has not
          been changed. The request came from the IP address
          <span i18n:name="ipaddress" tal:omit-tag="" tal:content="client_addr">0.0.0.0</span>.
        </p>
      </KitPanel>
    </div>

    <template #mentions>
      <!--
        One paragraph with a break, and the address as a real link. A
        client that autolinks a plain-text url styles it on its own; one
        that does not leaves the reader retyping a long url by hand.
        `data-dark="accent"` moves it to #ffadd9 in a dark client, where
        #b3004b is about 2:1 contrast.
      -->
      <p class="m-0 text-[13px] leading-[21px] text-imio-grey-dark">
        <span i18n:translate="email_mail_password_fallback" tal:omit-tag="">If the button does not work, copy this address into your browser:</span>
        <br>
        <a href="${reset_url}" class="break-all text-imio-magenta-dark underline" data-dark="accent">${reset_url}</a>
      </p>
    </template>
  </KitMain>
</template>
