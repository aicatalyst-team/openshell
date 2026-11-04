# OpenShell PoC Kubernetes deployment

Run `ac05c639abd848998db29ce2352d9a0f`, source revision
`f4a6137513b777c9b362be54baf388f7d45398aa`.

## Images

All three are built from this pinned source with UBI builders/runtimes:

- `quay.io/aicatalyst/openshell-gateway:deepseek-ac05c639`
- `quay.io/aicatalyst/openshell-supervisor:deepseek-ac05c639`
- `quay.io/aicatalyst/openshell-sandbox:deepseek-ac05c639`

## Install

```shell
helm upgrade --install openshell ./deploy/helm/openshell \
  --namespace poc-openshell-deepseek \
  -f kubernetes/values-openshell-deepseek.yaml \
  --wait --timeout 20m
```

The operator-prepared namespace, `openshell` ServiceAccount, namespace
validation Role, and the cluster-wide
`autopoc-openshell-deepseek-runtime` ClusterRole/Binding are inputs. The chart
does not create cluster-scoped RBAC.

## Access for validation

The gateway keeps TLS and client-certificate mTLS. For local evaluation, the
runner port-forwards the gateway pod and extracts the generated client bundle:

```shell
kubectl -n poc-openshell-deepseek port-forward pod/<gateway-pod> 8080:8080 8081:8081
kubectl -n poc-openshell-deepseek get secret openshell-client-tls \
  -o jsonpath='{.data.ca\.crt}'  | base64 -d > <private-dir>/ca.crt
kubectl -n poc-openshell-deepseek get secret openshell-client-tls \
  -o jsonpath='{.data.tls\.crt}' | base64 -d > <private-dir>/tls.crt
kubectl -n poc-openshell-deepseek get secret openshell-client-tls \
  -o jsonpath='{.data.tls\.key}' | base64 -d > <private-dir>/tls.key
```

Keep the private TLS files outside the evidence staging area. The chart's
`allow_unauthenticated_users` setting promotes only an already cert-verified
caller to a development principal; it is not production authentication.

## Sandbox workload pinning

The validation SDK creates the reusable workload template described in
`sandbox-workload-template.yaml`. Its `driver_config` pins the sandbox workload
Pod, and therefore the workspace PVC consumer, to
`ocp-gb-xz56l-worker-2-nsrd9`. `allow_driver_config=true` is required and is set
in the Helm values.
