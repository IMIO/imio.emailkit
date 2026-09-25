<script setup>
/**
 * `KitButton` renders a call-to-action as a single-cell table with a
 * block anchor, so the whole coloured rectangle is a click target.
 *
 * Props: `href` (required), `align` (`left`/`center`/`right`), `variant`
 * (`solid` default, or `outline`), `inline` (drop the top margin, for use
 * inside `KitButtonGroup`).
 *
 * Mail-client traps
 * ------------------
 * - `mso-padding-alt` repeats the padding for Word's renderer, which
 *   applies neither padding nor `display: block` to an `<a>`.
 * - `primary_color` rides on `bgcolor`, never `style`: a Chameleon
 *   placeholder inside `style` silently kills CSS inlining for the whole
 *   document. Only the solid variant sets it; an outline cell has no fill
 *   to paint.
 * - Outlook on Windows renders the button square: a VML `<v:roundrect>`
 *   needs a fixed pixel width, which cannot be hardcoded since the label
 *   is a translated slot of variable length.
 * - `variant` is resolved at build time, so the class strings stay
 *   literal for Tailwind's scanner; a runtime-computed class styles
 *   nothing.
 */
const props = defineProps({
  href: { type: String, required: true },
  align: { type: String, default: 'left' },
  variant: { type: String, default: 'solid' },
  inline: { type: Boolean, default: false },
})

const isOutline = props.variant === 'outline'

/** Whole class names, never fragments: a class built by concatenation
 * does not exist for Tailwind's scanner to find. The outline variant's
 * `mso-padding-alt` values are 2px smaller, since its own 2px rule makes
 * up the difference. */
const cellClass = isOutline
  ? 'rounded-[12px] border-2 border-solid border-imio-magenta-dark text-center [mso-padding-alt:11px_24px]'
  : 'rounded-[12px] text-center [mso-padding-alt:13px_26px]'

/** `rounded-[10px]` inside the outline variant's 12px cell: a border
 * radius is measured on the outside of the border, so the inner box must
 * be 2px tighter to sit flush against the rule. */
const labelClass = isOutline
  ? 'block rounded-[10px] px-6 py-[11px] text-base font-bold leading-tight text-imio-magenta-dark no-underline'
  : 'block rounded-[12px] px-[26px] py-[13px] text-base font-bold leading-tight text-imio-white no-underline'
</script>

<template>
  <table role="presentation" :align="align" :class="inline ? '' : 'mt-5'">
    <tr>
      <td v-if="isOutline" :class="cellClass">
        <a :href="href" :class="labelClass"><slot /></a>
      </td>
      <td v-else bgcolor="${primary_color}" :class="cellClass">
        <a :href="href" :class="labelClass"><slot /></a>
      </td>
    </tr>
  </table>
</template>
