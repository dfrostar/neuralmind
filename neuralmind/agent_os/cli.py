"""Agent OS CLI — operator commands for multi-tenant management."""

from __future__ import annotations

import argparse
import json


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
    signal_detector = SignalDetector()
    experiment_runner = ExperimentRunner()
    promotion_engine = PromotionEngine()
    correlator = RootCauseCorrelator()

    try:
        if action == "tenants":
            _cmd_tenants(args, registry, governance)
        elif action == "rbac":
            _cmd_rbac(args, registry, governance)
        elif action == "signals":
            _cmd_signals(args, signal_detector, correlator)
        elif action == "experiments":
            _cmd_experiments(args, experiment_runner, promotion_engine)
        else:
            print(f"Unknown Agent OS command: {action}")
    except Exception as e:
        print(f"Error: {e}")


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
        tenant = governance.assign_role(
            tenant_id=args.tenant,
            admin_email=args.admin,
            target_email=args.email,
            role=args.role,
        )
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
        signal = signal_detector.update(args.metric, args.value)
        print(json.dumps({"signal": signal.to_dict() if signal else None}, indent=2))
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
