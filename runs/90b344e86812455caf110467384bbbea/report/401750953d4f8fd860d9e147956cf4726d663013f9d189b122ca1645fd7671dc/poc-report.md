# OpenShell on OpenShift AI — Proof-of-Concept Report

**Project:** NVIDIA/OpenShell
**Run ID:** 90b344e86812455caf110467384bbbea
**Source pin:** f4a6137513b777c9b362be54baf388f7d45398aa
**Target namespace:** poc-openshell-kokoro-20261109 (Helm release `openshell`)

## Provenance note

This report and the accompanying executive narration went through a final
operator-directed content review after the original five-scenario execution and
before expensive narration rendering. The pass narrowed the scope of claims
(network, coverage, images, recommendations) and corrected two claim
classifications; it did not rerun tests, SDK or network probes, deployments,
builds, or resets. The original captured execution
(`af1836af24fc49a38c665ed61bfa76da`) and its outcomes are preserved unchanged.
This is a content-assistance intervention, not a functional deployment or test
failure.

## Objective

Demonstrate that NVIDIA OpenShell — an agentic-AI sandbox runtime composed of a
gateway control plane, a shared supervisor pool, and per-task sandbox runtimes —
can be containerized from source, deployed to OpenShift with bounded resources
and observed hardening (restricted-v2, mTLS, NetworkPolicies), and driven
end-to-end through its public SDK: creating a sandbox, executing a real process
inside it, pinning the sandbox to a specific node, and observing its network
reachability boundary.

## What OpenShell is

OpenShell is a Rust-based system with three cooperating components plus a
Python SDK:

- **Gateway** — the gRPC control plane. It authenticates clients over mTLS,
  registers sandboxes, routes execution to the appropriate sandbox runtime, and
  serves `/healthz` (8081) and Prometheus `/metrics` (9090). In this run it is
  deployed as a single-replica, SQLite-backed StatefulSet.
- **Supervisor** — a shared-pool process supervisor that hosts sandbox
  workloads. Deployed as a Deployment with a PodDisruptionBudget.
- **Sandbox runtime** — a static musl binary injected into each sandbox Pod
  alongside the workload container; it is the agent the gateway talks to.
- **Python SDK** — `SandboxClient` for CRUD and `exec`, speaking gRPC over mTLS.

## Environment and setup

- **Core images** built fresh from the pinned source with UBI9-based
  Dockerfiles and published to Quay under the unique tag `kokoro-90b344e8`
  (three source-built core/bootstrap images):
  - `quay.io/aicatalyst/openshell-gateway:kokoro-90b344e8`
    (sha256:c0aa13f9…, 137 MB, 41m50s build)
  - `quay.io/aicatalyst/openshell-supervisor:kokoro-90b344e8`
    (sha256:9bdf4d60…, 82 MB, 22m55s)
  - `quay.io/aicatalyst/openshell-sandbox:kokoro-90b344e8`
    (sha256:8df9f3bc…, 50 MB, 10m19s)
- **Sandbox workload image.** The sandbox *workload environment* ran on the
  external base image `nvcr.io/nvidia/base/ubuntu:24.04`, confirmed pullable by
  the cluster. This image is distinct from the three source-built images above
  and is not one of them.
- **Deployment** via the upstream Helm chart layered with `ci/values-openshift-scc.yaml`
  (restricted-v2 / nonroot) and a PoC values file. Gateway requests/limits are
  bounded to 2/4Gi and 4/16Gi respectively. The supervisor pool runs with a PDB.
- **Node placement.** The gateway PVC consumer is pinned to
  `ocp-gb-xz56l-worker-2-nsrd9` (eu-gb-2) via a Pod nodeSelector; each sandbox
  Pod is pinned to the same node through the public
  `driver_config.kubernetes.pod.node_selector`. The gateway's data volume is a
  block PVC on the `ibmc-vpc-block-10iops-tier` StorageClass (RWO). Sandbox
  storage is described as configured, not asserted beyond the retained
  evidence.
