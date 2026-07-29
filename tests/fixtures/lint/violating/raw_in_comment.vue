<script setup>
/**
 * VIOLATING FIXTURE for `raw-in-comment` (Phase 1).
 *
 * Maizzle extracts the raw-escape block with ONE naive global regex over the
 * whole file. It has no idea what a comment is, so the mention on the next line
 * becomes the opening tag of the match, the real </Raw> below closes it, and
 * everything in between is deleted from the output. Silently.
 *
 * Two mentions, two hits: one in this JavaScript comment (the regex reads the
 * raw file, so `<script>` is no shelter) and one in the template comment.
 */
</script>

<template>
  <KitMain>
    <!-- Wrap ESP syntax in <Raw> so Vue never parses the braces inside it. -->
    <Raw>
      <p class="m-0 text-sm">{{ unsubscribe_url }}</p>
    </Raw>
  </KitMain>
</template>
