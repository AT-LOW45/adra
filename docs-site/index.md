---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "Adra"
  text: "Code grounded in your ADRs"
  tagline: A VS Code extension that generates and edits code to match your team's documented conventions — not generic snippets.
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/AT-LOW45/adra

features:
  - icon: 📐
    title: Grounded in your ADRs
    details: Retrieves your team's Architecture Decision Records and instructs the model to follow them, so generated code matches your documented conventions instead of generic patterns.
  - icon: ✏️
    title: File-aware edits
    details: Describe a change in plain language — Adra locates the right code, applies precise search/replace edits in place, and resolves the imports for you.
  - icon: 📚
    title: Knowledge-base manager
    details: Upload, edit, and organize your ADRs from a built-in web UI that keeps the retrieval index in sync.
---
