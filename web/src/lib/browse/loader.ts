import type { createConbenchClient } from "../api/client";
import type { BrowseQuery } from "../router";
import { toBrowseRows, windowStartIso, type BrowseRow } from "./transform";

type Client = ReturnType<typeof createConbenchClient>;

export interface BrowsePage {
  rows: BrowseRow[];
  nextCursor: string | null;
}

export const BROWSE_PAGE_SIZE = 25;

function listSeriesError(res: { error?: { detail?: string } | undefined }): Error {
  return new Error(res.error?.detail ?? "failed to list series");
}

/** listSeries fetches one page of GET /api/series for the browse table. Filters
 * map 1:1 onto the endpoint; the window preset becomes an absolute UTC
 * active_since at call time. Throws on any error so the page's error state owns
 * presentation. now is injectable for tests. */
export async function listSeries(
  client: Client,
  query: BrowseQuery,
  cursor: string | null = null,
  now: Date = new Date(),
): Promise<BrowsePage> {
  const since = windowStartIso(query.window, now);
  const res = await client.GET("/api/series", {
    params: {
      query: {
        page_size: BROWSE_PAGE_SIZE,
        ...(query.q !== "" && { q: query.q }),
        ...(query.hardware !== "" && { hardware: query.hardware }),
        ...(query.repository !== "" && { repository: query.repository }),
        ...(since !== null && { active_since: since }),
        ...(cursor !== null && { cursor }),
      },
    },
  });
  if (res.error || !res.data) {
    throw listSeriesError(res);
  }
  // The generated schema types `series` as nullable (a Go nil slice serializes
  // as JSON null); treat null as an empty page, matching the history loader.
  return { rows: toBrowseRows(res.data.series ?? []), nextCursor: res.data.next_page_cursor };
}
