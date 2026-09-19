# Provenance transition

The initial local P20 package was intentionally absence-aware: original P16/P17 real-handoff artifacts could not then be located in bounded local worktrees and logs.

MSI subsequently recovered and transferred the original ZIP. Laptop 1 independently verified the ZIP hash and integrity, `SHA256SUMS.txt`, all 108 manifested artifacts, report and database hashes, immutable SQLite integrity, foreign keys, accepted record, DTO, lineage, dashboard artifacts, and provenance bundle.

This package now uses only verified originals. The historical absence-aware state is preserved here as provenance history rather than silently erased.

Runtime evidence provenance is the verified transferred ZIP. Git preservation provenance is separately `eb4013fa236ab758c6b84e1a3ae02579bbfe488f`.
