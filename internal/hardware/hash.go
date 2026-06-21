// Package hardware ports Conbench's hardware identity hashing (the `hash`
// column used to dedupe hardware and to seed history fingerprints) from
// Python. Behavior is pinned to the original output via golden tests under
// testdata/.
package hardware

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

// MachineHash returns the hardware hash for a machine, ported from the legacy
// Python Machine.generate_hash behavior. It is the machine name joined with the
// GPU count, CPU core/thread counts, and memory size, each formatted as
// Python's str() would (a nil pointer renders as "None").
func MachineHash(name string, gpuCount, cpuCoreCount, cpuThreadCount, memoryBytes *int64) string {
	return name + "-" + pyInt(gpuCount) + "-" + pyInt(cpuCoreCount) + "-" +
		pyInt(cpuThreadCount) + "-" + pyInt(memoryBytes)
}

// ClusterHash returns the hardware hash for a cluster, ported from the legacy
// Python Cluster.generate_hash behavior: the cluster name joined with the MD5
// hex digest of json.dumps(info, sort_keys=True). info is the raw JSON of the
// cluster's "info" object. MD5 matches the values already in the database; it
// is not a security boundary.
func ClusterHash(name string, info json.RawMessage) (string, error) {
	canon, err := pythonJSONString(info)
	if err != nil {
		return "", err
	}
	sum := md5.Sum([]byte(canon))
	return name + "-" + hex.EncodeToString(sum[:]), nil
}

func pyInt(n *int64) string {
	if n == nil {
		return "None"
	}
	return strconv.FormatInt(*n, 10)
}

// pythonJSONString re-serializes raw JSON the way CPython's
// json.dumps(value, sort_keys=True) does: ", " and ": " separators, object keys
// sorted, and non-ASCII escaped (ensure_ascii). Numbers pass through Go's
// json.Number so integers stay exact.
func pythonJSONString(raw json.RawMessage) (string, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return "", err
	}
	var b strings.Builder
	writePythonJSON(&b, v)
	return b.String(), nil
}

func writePythonJSON(b *strings.Builder, v any) {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if x {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case string:
		writePythonString(b, x)
	case json.Number:
		b.WriteString(pyNumber(x))
	case []any:
		b.WriteByte('[')
		for i, e := range x {
			if i > 0 {
				b.WriteString(", ")
			}
			writePythonJSON(b, e)
		}
		b.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteString(", ")
			}
			writePythonString(b, k)
			b.WriteString(": ")
			writePythonJSON(b, x[k])
		}
		b.WriteByte('}')
	}
}

// pyNumber formats a JSON number as CPython would. Integers are emitted
// verbatim; floats are normalized through float64 and given a trailing ".0"
// when whole, matching repr() for the simple decimals that appear in cluster
// info. Exotic float formats (large exponents) are not guaranteed to match.
func pyNumber(n json.Number) string {
	s := n.String()
	if !strings.ContainsAny(s, ".eE") {
		return s // integer: exact
	}
	f, err := n.Float64()
	if err != nil {
		return s
	}
	out := strconv.FormatFloat(f, 'g', -1, 64)
	if !strings.ContainsAny(out, ".eEnN") {
		out += ".0"
	}
	return out
}

// writePythonString writes s as a CPython json string literal with
// ensure_ascii=True: control characters and any non-ASCII rune are escaped as
// \uXXXX (surrogate pairs above U+FFFF); only 0x20..0x7e pass through.
func writePythonString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			switch {
			case r >= 0x20 && r < 0x7f:
				b.WriteRune(r)
			case r > 0xffff:
				r1, r2 := utf16.EncodeRune(r)
				writeUnicodeEscape(b, r1)
				writeUnicodeEscape(b, r2)
			default:
				writeUnicodeEscape(b, r)
			}
		}
	}
	b.WriteByte('"')
}

func writeUnicodeEscape(b *strings.Builder, r rune) {
	const hexdigits = "0123456789abcdef"
	b.WriteString(`\u`)
	b.WriteByte(hexdigits[(r>>12)&0xf])
	b.WriteByte(hexdigits[(r>>8)&0xf])
	b.WriteByte(hexdigits[(r>>4)&0xf])
	b.WriteByte(hexdigits[r&0xf])
}
