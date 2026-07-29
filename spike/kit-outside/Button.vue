<script setup>
// Kit component stub. Lives OUTSIDE the Maizzle project root, to prove
// SPEC §10.1 `kit-mode = path`. Deliberately import-free: a directory inside a
// Python egg has no `node_modules` ancestor for Vite to walk up to.
defineProps({
  href: { type: String, required: true },
})
</script>

<template>
  <table role="presentation" class="w-full">
    <tr>
      <td class="rounded-lg px-7 py-3 text-sm font-bold text-white">
        <!--
          SPEC §3 theme-token model: kit components emit tokens as literal inline
          styles containing a Chameleon placeholder. Under test here is whether
          `css.inline` (Juice) preserves a style attribute whose value is not
          valid CSS. If it strips it, §3's mechanism needs the `tal:attributes`
          form instead -- see the sibling test in emails/spike.vue.
        -->
        <a
          :href="href"
          tal:attributes="style string:background-color: ${theme/primary_color}"
          class="text-sm font-bold text-white no-underline"
          data-kit-marker="KitButton"
        >
          <slot />
        </a>
      </td>
    </tr>
  </table>
</template>
