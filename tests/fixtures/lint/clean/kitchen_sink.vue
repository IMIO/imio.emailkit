<script setup>
/**
 * CLEAN FIXTURE, everything at once -- the file whose job is to stay silent.
 *
 * Every construct the eight rules are near, written the way SPEC §3 asks for,
 * in one template. If a change to `lint.py` makes this file report anything, the
 * change has produced a false positive, and a false positive is how the whole
 * gate ends up commented out of CI.
 *
 * Deliberately present, deliberately silent:
 *
 *   - `tal:` and `i18n:` on plain elements, never on a PascalCase component
 *   - a `tal:repeat` row inside a kit component's slot
 *   - literal Tailwind classes, plus a `:class` binding that picks a whole
 *     literal name (what the kit's `Panel.vue` does)
 *   - a runtime colour through `tal:attributes="style string:..."` and another
 *     through `bgcolor`
 *   - `${...}` in `href`, in text and in a `tal:attributes` expression
 *   - `${python: ...}` for every call
 *   - an `alt` that is literal, one that is empty on purpose, one from TAL
 *   - a prose comment with no double hyphen, and MSO conditional comments that
 *     are made of hyphen runs
 *   - the Raw component named without angle brackets in prose
 *   - a JavaScript template literal in `<script>`, which is Node's `${}` and not
 *     Chameleon's
 */
const config = useConfig()
const stylesheet = `@import "@maizzle/tailwindcss";\n@import "${config.emailkit.cssEntry}";`
const TONES = {
  neutral: 'bg-imio-grey-bg border-imio-grey-border',
  accent: 'bg-imio-pink-soft border-imio-magenta',
}
const toneClass = TONES.accent
</script>

<template>
  <KitMain>
    <!-- Header; the logo token carries a translatable alt. -->
    <table role="presentation" class="w-full">
      <tr>
        <td class="pb-5">
          <img
            tal:condition="logo_url"
            src="${logo_url}"
            alt="iMio"
            i18n:attributes="alt email_logo_alt"
            width="140"
            class="block"
          >
        </td>
      </tr>
      <tr>
        <td bgcolor="${primary_color}" class="h-[3px] text-[0px] leading-[3px]">&zwj;</td>
      </tr>
    </table>

    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>

    <p i18n:translate="email_notification_lead" class="m-0 mb-4 text-sm leading-6">
      You have a new notification for
      <span i18n:name="site_name" tal:omit-tag="" tal:content="site_name">the site</span>.
    </p>

    <p class="m-0 mb-4 text-sm leading-6">${python: format_date(meeting_date)}</p>

    <!--[if mso]><table role="presentation" width="600"><tr><td><![endif]-->
    <div tal:condition="cta_url | nothing">
      <KitButton href="${cta_url}" align="center">
        <span i18n:translate="email_notification_cta" tal:omit-tag="">Open</span>
      </KitButton>
    </div>
    <!--[if mso]></td></tr></table><![endif]-->

    <div tal:condition="warning | nothing">
      <KitPanel tone="accent">
        <p
          tal:attributes="style string:border-left-color: ${theme/primary_color}"
          class="m-0 text-sm"
        >${warning}</p>
      </KitPanel>
    </div>

    <table role="presentation" class="my-4 w-full border border-solid" :class="toneClass">
      <tr>
        <td class="p-4 text-sm">
          <Img src="${divider_url}" alt="" width="552" />
        </td>
      </tr>
    </table>

    <KitDataTable>
      <template #head>
        <th scope="col" i18n:translate="email_col_item">Item</th>
        <th scope="col" i18n:translate="email_col_decision">Decision</th>
      </template>
      <tr tal:repeat="row rows">
        <td class="p-2 text-sm">${row/title}</td>
        <td class="p-2 text-sm" tal:attributes="alt row/decision">${row/decision}</td>
      </tr>
    </KitDataTable>

    <!-- ESP placeholders go inside a Raw block; spelled without brackets here so
         Maizzle's extraction regex cannot match this line. -->
    <Raw>
      <p class="m-0 text-xs">{{ unsubscribe_url }}</p>
    </Raw>

    <!--[if !mso]><!--><p class="m-0 text-xs">${footnote}</p><!--<![endif]-->

    <style v-html="stylesheet"></style>
  </KitMain>
</template>
