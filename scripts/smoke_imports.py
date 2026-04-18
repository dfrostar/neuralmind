"""Import smoke test for runtime package modules."""

import neuralmind
import neuralmind.cli
import neuralmind.compressors
import neuralmind.config
import neuralmind.core
import neuralmind.embedder
import neuralmind.hooks


def main() -> int:
    _ = neuralmind.__version__
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
