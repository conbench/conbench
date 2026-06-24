-- name: GetHardwareByNaturalKey :one
-- Dedup on the natural hardware columns, NOT on the (non-unique, derived) hash.
-- IS NOT DISTINCT FROM is NULL-safe, so this keys both machines (machine columns
-- set, info/optional_info NULL) and clusters (info set, machine columns NULL)
-- the same way the legacy filter_by(**hardware_info) get_or_create does.
SELECT id FROM hardware
WHERE type = $1
  AND name = $2
  AND architecture_name IS NOT DISTINCT FROM $3
  AND kernel_name IS NOT DISTINCT FROM $4
  AND os_name IS NOT DISTINCT FROM $5
  AND os_version IS NOT DISTINCT FROM $6
  AND cpu_model_name IS NOT DISTINCT FROM $7
  AND cpu_l1d_cache_bytes IS NOT DISTINCT FROM $8
  AND cpu_l1i_cache_bytes IS NOT DISTINCT FROM $9
  AND cpu_l2_cache_bytes IS NOT DISTINCT FROM $10
  AND cpu_l3_cache_bytes IS NOT DISTINCT FROM $11
  AND cpu_core_count IS NOT DISTINCT FROM $12
  AND cpu_thread_count IS NOT DISTINCT FROM $13
  AND cpu_frequency_max_hz IS NOT DISTINCT FROM $14
  AND memory_bytes IS NOT DISTINCT FROM $15
  AND gpu_count IS NOT DISTINCT FROM $16
  AND gpu_product_names IS NOT DISTINCT FROM $17
  AND info IS NOT DISTINCT FROM $18
  AND optional_info IS NOT DISTINCT FROM $19;

-- name: InsertHardware :one
-- ON CONFLICT targets the unique machine tuple (hardware_index), backstopping
-- the race for machines. Clusters have NULL machine columns (NULLs are distinct
-- in the index) so they never conflict here; their dedup is the prior SELECT.
INSERT INTO hardware (
  id, type, name, hash,
  architecture_name, kernel_name, os_name, os_version, cpu_model_name,
  cpu_l1d_cache_bytes, cpu_l1i_cache_bytes, cpu_l2_cache_bytes, cpu_l3_cache_bytes,
  cpu_core_count, cpu_thread_count, cpu_frequency_max_hz, memory_bytes,
  gpu_count, gpu_product_names, info, optional_info
)
VALUES (
  $1, $2, $3, $4,
  $5, $6, $7, $8, $9,
  $10, $11, $12, $13,
  $14, $15, $16, $17,
  $18, $19, $20, $21
)
ON CONFLICT (
  name, architecture_name, kernel_name, os_name, os_version, cpu_model_name,
  cpu_l1d_cache_bytes, cpu_l1i_cache_bytes, cpu_l2_cache_bytes, cpu_l3_cache_bytes,
  cpu_core_count, cpu_thread_count, cpu_frequency_max_hz, memory_bytes,
  gpu_count, gpu_product_names
) DO NOTHING
RETURNING id;
