<script setup>
/**
 * CLEAN counterpart to `violating/raw_in_comment.vue`.
 *
 * Same explanation, written without angle brackets around the component name.
 * Escaping them as &lt;Raw&gt; works too, and is the recommended fix when the
 * prose really wants to show the tag.
 */
</script>

<template>
  <KitMain>
    <!-- Wrap ESP syntax in a Raw block so Vue never parses the braces inside it.
         Spelled &lt;Raw&gt; when the brackets are wanted. -->
    <Raw>
      <p class="m-0 text-sm">{{ unsubscribe_url }}</p>
    </Raw>
  </KitMain>
</template>
