<script setup>
/**
 * CLEAN counterpart to `violating/style_placeholder.vue`.
 *
 * Two sanctioned forms, both of which must stay silent:
 *
 *   1. `tal:attributes="style string:..."` -- the amended sanctioned form. The
 *      placeholder is in a TAL expression, so juice never parses it as CSS.
 *   2. `bgcolor="${...}"` -- what the kit actually uses for background colours,
 *      because `bgcolor` is never parsed as CSS at all and is the most reliable
 *      way to colour a cell in mail.
 *
 * A literal `style` attribute with no placeholder in it is also fine, and the
 * hidden preheader div is the kit's own example of one.
 */
</script>

<template>
  <KitMain>
    <table role="presentation" class="w-full">
      <tr>
        <td
          tal:attributes="style string:background-color: ${theme/primary_color}"
          class="p-4"
        >${intro}</td>
      </tr>
      <tr>
        <td bgcolor="${primary_color}" class="h-[3px] text-[0px] leading-[3px]">&zwj;</td>
      </tr>
    </table>

    <div style="display: none">${preheader}</div>
  </KitMain>
</template>
