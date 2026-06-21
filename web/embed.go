// Package web embeds the built Svelte SPA (the Vite output under dist) so the
// single conbench binary can serve it without external files. The dist contents
// are produced by `make web-build` (bun run build); on a clean checkout only the
// tracked placeholder is present, which is enough for this package to compile.
package web

import (
	"embed"
	"io/fs"
)

//go:embed all:dist
var distFS embed.FS

// DistFS returns the embedded SPA assets rooted at the dist directory. fs.Sub
// only fails for an invalid path, which the constant "dist" is not, so a non-nil
// error here is an unreachable build invariant.
func DistFS() fs.FS {
	sub, err := fs.Sub(distFS, "dist")
	if err != nil {
		panic(err)
	}
	return sub
}
