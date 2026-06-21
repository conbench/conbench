package api

import (
	"errors"
	"net/http"
	"testing"

	"github.com/danielgtaylor/huma/v2"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestMapReadErrorStatementTimeoutIsActionable422(t *testing.T) {
	err := mapReadError(&pgconn.PgError{Code: "57014", Message: "canceling statement due to statement timeout"})

	var statusErr huma.StatusError
	require.ErrorAs(t, err, &statusErr)
	assert.Equal(t, http.StatusUnprocessableEntity, statusErr.GetStatus())
	assert.Contains(t, err.Error(), "read query timed out")
	assert.NotContains(t, err.Error(), "series")
}

func TestMapReadErrorWrappedStatementTimeoutIsActionable422(t *testing.T) {
	err := mapReadError(errors.Join(
		errors.New("list series"),
		&pgconn.PgError{Code: "57014", Message: "canceling statement due to statement timeout"},
	))

	var statusErr huma.StatusError
	require.ErrorAs(t, err, &statusErr)
	assert.Equal(t, http.StatusUnprocessableEntity, statusErr.GetStatus())
}

func TestMapReadErrorUserCanceledQueryReturnsOriginalError(t *testing.T) {
	pgErr := &pgconn.PgError{Code: "57014", Message: "canceling statement due to user request"}

	err := mapReadError(pgErr)

	assert.Same(t, pgErr, err)
	var statusErr huma.StatusError
	assert.NotErrorAs(t, err, &statusErr)
}
