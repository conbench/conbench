import { formatDate, formatSVS } from "../browse/transform";
import type { SeriesPoint } from "../series/transform";

/** CommitChoice is one selectable row in the benchmark-first compare picker:
 * a single result within a chosen series, labeled by its commit so a human
 * picks "commit A vs commit B" instead of pasting result IDs. */
export interface CommitChoice {
  resultId: string;
  commitHash: string;
  shortCommit: string;
  commitMessage: string;
  dateText: string;
  svsText: string;
}

/** toCommitChoices shapes a series' history points into newest-first rows.
 * Points arrive oldest-first (chart order); the picker shows the most recent
 * commits at the top since those are the likeliest comparison targets. */
export function toCommitChoices(
  points: SeriesPoint[],
  unit: string | null,
  locale?: string,
): CommitChoice[] {
  return [...points]
    .sort((a, b) => b.chartMs - a.chartMs)
    .map((p) => ({
      resultId: p.resultId,
      commitHash: p.commitHash,
      shortCommit: p.commitHash === "" ? "—" : p.commitHash.slice(0, 7),
      commitMessage: p.commitMessage,
      dateText: p.commitTimestampMs === null ? "—" : formatDate(new Date(p.commitTimestampMs).toISOString(), locale),
      svsText: `${formatSVS(p.svs)}${unit === null ? "" : ` ${unit}`}`,
    }));
}

export interface DefaultPair {
  baselineId: string;
  contenderId: string;
}

/** defaultPair preselects the common case — latest commit (contender) against
 * the most recent earlier commit (baseline) — so the page is one click from a
 * comparison. Reruns on the latest commit produce several rows sharing a commit;
 * the baseline skips those so the default compares two distinct commits rather
 * than two results of the same one. Null when no distinct earlier commit exists.
 * Choices are newest first (toCommitChoices output). */
export function defaultPair(choices: CommitChoice[]): DefaultPair | null {
  const [contender] = choices;
  if (contender === undefined) {
    return null;
  }
  const baseline = choices.find(
    (c) => c.commitHash !== "" && c.commitHash !== contender.commitHash,
  );
  if (baseline === undefined) {
    return null;
  }
  return { contenderId: contender.resultId, baselineId: baseline.resultId };
}
