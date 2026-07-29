<script setup>
/**
 * `KitMain` -- the single canonical iMio email shell (SPEC §3).
 *
 * It owns exactly the document: the `<html>` namespace declarations, the a11y
 * defaults, the preheader, the header, the footer and the content well.
 * Anything else is a component.
 *
 * Import-free on purpose: this file is read from inside a Python egg, and a
 * `site-packages` directory has no `node_modules` ancestor for Vite to walk up
 * to. `useConfig` and every built-in component are auto-imported by Maizzle.
 *
 * ---------------------------------------------------------------------------
 * The two hosts, and why the `tal:define` on `<html>` looks like that
 * ---------------------------------------------------------------------------
 * Our own templates render through SPEC §6.1 `render()`, whose context is flat
 * (`lang`, `theme`, `preheader`). The two Plone-default mails are rendered by a
 * *stock view*, whose kwargs land in `options` instead. TAL's `|` operator lets
 * the shell serve both without the author knowing which host is which.
 *
 * The chain for `theme` ends at `context/@@emailkit_theme`, the view that returns
 * the three registry-backed branding tokens as a mapping. That is what makes
 * SPEC §8.2 level 2 ("adjust branding only, via theme tokens") reach the
 * jbot-hosted default mails, which cannot see `render()`'s context at all. If
 * the view is absent the path raises, `|` falls through to `nothing`, and the
 * shell degrades to the brand defaults instead of failing.
 *
 * The three tokens are then read with `python:` rather than a path, because
 * `theme` may legitimately carry an *empty* value for a record nobody has set,
 * and TAL's `|` only fires on an error, never on an empty string. `primary_color`
 * therefore keeps a literal brand default; an empty `logo_url` or `footer_html`
 * simply collapses the block that would have used it. `theme` is a mapping under
 * both hosts, which this makes an explicit contract.
 *
 * ---------------------------------------------------------------------------
 * Theme tokens: `bgcolor`, never a `style` attribute
 * ---------------------------------------------------------------------------
 * A Chameleon placeholder inside a literal `style` attribute is fatal and
 * silent: Juice parses the attribute as CSS, the `{` opens a block, the closing
 * `}` is eaten, and CSS inlining stops for the whole document while the build
 * still exits 0. So a runtime colour rides on `bgcolor` (an attribute Juice
 * never parses, and the most bulletproof way to colour a cell in mail anyway)
 * and never on `style`. Same rule for `class`, where `css.safe` would rewrite
 * `$` and strip the braces.
 *
 * ---------------------------------------------------------------------------
 * Dark mode: `data-dark` hooks, rules in `kit/tailwind.css`
 * ---------------------------------------------------------------------------
 * The `color-scheme` / `supported-color-schemes` meta tags below only tell a
 * client we are dark-aware. The rules that act on it live in the kit's CSS entry
 * under one `@media (prefers-color-scheme: dark)` block, and they select on the
 * `data-dark` attributes this file places on the four surfaces it owns: the
 * page canvas, the content well, the body copy and the footer.
 *
 * The attribute is not decoration. `css.purge` only understands `class=` and
 * `id=`, so a class-keyed dark block is deleted silently with a successful
 * build; an attribute selector is outside purge's model and survives untouched.
 * The full reasoning, including why every declaration is `!important`, is in
 * `kit/tailwind.css` next to the rules themselves.
 */
const config = useConfig()

/**
 * The document's CSS entry.
 *
 * `@maizzle/tailwindcss` is imported *here* and not from the kit's own
 * `tailwind.css`: Tailwind resolves a bare specifier by walking up from the
 * importing file, and a kit directory inside a Python egg has no `node_modules`
 * ancestor. Written in the SFC it reaches Maizzle's PostCSS plugin, which
 * rewrites it to an absolute path before Tailwind ever sees it. Measured -- and
 * the failure is silent: Maizzle catches CSS errors and ships the uncompiled
 * stylesheet with a successful exit code.
 *
 * `cssEntry` is absolute for the same reason, and comes from the kit's base
 * config. Vue's template parser treats `<style>` as raw text, so `{{ }}` never
 * interpolates there -- hence `v-html`.
 */
const css = `@import "@maizzle/tailwindcss";\n@import "${config.emailkit.cssEntry}";`

