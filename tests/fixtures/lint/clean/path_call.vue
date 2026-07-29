<script setup>
/**
 * CLEAN counterpart to `violating/path_call.vue`.
 *
 * The `python:` prefix is the whole fix: it makes the contents an expression
 * rather than a path. Plain paths, `string:` and `structure` must all stay
 * silent, and so must the JavaScript template literal below -- a `${...}` inside
 * a `<script>` block belongs to Node, not to Chameleon.
 */
const config = useConfig()
const stylesheet = `@import "${config.emailkit.cssEntry}";`
</script>

<template>
  <KitMain>
    <p class="m-0 text-sm">${python: format_date(meeting_date)}</p>
    <p class="m-0 text-xs">${python: format_number(total, 2)}</p>
    <p class="m-0 text-xs">${meeting/title}</p>
    <p class="m-0 text-xs">${python:member.getProperty('fullname')}</p>
    <a href="${python: portal_url + '/dashboard'}" class="text-imio-magenta">${cta_label}</a>
    <style v-html="stylesheet"></style>
  </KitMain>
</template>
