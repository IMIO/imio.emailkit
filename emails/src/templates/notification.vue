<script setup>
/**
 * A generic transactional notification, and the one template
 * `imio.emailkit` registers through its own entry point.
 *
 * A flat context from `render()`, with no `options/` and no `python:`
 * anywhere: the shape consumer addons copy.
 *
 * Context it expects:
 *   title      the banner heading, read by the shell.
 *   subtitle   optional; the line under the banner heading, same deal.
 *   intro      lead paragraph
 *   body_html  optional; injected unescaped by the shell
 *   cta_url    optional; renders the button when present
 *   cta_label  button label, when `cta_url` is set
 *
 * The pill's label is a msgid, not context data: a runtime tone cannot
 * work, since `KitPill` resolves its fill to a literal class at build
 * time. A consumer needing a more specific label writes its own template
 * with its own pill.
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
