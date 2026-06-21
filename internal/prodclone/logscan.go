package prodclone

import (
	"bufio"
	"errors"
	"io"
	"slices"
	"strings"
	"unicode/utf8"
)

const maxRetainedLogLine = 4096

var blockedWritePatterns = []string{
	"permission denied",
	"cannot execute",
	"read-only transaction",
}

type LogFinding struct {
	LineNumber int    `json:"line_number"`
	Line       string `json:"line"`
	Pattern    string `json:"pattern"`
}

func ScanServerLog(r io.Reader) ([]LogFinding, error) {
	reader := bufio.NewReader(r)

	var findings []LogFinding
	lineNumber := 0
	for {
		_, pattern, ok, err := readLogLine(reader)
		if errors.Is(err, io.EOF) {
			return findings, nil
		}
		if err != nil {
			return nil, err
		}

		lineNumber++
		if ok {
			findings = append(findings, LogFinding{
				LineNumber: lineNumber,
				Line:       safeLogFindingLine(pattern),
				Pattern:    pattern,
			})
		}
	}
}

func matchingBlockedWritePattern(line string) (string, bool) {
	lower := strings.ToLower(line)
	for _, pattern := range blockedWritePatterns {
		if strings.Contains(lower, pattern) {
			return pattern, true
		}
	}
	return "", false
}

func safeLogFindingLine(pattern string) string {
	pattern = safeBlockedWritePattern(pattern)
	if pattern == "" {
		return "blocked-write marker detected"
	}
	return "blocked-write marker detected: " + pattern
}

func safeBlockedWritePattern(pattern string) string {
	if slices.Contains(blockedWritePatterns, pattern) {
		return pattern
	}
	return ""
}

func readLogLine(reader *bufio.Reader) (string, string, bool, error) {
	var retained strings.Builder
	var tail string
	var pattern string
	readAny := false

	for {
		part, err := reader.ReadSlice('\n')
		if len(part) > 0 {
			readAny = true
			if part[len(part)-1] == '\n' {
				part = part[:len(part)-1]
				if len(part) > 0 && part[len(part)-1] == '\r' {
					part = part[:len(part)-1]
				}
			}
			appendRetainedLogPart(&retained, part)
			if pattern == "" {
				pattern, _ = matchingBlockedWritePattern(tail + string(part))
			}
			tail = nextPatternTail(tail, part)
		}

		switch {
		case err == nil:
			return retained.String(), pattern, pattern != "", nil
		case errors.Is(err, bufio.ErrBufferFull):
			continue
		case errors.Is(err, io.EOF):
			if !readAny {
				return "", "", false, io.EOF
			}
			return retained.String(), pattern, pattern != "", nil
		default:
			return "", "", false, err
		}
	}
}

func appendRetainedLogPart(retained *strings.Builder, part []byte) {
	remaining := maxRetainedLogLine - retained.Len()
	if remaining <= 0 {
		return
	}

	text := string(part)
	if len(text) > remaining {
		text = truncateLogLineToLimit(text, remaining)
	}
	retained.WriteString(text)
}

func nextPatternTail(tail string, part []byte) string {
	const maxPatternTail = len("read-only transaction") - 1

	next := strings.ToLower(tail + string(part))
	if len(next) <= maxPatternTail {
		return next
	}
	return next[len(next)-maxPatternTail:]
}

func truncateLogLineToLimit(line string, limit int) string {
	if len(line) <= limit {
		return line
	}

	cut := limit
	for cut > 0 && !utf8.RuneStart(line[cut]) {
		cut--
	}
	if cut == 0 {
		return line[:limit]
	}
	return line[:cut]
}
