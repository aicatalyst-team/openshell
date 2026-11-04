# Blog Abstract

## Thesis
Deploying OpenShell's kernel-enforced agent sandbox on Red Hat OpenShift AI proves the control plane runs cleanly on the platform, and it surfaces exactly where a real cluster's storage limits meet a demanding sandbox workload.

## Target audience
Platform engineers and ML engineers who run autonomous agent workloads on OpenShift and want a hard execution boundary without giving up the platform's RBAC and SCC model.

## Blog type
Red Hat Developer Blog

## Key points (max 3)
1. All three source-built Rust components (gateway, supervisor, sandbox runtime) build into UBI9 images and deploy through the project's own Helm chart into a single OpenShift namespace with no privileged SCC.
2. The gateway control plane validates end-to-end: health, Prometheus metrics, and the mTLS gRPC API all pass against the live deployment.
3. The sandbox isolation scenarios hit a real platform wall. The lifecycle scenario errored on IBM's 12-secondary-volume quota on the GPU node, and the network-policy scenario was skipped because the sandbox never became ready.

## Products / projects
Red Hat OpenShift AI, Open Data Hub, NVIDIA OpenShell

## CTA
Try deploying your own project with AutoPoC.

## Section outline
1. What is OpenShell?
2. Why it matters for OpenShift AI
3. The components we chose to deploy
4. Containerizing for OpenShift
5. Deploying to the cluster
6. Running the PoC tests (limited scope: 3 pass, 1 error, 1 skip)
7. What we learned (build retries, storage quota, operator assistance)
8. Try it yourself
