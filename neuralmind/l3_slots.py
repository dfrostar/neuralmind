"""l3_slots.py — how the four L3 slots are spent (v4.6.0, spec 7).

L3 renders the top four search hits. On real repositories those four slots
went to two to four distinct files, a doc ranked first in most answers even
for "how does X work" questions, and hub docs (a wiki page, the changelog)
took a slot in most of them. Each pass here targets one of those patterns. Each
is behind its own flag, and kept on by default only if the multi-repo eval
(``evals/retrieval``) says so:

* ``NEURALMIND_L3_PER_FILE=2`` — **diversify by file.** At most N hits per
  file, refilled from the next-best candidates of the same search.
* ``NEURALMIND_DOC_HANDOFF=1`` — **doc-to-code hand-off.** A doc hit that
  names a code file or symbol (``app/billing.py``, ``apply_discount()``)
  brings that file's best-matching symbol into contention.
* ``NEURALMIND_HUB_DAMPEN=1`` — **hub dampening.** Files that turn up in more
  than ~15% of answers are down-weighted by their inverse document
  frequency, with a floor so a hub that is the only match still wins.
* ``NEURALMIND_BM25_CODE=1`` — **symbol-name lexical pass.** The default
  backend's BM25 index holds only document text; this adds a second index
  over symbol names, their files and docstrings, fused by RRF.

With every flag unset, nothing here runs and L3 is unchanged.

One pass is on by default (v4.11.1): **roles**, at the end of this module.
Indexed from its root, a repository's tests, examples and docs compete with
its own code for the four slots, and they often win: a test repeats the
names of the code it tests, an example script uses the very words of a
question about the feature it demonstrates, and a doc heading is a short,
question-like match. ``NEURALMIND_L3_ROLES=0`` turns it off.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PER_FILE_ENV = "NEURALMIND_L3_PER_FILE"
HANDOFF_ENV = "NEURALMIND_DOC_HANDOFF"
HUB_ENV = "NEURALMIND_HUB_DAMPEN"
CODE_BM25_ENV = "NEURALMIND_BM25_CODE"
UNIFIED_BM25_ENV = "NEURALMIND_BM25_UNIFIED"
INTENT_POOL_ENV = "NEURALMIND_INTENT_POOL"
ROLES_ENV = "NEURALMIND_L3_ROLES"

# A file counts as a hub above this share of answers.
HUB_SHARE = 0.15
# ...and more than this multiple of the share an average file gets by chance.
HUB_CHANCE_MULTIPLE = 3.0
# A hub's score never drops below this fraction of what it was.
HUB_FLOOR = 0.5
# Below this many logged queries the log is too thin; fall back to probes.
HUB_MIN_QUERIES = 20
HUB_LOG_WINDOW = 200
HUB_PROBES = 60
HUB_STATS_FILE = "hub_stats.json"
CODE_BM25_FILE = "bm25_code_index.json"
UNIFIED_BM25_FILE = "bm25_unified_index.json"

# A hand-off candidate ranks just below the doc hit that named it.
HANDOFF_FACTOR = 0.9
HANDOFF_MAX = 2

_DOC_SUFFIXES = (".md", ".markdown", ".rst", ".txt", ".org", ".mdx")
_CODE_SUFFIXES = (
    "py ts tsx js jsx mjs cjs go rs java kt rb php cs c h cpp hpp cc swift scala m mm lua sh"
).split()
_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.(?:" + "|".join(_CODE_SUFFIXES) + r"))\b"
)
_IDENT_RE = re.compile(
    r"`([A-Za-z_][\w.]*)(?:\(\))?`|\b([a-z_][a-z0-9]*_[a-z0-9_]+)\(\)|\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b"
)
_WORD_RE = re.compile(r"[A-Za-z][a-z0-9]+|[A-Z]+(?![a-z])|\d+")
_STOP = frozenset(
    "the a an of to in on for and or is are how does do what where which when why with "
    "by from that this it be as at get set".split()
)


# --------------------------------------------------------------------------- #
# Flags
# --------------------------------------------------------------------------- #
def per_file_cap() -> int:
    """Max hits per file in L3; 0 means no cap (the default)."""
    try:
        return max(0, int(os.environ.get(PER_FILE_ENV, "0") or 0))
    except ValueError:
        return 0


def _on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def handoff_enabled() -> bool:
    return _on(HANDOFF_ENV)


def hub_dampening_enabled() -> bool:
    return _on(HUB_ENV)


def code_bm25_enabled() -> bool:
    return _on(CODE_BM25_ENV)


def scoped_file(filename: str, scope: str | None) -> str:
    """The cache file for an index of ``scope``: ``name.<scope>.ext``, or as is for 'all'.

    A ``build --scope docs`` must not overwrite the index a default query reads.
    """
    if not scope or scope == "all":
        return filename
    stem, dot, ext = filename.rpartition(".")
    return f"{stem}.{scope}.{ext}" if dot else f"{filename}.{scope}"


def generation_key(scope: str | None = "all") -> str:
    """The ``build_status.json`` key that stamps the index of ``scope``."""
    return "index_generation" if not scope or scope == "all" else f"index_generation.{scope}"


def index_scope(embedder: Any) -> str:
    """The scope a backend indexes ('all' for backends without scopes)."""
    return getattr(embedder, "scope", None) or "all"


def unified_bm25_enabled() -> bool:
    """On by default since v4.6.0; ``NEURALMIND_BM25_UNIFIED=0`` restores v4.5."""
    return os.environ.get(UNIFIED_BM25_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


def intent_pool_enabled() -> bool:
    return _on(INTENT_POOL_ENV)


def roles_enabled() -> bool:
    """On by default since v4.11.1; ``NEURALMIND_L3_ROLES=0`` restores v4.11.0."""
    return os.environ.get(ROLES_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


def any_slot_pass_enabled() -> bool:
    return (
        bool(per_file_cap())
        or handoff_enabled()
        or hub_dampening_enabled()
        or intent_pool_enabled()
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def source_file(hit: dict) -> str:
    meta = hit.get("metadata") or {}
    return str(meta.get("source_file") or "").replace("\\", "/")


def is_doc_hit(hit: dict) -> bool:
    meta = hit.get("metadata") or {}
    return meta.get("file_type") == "document" or source_file(hit).lower().endswith(_DOC_SUFFIXES)


def words(text: str) -> set[str]:
    """Lowercase word set, splitting camelCase and snake_case."""
    out = {w.lower() for w in _WORD_RE.findall(text or "")}
    return {w for w in out if len(w) > 1 and w not in _STOP}


# --------------------------------------------------------------------------- #
# Node catalog: the index's nodes by file and by label
# --------------------------------------------------------------------------- #
class NodeCatalog:
    """Every indexed node, grouped for the hand-off and the code BM25 pass."""

    def __init__(self, nodes: list[dict]):
        self.by_id: dict[str, dict] = {}
        self.by_file: dict[str, list[dict]] = {}
        self.by_name: dict[str, list[dict]] = {}
        for node in nodes:
            nid = str(node.get("id") or "")
            if not nid:
                continue
            meta = dict(node.get("metadata") or {})
            meta.setdefault("label", node.get("label") or nid)
            meta.setdefault("node_id", nid)
            entry = {
                "id": nid,
                "document": node.get("content_text") or node.get("document") or "",
                "metadata": meta,
            }
            self.by_id[nid] = entry
            sf = str(meta.get("source_file") or "").replace("\\", "/")
            if sf:
                self.by_file.setdefault(sf, []).append(entry)
            name = _bare_name(str(meta.get("label") or ""))
            if name:
                self.by_name.setdefault(name.lower(), []).append(entry)
        self.files = sorted(self.by_file)

    @classmethod
    def from_embedder(cls, embedder: Any) -> NodeCatalog | None:
        getter = getattr(embedder, "get_all_nodes", None)
        if not callable(getter):
            return None
        try:
            return cls(getter() or [])
        except Exception:
            logger.debug("node catalog unavailable", exc_info=True)
            return None

    def resolve_path(self, mention: str) -> str | None:
        """The indexed file a path mention refers to (exact, then by suffix)."""
        mention = mention.replace("\\", "/").lstrip("./")
        if mention in self.by_file:
            return mention
        matches = [f for f in self.files if f.endswith("/" + mention)]
        return matches[0] if len(matches) == 1 else None

    def code_nodes(self, rel: str) -> list[dict]:
        return [
            n
            for n in self.by_file.get(rel, [])
            if (n["metadata"].get("file_type") or "") in ("code", "rationale")
        ]


def _bare_name(label: str) -> str:
    """``Foo.bar()`` → ``bar``; ``post_comment()`` → ``post_comment``."""
    label = label.strip().rstrip("()").strip()
    if not label or " " in label:
        return ""
    return label.rsplit(".", 1)[-1]


# --------------------------------------------------------------------------- #
# Item 2: doc-to-code hand-off
# --------------------------------------------------------------------------- #
def mentions(text: str) -> tuple[list[str], list[str]]:
    """Code paths and identifiers a doc passage names, in order of appearance."""
    paths = list(dict.fromkeys(m.group(1) for m in _PATH_RE.finditer(text or "")))
    idents: list[str] = []
    for m in _IDENT_RE.finditer(text or ""):
        name = next(g for g in m.groups() if g)
        if "/" in name or name.lower().endswith(tuple("." + s for s in _CODE_SUFFIXES)):
            continue
        name = name.rsplit(".", 1)[-1]
        if len(name) >= 4 and name not in idents:
            idents.append(name)
    return paths, idents


def _same_word(a: str, b: str) -> bool:
    """``refunds``/``refund``, ``issued``/``issue``: one is a 4+ letter prefix of the other."""
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 4 and long_.startswith(short[: max(4, len(short) - 1)])


def best_symbol(nodes: list[dict], query_words: set[str], prefer: str = "") -> dict | None:
    """The node of one file that best matches the query (or a named symbol)."""
    if not nodes:
        return None
    if prefer:
        for node in nodes:
            if _bare_name(str(node["metadata"].get("label") or "")).lower() == prefer.lower():
                return node

    def overlap(node: dict) -> tuple[int, int]:
        meta = node["metadata"]
        text = f"{meta.get('label', '')} {node.get('document', '')[:200]}"
        own = words(text)
        # Prefer real symbols over the file node and docstrings on a tie.
        kind = 1 if meta.get("file_type") == "code" and "(" in str(meta.get("label", "")) else 0
        return (sum(1 for q in query_words if any(_same_word(q, w) for w in own)), kind)

    return max(nodes, key=overlap)


def handoff_candidates(
    hits: list[dict], query: str, catalog: NodeCatalog | None, limit: int = HANDOFF_MAX
) -> list[dict]:
    """Code nodes named by the doc hits, scored just below the doc that named them."""
    if catalog is None:
        return []
    present = {h.get("id") for h in hits}
    seen_files = {source_file(h) for h in hits if not is_doc_hit(h)}
    qwords = words(query)
    out: list[dict] = []
    for hit in hits:
        if len(out) >= limit:
            break
        if not is_doc_hit(hit):
            continue
        text = f"{hit.get('document', '')} {(hit.get('metadata') or {}).get('label', '')}"
        paths, idents = mentions(text)
        targets: list[tuple[str, str]] = []
        for p in paths:
            rel = catalog.resolve_path(p)
            if rel:
                targets.append((rel, ""))
        for ident in idents:
            for node in catalog.by_name.get(ident.lower(), [])[:1]:
                sf = source_file(node)
                if sf and not sf.lower().endswith(_DOC_SUFFIXES):
                    targets.append((sf, ident))
        for rel, prefer in targets:
            if len(out) >= limit:
                break
            if rel in seen_files:
                continue
            node = best_symbol(catalog.code_nodes(rel), qwords, prefer)
            if node is None or node["id"] in present:
                continue
            cand = {
                "id": node["id"],
                "document": node.get("document", ""),
                "metadata": dict(node["metadata"]),
                "score": float(hit.get("score") or 0.0) * HANDOFF_FACTOR,
                "_handoff_from": hit.get("id"),
            }
            out.append(cand)
            present.add(node["id"])
            seen_files.add(rel)
    return out


# --------------------------------------------------------------------------- #
# Item 3: hub dampening
# --------------------------------------------------------------------------- #
def _answer_files_from_log(project: Path) -> list[set[str]]:
    path = Path(project) / ".neuralmind" / "recent_queries.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-HUB_LOG_WINDOW:]
    except OSError:
        return []
    answers: list[set[str]] = []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        files = {
            str(h.get("source_file") or "").replace("\\", "/")
            for h in (rec.get("top_hits") or [])[:4]
        }
        files.discard("")
        if files:
            answers.append(files)
    return answers


def _answer_files_from_probes(embedder: Any, catalog: NodeCatalog) -> list[set[str]]:
    """Self-generated traffic: search sampled symbol names, note the *other* files.

    Used until the query log has enough real answers. Probes are spread
    round-robin across files (one symbol per file per round, hash-ordered),
    and the probed symbol's own file is not counted: a module returned for
    its own symbols is doing its job; a doc returned for everyone else's is a
    hub. Sampling per symbol instead would make big files look like hubs.
    """
    import hashlib

    def key(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    per_file: dict[str, list[str]] = {}
    for node in catalog.by_id.values():
        meta = node["metadata"]
        label = str(meta.get("label") or "")
        if meta.get("file_type") == "code" and "(" in label:
            per_file.setdefault(source_file(node), []).append(label)
    queues = {f: sorted(set(v), key=key) for f, v in per_file.items() if f}
    probes: list[tuple[str, str]] = []
    files = sorted(queues, key=key)
    while files and len(probes) < HUB_PROBES:
        for f in list(files):
            if not queues[f]:
                files.remove(f)
                continue
            probes.append((f, queues[f].pop(0)))
            if len(probes) >= HUB_PROBES:
                break

    answers: list[set[str]] = []
    for own, name in probes:
        probe = " ".join(sorted(words(name))) or name
        try:
            hits = embedder.search(probe, n=4)
        except Exception:
            continue
        files_hit = {source_file(h) for h in hits or []} - {"", own}
        answers.append(files_hit)
    return answers


class HubStats:
    """Share of answers each file appears in, and the dampening factor it earns.

    A hub is a file that turns up far more often than chance: above
    ``HUB_SHARE`` (15%) of answers *and* above ``HUB_CHANCE_MULTIPLE`` times
    the share an average file would get. On an 18-file library every file is
    in ~22% of four-file answers by chance alone, so a fixed 15% bar would
    mark most of the repository.
    """

    def __init__(self, answers: list[set[str]], source: str, n_files: int = 0):
        self.n = len(answers)
        self.source = source
        self.df = Counter(f for files in answers for f in files)
        # Leave out the answer itself: a probe's own file is never counted.
        files = max(n_files - (1 if source == "probes" else 0), len(self.df), 1)
        per_answer = sum(len(a) for a in answers) / self.n if self.n else 0.0
        self.threshold = max(HUB_SHARE, HUB_CHANCE_MULTIPLE * per_answer / files)

    def share(self, rel: str) -> float:
        return self.df.get(rel, 0) / self.n if self.n else 0.0

    def factor(self, rel: str) -> float:
        """1.0 below the hub threshold; IDF-scaled above it, never below the floor."""
        if self.n == 0 or self.share(rel) <= self.threshold:
            return 1.0
        idf = math.log((self.n + 1) / (self.df[rel] + 1))
        ref = math.log((self.n + 1) / (self.threshold * self.n + 1))
        if ref <= 0:
            return HUB_FLOOR
        return max(HUB_FLOOR, min(1.0, idf / ref))

    def hubs(self) -> list[tuple[str, float]]:
        return sorted(
            ((f, self.share(f)) for f in self.df if self.share(f) > self.threshold),
            key=lambda kv: -kv[1],
        )

    @classmethod
    def load(cls, project: Path, embedder: Any, catalog: NodeCatalog | None) -> HubStats:
        n_files = len(catalog.files) if catalog is not None else 0
        answers = _answer_files_from_log(project)
        if len(answers) >= HUB_MIN_QUERIES:
            return cls(answers, "query log", n_files)
        cache = Path(project) / ".neuralmind" / HUB_STATS_FILE
        stamp = _index_stamp(project)
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("stamp") == stamp:
                return cls([set(a) for a in data["answers"]], "probes", n_files)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if catalog is None:
            return cls([], "none")
        answers = _answer_files_from_probes(embedder, catalog)
        try:
            if cache.parent.exists():
                cache.write_text(
                    json.dumps({"stamp": stamp, "answers": [sorted(a) for a in answers]}),
                    encoding="utf-8",
                )
        except OSError:
            pass
        return cls(answers, "probes", n_files)


def _index_stamp(project: Path, scope: str | None = "all") -> str:
    """Changes whenever the index of ``scope`` is rebuilt.

    ``build`` writes an ``index_generation`` into ``build_status.json`` (one
    per scope, see :func:`generation_key`); older indexes fall back to file
    mtimes.
    """
    key = generation_key(scope)
    try:
        status = json.loads(
            (Path(project) / ".neuralmind" / "build_status.json").read_text(encoding="utf-8")
        )
        if status.get(key):
            return f"generation:{status[key]}"
    except (OSError, ValueError, AttributeError):
        pass
    for name in ("build_status.json", "graph.json"):
        p = Path(project) / ".neuralmind" / name
        try:
            return f"{name}:{p.stat().st_mtime_ns}"
        except OSError:
            continue
    return ""


def dampen_hubs(hits: list[dict], stats: HubStats) -> list[dict]:
    for hit in hits:
        f = stats.factor(source_file(hit))
        if f < 1.0:
            hit["score"] = float(hit.get("score") or 0.0) * f
            hit["_hub_factor"] = round(f, 3)
    return hits


# --------------------------------------------------------------------------- #
# Item 1: per-file cap
# --------------------------------------------------------------------------- #
def _score(hit: dict) -> float:
    return float(hit.get("score") or 0.0)


def allocate(
    candidates: list[dict],
    n: int,
    cap: int,
    taken: Counter[str] | None = None,
    fallback: bool = True,
) -> list[dict]:
    """The best ``n`` hits, at most ``cap`` per file (0 = no cap).

    ``taken`` counts hits per file already placed elsewhere. With
    ``fallback``, candidates beyond the cap are used when the pool runs out of
    other files, so a one-file answer still fills its slots.
    """
    ranked = sorted(candidates, key=_score, reverse=True)
    if not cap:
        return ranked[:n]
    chosen: list[dict] = []
    overflow: list[dict] = []
    per_file: Counter[str] = Counter(taken or {})
    for hit in ranked:
        if len(chosen) >= n:
            break
        sf = source_file(hit) or str(hit.get("id"))
        if per_file[sf] < cap:
            chosen.append(hit)
            per_file[sf] += 1
        else:
            overflow.append(hit)
    if fallback and len(chosen) < n:
        chosen.extend(overflow[: n - len(chosen)])
        chosen.sort(key=_score, reverse=True)
    return chosen


def spend(originals: list[dict], refill: list[dict], n: int, cap: int) -> list[dict]:
    """Fill ``n`` slots: the ranked hits keep theirs unless a pass vacates one.

    ``originals`` are L3's hits after every earlier pass (plus any hand-off
    candidates); ``refill`` is the rest of the same search. A refill hit only
    takes a slot the per-file cap emptied, or one held by a hit hub dampening
    marked down — never one an undamped hit earned — so turning a pass on
    changes only what that pass is about.
    """
    first = allocate(originals, n, cap, fallback=False)
    keep = [h for h in first if "_hub_factor" not in h]
    chosen_ids = {h.get("id") for h in first}
    contest = [h for h in first if "_hub_factor" in h]
    contest += [h for h in originals if h.get("id") not in chosen_ids]
    contest += refill
    taken: Counter[str] = Counter(source_file(h) or str(h.get("id")) for h in keep)
    final = keep + allocate(contest, n - len(keep), cap, taken)
    final.sort(key=_score, reverse=True)
    return final


# --------------------------------------------------------------------------- #
# Item 5: symbol-name lexical pass
# --------------------------------------------------------------------------- #
def code_bm25_text(node: dict) -> str:
    """What the symbol index sees: name, file path and docstring text."""
    meta = node["metadata"]
    label = str(meta.get("label") or "")
    sf = str(meta.get("source_file") or "")
    if meta.get("file_type") == "rationale":
        return f"{label} {sf}"
    return f"{label} {_bare_name(label)} {sf}"


def _cached_bm25(
    project: Path, filename: str, build, *, rebuild: bool = True, scope: str | None = "all"
):
    """The cached index if it matches this build; else build it (``rebuild``) or None."""
    from .bm25 import BM25Index

    cache = Path(project) / ".neuralmind" / scoped_file(filename, scope)
    stamp_file = cache.with_suffix(".stamp")
    stamp = _index_stamp(project, scope)
    try:
        if cache.exists() and stamp_file.read_text(encoding="utf-8") == stamp:
            return BM25Index.load(cache)
    except (OSError, ValueError):
        pass
    if not rebuild:
        return None
    docs = build()
    if not docs:
        return None
    ids, texts, metas = zip(*docs, strict=True)
    idx = BM25Index()
    idx.add_documents(list(ids), list(texts), list(metas))
    idx.build()
    try:
        if cache.parent.exists():
            idx.save(cache)
            stamp_file.write_text(stamp, encoding="utf-8")
    except OSError:
        pass
    return idx


def code_bm25_index(project: Path, catalog: NodeCatalog | None, *, scope: str | None = "all"):
    """BM25 over code symbols and docstrings only, cached per index build and scope."""

    def build():
        if catalog is None:
            return []
        return [
            (n["id"], code_bm25_text(n), n["metadata"])
            for n in catalog.by_id.values()
            if n["metadata"].get("file_type") in ("code", "rationale")
        ]

    return _cached_bm25(project, CODE_BM25_FILE, build, scope=scope)


def unified_bm25_index(
    project: Path,
    catalog: NodeCatalog | None,
    *,
    rebuild: bool = False,
    scope: str | None = "all",
):
    """One BM25 index over every node: doc text, symbol names, docstrings.

    The turbovec backend's own BM25 index holds only documents, so in the
    hybrid fusion docs get a keyword signal code never can. (The ChromaDB
    backend's index already holds every node.) Here docs and code compete
    for the same terms in one index.

    ``build`` writes it (``rebuild=True``); a query only loads it, and an
    index built before v4.6.0 has none until the next build. Each ``scope``
    has its own file, so a scoped build leaves the default index alone.
    """

    def build():
        if catalog is None:
            return []
        out = []
        for n in catalog.by_id.values():
            meta = n["metadata"]
            if meta.get("file_type") in ("code", "rationale"):
                text = code_bm25_text(n)
            else:
                text = f"{meta.get('label', '')} {n.get('document', '')}"
            out.append((n["id"], text, meta))
        return out

    return _cached_bm25(project, UNIFIED_BM25_FILE, build, rebuild=rebuild, scope=scope)


# --------------------------------------------------------------------------- #
# Roles: the project's code, the code that exercises it, and prose (v4.11.1)
# --------------------------------------------------------------------------- #
SOURCE, SUPPORT, DOC = "source", "support", "doc"

_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec", "specs"})
_EXAMPLE_DIRS = frozenset({"example", "examples", "demo", "demos", "sample", "samples"})
_TEST_STEM = re.compile(r"^test_|_test$|^tests?$|^conftest$|[a-z0-9]Tests?$")
_TEST_NAME = re.compile(r"\.(?:test|spec)\.")
# A question asks for tests when it names them, or names a test: an identifier
# or file such as test_parse_option(), parse_test.go, cart.test.ts,
# UserServiceTest. "_" is a word character, so \btest\b alone misses those.
_ASKS_TESTS = re.compile(
    r"\b(?:tests?|testing|tested|specs?|pytest|unittest|fixtures?|conftest)\b"
    r"|\btest_\w|\w_tests?\b|\w\.(?:test|spec)\.\w",
    re.I,
)
_ASKS_TEST_CLASS = re.compile(r"\b[A-Za-z]\w*[a-z0-9]Tests?\b")
_ASKS_EXAMPLES = re.compile(r"\b(?:examples?|demos?|samples?)\b", re.I)
_ABSOLUTE = re.compile(r"^(?:/|[A-Za-z]:/)")
_PROSE_SUFFIXES = (*_DOC_SUFFIXES, ".pdf")

# What a hit the question didn't ask for is worth, as a fraction of its score:
# a test or an example always, unless the question names tests or examples,
# and a doc when the question asks for code.
ROLE_WEIGHT = 1 / 3
# How many of the L3 slots the project's own code is owed, by intent, when the
# rest of the search found some.
SOURCE_FLOOR = {"code": 2, "hybrid": 2, "docs": 1}


def project_path(path: str, root: str | os.PathLike | None = None) -> str:
    """``path`` with forward slashes, made relative to ``root`` if it's absolute and inside it.

    Graphs may store absolute source paths. Only the part inside the project
    says what a file is: a checkout at ``/home/work/examples/click`` doesn't
    make ``src/click/core.py`` an example. An absolute path outside ``root`` is
    returned as it is.
    """
    p = str(path).replace("\\", "/")
    if root is None or not _ABSOLUTE.match(p):
        return p
    bases = {str(root).replace("\\", "/").rstrip("/")}
    try:
        bases.add(str(Path(root).resolve()).replace("\\", "/").rstrip("/"))
    except OSError:
        pass
    for base in bases:
        if base and len(p) > len(base) and p[len(base)] == "/":
            head = p[: len(base)]
            if head == base or (re.match(r"^[A-Za-z]:", base) and head.lower() == base.lower()):
                return p[len(base) + 1 :]
    return p


def support_kind(path: str, root: str | os.PathLike | None = None) -> str:
    """'test' or 'example' for a file that exercises the code, '' for the code itself.

    By layout, inside the project (see :func:`project_path`): a ``tests/``,
    ``spec/`` or ``examples/`` directory anywhere in the path, or a test
    file's name (``test_x.py``, ``x_test.go``, ``x.test.ts``, ``conftest.py``).
    ``src/click/testing.py`` is not one: the project ships it.
    """
    parts = project_path(path, root).split("/")
    dirs = {d.lower() for d in parts[:-1]}
    name = parts[-1]
    if dirs & _TEST_DIRS or _TEST_STEM.search(name.split(".")[0]) or _TEST_NAME.search(name):
        return "test"
    if dirs & _EXAMPLE_DIRS:
        return "example"
    return ""


def asked_kinds(query: str) -> frozenset[str]:
    """The support kinds a question names: "how do I test …" asks for tests."""
    asked = set()
    if _ASKS_TESTS.search(query or "") or _ASKS_TEST_CLASS.search(query or ""):
        asked.add("test")
    if _ASKS_EXAMPLES.search(query or ""):
        asked.add("example")
    return frozenset(asked)


def is_prose(hit: dict) -> bool:
    """A doc: a ``document`` or ingested ``document_*`` node (``document_pdf``), or a doc file."""
    meta = hit.get("metadata") or {}
    file_type = str(meta.get("file_type") or "")
    if file_type == "document" or file_type.startswith("document_"):
        return True
    return source_file(hit).lower().endswith(_PROSE_SUFFIXES)


def role(
    hit: dict, asked: frozenset[str] = frozenset(), root: str | os.PathLike | None = None
) -> str:
    """SOURCE, SUPPORT or DOC. A test or example the question asks for is SOURCE.

    ``root`` is the project root, for graphs that store absolute paths.
    """
    if is_prose(hit):
        return DOC
    kind = support_kind(source_file(hit), root)
    return SUPPORT if kind and kind not in asked else SOURCE


def role_weight(hit_role: str, intent: str) -> float:
    """What ``hit_role`` is worth under ``intent``: 1, or :data:`ROLE_WEIGHT`."""
    if hit_role == SUPPORT or (hit_role == DOC and intent == "code"):
        return ROLE_WEIGHT
    return 1.0
