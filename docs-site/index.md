---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "Adra"
  text: "Your ADRs, followed by your coding agent"
  tagline: Adra gives coding agents your team's Architecture Decision Records over MCP, so the code they write follows your documented conventions, not generic best practice or whatever the surrounding file happens to do.
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/AT-LOW45/adra

# Icons are Lucide (https://lucide.dev, ISC), inlined so the site needs no icon dependency.
# stroke="currentColor" plus the brand color keeps them matching the theme in light and dark.
features:
  - icon: '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--vp-c-brand-1)"><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="m9 15 2 2 4-4"/></svg>'
    title: Grounded in your ADRs
    details: Before writing code, the agent searches your ADRs and gets each relevant one in full, code examples included, and follows it over local style. Tasks no ADR covers get nothing, so unrelated rules aren't forced in.
  - icon: '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--vp-c-brand-1)"><path d="M12 22v-5"/><path d="M15 8V2"/><path d="M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"/><path d="M9 8V2"/></svg>'
    title: Works with the agent you already use
    details: Adra doesn't generate code; your agent does. Connect any MCP client to one endpoint and it can search your ADRs and list them. Tested end to end with Claude Code.
  - icon: '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--vp-c-brand-1)"><path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/></svg>'
    title: Knowledge-base manager
    details: Write, upload, review and edit ADRs from a built-in web UI that keeps the search index in sync. Test which ADRs a task would find, and tune how strict matching is.
---
