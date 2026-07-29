<script setup>
/**
 * `dummy.complete:convocation` -- one template that uses the whole kit catalog.
 *
 * Deliberately the busiest template in the repository, because it is the one a
 * consumer copies from. Every kit component appears once, and so does every
 * runtime construct that has a rule attached to it.
 *
 * Context keys (see `tests/fixtures/convocation.py`):
 *   title     -- heading
 *   when      -- ISO date string, formatted through the locale helper
 *   place     -- where the session sits
 *   rows      -- list of {title, decision} mappings for the data table
 *   cta_url   -- optional; the button only renders when set
 *   cta_label -- button label
 *
 * The five rules this file demonstrates, all of them from failures that produced
 * a **successful build**:
 *
 * 1. `${python: format_date(when)}`, never `${format_date(when)}`. A TAL *path*
 *    expression cannot call a function; the path form raises `Invalid variable
 *    name` at render time.
 * 2. `tal:repeat` on the author's own `<tr>`, never on `<KitDataTable>`
 *    (SPEC §3 rule 1: attribute fallthrough).
 * 3. No `${...}` in a literal `class` or `style` attribute, ever. In `style` the
 *    `{` opens a CSS block, the `}` is eaten and CSS inlining dies for the whole
 *    document; in `class` the `css.safe` rewriter turns `$` into `-` and strips
 *    the braces. Runtime styling goes through
 *    `tal:attributes="style string:…"`, and runtime colours through `bgcolor`.
 * 4. `i18n:domain` on the author's own element when the msgid belongs to the
 *    add-on's own catalog. The kit shell declares `i18n:domain="imio.emailkit"`
 *    on `<html>`, and a nested `i18n:translate` inherits that domain -- so
 *    without the line below this add-on's msgid would be looked up in the wrong
 *    catalog and render its default text, which is indistinguishable from
 *    success.
 * 5. No `--` in any comment, in this file or in the compiled output. Chameleon
 *    refuses to parse it and the `.pt` becomes unloadable at *runtime*.
 */
</script>

<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>

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

    <div tal:condition="cta_url | nothing">
      <KitButton href="${cta_url}" align="center">${cta_label}</KitButton>
    </div>
  </KitMain>
</template>
