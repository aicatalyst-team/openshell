# PoC Plan: OpenShell

## Project Classification
- **Type:** infrastructure (agent runtime: gateway + supervisor + isolated sandbox, with SDK)
- **Key Technologies:** Rust (gateway/supervisor/sandbox), gRPC/tonic, axum, mTLS (rustls), Kubernetes compute driver, Agent Sandbox CRD (`agents.x-k8s.io/v1beta1`), Helm chart, Python SDK
- **ODH Relevance:** OpenShell is a purpose-built runtime for autonomous AI agents. It isolates untrusted agent workloads in per-sandbox Pods, mediates them through a trusted supervisor, and exposes a control-plane gateway — a direct fit for the CY2026 agentic-AI strategy area and for demonstrating agent-execution isolation on OpenShift AI.

## PoC Objectives
1. Prove the OpenShell gateway, shared supervisor pool and sandbox runtime build from the pinned source as UBI images and deploy on OpenShift under restricted-v2/nonroot with the preinstalled `openshell` ServiceAccount.
2. Prove a sandbox can be created through the SDK and a process actually executes inside it (functional execution, not just Pod/API readiness).
3. Prove operator-directed placement: gateway and sandbox PVC consumers land on the required node with the required StorageClass.
4. Prove NetworkPolicy enforcement with a reachable in-cluster control (not merely policy existence).
5. Confirm observability surfaces (health, metrics) are live.

## Scope and exclusions
- **In scope:** gateway health/metrics, one functional sandbox exec, sandbox node placement, one NetworkPolicy enforcement check, image provenance.
- **Out of scope (not claimed without a dedicated test):** production security posture, OIDC/authn flows, load/HA failover, filesystem isolation guarantees, multi-replica gateway, Kubernetes (non-OpenShift) portability, GPU sandboxes.
- The three images are built from the pinned revision `f4a6137513b777c9b362be54baf388f7d45398aa` using the operator-provided reference UBI Dockerfiles (provenance recorded). No prebuilt upstream images are substituted.

## Infrastructure Requirements
- **Deployment vehicle:** the project's Helm chart `deploy/helm/openshell`, release name `openshell`, namespace `poc-openshell-kokoro-20261109`.
- **Workloads the chart renders for this run:**
  - Gateway: StatefulSet (SQLite-backed) with a data PVC.
  - Shared supervisor pool: Deployment (1 replica) + PodDisruptionBudget (maxUnavailable 1) + Service + NetworkPolicy, selected via `supervisor_topology=gateway`.
  - Sandboxes: dynamically created `agents.x-k8s.io/v1beta1 Sandbox` CRs / Pods in the same namespace by the in-tree Kubernetes compute driver.
