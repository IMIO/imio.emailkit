<script setup>
/**
 * `KitPanel` -- a tinted callout inside the shell's white content well.
 *
 * The shell already provides the white card, so a panel is for emphasis, not
 * for layout. Two tones only: `neutral` for supporting detail, `accent` for the
 * one thing the reader must not miss. Magenta is high-signal at iMio and is
 * used sparingly by design.
 *
 * `tone` is resolved at *build* time, so the class strings are literal in the
 * compiled output and Tailwind's scanner and `css.purge` both see them. This is
 * not a runtime-computed class, which SPEC §3 rule 2 forbids.
 *
 * `data-dark="surface"` is the shell's dark-mode hook (see `kit/tailwind.css`).
 * Without it a panel keeps its light fill on a dark card while the shell has
 * already flipped the text to light, i.e. light on light. Both tones take the
 * same dark fill; the accent tone keeps its magenta border, which is what
 * carries the distinction in the first place.
 *
 * Import-free, like every kit component.
 */
const props = defineProps({
  /** `neutral` (default) or `accent`. */
  tone: { type: String, default: 'neutral' },
})

const TONES = {
  neutral: 'bg-imio-grey-bg border-imio-grey-border',
  accent: 'bg-imio-pink-soft border-imio-magenta',
}

const toneClass = TONES[props.tone] || TONES.neutral
</script>

<template>
  <table role="presentation" class="my-4 w-full border border-solid" :class="toneClass" data-dark="surface">
    <tr>
      <td class="p-4 text-sm leading-6 text-imio-black">
        <slot />
      </td>
    </tr>
  </table>
</template>
