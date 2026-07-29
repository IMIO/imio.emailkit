<script setup>
/**
 * The one template this throwaway addon ships.
 *
 * Written to pass the authoring lint clean, so that `bin/check-emails` has a
 * package whose gate 2 is green ; a lint with no passing fixture proves nothing.
 *
 * Context it expects:
 *   title  ; heading text
 *   intro  ; lead paragraph
 */
</script>

<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>

    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>
  </KitMain>
</template>
