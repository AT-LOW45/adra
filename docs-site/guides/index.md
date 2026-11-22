---
title: Guides
description: Writing ADRs that coding agents actually follow.
---

<script setup>
// .mts, not .ts: docs-site is a CommonJS package, so a .ts loader can't require the
// ESM-only vitepress module. The .mts extension forces it to load as ESM.
import { withBase } from 'vitepress'
import { data as guides } from './guides.data.mts'

const formatDate = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
    : ''
</script>

# Guides

Writing ADRs that coding agents actually follow.

<div class="guide-grid">
  <a v-for="guide in guides" :key="guide.url" class="guide-card" :href="withBase(guide.url)">
    <!-- Rendered only when a guide declares one, so a card without an image reads as
         deliberate rather than as a picture that failed to load. Add `image: /…` to a
         guide's frontmatter and it appears. -->
    <div v-if="guide.image" class="guide-card-image">
      <img :src="withBase(guide.image)" alt="" loading="lazy" />
    </div>
    <div class="guide-card-body">
      <h2>{{ guide.title }}</h2>
      <p v-if="guide.description">{{ guide.description }}</p>
      <time v-if="guide.date" :datetime="guide.date">{{ formatDate(guide.date) }}</time>
    </div>
  </a>
</div>

<style scoped>
.guide-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.25rem;
  margin-top: 2.5rem;
}

@media (min-width: 720px) {
  .guide-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.guide-card {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  overflow: hidden;
  background: var(--vp-c-bg-soft);
  text-decoration: none;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.guide-card:hover {
  border-color: var(--vp-c-brand-1);
  transform: translateY(-2px);
}

.guide-card-image {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: var(--vp-c-bg-alt);
}

.guide-card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.guide-card-body {
  padding: 1.25rem 1.35rem 1.4rem;
}

/* Cards carry their own type scale. VitePress's default h2 adds a top border and
   page-heading margins, which would draw a line across the middle of the card. */
.guide-card-body h2 {
  margin: 0;
  padding: 0;
  border: 0;
  font-size: 1.1rem;
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--vp-c-text-1);
}

.guide-card-body p {
  margin: 0.5rem 0 0;
  font-size: 0.925rem;
  line-height: 1.6;
  color: var(--vp-c-text-2);
}

.guide-card-body time {
  display: block;
  margin-top: 0.9rem;
  font-size: 0.8rem;
  color: var(--vp-c-text-3);
}

@media (prefers-reduced-motion: reduce) {
  .guide-card {
    transition: none;
  }
  .guide-card:hover {
    transform: none;
  }
}
</style>
