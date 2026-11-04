# Formatting Review — v2 (re-review)

Re-review of `drafts/v2.md` against `reviewer-formatting.md`. v2 was edited specifically to address v1 formatting findings; each is re-checked below.

## Score Table

| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Heading hierarchy | 1x | 10 | All H2, sentence case, no H1 in body, no skipped levels |
| Code formatting | 1x | 9 | Zero inline backticks in prose; 3 mermaid blocks properly fenced with captions |
| CTA placement | 2x | 9 | Top (L15, docs.redhat.com), mid (L87, redhat.com), closing (L116, unlinked) |
| SEO readiness | 1x | 8 | Primary keywords (OpenShell, Red Hat OpenShift AI, autonomous agents, Kubernetes) in first paragraph; no CMS-level 50–60 char H1 visible in draft |
| Link strategy | 1x | 9 | 3 links, all redhat.com (L11, L15, L87); no competitor links |
| Editorial compliance | 2x | 7 | Oxford commas, official product names, 0 em dashes; HTTP unexpanded, ~10 uncontracted negatives remain |
| Brand standards | 1x | 9 | Mermaid themes use Red Hat palette (#EE0000, #0066CC, #F0F0F0, #6A6E73) |
| Word count | 1x | 9 | 1,249 prose words (1,470 incl. diagrams/tables) — within 800–1300 |

**Weighted total: 86/100 → Normalized: 8.6/10**

## Re-check of v1 Findings

1. **First product mention** — FIXED. L11 first OpenShift mention is "[Red Hat OpenShift AI](https://www.redhat.com/...)"; shortened "OpenShift AI" used correctly thereafter; "RHOAI" never appears.
2. **Acronyms expanded on first use** — PARTIAL. gRPC (L13), RBAC (L19), SCC (L19), SDK (L25), UID (L43), TLS (L56), GPU (L57), API (L87), mTLS (L87), CSI (L89), OIDC (L110) all expanded. **HTTP is not**: first use is the results table L81 ("HTTP 200") with no expansion. Minor: mTLS first appears unexpanded in the L83 table row (expanded 4 lines later in prose); "PoC" appears in the L100 caption without expansion (full form appears earlier, so acceptable).
3. **Inline backticks** — FIXED. Zero backticks outside code fences.
4. **Numerals** — FIXED. "3 of them" (L25), "2 retries" (L45), "2 things" (L54), "5 scenarios / 3 passed, 1 errored, 1 skipped" (L77), "2 practical lessons" (L108), "12 secondary volumes" (L89/L108). Remaining "one" uses (L39, L110, L114, L100) are idiomatic singulars, acceptable; "First/Second" (L108) are ordinal enumerators, acceptable.
5. **Contractions** — PARTIAL. Added: "it's" (L15, L54, L89), "We're" (L87, L106), "That's" (L104, L110), "that's" (L106). Still uncontracted: "did not write" (L11), "does not trust" (L13), "we will show" (L21), "is not / It is / does not" (L39), "does not ship" (L47), "was not enough" (L89), "is not / that is" (L106), "It is not / did not test" (L110). Rubric says aggressive — roughly half the negatives remain long-form.
6. **CTAs + internal link** — FIXED. Top CTA L15 ("a good place to start" → docs.redhat.com), mid CTA L87 ("fastest way to try it" → redhat.com), closing CTA L116 ("Try deploying your own project with AutoPoC"). Closing CTA carries no link of its own (AutoPoC was linked at L87) — acceptable, noted.

## Remaining Issues (line-level)

- L81: expand HTTP on first use → "HTTP (HyperText Transfer Protocol) 200", or move the expansion to L87 prose and accept the table as data.
- L11, L13, L21, L39, L47, L89, L106, L110: contract negatives ("didn't", "doesn't", "we'll", "isn't", "wasn't", "it's", "didn't test").
- L116: optionally attach the AutoPoC link to the closing CTA for a fully linked triad.
- SEO: confirm the CMS title is 50–60 chars containing "OpenShell" + "OpenShift AI" (not visible in draft body).

## Summary

v2 resolves 4 of 6 v1 findings cleanly (product name, backticks, numerals, CTA triad). Two are substantially improved but incomplete: acronyms (HTTP missed) and contractions (~10 long-form negatives remain). Structure, links, brand colors, and length are all compliant. Normalized score **8.6/10**. Recommend a light v3 pass limited to the two partial items.
