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
 *   title      -- the banner heading. Read by the SHELL, not by this file: the
 *                 v2 layout defines `title` on `<html>` and renders the banner
 *                 itself, so a template whose title is runtime data writes no
 *                 markup for it at all.
 *   subtitle   -- optional; the line under the banner heading, same deal.
 *   intro      -- lead paragraph
 *   body_html  -- optional; injected unescaped by the shell (§3 rule 4)
 *   cta_url    -- optional; renders the button when present
 *   cta_label  -- button label, when `cta_url` is set
 *
 * The pill is `info` and its label is a msgid rather than context data, because
 * a runtime tone cannot work: `KitPill` resolves its fill to a literal class at
 * build time (SPEC §3 rule 2). A consumer that needs to say something more
 * specific than "notification" writes its own template with its own pill, which
 * is a two-line diff on this file.
 */
</script>

<template>
  <KitMain>
    <template #pill>
      <KitPill tone="info">
        <span i18n:translate="email_pill_notification" tal:omit-tag="">Notification</span>
      </KitPill>
    </template>

    <p class="m-0 text-[15px] leading-6 text-imio-grey-dark">${intro}</p>

    <div tal:condition="cta_url | nothing">
      <KitButton href="${cta_url}" align="center">${cta_label}</KitButton>
    </div>
  </KitMain>
</template>
