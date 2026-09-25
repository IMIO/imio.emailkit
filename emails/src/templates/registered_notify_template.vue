<script setup>
/**
 * Plone's "an account has been created for you" mail, restyled.
 *
 * An ordinary template in the ordinary dialect; see the note in
 * `mail_password_template.vue`.
 * `imio.emailkit.browser.default_mails.RegisteredNotifyView` owns the
 * stock view and builds the context below.
 *
 * Context keys: `fullname`, `username`, `email`, `password_url`,
 * `expires`, `email_from_name`.
 *
 * `expires` is a real datetime, formatted here through the kit's
 * `format_datetime` helper, which `render()` binds to the recipient's
 * language. Stock Plone uses `context.toLocalizedTime`, which follows the
 * request instead.
 *
 * The account details are the rail card, the design's block for "the
 * thing this message is about". The username, full name and email address
 * are labelled rows in the card's metadata list.
 *
 * The pill is `success`: this is the one mail in the package reporting
 * something good having happened, rather than something the reader has
 * to do.
 *
 * Nothing here is "activated", because Plone activates nothing
 * -----------------------------------------------------------------
 * `RegistrationTool.registeredNotify` runs after the account exists, and
 * the account is usable from that moment: `RegisteredNotifyView.build_context`
 * calls `portal_password_reset.requestReset()` and builds an ordinary
 * password-reset url. There is no pending state and no activation step.
 * What expires is the LINK, exactly as in `mail_password_template`, which
 * is why that mail's `email_callout_link_validity` msgid is reused here.
 *
 * A reader told to "activate" looks for a state change and, when the link
 * has expired, may conclude the account is dead. It is not: they use
 * "forgotten password" and carry on.
 */
</script>

<template>
  <KitMain>
    <template #pill>
      <KitPill tone="success">
        <span i18n:translate="email_pill_new_account" tal:omit-tag="">New account</span>
      </KitPill>
    </template>

    <template #title>
      <span i18n:translate="email_registered_notify_title" tal:omit-tag="">Welcome</span>
    </template>
    <template #subtitle>${email_from_name}</template>

    <p i18n:translate="email_registered_notify_greeting" class="m-0 mb-4 text-[15px] leading-6 text-imio-black">
      Hello <span i18n:name="fullname" tal:omit-tag="" tal:content="fullname">Fullname</span>,
    </p>

    <p i18n:translate="email_registered_notify_created" class="m-0 text-[15px] leading-6 text-imio-grey-dark">
      Your account has been created. Choose a password to start using it.
    </p>

    <KitCard>
      <template #overline>
        <span i18n:translate="email_card_your_account" tal:omit-tag="">Your account</span>
      </template>
      <!--
        No `#title`: the three fields below are the account, and a card
        title would only repeat the full name. The overline says what the
        block is.
      -->
      <KitDataList>
        <KitDataRow>
          <template #label>
            <span i18n:translate="email_field_username" tal:omit-tag="">Username</span>
          </template>
          ${username}
        </KitDataRow>
        <KitDataRow>
          <template #label>
            <span i18n:translate="email_field_fullname" tal:omit-tag="">Full name</span>
          </template>
          ${fullname}
        </KitDataRow>
        <KitDataRow>
          <template #label>
            <span i18n:translate="email_field_email" tal:omit-tag="">Email address</span>
          </template>
          ${email}
        </KitDataRow>
      </KitDataList>
    </KitCard>

    <KitPanel>
      <template #overline>
        <span i18n:translate="email_callout_link_validity" tal:omit-tag="">Link validity</span>
      </template>
      <p i18n:translate="email_registered_notify_expiry" class="m-0 text-sm leading-[22px] text-imio-black">
        This link is valid until
        <span
          i18n:name="expiration_date"
          tal:omit-tag=""
          tal:content="python: format_datetime(expires)"
        >date</span>.
      </p>
    </KitPanel>

    <KitButton href="${password_url}" align="center">
      <span i18n:translate="email_registered_notify_cta" tal:omit-tag="">Choose my password</span>
    </KitButton>

    <template #mentions>
      <!--
        One paragraph with a break, and the address as a real link. A
        client that autolinks a plain-text url styles it on its own; one
        that does not leaves the reader retyping a long url by hand.
        `data-dark="accent"` moves it to #ffadd9 in a dark client, where
        #b3004b is about 2:1 contrast.
      -->
      <p class="m-0 text-[13px] leading-[21px] text-imio-grey-dark">
        <span i18n:translate="email_registered_notify_fallback" tal:omit-tag="">If the button does not work, copy this address into your browser:</span>
        <br>
        <a href="${password_url}" class="break-all text-imio-magenta-dark underline" data-dark="accent">${password_url}</a>
      </p>
    </template>
  </KitMain>
</template>
