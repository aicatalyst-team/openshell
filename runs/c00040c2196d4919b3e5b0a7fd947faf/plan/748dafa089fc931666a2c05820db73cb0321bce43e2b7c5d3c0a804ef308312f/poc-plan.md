# OpenShell Fresh PoC Plan

Run: c00040c2196d4919b3e5b0a7fd947faf
Pinned source: f4a6137513b777c9b362be54baf388f7d45398aa

## Objective
Can source-built UBI OpenShell components run under OpenShift restricted-v2 and provide a usable sandbox lifecycle through their actual SDK?
OpenShell intends to govern autonomous agent execution through gateway, supervisor and sandbox policy boundaries. That intent is not a validated security claim.

## Scope and setup
Deploy Helm release openshell only in poc-openshell-story-c00040c2. Adopt operator-provided service account openshell and cluster prerequisites; create no cluster RBAC. Retain supervisor PDB. Pin gateway and sandbox PVC consumers to ocp-gb-xz56l-worker-3-cpu-f88sc using Helm nodeSelector and the source-defined per-sandbox driver config. Use ibmc-vpc-block-10iops-tier for gateway and workspace storage. Worker PVC remains on the separately supplied node.

Build fresh gateway (full features including vendored Z3), supervisor and sandbox runtime from the pinned checkout, using disclosed same-revision reference Dockerfiles. Only Quay tag story-c00040c2 is authorized. The sandbox image can also supply a minimal UBI shell workload; its trusted launcher remains distinct from that workload role.

## Scenarios
| ID | Check | Procedure and success criterion | Budget |
| --- | --- | --- | --- |
| gateway-access | Gateway readiness and mTLS access | Observe ready gateway/supervisor; authenticated API call succeeds and a no-client-certificate call to an authenticated API is rejected. Health alone does not establish authentication. | 90s |
| sandbox-process | Sandbox readiness and process contract | Create unique sandbox through pinned SDK with required node selector. Require READY, then execute a process and verify stdout, stderr and deliberate exit 7; observe non-root UID. Readiness is not process success. | 600s |
| workspace-lifecycle | Persistent workspace lifecycle | Write unique marker, stop/start sandbox, require READY and exact marker readback with unchanged sandbox identity. | 600s |
| network-contrast | Scoped reachable-control network contrast | From the worker, require gateway metrics reachability, then attempt sandbox port 2222 using its observed pod IP. Report reachability contrast only, never policy-enforcement proof. Missing reachable control is an error. | 45s |
| sandbox-cleanup | Run-owned sandbox deletion | Delete only this run's unique sandbox; wait for SDK disappearance and inspect run-owned CR/pod deletion. Do not infer PVC reclamation from logical disappearance. | 180s |

No production security, HA, load, OIDC, filesystem isolation, GPU, broad network enforcement or Kubernetes portability claims. The full prover is included in the gateway build, but no standalone prover CLI proof is planned. Five checks maximum. Each real attempt is recorded before any retry through the bundled capture-execution contract. Preserve failed, errored, skipped and incomplete outcomes separately.

## Failure handling
Build retries at most three; deploy retries at most two, without counter resets. Keep healthy successful component builds. Retain original private logs and sanitized bounded excerpts outside checkout. Mandatory exhausted failures stop the pipeline explicitly. Never reuse previous run attempts or reports. Cloud storage is blocked/outside review-run authorization; complete eligible local report, blog and reviewed sealed inputs without pretending publication succeeded.
