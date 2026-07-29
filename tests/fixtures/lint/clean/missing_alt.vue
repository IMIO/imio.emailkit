<script setup>
/**
 * CLEAN counterpart to `violating/missing_alt.vue`.
 *
 * Three accepted spellings, all of which must stay silent:
 *
 *   1. a literal `alt`, translatable through `i18n:attributes` (the kit's own
 *      header logo does this);
 *   2. `alt=""` -- the correct, deliberate spelling for a decorative image, and
 *      not the same thing as a missing attribute;
 *   3. `tal:attributes="alt ..."` for a caption that only exists at runtime.
 */
</script>

<template>
  <KitMain>
    <img
      tal:condition="logo_url"
      src="${logo_url}"
      alt="iMio"
      i18n:attributes="alt email_logo_alt"
      width="140"
      class="block"
    >

    <Img src="${divider_url}" alt="" width="600" />

    <img src="${chart_url}" tal:attributes="alt chart_caption" width="600">
  </KitMain>
</template>
