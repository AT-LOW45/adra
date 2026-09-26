import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Adra Docs",
  description: "Documentation site for the setup and usage of Adra",
  // Served from https://at-low45.github.io/adra/ — assets need this base path.
  base: "/adra/",
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Getting Started', link: '/getting-started' }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/AT-LOW45/adra' }
    ]
  }
})
