# OpenShell OpenShift AI Fitness

Source revision: f4a6137513b777c9b362be54baf388f7d45398aa
Strategy: redhat-ai-2026. Relationship: adjacent.

| Dimension | Score / 20 | Reason |
| --- | --- | --- |
| Audience value | 17 | Agent developers need bounded execution and policy controls. |
| Strategic alignment | 17 | Agent runtimes and management/security are relevant strategy areas. |
| Strategy fit | 16 | Complements agent platforms rather than serving models itself. |
| Platform leverage | 16 | Native Kubernetes driver, storage, service accounts and NetworkPolicy integration. |
| Demo potential | 16 | Sandbox lifecycle and real process results can be demonstrated. |
| Total | 82 / 100 | Source-based assessment, not runtime certification. |

Strengths: source-visible policy model, multiple SDKs, Helm deployment and native Kubernetes driver.
Risks: kernel isolation prerequisites, CRD/controller dependency, storage placement, native Rust/Z3 builds and production authorization requirements.
No inference, GPU, OpenShift AI integration, HA, load, OIDC, filesystem isolation or broad Kubernetes portability is validated by this evaluation.
