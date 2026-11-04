# PoC Plan: openshell

## Project Classification

- **Type:** infrastructure
- **Key Technologies:** Rust (workspace of 40+ crates), gRPC/tonic control plane, Helm chart, Agent Sandbox CRD (agents.x-k8s.io), kernel isolation (Landlock + nested seccomp user-notification + SO_BINDTODEVICE), OPA/Regorus policy engine with z3 formal verification, mTLS gateway authentication
- **ODH Relevance:** OpenShift AI agent workloads (autonomous agents, TrustyAI guardrails, MCP credential connectivity) need a hard execution boundary. OpenShell is a production-grade, kernel-enforced sandbox runtime that deploys natively on OpenShift through its own Helm chart with restricted-v2 SCC support and no privileged SCC requirement. It is a direct fit for securing agent fleets on OpenShift AI.

## PoC Objectives

1. Build all three source-built Rust components (gateway, supervisor, sandbox runtime) from the pinned commit `f4a6137` into UBI-based images and push them to Quay (`quay.io/aicatalyst/openshell-{gateway,supervisor,sandbox}:f4a6137`).
2. Deploy the project's own Helm chart into namespace `poc-openshell` using the preinstalled gateway ServiceAccount binding (`autopoc-openshell-runtime` ClusterRole bound to SA `openshell`) with `rbac.clusterScoped.create=false`, OpenShift restricted-v2 SCC compatibility, and no privileged SCC.
3. Validate the gateway control plane: HTTP health endpoint, Prometheus metrics endpoint, and the gRPC API (Health + sandbox listing) over mTLS using the project's Python SDK.
4. Validate the full sandbox lifecycle through the Agent Sandbox controller: create a sandbox via the gRPC API, wait for readiness, exec a command inside the sandbox, verify the Agent Sandbox CR and its pod (workload + sandbox-runtime containers) exist, then delete it.
5. Validate actual runtime isolation, not just a working gateway: a policy-allowed egress destination succeeds while an unauthorized destination is blocked by the supervisor's kernel-mediated network path, and the outer-fence Kubernetes NetworkPolicy for the sandbox pod is present.

## Infrastructure Requirements

- **Resource Profile:** medium (gateway: 1Gi RAM / 500m CPU requests; supervisor pool: small)
- **GPU Required:** no
- **Persistent Storage:** gateway SQLite data PVC 1Gi and per-sandbox workspace PVC 2Gi, both on `ibmc-vpc-block-10iops-tier` (block-backed, required for SQLite WAL)
- **Sidecar Containers:** none; the trusted supervisor runs as a shared-pool Deployment (`supervisor_topology: gateway`)

### Deployment model

- `deployment_model: deployment` (long-running services; the chart renders the gateway as a StatefulSet for its SQLite volume and the supervisor as a Deployment)
- `listens_on_port: true` — gateway gRPC/HTTP on 8080, health on 8081, metrics on 9090
- `long_running: true`
- `test_strategy: exec` (mixed HTTP + gRPC/exec validation driven from the validation runner)
- `needs_llm_api: false` (the gateway can front LLM providers, but the PoC validates the runtime without an external LLM API)

### OpenShift specifics

- Namespace `poc-openshell` (SCC range 1001650000/10000, MCS s0:c41,c5)
- Preinstalled ClusterRole `autopoc-openshell-runtime` (runtimeclasses/priorityclasses get, tokenreviews create, nodes get/list/watch, namespaces[poc-openshell] get) matches the chart's shared-workspace-mode cluster role exactly; it is bound to SA `openshell` out of band, so the chart sets `rbac.clusterScoped.create=false`
- The chart's OpenShift SCC overlay is applied (`runAsUser`/`fsGroup` null) so restricted-v2 assigns IDs; no privileged SCC is requested
- Agent Sandbox controller is preinstalled and running in `agent-sandbox-system`; the chart preflight check stays enabled
- The `autopoc-openshell-validation` Role (bound to `autopoc-test/autopoc-runner`) is extended with namespace-scoped `secrets` get/list so the test client can read the mTLS client certificate Secret; this is the only RBAC change beyond the operator-prepared scope

## Test Scenarios

### Scenario 1: gateway-health
- **Description:** The gateway health endpoint responds and reports a healthy gateway (database check included).
- **Type:** http
- **Input:** `GET http://openshell.poc-openshell.svc.cluster.local:8081/health`
- **Expected:** HTTP 200 with JSON body whose `status` is `healthy`
- **Timeout:** 120 (gateway may still be initializing)

### Scenario 2: gateway-metrics
- **Description:** The gateway exposes Prometheus metrics.
- **Type:** http
- **Input:** `GET http://openshell.poc-openshell.svc.cluster.local:9090/metrics`
- **Expected:** HTTP 200 with Prometheus text exposition format content
- **Timeout:** 30

### Scenario 3: gateway-api
- **Description:** The gRPC control-plane API answers over mTLS using the project's Python SDK (client certificate from the chart-generated `openshell-client-tls` Secret).
- **Type:** exec
- **Input:** `SandboxClient(endpoint="openshell.poc-openshell.svc.cluster.local:8080", tls=TlsConfig(ca, cert, key))`; call `health()` and `list()` sandboxes in workspace `default`
- **Expected:** gRPC Health RPC returns a healthy response; sandbox listing succeeds (zero or more entries)
- **Timeout:** 60

