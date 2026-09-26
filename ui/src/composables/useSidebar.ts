import { useStorage } from "@vueuse/core";

// Module-level => shared singleton across every component that imports it, so the
// Sidebar and AppLayout stay in sync. Backed by localStorage so the choice persists
// across reloads; defaults to collapsed on first ever visit.
const collapsed = useStorage<boolean>("adra:sidebar-collapsed", true);

export function useSidebar() {
	const toggle = (): void => {
		collapsed.value = !collapsed.value;
	};

	return { collapsed, toggle };
}
