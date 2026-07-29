<template>
  <!--
    Second out-of-root kit component, so assumption (c) rests on more than a
    single-file fluke. Import-free, same reason as Button.vue.
    `role="presentation"` is one of SPEC §3's baked-in a11y defaults: the kit
    does it so authors never have to think about it.
  -->
  <table role="presentation" class="w-full rounded-lg bg-white p-6" data-kit-marker="KitPanel">
    <tr>
      <td class="p-6 text-base text-gray-700">
        <slot />
      </td>
    </tr>
  </table>
</template>
