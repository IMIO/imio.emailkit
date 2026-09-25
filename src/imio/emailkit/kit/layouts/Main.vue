<script setup>
/**
 * `KitMain` -- the single canonical iMio email shell.
 *
 * It owns exactly the document: the `<html>` namespace declarations, the a11y
 * defaults, the preheader, and the four bands of the v3 design -- white logo
 * band under the head artwork, tinted title band, content well, negative footer.
 * Anything else is a component.
 *
 * Import-free on purpose: this file is read from inside a Python egg, and a
 * `site-packages` directory has no `node_modules` ancestor for Vite to walk up
 * to. `useConfig` and every built-in component are auto-imported by Maizzle.
 *
 * ---------------------------------------------------------------------------
 * The four bands, and why the shell owns the title
 * ---------------------------------------------------------------------------
 * The design is a card, not a page: one 600 px white block with a 12 px radius
 * floating on an #ededed canvas, divided into four bands.
 *
 *   1. WHITE BAND -- the head artwork as a background, the site logo on the
 *      left, an optional status pill on the right. Always rendered, even with no
 *      `logo_url` and no pill: it is the card's top edge, and making it
 *      conditional would mean deciding at runtime which band carries the top
 *      radius, which cannot be expressed in a build-time class.
 *   2. TITLE BAND -- #f8f8f8 closed by a 1 px rule, with the head artwork's tail
 *      running 80 px down into it, holding the title and an optional subtitle in
 *      ink. This is the band that moved responsibility: the title used to be an
 *      `<h1>` each template wrote into the content well, and it is now the
 *      shell's, because the band is what the design uses to say what kind of
 *      message this is. A template with no title degrades to the rule alone.
 *   3. CONTENT WELL -- the default slot, plus the `body_html` seam.
 *   4. NEGATIVE FOOTER -- #1c1c1c, `footer_html` or the translated default,
 *      then the iMio logo.
 *
 * Between 3 and 4 sits the optional `mentions` region: the centred small print
 * every model in the design ends with (a fallback link, why you received this).
 * It is a slot rather than authored markup so that the shell keeps ownership of
 * the one thing an author cannot get right from outside -- the `data-dark` hook.
 *
 * ---------------------------------------------------------------------------
 * The brand artwork, and where the brand colour went
 * ---------------------------------------------------------------------------
 * v3's whole subject is a cut of the iMio brand shapes entering the mail: a head
 * visual behind the logo band, with its tail in the title band. It ships as
 * PNGs from the resource directory, transparent so the card shows through and an
 * image-blocking client is left with a clean flat rather than a hole. SVG is not
 * an option; mail clients do not render it.
 *
 * The head visual is a CSS background because the logo and the pill sit on top
 * of it. See the band itself for why there is no VML behind it.
 *
 * In exchange the title band gave up `primary_color`. The token still drives
 * `KitCard`'s rail and `KitButton`'s fill, so a site's colour is still in the
 * mail, but the largest coloured surface is now a raster asset that is iMio
 * magenta for everyone. A consumer who needs its own colour there replaces
 * `art-head.png` and `art-head-tail.png` in the resource directory; nothing in
 * this file has to change.
 *
 * ---------------------------------------------------------------------------
 * Slots, and the runtime/build-time pairs
 * ---------------------------------------------------------------------------
 * `title`, `subtitle` and `preheader` each exist twice: as a name in the render
 * context and as a named slot. They are not redundant.
 *
 * A value from `render()`'s context (`${title}`) is a *runtime* string: right
 * for `notification`, whose title is data, and for `shell`, whose title is the
 * already-translated subject. A named slot is *build-time* markup: the only way
 * to write `i18n:translate` on a heading, which is what the three restyled
 * Plone default mails need, since their title is wording and not data.
 *
 * Runtime wins where both could apply, and the choice between the two shapes is
 * made at build time by `$slots`, so exactly one of them reaches the output.
 *
 * ---------------------------------------------------------------------------
 * The two hosts, and why the `tal:define` on `<html>` looks like that
 * ---------------------------------------------------------------------------
 * Our own templates render through `render()`, whose context is flat
 * (`lang`, `theme`, `preheader`). A consumer's template may instead be rendered
 * by a *stock view*, whose kwargs land in `options`. TAL's `|` operator lets the
 * shell serve both without the author knowing which host is which.
 *
 * The chain for `theme` ends at `context/@@emailkit_theme`, the view that returns
 * the three registry-backed branding tokens as a mapping. That is what lets a
 * branding-only override ("adjust branding only, via theme tokens") reach a template
 * that cannot see `render()`'s context at all. If the view is absent the path
 * raises, `|` falls through to `nothing`, and the shell degrades to the brand
 * defaults instead of failing.
 *
 * The three tokens are then read with `python:` rather than a path, because
 * `theme` may legitimately carry an *empty* value for a record nobody has set,
 * and TAL's `|` only fires on an error, never on an empty string. `primary_color`
 * therefore keeps a literal brand default; an empty `logo_url` or `footer_html`
 * simply collapses the block that would have used it. `theme` is a mapping under
 * both hosts, which this makes an explicit contract.
 *
 * ---------------------------------------------------------------------------
 * `asset_base`, and why an image can be missing
 * ---------------------------------------------------------------------------
 * The head artwork, the pill icons and the footer's iMio logo are raster
 * assets served from the `++resource++imio.emailkit` directory registered in
 * `browser/configure.zcml`.
 * A mail client fetches them over HTTP long after the render, from outside the
 * site, so they need an ABSOLUTE URL -- which means `portal_url`, which
 * `render()` injects and which is empty whenever there is no request (a golden
 * file, a unit test, a cron job with no site).
 *
 * `asset_base` is therefore either a full URL prefix or the empty string, and
 * every image built on it carries `tal:condition="asset_base"`. Skipping the
 * image is the right degradation: a relative `/++resource++...` in an inbox is
 * a broken-image icon in every client, which is worse than no icon at all.
 * Every place that uses it stays legible without it -- a pill is a coloured fill
 * with a bold label, the footer keeps its text, and the two artwork bands fall
 * back to the flat surfaces underneath them, which is the v2 rendering.
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
 * `data-dark` attributes this file places on the surfaces it owns: the page
 * canvas, the card, the body copy and the mentions. The footer has none, on
 * purpose; it is negative already.
 *
 * The attribute is not decoration. `css.purge` only understands `class=` and
 * `id=`, so a class-keyed dark block is deleted silently with a successful
 * build; an attribute selector is outside purge's model and survives untouched.
 * The full reasoning, including why every declaration is `!important`, is in
 * `kit/tailwind.css` next to the rules themselves.
 *
 * ---------------------------------------------------------------------------
 * Vertical rhythm: every block spaces itself from ABOVE
 * ---------------------------------------------------------------------------
 * `KitCard`, `KitPanel`, `KitDataTable`, `KitButton` and `KitButtonGroup` carry
 * `mt-5` and no bottom margin, and the content well below supplies the closing
 * `pb-6`. That is the mockups' own model, where each row is
 * `padding: <gap> 40px 0` and only the last row of the card sets a bottom.
 *
 * They used to carry `my-5`, and the bottom halves added up: a mail ending in a
 * button spent 20 px of button margin plus 24 px of well padding, 44 px where
 * the design draws 22. Nothing in mail can express "except the last one" --
 * `:last-child` does not survive CSS inlining -- so the only way to keep the
 * spacing from compounding is for no block to claim any space under itself.
 *
 * The consequence for an author is one line: a block wanting more air above it
 * overrides with `mt-6`, and nothing ever needs a bottom margin.
 *
 * ---------------------------------------------------------------------------
 * Narrow screens
 * ---------------------------------------------------------------------------
 * `sm:` is Maizzle's `@media (max-width: 600px)`, and it is used for exactly the
 * two things the design's own media query did: let the card fill the width, and
 * pull the 40 px side padding in to 20 px so a phone does not spend a third of
 * its screen on gutters. The head artwork needs no rule of its own: anchored
 * right at a fixed 400 px, a narrower card simply crops it from the left, where
 * it is transparent, so the logo keeps its clear space at every width. Those rules live in a `<style>` element rather than
 * inline, which is what makes them work at all -- Juice never inlines a media
 * query.
 */
