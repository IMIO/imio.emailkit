<script setup>
/**
 * Plone's password-reset mail, restyled (SPEC §8.1). Shipped as a `z3c.jbot`
 * override of `Products.CMFPlone.browser.login.templates.mail_password_template`.
 *
 * ---------------------------------------------------------------------------
 * This file is one of exactly two documented exceptions to §3's authoring rules
 * ---------------------------------------------------------------------------
 * Every other template renders through §6.1 `render()` with a flat context. This
 * one is rendered by a *stock Plone view* we do not control
 * (`PasswordResetToolView`, called from `RegistrationTool.mailPassword`), which
 * means:
 *
 *   - view kwargs land in `options`, not at top level, so `member` is
 *     `options/member` and never plain `member`;
 *   - `MemberData` is not path-traversable at all -- `${member/email}` raises
 *     LocationError -- so member fields go through
 *     `python:member.getProperty('…')`, exactly as the stock template does.
 *
 * The kwargs the view is called with are `member`, `reset`, `password` and
 * `charset`. `view` and `context` (the `portal_registration` tool, acquisition
 * wrapped) are available as usual.
 *
 * ---------------------------------------------------------------------------
 * Mail headers
 * ---------------------------------------------------------------------------
 * Plone parses the headers back out of the rendered text
 * (`message_from_string(mail_text)`), so the template owns them -- which is also
 * how the subject becomes an `imio.emailkit` msgid, since the stock subject is a
 * Python method that jbot cannot reach.
 *
 * `useDoctype()` is the only hook Maizzle gives for text ahead of the document,
 * and it is a good fit rather than a hack: the string is prepended verbatim
 * *after* every transformer and after `afterTransform`, so the header block is
 * byte-stable and can never be reformatted, entity-encoded or comment-stripped.
 *
 * Each `<span>` carries `tal:omit-tag=""`. Without it the tag itself survives
 * into the header -- `Subject: <span>Password reset request</span>` -- and the
 * header is corrupt.
 */
const config = useConfig()

useOutputPath(
  `${config.emailkit.overridesPath}/Products.CMFPlone.browser.login.templates.mail_password_template.pt`
)

useDoctype(`From: <span tal:replace="structure view/encoded_mail_sender" />
To: <span tal:replace="python:options['member'].getProperty('email')" />
Subject: <span i18n:domain="imio.emailkit" i18n:translate="email_subject_mail_password_template" tal:omit-tag="">Password reset request</span>
Content-Type: text/html; charset=utf-8
Precedence: bulk

<!DOCTYPE html>`)
</script>

<template>
  <KitMain>
    <!--
      The stock view cannot hand us a runtime preheader, so the msgid the package
      registers for this template (SPEC §4) is supplied as markup. Same msgid,
      same domain; just delivered at build time instead.
    -->
    <template #preheader>
      <span i18n:translate="email_preheader_mail_password_template" tal:omit-tag="">Follow the link to choose a new password.</span>
    </template>

    <div
      tal:omit-tag=""
      tal:define="member python:options['member'];
                  reset options/reset;
                  portal_state context/@@plone_portal_state;
                  is_anonymous portal_state/anonymous;
                  site_name portal_state/navigation_root_title;
                  reset_url python:view.construct_url(reset['randomstring'])"
    >
      <p
        tal:condition="not:is_anonymous"
        i18n:translate="email_mail_password_admin_request"
        class="m-0 mb-4 text-sm leading-6 text-imio-black"
      >
        The site administrator has asked you to reset the password of the account
        <span i18n:name="userid" tal:omit-tag="" tal:content="python:member.getId()">userid</span>.
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
        <span i18n:name="hours" tal:omit-tag="" tal:content="view/expiration_timeout">24</span> hours.
      </p>

      <div tal:condition="is_anonymous">
        <KitPanel>
          <p i18n:translate="email_mail_password_tracking" class="m-0 text-sm leading-6 text-imio-black">
            If you did not ask for this, simply ignore this message: your password has not
            been changed. The request came from the IP address
            <!--
              `request/getClientAddr`, NOT stock Plone's
              `request/HTTP_X_FORWARDED_FOR | request/REMOTE_ADDR`.

              That expression renders EMPTY whenever no `X-Forwarded-For` header is
              present, and stock Plone has the bug too
              (`Products/CMFPlone/browser/login/templates/mail_password_template.pt`).
              Two behaviours combine: `HTTPRequest.get()` special-cases CGI and
              `HTTP_` keys and returns `''` for a missing one instead of raising
              (`ZPublisher/HTTPRequest.py`), while `ZopePathExpr._eval` falls through
              a `|` chain only on a traversal *exception*, never on a falsy result
              (`Products/PageTemplates/Expressions.py`). So the first subexpression
              succeeds with `''` and `REMOTE_ADDR` is dead code.

              `getClientAddr` is Zope's supported accessor and resolves the proxy
              chain itself, but only for proxies declared as `trusted-proxy` in
              zope.conf, since `HTTPRequest.trusted_proxies` defaults to empty. That
              is a deployment requirement, documented in the README. Reading the raw
              header instead would work with no configuration at all and was
              rejected: `X-Forwarded-For` is client-settable, so the sender could
              choose which IP this mail names.
            -->
            <span
              i18n:name="ipaddress"
              tal:omit-tag=""
              tal:define="host request/getClientAddr"
              tal:content="host"
            >0.0.0.0</span>.
          </p>
        </KitPanel>
      </div>
    </div>
  </KitMain>
</template>
