<script setup>
/**
 * `KitDataList` -- the label/value table: three or four facts, tabulated.
 *
 * Not the same thing as `KitDataTable`, and the difference is worth keeping.
 * `KitDataTable` is a real data table: many rows of the same shape, a header row
 * naming the columns, `role="table"` so a screen reader announces the grid.
 * `KitDataList` is a definition list wearing a table's clothes: a fixed handful
 * of label/value pairs -- who, when, where -- with no header, no repetition and
 * no grid to navigate. Marking that as a data table would announce a two-column
 * structure that carries no meaning; it is `role="presentation"`, and the labels
 * do the work.
 *
 * Normally the last thing inside a `KitCard`:
 *
 *     <KitDataList>
 *       <KitDataRow>
 *         <template #label><span i18n:translate="email_field_author" tal:omit-tag="">Author</span></template>
 *         ${author}
 *       </KitDataRow>
 *     </KitDataList>
 *
 * ---------------------------------------------------------------------------
 * The rule between the rows
 * ---------------------------------------------------------------------------
 * `kit-datalist` is not decoration: `kit/tailwind.css` hangs a
 * `tr + tr > td { border-top: … }` rule off it, which is what draws the
 * separator the mockups put between rows. Written as a top border on every row
 * but the first rather than a bottom border on every row but the last, because
 * only one of those two can be expressed at all -- see `DataRow.vue`.
 *
 * ---------------------------------------------------------------------------
 * Rows may be a component here; in `KitDataTable` they may not
 * ---------------------------------------------------------------------------
 * SPEC §3 rule 1 forbids `tal:` on a kit component, because Vue attribute
 * fallthrough lands it on whichever element happens to be the component's root.
 * A `tal:repeat` therefore has to live on an author's own `<tr>`. That binds
 * `KitDataTable`, whose whole purpose is repeated rows; it does not bind this
 * component, which by definition holds a fixed handful of pairs. `KitDataRow` is
 * the shorthand for them. An author who does need a repeat writes a plain `<tr>`
 * with the cell classes spelled out, which still works and still gets the rule
 * above.
 *
 * `data-dark="surface"` rather than `raised`: inside a `KitCard` this is the
 * innermost of three nested fills, and in dark mode the nesting inverts -- the
 * card lightens to `raised` and this recedes to `surface`, keeping the same two
 * steps of contrast the light rendering has between #f8f8f8 and #ffffff. Used
 * outside a card, on the shell's white surface, it simply matches its
 * background, which is also what it does in the light rendering.
 *
 * Import-free, like every kit component.
 */
</script>

<template>
  <table
    role="presentation"
    class="kit-datalist mt-4 w-full rounded-[10px] border border-solid border-imio-grey-border bg-imio-white"
    data-dark="surface"
  >
    <slot />
  </table>
</template>
