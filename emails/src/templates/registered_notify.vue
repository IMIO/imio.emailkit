<script setup>
/**
 * Plone's "your account has been created" mail, restyled (SPEC §8.1). Shipped as
 * a `z3c.jbot` override of
 * `Products.CMFPlone.browser.login.templates.registered_notify_template`.
 *
 * The second and last of the two documented exceptions to §3's authoring rules
 * -- see the long note in `mail_password.vue`; the same constraints apply here.
 * The stock view (`RegistrationTool.registeredNotify`) is called with `member`,
 * `reset`, `email` and `charset`.
 *
 * `reset` keeps the stock template's fallback: `registeredNotify` does pass it,
 * but other callers of the same view do not, and requesting one here costs
 * nothing when it is already there.
 */
const config = useConfig()

useOutputPath(
  `${config.emailkit.overridesPath}/Products.CMFPlone.browser.login.templates.registered_notify_template.pt`
)

useDoctype(`From: <span tal:replace="structure view/encoded_mail_sender" />
To: <span tal:replace="python:options['member'].getProperty('email')" />
Subject: <span i18n:domain="imio.emailkit" i18n:translate="email_subject_registered_notify_template" tal:omit-tag="">An account has been created for you</span>
Content-Type: text/html; charset=utf-8
Precedence: bulk

<!DOCTYPE html>`)
</script>

<template>
  <KitMain>
    <!-- Build-time preheader; see the note in `mail_password.vue`. -->
    <template #preheader>
      <span i18n:translate="email_preheader_registered_notify_template" tal:omit-tag="">Follow the link to activate your account.</span>
    </template>

    <div
      tal:omit-tag=""
      tal:define="member python:options['member'];
                  reset python:options.get('reset', None) or context.portal_password_reset.requestReset(member.getId());
                  fullname python:member.getProperty('fullname');
                  username python:member.getUserName();
                  activation_url python:view.construct_url(reset['randomstring']) + '?userid=' + member.getUserName();
                  expiration_date python:context.toLocalizedTime(reset['expires'], long_format=1);
                  email_from_name python:context.portal_registry['plone.email_from_name']"
    >
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
          <span i18n:name="expiration_date" tal:omit-tag="" tal:content="expiration_date">date</span>.
        </p>
      </KitPanel>

      <p i18n:translate="email_regards" class="m-0 mt-4 text-sm leading-6 text-imio-black">
        Kind regards,
      </p>
      <p class="m-0 text-sm leading-6 text-imio-black">${email_from_name}</p>
    </div>
  </KitMain>
</template>
