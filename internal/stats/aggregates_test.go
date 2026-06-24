package stats

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// aggSvsGolden mirrors checked-in references from the retired Python aggregate
// and single-value-summary behavior.
type aggSvsGolden struct {
	Aggregates []struct {
		Samples []float64 `json:"samples"`
		Mean    float64   `json:"mean"`
		Q1      *float64  `json:"q1"`
		Q3      *float64  `json:"q3"`
		Median  *float64  `json:"median"`
		Min     *float64  `json:"min"`
		Max     *float64  `json:"max"`
		Stdev   *float64  `json:"stdev"`
		Iqr     *float64  `json:"iqr"`
	} `json:"aggregates"`
	SVS []struct {
		Data         []*float64 `json:"data"`
		Unit         *string    `json:"unit"`
		HasError     bool       `json:"has_error"`
		Mode         string     `json:"mode"`
		IsFailed     bool       `json:"is_failed"`
		Measurements []float64  `json:"measurements"`
		SVSType      string     `json:"svs_type"`
		SVS          *float64   `json:"svs"`
	} `json:"svs"`
}

func loadAggSvsGolden(t *testing.T) aggSvsGolden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "aggregates_svs.json"))
	require.NoError(t, err, "read golden")
	var g aggSvsGolden
	require.NoError(t, json.Unmarshal(raw, &g), "parse golden")
	require.True(t, len(g.Aggregates) > 0 && len(g.SVS) > 0, "golden file missing aggregate or svs cases")
	return g
}

// closeEnough compares floats within a tolerance loose enough to absorb the
// last bits of numpy's summation but far tighter than any meaningful benchmark
// precision.
func closeEnough(got, want float64) bool {
	return math.Abs(got-want) <= 1e-9+1e-9*math.Abs(want)
}

// optClose compares an optional aggregate (nil means "not computed", which the
// Python oracle emits for samples shorter than three).
func optClose(t *testing.T, name string, got, want *float64) {
	t.Helper()
	switch {
	case got == nil && want == nil:
	case got == nil || want == nil:
		assert.Failf(t, "optional aggregate mismatch", "%s = %v, want %v", name, got, want)
	case !closeEnough(*got, *want):
		assert.Failf(t, "optional aggregate mismatch", "%s = %v, want %v", name, *got, *want)
	}
}

// TestAggregateMatchesNumpyGolden pins Aggregate to numpy's mean/percentile/
// median/std(ddof=1), including the len<3 short-circuit and zero-variance.
func TestAggregateMatchesNumpyGolden(t *testing.T) {
	g := loadAggSvsGolden(t)
	for _, c := range g.Aggregates {
		a := Aggregate(c.Samples)
		assert.Truef(t, closeEnough(a.Mean, c.Mean),
			"samples %v: Mean = %v, want %v", c.Samples, a.Mean, c.Mean)
		optClose(t, "Q1", a.Q1, c.Q1)
		optClose(t, "Q3", a.Q3, c.Q3)
		optClose(t, "Median", a.Median, c.Median)
		optClose(t, "Min", a.Min, c.Min)
		optClose(t, "Max", a.Max, c.Max)
		optClose(t, "Stdev", a.Stdev, c.Stdev)
		optClose(t, "Iqr", a.Iqr, c.Iqr)
	}
}
