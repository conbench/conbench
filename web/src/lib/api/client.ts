import createClient from "openapi-fetch";

import type { paths } from "./schema";

// createConbenchClient returns a fully typed client for the Conbench API. The
// `paths` types come from src/lib/api/schema.ts, generated from the checked-in
// OpenAPI contract (api/openapi.yaml) by `bun run codegen`. Do not edit schema.ts
// by hand; the codegen drift gate regenerates it and fails on any diff.
export function createConbenchClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}
