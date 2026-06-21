package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math/big"
	"strings"
)

// tokenPrefixLen is how much of the plaintext is stored for display (the
// api_token.token_prefix column); it cannot be recovered from the hash later.
const tokenPrefixLen = 8

// secretLen is the fixed width of the base62 payload: 62^43 > 2^256, so 43
// digits hold any 32-byte value. Left-padding to it keeps every plaintext the
// same length even when the random bytes start with zeros.
const secretLen = 43

// Token is a freshly minted API token. Plaintext is shown to the user exactly
// once; only Hash and Prefix are stored.
type Token struct {
	Plaintext string
	Hash      string
	Prefix    string
}

// GenerateToken mints a token: "cb_" + 32 bytes from crypto/rand,
// base62-encoded and left-padded to a fixed width. The 256 bits of entropy
// make a fast unsalted hash the correct storage form (no bcrypt/argon2).
func GenerateToken() (Token, error) {
	var b [32]byte
	if _, err := rand.Read(b[:]); err != nil {
		return Token{}, fmt.Errorf("generate token: %w", err)
	}
	plaintext := encodeToken(b)
	return Token{
		Plaintext: plaintext,
		Hash:      HashToken(plaintext),
		Prefix:    plaintext[:tokenPrefixLen],
	}, nil
}

// encodeToken formats 32 random bytes as "cb_" + a base62 payload left-padded
// to secretLen. Padding is what makes the prefix slice safe: base62 drops
// leading zero bytes, so without it an all-zero or zero-prefixed value would
// produce a plaintext shorter than tokenPrefixLen.
func encodeToken(b [32]byte) string {
	secret := new(big.Int).SetBytes(b[:]).Text(62)
	return "cb_" + strings.Repeat("0", secretLen-len(secret)) + secret
}

// HashToken returns the stored form of a token: hex SHA-256 over the full
// plaintext. Verification recomputes this and looks the row up by it.
func HashToken(plaintext string) string {
	sum := sha256.Sum256([]byte(plaintext))
	return hex.EncodeToString(sum[:])
}
