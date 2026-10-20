const CHUNK_ERROR =
  /dynamically imported module|importing a module script failed|unable to preload|error loading dynamically/i;

/** True for the errors a stale tab gets when a deploy removed the old hashed assets. */
export const isChunkLoadError = (error: unknown): boolean =>
  error instanceof Error && CHUNK_ERROR.test(error.message);
