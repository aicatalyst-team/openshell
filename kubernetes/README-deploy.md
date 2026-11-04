# OpenShell PoC deployment (run a189bdf54ac849778a8ed7b228db599f)

This PoC deploys the project's own Helm chart — the first-class
OpenShift/Kubernetes path — into the `poc-openshell` namespace.

## Prerequisites (prepared by the operator)

- Agent Sandbox controller running in `agent-sandbox-system`
  (Sandbox CRD `agents.x-k8s.io/v1beta1` served; OVN enforces NetworkPolicy)
- ClusterRole `autopoc-openshell-runtime` and its ClusterRoleBinding to
  ServiceAccount `openshell` in `poc-openshell` (cluster-scoped RBAC applied
  out of band, so the chart sets `rbac.clusterScoped.create=false`)
- Role/RoleBinding `autopoc-openshell-validation` in `poc-openshell` bound to
  `autopoc-test/autopoc-runner` (validation runner: sandboxes, networkpolicies,
  events, pods/exec, pods/portforward, secrets)

## Operator-assisted recovery

- The first Helm install lacked `policy/poddisruptionbudgets` permission.
  An operator applied the namespace-only Role/RoleBinding
  `autopoc-openshell-helm` for `autopoc-test/autopoc-runner`. Kubernetes
  escalation checks cannot be bypassed by applying a RoleBinding before a
  Role. The worker temporarily disabled the one-replica PDB; the final values
  restore the chart's PDB now that the required permission exists.
- IBM CSI rejected the gateway volume attachment on GPU node
  `ocp-gb-xz56l-gpu-l40s-vzwxt`: `over_quota`, maximum 12 secondary volumes.
  The operator rescheduled only the not-yet-started gateway Pod onto
  `ocp-gb-xz56l-worker-1-hhkzb`, which has capacity in the PVC's `eu-gb-1`
  zone. The final `nodeSelector` preserves that placement. No volume data or
  unrelated workloads were deleted, and no privileged SCC was granted.
- This node name is specific to this PoC cluster. On another cluster, select a
  node with available disk attachments in the volume's zone, or omit the
  selector after verifying scheduling/storage capacity.

## Apply order

1. `kubectl apply -f kubernetes/namespace.yaml` (idempotent; namespace exists)
2. `kubectl apply -f kubernetes/serviceaccount.yaml` (gateway SA)
3. `helm install openshell deploy/helm/openshell -n poc-openshell -f kubernetes/helm-values.yaml`

The chart's pre-install `pkiInitJob` runs `openshell-gateway generate-certs`
from the source-built gateway image to create `openshell-server-tls`,
`openshell-client-tls`, and the JWT signing secret.

## Endpoints (in-cluster)

- gRPC/HTTP control plane: `openshell.poc-openshell.svc.cluster.local:8080` (mTLS)
- Metrics: `openshell.poc-openshell.svc.cluster.local:9090/metrics`
- Health: pod-level only (not in the Service) — port 8081 on the gateway pod
- Supervisor pool runtime: `openshell-supervisor.poc-openshell.svc.cluster.local:5500`
