<script setup>
/**
 * `KitButton` -- the bulletproof call-to-action.
 *
 * A single-cell table rather than a padded `<a>`: cell padding is the one form
 * of padding every mail client including Outlook honours, so no MSO spacer
 * hacks are needed.
 *
 * The `primary_color` theme token rides on `bgcolor`, not on `style`. A
 * Chameleon placeholder in a literal `style` attribute silently kills CSS
 * inlining for the whole document; `bgcolor` is never parsed as CSS, and it is
 * also the most widely supported way to colour a cell in mail. `primary_color`
 * is defined by the shell (`layouts/Main.vue`), so this component only works
 * inside it -- which is the only place it is meant to be used.
 *
 * Import-free: a kit directory inside a Python egg has no `node_modules`
 * ancestor. `defineProps` is a compiler macro, not an import.
 */
defineProps({
  /** Destination. A Chameleon placeholder is fine here -- `href` is not CSS. */
  href: { type: String, required: true },
  /** Horizontal placement of the button block: `left`, `center` or `right`. */
  align: { type: String, default: 'left' },
})
</script>

<template>
  <table role="presentation" :align="align" class="my-4">
    <tr>
      <td bgcolor="${primary_color}" class="rounded-md px-6 py-3 text-center">
        <a :href="href" class="font-display text-base font-bold text-imio-white no-underline">
          <slot />
        </a>
      </td>
    </tr>
  </table>
</template>
