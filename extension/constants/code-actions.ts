// VS Code code-action kinds we drive programmatically. Kept as plain strings —
// executeCodeActionProvider's `kind` argument rejects a CodeActionKind object.
const CODE_ACTIONS = {
	addMissingImports: "source.addMissingImports",
} as const;

export default CODE_ACTIONS;
