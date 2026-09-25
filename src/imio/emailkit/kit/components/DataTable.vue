<script setup>
/**
 * `KitDataTable` renders table chrome for real tabular data: a 1px
 * outline and a 10px radius, matching `KitDataList` and the rail card.
 *
 * Slots: `head` (optional header cells), default (body rows, an author's
 * own `<tr>`s, since `tal:repeat` cannot go on a kit component).
 *
 * Mail-client traps
 * ------------------
 * - `role="table"` is stated explicitly: Maizzle's `addAttributes`
 *   transformer otherwise adds `role="none"` to every `<table>`, hiding
 *   the structure from screen readers.
 * - Header `<th>` cells want `scope="col"`, which the kit cannot add
 *   since they come from the slot.
 * - The head row carries `data-dark="raised"`, or its `<th>` cells would
 *   inherit the shell's light body colour in dark mode while the row
 *   keeps its light tint.
 * - `border-collapse` stays off: a collapsed border cannot round, since
 *   the corner belongs to two cells at once.
 */
</script>

<template>
  <table
    role="table"
    class="mt-5 w-full rounded-[10px] border border-solid border-imio-grey-border bg-imio-white"
    data-dark="surface"
  >
    <thead v-if="$slots.head">
      <tr class="bg-imio-grey-bg" data-dark="raised">
        <slot name="head" />
      </tr>
    </thead>
    <tbody>
      <slot />
    </tbody>
  </table>
</template>
