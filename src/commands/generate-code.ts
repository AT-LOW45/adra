// src/commands/generate-code.ts
import boilerplateService from "../service/boilerplate.service";
import codeActions from "../constants/code-actions";
import { applyCodeEdits, CodeEdit } from "../service/edit.service";
import * as vscode from "vscode";

/** An Output channel works with no debugger attached, unlike console.log. View: Output → "Patterngen". */
const log = vscode.window.createOutputChannel("Patterngen");

/** Ask the language server for the code actions available in `range`, optionally filtered to a `kind`. */
async function requestCodeActions(
	document: vscode.TextDocument,
	range: vscode.Range,
	kind?: string,
): Promise<vscode.CodeAction[]> {
	return (
		(await vscode.commands.executeCommand<vscode.CodeAction[]>(
			"vscode.executeCodeActionProvider",
			document.uri,
			range,
			kind,
			50, // itemResolveCount — without it, action.edit comes back undefined
		)) ?? []
	);
}

/** How an import statement begins, across the languages a language server might serve. */
const IMPORT_STATEMENT = /^(import\b|from\s|export\s+\*|require\b|const\s.*\brequire\s*\(|using\s|#include\b|use\s)/;

/**
 * The import statement this action would insert, or null if it isn't an import fix.
 *
 * Identified by its EDIT, not its title: titles are vendor-specific and localised. An
 * import inserts a whole line; a suppression (`# type: ignore`) appends to the error's own
 * line. An action may carry other edits alongside (Pylance also rewrites the symbol).
 */
function importInsertionText(action: vscode.CodeAction, document: vscode.TextDocument): string | null {
	// Imports are quickfixes. Refactors insert whole lines too — TS's "Generate get/set
	// accessors" got applied 7 times before this check existed.
	if (!action.kind || !vscode.CodeActionKind.QuickFix.contains(action.kind)) {
		return null;
	}

	const entries = action.edit?.entries() ?? [];

	// An import fix only ever touches the file being fixed.
	if (entries.length !== 1) {
		return null;
	}
	const [uri, edits] = entries[0];
	if (uri.toString() !== document.uri.toString()) {
		return null;
	}

	// The whole-line insertion is the import; any other edits in the action are ignored.
	const lineInsert = edits.find((edit) => edit.range.isEmpty && edit.newText.includes("\n") && edit.newText.trim());
	if (!lineInsert) {
		return null;
	}

	const statement = lineInsert.newText.trim();

	// An import is a single statement, never a multi-line block (that's a refactor).
	if (statement.includes("\n")) {
		return null;
	}

	// Finally, it must actually READ like an import. These are language keywords, not UI
	// labels — never translated, never renamed — so unlike action titles they're safe to
	// match on. Without this, any single-line quickfix qualified (TS's "generate get/set
	// accessors" was applied 7 times).
	return IMPORT_STATEMENT.test(statement) ? statement : null;
}

/**
 * Generated code omits imports by design, so have the language server add them. Two routes:
 * a whole-file `source.addMissingImports` (TS/JS, Volar), else a per-diagnostic quickfix
 * (Pylance). Retries because the server needs a beat to analyse newly inserted code.
 */
async function applyAddMissingImports(document: vscode.TextDocument): Promise<boolean> {
	const errorDiagnostics = () =>
		vscode.languages
			.getDiagnostics(document.uri)
			.filter((d) => d.severity === vscode.DiagnosticSeverity.Error);

	const fullRange = () =>
		new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));

	let appliedAny = false;
	// A stale diagnostic re-offers a fix we already applied -> duplicate imports.
	const alreadyApplied = new Set<string>();
	// Fix-all only needs one successful run; re-running re-inserts what it already added.
	let sourceActionUsed = false;
	log.show(true); // reveal without stealing focus

	for (let round = 0; round < 10; round++) {
		// Fix-all route. Requested BY KIND, so anything returned is already the right action.
		let action: vscode.CodeAction | undefined;
		let chosenImport: string | undefined;
		let fromSourceAction = false;

		if (!sourceActionUsed) {
			const sourceActions = await requestCodeActions(document, fullRange(), codeActions.addMissingImports);
			action = sourceActions[0];
			// Consumed only on a successful apply — round 1 often returns it unresolved.
			fromSourceAction = Boolean(action);
		}

		// Per-diagnostic route: the singular fix only appears when asked AT the error's range
		// (what Cmd+. does).
		if (!action) {
			const diagnostics = errorDiagnostics();
			if (diagnostics.length === 0) {
				if (appliedAny) {
					break; // nothing left to import
				}
				await new Promise((resolve) => setTimeout(resolve, 400)); // maybe still analysing
				continue;
			}
			for (const diagnostic of diagnostics) {
				const errorLine = diagnostic.range.start.line;
				const offered = await requestCodeActions(document, diagnostic.range);

				const candidates: { action: vscode.CodeAction; inserts: string }[] = [];
				for (const candidate of offered) {
					const inserts = importInsertionText(candidate, document);
					if (inserts !== null && !alreadyApplied.has(inserts)) {
						candidates.push({ action: candidate, inserts });
					}
				}

				// Servers don't rank best-first (Pylance put "from uvicorn import logging" above
				// "import logging"); the shortest statement is the most direct module.
				candidates.sort((a, b) => a.inserts.length - b.inserts.length);

				log.appendLine(
					`line ${errorLine}: ${offered.length} offered, ${candidates.length} import-shaped` +
						(candidates.length ? ` -> chose ${JSON.stringify(candidates[0].inserts)}` : "") +
						candidates.slice(1).map((c) => `\n    skipped ${JSON.stringify(c.inserts)}`).join(""),
				);

				if (candidates.length > 0) {
					action = candidates[0].action;
					chosenImport = candidates[0].inserts;
					break;
				}
			}
			if (!action) {
				break; // no import fix available for the remaining errors
			}
		}

		if (action.edit) {
			await vscode.workspace.applyEdit(action.edit);
			appliedAny = true;
		} else if (action.command) {
			await vscode.commands.executeCommand(action.command.command, ...(action.command.arguments ?? []));
			appliedAny = true;
		} else {
			await new Promise((resolve) => setTimeout(resolve, 400)); // found but edit unresolved — wait
			continue;
		}

		if (fromSourceAction) {
			sourceActionUsed = true;
			log.appendLine(`applied the whole-file "add all missing imports" action`);
		}
		if (chosenImport) {
			alreadyApplied.add(chosenImport);
		}

		await new Promise((resolve) => setTimeout(resolve, 300)); // let diagnostics refresh
	}

	return appliedAny;
}

