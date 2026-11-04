# Image Review — v3 (Visual Communication) — RE-REVIEW

Reviewer role: IMAGE (visual communication only).
Scope: 3 inline Mermaid diagrams, 0 raster/image placeholders (`![...]`). Per rubric, Mermaid is evaluated on **clarity**, **diagram type**, and presence of a Red Hat `%%{init}%%` theme block. Missing brand hex / aspect ratios are NOT penalized.

This is a re-review of the revised draft. v3 made three image-related changes: (1) added a caption line under each diagram, (2) dashed the control-plane CR edge in Figure 1, (3) labeled the mount edges in Figure 2. All three map directly to items raised in the v1 image review.

## Inventory

| # | Location (section) | Type | `%%{init}%%` | Verdict |
|---|---|---|---|---|
| D1 / Fig 1 | "The components we chose to deploy" | `graph LR` flow | Present (RH vars) | Clear, correct type; CR edge now dashed + captioned |
| D2 / Fig 2 | "Deploying to the cluster" | `graph TD` + `subgraph` | Present (RH vars) | Clear, correct type; mount edges now labeled "mounts" |
| D3 / Fig 3 | "Running the proof-of-concept tests" | `flowchart TD` | Present (RH vars) | Clear, correct type; now captioned |

All three use the identical theme block:
`primaryColor #EE0000`, `primaryTextColor #fff`, `primaryBorderColor #A30000`, `lineColor #6A6E73`, `secondaryColor #F0F0F0`, `tertiaryColor #0066CC` — all valid Red Hat brand hex values. Confirmed present in all three; unchanged from v1/v2.

## Per-diagram feedback

**Fig 1 — Component flow.** The v1 loop-readability nit is resolved. The `Agent Sandbox CR` branch is now drawn with dashed edges (`G -.-> A -.-> X`), visually separating control-plane objects from the solid runtime path, and the caption explicitly states "The dashed edges are control-plane objects, not runtime hops." Edge labels still carry real signal ("mTLS gRPC 8080", "mediates policy", "seccomp + Landlock"). Left-to-right is the right type for a linear data/control path. Clean now.

**Fig 2 — Namespace topology.** The v1 link-ambiguity nit is resolved in the way that mattered: the `GW --- PVC` / `GW --- SEC` links are now labeled "mounts", so it is unambiguous what the volumes/Secrets attach to. `subgraph poc-openshell` + node/role annotations (worker vs GPU, ports, PVC sizes) remains the correct topology idiom. Minor residual: the mount edges are still undirected (`---`) while the `mediates` edge is directed (`-->`) — a light stylistic inconsistency, not a comprehension problem.

**Fig 3 — Test-outcome tree.** `flowchart TD` for the 5→(3/1/1) split with the error node tracing to the 12-secondary-volume root cause is appropriate and honest. Now captioned. Still sits directly under the results table, so it partially duplicates it — an optional trim, not a defect.

## Alt text (captions)

Captions were added to all three — the weakest v1 dimension, now materially improved:
- Fig 1: "OpenShell component flow. The dashed edges are control-plane objects, not runtime hops." — descriptive, conveys purpose, and doubles as the disambiguation for the dashed edges. Strong.
- Fig 2: "poc-openshell topology after the operator-assisted placement." — descriptive, adds deployment context. Good.
- Fig 3: "The PoC outcome in one view." — conveys purpose but thin; it does not state the actual 3/1/1 result, so a screen reader still leans on the table.

## Missing image opportunities

None required — the three diagrams cover architecture, deployment, and results. The optional v1 suggestion (a short sequence diagram for the sandbox-lifecycle failure: pod → CSI `FailedAttachVolume` → 240s timeout) remains unaddressed; it would make the "real storage limit, not a readiness race" argument more vivid. Not required.

## Scores

| Dimension | Weight | v1 | v3 | Rationale |
|---|---|---|---|---|
| Placement rationale | 2x | 9 | 9 | Each diagram sits in the section it explains; all aid comprehension, none decorative |
| Prompt specificity (clarity & type) | 2x | 8 | 9 | Both v1 clarity nits resolved: D1 CR edge dashed, D2 mount edges labeled; all correctly typed |
| Brand compliance | 2x | 9 | 9 | All three carry a full `%%{init}%%` block with valid Red Hat hex (#EE0000/#A30000/#6A6E73/#F0F0F0/#0066CC) |
| Aspect ratio & sizing | 1x | 8 | 9 | Not penalized per rubric; Mermaid auto-sizes, no awkward ratios |
| Alt text quality | 1x | 5 | 8 | Captions added to all three; Fig 1 strongest, Fig 3 thinnest |
| Image count | 1x | 9 | 9 | 3 visuals, well under cap, each earns its place (D3 mildly overlaps the table) |

**Weighted total** = (9×2)+(9×2)+(9×2)+(9×1)+(8×1)+(9×1) = 18+18+18+9+8+9 = **80**
**Normalized** = (80 / 90) × 10 = **8.9**

## Summary

Strong re-review. All three v1 image asks are resolved: captions added to every diagram (alt-text jumps 5→8), the Figure 1 control-plane CR edge is now dashed and explained (loop-readability cleared), and the Figure 2 mount edges are labeled (link ambiguity cleared). All diagrams remain correctly typed and themed with the Red Hat palette. Remaining items are minor: Figure 3 still duplicates the results table above it (optional trim), the Figure 2 mount edges are still undirected vs the directed `mediates` edge, and the Figure 3 caption is thinner than the other two. Optional, not blocking: a sequence diagram for the sandbox-lifecycle failure.
