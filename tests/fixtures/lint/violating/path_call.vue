<script setup>
/**
 * VIOLATING FIXTURE for `path-call` (Phase 1, the locale helpers).
 *
 * TAL *path* expressions cannot call functions, so both lines below raise
 * "Invalid variable name" when Chameleon compiles the template. This one at
 * least fails loudly -- but it fails at render time, on the first real mail, and
 * authors hit it constantly because `${format_date(when)}` is what every other
 * templating language would want.
 */
</script>

<template>
  <KitMain>
    <p class="m-0 text-sm">${format_date(meeting_date)}</p>
    <p class="m-0 text-xs">${format_number(total, 2)}</p>
  </KitMain>
</template>
