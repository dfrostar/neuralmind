"""Build ``index.scip`` for the precision fixture — committed alongside it.

This hand-builds the SCIP index that a tool like ``scip-python`` would emit for
``app.py``: definitions for ``B#handle``, ``A#handle``, and ``run``, plus a
*reference* occurrence to ``A#handle`` inside ``run``'s body. The precision pass
(`neuralmind/precision.py`) decodes this with the same minimal protobuf reader
it uses on real indexes, so the fixture exercises the real code path.

Regenerate with::

    python tests/fixtures/scip_precision/build_index.py

Field numbers match sourcegraph/scip's ``scip.proto`` (Index.documents=2,
Document.relative_path=1/occurrences=2/symbols=3, Occurrence.range=1/symbol=2/
symbol_roles=3/enclosing_range=7).
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
_ROLE_DEFINITION = 0x1


# ----- minimal protobuf encoder ----- #
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _tag(field: int, wt: int) -> bytes:
    return _varint((field << 3) | wt)


def _f_varint(field: int, n: int) -> bytes:
    return _tag(field, 0) + _varint(n)


def _f_len(field: int, data: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(data)) + data


def _f_str(field: int, s: str) -> bytes:
    return _f_len(field, s.encode("utf-8"))


def _packed(field: int, ints: list[int]) -> bytes:
    return _f_len(field, b"".join(_varint(i) for i in ints))


def _occurrence(
    rng: list[int], symbol: str, roles: int, enclosing: list[int] | None = None
) -> bytes:
    msg = _packed(1, rng) + _f_str(2, symbol) + _f_varint(3, roles)
    if enclosing:
        msg += _packed(7, enclosing)
    return msg


def _locate(text: str, needle: str, start: int = 0) -> tuple[int, int, int]:
    """Return (line0, startCol, endCol) of ``needle`` in ``text`` (0-based)."""
    idx = text.index(needle, start)
    line0 = text.count("\n", 0, idx)
    line_start = text.rfind("\n", 0, idx) + 1
    col = idx - line_start
    return line0, col, col + len(needle)


def main() -> None:
    src = (_DIR / "app.py").read_text(encoding="utf-8")
    sym_b = "scip-python python . . app/B#handle()."
    sym_a = "scip-python python . . app/A#handle()."
    sym_run = "scip-python python . . app/run()."

    # Definition name ranges.
    b_def = list(_locate(src, "handle", src.index("class B")))
    a_def = list(_locate(src, "handle", src.index("class A")))
    run_name = list(_locate(src, "run", src.index("def run")))
    # run()'s body range: from its `def` line to the end of the file.
    def_run_line = src.count("\n", 0, src.index("def run"))
    last_line = src.rstrip("\n").count("\n")
    run_body = [def_run_line, 0, last_line, 80]
    # The call site: `a.handle()` inside run → reference to A#handle.
    call_off = src.index("a.handle()")
    ref = list(_locate(src, "handle", call_off))

    occs = [
        _occurrence(b_def, sym_b, _ROLE_DEFINITION),
        _occurrence(a_def, sym_a, _ROLE_DEFINITION),
        _occurrence(run_name, sym_run, _ROLE_DEFINITION, enclosing=run_body),
        _occurrence(ref, sym_a, 0),  # reference (role 0) → A#handle
    ]
    document = _f_str(1, "app.py") + b"".join(_f_len(2, o) for o in occs)
    index = _f_len(2, document)
    (_DIR / "index.scip").write_bytes(index)
    print(f"wrote {(_DIR / 'index.scip')} ({len(index)} bytes)")


if __name__ == "__main__":
    main()
