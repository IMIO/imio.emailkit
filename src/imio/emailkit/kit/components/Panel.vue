<script setup>
/**
 * `KitPanel` -- the callout: a bordered block for the one condition attached to
 * the message. How long the link lasts, what the author asked you to check,
 * what happens if you ignore this.
 *
 * The shell already provides the white card and `KitCard` already provides the
 * subject, so a panel is neither layout nor payload. It is the sentence the
 * reader must not skim past, and in the v2 design it is drawn as an outline
 * rather than a fill -- a light box on the white card, with an optional overline
 * naming what the condition is about:
 *
 *     <KitPanel tone="accent">
 *       <template #overline>
 *         <span i18n:translate="email_callout_validity" tal:omit-tag="">Link validity</span>
 *       </template>
 *       <p class="m-0 text-sm leading-[22px] text-imio-black">…</p>
 *     </KitPanel>
 *
 * `tal:` may not go on the component, so a translated overline
 * is a `<span tal:omit-tag="">` inside the slot.
 *
 * ---------------------------------------------------------------------------
 * The two tones
 * ---------------------------------------------------------------------------
 * `accent` is the default now, and that is a change from the pre-v2 panel. In
 * the v2 design every callout is drawn in pink: the callout IS the emphasis
 * device, and a template that reaches for one has already decided the reader
 * must not miss what is in it. `neutral` remains for the second callout in a
 * mail that genuinely has two, where a matching pair of pink boxes would cancel
 * each other out.
 *
 * `tone` is resolved at BUILD time, so the class strings are literal in the
 * compiled output and Tailwind's scanner and `css.purge` both see them. A
 * runtime-computed class would style nothing.
 *
 * ---------------------------------------------------------------------------
 * No fill, and what that costs in dark mode
 * ---------------------------------------------------------------------------
 * The v2 callout has a border and no background, so there is no `data-dark`
 * SURFACE hook here: there is no fill to flip. The border colour is a brand
 * value that reads correctly on both the light card and the dark one, and the
 * text inside is the shell's body copy, which `[data-dark="body"]` already
 * recolours.
 *
 * The overline is the exception, and it carries `data-dark="accent"`. #b3004b on
 * a dark surface is about 2:1; without the hook the dark block's body colour
 * would win and the overline would go grey, taking the last brand accent out of
 * the content well. See `kit/tailwind.css`.
 *
 * Import-free, like every kit component.
 */
const props = defineProps({
  /** `accent` (default) or `neutral`. */
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
