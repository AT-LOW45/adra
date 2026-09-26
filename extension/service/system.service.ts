import ragApi from "../config/api-config";
import * as vscode from "vscode";

const systemService = {
	checkLiveliness: () => ragApi.post("/health"),
};

type BackendStatus = "checking" | "up" | "down";
let status: BackendStatus = "checking";
let probe: Promise<void> | null = null;

/**
 * Kick off a one-shot backend liveness probe (POST /health) in the background and
 * record the outcome in `status`. Call once on activation; command guards read `status`.
 */
export const startLivelinessCheck = () => {
	console.log(`[adra] liveliness check started at ${new Date().toISOString()}`);
	status = "checking";
	probe = systemService
		.checkLiveliness()
		.then(() => {
			status = "up";
			console.log(`[adra] liveliness check resolved UP at ${new Date().toISOString()}`);
		})
		.catch(() => {
			status = "down";
			console.log(`[adra] liveliness check resolved DOWN at ${new Date().toISOString()}`);
		});
};

/**
 * Gate for backend-dependent commands. If the probe is still in flight, tell the user
 * and wait for it to settle, then allow the command only when the backend is up —
 * warning and blocking when it's down.
 */
const ensureBackendReady = async () => {
	// still in flight — tell the user, wait for it to settle, then re-check below
	if (status === "checking") {
		vscode.window.showInformationMessage("Adra is still checking the backend - one moment...");
		await probe;
	}
	if (status === "down") {
		vscode.window.showWarningMessage("Adra backend is not reachable now. Please check the configuration");
		return false;
	}
	return true;
};

/**
 * Wrap a command handler so it runs only after `ensureBackendReady` passes. Apply it
 * at registration to gate backend-dependent commands without touching their bodies.
 */
export const withBackendReady = (run: () => unknown) => {
	return async () => {
		if (!(await ensureBackendReady())) {
			return;
		}
		return await run();
	};
};

export default systemService;
