<script setup>
/**
 * `KitButtonGroup` puts two `KitButton`s on one row: each button is its
 * own table, and two tables cannot otherwise share a line in mail.
 *
 * Props: `align` (`left`/`center`/`right`). Slots: `primary`, `secondary`
 * (optional; with only `primary` filled this renders one centred button).
 *
 * Mail-client trap: the two cells always stay side by side, since `sm:`
 * cannot turn a `<td>` into a block in Outlook. A mail whose actions do
 * not fit on one line needs two stacked `KitButton`s instead.
 */
defineProps({
  align: { type: String, default: 'center' },
})
</script>

<template>
  <table role="presentation" :align="align" class="mt-5">
    <tr>
      <td><slot name="primary" /></td>
      <!-- The 12px gap is padding on the CELL, not a margin on the button,
           because Outlook drops margins on a nested table. -->
      <td v-if="$slots.secondary" class="pl-3"><slot name="secondary" /></td>
    </tr>
  </table>
</template>
