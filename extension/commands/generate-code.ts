// src/commands/generate-code.ts
import boilerplateService from "../service/boilerplate.service";
import codeActions from "../constants/code-actions";
import { applyCodeEdits, CodeEdit } from "../service/edit.service";
import * as vscode from "vscode";

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
			// itemResolveCount: force the provider to resolve each action's edit.
			// Without it, action.edit comes back undefined and there's nothing to apply.
			50,
		)) ?? []
	);
}

/**
 * The generated code deliberately omits imports, so ask the language server to add
 * them. TS/JS expose a dedicated `source.addMissingImports` action; Vue/Volar only
 * surface a titled action, so we fall back to that. The server needs a beat to
 * analyse the freshly inserted code, hence the short retry loop.
 */
async function applyAddMissingImports(document: vscode.TextDocument): Promise<boolean> {
	const isImportAction = (a: vscode.CodeAction) =>
		a.kind?.value === codeActions.addMissingImports ||
		/add all missing imports/i.test(a.title) ||
		/^add import\b/i.test(a.title);

	const errorDiagnostics = () =>
		vscode.languages
			.getDiagnostics(document.uri)
			.filter((d) => d.severity === vscode.DiagnosticSeverity.Error);

	const fullRange = () =>
		new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));

	let appliedAny = false;

	for (let round = 0; round < 10; round++) {
		// Prefer the "add all missing imports" source action — it fixes everything in one
		// shot and is reliably returned over the whole file.
		const sourceActions = await requestCodeActions(document, fullRange(), codeActions.addMissingImports);
		let action = sourceActions.find(isImportAction);

		// Otherwise drive it per-diagnostic: the singular "Add import from '…'" is a
		// quick-fix scoped to a diagnostic, so it only shows when requested AT that
		// diagnostic's range (this is what Cmd+. does at the cursor).
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
				const atDiagnostic = await requestCodeActions(document, diagnostic.range);
				action = atDiagnostic.find(isImportAction);
				if (action) {
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
				title: "Adra: generating boilerplate...",
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
				`Adra: ${missed} change(s) couldn't be located in the file and were skipped.`,
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
