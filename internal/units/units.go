// Package units ports Conbench's legacy unit registry: the set of known
// measurement-unit symbols and their less_is_better direction, used by the
// analysis core to orient regressions. Behavior is pinned to the retired Python
// output via golden tests under testdata/.
package units

import "fmt"

// Unit describes a known measurement unit.
type Unit struct {
	Symbol       string
	Long         string
	LessIsBetter bool
}

// known mirrors the legacy Python KNOWN_UNITS set.
var known = map[string]Unit{
	"B":   {Symbol: "B", Long: "bytes", LessIsBetter: true},
	"B/s": {Symbol: "B/s", Long: "bytes per second", LessIsBetter: false},
	"s":   {Symbol: "s", Long: "seconds", LessIsBetter: true},
	"ns":  {Symbol: "ns", Long: "nanoseconds", LessIsBetter: true},
	"i/s": {Symbol: "i/s", Long: "iterations per second", LessIsBetter: false},
}

// Known reports whether symbol is a recognized unit symbol.
func Known(symbol string) bool {
	_, ok := known[symbol]
	return ok
}

// LessIsBetter reports whether a lower value is better for the given unit. It
// returns an error for unrecognized symbols (Python raises KeyError).
func LessIsBetter(symbol string) (bool, error) {
	u, ok := known[symbol]
	if !ok {
		return false, fmt.Errorf("unknown unit symbol %q", symbol)
	}
	return u.LessIsBetter, nil
}

// Longform returns the long name of a unit symbol, erroring for unknown symbols.
func Longform(symbol string) (string, error) {
	u, ok := known[symbol]
	if !ok {
		return "", fmt.Errorf("unknown unit symbol %q", symbol)
	}
	return u.Long, nil
}

// LegacyConvert validates a user-given unit symbol and returns the canonical
// symbol, rewriting the legacy "b/s" to "B/s". Unknown symbols are rejected
// like the retired Python implementation did.
func LegacyConvert(symbol string) (string, error) {
	if symbol == "b/s" {
		return "B/s", nil
	}
	if !Known(symbol) {
		return "", fmt.Errorf("invalid unit string %q", symbol)
	}
	return symbol, nil
}
