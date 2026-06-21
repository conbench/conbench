package service_test

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/service"
)

// TestSubmitRequestMarshalOmitsAbsentError pins the omitzero behavior: a
// request that never set error marshals without the key, so a marshaled
// success request is not rejected by the error-null check on resubmission.
func TestSubmitRequestMarshalOmitsAbsentError(t *testing.T) {
	b, err := json.Marshal(service.SubmitRequest{RunID: "r1"})
	require.NoError(t, err)
	assert.NotContains(t, string(b), `"error"`)

	withErr := service.SubmitRequest{
		Error: service.JSONObject{Present: true, Value: map[string]any{"oops": true}},
	}
	b, err = json.Marshal(withErr)
	require.NoError(t, err)
	var m map[string]json.RawMessage
	require.NoError(t, json.Unmarshal(b, &m))
	assert.JSONEq(t, `{"oops":true}`, string(m["error"]))
}
