<script setup>
/**
 * `KitPanel` renders a callout: a bordered, unfilled box for the one
 * condition attached to the message (a deadline, a check, a consequence).
 *
 * Prop: `tone` (`accent` default, pink; or `neutral`, for a second
 * callout in a mail that has two). Slots: `overline`, default (body).
 *
 * Mail-client traps
 * ------------------
 * - `tone` is resolved at build time, so the class strings stay literal
 *   in the compiled output; a runtime-computed class styles nothing.
 * - No `data-dark` surface hook: there is no fill to flip. The overline
 *   is the exception (`data-dark="accent"`): without it, the dark
 *   block's body colour would win and the overline would go grey.
 */
const props = defineProps({
  tone: { type: String, default: 'accent' },
})

const TONES = {
  accent: 'border-imio-pink-soft',
  neutral: 'border-imio-grey-border',
}

const toneClass = TONES[props.tone] || TONES.accent
</script>

<template>
  <table role="presentation" class="mt-5 w-full rounded-[12px] border-2 border-solid" :class="toneClass">
    <tr>
      <td class="px-5 py-4">
        <p v-if="$slots.overline" class="m-0 mb-1 font-display text-xs font-bold uppercase leading-4 tracking-[1.2px] text-imio-magenta-dark" data-dark="accent">
          <slot name="overline" />
        </p>
        <slot />
      </td>
    </tr>
  </table>
</template>
