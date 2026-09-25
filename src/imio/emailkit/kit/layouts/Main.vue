<script setup>
/**
 * `KitMain` is the single iMio email shell.
 *
 * It owns the document: the `<html>` namespace declarations, a11y
 * defaults, the preheader, and four bands: white logo band, tinted title
 * band, content well, dark footer. Everything else is a component.
 *
 * No imports: this file loads from inside a Python egg, which has no
 * `node_modules` ancestor for Vite. Maizzle auto-imports `useConfig` and
 * every built-in component.
 *
 * Slots: `pill`, `title`, `subtitle`, `preheader`, default (body well),
 * `mentions`. `title`, `subtitle` and `preheader` also exist as runtime
 * values (`${title}` etc). Use the slot for text that needs
 * `i18n:translate`; use the runtime value for data. Runtime wins if both
 * are given.
 *
 * `theme` (`logo_url`, `primary_color`, `footer_html`) falls back through
 * `context/@@emailkit_theme` when the render context has none, so a stock
 * Plone view without `render()` still gets brand defaults.
 *
 * Mail-client traps
 * ------------------
 * - Never put a Chameleon placeholder inside a `style` attribute or a
 *   `class`. Juice parses `style` as CSS, so the placeholder's `{` opens
 *   a block that never closes, and CSS inlining silently stops for the
 *   whole document while the build still exits 0. A runtime colour rides
 *   on `bgcolor` instead, which Juice never parses.
 * - `&lt;title&gt;` and `&lt;style&gt;` are rawtext elements in Vue: a
 *   slot placed inside either becomes literal escaped text, not markup.
 *   Only a Chameleon placeholder, being plain text, survives there.
 * - `asset_base` (built from `portal_url`) is empty with no request (a
 *   golden file, a unit test, a cron job). Every image built on it
 *   carries `tal:condition="asset_base"`, since a relative
 *   `/++resource++...` url shows as a broken-image icon in every client.
 * - `data-dark` is an attribute, not a class: `css.purge` only
 *   understands `class=`/`id=` and silently deletes a class-keyed dark
 *   rule on a successful build. The rules themselves live in
 *   `kit/tailwind.css`.
 * - Mail CSS has no `:last-child` that survives inlining, so
 *   `KitCard`, `KitPanel`, `KitDataTable`, `KitButton` and
 *   `KitButtonGroup` set only a top margin; the content well supplies the
 *   closing bottom padding. Add space above a block with `mt-6`.
 * - The head artwork is a CSS background, not an `<img>`, so the logo and
 *   pill can sit on top of it. Its url rides on the `background`
 *   ATTRIBUTE, never a style declaration.
 * - The `sm:` narrow-screen rules live in a `&lt;style&gt;` element, not
 *   inline, because Juice never inlines a media query.
 */
const props = defineProps({
  /**
   * TAL expression for `shell.vue`: drops the title row when the value is
   * empty, but a missing value still raises `KeyError`. Ignored unless a
   * `title` slot is given.
   */
  titleCondition: { type: String, default: '' },
})

/** An object, since `tal:condition` cannot be a Vue shorthand binding
 * (the colon is already `v-bind`'s). Empty adds no attribute. */
const titleRowAttrs = props.titleCondition
  ? { 'tal:condition': props.titleCondition }
  : {}

const config = useConfig()

/**
 * `@maizzle/tailwindcss` is imported here, not from `tailwind.css`: a kit
 * directory inside a Python egg has no `node_modules` ancestor, and
 * Maizzle's PostCSS plugin only rewrites this specific import to an
 * absolute path. Vue treats `&lt;style&gt;` as raw text, so `v-html`
 * carries it instead of `{{ }}`.
 */
const css = `@import "@maizzle/tailwindcss";\n@import "${config.emailkit.cssEntry}";`

/**
 * Outlook's document settings, kept as a raw string and injected with
 * `v-html` so Vue never treats `<o:OfficeDocumentSettings>` as a
 * component. Not written as the Outlook component with an empty slot:
 * Vue then splits the markup around the slot placeholder, ending the
 * conditional comment early and leaving a dangling double hyphen that
 * Chameleon refuses to parse.
 */
const msoOfficeSettings =
  '<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch>'
  + '</o:OfficeDocumentSettings><w:WordDocument><w:DontUseAdvancedTypographyReadingMail />'
  + '</w:WordDocument></xml><![endif]-->'

/** Invisible filler after the preheader, so clients do not pull body
 * copy into the inbox snippet. Fixed here, not by Maizzle's `Preheader`
 * component, since the text is a runtime `${preheader}` placeholder. */
const preheaderFiller = '&#8199;&#65279;&#847; '.repeat(20)

