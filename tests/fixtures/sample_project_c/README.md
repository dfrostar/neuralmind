# sample_project_c

A small but realistic C project used as a hermetic fixture for the bundled
tree-sitter C extractor (header/impl pairs across auth, users, db, billing, and
api). Mirrors the shape of the other `sample_project_*` fixtures so the parity
gate can compare the built-in backend's symbol coverage against a committed gold
graph. `#include "x.h"` resolves to an `imports_from` edge; `<system>` headers
are external. Macros are intentionally not indexed as symbols (documented MVP
scope).
