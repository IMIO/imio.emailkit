<script setup>
/**
 * Plone's "an account has been created for you" mail, restyled (SPEC §8.1).
 *
 * An ordinary template in the ordinary dialect; see the note in
 * `mail_password_template.vue` for what changed and why.
 * `imio.emailkit.browser.default_mails.RegisteredNotifyView` owns the stock view
 * and builds the context below.
 *
 * Context keys: `fullname`, `username`, `activation_url`, `expires`,
 * `email_from_name`.
 *
 * `expires` is a real datetime and is formatted here through the kit's
 * `format_datetime` helper, which `render()` binds to the *recipient's* language.
 * Stock used `context.toLocalizedTime`, which follows the request instead.
 */
</script>

<template>
  <KitMain>
    <p i18n:translate="email_registered_notify_greeting" class="m-0 mb-4 text-sm leading-6 text-imio-black">
      Hello <span i18n:name="fullname" tal:omit-tag="" tal:content="fullname">Fullname</span>,
    </p>

    <p i18n:translate="email_registered_notify_created" class="m-0 mb-4 text-sm leading-6 text-imio-black">
      Your account has been created. Your username is
      <span i18n:name="username" tal:omit-tag="" tal:content="username">username</span>.
      Activate it by choosing a password.
    </p>

    <KitButton href="${activation_url}" align="center">
      <span i18n:translate="email_registered_notify_cta" tal:omit-tag="">Activate my account</span>
    </KitButton>

    <p i18n:translate="email_registered_notify_fallback" class="m-0 mb-1 text-xs leading-5 text-imio-grey-dark">
      If the button does not work, copy this address into your browser:
    </p>
    <p class="m-0 mb-4 break-all text-xs leading-5 text-imio-grey-dark">${activation_url}</p>

    <KitPanel>
      <p i18n:translate="email_registered_notify_expiry" class="m-0 text-sm leading-6 text-imio-black">
        Activate your account before
        <span
          i18n:name="expiration_date"
          tal:omit-tag=""
          tal:content="python: format_datetime(expires)"
        >date</span>.
      </p>
    </KitPanel>

    <p i18n:translate="email_regards" class="m-0 mt-4 text-sm leading-6 text-imio-black">
      Kind regards,
    </p>
    <p class="m-0 text-sm leading-6 text-imio-black">${email_from_name}</p>
  </KitMain>
</template>
