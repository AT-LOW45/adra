import * as vscode from "vscode";

export default function openKnowledgeBase() {
	const config = vscode.workspace.getConfiguration("adra");
	const ragBaseUrl = config.get<string>("ragEndpoint");

	if (!ragBaseUrl) {
		vscode.window.showErrorMessage("Rag endpoint not configured.");
		return;
	}

	// Open the configured endpoint as-is rather than decomposing it into
	// scheme/authority/path and rebuilding — parsing the whole string preserves the
	// full URL (incl. any query/fragment) and won't throw on a malformed setting.
	vscode.env.openExternal(vscode.Uri.parse(ragBaseUrl));
}