const props = defineProps({
  /**
   * A TAL expression to make the banner row conditional on, for the one case the
   * slots cannot express on their own.
   *
   * `shell.vue` is that case, and is expected to stay the only one. Its heading
   * is a runtime `${subject}`, and the compiled `shell.pt` has to RAISE on a
   * missing `subject` rather than ship an untitled mail -- which rules out the
   * layout's `title | options/title | nothing` chain, whose whole job is to
   * swallow a missing name so that a template without a banner still renders.
   * So the name is interpolated inside the `<h1>` instead, through the `title`
   * slot. That leaves the row itself unconditional, and an EMPTY subject would
   * then print a coloured band with nothing in it.
   *
   * `title-condition="subject"` closes the gap: the row is dropped when the
   * value is empty, and the expression still raises when the name is absent
   * altogether. Ignored unless a `title` slot is given.
   */
  titleCondition: { type: String, default: '' },
})

/**
 * Bound as an object because `tal:condition` cannot be written as a Vue
 * shorthand binding -- the colon is already taken by `v-bind`. An empty object
 * adds no attribute at all, which is what every template but the shell wants.
 */
const titleRowAttrs = props.titleCondition
  ? { 'tal:condition': props.titleCondition }
  : {}

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
 * output contains `<!--[endif]---->`. That is a `..` inside a comment, which
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

