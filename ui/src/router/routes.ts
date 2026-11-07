const ROUTES = {
	default: "/",
	knowledgeBase: "/knowledge-base",
	knowledgeBaseRecord: "/knowledge-base/:id",
	knowledgeBaseCreate: "/knowledge-base/create",
	adrConfig: "/adr-config",
	searchTuning: "/search-tuning"
} as const;

export default ROUTES;
