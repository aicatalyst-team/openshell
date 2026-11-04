# RHOAI Fitness Evaluation: OpenShell

Active strategy: `redhat-ai-2026` (Red Hat AI CY2026 Product Strategy).

## Verdict
OpenShell is a **strong strategic fit** for the Red Hat AI 2026 story. It is a
general-purpose, kernel-enforced sandbox runtime for autonomous AI agents that
deploys natively on OpenShift/Kubernetes. It sits squarely in the **agentic-AI**
strategy area (securely running agent fleets) and is adjacent to **TrustyAI**
(responsible-AI guardrails) and **MCP** (tool/credential connectivity). It is a
capability the OpenShift AI platform can host and operators can consume directly.

## Impact scores (each 0-20)
| Dimension | Score | Rationale |
|---|---|---|
| audience_value | 18 | Developers/operators running agent fleets need a way to give agents real capability (files, network, credentials) without blast radius. Broad, timely audience. |
| strategic_alignment | 18 | Agentic AI is a core CY2026 theme; a secure agent runtime is a natural layer under Llama Stack / OpenShift AI agent workloads. |
| strategy_fit | 17 | Maps to agentic-ai and touches TrustyAI (policy as guardrails) and MCP (endpoint-bound credentials). Not a model-serving or InstructLab project, so not a perfect 1:1. |
| platform_leverage | 18 | Ships a first-class OpenShift/Helm path: Agent Sandbox CRD, NetworkPolicy, restricted-v2 SCC (no privileged SCC), namespace UID ranges. Deep OpenShift leverage. |
| demo_potential | 17 | Compelling live demo: create a sandbox, run a command, watch allowed egress succeed and denied egress/filesystem fail. Clear security narrative. |

**Impact total: 88 / 100.**

## Feasibility (qualitative)
- **container_readiness**: medium-high. Mature Helm chart + existing Dockerfiles, but the three components are Rust and must be rebuilt (here, UBI-ified) from source.
- **dependency_profile**: medium. Large 41-crate workspace, but pinned via Cargo.lock; protobuf/protoc vendored, TLS pure-Rust, z3 vendored for the gateway — a self-contained build context.
- **reproduction_confidence**: medium-high. Clear build/CI docs and a working Agent Sandbox controller + OVN on the target cluster, but the sandbox boundary has real kernel prerequisites (Landlock ABI>=3, nested seccomp user-notification, SO_BINDTODEVICE) that must be qualified at runtime — not assumed from the kernel version.
- **complexity_sweet_spot**: low-medium. It is a large, security-critical project, not a lightweight demo app; the PoC scope is deliberately bounded to the gateway + one sandbox to stay tractable.

## Risks
- Heavy Rust build (three components) increases build time and failure surface.
- The sandbox boundary can fail closed if the node runtime profile blocks the
  required seccomp/Landlock operations; this must be verified on the actual
  restricted-v2 runtime, not presumed.
- NetworkPolicy enforcement depends on the CNI (OVN here); allowed/denied
  behavior must be demonstrated empirically.
