# Formatting Review — v1 (Editorial Compliance)

Reviewer role: FORMATTING (editorial standards only — not structure/substance/images).
Draft: `drafts/v1.md` (leading HTML CHANGELOG comment ignored).

## Scores

| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Heading hierarchy | 1x | 9 | All H2, sentence case, no H1, no skipped levels. Minor: "PoC" acronym in H2 (L61) not tied to an expansion. |
| Code formatting | 1x | 6 | Mermaid diagrams are real/runnable, but 11 inline-code backtick spans sit in running prose. |
| CTA placement | 2x | 4 | Closing CTA only ("Try it yourself", L96–100). No top or mid CTA; no redhat.com link. |
| SEO readiness | 1x | 6 | Keyword "OpenShell" in first paragraph (L7). No title/H1 element present to verify 50–60 char title. |
| Link strategy | 1x | 4 | Zero links — no internal redhat.com links, no competitor links. |
| Editorial compliance | 2x | 5 | Oxford commas strong; but product name, acronyms, contractions, and numerals all have gaps. |
| Brand standards | 1x | 8 | Mermaid uses Red Hat red #EE0000 / #A30000 and gray #6A6E73 correctly. |
| Word count | 1x | 9 | 1207 words, within 800–1300. |

**Weighted total:** 9 + 6 + 8 + 6 + 4 + 10 + 8 + 9 = **60 / 100**
**Normalized:** (60 / 100) × 10 = **6.0**

## Em dashes

- True em dash `—`: **0** in the body.
- Double-hyphen `--`: 15 occurrences, **all inside code contexts** (mermaid `-->` arrows L22–26, 58, 80–83; `---` connectors L56–57; table separator L66). None in running prose. Acceptable.

## Editorial compliance checklist

| Rule | Status | Detail |
|---|---|---|
| Sentence-case headings | PASS | All H2 sentence case. |
| No H1 in body | PASS | No H1 present. |
| Oxford commas | PASS | L7, L17, L63, L88, L98 all correct. |
| No backticks in running prose | FAIL | 11 inline spans in prose (see below). |
| Official product names (Red Hat OpenShift AI, never RHOAI) | FAIL | "Red Hat" never appears; first mention is bare "OpenShift AI" (L11/13). "RHOAI" never used (good). |
| Expand acronyms on first use | FAIL | RBAC, gRPC, mTLS, TLS, OIDC, CSI, SDK, HTTP, API, GPU, UID, PoC unexpanded. |
| Aggressive contractions | FAIL | Formal "it is" (L9, L94), "We are" (L73, L90); few contractions overall. |
| Numerals in running text | PARTIAL | Digits used in L31/36/40/45/70/75; words used in L17 "forty", L63 "five/three/one/one", L92 "two". Inconsistent. |
| No em dashes | PASS | 0 in prose. |
| Word count 800–1300 | PASS | 1207. |

## Line-level feedback

- **L7** — `SO_BINDTODEVICE` backticked in prose; "gRPC" unexpanded (Remote Procedure Call).
- **L11** — H2 "Why it matters for OpenShift AI": first product mention should be "Red Hat OpenShift AI".
- **L13** — `restricted-v2` backticked in prose; "RBAC" (Role-Based Access Control) unexpanded.
- **L17** — "forty crates" → "40 crates"; "Python SDK" (Software Development Kit) unexpanded.
- **L31** — `ubi9/ubi-minimal` backticked in prose; "UID" (User ID) unexpanded.
- **L35** — `libclang`, `clang-devel` backticked in prose.
- **L36** — `std::format` backticked in prose.
- **L40** — `poc-openshell` backticked in prose; "RBAC" reused (still unexpanded).
- **L45** — `nodeSelector` backticked in prose; "GPU" (Graphics Processing Unit) unexpanded.
- **L61** — H2 "Running the PoC tests": "PoC" (Proof of Concept) not formally introduced.
- **L63** — "five scenarios", "three passed, one errored, and one was skipped" → 5 / 3 / 1 / 1.
- **L67** — "HTTP 200" (HyperText Transfer Protocol) unexpanded.
- **L70** — `Init:0/2` backticked (table cell, borderline).
- **L73** — "We are" → "we're"; "gRPC API" — "API" (Application Programming Interface) unexpanded.
- **L75** — `FailedAttachVolume` backticked in prose; "CSI" (Container Storage Interface) unexpanded.
- **L90** — "We are not claiming" → "we're not claiming".
- **L92** — "two practical lessons" → "2"; `libclang` backticked in prose.
- **L94** — "it also promotes", "It is not the same" → "it's"; "OIDC" (OpenID Connect) unexpanded; "TLS" unexpanded.
- **L96–100** — Closing CTA only; add a top + mid CTA and a redhat.com link.

## Summary

Solid foundation: clean sentence-case H2 cascade, no H1, consistent Oxford commas, correct Red Hat brand colors, and a compliant word count (1207). The main editorial gaps are (1) the full product name "Red Hat OpenShift AI" never appears, (2) a dozen acronyms are never expanded on first use, (3) 11 backtick-wrapped identifiers sit in running prose, (4) numerals are inconsistent (words vs. digits), and (5) contractions are underused. CTA/link dimensions are the weakest structurally (closing-only CTA, no redhat.com links).

**Overall normalized score: 6.0**
