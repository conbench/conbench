package service

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRound4SigFigs(t *testing.T) {
	cases := []struct {
		in, want float64
	}{
		{0, 0},
		{-10.0, -10.0},
		{1.23456, 1.235},
		{-3.21789, -3.218},
		{123456.0, 123500.0},
		{10.0, 10.0},
	}
	for _, c := range cases {
		assert.InDelta(t, c.want, round4SigFigs(c.in), 1e-9, "round4SigFigs(%v)", c.in)
	}
}
