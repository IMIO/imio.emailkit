<script setup>
/**
 * `shell` -- the template SPEC §9 phase 3's `render_shell(subject, body_html)`
 * renders (docs/plans/phase-3.md §2).
 *
 * The one template in the kit with no content of its own. Its entire job is to
 * put an *existing* notification body inside the iMio shell with zero template
 * redesign, so everything except the heading is inherited from `KitMain`:
 * `i18n:domain`, `lang`, the preheader, `role="presentation"`, the theme-token
 * header rule, the logo, the content well, the footer and the `data-dark` hooks.
 *
 * Context it expects:
 *   subject    -- the heading. Interpolated, never `i18n:translate`d: a template
 *                 cannot translate a *runtime* msgid, and the same value is what
 *                 the caller hands `.subject()` for the mail header, which SPEC
 *                 §6.2 already translates Python-side. So `render_shell` passes
 *                 a translated string, exactly as it would for the header.
 *   body_html  -- arbitrary legacy HTML, injected unescaped by the layout.
 *
 * WHERE THE BODY GOES, AND WHY IT IS NOT WRITTEN HERE.
 * `KitMain` already owns that seam. It defines `body_html` on `<html>` (so both
 * §6.1's flat context and a stock view's `options` reach it) and renders it with
 * `structure` inside the content well, immediately after the default slot. A
 * second `tal:content="structure body_html"` in this file would not create the
 * slot; it would render the legacy body TWICE. This template therefore adds the
 * heading and stops, and the injection point stays in the one file that owns it.
 *
 * WHAT IT DELIBERATELY DOES NOT DO.
 * No wrapper, no reset, no typography, no sanitising around the injected markup.
 * The body is legacy HTML with its own nested tables, inline styles and links,
 * and this document's CSS was inlined at build time so it cannot see the body at
 * all. Every element added around the body is one more thing a legacy body can
 * collide with, and the shell's own layout must not depend on the body
 * cooperating. The shell wraps; it does not clean.
 *
 * WHAT THE BODY DOES GET FOR FREE, AND IT IS NOT INLINED CSS.
 * The dark-mode block in `kit/tailwind.css` reaches the client as a real
 * `<style>` element and selects on `[data-dark="body"] p|td|div|h1…`, so an
 * injected legacy body is recoloured in a dark client even though nothing at
 * build time ever saw it. Those declarations are `!important`, which is what
 * lets them win against the legacy body's own inline styles.
 *
 * NO PREHEADER, ON PURPOSE.
 * `KitMain` has a named `preheader` slot for build-time fallbacks and this
 * template leaves it empty. Filling it with the subject would spend the whole
 * inbox snippet repeating the subject line the client already shows; left empty
 * the div collapses and clients continue the snippet into the legacy body, which
 * carries information. A caller who wants an explicit preheader passes one in
 * the render context and the layout's runtime path wins, with no change here.
 */
</script>

<template>
  <KitMain>
    <h1
      tal:condition="subject"
      class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black"
    >${subject}</h1>
  </KitMain>
</template>
