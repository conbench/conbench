package units

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type unitsGolden struct {
	Units []struct {
		Symbol       string `json:"symbol"`
		LessIsBetter bool   `json:"less_is_better"`
		Long         string `json:"long"`
	} `json:"units"`
	LegacyConvert []struct {
		Input  string  `json:"input"`
		Output *string `json:"output"`
		Valid  bool    `json:"valid"`
	} `json:"legacy_convert"`
}

func loadUnitsGolden(t *testing.T) unitsGolden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "units.json"))
	require.NoError(t, err, "read golden")
	var g unitsGolden
	require.NoError(t, json.Unmarshal(raw, &g), "parse golden")
	require.True(t, len(g.Units) > 0 && len(g.LegacyConvert) > 0, "golden file missing units or convert cases")
	return g
}

// TestKnownUnitsMatchPythonGolden pins the registry to checked-in references
// from the retired Python unit registry.
func TestKnownUnitsMatchPythonGolden(t *testing.T) {
	g := loadUnitsGolden(t)
	for _, u := range g.Units {
		assert.Truef(t, Known(u.Symbol), "Known(%q) = false, want true", u.Symbol)
		lib, err := LessIsBetter(u.Symbol)
		require.NoErrorf(t, err, "LessIsBetter(%q)", u.Symbol)
		assert.Equalf(t, u.LessIsBetter, lib, "LessIsBetter(%q)", u.Symbol)
		long, err := Longform(u.Symbol)
		require.NoErrorf(t, err, "Longform(%q)", u.Symbol)
		assert.Equalf(t, u.Long, long, "Longform(%q)", u.Symbol)
	}
}

// TestLegacyConvertMatchesPython pins legacy_convert, including the b/s -> B/s
// rewrite and rejection of unknown symbols.
func TestLegacyConvertMatchesPython(t *testing.T) {
	g := loadUnitsGolden(t)
	for _, c := range g.LegacyConvert {
		got, err := LegacyConvert(c.Input)
		if c.Valid {
			require.NoErrorf(t, err, "LegacyConvert(%q)", c.Input)
			assert.Falsef(t, c.Output == nil || got != *c.Output,
				"LegacyConvert(%q) = %q, want %v", c.Input, got, c.Output)
		} else {
			assert.Errorf(t, err, "LegacyConvert(%q) = %q, want error", c.Input, got)
		}
	}
}

// TestRegistryIsExactlyGolden proves the Go registry equals the Python one in
// both directions: the existing tests show every Python symbol is Known (Python
// ⊆ Go); this adds Go ⊆ Python plus a size check, so a stray extra symbol in
// the registry would fail.
func TestRegistryIsExactlyGolden(t *testing.T) {
	g := loadUnitsGolden(t)
	assert.Lenf(t, known, len(g.Units), "registry has %d units, Python golden has %d", len(known), len(g.Units))
	golden := make(map[string]bool, len(g.Units))
	for _, u := range g.Units {
		golden[u.Symbol] = true
	}
	for sym := range known {
		assert.Truef(t, golden[sym], "registry has %q, which is not in the Python golden set", sym)
	}
}

// TestUnknownSymbolsRejected pins the negative paths: an unrecognized symbol is
// not Known and yields errors from LessIsBetter and Longform.
func TestUnknownSymbolsRejected(t *testing.T) {
	for _, sym := range []string{"ms", "foo", "", "S", "B/s "} {
		assert.Falsef(t, Known(sym), "Known(%q) = true, want false", sym)
		_, err := LessIsBetter(sym)
		require.Errorf(t, err, "LessIsBetter(%q): want error, got nil", sym)
		_, err = Longform(sym)
		assert.Errorf(t, err, "Longform(%q): want error, got nil", sym)
	}
}
