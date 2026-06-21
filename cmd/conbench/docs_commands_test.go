package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/spf13/cobra"
)

func TestDocumentedConbenchCommandsResolveAgainstCobra(t *testing.T) {
	root := newRootCommand(ioDiscard(), ioDiscard())
	sources := documentedConbenchCommandSources(t)

	require.NotEmpty(t, sources)
	assert.NoError(t, validateDocumentedConbenchCommands(root, sources))
}

func TestDocumentedConbenchCommandsRejectUnknownNestedCommand(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "quickstart.md")
	writeTestFile(t, doc, "# Quickstart\n\nRun `conbench results slubmit result.json --server URL`.\n")
	root := newRootCommand(ioDiscard(), ioDiscard())

	err := validateDocumentedConbenchCommands(root, []string{doc})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "quickstart.md")
	assert.Contains(t, err.Error(), "conbench results slubmit")
}

func TestDocumentedConbenchCommandsRejectUnknownSecondCommand(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "quickstart.md")
	writeTestFile(
		t,
		doc,
		"# Quickstart\n\nRun `conbench results submit result.json --server URL && conbench ci raport --server URL`.\n",
	)
	root := newRootCommand(ioDiscard(), ioDiscard())

	err := validateDocumentedConbenchCommands(root, []string{doc})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "quickstart.md")
	assert.Contains(t, err.Error(), "conbench ci raport")
}

func ioDiscard() *bytes.Buffer {
	return &bytes.Buffer{}
}

func documentedConbenchCommandSources(t *testing.T) []string {
	t.Helper()

	root := filepath.Join("..", "..")
	sources := []string{
		filepath.Join(root, "README.md"),
		filepath.Join(root, "sdk", "python", "README.md"),
	}
	for _, pattern := range []string{
		filepath.Join(root, "docs", "site", "*.md"),
		filepath.Join(root, "docs", "site", "migration", "*.md"),
	} {
		matches, err := filepath.Glob(pattern)
		require.NoError(t, err)
		sources = append(sources, matches...)
	}
	return sources
}

type documentedConbenchCommand struct {
	line int
	raw  string
	args []string
}

var markdownInlineCodeRE = regexp.MustCompile("`([^`\\n]+)`")

func validateDocumentedConbenchCommands(root *cobra.Command, sources []string) error {
	for _, source := range sources {
		data, err := os.ReadFile(source)
		if err != nil {
			return fmt.Errorf("read %s: %w", source, err)
		}
		for _, command := range documentedConbenchCommands(string(data)) {
			if err := validateDocumentedConbenchCommand(root, command); err != nil {
				return fmt.Errorf("%s:%d: %w", filepath.Base(source), command.line, err)
			}
		}
	}
	return nil
}

func documentedConbenchCommands(markdown string) []documentedConbenchCommand {
	var commands []documentedConbenchCommand
	for idx, line := range strings.Split(markdown, "\n") {
		lineNo := idx + 1
		commands = append(commands, extractDocumentedConbenchCommands(line, lineNo)...)
		for _, match := range markdownInlineCodeRE.FindAllStringSubmatch(line, -1) {
			commands = append(commands, extractDocumentedConbenchCommands(match[1], lineNo)...)
		}
	}
	return commands
}

func extractDocumentedConbenchCommands(text string, line int) []documentedConbenchCommand {
	tokens := shellishFields(text)
	var commands []documentedConbenchCommand
	for len(tokens) > 0 {
		var segment []string
		segment, tokens = nextShellSegment(tokens)
		if command, ok := extractDocumentedConbenchCommandSegment(segment, line); ok {
			commands = append(commands, command)
		}
	}
	return commands
}

