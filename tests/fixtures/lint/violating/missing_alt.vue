<script setup>
/**
 * VIOLATING FIXTURE for `missing-alt` (the enforced-alt a11y default).
 *
 * RGAA applies to iMio's clients, and a mail client that blocks remote images
 * shows an unlabelled box. Neither is visible from a developer's inbox.
 */
</script>

<template>
  <KitMain>
    <img src="${logo_url}" width="140" class="block">

    <Img
      src="${banner_url}"
      width="600"
    />
  </KitMain>
</template>
