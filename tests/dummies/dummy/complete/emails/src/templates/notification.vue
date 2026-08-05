<script setup>
/**
 * `dummy.complete:notification` -- the everyday transactional template.
 *
 * Same basename as `dummy.minimal:notification` and as
 * `imio.emailkit:notification`, and there is no clash: SPEC §4 namespaces every
 * lookup by the package the ZCML registration belongs to.
 *
 * Context keys (see `tests/fixtures/notification.py`):
 *   title     -- heading
 *   intro     -- lead paragraph
 *   reference -- file reference, shown in a neutral panel
 *   cta_url   -- optional; the button only renders when it is set
 *   cta_label -- button label
 *
 * `tal:condition` goes on a plain `<div>`, never on `<KitButton>`: SPEC §3 rule 1
 * forbids `tal:`/`i18n:` attributes on kit components, because Vue attribute
 * fallthrough lands them on whichever element happens to be the component's root
 * and that is not part of any contract.
 */
</script>

<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>

    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>

    <KitPanel>
      <strong>${reference}</strong>
    </KitPanel>

    <div tal:condition="cta_url | nothing">
      <KitButton href="${cta_url}" align="left">${cta_label}</KitButton>
    </div>
  </KitMain>
</template>
