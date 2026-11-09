# RHOAI Fitness Evaluation: OpenShell

**Strategy:** redhat-ai-2026 (Red Hat AI CY2026)
**Relationship:** direct
**Strategy areas:** agentic-ai, management-observability-security

## Scores (0-20 each, total /100)

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| audience_value | 16 | Sandboxed execution for autonomous agents is a high-interest, high-demand capability for AI/agent engineers; OpenShell is one of the few OSS runtimes that isolates untrusted agent workloads. |
| strategic_alignment | 17 | Agentic AI is a named CY2026 strategy area; OpenShell is purpose-built as an agent runtime (gateway + supervisor + isolated sandbox), aligning directly with the Llama Stack / agent story. |
| strategy_fit | 15 | Serves agentic-ai as the primary area and management-observability-security (policy, mTLS, OCSF telemetry, NetworkPolicy, isolation) as secondary. It is an agent runtime, not a model-serving or inference-optimization tool, so it is complementary rather than central to the inference stack. |
| platform_leverage | 14 | Ships a first-party Helm chart that deploys a StatefulSet gateway, a shared supervisor pool with a PDB, dynamic per-sandbox Pods via the in-tree Kubernetes compute driver, mTLS PKI bootstrap, NetworkPolicies and an OpenShift Route — real OpenShift leverage. It is also platform-portable (docker/podman/vm drivers), so OpenShift is a target, not the only home. |
| demo_potential | 15 | A compelling demo: drive the gateway from the SDK, spin up an isolated sandbox, run an agent process inside it, and observe policy/NetworkPolicy enforcement and telemetry. |

**Total: 77/100** — a strong, directly-aligned agentic-AI candidate for an OpenShift AI PoC.

## Strengths
- Purpose-built agent runtime with a clear control-plane (gateway) / trusted-runtime (supervisor) / isolated-workload (sandbox) separation.
- First-party Helm chart with OpenShift overlays (restricted-v2 SCC, Route/mTLS transport).
- Rich security surface to validate: mTLS, NetworkPolicy, policy engine, OCSF observability, per-sandbox isolation.
- Multi-language SDK (Python/Go/TS) makes functional validation straightforward.

## Risks
- Large Rust workspace (~40 crates); gateway build is heavy (vendored z3, aws-lc) and can exceed 20 minutes.
- The Kubernetes compute driver requires an Agent Sandbox API / supporting CRDs in-cluster for dynamic sandboxes; availability must be confirmed at deploy time.
- Deep TLS/PKI bootstrap (certgen hook) adds moving parts; a misconfigured secret can stall the gateway.
- Sandbox placement and storage are operator-dependent (node affinity, StorageClass), which constrains where the PoC can run.
