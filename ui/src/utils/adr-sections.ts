// Splits an ADR's raw markdown into editable H2 sections and joins them back, WITHOUT
// re-serialising from a model. Each section keeps its body verbatim, so joining an
// unedited document reproduces the original byte-for-byte — editing one card never
// reflows or drops content elsewhere (tables, prose, sections the create form doesn't
// model, file-uploaded ADRs). See scratchpad/roundtrip checks for the guarantees.

export interface AdrSection {
	/** The exact first line of the block, e.g. "## Decision" (no trailing newline). */
	headingLine: string;
	/** Display heading (the text after "## "), e.g. "Decision". Drives card title + anchor. */
	heading: string;
	/** Everything after the heading line, verbatim, including trailing blank lines. */
	body: string;
	/** Whether the original block had a newline after the heading (false only for a heading at EOF). */
	hadNewline: boolean;
}

export interface AdrDocument {
	/** Text before the first "## " — the H1 title and any intro. Kept verbatim. */
	preamble: string;
	sections: AdrSection[];
}

const displayHeading = (headingLine: string): string => headingLine.replace(/^##\s+/, "").trim();

const parseChunk = (chunk: string): AdrSection => {
	const nl = chunk.indexOf("\n");
	if (nl === -1) {
		return { headingLine: chunk, heading: displayHeading(chunk), body: "", hadNewline: false };
	}
	const headingLine = chunk.slice(0, nl);
	return { headingLine, heading: displayHeading(headingLine), body: chunk.slice(nl + 1), hadNewline: true };
};

/** Parse markdown into a preamble + H2 sections. Fence-aware: a "## " inside a ``` code
 * block is treated as content, not a heading. */
export const splitAdr = (markdown: string): AdrDocument => {
	const rawParts = markdown.split(/(?=^## )/m);

	// Re-merge any "## " that fell inside an open code fence back into the previous chunk.
	const parts: string[] = [];
	let fenceOpen = false;
	for (const part of rawParts) {
		if (part.startsWith("## ") && fenceOpen && parts.length) parts[parts.length - 1] += part;
		else parts.push(part);
		const fences = (part.match(/^[ \t]*(```|~~~)/gm) || []).length;
		if (fences % 2 === 1) fenceOpen = !fenceOpen;
	}

	const hasPreamble = parts.length > 0 && !parts[0].startsWith("## ");
	const preamble = hasPreamble ? parts[0] : "";
	const chunks = hasPreamble ? parts.slice(1) : parts;
	return { preamble, sections: chunks.filter((c) => c.startsWith("## ")).map(parseChunk) };
};

const reassemble = (s: AdrSection): string =>
	s.body.length > 0 || s.hadNewline ? `${s.headingLine}\n${s.body}` : s.headingLine;

/**
 * Rebuild the full markdown. `joinAdr(splitAdr(md)) === md` for any input.
 *
 * A section's text must end with a newline or the next "## " lands on its last line and
 * stops being a heading, silently merging the two sections. splitAdr keeps trailing
 * newlines verbatim, so a round-tripped document already satisfies this and the padding
 * below is a no-op for it — but an edited body comes back from the editor without one,
 * and a section built by hand may never have had one. Only non-last sections are padded,
 * so a document whose final section has no trailing newline still round-trips exactly.
 */
export const joinAdr = (doc: AdrDocument): string =>
	doc.preamble +
	doc.sections
		.map((section, index) => {
			const text = reassemble(section);
			const isLast = index === doc.sections.length - 1;
			return isLast || text.endsWith("\n") ? text : `${text}\n`;
		})
		.join("");

export const sectionSlug = (heading: string): string =>
	heading.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

/** DOM id for a section card, so review findings can scroll to it. */
export const sectionAnchorId = (heading: string): string => `adr-section-${sectionSlug(heading)}`;
