# NeuralMind v4.8.0

**Type:** Minor release

## Other fixes

- **`neuralmind audit export -o` reports what it wrote.** In v4.7.0 and
  earlier it printed the size of the whole audit log, whatever `--since`,
  `--until`, `--category`, `--action` or `--actor` kept, so a filtered export
  over an empty file said "Exported 7 events". It now counts the records it
  writes, and says so when none matched the filters. Export to stdout is
  unchanged.

## Upgrade notes

- `pip install -U neuralmind`. No configuration changes.
