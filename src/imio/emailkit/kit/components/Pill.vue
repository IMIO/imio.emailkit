<script setup>
/**
 * `KitPill` -- the status badge in the shell's white band.
 *
 * One pill per message, top right, saying in two words what kind of message
 * this is: something to review, a new account, a link that expires. It is the
 * first thing the eye lands on after the logo, and it is the only part of the
 * design that changes colour by meaning rather than by brand.
 *
 * THE PILL IS WHITE, AND THE COLOUR IS IN THE ICON. v3 puts the head artwork
 * behind this band, so a pill now sits on magenta rather than on white, and a
 * tinted fill there is either washed out (the pale `info` blue) or a second
 * colour fighting the brand (the green and the yellow). White reads on every
 * part of the cut, and the tone moves into a coloured disc under the glyph.
 * That is the design's own answer: `pill-info-solid.png` in the v3 assets is a
 * blue disc with a white `i`, and the other three are drawn to match it.
 *
 * Goes in `KitMain`'s `pill` slot and nowhere else:
 *
 *     <KitMain>
 *       <template #pill>
 *         <KitPill tone="success">
 *           <span i18n:translate="email_pill_new_account" tal:omit-tag="">New account</span>
 *         </KitPill>
 *       </template>
 *       …
 *     </KitMain>
 *
 * A `tal:` attribute may not go on the component, which is why
 * the label above is wrapped in a `<span tal:omit-tag="">` rather than written
 * as `<KitPill i18n:translate="…">`.
 *
 * ---------------------------------------------------------------------------
 * The tones
 * ---------------------------------------------------------------------------
 * Four. Since the fill left the markup, a tone is nothing but a file name, so
 * this is now a lookup of one value; it still resolves at BUILD time, because a
 * runtime file name would have no `tal:condition` to hang the missing-asset case
 * on, and a runtime class is ruled out either way.
 *
 *   info     blue disc,   white glyph  -- something to read or review
 *   success  green disc,  dark glyph   -- something that now exists and works
 *   warning  yellow disc, dark glyph   -- something with a deadline
 *   danger   red disc,    white glyph  -- something broken
 *
 * The dark/white split is not decoration. Green #00e667 and yellow #e6da00 are
 * light fills that carry #1c1c1c and never white; blue and red are dark enough
 * for a white glyph. That is the same rule the labels used to follow, applied to
 * the one place the colour still lives.
 *
 * TWO OF THE FOUR DISC COLOURS ARE NOT CHARTE COLOURS. The iMio palette has
 * `positive` and `warning` and nothing else semantic: no blue at all, and a
 * `negative` that is the dark magenta. The blue is #1b6c9c, which is the design's
 * own value from `pill-info-solid.png`; the red is #c8102e, inherited from the v2
 * design. Both are awaiting sign-off from communication, and the substitution
 * stays mechanical because it is now four files in `browser/static/` and no
 * markup at all. See the note in `kit/tailwind.css`.
 *
 * ---------------------------------------------------------------------------
 * The icon, and why it can be absent
 * ---------------------------------------------------------------------------
 * A 14 px PNG, from the `++resource++imio.emailkit` directory, drawn at 48 px so
 * it is better than 2x. PNG rather than SVG because mail clients do not render
 * SVG reliably; one file per tone rather than one recoloured file because a mail
 * client cannot recolour anything.
 *
 * THE DISC IS BAKED INTO THE PNG rather than drawn as a coloured cell behind a
 * glyph. A cell would keep the colour when a client blocks images, which is the
 * real argument for it, but it costs a `border-radius` Outlook squares into a
 * coloured box, and a 14 px glyph centred in a 22 px cell is three more nested
 * tables to get wrong. The design ships the composited form, and a PNG renders
 * identically everywhere it renders at all.
 *
 * It is `alt=""` -- purely decorative, since the label next to it says the same
 * thing in words -- and `tal:condition="asset_base"`, because `asset_base` is
 * empty whenever the render had no request to build an absolute URL from. See
 * the `asset_base` section of `layouts/Main.vue`.
 *
 * What a missing icon costs is larger than it was: the pill used to degrade to a
 * coloured fill with a bold label, and it now degrades to a bold label on white,
 * with no colour anywhere. That is the accepted cost of the white pill. The
 * label is words and was always the part carrying the meaning; the tone was only
 * ever the part carrying it FASTER.
 *
 * Import-free: a kit directory inside a Python egg has no `node_modules`
 * ancestor. `defineProps` is a compiler macro, not an import.
 */
const props = defineProps({
  /** `info` (default), `success`, `warning` or `danger`. */
  tone: { type: String, default: 'info' },
})

/**
 * Whole utility names, never fragments. Tailwind's content scanner reads this
 * file including the `<script>` block, so a complete name written here is
 * generated; `'bg-imio-' + props.tone` would generate nothing at all and style
 * nothing, silently, which is what the lint's `runtime-class` rule is for.
 * Bound as an array below for the same reason: an array literal picks whole
 * names, a template literal assembles one.
 */
const TONES = {
  info: { icon: 'pill-info.png' },
  success: { icon: 'pill-success.png' },
  warning: { icon: 'pill-warning.png' },
  danger: { icon: 'pill-danger.png' },
}

const tone = TONES[props.tone] || TONES.info

/*
 * `rounded-[400px]`, not `rounded-full`. Tailwind 4 defines `--radius-full` as
 * `calc(infinity * 1px)`, which Maizzle's CSS pipeline resolves to a literal
 * `3.40282e38px` -- a value no mail client parses, so the pill comes out square.
 * A large finite radius is the standard email workaround and is what the v2
 * design specifies.
 */
const FILL = 'rounded-[400px] bg-imio-white py-1.5 pl-[11px] pr-[14px]'
const LABEL = 'font-display text-xs font-bold whitespace-nowrap text-imio-black'

/**
 * The icon's `src`. `asset_base` is a Chameleon name the shell defines on
 * `<html>`, so it is in scope for every element of the compiled document; this
 * is a single-quoted JS string precisely so that `${asset_base}` reaches the
 * output as a placeholder rather than being interpolated here.
 */
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
