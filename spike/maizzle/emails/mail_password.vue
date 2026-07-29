<script setup>
import { useDoctype } from '@maizzle/framework'

// Plone's RegistrationTool renders this template and parses the mail headers
// straight back out of the rendered text (`message_from_string(mail_text)`),
// reading Content-Type from it. So the template owns its own headers.
//
// Maizzle has no first-class "emit text before the doctype" hook, so Phase 0
// borrows `useDoctype()` for it. That is a spike expedient, NOT a Phase 1
// pattern -- emitting mail headers properly is an open Phase 1 design question.
useDoctype(`Subject: <span i18n:translate="email_subject_password_reset">Reset your password</span>
To: \${member/email}
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>`)
</script>

<template>
  <Layout lang="${lang}">
    <Container class="max-w-xl p-6">
      <p class="text-base text-gray-700" data-emailkit-override="mail_password">
        Bonjour ${member/fullname}, voici le lien de reinitialisation.
      </p>
      <a href="${reset_url}" class="text-sm font-bold underline">Reinitialiser</a>
    </Container>
  </Layout>
</template>
