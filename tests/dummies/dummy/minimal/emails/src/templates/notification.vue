<script setup>
/**
 * `dummy.minimal:notification` -- the smallest template that is still correct.
 *
 * Everything a template needs and nothing more: the shell, a heading, a
 * paragraph. No preheader, no plaintext twin, no components beyond `KitMain`.
 *
 * Context keys, which must match `tests/fixtures/notification.py` exactly:
 *   title  -- heading text
 *   intro  -- lead paragraph
 *
 * Note what is *not* here, because the kit owns it: `role="presentation"`,
 * `lang`, `i18n:domain`, the charset and viewport meta tags, dark mode, the
 * header logo and the footer. An author never writes those.
 */
</script>

<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>

    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>
  </KitMain>
</template>
