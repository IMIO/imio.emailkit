<script setup>
/**
 * A generic transactional notification, and the one template `imio.emailkit`
 * registers through SPEC §4's entry point for itself.
 *
 * This is the template that speaks the *normal* dialect: a flat context from
 * §6.1 `render()`, with no `options/` and no `python:` anywhere. It is the shape
 * consumer addons copy, and it is what the discovery, `render()` and golden-file
 * tests exercise.
 *
 * Context it expects:
 *   title      -- heading text
 *   intro      -- lead paragraph
 *   body_html  -- optional; injected unescaped by the shell (§3 rule 4)
 *   cta_url    -- optional; renders the button when present
 *   cta_label  -- button label, when `cta_url` is set
 */
</script>

<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>

    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>

    <div tal:condition="cta_url | nothing">
      <KitButton href="${cta_url}" align="center">${cta_label}</KitButton>
    </div>
  </KitMain>
</template>
