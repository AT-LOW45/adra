import { createContentLoader } from "vitepress";

export interface Guide {
	url: string;
	title: string;
	description: string;
	date: string;
	/** Optional cover image, as a site-absolute path. Cards omit the image area without one. */
	image?: string;
}

// Resolved at build time, so the index never drifts from what's on disk: adding a guide
// is adding a file. index.md is excluded so the list doesn't contain itself.
const toIsoDate = (value: unknown): string => {
	if (value instanceof Date) return value.toISOString().slice(0, 10);
	if (typeof value === "string") return value.slice(0, 10);
	return "";
};

export default createContentLoader("guides/*.md", {
	excerpt: false,
	transform(raw): Guide[] {
		return raw
			.filter(({ url, frontmatter }) => !url.endsWith("/guides/") && frontmatter.title)
			.map(({ url, frontmatter }) => ({
				url,
				title: frontmatter.title,
				description: frontmatter.description ?? "",
				// YAML parses an unquoted 2026-11-22 into a Date, so it has to be normalised
				// rather than stringified: String(date) gives "Sun Nov 22 2026 …", and slicing
				// that to 10 characters yields "Sun Nov 2", which re-parses as the year 2001.
				// Falls back to an empty string rather than today, so a guide that forgets its
				// date sorts last and is visibly wrong instead of quietly looking newest.
				date: toIsoDate(frontmatter.date),
				image: frontmatter.image,
			}))
			.sort((a, b) => b.date.localeCompare(a.date));
	},
});
