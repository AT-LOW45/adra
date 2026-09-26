import * as dotenv from "dotenv";
import * as vscode from "vscode";
import generateCode from "./commands/generate-code";
import openKnowledgeBase from "./commands/open-knowledge-base";
import COMMANDS from "./constants/commands";
import { startLivelinessCheck, withBackendReady } from "./service/system.service";

dotenv.config();

/** Extension entry point — registers the commands and starts the backend liveness check. */
export async function activate(context: vscode.ExtensionContext) {
	const { registerCommand } = vscode.commands;
	console.log("welcome to adra!");

	context.subscriptions.push(
		registerCommand(
			COMMANDS.generateCode.id,
			withBackendReady(() => generateCode(context)),
		),
		registerCommand(
			COMMANDS.openKnowledgeBase.id,
			withBackendReady(() => openKnowledgeBase()),
		),
	);

	// commands are already registered; run the check in the background so it can
	// never delay activation. Gated commands consult its status via withBackendReady.
	startLivelinessCheck();
}

/** Called when the extension is deactivated. */
export function deactivate() {
	console.log("Thanks for using adra!");
}
