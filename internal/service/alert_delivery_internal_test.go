package service

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestEmailAlertDeliveryDeadlineUsesSingleBudget(t *testing.T) {
	now := time.Date(2026, 6, 19, 12, 0, 0, 0, time.UTC)

	t.Run("timeout without parent deadline", func(t *testing.T) {
		deadline, ok := emailAlertDeliveryDeadline(context.Background(), 3*time.Second, now)

		require.True(t, ok)
		assert.Equal(t, now.Add(3*time.Second), deadline)
	})

	t.Run("parent deadline earlier than timeout", func(t *testing.T) {
		parentDeadline := now.Add(2 * time.Second)
		ctx, cancel := context.WithDeadline(context.Background(), parentDeadline)
		defer cancel()

		deadline, ok := emailAlertDeliveryDeadline(ctx, 5*time.Second, now)

		require.True(t, ok)
		assert.Equal(t, parentDeadline, deadline)
	})

	t.Run("timeout earlier than parent deadline", func(t *testing.T) {
		ctx, cancel := context.WithDeadline(context.Background(), now.Add(10*time.Second))
		defer cancel()

		deadline, ok := emailAlertDeliveryDeadline(ctx, 5*time.Second, now)

		require.True(t, ok)
		assert.Equal(t, now.Add(5*time.Second), deadline)
	})

	t.Run("no deadline when timeout disabled and parent lacks deadline", func(t *testing.T) {
		deadline, ok := emailAlertDeliveryDeadline(context.Background(), 0, now)

		require.False(t, ok)
		assert.True(t, deadline.IsZero())
	})

	t.Run("parent deadline when timeout disabled", func(t *testing.T) {
		parentDeadline := now.Add(2 * time.Second)
		ctx, cancel := context.WithDeadline(context.Background(), parentDeadline)
		defer cancel()

		deadline, ok := emailAlertDeliveryDeadline(ctx, 0, now)

		require.True(t, ok)
		assert.Equal(t, parentDeadline, deadline)
	})
}

func TestGithubRepositorySpec(t *testing.T) {
	tests := []struct {
		name    string
		raw     string
		want    string
		wantErr bool
	}{
		{name: "https web url", raw: "https://github.com/org/repo", want: "org/repo"},
		{name: "https with trailing slash", raw: "https://github.com/org/repo/", want: "org/repo"},
		{name: "https clone url with .git", raw: "https://github.com/org/repo.git", want: "org/repo"},
		{name: "ssh clone url", raw: "git@github.com:org/repo", want: "org/repo"},
		{name: "ssh clone url with .git", raw: "git@github.com:org/repo.git", want: "org/repo"},
		{name: "non-github host", raw: "https://gitlab.com/org/repo", wantErr: true},
		{name: "missing repo segment", raw: "https://github.com/org", wantErr: true},
		{name: "bare .git repo name", raw: "https://github.com/org/.git", wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := githubRepositorySpec(tt.raw)
			if tt.wantErr {
				require.Error(t, err)
				return
			}
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}
