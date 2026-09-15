<script setup>
/**
 * `shell` -- the template `render_shell(subject, body_html)` renders.
 *
 * The one template in the kit with no content of its own, and since the v2
 * layout it has no markup either. Its entire job is to put an *existing*
 * notification body inside the iMio shell with zero template redesign, and
 * everything it needs is now something `KitMain` already does: `i18n:domain`,
 * `lang`, the preheader, `role="presentation"`, the white logo band, the title
 * banner, the content well, the negative footer and the `data-dark` hooks.
 *
 * Context it expects:
 *   subject    -- the banner heading. Interpolated, never `i18n:translate`d: a
 *                 template cannot translate a *runtime* msgid, and the same
 *                 value is what the caller hands `.subject()` for the mail
 *                 header, which is already translated Python-side. So
 *                 `render_shell` passes a translated string, exactly as it would
 *                 for the header.
 *   body_html  -- arbitrary legacy HTML, injected unescaped by the layout.
 *
 * WHY THE HEADING IS A `#title` SLOT AND NOT THE LAYOUT'S RUNTIME `title`.
 * It used to be an `<h1>` in the content well, because the pre-v2 shell had
 * nowhere else to put one; the v2 shell has the banner, so the heading moved
 * there. The layout would also accept a `title` name straight from the render
 * context, and `render_shell` could pass one — but that path resolves through
 * `title | options/title | nothing`, so a caller who omitted it would get a
 * silently headless mail.
 *
 * The slot keeps the old contract instead. `${subject}` is a bare Chameleon name
 * with no `|` default, so rendering the compiled `shell.pt` without a `subject`
 * raises `KeyError` — loud, at the first render, rather than a mail that goes
 * out with an empty banner. `render_shell`'s signature already makes `subject`
 * mandatory; this is the guard for the shipped artifact, which `z3c.jbot` can
 * override and which a future caller could render another way.
 *
 * WHERE THE BODY GOES, AND WHY IT IS NOT WRITTEN HERE.
 * `KitMain` already owns that seam. It defines `body_html` on `<html>` (so both
 * the flat render context and a stock view's `options` reach it) and renders it with
 * `structure` inside the content well, immediately after the default slot. A
 * `tal:content="structure body_html"` in this file would not create the slot; it
 * would render the legacy body TWICE. The heading above is all this file adds,
 * and the injection point stays in the one file that owns it.
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
 * NO PILL, AND NO PREHEADER, ON PURPOSE.
 * A pill states what kind of message this is, and this template does not know:
 * its body came from a caller it has never seen. Inventing a badge for it would
 * be the shell asserting something it cannot check. `KitMain`'s `preheader` slot
 * is left empty for a related reason: filling it with the subject would spend the
 * whole inbox snippet repeating the subject line the client already shows, while
 * an empty div collapses and lets clients continue the snippet into the legacy
 * body, which carries information. A caller who wants an explicit preheader
 * passes one in the render context and the layout's runtime path wins, with no
 * change here.
 */
</script>

<template>
  <KitMain title-condition="subject">
    <template #title>${subject}</template>
  </KitMain>
</template>
