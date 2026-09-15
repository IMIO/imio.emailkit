<script setup>
/**
 * VIOLATING FIXTURE for `tal-on-component`.
 *
 * Both components below compile, render, and put the attribute on whichever
 * element the kit happens to use as that component's root. The author cannot
 * see which one from here, and the kit is free to change it.
 */
</script>

<template>
  <KitMain>
    <KitPanel tal:condition="warning">
      <p class="m-0 text-sm">${warning}</p>
    </KitPanel>

    <KitButton
      href="${cta_url}"
      i18n:attributes="title cta_title"
      align="center"
    >
      <span i18n:translate="cta_label" tal:omit-tag="">Open</span>
    </KitButton>
  </KitMain>
</template>
