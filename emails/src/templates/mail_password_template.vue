<script setup>
/**
 * Plone's password-reset mail, restyled (SPEC §8.1).
 *
 * An ordinary template in the ordinary dialect. It used to be a `z3c.jbot`
 * override rendered by a stock Plone view, which forced `options/member`,
 * `python:member.getProperty(…)`, a hand-written header block and no locale
 * helpers. `imio.emailkit.browser.default_mails.MailPasswordView` now owns that
 * view, builds a flat context and renders through `render()`, so nothing here is
 * special any more: no `useDoctype`, no `useOutputPath`, no `#preheader` slot.
 * The subject and the preheader are msgids in this package's
 * `<emailkit:templates>` registration, like every other template.
 *
 * Context keys, all of them from `MailPasswordView.build_context`:
 * `userid`, `site_name`, `is_anonymous`, `reset_url`, `expiration_hours`,
 * `client_addr`.
 */
</script>

<template>
  <KitMain>
    <p
      tal:condition="not:is_anonymous"
      i18n:translate="email_mail_password_admin_request"
      class="m-0 mb-4 text-sm leading-6 text-imio-black"
    >
      The site administrator has asked you to reset the password of the account
      <span i18n:name="userid" tal:omit-tag="" tal:content="userid">userid</span>.
      Your previous password no longer works.
    </p>

    <p i18n:translate="email_mail_password_lead" class="m-0 mb-4 text-sm leading-6 text-imio-black">
      Use the button below to choose a new password for
      <span i18n:name="site_name" tal:omit-tag="" tal:content="site_name">the site</span>.
    </p>

    <KitButton href="${reset_url}" align="center">
      <span i18n:translate="email_mail_password_cta" tal:omit-tag="">Choose a new password</span>
    </KitButton>

    <p i18n:translate="email_mail_password_fallback" class="m-0 mb-1 text-xs leading-5 text-imio-grey-dark">
      If the button does not work, copy this address into your browser:
    </p>
    <p class="m-0 mb-4 break-all text-xs leading-5 text-imio-grey-dark">${reset_url}</p>

    <p i18n:translate="email_mail_password_expiry" class="m-0 text-xs leading-5 text-imio-grey-dark">
      This link is valid for
      <span i18n:name="hours" tal:omit-tag="" tal:content="expiration_hours">24</span> hours.
    </p>

    <div tal:condition="is_anonymous">
      <KitPanel>
        <p i18n:translate="email_mail_password_tracking" class="m-0 text-sm leading-6 text-imio-black">
          If you did not ask for this, simply ignore this message: your password has not
          been changed. The request came from the IP address
          <span i18n:name="ipaddress" tal:omit-tag="" tal:content="client_addr">0.0.0.0</span>.
        </p>
      </KitPanel>
    </div>
  </KitMain>
</template>
