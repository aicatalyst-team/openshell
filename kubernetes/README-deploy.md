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