- **Security posture (observed configuration).** restricted-v2 / nonroot; no
  privileged/anyuid SCC and no cluster-admin. The gateway terminates mTLS with a
  run-generated CA (`openshell-ca`) signing both the server and client
  certificates. Ingress NetworkPolicies restrict the sandbox SSH port (2222) to
  the gateway and bound the supervisor. The Agent Sandbox CRDs
  (`agents.x-k8s.io/v1beta1`) are present and used for sandbox lifecycle. These
  are observed configuration properties, not a security certification.

## Methodology

Five scenarios were executed against the live deployment using the Python SDK
over mTLS (reached through a local port-forward to the gateway) and `kubectl`,
with every attempt recorded through the AutoPoC attempt/capture mechanism:

1. **gateway-health** — `GET /healthz` on the gateway health port returns 200.
2. **gateway-metrics** — `GET /metrics` on the metrics port exposes
   `openshell_server_*` Prometheus metrics.
3. **sandbox-exec** — create a sandbox via the SDK, wait for the READY phase,
   then `exec` a shell command and verify the returned process output.
4. **sandbox-node-placement** — verify the created sandbox Pod is scheduled on
   the required node as a direct result of the `node_selector` driver config.
5. **network-denial** — from an in-cluster worker Pod outside the app
   namespace, a plain TCP connection to the gateway Pod's metrics port (9090)
   should succeed (reachable control), while a plain TCP connection to the
   sandbox Pod's port 2222 should not (restricted path).

## Results

**All five scenarios passed: 5 pass, 0 fail, 0 error, 0 skip, 0 incomplete.**
Every planned scenario therefore has a terminal captured outcome; there are no
missing planned results. That is a statement about planned coverage only, not
about the completeness of functional, security, or trace coverage. The retained
evidence supports audit and traceability of the captured execution; it is not a
guarantee of full reproducibility or replayability.

- **gateway-health: PASS** — `/healthz` returned HTTP 200.
- **gateway-metrics: PASS** — `/metrics` returned `openshell_server_*` metrics.
- **sandbox-exec: PASS** — a sandbox reached the READY phase and `exec`
  returned real process output (a host-stamped marker and a `uname` banner)
  with exit code 0.
- **sandbox-node-placement: PASS** — the sandbox Pod's `spec.nodeName` and
  `spec.nodeSelector` both resolved to `ocp-gb-xz56l-worker-2-nsrd9`, matching
  the requested placement.
- **network-denial: PASS** — from the in-cluster worker, a TCP connection to
  the gateway Pod's metrics port 9090 succeeded, while a TCP connection to the
  sandbox Pod's port 2222 did not. This is a limited observed ingress
  reachability pattern, consistent with the `openshell-sandbox-ssh`
  NetworkPolicy but not, by itself, proof of policy causation, all network
  enforcement, egress isolation, filesystem isolation, or production security.

## Limitations

- The gateway runs as a **single, SQLite-backed replica** on one node; this is a
  functional PoC configuration, not a high-availability deployment.
- The functional test is a **smoke-level** exercise: it validates creation,
  a single `exec`, placement, and one limited network reachability observation.
  It does not establish authenticated (OIDC) workflows, sustained reliability,
  or production readiness.
- The network result is a **single TCP contrast from one in-cluster vantage
  point** (a worker Pod outside the app namespace). It does not establish
  policy causation, egress isolation, filesystem isolation, or production
  security.
- The workload base image is pulled from an **external registry** (nvcr.io);
  air-gapped or strictly internal environments would need a mirrored image.
- Placement was validated on a **single target node**; multi-node and GPU
  workload behavior were not exercised in this run.
- The retained evidence enables **audit and traceability** of the captured
  execution; it does not guarantee full reproducibility or replayability.

## Recommendation

OpenShell deploys cleanly to OpenShift from source, and the run observed
sandbox creation, in-sandbox execution, node placement, and a limited ingress
reachability pattern. The chart ships supported high-availability overlays
(a multi-replica gateway backed by an external database, and a 2-replica
supervisor pool) that this run did not exercise. As future work, before
production consideration: exercise those supported HA/persistence paths,
exercise authenticated (OIDC) flows, and extend the functional suite to load
and reliability, GPU workloads, and multi-node placement.
