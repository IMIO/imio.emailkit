<template>
  <!--
    EVIDENCE TEMPLATE, not a real email.

    SPEC §3 states kit components emit theme tokens as
    `style="background-color: ${theme/primary_color}"`.
    This template does exactly that, and nothing else of note.

    Expected result (verified in Phase 0): Juice parses every style attribute as
    CSS, so the `{` opens a block and the closing `}` is swallowed -- AND CSS
    inlining silently stops for the WHOLE document. Compare the two <p> elements
    below: neither gets its Tailwind utilities inlined, even though they are
    plain and would inline fine on their own.
  -->
  <Layout>
    <p class="text-sm text-gray-600">this should inline, but will not</p>
    <a href="#" style="background-color: ${theme/primary_color}" class="text-sm font-bold text-white">literal token</a>
    <p class="text-base text-gray-700">neither will this</p>
  </Layout>
</template>
