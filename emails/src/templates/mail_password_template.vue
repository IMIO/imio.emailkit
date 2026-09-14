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
 *
 * ---------------------------------------------------------------------------
 * What the v2 layout changed here
 * ---------------------------------------------------------------------------
 * Nothing about the *wording*. The title moved out of the body into the banner
 * (a `#title` slot, because it is wording and only a slot can be translated),
 * the validity sentence moved from a trailing grey paragraph into a callout with
 * an overline, and the copy-this-link fallback moved into the shell's `mentions`
 * region. All three are the same sentences in the place the design puts them:
 * a deadline is a condition, and a condition is a callout.
 *
 * The pill is `info`, on the maintainer's call, and it used to be `warning`.
 * The argument for `warning` was that this is the one mail whose link stops
 * working, and the pill is the only part of the design a reader sees before
 * deciding whether to open the message now or later. The argument against it
 * won: this mail and `get_username` carry the SAME label, "Your account", and
 * two mails that say the same words while showing different colours and
 * different glyphs are telling the reader about a distinction that does not
 * exist. The deadline is stated where it belongs, in the callout below, which
 * is the one place that can give the actual date.
 *
 * v3's white pill sharpened the point. With the tone reduced to a coloured disc
 * under the glyph, the difference between the two "Your account" pills was a
 * yellow circle with an exclamation mark against a blue one with an `i` -- and
 * an exclamation mark on a password mail reads as "something is wrong with your
 * account", which is the one thing this mail must not imply.
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
        One paragraph with a break, and the address as a real link, which is
        what the mockups draw. It used to be two paragraphs with the url as
        plain grey text: a client that autolinked it styled it its own way
        (blue, usually) and one that did not left the reader retyping a
        sixty-character url by hand. `data-dark="accent"` moves it to
        #ffadd9 in a dark client, where #b3004b is around 2:1.
      -->
      <p class="m-0 text-[13px] leading-[21px] text-imio-grey-dark">
        <span i18n:translate="email_mail_password_fallback" tal:omit-tag="">If the button does not work, copy this address into your browser:</span>
        <br>
        <a href="${reset_url}" class="break-all text-imio-magenta-dark underline" data-dark="accent">${reset_url}</a>
      </p>
    </template>
  </KitMain>
</template>
