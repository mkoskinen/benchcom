// Test descriptions for benchmark tests
// Maps test_name to human-readable descriptions

export const testDescriptions: Record<string, string> = {
  // PassMark CPU tests
  passmark_cpu_mt: "PassMark CPU Mark - Overall multi-threaded CPU performance score",
  passmark_cpu_single: "PassMark single-thread CPU performance score",
  passmark_integer: "PassMark integer math operations (MOps/s)",
  passmark_float: "PassMark floating point math operations",
  passmark_prime: "PassMark prime number search performance",
  passmark_encryption: "PassMark encryption/decryption performance",
  passmark_compression: "PassMark compression performance",
  passmark_physics: "PassMark extended instructions physics simulation",
  passmark_sse: "PassMark SSE matrix multiplication",

  // PassMark Memory tests
  passmark_memory: "PassMark Memory Mark - Overall memory performance score",
  passmark_mem_read_cached: "PassMark cached memory read throughput",
  passmark_mem_read_uncached: "PassMark uncached memory read throughput",
  passmark_mem_write: "PassMark memory write throughput",
  passmark_mem_latency: "PassMark memory latency (lower is better)",
  passmark_mem_threaded: "PassMark threaded memory operations",

  // PassMark Disk tests
  passmark_disk: "PassMark Disk Mark - Overall disk performance score",
  passmark_disk_seq_read: "PassMark sequential disk read speed",
  passmark_disk_seq_write: "PassMark sequential disk write speed",
  passmark_disk_random: "PassMark random seek read/write operations",

  // Sysbench tests
  sysbench_cpu_st: "Sysbench CPU single-threaded prime number calculation",
  sysbench_cpu_mt: "Sysbench CPU multi-threaded prime number calculation",
  sysbench_memory: "Sysbench memory throughput test (1KB block size)",

  // Other CPU tests
  pi_calculation: "Time to calculate 5000 digits of Pi using bc (lower is better)",

  // Compression tests
  "7zip_st": "7-Zip LZMA compression benchmark, single-threaded",
  "7zip_mt": "7-Zip LZMA compression benchmark, multi-threaded",
  zstd_compress: "Zstd compression speed at level 3",
  zstd_decompress: "Zstd decompression speed",

  // Cryptography tests
  openssl_sha256: "OpenSSL SHA-256 hashing throughput (16KB blocks)",
  openssl_sha512: "OpenSSL SHA-512 hashing throughput (16KB blocks)",
  openssl_aes256: "OpenSSL AES-256-CBC encryption throughput (16KB blocks)",

  // Disk tests
  disk_write: "Sequential disk write speed (1GB file with sync)",
  disk_read: "Sequential disk read speed (1GB, direct I/O)",
};

export function getTestDescription(testName: string): string | undefined {
  return testDescriptions[testName];
}
