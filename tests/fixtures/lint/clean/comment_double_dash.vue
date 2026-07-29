<script setup>
/**
 * CLEAN counterpart to `violating/comment_double_dash.vue`, and the fixture that
 * protects Outlook.
 *
 * The prose comment uses a semicolon. The three conditional comments below must
 * NOT be reported: they are load-bearing markup rather than commentary, the kit's
 * comment stripper deliberately keeps them, and the downlevel-revealed pair
 * (`<!--[if !mso]><!-->` ... `<!--<![endif]-->`) is full of hyphen runs by
 * construction. A lint that flagged those would be switched off within a day,
 * and `style-placeholder` would go with it.
 */
</script>

<template>
  <KitMain>
    <!-- The subject is translated Python-side; see SPEC §6.2. -->
    <!--[if mso]><table role="presentation" width="600"><tr><td><![endif]-->
    <p class="m-0 text-sm">${intro}</p>
    <!--[if mso]></td></tr></table><![endif]-->
    <!--[if !mso]><!--><p class="m-0 text-xs">${footnote}</p><!--<![endif]-->
  </KitMain>
</template>
