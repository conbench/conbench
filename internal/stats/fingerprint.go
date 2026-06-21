// Package stats ports Conbench's benchmark analysis logic (history
// fingerprinting, single value summaries, aggregates) from Python. Behavior is
// pinned to the original output via golden tests under testdata/.
package stats

import (
	"crypto/md5"
	"encoding/hex"
)

// HistoryFingerprint returns the identifier of a benchmark result's history
// (the timeseries group of directly comparable results): the MD5 hex digest of
// the case ID, context ID, hardware hash, and repository URL concatenated in
// that order.
//
// Ported from the legacy Python generate_history_fingerprint implementation.
// MD5 is used to match the existing fingerprints in the database; it is not a
// security boundary.
func HistoryFingerprint(caseID, contextID, hardwareHash, repoURL string) string {
	h := md5.New()
	h.Write([]byte(caseID))
	h.Write([]byte(contextID))
	h.Write([]byte(hardwareHash))
	h.Write([]byte(repoURL))
	return hex.EncodeToString(h.Sum(nil))
}
