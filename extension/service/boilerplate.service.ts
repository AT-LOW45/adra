import ragApi from "../config/api-config";

const boilerplateService = {
	generateCode: (query: string, language: string, selection_context: string, file_content: string) =>
		// override the client's short default timeout: generation is a slow LLM call
		// (whole file + structured output), unlike the quick liveness ping it was set for
		ragApi.post(
			"/boilerplate/generate-code",
			{ query, language, selection_context, file_content },
			{ timeout: 60000 },
		),
} as const;

export default boilerplateService;
