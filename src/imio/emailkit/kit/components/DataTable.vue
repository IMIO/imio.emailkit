<script setup>
/**
 * `KitDataTable` -- table chrome for tabular data.
 *
 * This is the one table in the kit that is NOT `role="presentation"`. It holds
 * real data, and marking a data table as presentational hides its structure from
 * screen readers. `role="table"` is stated explicitly because Maizzle's
 * `addAttributes` transformer otherwise adds `role="none"` to every `<table>`.
 *
 * Rows are the author's, not the kit's: SPEC §3 rule 1 forbids `tal:` on kit
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
 * Import-free, like every kit component.
 */
</script>

<template>
  <table role="table" class="my-4 w-full border-collapse">
    <thead v-if="$slots.head">
      <tr class="bg-imio-grey-bg">
        <slot name="head" />
      </tr>
    </thead>
    <tbody>
      <slot />
    </tbody>
  </table>
</template>
