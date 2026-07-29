<script setup>
/**
 * VIOLATING FIXTURE for `style-placeholder` (Phase 0 caveat A1) -- the most
 * damaging mistake in this whole pipeline, and the one SPEC §3 originally
 * prescribed before it was measured.
 *
 * Juice parses every `style` attribute as CSS. The `{` opens a block, the
 * closing `}` is eaten, and CSS inlining stops for the ENTIRE document: the
 * spike template went from 31 inline styles to 6 because of one attribute like
 * the one below. The build exits 0 and the browser preview looks plausible.
 */
</script>

<template>
  <KitMain>
    <table role="presentation" class="w-full">
      <tr>
        <td style="background-color: ${theme/primary_color}" class="p-4">${intro}</td>
      </tr>
    </table>
  </KitMain>
</template>