export default async function generateCode(context: vscode.ExtensionContext) {
	try {
		// capture editor + selection first, before any dialogs shift focus
		const editor = vscode.window.activeTextEditor;
		if (!editor) {
			vscode.window.showWarningMessage("No active editor found");
			return;
		}
		const selection = editor.selection;

		const input = await vscode.window.showInputBox({
			prompt: "What do you want to generate?",
			placeHolder: "e.g. express route handler for user authentication",
		});

		if (!input || input.trim().length === 0) {
			return;
		}

		const edits = await vscode.window.withProgress(
			{
				location: vscode.ProgressLocation.Notification,
				title: "Patterngen: generating boilerplate...",
				cancellable: false,
			},
			async () => {
				const language = editor.document.languageId;
				const selectedText = editor.document.getText(selection);
				const fileContent = editor.document.getText();
				const response = await boilerplateService.generateCode(
					input,
					language,
					selectedText,
					fileContent,
				);
				return response.data.edits as CodeEdit[];
			},
		);

		// apply every edit, each located by its `search` anchor against the original file
		const { applied, missed } = await applyCodeEdits(editor, selection, edits);

		if (missed > 0) {
			vscode.window.showWarningMessage(
				`Patterngen: ${missed} change(s) couldn't be located in the file and were skipped.`,
			);
		}

		// generated code omits imports by design — let the editor add the correct ones
		if (applied > 0) {
			await applyAddMissingImports(editor.document);
		}
	} catch (error) {
		console.error("generateCode error:", error); // full error in Debug Console
		vscode.window.showErrorMessage(`Error: ${error instanceof Error ? error.message : String(error)}`);
	}
}
