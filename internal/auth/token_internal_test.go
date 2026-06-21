package auth

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestEncodeTokenFixedWidth pins the leading-zero edge deterministically: live
// randomness in GenerateToken almost never produces a zero-prefixed value, so
// the panic path that fixed-width padding closes needs explicit byte inputs.
func TestEncodeTokenFixedWidth(t *testing.T) {
	// All-zero bytes are the worst case: big.Int.Text(62) collapses them to
	// "0", so without padding the plaintext would be "cb_0" and plaintext[:8]
	// would panic.
	var zero [32]byte
	assert.Equal(t, "cb_"+strings.Repeat("0", secretLen), encodeToken(zero))

	// Only the last byte set: value 1, the maximal leading-zero payload.
	var one [32]byte
	one[31] = 1
	assert.Equal(t, "cb_"+strings.Repeat("0", secretLen-1)+"1", encodeToken(one))

	// All bytes 0xff is the largest value; it must still fit in secretLen
	// digits (no padding, no overflow of the fixed width).
	var max [32]byte
	for i := range max {
		max[i] = 0xff
	}
	plaintext := encodeToken(max)
	assert.Len(t, plaintext, 3+secretLen)
	assert.Equal(t, "cb_", plaintext[:3])

	// Every encoding is exactly "cb_" + secretLen and safe to slice for the
	// prefix.
	for _, b := range [][32]byte{zero, one, max} {
		assert.Len(t, encodeToken(b), 3+secretLen)
		assert.GreaterOrEqual(t, len(encodeToken(b)), tokenPrefixLen)
	}
}
