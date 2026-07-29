<script setup>
/**
 * VIOLATING FIXTURE for `comment-double-dash` (Phase 0 caveat A2).
 *
 * The HTML comment in the template below contains a double hyphen. Chameleon
 * refuses to parse it ("The string '--' is not allowed in a comment"), so the
 * compiled `.pt` is unparseable AT RUNTIME while the build reports success.
 * This has cost this project time four separate times, including in ZCML, where
 * it stops the instance from starting.
 *
 * This comment block is JavaScript, not markup, and its own hyphens are
 * therefore not reported: a `<script>` block never reaches the email.
 */
</script>

<template>
  <KitMain>
    <!-- The subject is translated Python-side -- see SPEC §6.2. -->
    <p class="m-0 text-sm">${intro}</p>
  </KitMain>
</template>
