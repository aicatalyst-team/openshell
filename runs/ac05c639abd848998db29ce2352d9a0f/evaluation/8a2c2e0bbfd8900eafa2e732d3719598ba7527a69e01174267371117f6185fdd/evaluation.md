# RHOAI Evaluation: NVIDIA/OpenShell

- Strategy: Red Hat AI 2026 (`redhat-ai-2026`, baseline 2026-04-29)
- Evaluated revision: `f4a6137513b777c9b362be54baf388f7d45398aa`
- Relationship: enriches-existing-capability

## Impact scores (0-20 each)

| Dimension | Score | Rationale |
|---|---:|---|
| audience_value | 18 | Directly serves platform, security, and AI engineering teams that need governed agent execution rather than local-only demos. |
| strategic_alignment | 19 | Strong fit for Agentic AI plus Management, Observability & Security: policy enforcement, formal verification, and runtime governance for agents. |
| strategy_fit | 18 | Maps to `agent-runtime`, `tool-calling`, `mcp`, `guardrails`, `observability`, and `supply-chain` capability labels. |
| platform_leverage | 18 | Kubernetes-native gateway/sandbox model, Helm deployment, Agent Sandbox integration, and OpenShift-specific SCC handling. |
| demo_potential | 17 | Concrete lifecycle, execution, and policy-denial demos; three Rust images and cluster prerequisites add demo setup cost. |

**Impact total: 90 / 100**

## Feasibility (0-20 each)

| Dimension | Score | Rationale |
|---|---:|---|
| container_readiness | 15 | Upstream images exist, but they use distroless/scratch and prebuilt binaries; this run must source-build three UBI images. |
| dependency_profile | 13 | Large Rust workspace (41 crates), vendored Z3, aws-lc, and a musl cross-toolchain make builds heavy but reproducible. |
| reproduction_confidence | 15 | Exact source pin, pinned Cargo.lock, Helm chart, and documented OpenShift path; sandbox runtime still depends on Landlock/seccomp support. |
| complexity_sweet_spot | 14 | Real control-plane/data-plane architecture is valuable for a PoC but requires Agent Sandbox, NetworkPolicy CNI, and TLS client handling. |

**Feasibility total: 57 / 80**

## Strengths

- Real, differentiated agent-runtime security story with kernel-level policy and
  formal policy verification.
- Kubernetes/OpenShift-native: gateway, supervisor, sandbox, CRDs, Helm, and
  documented SCC behavior.
- Testable behaviours that are meaningful beyond a health check: process
  execution, workspace persistence, and allow/deny network policy.
- Pinned source and lockfile support reproducible source builds.

## Risks

- Build time and resource consumption for three full Rust builds.
- Restricted-v2 may not permit the nested seccomp user-notification/Landlock
  probes; any failure must be recorded, not worked around with a privileged SCC.
- Network denial must be demonstrated against a reachable control to separate
  application-level policy mediation from CNI or cluster egress behaviour.
- Upstream's production auth (OIDC, HA, multi-replica) is out of scope for a
  single-replica evaluation; a development principal over client-cert mTLS is
  not production authentication.

## Recommendation

Proceed with a focused PoC on the gateway, shared supervisor, and sandbox
runtime, validating health, genuine process execution, workspace persistence,
and an allow/deny network-policy pair against a reachable control. Do not claim
production security, OIDC, HA, load, or portability from smoke checks.
