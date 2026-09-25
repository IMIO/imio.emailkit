<script setup>
/**
 * `shell` is the template `render_shell(subject, body_html)` renders.
 *
 * It has no markup of its own. Its job is to put an existing notification
 * body inside the iMio shell, using what `KitMain` already provides.
 *
 * Context it expects:
 *   subject    the banner heading. Interpolated, never `i18n:translate`d:
 *              a template cannot translate a runtime msgid.
 *   body_html  arbitrary legacy HTML, injected unescaped by the layout.
 *
 * Why the heading is a `#title` slot, not the layout's runtime `title`
 * ------------------------------------------------------------------------
 * The layout's runtime path resolves through
 * `title | options/title | nothing`, so a caller who omits it gets a
 * silently headless mail. The slot avoids that: `${subject}` is a bare
 * Chameleon name with no `|` default, so rendering the compiled
 * `shell.pt` without a `subject` raises `KeyError` at the first render,
 * instead of shipping a mail with an empty banner.
 *
 * Where the body goes, and why it is not written here
 * ------------------------------------------------------
 * `KitMain` already owns that seam: it defines `body_html` on `<html>`
 * and renders it with `structure` inside the content well. Writing
 * `tal:content="structure body_html"` here too would render the legacy
 * body twice.
 *
 * What this template deliberately does not do
 * -----------------------------------------------
 * No wrapper, no reset, no typography, no sanitising around the injected
 * markup. This document's CSS was inlined at build time, so it cannot see
 * the legacy body at all. The shell wraps the body; it does not clean it.
 *
 * The body still gets dark-mode support: the dark-mode block in
 * `kit/tailwind.css` reaches the client as a real `&lt;style&gt;` element,
 * so an injected legacy body is recoloured in a dark client even though
 * nothing at build time ever saw it.
 *
 * No pill and no preheader
 * -------------------------
 * A pill states what kind of message this is, and this template cannot
 * know that: the body came from a caller it has never seen. The
 * `preheader` slot stays empty too, so clients continue the inbox
 * snippet into the legacy body instead of repeating the subject line.
 */
</script>

<template>
  <KitMain title-condition="subject">
    <template #title>${subject}</template>
  </KitMain>
</template>
