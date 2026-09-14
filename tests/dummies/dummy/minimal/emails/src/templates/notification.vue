<script setup>
/**
 * `dummy.minimal:notification` -- the smallest template that is still correct.
 *
 * Everything a template needs and nothing more: the shell and a paragraph. No
 * preheader, no plaintext twin, no components beyond `KitMain`.
 *
 * Context keys, which must match `tests/fixtures/notification.py` exactly:
 *   title  -- the banner heading, rendered by the SHELL and not by this file
 *   intro  -- lead paragraph
 *
 * There is no `<h1>` here, and that is the v2 layout rather than an omission:
 * `KitMain` reads `title` from the render context and puts it in the coloured
 * banner. A template that keeps its own heading as well now shows the title
 * twice -- which is the one thing to check when porting a pre-v2 template.
 *
 * Note what else is *not* here, because the kit owns it: `role="presentation"`,
 * `lang`, `i18n:domain`, the charset and viewport meta tags, dark mode, the
 * header logo and the footer. An author never writes those.
 */
</script>

<template>
  <KitMain>
    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>
  </KitMain>
</template>
