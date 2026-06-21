package hardware

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type machineCase struct {
	Name           string `json:"name"`
	GpuCount       *int64 `json:"gpu_count"`
	CPUCoreCount   *int64 `json:"cpu_core_count"`
	CPUThreadCount *int64 `json:"cpu_thread_count"`
	MemoryBytes    *int64 `json:"memory_bytes"`
	Hash           string `json:"hash"`
}

type clusterCase struct {
	Name       string          `json:"name"`
	Info       json.RawMessage `json:"info"`
	PythonJSON string          `json:"python_json"`
	Hash       string          `json:"hash"`
}

func loadHardwareGolden(t *testing.T) ([]machineCase, []clusterCase) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "hardware_hash.json"))
	require.NoError(t, err, "read golden")
	var g struct {
		Machines []machineCase `json:"machines"`
		Clusters []clusterCase `json:"clusters"`
	}
	require.NoError(t, json.Unmarshal(raw, &g), "parse golden")
	require.True(t, len(g.Machines) > 0 && len(g.Clusters) > 0, "golden file missing machines or clusters")
	return g.Machines, g.Clusters
}

// TestMachineHashMatchesPythonGolden pins MachineHash to hardware.py:Machine.generate_hash.
func TestMachineHashMatchesPythonGolden(t *testing.T) {
	machines, _ := loadHardwareGolden(t)
	for _, m := range machines {
		got := MachineHash(m.Name, m.GpuCount, m.CPUCoreCount, m.CPUThreadCount, m.MemoryBytes)
		assert.Equalf(t, m.Hash, got, "MachineHash(%q, ...)", m.Name)
	}
}

// TestClusterCanonicalJSONMatchesPython pins the internal serializer to
// json.dumps(info, sort_keys=True) byte-for-byte.
func TestClusterCanonicalJSONMatchesPython(t *testing.T) {
	_, clusters := loadHardwareGolden(t)
	for _, c := range clusters {
		got, err := pythonJSONString(c.Info)
		require.NoErrorf(t, err, "%s: pythonJSONString", c.Name)
		assert.Equalf(t, c.PythonJSON, got, "%s: canonical JSON", c.Name)
	}
}

// TestClusterHashMatchesPythonGolden pins ClusterHash to hardware.py:Cluster.generate_hash.
func TestClusterHashMatchesPythonGolden(t *testing.T) {
	_, clusters := loadHardwareGolden(t)
	for _, c := range clusters {
		got, err := ClusterHash(c.Name, c.Info)
		require.NoErrorf(t, err, "%s: ClusterHash", c.Name)
		assert.Equalf(t, c.Hash, got, "%s: ClusterHash", c.Name)
	}
}
