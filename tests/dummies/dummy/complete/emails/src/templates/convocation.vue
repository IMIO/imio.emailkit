<script setup>
/**
 * `dummy.complete:convocation` -- one template that uses the whole kit catalog.
 *
 * Meant to be copied from: every kit component appears once.
 *
 * Context keys (see `tests/fixtures/convocation.py`): title, when (ISO date
 * string), place, rows (list of {title, decision}), cta_url (optional),
 * cta_label.
 *
 * Rules:
 * 1. `${python: format_date(when)}`, never `${format_date(when)}`: a TAL
 *    path expression cannot call a function.
 * 2. `tal:repeat` on the author's own `<tr>`, never on the data-table
 *    component (attribute fallthrough would land it on the wrong element).
 * 3. No `${...}` in a literal `class` or `style` attribute: it breaks CSS
 *    inlining. Runtime styling uses `tal:attributes`, colours use `bgcolor`.
 * 4. `i18n:domain` on the author's own element when the msgid belongs to the
 *    add-on's catalog, since the shell's own domain would otherwise apply.
 * 5. No two consecutive hyphens in any comment: Chameleon cannot parse it.
 */
</script>

<template>
  <KitMain>
    <p
      class="m-0 mb-4 text-sm leading-6 text-imio-black"
      i18n:domain="dummy.complete"
      i18n:translate="email_convocation_intro"
    >You are convened to the session below.</p>

    <KitPanel tone="accent">
      <strong>${python: format_date(when)}</strong> &mdash; ${place}
    </KitPanel>

    <KitDataTable>
      <template #head>
        <th scope="col" class="border border-solid border-imio-grey-border p-2 text-left text-sm">Point</th>
        <th scope="col" class="border border-solid border-imio-grey-border p-2 text-left text-sm">Decision</th>
      </template>
      <tr tal:repeat="row rows">
        <td class="border border-solid border-imio-grey-border p-2 text-sm">${row/title}</td>
        <td class="border border-solid border-imio-grey-border p-2 text-sm">${row/decision}</td>
      </tr>
    </KitDataTable>

    <!--
      Three rows, to exercise the `tr + tr` row-separator rule: a single
      row would render the same with or without it.
    -->
    <KitCard>
      <template #overline>
        <span i18n:domain="dummy.complete" i18n:translate="email_convocation_card">Session</span>
      </template>
      <template #title>${place}</template>
      <KitDataList>
        <KitDataRow label-width="120">
          <template #label>Date</template>
          ${python: format_date(when)}
        </KitDataRow>
        <KitDataRow label-width="120">
          <template #label>Place</template>
          ${place}
        </KitDataRow>
        <KitDataRow label-width="120">
          <template #label>Points</template>
          ${python: len(rows)}
        </KitDataRow>
      </KitDataList>
    </KitCard>

    <!-- `inline` drops each button's own top margin; the group supplies it once. -->
    <div tal:condition="cta_url | nothing">
      <KitButtonGroup align="center">
        <template #primary>
          <KitButton href="${cta_url}" inline>${cta_label}</KitButton>
        </template>
        <template #secondary>
          <KitButton href="${cta_url}" variant="outline" inline>
            <span i18n:domain="dummy.complete" i18n:translate="email_convocation_decline">Decline</span>
          </KitButton>
        </template>
      </KitButtonGroup>
    </div>
  </KitMain>
</template>
