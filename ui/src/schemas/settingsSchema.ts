import { z } from "zod/v4";

// Relevance scores are cosine similarities of normalized embeddings, so a threshold
// only makes sense in 0..1. Mirrors the bounds the backend enforces on PUT /settings.
export const retrievalThresholdSchema = z.object({
	retrievalThreshold: z
		.number({ message: "Threshold must be a number." })
		.min(0, { message: "Threshold cannot be below 0." })
		.max(1, { message: "Threshold cannot be above 1." }),
});

export type RetrievalThresholdSchema = z.infer<typeof retrievalThresholdSchema>;