### Scenario 4: sandbox-lifecycle
- **Description:** A sandbox created through the gRPC API is materialized by the Agent Sandbox controller into a pod containing the workload image and the source-built sandbox runtime, runs a command, and is cleanly deleted.
- **Type:** exec
- **Input:** SDK `create(workspace="default", spec=SandboxSpec(policy=...))`, then `wait_ready`, then `exec(["sh", "-c", "echo openshell-poc-marker"])`; then `delete` + `wait_deleted`
- **Expected:** sandbox reaches ready; exec output contains the marker; an Agent Sandbox CR and a pod with a sandbox-runtime container exist in `poc-openshell` while running; the CR/pod are removed after deletion
- **Timeout:** 300

### Scenario 5: network-policy-enforcement
- **Description:** Actual runtime isolation: egress is mediated by the supervisor (seccomp-intercepted connect + policy decision) and fenced by a Kubernetes NetworkPolicy. A policy-allowed destination succeeds; an unauthorized destination is blocked.
- **Type:** exec
- **Input:** inside the scenario-4 sandbox (policy allows `example.com:80/443` tcp, binaries `/**`): (a) `curl http://example.com/` expecting HTTP 200; (b) `curl http://198.51.100.1/` (TEST-NET-1, not in policy) expecting a non-zero exit/connection failure; (c) verify a NetworkPolicy governing the sandbox pod exists in `poc-openshell` (outer fence)
- **Expected:** (a) succeeds with 200; (b) fails (connection refused/reset, i.e. denied at the kernel-mediated boundary); (c) the outer-fence NetworkPolicy is present. If the sandbox image lacks curl, the same checks run via python3 or bash; the tool used is recorded.
- **Timeout:** 180

## Dockerfile Considerations

- All three components are built from the pinned source in a multi-stage UBI9 build. The builder stage installs the Rust 1.95.0 toolchain via rustup plus `gcc gcc-c++ make cmake pkg-config clang clang-devel libclang openssl-devel perl-core` (aws-lc-sys and vendored z3 need cmake + a C compiler; z3-sys bindgen needs libclang).
- Build commands (matching the project's CI build modes):
  - gateway: `cargo build --locked -p openshell-gateway --no-default-features --features compute-driver-kubernetes,vendored-z3` (Kubernetes compute driver is the only driver the chart selects; telemetry compiled out to match `telemetryEnabled: false`)
  - supervisor: `cargo build --locked -p openshell-supervisor --no-default-features --features defaults-without-telemetry` (keeps bundled CA roots required for TLS mediation)
  - sandbox: `cargo build --locked -p openshell-sandbox`
- Runtime stages use `registry.access.redhat.com/ubi9/ubi-minimal` (glibc present for the GNU-linked gateway/supervisor binaries; the static musl sandbox binary runs on any base). Binaries keep their canonical paths (`/usr/local/bin/openshell-gateway`, `/openshell-supervisor`, `/openshell-sandbox`). Final `USER 1001` with `chgrp -R 0` for OpenShift arbitrary-UID assignment.
- Gateway exposes 8080 (gRPC/HTTP), 8081 (health), 9090 (metrics) — all non-privileged.
- Build context is the repository root (48 MB); a `.dockerignore` excludes `.git`, docs, and unrelated trees. Builds run as OpenShift binary builds in `autopoc-test-builds` and push to Quay with tag `f4a6137` (short pinned-commit hash, immutable per source).

## Deployment Considerations

- Deployment is via the project's own Helm chart (`deploy/helm/openshell`) — the first-class OpenShift path — with release name `openshell` in namespace `poc-openshell`.
- Values overlay (committed under `kubernetes/`):
  - `global.image.registry=quay.io/aicatalyst`, `global.image.tag=f4a6137`, `pullPolicy=Always`; component repositories `openshell-gateway`, `openshell-supervisor`, `openshell-sandbox`
  - `serviceAccount.create=false`, `serviceAccount.name=openshell` (preinstalled binding target); `rbac.create=true`, `rbac.clusterScoped.create=false`
  - OpenShift SCC overlay: `podSecurityContext=null`, `securityContext.runAsUser=null`, `supervisor.podSecurityContext.{runAsUser,runAsGroup,fsGroup}=null` so restricted-v2 assigns IDs
  - `gatewayConfig.openshell.drivers.kubernetes.supervisor_topology: gateway` (shared supervisor pool Deployment); `workspaceMode` stays `shared`
  - `server.telemetryEnabled=false`; `server.dataStorageSize=1Gi`, `server.dataStorageClass=ibmc-vpc-block-10iops-tier`, `server.workspaceDefaultStorageSize=2Gi`, `server.workspaceStorageClass=ibmc-vpc-block-10iops-tier`
  - `server.auth.allowUnauthenticatedUsers=true` with mTLS kept mandatory (the chart-generated client certificate is the access gate; the caller is promoted to the local-dev principal, the project's own OpenShift e2e posture)
  - `pkiInitJob.serverDnsNames` extended with `openshell.poc-openshell.svc` and `openshell.poc-openshell.svc.cluster.local` so the in-cluster FQDN validates against the server certificate
  - `agentSandbox.preflight.enabled=true`
- The chart's pre-install `pkiInitJob` runs `openshell-gateway generate-certs` from the source-built gateway image to create `openshell-server-tls`, `openshell-client-tls`, and the JWT signing Secret.
- Tests run from the validation runner (`autopoc-test/autopoc-runner`, Role `autopoc-openshell-validation` in `poc-openshell`) against `openshell.poc-openshell.svc.cluster.local`; no ports are exposed cluster-wide and no Routes are created.
- Skip/failure reporting: if the Agent Sandbox controller or CNI NetworkPolicy enforcement is unavailable at runtime, the affected scenario is recorded as an explicit skip/failure with the observed reason — a working gateway alone does not establish sandbox isolation.
