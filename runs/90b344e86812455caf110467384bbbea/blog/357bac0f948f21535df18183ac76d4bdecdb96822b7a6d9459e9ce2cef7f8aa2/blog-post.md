## NVIDIA OpenShell on OpenShift AI: a sandboxed agent PoC

**A 5-scenario proof of concept (PoC) under restricted-v2, with a limited network observation**

An agent sandbox that can't be bounded is a liability the moment an agent starts running code. We deployed NVIDIA OpenShell on Red Hat OpenShift AI because platform teams keep asking whether an agent runtime can be constrained without giving it a privileged node. This PoC shows that OpenShell's gateway, supervisor, and sandbox deploy from source under restricted-v2, that all 5 planned scenarios passed, and that the one network observation we could make from outside the app namespace behaved as a limited ingress pattern. **Start here:** explore [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai), then read the [PoC report](https://github.com/aicatalyst-team/openshell/tree/autopoc-artifacts/runs/90b344e86812455caf110467384bbbea) for the evidence chain.

## What NVIDIA OpenShell adds to an agent platform

OpenShell is a runtime for autonomous AI agents, and its job is to give each agent a bounded place to run. It's a Rust workspace with 3 cooperating components and a Python SDK. The gateway is the gRPC control plane: it authenticates clients over mutual TLS (mTLS), registers sandboxes, routes execution to the right sandbox runtime, and serves a health endpoint on port 8081 and Prometheus metrics on port 9090. The supervisor is a shared-pool process supervisor that hosts sandbox workloads, deployed as a Deployment with a pod disruption budget (PDB). The sandbox runtime is a static binary injected into each sandbox Pod alongside the workload container, and it's the agent the gateway talks to. The Python SDK wraps all of it behind a single client for create, get, delete, and exec.

<div class="mermaid" role="img" aria-label="A Python SDK client calls the gateway over mutual TLS. The gateway routes execution to a sandbox pod containing a sandbox runtime and a workload container. A shared supervisor pool hosts sandbox pods, and an ingress NetworkPolicy restricts sandbox port 2222 to the gateway.">
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EE0000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#A60000', 'lineColor': '#6A6E73', 'secondaryColor': '#F0F0F0', 'tertiaryColor': '#0066CC'}}}%%
graph LR
    SDK[Python SDK] -->|mTLS gRPC| GW[Gateway control plane]
    GW -->|routes execution| POD[Sandbox Pod]
    POD --> RT[Sandbox runtime]
    POD --> WL[Workload container<br/>external base image]
    SUP[Shared supervisor pool<br/>Deployment with PDB] -.hosts.-> POD
    NP[Ingress NetworkPolicy] -.port 2222 restricted to gateway.-> POD
</div>

*Figure 1: The control path as deployed, with the sandbox's ingress policy.*

## Why it matters for OpenShift AI

Platform engineers need a way to separate agent execution from the control plane. OpenShell provides distinct gateway, supervisor, and sandbox components. It ships a first-party Helm chart with an OpenShift overlay for restricted-v2 Security Context Constraints (SCC). In our deployment, mTLS terminates at the gateway.

## Preparing for deployment

We pinned the source at a specific commit and worked from a fork so every change stayed traceable. The deployment vehicle is the project's own Helm chart, layered with the restricted-v2 OpenShift overlay and a small PoC values file. Two placement constraints shaped the values: the gateway consumes a block persistent volume claim (PVC), so it's pinned to a specific worker node, and each sandbox Pod is pinned to the same node through the public node_selector field in the driver config.

## Containerizing for OpenShift

We built 3 core and bootstrap images from the pinned source with UBI-based Dockerfiles and published them to Red Hat Quay under a run-unique tag. Existing tags stayed untouched.

| Component | Base image | Build time | Result |
|---|---|---:|---|
| Gateway | UBI9 builder + ubi9-minimal runtime | 41m50s | Pushed |
| Supervisor | UBI9 builder + ubi9-minimal runtime | 22m55s | Pushed |
| Sandbox runtime | UBI9 builder + ubi9-minimal runtime | 10m19s | Pushed |

The gateway build takes longest because it compiles a vendored satisfiability modulo theories (SMT) solver. One distinction worth keeping straight: those 3 are the images we built. The sandbox *workload* environment ran on a separate, external base image from NVIDIA's registry. Air-gapped sites would want to mirror it.

## Deploying to the cluster

With operator-provided storage placement and scoped access prepared before deployment, the Helm install succeeded in a dedicated namespace. Run from deploy/helm/openshell with the saved PoC values:

```
helm install openshell . \
  -f ci/values-openshift-scc.yaml \
  -f poc/poc-values.yaml \
  -n <namespace>
```

What we observed afterward is configuration, not a certification, but it's the kind of posture you want to see: restricted-v2 and nonroot, no privileged or anyuid SCC, no cluster-admin. The gateway terminates mTLS with a run-generated certificate authority that signs both the server and client certificates. Ingress NetworkPolicies restrict the sandbox's port 2222 to the gateway and bound the supervisor. Gateway requests and limits are bounded, and the supervisor pool runs under its PDB.

## Running the PoC tests

We ran 5 scenarios against the live deployment, using the Python SDK over mTLS and kubectl, and every attempt was recorded through the AutoPoC attempt and capture mechanism. All 5 passed: 5 pass, 0 fail, 0 error, 0 skip, 0 incomplete. Every planned scenario has a terminal recorded outcome, which is a statement about planned coverage, not a claim that we covered every functional or security angle.

The health check returned HTTP 200, and the metrics endpoint exposed the expected server metrics. The placement check confirmed the sandbox Pod landed on the required node. The exec output is the one we'd show a skeptic:

```
exec: sh -c "echo POCEXEC-$(hostname); uname -a"
POCEXEC-default--poc-90b344e8
Linux default--poc-90b344e8 5.14.0-570.103.1.el9_6
exit code 0
```

The captured test used these SDK calls after configuring its mTLS client (excerpt, not a complete replay script):

```python
spec = openshell_pb2.SandboxSpec()
spec.template.driver_config.update(
    {"kubernetes": {"pod": {"node_selector": {"kubernetes.io/hostname": NODE}}}}
)
client.create(workspace=WORKSPACE, spec=spec, name=SANDBOX_NAME)
# The original test polls client.get until the sandbox is READY.
res = client.get_session(SANDBOX_NAME, workspace=WORKSPACE).exec(
    ["sh", "-c", "echo POCEXEC-$(hostname); uname -a"], timeout_seconds=40
)
```

The network check is the one to read carefully. From an in-cluster worker outside the app namespace, a plain transmission control protocol (TCP) connection to the gateway's metrics port succeeded, while a plain TCP connection to the sandbox's port 2222 did not.

<div class="mermaid" role="img" aria-label="An in-cluster worker outside the app namespace opens a TCP connection to the gateway pod's metrics port, which succeeds, and attempts a TCP connection to the sandbox pod's port 2222, which does not succeed.">
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EE0000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#A60000', 'lineColor': '#6A6E73', 'secondaryColor': '#F0F0F0', 'tertiaryColor': '#0066CC'}}}%%
graph LR
    W[In-cluster worker<br/>outside the app namespace] -->|TCP to gateway port 9090: succeeded| G[Gateway pod]
    W -.->|TCP to sandbox port 2222: did not succeed| S[Sandbox pod]
</div>

*Figure 2: The network check as recorded: one reachable path, one that did not respond, from a single vantage point.*

That's a limited observed ingress reachability pattern, consistent with the sandbox's ingress NetworkPolicy. It is not proof of policy causation, all network enforcement, egress or filesystem isolation, or production security, and the worker is an in-cluster peer, not a public Internet attacker. The retained evidence supports auditing the run, which is useful, and it isn't a guarantee of full reproducibility.

## What we learned

The headline is that OpenShell deployed to OpenShift from source and its core loop works: create, execute, place, and a network reachability pattern that matched the configured policy in our limited check. The caveats are equally clear. The gateway is a single SQLite-backed replica, which is a functional configuration, not a high-availability (HA) one. The test was smoke-level, so it doesn't establish OpenID Connect (OIDC) workflows, sustained reliability, or production readiness. Placement was validated on a single node, and graphics processing unit (GPU) workloads weren't exercised. The pinned chart includes CI/dev and E2E HA example overlays for a multi-replica gateway with an external database and a 2-replica supervisor pool. This PoC did not test them. Next, exercise those examples, authenticated flows, load, reliability, GPU, and multi-node workloads.

## Try it yourself

This whole path, from pinned commit to 5 passing scenarios, is what AutoPoC automates for OpenShift AI. Point it at a GitHub repository, and it will containerize the components on UBI, deploy them, run the validation suite, and hand you a report. If you're weighing an agentic-AI runtime for your cluster, start with the sandbox boundary and see what [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai) gives you for free.
