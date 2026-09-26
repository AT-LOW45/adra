import * as vscode from "vscode";

export interface CodeEdit {
	search: string;
	replace: string;
}

export interface ApplyEditsResult {
	applied: number;
	missed: number;
}

type Match = { start: number; end: number };

/**
 * Find every place an edit's `search` occurs in the file, in order. Tries exact
 * matches first; if there are none, falls back to a tolerant match — runs of
 * whitespace become flexible and semicolons are optional — so the model reformatting
 * indentation/spacing or a trailing semicolon doesn't cause a miss. Returning ALL
 * occurrences lets the caller give each edit a distinct one (duplicate anchors).
 */
function findMatches(text: string, search: string): Match[] {
	const matches: Match[] = [];
	if (search.length === 0) {
		return matches;
	}

	// exact occurrences
	let from = text.indexOf(search);
	while (from !== -1) {
		matches.push({ start: from, end: from + search.length });
		from = text.indexOf(search, from + search.length);
	}
	if (matches.length > 0) {
		return matches;
	}

	// tolerant fallback: escape regex specials, then relax the semantically
	// insignificant differences (JS/TS, Ruby, Kotlin, Swift, Go, Lua, Scala treat
	// whitespace runs and trailing semicolons as flexible).
	const trimmed = search.trim();
	if (trimmed.length === 0) {
		return matches;
	}
	const pattern = trimmed
		.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
		.replace(/\s+/g, "\\s+")
		.replace(/;/g, ";?");
	const re = new RegExp(pattern, "g");
	let m: RegExpExecArray | null;
	while ((m = re.exec(text)) !== null) {
		matches.push({ start: m.index, end: m.index + m[0].length });
		if (re.lastIndex === m.index) {
			re.lastIndex++; // guard against a zero-length match looping forever
		}
	}
	return matches;
}

const overlaps = (a: Match, b: Match) => a.start < b.end && b.start < a.end;

/**
 * Apply a set of search/replace edits to the editor's document. Every `search`
 * anchor is located against the ORIGINAL document text and all edits are applied
 * together in a single edit() call, so earlier replacements don't shift the offsets
 * of later ones. An edit with an empty `search` is inserted at the selection/cursor
 * (new code with no anchor). Returns how many edits were applied vs. not located.
 *
 * Kept independent of any one command so the input-box flow and a future chat/coding
 * session can share the same edit-application engine.
 */
export async function applyCodeEdits(
	editor: vscode.TextEditor,
	selection: vscode.Selection,
	edits: CodeEdit[],
): Promise<ApplyEditsResult> {
	const document = editor.document;
	const originalText = document.getText();

	type Op = { range?: vscode.Range; insertAt?: vscode.Position; replace: string };
	const ops: Op[] = [];
	let missed = 0;

	// Ranges already taken, so different edits never target the same span (VS Code
	// rejects overlapping edits in one edit() call).
	const claimed: Match[] = [];

	// Dedupe identical edits — if the model emits the same {search, replace} twice for
	// a repeated line, we only need it once (each edit already covers every occurrence).
	const seen = new Set<string>();
	const uniqueEdits = edits.filter((edit) => {
		const key = `${edit.search} ${edit.replace}`;
		if (seen.has(key)) {
			return false;
		}
		seen.add(key);
		return true;
	});

	for (const edit of uniqueEdits) {
		if (!edit.search) {
			// no anchor — insert at the selection/cursor (typically new code in an empty file)
			ops.push({ insertAt: selection.active, replace: edit.replace });
			continue;
		}

		const matches = findMatches(originalText, edit.search);
		if (matches.length === 0) {
			missed++;
			continue;
		}

		// Apply to EVERY occurrence (skipping any a prior edit already claimed). This is
		// what makes a rename replace all identical spots — e.g. two identical @keydown
		// handlers — even when the model emits a single edit for them.
		for (const match of matches) {
			if (claimed.some((c) => overlaps(match, c))) {
				continue;
			}
			claimed.push(match);
			ops.push({
				range: new vscode.Range(
					document.positionAt(match.start),
					document.positionAt(match.end),
				),
				replace: edit.replace,
			});
		}
	}

	if (ops.length === 0) {
		return { applied: 0, missed };
	}

	const ok = await editor.edit((editBuilder) => {
		for (const op of ops) {
			if (op.range) {
				editBuilder.replace(op.range, op.replace);
			} else if (op.insertAt) {
				editBuilder.insert(op.insertAt, op.replace);
			}
		}
	});

	return { applied: ok ? ops.length : 0, missed };
}
