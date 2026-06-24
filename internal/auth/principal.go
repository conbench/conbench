package auth

// Principal is the authenticated identity of a request. UserID is the
// api_token/session user; it is empty for the static operator token and for
// auth-disabled mode, neither of which is attributable to a user. Endpoints
// that own user data (token CRUD) require IsUser.
type Principal struct {
	UserID string
}

// IsUser reports whether the principal is attributable to a specific user.
func (p Principal) IsUser() bool { return p.UserID != "" }
