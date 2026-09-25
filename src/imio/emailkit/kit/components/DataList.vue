<script setup>
/**
 * `KitDataList` renders a label/value table: a fixed handful of facts,
 * `role="presentation"` since it has no header or repetition (unlike
 * `KitDataTable`, a real data table with `role="table"`).
 *
 * Slot: default, holding `KitDataRow`s (or plain `<tr>`s for a
 * `tal:repeat`, which cannot go on a kit component).
 *
 * Mail-client traps
 * ------------------
 * - The `kit-datalist` class carries a `tr + tr > td { border-top: … }`
 *   rule from `kit/tailwind.css`: a top border on every row but the
 *   first, since only that form can be expressed with a sibling selector
 *   (`:last-child` does not survive CSS inlining; see `DataRow.vue`).
 * - `data-dark="surface"`, not `raised`: inside a `KitCard` this is the
 *   innermost of three nested fills, and dark mode inverts the nesting.
 */
</script>

<template>
  <table
    role="presentation"
    class="kit-datalist mt-4 w-full rounded-[10px] border border-solid border-imio-grey-border bg-imio-white"
    data-dark="surface"
  >
    <slot />
  </table>
</template>