func extractDocumentedConbenchCommandSegment(tokens []string, line int) (documentedConbenchCommand, bool) {
	var zero documentedConbenchCommand
	if len(tokens) == 0 {
		return zero, false
	}
	idx := 0
	if tokens[idx] == "$" {
		idx++
	}
	for idx < len(tokens) && isShellAssignment(tokens[idx]) {
		idx++
	}
	if idx < len(tokens) && tokens[idx] == "env" {
		idx++
		for idx < len(tokens) && isShellAssignment(tokens[idx]) {
			idx++
		}
	}
	if idx >= len(tokens) || !isConbenchBinary(tokens[idx]) {
		return zero, false
	}

	args := make([]string, 0, len(tokens)-idx-1)
	for _, token := range tokens[idx+1:] {
		cleaned := cleanDocCommandToken(token)
		if cleaned == "" {
			continue
		}
		args = append(args, cleaned)
	}
	raw := "conbench"
	if len(args) > 0 {
		raw += " " + strings.Join(args, " ")
	}
	return documentedConbenchCommand{line: line, raw: raw, args: args}, true
}

func nextShellSegment(tokens []string) ([]string, []string) {
	for index, token := range tokens {
		if isShellSeparator(token) {
			return tokens[:index], tokens[index+1:]
		}
	}
	return tokens, nil
}

func validateDocumentedConbenchCommand(root *cobra.Command, command documentedConbenchCommand) error {
	current := root
	path := []string{"conbench"}
	for _, arg := range command.args {
		if arg == "" {
			continue
		}
		if strings.HasPrefix(arg, "-") {
			break
		}
		child := commandChild(current, arg)
		if child != nil {
			current = child
			path = append(path, arg)
			continue
		}
		if len(commandChildren(current)) > 0 && !isDocArgumentToken(arg) {
			return fmt.Errorf("unknown documented command %q from %q", strings.Join(append(path, arg), " "), command.raw)
		}
		break
	}
	return nil
}

func commandChild(cmd *cobra.Command, name string) *cobra.Command {
	for _, child := range commandChildren(cmd) {
		if child.Name() == name {
			return child
		}
	}
	return nil
}

func commandChildren(cmd *cobra.Command) []*cobra.Command {
	children := make([]*cobra.Command, 0, len(cmd.Commands()))
	for _, child := range cmd.Commands() {
		if !child.Hidden {
			children = append(children, child)
		}
	}
	return children
}

func shellishFields(text string) []string {
	text = strings.TrimSpace(text)
	text = strings.TrimPrefix(text, "$ ")
	text = strings.ReplaceAll(text, "\\", " ")
	for _, separator := range []string{"&&", "||", ";", "|"} {
		text = strings.ReplaceAll(text, separator, " "+separator+" ")
	}
	if text == "" {
		return nil
	}
	return strings.Fields(text)
}

func isShellAssignment(token string) bool {
	token = strings.TrimSpace(token)
	eq := strings.IndexByte(token, '=')
	if eq <= 0 {
		return false
	}
	name := token[:eq]
	for idx, r := range name {
		if r == '_' || (r >= 'A' && r <= 'Z') || (idx > 0 && r >= '0' && r <= '9') {
			continue
		}
		return false
	}
	return true
}

func isConbenchBinary(token string) bool {
	token = cleanDocCommandToken(token)
	return token == "conbench" || token == "./bin/conbench" || strings.HasSuffix(token, "/conbench")
}

func cleanDocCommandToken(token string) string {
	token = strings.TrimSpace(token)
	token = strings.Trim(token, `"'`)
	token = strings.TrimSuffix(token, ",")
	token = strings.TrimSuffix(token, "\\")
	return strings.TrimSpace(token)
}

func isShellSeparator(token string) bool {
	return token == ";" || token == "&&" || token == "||" || token == "|"
}

func isDocArgumentToken(token string) bool {
	if token == "..." || strings.Contains(token, "...") {
		return true
	}
	if strings.HasPrefix(token, "<") || strings.HasPrefix(token, "$") {
		return true
	}
	for _, r := range token {
		if r < 'A' || r > 'Z' {
			return false
		}
	}
	return token != ""
}

func writeTestFile(t *testing.T, path string, contents string) {
	t.Helper()
	require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o755))
	require.NoError(t, os.WriteFile(path, []byte(contents), 0o644))
}
