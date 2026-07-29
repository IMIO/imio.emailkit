<script setup>
/**
 * FIXTURE for the escape hatch.
 *
 * Every construct below would be reported. Each carries an opt-out, so nothing
 * is. Without a hatch like this, the first author who meets a genuine exception
 * deletes the whole gate from CI, and `style-placeholder` starts shipping again.
 *
 * Four placements are exercised:
 *
 *   1. the marker on the offending line itself;
 *   2. the marker above a multi-line tag, suppressing a violation found three
 *      lines further in -- an HTML comment cannot be written inside a tag, so
 *      this is the only placement available there;
 *   3. two rule ids in one marker;
 *   4. `ignore=all`, for the rare file-level oddity.
 *
 * The marker is deliberately not silent about itself: `--list-rules` explains
 * what is being waived, and the report names the marker every time it prints a
 * violation.
 */
</script>

<template>
  <KitMain>
    <!-- 1. on the offending line -->
    <p class="m-0 text-sm ${extra_class}">${intro}</p><!-- emailkit-lint: ignore=class-placeholder -->

    <!-- 2. above a multi-line tag: emailkit-lint: ignore=tal-on-component -->
    <KitPanel
      tal:condition="warning"
      tone="accent"
    >
      <p class="m-0 text-sm">${warning}</p>
    </KitPanel>

    <!-- 3. two rules at once: emailkit-lint: ignore=style-placeholder, missing-alt -->
    <img src="${logo_url}" style="border: 1px solid ${theme/primary_color}" width="140">

    <!-- 4. everything on this line: emailkit-lint: ignore=all -->
    <p class="m-0 ${extra_class}" style="color: ${theme/primary_color}">${format_date(when)}</p>
  </KitMain>
</template>
