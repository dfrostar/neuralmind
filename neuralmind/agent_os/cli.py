"""Agent OS CLI — operator commands for multi-tenant management."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_agent_os(args: argparse.Namespace) -> None:
    """Execute an Agent OS command."""
    from neuralmind.agent_os import (
        AgentOSGovernance,
        ExperimentRunner,
        PromotionEngine,
        RootCauseCorrelator,
        SignalDetector,
        TenantRegistry,
    )

    action = getattr(args, "agent_os_command", None)
    if action is None:
        print("No Agent OS command specified. Run `neuralmind agent-os --help`.")
        return

    # Initialize components
    registry = TenantRegistry()
    governance = AgentOSGovernance(registry)
    correlator = RootCauseCorrelator()
    signal_detector = SignalDetector(correlator=correlator)
    experiment_runner = ExperimentRunner()
    promotion_engine = PromotionEngine()

    try:
        if action == "tenants":
            _cmd_tenants(args, registry, governance)
        elif action == "rbac":
            _cmd_rbac(args, registry, governance)
        elif action == "signals":
            _cmd_signals(args, signal_detector, correlator)
        elif action == "experiments":
            _cmd_experiments(args, experiment_runner, promotion_engine)
        elif action == "proposals":
            _cmd_proposals(args, signal_detector, promotion_engine)
        elif action == "health-snapshot":
            _cmd_health_snapshot(args, registry, signal_detector, promotion_engine)
        else:
            print(f"Unknown Agent OS command: {action}")
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_tenants(args, registry, governance):
    action = getattr(args, "tenants_action", None)
    if action == "list":
        tenants = registry.list_tenants()
        print(json.dumps([t.to_dict() for t in tenants], indent=2))
    elif action == "create":
        tenant = governance.create_tenant(
            tenant_id=args.id,
            email=args.admin,
            name=args.name,
            tier=args.tier,
            projects=args.projects,
        )
        print(json.dumps(tenant.to_dict(), indent=2))
    elif action == "delete":
        governance.delete_tenant(args.id, args.admin)
        print(json.dumps({"deleted": args.id}))
    else:
        print("Unknown tenants action")


def _cmd_rbac(args, registry, governance):
    action = getattr(args, "rbac_action", None)
    if action == "add":
        # Pass positional args: decorator extracts tenant_id=args[1], email=args[2]
        tenant = governance.assign_role(args.tenant, args.admin, args.email, args.role)
        print(json.dumps(tenant.to_dict(), indent=2))
    else:
        print("Unknown rbac action")


def _cmd_signals(args, signal_detector, correlator):
    action = getattr(args, "signals_action", None)
    if action == "list":
        metrics = signal_detector.list_metrics()
        stats = {}
        for m in metrics:
            s = signal_detector.get_stats(m)
            if s:
                stats[m] = s
        print(json.dumps({"metrics": stats}, indent=2))
    elif action == "push":
        # Use push() for auto-correlation (was using old .update() API)
        result = signal_detector.push(
            args.metric, float(args.value),
            project_path=getattr(args, "project_path", None)
        )
        output = {
            "signal": result.signal.to_dict() if result.signal else None,
            "insight": result.insight.to_dict() if result.insight else None,
            "metric": args.metric,
            "value": float(args.value),
        }
        print(json.dumps(output, indent=2))
    else:
        print("Unknown signals action")


def _cmd_experiments(args, experiment_runner, promotion_engine):
    action = getattr(args, "experiments_action", None)
    if action == "run":
        result = promotion_engine.run(
            proposal_id=args.proposal,
            metric_name=args.metric,
            baseline_value=args.baseline,
            candidate_value=args.candidate,
            higher_is_better=args.higher_is_better,
            threshold_pct=args.threshold,
        )
        print(json.dumps(result.to_dict(), indent=2))
    elif action == "history":
        history = experiment_runner.get_history()
        print(json.dumps([r.to_dict() for r in history], indent=2))
    else:
        print("Unknown experiments action")


def _cmd_proposals(args, signal_detector, promotion_engine):
    from neuralmind.agent_os import PromotionEngine, Proposal, TunerIncumbent
    from neuralmind.agent_os.proposal_store import (
        create_proposal,
        get_proposal,
        history,
        list_proposals,
        update_proposal,
    )

    action = getattr(args, "proposals_action", None)
    if action == "create":
        proposal = create_proposal(
            title=args.title,
            hypothesis=args.hypothesis,
            baseline_tag=args.baseline_tag,
            candidate_tag=args.candidate_tag,
            metric_name=args.metric,
            baseline_value=args.baseline,
            candidate_value=args.candidate,
            tags=getattr(args, "tags", None),
        )
        print(json.dumps(proposal, indent=2))
    elif action == "list":
        proposals = list_proposals()
        print(json.dumps(proposals, indent=2))
    elif action == "history":
        records = history(args.id)
        print(json.dumps(records, indent=2))
    elif action == "run":
        proposal_dict = get_proposal(args.id)
        if proposal_dict is None:
            print(f"Proposal {args.id} not found")
            sys.exit(1)
        proposal = Proposal(
            proposal_id=proposal_dict["proposal_id"],
            title=proposal_dict["title"],
            hypothesis=proposal_dict["hypothesis"],
            baseline_tag=proposal_dict["baseline_tag"],
            candidate_tag=proposal_dict["candidate_tag"],
            metric_name=proposal_dict["metric_name"],
            baseline_value=proposal_dict["baseline_value"],
            candidate_value=proposal_dict["candidate_value"],
            status=proposal_dict.get("status", "proposed"),
            signal_count=proposal_dict.get("signal_count", 0),
        )
        incumbent = TunerIncumbent(proposal.metric_name, proposal.baseline_value, proposal.baseline_tag)
        engine = PromotionEngine(incumbent=incumbent, proposal=proposal, signal_count=proposal.signal_count)
        result = engine.run()
        update_proposal(args.id, {
            "status": proposal.status,
            "signal_count": proposal.signal_count,
            "last_experiment_id": result.experiment_id,
            "last_verdict": result.verdict.value,
        })
        print(json.dumps({
            "proposal_id": args.id,
            "experiment": result.to_dict(),
            "proposal_status": proposal.status,
            "incumbent_value": incumbent.value,
            "incumbent_tag": incumbent.tag,
        }, indent=2))
    else:
        print("Unknown proposals action")


def _cmd_health_snapshot(args, registry, signal_detector, promotion_engine):
    """Print a comprehensive health snapshot for the Agent OS."""
    from neuralmind.agent_os.proposal_store import list_proposals

    tracked_metrics = signal_detector.list_metrics()
    proposals = list_proposals()
    experiments = promotion_engine.get_history()

    # Get recent experiments with details
    recent_experiments = []
    for exp in experiments[:5]:
        recent_experiments.append({
            "experiment_id": exp.experiment_id,
            "proposal_id": exp.proposal_id,
            "metric_name": exp.metric_name,
            "verdict": exp.verdict.value if hasattr(exp.verdict, 'value') else str(exp.verdict),
            "delta": round(exp.delta, 6) if exp.delta else None,
            "p_value": exp.p_value,
            "ci_lower": exp.ci_lower,
            "ci_upper": exp.ci_upper,
            "ts": exp.ended_at,
        })

    snapshot = {
        "tenants": {
            "total": len(registry.list_tenants()),
        },
        "signals": {
            "tracked_metrics": len(tracked_metrics),
            "metrics": tracked_metrics,
            "stats": {m: signal_detector.get_stats(m) for m in tracked_metrics if signal_detector.get_stats(m)},
        },
        "proposals": {
            "total": len(proposals),
            "active": len([p for p in proposals if p.get("status") == "proposed"]),
            "promoted": len([p for p in proposals if p.get("status") == "promoted"]),
            "rolled_back": len([p for p in proposals if p.get("status") == "rolled_back"]),
            "recent": proposals[:5],
        },
        "experiments": {
            "total": len(experiments),
            "recent": recent_experiments,
        },
        "correlator": {
            "configured": signal_detector._correlator is not None,
        },
    }
    print(json.dumps(snapshot, indent=2))
