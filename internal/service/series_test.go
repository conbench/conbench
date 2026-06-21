package service

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"

	"github.com/conbench/conbench/internal/storage"
)

// membersFromSVS builds a history series with one datum per member, all in unit
// `unit`, at distinct ascending commit timestamps. Each member's single value
// summary is its datum (a one-element best-mode SVS is that element). The series
// is ordered oldest-commit-first, so the last element is the latest member.
func membersFromSVS(svs []float64, unit string) []storage.HistoryRow {
	base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	u := unit
	rows := make([]storage.HistoryRow, len(svs))
	for i, v := range svs {
		ts := base.Add(time.Duration(i) * time.Hour)
		rows[i] = storage.HistoryRow{
			ID:                 "result-" + unit,
			HistoryFingerprint: "fp",
			Timestamp:          ts,
			Unit:               &u,
			Data:               []float64{v},
			CommitSha:          "sha",
			CommitRepository:   "https://github.com/org/repo",
			CommitTimestamp:    &ts,
		}
	}
	return rows
}

// mixedUnitMembers builds a series spanning two units ("s" then "ns"), so the
// series has no single unit and status must be insufficient.
func mixedUnitMembers() []storage.HistoryRow {
	rows := membersFromSVS([]float64{1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.01, 1.20}, "s")
	other := "ns"
	for i := range rows[len(rows)/2:] {
		rows[len(rows)/2+i].Unit = &other
	}
	return rows
}

func TestSeriesStatus(t *testing.T) {
	libTrue := true
	// Status scores the LATEST member against the PRECEDING members' distribution,
	// so the latest is never in its own baseline.

	// regressed: noisy in-band baseline, then a clear worsening jump (less-is-better).
	assert.Equal(t, "regressed",
		seriesStatus(membersFromSVS([]float64{1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.01, 1.20}, "s"), new("s"), &libTrue))
	// improved: same baseline, a clear bettering drop.
	assert.Equal(t, "improved",
		seriesStatus(membersFromSVS([]float64{1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.01, 0.80}, "s"), new("s"), &libTrue))
	// stable: noisy baseline, latest within band.
	assert.Equal(t, "stable",
		seriesStatus(membersFromSVS([]float64{1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.01, 1.005}, "s"), new("s"), &libTrue))
	// insufficient: a single point (no baseline) and a zero-variance baseline both
	// give an uncomputable z (zero stddev).
	assert.Equal(t, "insufficient", seriesStatus(membersFromSVS([]float64{1}, "s"), new("s"), &libTrue))
	assert.Equal(t, "insufficient", seriesStatus(membersFromSVS([]float64{1, 1, 1, 1, 1}, "s"), new("s"), &libTrue))
	// mixed unit -> nil unit -> insufficient.
	assert.Equal(t, "insufficient", seriesStatus(mixedUnitMembers(), nil, nil))
}

func TestSeriesUnit(t *testing.T) {
	// single unit -> that unit
	u := seriesUnit(membersFromSVS([]float64{1, 2, 3}, "s"))
	if assert.NotNil(t, u) {
		assert.Equal(t, "s", *u)
	}
	// mixed -> nil
	assert.Nil(t, seriesUnit(mixedUnitMembers()))
	// empty -> nil
	assert.Nil(t, seriesUnit(nil))
}

func TestSeriesIdentityUnit(t *testing.T) {
	// recognized single unit -> unit + orientation
	unit, lib := seriesIdentityUnit(membersFromSVS([]float64{1, 2}, "s"))
	if assert.NotNil(t, unit) {
		assert.Equal(t, "s", *unit)
	}
	if assert.NotNil(t, lib) {
		assert.True(t, *lib, "seconds: less is better")
	}
	// single but unrecognized unit -> BOTH null: a raw, unvalidated unit is never
	// surfaced as series identity (and status reads insufficient via the nil unit).
	unit, lib = seriesIdentityUnit(membersFromSVS([]float64{1, 2}, "zzz"))
	assert.Nil(t, unit)
	assert.Nil(t, lib)
	// mixed units -> both null
	unit, lib = seriesIdentityUnit(mixedUnitMembers())
	assert.Nil(t, unit)
	assert.Nil(t, lib)
}
