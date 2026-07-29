<template>
  <!--
    Phase 0 torture-test template. NOT a realistic email -- it exists to carry
    every construct the runtime depends on in one file, so a single build/diff
    answers several assumptions at once. Realism is Phase 1's job.

    `lang` is a plain string prop, so the Chameleon placeholder rides through to
    `<html lang="...">` -- SPEC §3's a11y default.

    GOTCHA: do NOT write the raw-escape component's name in angle brackets
    inside a comment. Its extraction is a naive global regex over the file
    source that also matches inside HTML comments, so a mention in a comment
    swallows the real block. That is what silently deleted this template's
    escape block on the first build.
  -->
  <Layout lang="${lang}" body-class="bg-gray-50">
    <!-- SPEC §3 preheader slot, fed by the optional `preheader` msgid (§4). -->
    <Preheader>${preheader}</Preheader>

    <!--
      Custom CSS must be a real <style> ELEMENT inside <template>. A top-level
      SFC <style> block is standard Vue component styling: the bundler extracts
      it and it never reaches the email, after which purge strips the orphaned
      class from the class attribute too. Verified in Phase 0.
    -->
    <style>
      .spike-kept-class {
        color: #7c3aed;
      }

      .spike-purge-victim {
        color: #059669;
        font-weight: 700;
      }
    </style>

    <Container class="max-w-xl p-6">
      <!--
        i18n:domain is REQUIRED for i18n:translate to translate anything. The
        compiled output had none, so every msgid silently rendered as its own
        untranslated default -- indistinguishable from success. Declared on a
        plain wrapper, never on a kit component (§3 rule 1); in Phase 1 the
        kit's Main.vue emits it on <html>, which the kit owns.
      -->
      <div i18n:domain="imio.emailkit">
      <!-- a11y: enforced `alt` on the logo (§3). -->
      <Img src="/logo.png" width="60" alt="iMio" />

      <!-- (1) ${...} in a text node, plus a custom class that IS referenced
           from a real class attribute, so its rule must survive purge. -->
      <p class="spike-kept-class text-base text-gray-700">
        Bonjour ${member/fullname}, voici votre convocation.
      </p>

      <!-- (2) i18n:translate="" with no msgid, on a plain element. -->
      <p i18n:translate="" class="text-sm text-gray-600">email_intro_default</p>

      <!-- (3) i18n:translate="msgid" + i18n:name interpolation. -->
      <p i18n:translate="email_greeting" class="text-sm text-gray-600">
        Bonjour <span i18n:name="fullname" tal:content="member/fullname">Name</span>
      </p>

      <!-- (4) ${...} in a non-class, non-style attribute. NOTE: a Chameleon
           placeholder must never go in a `style` attribute -- see
           emails/theme-token-literal.vue for what that does. -->
      <a href="${item/absolute_url}" class="text-sm underline">${item/title}</a>

      <!-- (5) tal:condition + tal:attributes with a literal value: §3 rule 2's
           sanctioned pattern for runtime-conditional styling. -->
      <p
        tal:condition="item/is_urgent"
        tal:attributes="style string:color: #b91c1c"
        class="text-sm font-bold"
      >URGENT</p>

      <!-- (6) tal:repeat on a <tr> INSIDE a table -- the specific §9 requirement.
           Authored as plain markup, never as a kit component (§3 rule 1). -->
      <table role="presentation" class="w-full border-collapse">
        <tr class="bg-gray-100">
          <th i18n:translate="" class="p-2 text-left text-xs font-bold text-gray-700">col_title</th>
          <th i18n:translate="" class="p-2 text-left text-xs font-bold text-gray-700">col_status</th>
        </tr>
        <tr tal:repeat="row items" class="border-b border-gray-200">
          <td class="p-2 text-sm text-gray-800">${row/title}</td>
          <td class="p-2 text-sm text-gray-500">${row/status}</td>
        </tr>
      </table>

      <!-- (7) Two kit components resolved from an absolute path OUTSIDE this
           project root (§10.1). No tal:/i18n: attributes on them (§3 rule 1). -->
      <KitPanel>
        <KitButton href="${item/absolute_url}">Voir le point</KitButton>
      </KitPanel>

      <!-- (8) Theme token via tal:attributes -- the form that actually works. -->
      <a
        href="#"
        tal:attributes="style string:background-color: ${theme/primary_color}"
        class="rounded px-4 py-2 text-white"
      >Token via tal:attributes</a>

      <!-- (9) `structure` on the body_html slot: §3 rule 4's one sanctioned use. -->
      <div tal:content="structure body_html" class="text-base text-gray-700">slot placeholder</div>

      <!-- (10) Block-level raw escape: content must survive the Vue compiler
           verbatim, including a repeat over a table row. -->
      <Raw>
        <table role="presentation" class="w-full">
          <tr tal:repeat="extra extras">
            <td>${extra/label}</td>
          </tr>
        </table>
      </Raw>

      <!-- (11) v-pre: Vue's own escape. {{ }} must survive the Vue compiler.
           Note it protects against Vue ONLY. Chameleon still evaluates ${...}
           inside a v-pre element at runtime, so v-pre alone does NOT make a
           placeholder literal. The two escape layers are independent. -->
      <p v-pre class="text-xs text-gray-400">{{ vue_would_eat_this }}</p>

      <!-- (12) Chameleon-level escape: `$${...}` renders as a literal `${...}`.
           This is the escape for text that must survive to the INBOX, not just
           past the Vue compiler. -->
      <p class="text-xs text-gray-400">$${not/evaluated}</p>

      <!-- NEGATIVE CONTROL 1 (non-gating): `spike-purge-victim` is defined in
           the style element above but referenced ONLY from tal:attributes.
           css.purge sees no such class in any class attribute, so the rule is
           expected to be removed. This is the failure mode §3 rule 2 prevents.
           Compare with `spike-kept-class` above: same style element, one kept. -->
      <p tal:attributes="class string:spike-purge-victim" class="text-sm">control 1</p>

      <!-- NEGATIVE CONTROL 2 (non-gating): a Chameleon placeholder inside a
           class attribute. css.safe maps $ -> - and strips { }, so this is
           expected to be corrupted. -->
      <p class="text-sm ${item/css_class}">control 2</p>
      </div>
    </Container>
  </Layout>
</template>
