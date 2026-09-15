<script setup>
/**
 * `KitDataTable` -- table chrome for tabular data.
 *
 * This is the one table in the kit that is NOT `role="presentation"`. It holds
 * real data, and marking a data table as presentational hides its structure from
 * screen readers. `role="table"` is stated explicitly because Maizzle's
 * `addAttributes` transformer otherwise adds `role="none"` to every `<table>`.
 *
 * Rows are the author's, not the kit's: `tal:` is forbidden on kit
 * components, because attribute fallthrough lands them on an unpredictable root
 * element. So a `tal:repeat` lives on the author's own `<tr>` inside the default
 * slot:
 *
 *     <KitDataTable>
 *       <template #head>
 *         <th scope="col" i18n:translate="">col_title</th>
 *       </template>
 *       <tr tal:repeat="row rows">
 *         <td>${row/title}</td>
 *       </tr>
 *     </KitDataTable>
 *
 * Header cells want `scope="col"`; the kit cannot add it for you because the
 * cells come from the slot.
 *
 * The head row carries `data-dark="raised"` (see `kit/tailwind.css`). Measured:
 * its `<th>` cells get no inline colour of their own, so in dark mode they
 * inherit the shell's light body colour while the row keeps its light tint,
 * i.e. light on light. In dark mode the head therefore reads as a raised block
 * and is told apart by `<th>`'s own bold weight as much as by its tint.
 *
 * The v2 chrome is the rest: a 1 px #ededed outline and a 10 px radius, the same
 * two values `KitDataList` and the rail card use, so a mail that shows both a
 * data table and a metadata list does not show two different table styles.
 * `border-collapse` is gone with it -- a collapsed border cannot round, because
 * the corner belongs to two cells at once.
 *
 * Not to be confused with `KitDataList`, which looks similar and is a different
 * thing: a fixed handful of label/value pairs, presentational, no header. See
 * its own file for the distinction.
 *
 * Import-free, like every kit component.
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
