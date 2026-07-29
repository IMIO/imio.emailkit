<script setup>
/**
 * VIOLATING FIXTURE for `class-placeholder` (Phase 0 control 2).
 *
 * `css.safe` rewrites `$` to `-` and strips `{`/`}` inside class atoms, so the
 * placeholder is not merely unresolved -- it is corrupted into a class name
 * nobody wrote, and the build succeeds.
 */
</script>

<template>
  <KitMain>
    <p class="m-0 text-sm ${extra_class}">${intro}</p>
  </KitMain>
</template>
