package service

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRecentRunsCandidateCountUsesMaxWindowForRepositoryFilters(t *testing.T) {
	repository := "https://github.com/apache/arrow-go"

	assert.Equal(t, recentRunsCandidateMax, recentRunsCandidateCount(5, &repository))
	assert.Equal(t, recentRunsCandidateMin, recentRunsCandidateCount(5, nil))
}
