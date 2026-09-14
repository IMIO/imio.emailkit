<script setup>
/**
 * `KitButtonGroup` -- two actions on one row, as the v2 notification model draws
 * them ("Relire et publier" beside "Renvoyer").
 *
 * Before this component two `KitButton`s stacked, because each is its own table
 * and two tables do not share a line in mail. The fix is a row whose cells hold
 * them, which is exactly the markup the mockup writes by hand; putting it in a
 * component is what keeps the author from writing `<td>` soup for the one layout
 * that needs it.
 *
 * ---------------------------------------------------------------------------
 * Two named slots, not one
 * ---------------------------------------------------------------------------
 * `#primary` and `#secondary` rather than a single default slot the children
 * fill. A default slot would drop both buttons into ONE cell, because a
 * component cannot wrap children it has not been told about -- and the gap
 * between them then has nowhere to live. Naming them also states the design's
 * own rule in the API: the pair is one primary action with an alternative, never
 * two equal choices, which is why `KitButton`'s `outline` variant exists.
 *
 * `#secondary` is optional. With one slot filled this renders a single centred
 * button, the same thing a bare `KitButton` would.
 *
 * ---------------------------------------------------------------------------
 * On a phone
 * ---------------------------------------------------------------------------
 * The two cells stay side by side. At 600 px the pair is well under the card's
 * width, and `sm:` cannot turn a `<td>` into a block in Outlook anyway. Two
 * short labels are the contract; a mail whose actions do not fit on one line
 * wants two stacked `KitButton`s and not this component.
 */
defineProps({
  /** Horizontal placement of the row: `left`, `center` or `right`. */
  align: { type: String, default: 'center' },
})
</script>

<template>
  <table role="presentation" :align="align" class="mt-5">
    <tr>
      <td><slot name="primary" /></td>
      <!-- 12 px, the mockup's own `padding-left` on the second action's cell.
           On the CELL rather than as a margin on the button, because Outlook
           drops margins on a nested table. -->
      <td v-if="$slots.secondary" class="pl-3"><slot name="secondary" /></td>
    </tr>
  </table>
</template>
