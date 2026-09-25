<script setup>
/**
 * `dummy.minimal:notification` -- the smallest template that is still correct.
 *
 * Context keys (see `tests/fixtures/notification.py`): title (banner
 * heading, rendered by the shell), intro (lead paragraph).
 *
 * No `<h1>` here: the shell already puts `title` in the banner. Also not
 * here, since the kit owns it: `role="presentation"`, `lang`,
 * `i18n:domain`, meta tags, dark mode, the header logo and the footer.
 */
</script>

<template>
  <KitMain>
    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>
  </KitMain>
</template>
