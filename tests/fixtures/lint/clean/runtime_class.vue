<script setup>
/**
 * CLEAN counterpart to `violating/runtime_class.vue`, and the fixture that keeps
 * this rule honest.
 *
 * Runtime styling goes through `tal:attributes="style ..."` with literal values,
 * which is what SPEC §3 rule 2 prescribes.
 *
 * The two `:class` bindings must NOT be reported. Vue resolves them at *build*
 * time and every complete utility name is present verbatim in this file, so
 * Tailwind's content scanner finds them and the compiled output carries a
 * literal class attribute. The kit's own `Panel.vue` picks a tone exactly like
 * this; reporting it would make the rule a false alarm on correct kit code, and
 * a lint that cries wolf gets switched off.
 */
const TONES = {
  neutral: 'bg-imio-grey-bg border-imio-grey-border',
  accent: 'bg-imio-pink-soft border-imio-magenta',
}
const toneClass = TONES.neutral
const highlight = false
</script>

<template>
  <KitMain>
    <p
      tal:attributes="style string:color: ${theme/primary_color}"
      class="m-0 text-sm"
    >${intro}</p>

    <table role="presentation" class="border border-solid" :class="toneClass">
      <tr><td class="p-4">${detail}</td></tr>
    </table>

    <table
      role="presentation"
      :class="highlight ? 'bg-imio-pink-soft' : 'bg-imio-grey-bg'"
    >
      <tr><td class="p-4">${detail}</td></tr>
    </table>
  </KitMain>
</template>
