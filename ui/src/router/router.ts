    import AppLayout from "@/components/layout/AppLayout.vue";
import { createRouter, createWebHistory } from "vue-router";
import ROUTES from "./routes";

export type ExtractRoutes<T> = T extends string ? T : T extends Record<string, any> ? ExtractRoutes<T[keyof T]> : never;

export type RoutePaths = ExtractRoutes<typeof ROUTES>;
export type CreateRouterRoutes = Parameters<typeof createRouter>[0]["routes"];

const routes: CreateRouterRoutes = [
	{
		path: ROUTES.default,
		component: AppLayout,
		children: [
			{
				path: ROUTES.default,
				redirect: () => {
					return ROUTES.knowledgeBase;
				},
			},
			{
				path: ROUTES.knowledgeBase,
				name: "KnowledgeBase",
				component: () => import("@/pages/KnowledgeBaseListPage.vue"),
			},
			{
				path: ROUTES.knowledgeBaseRecord,
				name: "KnowledgeBaseRecord",
				component: () => import("@/pages/KnowledgeBaseRecordPage.vue"),
			},
			{
				path: ROUTES.knowledgeBaseCreate,
				name: "KnowledgeBaseCreate",
				component: () => import("@/pages/CreateAdrTemplatePage.vue"),
			},
			{
				path: ROUTES.adrConfig,
				name: "ADRConfig",
				component: () => import("@/pages/AdrConfigPage.vue"),
			},
			{
				path: ROUTES.searchTuning,
				name: "SearchTuning",
				component: () => import("@/pages/SearchTuningPage.vue"),
			},
		],
	},
];

const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
