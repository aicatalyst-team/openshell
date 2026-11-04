# PoC Plan: OpenShell on OpenShift

- Run ID: `ac05c639abd848998db29ce2352d9a0f`
- Source revision: `f4a6137513b777c9b362be54baf388f7d45398aa`
- Namespace: `poc-openshell-deepseek`
- Helm release: `openshell`
- Target node for data-bearing workloads: `ocp-gb-xz56l-worker-2-nsrd9` (eu-gb-2)
- StorageClass: `ibmc-vpc-block-10iops-tier` (small claims are requested at 10Gi)
- Security posture: OpenShift `restricted-v2`, non-root, no added capabilities, no
  privileged/anyuid SCC.

## Project Classification

- **Type:** `infrastructure` (agent runtime/control plane, with SDK validation)
- **Key technologies:** Rust (gateway, supervisor, sandbox), Kubernetes
  `agents.x-k8s.io` Sandbox CRD, Helm, mTLS, policy proxy, Python SDK.
- **ODH/OpenShift AI relevance:** A governed runtime for autonomous agents is a
  concrete Agentic AI and security/governance capability. It shows how an agent
  sandbox can be deployed as a platform workload with policy-controlled process
  and network access.

## PoC Objectives

1. Build the three trusted runtime binaries from the pinned source with UBI base
   images and no prebuilt core images.
2. Deploy the gateway and a shared supervisor with a restricted-v2-compatible
   security context, pinned block storage, and the preinstalled runtime RBAC.
3. Prove the deployment is functional: health, genuine process execution,
   workspace persistence across a lifecycle restart, and network policy that
   allows a reachable control while denying a second reachable destination.
4. Record real evidence and report the tested scope honestly, separating
   application-level policy mediation from CNI enforcement and excluding
   production OIDC/HA/load/portability claims.

## Infrastructure Requirements

- **Resource profile:** `large` for the gateway (2 CPU / 4Gi request,
  4 CPU / 8Gi limit); supervisor uses the chart default.
- **GPU required:** no.
- **Persistent storage:** gateway SQLite PVC `10Gi`, sandbox workspace PVC
  `10Gi`, both on `ibmc-vpc-block-10iops-tier`.
- **Sidecars:** none explicitly added.
- **Service account:** existing `openshell`; `serviceAccount.create=false`,
  `serviceAccount.name=openshell`.
- **Cluster RBAC:** `rbac.clusterScoped.create=false`; the operator-preinstalled
  ClusterRole/ClusterRoleBinding `autopoc-openshell-deepseek-runtime` is bound to
  the `openshell` service account.
- **Namespace RBAC:** the chart creates/uses namespace-scoped sandbox
  Role/RoleBinding; the operator-preinstalled
  `autopoc-openshell-deepseek-validation` Role allows the runner to inspect
  sandboxes, NetworkPolicies, events, pods/exec, Secrets read, and PDBs.
- **Supervisor:** `gatewayConfig.openshell.drivers.kubernetes.supervisor_topology=gateway`
  (shared pool); `supervisor.podDisruptionBudget.enabled=true`.
- **Driver config:** `allow_driver_config=true` so the workload template can pin
  `kubernetes.pod.node_selector` to `ocp-gb-xz56l-worker-2-nsrd9`.
- **Gateway placement:** `nodeSelector.kubernetes.io/hostname=ocp-gb-xz56l-worker-2-nsrd9`.
- **Authentication for this evaluation:** gateway HTTPS with client-certificate
  mTLS plus `allow_unauthenticated_users=true` to promote the already
  cert-verified caller to a development principal. This is not production
  authentication; OIDC and multi-user access control are out of scope.

## Container Images

| Component | Source | Dockerfile | New image |
|---|---|---|---|
| gateway | pinned source | `Dockerfile.gateway.ubi` | `quay.io/aicatalyst/openshell-gateway:deepseek-ac05c639` |
| supervisor | pinned source | `Dockerfile.supervisor.ubi` | `quay.io/aicatalyst/openshell-supervisor:deepseek-ac05c639` |
| sandbox runtime | pinned source | `Dockerfile.sandbox.ubi` | `quay.io/aicatalyst/openshell-sandbox:deepseek-ac05c639` |

The UBI Dockerfiles are reused from the operator-supplied
`/workspace/reference` compiled references, copied unchanged except for a
provenance comment. They build from the pinned source and do not use prebuilt
core images.

## Test Scenarios

### Scenario 1: `gateway_health`

- **Description:** Probe the gateway health listener after rollout.
- **Type:** HTTP
- **Input:** `GET http://127.0.0.1:8081/healthz` through a port-forward to the
  gateway pod.
- **Expected:** HTTP 200 and a healthy status body.
- **Timeout:** 60 seconds.
- **Scope note:** A health probe is a smoke check; it does not certify
  production readiness, security, or high availability.

### Scenario 2: `sandbox_process_execution`

- **Description:** Create an OpenShell sandbox from a node-pinned workload
  template and execute real commands inside it.
- **Type:** exec (SDK `SandboxSession.exec`)
- **Input:** `uname -s`, `id -u`, and a marker `printf`.
- **Expected:** Sandbox reaches `READY`; commands exit 0; output confirms Linux,
  a non-root UID from the namespace SCC range, and the expected marker.
- **Timeout:** 300 seconds.
- **Cleanup:** Delete the sandbox in a `finally` block even on failure.

### Scenario 3: `sandbox_workspace_persistence`

- **Description:** Prove the workspace PVC survives a sandbox stop/start.
- **Type:** exec + lifecycle (SDK stop/start)
- **Input:** Write `/sandbox/poc-marker`, stop, start, read the marker.
- **Expected:** Marker content is identical after restart; the sandbox reaches
  `READY` again.
- **Timeout:** 420 seconds.
- **Cleanup:** Delete the sandbox in a `finally` block even on failure.

### Scenario 4: `network_allow_control`

- **Description:** Establish that a policy-approved destination is reachable
  from inside the sandbox, so a later denial is meaningful.
- **Type:** exec (SDK `SandboxSession.exec`)
- **Input:** `curl -sS -o /dev/null -w '%{http_code}' https://example.com`
  with a policy allowing `/usr/bin/curl` to `example.com:443`.
- **Expected:** HTTP 200.
- **Independent control:** A plain UBI pod in the same namespace was separately
  observed reaching `example.com`, `api.github.com`, and `pypi.org` before the
  sandbox test.
- **Timeout:** 300 seconds.

### Scenario 5: `network_deny_enforcement`

- **Description:** Prove OpenShell's application-level network policy denies a
  second, independently reachable destination that has no allow rule.
- **Type:** exec + policy evidence
- **Input:** `curl -sS ... https://api.github.com/zen` in the same sandbox
  policy; collect the sandbox log denial line.
- **Expected:** The request fails with a proxy `403`/`policy_denied` result and
  the sandbox log records a `DENIED /usr/bin/curl -> api.github.com:443` event
  with a policy reason.
- **Timeout:** 300 seconds.
- **Scope note:** This tests OpenShell's supervisor/proxy mediation. It does not
  by itself prove that the cluster CNI enforces the generated Kubernetes
  NetworkPolicy; that is reported separately as not independently verified.

## Exclusions and Honest Limits

- No production OIDC, multi-user authorization, HA, load, or failover claims.
- No claim that the cluster CNI enforces NetworkPolicy from object presence.
- No claim of filesystem isolation beyond what the scenarios actually exercise.
- No reused results, counts, evidence, or cloud links from the prior Qwen run.
- Google durable storage is known blocked; report artifacts stay local and
  append-only, with no fabricated cloud links.
