import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Adra Docs",
  description: "Give coding agents your team's Architecture Decision Records over MCP",
  // Served from https://at-low45.github.io/adra/ — assets need this base path.
  base: "/adra/",
  // The guides link to the reader's own running Adra (http://localhost:8000), which the
  // dead-link check can't reach at build time. Every other link is still checked.
  ignoreDeadLinks: 'localhostLinks',
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Getting Started', link: '/getting-started' },
      { text: 'Guides', link: '/guides/' }
    ],

    // Keyed by path, so /guides/ is its own section rather than another heading under
    // the docs: a reader there sees only guides, and the docs reader only the docs.
    sidebar: {
      '/guides/': [
        {
          text: 'Guides',
          items: [
            { text: 'All guides', link: '/guides/' },
            { text: 'Writing ADRs an agent can find', link: '/guides/writing-findable-adrs' }
          ]
        }
      ],
      '/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Quickstart', link: '/getting-started' },
            { text: 'Connect your agent', link: '/connect-your-agent' },
            { text: 'Run from source', link: '/run-from-source' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/AT-LOW45/adra' }
    ]
  }
})
