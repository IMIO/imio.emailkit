<script setup>
/**
 * `dummy.complete:notification` -- the everyday transactional template.
 *
 * Same basename as `dummy.minimal:notification` and
 * `imio.emailkit:notification`, with no clash: lookup is namespaced.
 *
 * Context keys (see `tests/fixtures/notification.py`): title, intro,
 * reference (shown in a neutral panel), cta_url (optional), cta_label.
 *
 * `tal:condition` goes on a plain `<div>`, never on the button component:
 * `tal:`/`i18n:` attributes are forbidden on kit components, since Vue
 * attribute fallthrough lands them on an arbitrary element.
 */
</script>

<template>
  <KitMain>
    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>

    <KitPanel>
      <strong>${reference}</strong>
    </KitPanel>

    <div tal:condition="cta_url | nothing">
      <KitButton href="${cta_url}" align="left">${cta_label}</KitButton>
    </div>
  </KitMain>
</template>
