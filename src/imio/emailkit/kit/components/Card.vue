<script setup>
/**
 * `KitCard` -- the rail card: the block that holds what the mail is *about*.
 *
 * A tinted panel with a 6 px coloured rail down its left edge, and the design's
 * one structural idea. A transactional mail is nearly always "here is a thing,
 * here is what to do about it"; the rail card is the thing. The content submitted
 * for review, the account that was created, the error that fired. Everything
 * outside it is address, instruction or footer.
 *
 *     <KitCard>
 *       <template #overline>
 *         <span i18n:translate="email_card_kind" tal:omit-tag="">News item</span>
 *       </template>
 *       <template #title>${item_title}</template>
 *       <p class="m-0 text-sm leading-[22px] text-imio-grey-dark">${item_description}</p>
 *       <KitDataList>
 *         <tr>…</tr>
 *       </KitDataList>
 *     </KitCard>
 *
 * `tal:` may not go on the component, so a translated overline
 * is a `<span tal:omit-tag="">` inside the slot, exactly as for `KitPill`.
 *
 * ---------------------------------------------------------------------------
 * Why the rail is a table cell and not a border
 * ---------------------------------------------------------------------------
 * `border-left: 6px solid` would be one declaration instead of a whole column,
 * and it is what a web page would use. It is not reliable in mail: Outlook
 * renders a table border through Word's box model and collapses or thickens it,
 * and a border cannot carry a `bgcolor` attribute, which is how a runtime colour
 * has to travel (see the theme-token note in `layouts/Main.vue`). A 6 px cell
 * with `bgcolor="${primary_color}"` is a filled rectangle in every client, and
 * it takes the site's own colour for free.
 *
 * The `&nbsp;` in that cell is load-bearing: Outlook collapses an empty table
 * cell and the rail disappears. `font-size: 0` and `line-height: 0` keep the
 * character from adding height.
 *
 * ---------------------------------------------------------------------------
 * The radius, and why only three corners are rounded
 * ---------------------------------------------------------------------------
 * The rail is square on its left edge and the card is rounded on its right, so
 * the outer border and the inner fill each round only the two corners the rail
 * does not touch. Rounding all four would leave a visible notch where the square
 * rail meets a rounded fill. The inner radius is 10 px against the outer 12 px
 * for the usual reason: concentric corners look wrong when the radii are equal.
 *
 * `data-dark="raised"` is the shell's dark-mode hook (see `kit/tailwind.css`).
 * Without it the card keeps its light tint on a dark surface while the shell has
 * already flipped the text to light, i.e. light on light. The rail keeps its
 * colour in both modes; it is what tells the card apart from the surface once
 * the tints have converged.
 *
 * Import-free, like every kit component.
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
