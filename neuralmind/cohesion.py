"""Cluster-cohesion outlier detection over the synapse graph (PROTOTYPE).

The spreading-activation recall in :mod:`neuralmind.synapses` answers
"what is related to this?" — a flat ranked list of neighbors. That is the
right primitive for orientation, but it is silent about *anomalies*: it
surfaces the cluster without telling the agent which member breaks the
cluster's shared pattern.

That silence is the "handler #11" failure mode. When ten call sites all
route ``req.auth.orgId`` through ``resolveOrgId`` and one passes a bare
string literal, the odd one out is exactly the line that ships a bug —
and it looks like every other member of the topical cluster to a flat
recall list. Grep finds the string; it cannot find "the one that skips
the pattern its peers share".

This module closes that gap with a small, dependency-free analysis:

    given a surfaced cluster of nodes, find an *associate* that most of
    the cluster connects to, then flag the cluster members that do not.

It operates purely on a ``neighbors(node_id) -> [(other, weight), ...]``
callable, so it is testable with a plain dict and carries no dependency
on ChromaDB, SQLite, or the embedder. The real caller passes
``SynapseStore.neighbors``; a test passes a fake.

Status: prototype. Wired into the ``UserPromptSubmit`` injection path
behind the opt-in ``NEURALMIND_SYNAPSE_OUTLIERS`` env flag so it changes
nothing by default. Not yet shipped as a release feature.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# A neighbor lookup: node id -> [(neighbor id, edge weight), ...].
NeighborFn = Callable[[str], "list[tuple[str, float]]"]

# Default knobs, deliberately conservative so the prototype stays quiet
# unless the pattern is real.
DEFAULT_COHESION = 0.6  # fraction of the cluster that must share an associate
DEFAULT_MIN_PEERS = 3  # the sharing majority must be at least this many nodes
DEFAULT_MIN_WEIGHT = 0.0  # ignore edges weaker than this when reading neighbors


@dataclass(frozen=True)
class Outlier:
    """One cluster member that breaks its cluster's shared association.

    ``node`` sits inside the surfaced cluster but does *not* connect to
    ``associate``, while ``peers`` of its ``cluster_size`` neighbors do.
    ``share`` is ``peers / (cluster_size - 1)`` — how lopsided the
    consensus is, in ``[0, 1]``. Higher means "more alone".
    """

    node: str
    associate: str
    peers: int
    cluster_size: int

    @property
    def share(self) -> float:
        others = self.cluster_size - 1
        return self.peers / others if others else 0.0


def find_outliers(
    cluster: Iterable[str],
    neighbors: NeighborFn,
    *,
    cohesion: float = DEFAULT_COHESION,
    min_peers: int = DEFAULT_MIN_PEERS,
    min_weight: float = DEFAULT_MIN_WEIGHT,
    max_findings: int = 5,
) -> list[Outlier]:
    """Flag cluster members that skip an association their peers share.

    ``cluster`` is a set of node ids that co-activated for one query (the
    output of spreading activation). For every candidate *associate* — a
    node that at least one cluster member links to — we count how many
    members link to it. When a strong majority (``>= cohesion`` of the
    cluster, and at least ``min_peers`` nodes) share an associate but some
    members do not, each non-sharing member is reported as an
    :class:`Outlier`.

    Returns findings ranked by consensus strength (most lopsided first),
    then by peer count, capped at ``max_findings``. Empty when the cluster
    is too small, has no shared structure, or is internally consistent —
    the common, quiet case.
    """
    members = list(dict.fromkeys(cluster))  # de-dup, preserve order
    n = len(members)
    if n < min_peers + 1:
        # Need a majority AND at least one dissenter to say anything.
        return []

    # member -> set of associates it links to (above the weight floor).
    member_links: dict[str, set[str]] = {}
    for node in members:
        try:
            edges = neighbors(node)
        except Exception:
            edges = []
        member_links[node] = {
            other
            for other, weight in edges
            if other not in member_links.get(node, set())
            and float(weight) >= min_weight
            and other != node
        }

    member_set = set(members)

    # associate -> members that link to it. An associate shared by the
    # cluster is typically *outside* the cluster (e.g. resolveOrgId), so
    # we do not require it to be a member.
    associate_supporters: dict[str, set[str]] = {}
    for node, links in member_links.items():
        for associate in links:
            if associate in member_set:
                # A member linking to another member is intra-cluster
                # cohesion, not a shared external pattern — skip it so
                # the signal stays "everyone reaches out to X".
                continue
            associate_supporters.setdefault(associate, set()).add(node)

    threshold = max(min_peers, math.ceil(cohesion * n))

    findings: list[Outlier] = []
    for associate, supporters in associate_supporters.items():
        peers = len(supporters)
        if peers < threshold or peers >= n:
            # Not a strong-enough majority, or unanimous (no dissenter).
            continue
        for node in members:
            if node not in supporters:
                findings.append(
                    Outlier(
                        node=node,
                        associate=associate,
                        peers=peers,
                        cluster_size=n,
                    )
                )

    findings.sort(key=lambda o: (o.share, o.peers), reverse=True)
    return findings[:max_findings]


def format_outliers(findings: list[Outlier]) -> str:
    """Render outliers as a compact markdown block for prompt injection.

    Empty string when there is nothing to report, so the caller can
    concatenate unconditionally without emitting a dangling header.
    """
    if not findings:
        return ""
    lines = ["## NeuralMind cohesion check", ""]
    for o in findings:
        pct = round(o.share * 100)
        lines.append(
            f"- `{o.node}` skips `{o.associate}` — "
            f"{o.peers} of its {o.cluster_size - 1} cluster-peers ({pct}%) use it. "
            f"Likely the odd one out; verify before trusting it."
        )
    return "\n".join(lines)
