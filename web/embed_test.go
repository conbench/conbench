package web_test

import (
	"io/fs"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/web"
)

func TestDistFSReadable(t *testing.T) {
	entries, err := fs.ReadDir(web.DistFS(), ".")
	require.NoError(t, err)
	require.NotEmpty(t, entries, "embedded dist should contain at least the placeholder")
}
