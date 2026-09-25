<script setup>
/**
 * `KitPill` renders the status badge in the shell's white band: a white
 * pill with a coloured icon disc, since a tinted fill would fight the
 * head artwork behind it. Goes only in `KitMain`'s `pill` slot.
 *
 * Prop: `tone`, each a lookup of one icon file name:
 *
 *   info     (default) blue disc,   white glyph; something to review
 *   success  green disc,  dark glyph;  something that now works
 *   warning  yellow disc, dark glyph;  something with a deadline
 *   danger   red disc,    white glyph; something broken
 *
 * `info` and `danger` are not in the iMio palette; both are placeholder
 * values in `browser/static/`.
 *
 * Mail-client traps
 * ------------------
 * - The icon is a 14px PNG, not SVG: mail clients do not render SVG
 *   reliably, and a client cannot recolour an image, hence one file per
 *   tone.
 * - The disc is baked into the PNG rather than a coloured cell behind a
 *   glyph: Outlook squares any `border-radius`.
 * - `alt=""` and `tal:condition="asset_base"`: a missing request leaves a
 *   bold label on white rather than a broken-image icon.
 * - `rounded-[400px]`, not `rounded-full`: Tailwind 4 resolves
 *   `--radius-full` to a literal value no mail client parses.
 * - The tone lookup and its class names are resolved at build time: a
 *   runtime file name would have no `tal:condition` to hang the
 *   missing-asset case on, and a name built by concatenation is invisible
 *   to Tailwind's scanner.
 */
const props = defineProps({
  tone: { type: String, default: 'info' },
})

const TONES = {
  info: { icon: 'pill-info.png' },
  success: { icon: 'pill-success.png' },
  warning: { icon: 'pill-warning.png' },
  danger: { icon: 'pill-danger.png' },
}

const tone = TONES[props.tone] || TONES.info

const FILL = 'rounded-[400px] bg-imio-white py-1.5 pl-[11px] pr-[14px]'
const LABEL = 'font-display text-xs font-bold whitespace-nowrap text-imio-black'

/** Single-quoted, so `${asset_base}` reaches the output as a placeholder
 * instead of being interpolated here. */
const iconSrc = '${asset_base}/' + tone.icon
</script>

<template>
  <table role="presentation" align="right">
    <tr>
      <td bgcolor="#ffffff" :class="FILL">
        <table role="presentation">
          <tr>
            <td tal:condition="asset_base" class="pr-[7px] text-[0px] leading-[0]">
              <img :src="iconSrc" alt="" width="14" height="14" class="block">
            </td>
            <td :class="LABEL">
              <slot />
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</template>
