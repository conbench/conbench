package api_test

import (
	"encoding/json"
	"net/http"
	"testing"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
)

func TestHealthPing(t *testing.T) {
	_, tapi := humatest.New(t)
	api.RegisterHealth(tapi)

	resp := tapi.Get("/api/ping")
	require.Equal(t, http.StatusOK, resp.Code, "body = %s", resp.Body.String())
	var out struct {
		Status string `json:"status"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	assert.Equal(t, "ok", out.Status)
}
