//go:build ignore

// Command openapi_emit writes the backend OpenAPI document to stdout for the
// codegen pipeline. It imports only the server spec package so codegen can
// refresh generated clients even when the main CLI's generated-client imports
// are temporarily stale.
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/conbench/conbench/internal/server"
)

func main() {
	downgrade := flag.Bool("downgrade", false, "emit the OpenAPI 3.0 compatibility document")
	flag.Parse()

	emit := server.OpenAPISpec
	if *downgrade {
		emit = server.OpenAPISpec30
	}
	spec, err := emit()
	if err != nil {
		fmt.Fprintln(os.Stderr, "openapi_emit:", err)
		os.Exit(1)
	}
	if _, err := os.Stdout.Write(spec); err != nil {
		fmt.Fprintln(os.Stderr, "openapi_emit:", err)
		os.Exit(1)
	}
}
