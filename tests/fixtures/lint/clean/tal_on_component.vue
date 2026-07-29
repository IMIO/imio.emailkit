<script setup>
/**
 * CLEAN counterpart to `violating/tal_on_component.vue`.
 *
 * Same two effects, expressed the way SPEC §3 rule 1 asks for: the conditional
 * lives on the author's own `<div>`, and the translatable label lives on a plain
 * `<span>` inside the component's slot. `tal:` and `i18n:` on lowercase tags are
 * exactly what the rule wants and must never be reported.
 */
</script>

<template>
  <KitMain>
    <div tal:condition="warning">
      <KitPanel>
        <p class="m-0 text-sm">${warning}</p>
      </KitPanel>
    </div>

    <KitButton href="${cta_url}" align="center">
      <span i18n:translate="cta_label" tal:omit-tag="">Open</span>
    </KitButton>

    <KitDataTable>
      <template #head>
        <th scope="col" i18n:translate="col_title">Title</th>
      </template>
      <tr tal:repeat="row rows">
        <td class="p-2 text-sm">${row/title}</td>
      </tr>
    </KitDataTable>
  </KitMain>
</template>
