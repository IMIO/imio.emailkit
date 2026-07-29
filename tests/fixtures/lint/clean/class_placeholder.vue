<script setup>
/**
 * CLEAN counterpart to `violating/class_placeholder.vue`.
 *
 * The classes are literal, and the runtime value that used to be spliced into
 * the class attribute is now a `style` set through `tal:attributes` -- which is
 * both what SPEC §3 rule 2 asks for and the only form that survives inlining.
 *
 * A `${...}` in an ordinary attribute such as `href` is fine and common; only
 * `class` and `style` are parsed by the CSS toolchain.
 */
</script>

<template>
  <KitMain>
    <p
      tal:attributes="style string:color: ${theme/primary_color}"
      class="m-0 text-sm"
    >${intro}</p>

    <a href="${cta_url}" class="text-imio-magenta">${cta_label}</a>
  </KitMain>
</template>
