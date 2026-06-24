package commitrepair

import (
	"encoding/base64"
	"encoding/json"
	"errors"
)

// Cursor marks the last inspected candidate in repository, sha scan order.
type Cursor struct {
	Repository string `json:"repository"`
	Sha        string `json:"sha"`
}

// EncodeCursor serializes c as opaque base64url JSON for operator pagination.
func EncodeCursor(c Cursor) (string, error) {
	if err := validateCursor(c); err != nil {
		return "", err
	}
	data, err := json.Marshal(c)
	if err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(data), nil
}

// DecodeCursor parses a cursor produced by EncodeCursor.
func DecodeCursor(encoded string) (Cursor, error) {
	data, err := base64.RawURLEncoding.DecodeString(encoded)
	if err != nil {
		return Cursor{}, err
	}
	var c Cursor
	if err := json.Unmarshal(data, &c); err != nil {
		return Cursor{}, err
	}
	if err := validateCursor(c); err != nil {
		return Cursor{}, err
	}
	return c, nil
}

func validateCursor(c Cursor) error {
	if c.Repository == "" {
		return errors.New("cursor repository is required")
	}
	if c.Sha == "" {
		return errors.New("cursor sha is required")
	}
	return nil
}