/**
 * Outlook's document settings: a whole conditional comment in one raw string,
 * injected with `v-html`. Kept as a string so Vue never tries to resolve
 * `<o:OfficeDocumentSettings>` as a component.
 *
 * `<Outlook>` is used for the MSO head style below, and it is safe there because
 * it has real slot content. Measured: with an *empty* slot and the markup passed
 * as its `open` prop, the two halves come out as separate static nodes with a
 * Vue placeholder between them, the parser ends the comment early, and the
 * output contains `<!--[endif]---->`. That is a `--` inside a comment, which
 * Chameleon refuses to parse, and the build still exits 0. `<o:…>` tags cannot
 * be slot content, so this block takes the `v-html` route instead.
 */
const msoOfficeSettings =
  '<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch>'
  + '</o:OfficeDocumentSettings><w:WordDocument><w:DontUseAdvancedTypographyReadingMail />'
  + '</w:WordDocument></xml><![endif]-->'

/**
 * Invisible filler after the preheader, so clients do not pull body copy into
 * the inbox snippet. Maizzle's own `Preheader` sizes this from the text length
 * at *build* time, which is wrong when the text is a runtime `${preheader}`
 * placeholder -- so the count is fixed here instead.
 */
const preheaderFiller = '&#8199;&#65279;&#847; '.repeat(20)
</script>

<template>
  <html
    lang="${lang}"
    dir="ltr"
    xmlns:v="urn:schemas-microsoft-com:vml"
    xmlns:o="urn:schemas-microsoft-com:office:office"
    i18n:domain="imio.emailkit"
    tal:define="lang lang | options/lang | request/LANGUAGE | string:en; preheader preheader | options/preheader | nothing; body_html body_html | options/body_html | nothing; theme theme | options/theme | context/@@emailkit_theme | nothing; logo_url python:(theme or {}).get('logo_url') or ''; primary_color python:(theme or {}).get('primary_color') or '#e6007e'; footer_html python:(theme or {}).get('footer_html') or ''"
  >
  <head>
    <meta charset="utf-8">
    <meta name="x-apple-disable-message-reformatting">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no, url=no">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <Outlook>
      <style>td,th,div,p,a,h1,h2,h3,h4,h5,h6 {font-family: Arial, Helvetica, sans-serif; mso-line-height-rule: exactly;}</style>
    </Outlook>
    <style v-html="css"></style>
  </head>

  <body class="m-0 w-full bg-imio-grey-bg p-0 [word-break:break-word]" xml:lang="${lang}" dir="ltr" data-dark="page">
    <!-- SPEC §3 preheader slot, fed by the optional `preheader` msgid (§4).
         The named slot is the build-time fallback for templates a stock Plone
         view renders: they never see `render()`'s preheader, so they supply the
         msgid as markup instead. Runtime always wins when it has a value. -->
    <div tal:condition="preheader" style="display: none">${preheader}{{ preheaderFiller }}</div>
    <div v-if="$slots.preheader" tal:condition="not:preheader" style="display: none"><slot name="preheader" />{{ preheaderFiller }}</div>

    <span style="display: none" v-html="msoOfficeSettings"></span>

    <div
      role="article"
      aria-roledescription="email"
      lang="${lang}"
      dir="ltr"
      class="bg-imio-grey-bg font-body text-sm text-imio-black"
      data-dark="page"
    >
      <Container class="px-6 py-8">
        <!-- Header: the logo token, with an alt that is enforced and translatable. -->
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

        <!-- Content well. Authored markup goes in the slot; `body_html` is the
             one sanctioned `structure` injection point (§3 rule 4) and the seam
             SPEC §9 phase 3's `render_shell()` will hand its body to. -->
        <table role="presentation" class="w-full bg-imio-white" data-dark="surface">
          <tr>
            <td class="p-6 text-sm leading-6 text-imio-black" data-dark="body">
              <slot />
              <div tal:condition="body_html" tal:content="structure body_html" class="text-sm leading-6"></div>
            </td>
          </tr>
        </table>

        <!-- Footer: `footer_html` unescaped (§3 rule 4), or a neutral default. -->
        <table role="presentation" class="w-full">
          <tr>
            <td class="pt-5 text-xs leading-5 text-imio-grey-dark" data-dark="muted">
              <div tal:condition="footer_html" tal:content="structure footer_html"></div>
              <p tal:condition="not:footer_html" i18n:translate="email_footer_default" class="m-0 text-xs leading-5 text-imio-grey-dark">
                This message was sent automatically. Please do not reply to it.
              </p>
            </td>
          </tr>
        </table>
      </Container>
    </div>
  </body>
  </html>
</template>