/**
 * The preheader's hiding rule, as the v2 mockups write it.
 *
 * `display: none` alone is not enough and never was: Outlook.com's sanitiser
 * strips it from a block element, and a handful of Android clients honour it
 * only on inline elements. The other five declarations are the belt and braces
 * every mail framework converged on -- the text is sized to nothing, coloured
 * to the canvas, clipped and made transparent, so a client that drops any one
 * of them still shows nothing.
 *
 * Bound rather than written as a literal `style` attribute so it stays one
 * string shared by both branches. There is no placeholder in it, so the usual
 * ban on `style` is not in play.
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
    <!-- The document title, for the archived `.eml`, the screen reader and the
         occasional client that shows one.

         RUNTIME TITLES ONLY, and that is a parser limit rather than a choice:
         Vue treats &lt;title&gt; as a rawtext element exactly as it treats
         &lt;style&gt;, so a slot inside it is escaped into literal text and
         shipped, as `&lt;slot name="title" /&gt;`. A Chameleon placeholder is
         plain text and survives that untouched, which is why this branch works
         and a slot branch cannot. A template whose banner title is a translated
         msgid therefore has no title element; nothing in a mail client depends
         on one, and the alternative was asking every such template to repeat
         its own msgid as a prop.

         The angle brackets above are escaped for a second reason: the authoring
         lint blanks everything between a literal &lt;style&gt; and the next
         &lt;/style&gt;, comments included, so spelling it plainly here would
         swallow this comment's own terminator. -->
    <title tal:condition="title">${title}</title>
    <Outlook>
      <style>td,th,div,p,a,h1,h2,h3,h4,h5,h6 {font-family: Arial, Helvetica, sans-serif; mso-line-height-rule: exactly;}</style>
    </Outlook>
    <!-- Quicksand, self-hosted from the resource directory; see the reasoning in
         `browser/static/fonts.css`. A LINK and not an `@font-face` block in the
         &lt;style&gt; below: the url has to carry `${asset_base}`, and a
         Chameleon placeholder inside a &lt;style&gt; element is parsed as CSS by
         Juice, which kills inlining for the whole document while the build still
         exits 0. An `href` is never parsed as CSS. -->
    <link tal:condition="asset_base" rel="stylesheet" href="${asset_base}/fonts.css">
    <style v-html="css"></style>
  </head>

  <body class="m-0 w-full bg-imio-grey-canvas p-0 [word-break:break-word]" xml:lang="${lang}" dir="ltr" data-dark="page">
    <!-- Preheader slot, fed by the optional `preheader` msgid.
         The named slot is the build-time fallback for templates a stock view
         renders: they never see `render()`'s preheader, so they supply the
         msgid as markup instead. Runtime always wins when it has a value. -->
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
            <!-- The card. `data-dark="surface"` is here rather than on each band
                 because the bands are transparent: a table's background paints
                 behind every cell that does not set one of its own. -->
            <table
              role="presentation"
              align="center"
              width="600"
              class="w-[600px] max-w-full rounded-[12px] bg-imio-white text-left sm:w-full"
              data-dark="surface"
            >
              <!-- 1. White band: the head artwork, the logo, and the status
                   pill when there is one.

                   The artwork is a BACKGROUND, which is the whole reason the band
                   is built this way: the logo and the pill have to sit on top of
                   it, and an `img` in a table cell cannot have anything over it.
                   It is 400x120 anchored top right of a 600x120 band, so the left
                   third stays white and the logo never lands on magenta.

                   The band therefore owns no colour of its own. The card behind it
                   is `bg-imio-white` and shows through the PNG's transparency,
                   which is what lets `data-dark="surface"` on the card flip this
                   band with everything else; painting #ffffff here would nail one
                   band to white in a dark client.

                   The url rides on the `background` ATTRIBUTE, not on a
                   `background-image` declaration, and that is forced rather than
                   stylistic: `${asset_base}` inside a `style` attribute is the
                   fatal, silent `style-placeholder` failure the authoring lint
                   exists for. An attribute Juice never parses as CSS can carry a
                   placeholder; the size, position and repeat are static, so they
                   stay in classes and Juice inlines them on top. Browsers treat
                   the attribute as a presentational hint for `background-image`
                   and author CSS wins over a hint, so the two halves compose.

                   `tal:attributes` rather than a literal value because an empty
                   `asset_base` (a render with no request: a golden file, a unit
                   test, a cron job with no site) would otherwise emit
                   `background="/art-head.png"`, a relative url that resolves
                   against the reader's webmail. A value of `None` drops the
                   attribute entirely and the band is plain white, which is the v2
                   rendering and perfectly serviceable.

                   The logo is 158x32 in the design; `height` is deliberately not
                   set, so a logo with different proportions is not squashed. -->
              <tr>
                <td
                  height="120"
                  tal:attributes="background python:(asset_base + '/art-head.png') if asset_base else None"
                  class="h-[120px] rounded-t-[12px] bg-[length:400px_120px] bg-[position:top_right] bg-no-repeat p-0"
                >
                  <!-- NO VML FALLBACK HERE, and it is a hard limit rather than
                       an omission.

                       The design ships one: Outlook on Windows ignores
                       `background-image`, so a `v:rect` repeats the artwork
                       behind the same content. Every way of writing it puts the
                       url inside an Outlook conditional, and Chameleon does not
                       interpolate a placeholder inside a comment at all. The
                       `.pt` therefore ships `${asset_base}` to the recipient
                       verbatim, which is the one failure this package's whole
                       test suite is built around. Measured, not assumed:
                       `test_no_unresolved_placeholder_in_html` catches it.

                       Nothing is lost that Outlook was going to show anyway.
                       Word's engine honours the `background` ATTRIBUTE below on
                       its own, so Outlook does render the artwork; it ignores
                       `background-size`, `background-position` and
                       `background-repeat`, so it tiles the PNG at natural size
                       from the top left rather than placing it at 400x120 top
                       right. The left third of the cut is transparent either
                       way, so the logo keeps its clear space and the pill still
                       lands on magenta. A `v:rect` would have been WORSE: VML
                       has no equivalent of a sized, anchored background, and
                       `type="frame"` stretches the art across the full 600 px,
                       dragging magenta under the logo.

                       And if a client renders neither, the band is plain white
                       with the logo and the pill intact, which is the v2
                       rendering and the fallback the design itself specifies. -->
                  <table role="presentation" class="w-full">
                    <tr>
                      <td class="px-10 py-6 sm:px-5">
                  <table role="presentation" class="w-full">
                    <tr>
                      <td align="left" class="text-[0px] leading-[0]">
                        <!-- The site's own logo, at the design's 158 px. `height`
                             is deliberately unset so a logo with different
                             proportions is not squashed. -->
                        <img
                          tal:condition="logo_url"
                          src="${logo_url}"
                          alt="iMio"
                          i18n:attributes="alt email_logo_alt"
                          width="158"
                          class="block"
                        >
                        <!-- Fallback: the kit's own iMio logo, so the white band
                             is never an empty 46 px strip.

                             `logo_url` is a registry token with no default and no
                             sensible one to give it; it is the CONSUMER's
                             product logo, which a shared kit cannot know. Before
                             this fallback a site that had not filled the record
                             in (which is every site on the day it is installed)
                             got a band with nothing in it, and the v2 design
                             reads as a logo band first and a white top edge
                             second. iMio built every consumer of this package, so
                             its own mark is the one honest placeholder.

                             The COLOUR logo, the one imio.be serves in its own
                             header, not the monochrome version: this sits on the
                             white band, where the magenta is the point. Shipped as
                             a 216x64 PNG and drawn at 108x32, so it is exactly 2x
                             for a retina screen and lands on the design's 32 px cap
                             height. PNG and not SVG for the reason in
                             `browser/configure.zcml`: mail clients do not render
                             SVG reliably. -->
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

              <!-- 2. Title band. Build-time markup when the template supplies
                   a `title` slot, runtime `${title}` otherwise, and a 1 px rule
                   for a template that has neither.

                   THE BAND IS NO LONGER MAGENTA. It was a `primary_color` flat
                   with white type; v3 makes it #f8f8f8 with #1c1c1c type, closed
                   by a 1 px #d2d2d2 rule, and lets the head artwork's tail run
                   80 px down into it so the two bands read as one masthead. The
                   brand colour did not leave the mail, it moved: it is the
                   artwork above, the rail on `KitCard`, and the fill on a solid
                   `KitButton`.

                   That does mean `primary_color` no longer reaches the largest
                   coloured surface in the mail. A consumer who sets the token to
                   something other than iMio magenta now gets its own rails and
                   buttons under iMio's magenta artwork, because the artwork is a
                   raster asset and cannot be recoloured per site. The escape is
                   the one the resource directory already offers: ship a
                   replacement `art-head.png`.

                   `data-dark` is nested rather than doubled: the cell carries
                   `raised` for the tint, the table inside it carries `body` for
                   the type. One element cannot hold both tokens, and the pair is
                   exactly what a tinted block inside the card already uses.

                   Only the runtime branch carries the 1 px rule. A template using
                   the slot has committed to a band at build time, so the only way
                   it can lose one is `title-condition` going false at runtime, and
                   a rule there would be a stub of a band the template asked not to
                   draw. -->
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
                <!-- No title: the band's closing rule without the band.

                     This was a 3 px `primary_color` bar, a stub of the magenta
                     flat that used to sit here. With the flat gone the stub has
                     nothing to stand for, and a 3 px magenta line under artwork
                     that is already magenta reads as a mistake. What separates
                     the masthead from the content well in v3 is the band's 1 px
                     #d2d2d2 rule, so that is what an untitled mail keeps. -->
                <tr tal:condition="not:title">
                  <td bgcolor="#d2d2d2" class="h-px text-[0px] leading-[1px]">&zwj;</td>
                </tr>
              </template>

              <!-- 3. Content well. Authored markup goes in the slot; `body_html`
                   is the one sanctioned `structure` injection point and the seam
                   `render_shell()` hands its body to. -->
              <tr>
                <td class="px-10 pb-6 pt-[30px] text-[15px] leading-6 text-imio-black sm:px-5" data-dark="body">
                  <slot />
                  <div tal:condition="body_html" tal:content="structure body_html" class="text-[15px] leading-6"></div>
                </td>
              </tr>

              <!-- Mentions: the centred small print the design ends every model
                   with. A slot rather than authored markup, so the shell keeps
                   the `data-dark` hook and the centring in one place. -->
              <tr v-if="$slots.mentions">
                <td align="center" class="px-10 pb-[26px] text-center text-[13px] leading-[21px] text-imio-grey-dark sm:px-5" data-dark="muted">
                  <slot name="mentions" />
                </td>
              </tr>

              <!-- 4. Negative footer: `footer_html` unescaped, or a
                   neutral default, then the iMio logo. No `data-dark`: this band
                   is already black in the light rendering. -->
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
                    <!-- The mark, and no attribution line above it. The v2
                         mockups ended every model on three blocks (the sender's
                         contact details, a "Service provided by iMio" signature,
                         then the mark) and the signature is gone: `footer_html`
                         is the sender's own block, and the logo already says who
                         runs the service, so that sentence was the one part of a
                         transactional mail speaking for a third party in the
                         middle of somebody else's message. Its msgid,
                         `email_footer_powered_by`, is retired with it. -->
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
