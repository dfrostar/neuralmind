# sample_project_cpp

A small but realistic C++ project used as a hermetic fixture for the bundled
tree-sitter C++ extractor — namespaces, classes (with inheritance), member
methods and fields, and out-of-line method definitions across header/impl pairs
(auth, users, db, billing, api). Mirrors the other `sample_project_*` fixtures so
the parity gate can compare the built-in backend's symbol coverage against a
committed gold graph. Local `#include "app/x.hpp"` resolves to an `imports_from`
edge; base classes produce `inherits` edges. Template specialization, macros, and
`#ifdef` evaluation are intentionally out of MVP scope (documented).