/**
 * The preheader's hiding rule. `display: none` alone is not enough:
 * Outlook.com strips it from a block element, and some Android clients
 * honour it only on inline elements. Bound, not a literal `style`
 * attribute, so both branches below share one string.
 */
const hiddenPreheader =
  'display:none;font-size:1px;color:#ededed;line-height:1px;'
  + 'max-height:0;max-width:0;opacity:0;overflow:hidden;'
</script>

<template>
  <html
    lang="${lang}"
    dir="ltr"
    xmlns:v="urn:schemas-microsoft-com:vml"
    xmlns:o="urn:schemas-microsoft-com:office:office"
    i18n:domain="imio.emailkit"
    tal:define="lang lang | options/lang | request/LANGUAGE | string:en; preheader preheader | options/preheader | nothing; title title | options/title | nothing; subtitle subtitle | options/subtitle | nothing; body_html body_html | options/body_html | nothing; theme theme | options/theme | context/@@emailkit_theme | nothing; logo_url python:(theme or {}).get('logo_url') or ''; primary_color python:(theme or {}).get('primary_color') or '#e6007e'; footer_html python:(theme or {}).get('footer_html') or ''; portal_url portal_url | options/portal_url | string:; asset_base python:(str(portal_url).rstrip('/') + '/++resource++imio.emailkit') if portal_url else ''"
  >
  <head>
    <meta charset="utf-8">
    <meta name="x-apple-disable-message-reformatting">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no, url=no">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <!-- Runtime title only: see the rawtext-element trap above. -->
    <title tal:condition="title">${title}</title>
    <Outlook>
      <style>td,th,div,p,a,h1,h2,h3,h4,h5,h6 {font-family: Arial, Helvetica, sans-serif; mso-line-height-rule: exactly;}</style>
    </Outlook>
    <!-- A LINK, not @font-face in the style below: `${asset_base}` inside
         a &lt;style&gt; element hits the Juice trap above. -->
    <link tal:condition="asset_base" rel="stylesheet" href="${asset_base}/fonts.css">
    <style v-html="css"></style>
  </head>

  <body class="m-0 w-full bg-imio-grey-canvas p-0 [word-break:break-word]" xml:lang="${lang}" dir="ltr" data-dark="page">
    <!-- Slot: build-time fallback for a stock-view template. Runtime wins. -->
    <div tal:condition="preheader" :style="hiddenPreheader">${preheader}{{ preheaderFiller }}</div>
    <div v-if="$slots.preheader" tal:condition="not:preheader" :style="hiddenPreheader"><slot name="preheader" />{{ preheaderFiller }}</div>

    <span style="display: none" v-html="msoOfficeSettings"></span>

    <div
      role="article"
      aria-roledescription="email"
      lang="${lang}"
      dir="ltr"
      class="bg-imio-grey-canvas font-body text-sm text-imio-black"
      data-dark="page"
    >
      <table role="presentation" class="w-full bg-imio-grey-canvas" data-dark="page">
        <tr>
          <td align="center" class="px-3 pb-9 pt-8">
            <!-- `data-dark="surface"` is here, not per band: the bands are
                 transparent and this table's background shows through. -->
            <table
              role="presentation"
              align="center"
              width="600"
              class="w-[600px] max-w-full rounded-[12px] bg-imio-white text-left sm:w-full"
              data-dark="surface"
            >
              <!-- 1. White band: head artwork, logo, optional status pill.
                   `tal:attributes` drops a `None` background rather than
                   emit a relative url when `asset_base` is empty. -->
              <tr>
                <td
                  height="120"
                  tal:attributes="background python:(asset_base + '/art-head.png') if asset_base else None"
                  class="h-[120px] rounded-t-[12px] bg-[length:400px_120px] bg-[position:top_right] bg-no-repeat p-0"
                >
                  <!-- No VML fallback: a `v:rect` needs the url inside an
                       Outlook conditional comment, where Chameleon cannot
                       interpolate a placeholder, so it would ship
                       `${asset_base}` verbatim. Word's own `background`
                       ATTRIBUTE support renders the artwork tiled instead;
                       with no support at all the band is plain white. -->
                  <table role="presentation" class="w-full">
                    <tr>
                      <td class="px-10 py-6 sm:px-5">
                  <table role="presentation" class="w-full">
                    <tr>
                      <td align="left" class="text-[0px] leading-[0]">
                        <!-- Site logo; `height` unset so it is not squashed. -->
                        <img
                          tal:condition="logo_url"
                          src="${logo_url}"
                          alt="iMio"
                          i18n:attributes="alt email_logo_alt"
                          width="158"
                          class="block"
                        >
                        <!-- Fallback: iMio's own mark, so the band is
                             never empty when `logo_url` is unset. -->
                        <img
                          tal:condition="python:not logo_url and asset_base"
                          src="${asset_base}/imio-logo.png"
                          alt="iMio"
                          i18n:attributes="alt email_logo_alt"
                          width="108"
                          height="32"
                          class="block"
                        >
                      </td>
                      <td v-if="$slots.pill" align="right"><slot name="pill" /></td>
                    </tr>
                  </table>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- 2. Title band: `title` slot at build time, runtime
                   `${title}` otherwise, a 1px rule when there is neither.
                   `data-dark` is nested (`raised` on the cell, `body` on
                   the inner table): one element cannot carry both. -->
              <template v-if="$slots.title">
                <tr v-bind="titleRowAttrs">
                  <td
                    bgcolor="#f8f8f8"
                    tal:attributes="background python:(asset_base + '/art-head-tail.png') if asset_base else None"
                    class="[border-bottom:1px_solid_#d2d2d2] bg-imio-grey-bg bg-[length:400px_80px] bg-[position:top_right] bg-no-repeat px-10 pb-[30px] pt-[22px] sm:px-5"
                    data-dark="raised"
                  >
                    <table role="presentation" class="w-full" data-dark="body">
                      <tr>
                        <td>
                          <h1 class="m-0 font-display text-[28px] font-bold leading-9 text-imio-black sm:text-2xl sm:leading-8"><slot name="title" /></h1>
                          <p v-if="$slots.subtitle" class="m-0 pt-[10px] text-sm leading-[22px] text-imio-grey-dark"><slot name="subtitle" /></p>
                          <p v-else tal:condition="subtitle" class="m-0 pt-[10px] text-sm leading-[22px] text-imio-grey-dark">${subtitle}</p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </template>
              <template v-else>
                <tr tal:condition="title">
                  <td
                    bgcolor="#f8f8f8"
                    tal:attributes="background python:(asset_base + '/art-head-tail.png') if asset_base else None"
                    class="[border-bottom:1px_solid_#d2d2d2] bg-imio-grey-bg bg-[length:400px_80px] bg-[position:top_right] bg-no-repeat px-10 pb-[30px] pt-[22px] sm:px-5"
                    data-dark="raised"
                  >
                    <table role="presentation" class="w-full" data-dark="body">
                      <tr>
                        <td>
                          <h1 class="m-0 font-display text-[28px] font-bold leading-9 text-imio-black sm:text-2xl sm:leading-8">${title}</h1>
                          <p tal:condition="subtitle" class="m-0 pt-[10px] text-sm leading-[22px] text-imio-grey-dark">${subtitle}</p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <!-- No title: only the band's closing rule. -->
                <tr tal:condition="not:title">
                  <td bgcolor="#d2d2d2" class="h-px text-[0px] leading-[1px]">&zwj;</td>
                </tr>
              </template>

              <!-- 3. Content well: the slot, plus the `body_html` seam. -->
              <tr>
                <td class="px-10 pb-6 pt-[30px] text-[15px] leading-6 text-imio-black sm:px-5" data-dark="body">
                  <slot />
                  <div tal:condition="body_html" tal:content="structure body_html" class="text-[15px] leading-6"></div>
                </td>
              </tr>

              <!-- Mentions: small print. A slot, so the shell keeps the
                   `data-dark` hook. -->
              <tr v-if="$slots.mentions">
                <td align="center" class="px-10 pb-[26px] text-center text-[13px] leading-[21px] text-imio-grey-dark sm:px-5" data-dark="muted">
                  <slot name="mentions" />
                </td>
              </tr>

              <!-- 4. Dark footer: `footer_html` or a default message,
                   then the iMio logo. -->
              <tr>
                <td bgcolor="#1c1c1c" class="rounded-b-[12px] bg-imio-black px-10 pb-7 pt-[26px] sm:px-5">
                  <table role="presentation" class="w-full">
                    <tr>
                      <td align="center" class="text-center text-xs leading-5 text-imio-grey-border">
                        <div tal:condition="footer_html" tal:content="structure footer_html"></div>
                        <p tal:condition="not:footer_html" i18n:translate="email_footer_default" class="m-0 text-xs leading-5 text-imio-grey-border">
                          This message was sent automatically. Please do not reply to it.
                        </p>
                      </td>
                    </tr>
                    <!-- No attribution line: `footer_html` is the
                         sender's own block, and the logo names the service. -->
                    <tr tal:condition="asset_base">
                      <td align="center" class="pt-[18px] text-[0px] leading-[0]">
                        <img
                          src="${asset_base}/imio-logo-negative.png"
                          alt="iMio"
                          i18n:attributes="alt email_logo_alt"
                          width="68"
                          height="20"
                          class="mx-auto block"
                        >
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
  </body>
  </html>
</template>
