<script setup>
/**
 * VIOLATING FIXTURE for `runtime-class`.
 *
 * Three ways to end up with a class name that exists nowhere in the source at
 * build time, so Tailwind never generates the utility and `css.purge` never
 * sees the reference. All three produce a class attribute in the output and no
 * CSS behind it.
 */
const tone = 'imio-pink-soft'
</script>

<template>
  <KitMain>
    <p tal:attributes="class string:m-0 text-sm ${tone_class}">${intro}</p>

    <table role="presentation" :class="'bg-' + tone">
      <tr><td class="p-4">${detail}</td></tr>
    </table>

    <table role="presentation" :class="`bg-${tone}`">
      <tr><td class="p-4">${detail}</td></tr>
    </table>
  </KitMain>
</template>