- **Resource Profile:** large. Gateway requests 2 CPU / 4Gi, limits 4 CPU / 16Gi (bounded).
- **GPU Required:** no.
- **Persistent Storage:** gateway data PVC + sandbox workspace PVCs, StorageClass `ibmc-vpc-block-10iops-tier` (block-backed, WaitForFirstConsumer).
- **Node placement (mandatory):** gateway Pod and sandbox PVC consumers on node `ocp-gb-xz56l-worker-2-nsrd9` (eu-gb-2). Gateway via Helm `nodeSelector`; sandbox via per-sandbox `driver_config.kubernetes.pod.node_selector` = `{kubernetes.io/hostname: ocp-gb-xz56l-worker-2-nsrd9}`.
- **Identity/RBAC:** use preinstalled ServiceAccount `openshell` (`serviceAccount.create=false`, `name=openshell`); `rbac.clusterScoped.create=false` (cluster-scoped node-reader already provided by the operator); workspace Resources enabled.
- **Security context:** restricted-v2 / nonroot (OpenShift SCC overlay); PDB enabled; no privileged/anyuid SCC, no cluster-admin, no weakened sandbox isolation.
- **Images (all tag `kokoro-90b344e8` on `quay.io/aicatalyst`):**
  - `openshell-gateway`, `openshell-supervisor`, `openshell-sandbox` (the sandbox runtime image used as the sandbox Pod's runtime/companion).
- **Prerequisite confirmed:** Agent Sandbox API `agents.x-k8s.io/v1beta1` (Sandbox) is served by the cluster.

## Test Scenarios
### Scenario 1: gateway-health
- **Description:** The gateway process is functionally up (not merely Pod-Ready).
- **Type:** http
- **Input:** `GET /healthz` against the gateway health port (8081) via a `kubectl port-forward` to the gateway service.
- **Expected:** HTTP 200 (healthy).
- **Timeout:** 30

### Scenario 2: gateway-metrics
- **Description:** The observability/metrics surface is live.
- **Type:** http
- **Input:** `GET /metrics` against the gateway metrics port (9090) via port-forward.
- **Expected:** HTTP 200 and body contains `openshell_` metric names.
- **Timeout:** 30

### Scenario 3: sandbox-exec
- **Description:** A sandbox is created through the SDK and a process genuinely executes inside it. This distinguishes functional process execution from mere Pod/API readiness.
- **Type:** exec
- **Input:** Using the Python SDK over mTLS (client cert from the `openshell-client-tls` Secret) to the gateway via port-forward: create a sandbox in the default workspace, then `exec` a command such as `sh -c 'echo openshell-poc-<run>'` and read the streamed stdout.
- **Expected:** exit status 0 and stdout contains the expected marker string produced by the in-sandbox process.
- **Timeout:** 120

### Scenario 4: sandbox-node-placement
- **Description:** Operator-directed placement of the sandbox PVC consumer on the required node.
- **Type:** exec
- **Input:** After creating the sandbox in Scenario 3 with `driver_config.kubernetes.pod.node_selector={kubernetes.io/hostname: ocp-gb-xz56l-worker-2-nsrd9}`, read the backing Pod's `spec.nodeName`.
- **Expected:** `spec.nodeName == ocp-gb-xz56l-worker-2-nsrd9`.
- **Timeout:** 60

### Scenario 5: network-denial
- **Description:** NetworkPolicy enforcement proven with a reachable in-cluster control, not just policy existence.
- **Type:** exec
- **Input:** In the sandbox namespace, run a short-lived non-gateway "talker" Pod. (a) Reachable control: talker connects to the gateway ClusterIP service (a path with no restrictive ingress policy) and succeeds. (b) Denial: the same talker attempts to reach the sandbox Pod's SSH port (2222), which the sandbox ingress NetworkPolicy restricts to the gateway Pod only.
- **Expected:** the control connection succeeds while the policy-restricted connection is denied (filtered/timeout), demonstrating CNI enforcement of the sandbox ingress policy. If the distinction cannot be made unambiguous, the scenario is reported as incomplete rather than passed.
- **Timeout:** 90

## Dockerfile Considerations
- Reuse the operator-provided reference UBI Dockerfiles (record provenance): gateway = UBI9 + rustup 1.95.0 + gcc-toolset-15 + clang, `cargo build --release --target x86_64-unknown-linux-gnu -p openshell-gateway --features vendored-z3`, runtime `ubi9/ubi-minimal`, USER 1001, EXPOSE 8080/8081/9090. supervisor = same builder minus the toolset, `-p openshell-supervisor`, EXPOSE 5500. sandbox = UBI9 + rustup + musl.cc cross toolchain, `--target x86_64-unknown-linux-musl -p openshell-sandbox`, static binary, runtime `ubi9/ubi-minimal`, USER 1001.
- Inspect each against the pinned source (crate/bin names, features) before building. Build on-cluster (BUILD_STRATEGY=openshift) with BuildConfig prefix `openshell-kokoro-90b344e8-` in `autopoc-test-builds`, pushing tag `kokoro-90b344e8` (never overwriting earlier tags).

## Deployment Considerations
- Install the project Helm chart (not hand-written manifests) so the real chart/API structure is exercised. No `helm` binary is present in the worker; install the static helm binary as a setup step.
- `helm install openshell deploy/helm/openshell -n poc-openshell-kokoro-20261109 -f ci/values-openshift-scc.yaml -f <poc-values.yaml>`, where `poc-values.yaml` sets: the three `quay.io/aicatalyst` images at tag `kokoro-90b344e8`, `serviceAccount.create=false`/`name=openshell`, `rbac.clusterScoped.create=false`, `supervisor.podDisruptionBudget.enabled=true` with `gatewayConfig.openshell.drivers.kubernetes.supervisor_topology=gateway`, `nodeSelector={kubernetes.io/hostname: ocp-gb-xz56l-worker-2-nsrd9}`, `server.dataStorageClass=ibmc-vpc-block-10iops-tier`, `server.workspaceStorageClass=ibmc-vpc-block-10iops-tier`, gateway `resources` (2/4Gi requests, 4/16Gi limits), and `allow_driver_config=true` so the per-sandbox node selector is honored.
- Verify rollout: gateway StatefulSet Pod Ready, supervisor Deployment Pod Ready + PDB present, then drive the SDK scenarios. Keep cleanup bounded to resources in `poc-openshell-kokoro-20261109` owned by this release.
