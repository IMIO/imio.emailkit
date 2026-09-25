<script setup>
/**
 * `KitCard` renders the rail card: a tinted panel with a 6px coloured
 * rail down its left edge, for the one thing a transactional mail is
 * about.
 *
 * Slots: `overline`, `title`, default (body). `tal:` may not go on the
 * component, so a translated overline is a `<span tal:omit-tag="">`
 * inside the slot.
 *
 * Mail-client traps
 * ------------------
 * - The rail is a `bgcolor` cell, not `border-left`: Outlook renders a
 *   table border through Word's box model and collapses or thickens it,
 *   and a border cannot carry a runtime `bgcolor`.
 * - The `&nbsp;` in that cell is load-bearing: Outlook collapses an empty
 *   table cell and the rail disappears.
 * - `data-dark="raised"` is required: without it the card keeps its
 *   light tint while the shell flips the text to light, giving light
 *   text on a light tint.
 */
</script>

<template>
  <table role="presentation" class="mt-5 w-full rounded-r-[12px] border-2 border-solid border-imio-grey-border">
    <tr>
      <td width="6" bgcolor="${primary_color}" class="w-[6px] text-[0px] leading-[0]">&nbsp;</td>
      <td class="p-0">
        <table role="presentation" class="w-full rounded-r-[10px] bg-imio-grey-bg" data-dark="raised">
          <tr>
            <td class="px-[22px] pb-5 pt-5">
              <p v-if="$slots.overline" class="m-0 mb-2 font-display text-xs font-bold uppercase leading-4 tracking-[1.2px] text-imio-magenta-dark" data-dark="accent">
                <slot name="overline" />
              </p>
              <p v-if="$slots.title" class="m-0 font-display text-lg font-bold leading-[25px] text-imio-black">
                <slot name="title" />
              </p>
              <slot />
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</template>
