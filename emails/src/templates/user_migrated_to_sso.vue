<script setup>
/**
 * "Your account now uses Wallonie Connect": sent once per account, when a
 * local account has been migrated onto its Wallonie Connect (SSO)
 * identity.
 *
 * Context keys:
 *   site_name    the product the reader knows, e.g. "Délibérations.be"
 *   institution  the institution's title, e.g. "Ville de Namur"
 *   email        the address the account is now reached by, and its new
 *                userid
 *   username     the local username that has just stopped working
 *   login_url    starts the OIDC flow and comes back to the institution
 *   account_url  the Wallonie Connect account console; may be empty, and
 *                the password callout then drops its link
 *
 * The reader is being told about a change they did not ask for and cannot
 * undo, so the mail answers the three questions they will have, in order:
 * what do I type now (the card), how do I get in (the button), and what
 * happened to my password (the callout). Nothing else.
 *
 * The subject names no product, because the registration subject is one
 * fixed msgid for every consumer. The product name is in the lead
 * paragraph instead.
 */
</script>

<template>
  <KitMain>
    <template #pill>
      <KitPill tone="success">
        <span i18n:translate="email_pill_account_migrated" tal:omit-tag="">Account migrated</span>
      </KitPill>
    </template>

    <template #title>
      <span i18n:translate="email_title_sso_migrated" tal:omit-tag="">Your account now uses Wallonie Connect</span>
    </template>
    <template #subtitle>${institution}</template>

    <p
      i18n:translate="email_sso_migrated_lead"
      class="m-0 text-[15px] leading-6 text-imio-grey-dark"
    >
      Your access to
      <span i18n:name="institution" tal:omit-tag="" tal:content="institution">the institution</span>
      on
      <span i18n:name="site_name" tal:omit-tag="" tal:content="site_name">the site</span>
      is now managed by Wallonie Connect, the single sign-on service of the
      Walloon local authorities. Nothing you published changes; only the way you
      log in does.
    </p>

    <KitCard>
      <template #overline>
        <span i18n:translate="email_card_your_account" tal:omit-tag="">Your account</span>
      </template>
      <template #title>${email}</template>
      <KitDataList>
        <KitDataRow>
          <template #label>
            <span i18n:translate="email_field_institution" tal:omit-tag="">Institution</span>
          </template>
          ${institution}
        </KitDataRow>
        <KitDataRow>
          <template #label>
            <span i18n:translate="email_field_former_username" tal:omit-tag="">Former username</span>
          </template>
          ${username}
        </KitDataRow>
      </KitDataList>
    </KitCard>

    <!--
      The mark, then the button that repeats it in words. `asset_base` is
      empty whenever the render had no request to build an absolute URL
      from (a preview, a unit test), so the whole row is dropped rather
      than shipping a relative url that would show as a broken-image icon.

      A raster logo, not SVG: mail clients do not render SVG. If images
      are blocked, the `alt` text and the button below say the same thing.
    -->
    <table role="presentation" tal:condition="asset_base" class="w-full">
      <tr>
        <td align="center" class="pt-2 text-[0px] leading-[0]">
          <img
            src="${asset_base}/logo-wallonie-connect.png"
            alt="Wallonie Connect"
            width="200"
            height="48"
            class="block"
          >
        </td>
      </tr>
    </table>

    <KitButton href="${login_url}" align="center">
      <span i18n:translate="email_cta_sso_migrated" tal:omit-tag="">Log in with Wallonie Connect</span>
    </KitButton>

    <KitPanel>
      <template #overline>
        <span i18n:translate="email_callout_password" tal:omit-tag="">Your password</span>
      </template>
      <p
        i18n:translate="email_sso_migrated_password"
        class="m-0 text-sm leading-[22px] text-imio-black"
      >
        Your former username
        <span i18n:name="username" tal:omit-tag="" tal:content="username">username</span>
        and its password no longer work. Your password is now the one on your
        Wallonie Connect account, and that is where you change it.
      </p>
      <p tal:condition="account_url | nothing" class="m-0 pt-2 text-sm leading-[22px]">
        <a href="${account_url}" class="text-imio-magenta-dark underline" data-dark="accent"
          ><span i18n:translate="email_sso_migrated_account_link" tal:omit-tag="">Manage my Wallonie Connect account</span></a>
      </p>
    </KitPanel>

    <template #mentions>
      <!--
        The address as a real link, not plain grey text: a client that
        autolinks it styles it on its own; one that does not leaves the
        reader retyping it by hand. `data-dark="accent"` moves it off
        #b3004b, which is about 2:1 on a dark ground.
      -->
      <p class="m-0 text-[13px] leading-[21px] text-imio-grey-dark">
        <span i18n:translate="email_sso_migrated_fallback" tal:omit-tag="">If the button does not work, copy this address into your browser:</span>
        <br>
        <a href="${login_url}" class="break-all text-imio-magenta-dark underline" data-dark="accent">${login_url}</a>
      </p>
    </template>
  </KitMain>
</template>
