<script setup>
/**
 * Plone's "an account has been created for you" mail, restyled (SPEC §8.1).
 *
 * An ordinary template in the ordinary dialect; see the note in
 * `mail_password_template.vue` for what changed and why.
 * `imio.emailkit.browser.default_mails.RegisteredNotifyView` owns the stock view
 * and builds the context below.
 *
 * Context keys: `fullname`, `username`, `email`, `password_url`, `expires`,
 * `email_from_name`.
 *
 * `expires` is a real datetime and is formatted here through the kit's
 * `format_datetime` helper, which `render()` binds to the *recipient's* language.
 * Stock used `context.toLocalizedTime`, which follows the request instead.
 *
 * ---------------------------------------------------------------------------
 * What the v2 layout changed here
 * ---------------------------------------------------------------------------
 * The account details left the greeting paragraph and became the rail card,
 * which is the design's block for "the thing this message is about". An account
 * is a thing, and its three fields -- the username to type at the login form, the
 * name it was opened under, the address everything will be sent to -- are what
 * the reader checks and keeps. They are labelled rows in the card's metadata list
 * rather than clauses in a sentence they will have closed by then.
 *
 * The sign-off went. `email_from_name` already names the sender in the banner
 * subtitle and again in the footer, and a third repetition as "Kind regards,
 * <name>" was the pre-v2 layout's way of closing a mail that had no footer.
 *
 * The deadline was already a panel and stays one, now with the overline the
 * design gives every callout, and the copy-this-link fallback moved to the
 * shell's `mentions` region.
 *
 * The pill is `success`. This is the one mail in the package that reports
 * something good having happened rather than something the reader has to do.
 *
 * ---------------------------------------------------------------------------
 * Nothing here is "activated", because Plone activates nothing
 * ---------------------------------------------------------------------------
 * This mail used to say "Activate my account", under an "Activation deadline",
 * pointing at an `activation_url`. All three were wrong about what happens.
 *
 * `RegistrationTool.registeredNotify` runs AFTER the account exists, and the
 * account is usable from that moment: `RegisteredNotifyView.build_context` calls
 * `portal_password_reset.requestReset()` and builds an ordinary password-reset
 * url. There is no pending state, no activation step, and nothing the recipient
 * can fail to do that would leave the account unusable. What expires is the
 * LINK, exactly as in `mail_password_template`, which is why that mail's
 * `email_callout_link_validity` msgid is reused here rather than a second one
 * saying the same thing about a different imaginary thing.
 *
 * A reader told to "activate" looks for a state change and, when the link has
 * expired, reasonably concludes the account is dead. It is not: they use
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
        No `#title`: the three fields below are the account, and the design's card
        title would only be the fullname a second time. The overline still says
        what the block is.
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
        One paragraph with a break, and the address as a real link, which is
        what the mockups draw. It used to be two paragraphs with the url as
        plain grey text: a client that autolinked it styled it its own way
        (blue, usually) and one that did not left the reader retyping a
        sixty-character url by hand. `data-dark="accent"` moves it to
        #ffadd9 in a dark client, where #b3004b is around 2:1.
      -->
      <p class="m-0 text-[13px] leading-[21px] text-imio-grey-dark">
        <span i18n:translate="email_registered_notify_fallback" tal:omit-tag="">If the button does not work, copy this address into your browser:</span>
        <br>
        <a href="${password_url}" class="break-all text-imio-magenta-dark underline" data-dark="accent">${password_url}</a>
      </p>
    </template>
  </KitMain>
</template>
