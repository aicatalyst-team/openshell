# Image Review — v1 (Visual Communication)

Reviewer role: IMAGE (visual communication only).
Scope: 3 inline Mermaid diagrams, 0 raster/image placeholders (`![...]`). Per rubric, Mermaid is evaluated on **clarity**, **diagram type**, and presence of a Red Hat `%%{init}%%` theme block. Missing brand hex / aspect ratios are NOT penalized.

## Inventory

| # | Location (section) | Type | `%%{init}%%` | Verdict |
|---|---|---|---|---|
| D1 | "Setting up for deployment" (L19–27) | `graph LR` flow | Present (6 RH vars) | Clear, correct type |
| D2 | "Deploying to the cluster" (L47–59) | `graph TD` + `subgraph` | Present (6 RH vars) | Clear, correct type |
| D3 | "Running the PoC tests" (L77–84) | `flowchart TD` | Present (6 RH vars) | Clear, correct type |

All three use the identical theme block:
`primaryColor #EE0000`, `primaryTextColor #fff`, `primaryBorderColor #A30000`, `lineColor #6A6E73`, `secondaryColor #F0F0F0`, `tertiaryColor #0066CC` — all valid Red Hat brand hex values.

## Per-diagram feedback

**D1 — Component flow (L19–27).** Left-to-right pipeline is the right choice for a linear data/control path. Edge labels carry real signal ("mTLS gRPC 8080", "seccomp + Landlock", "creates", "materializes"), which makes it genuinely explanatory, not decorative. Minor: the `Agent Sandbox CR` node branches off Gateway and re-merges into the sandbox, which reads slightly as a loop; a thin dashed edge or a small caption would clarify it is a control-plane object, not a runtime hop.

**D2 — Namespace topology (L47–59).** `subgraph poc-openshell` + node/role annotations (worker vs GPU, ports, PVC sizes) is the correct topology idiom and mirrors the prose about the 12-secondary-volume limit. Strong. Minor: `GW --- PVC` / `GW --- SEC` use undirected links; a directed or labeled link ("mounts") would remove ambiguity about what the volumes/Secrets attach to.

**D3 — Test-outcome tree (L77–84).** `flowchart TD` for a 5→(3/1/1) outcome split is appropriate and honest. Minor: this duplicates the results table directly above it. It earns its place as a visual summary, but consider trimming the table or the diagram to one source of truth if layout feels heavy.

## Missing image opportunities

None are strictly required — the three diagrams cover architecture, deployment, and results. One optional win: a short **sequence diagram** for the sandbox-lifecycle failure (pod → CSI `FailedAttachVolume` → 240s timeout) would make the "real storage limit, not a readiness race" argument more vivid than prose alone. Not required.

## Scores

| Dimension | Weight | Score | Rationale |
|---|---|---|---|
| Placement rationale | 2x | 9 | Each diagram sits in the section it explains; all aid comprehension, none decorative |
| Prompt specificity (clarity & type) | 2x | 8 | All three are readable and correctly typed; minor loop-readability (D1) and link-direction (D2) nits |
| Brand compliance | 2x | 9 | All three carry a full `%%{init}%%` block with valid Red Hat hex (#EE0000/#A30000/#6A6E73/#F0F0F0/#0066CC) |
| Aspect ratio & sizing | 1x | 8 | Mermaid auto-sizes; no awkward ratios, not penalized |
| Alt text quality | 1x | 5 | No diagram titles/captions; screen-reader text relies on surrounding prose. Add a short title line to each |
| Image count | 1x | 9 | 3 visuals, well under cap, each earns its place |

**Weighted total** = (9×2)+(8×2)+(9×2)+(8×1)+(5×1)+(9×1) = 18+16+18+8+5+9 = **74**
**Normalized** = (74 / 90) × 10 = **8.2**

## Summary

Visually strong and on-brand. All three diagrams are correctly typed, clearly placed, and themed with the Red Hat palette via `%%{init}%%`. The main gaps are small: add a short accessible title/caption to each diagram (alt-text dimension is the weakest at 5), disambiguate the D1 Agent-Sandbox-CR loop and the D2 undirected mount links, and optionally drop either the results table or the D3 diagram to avoid duplication.
