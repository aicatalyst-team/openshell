# Local Executive Input Handoff

Run: `c00040c2196d4919b3e5b0a7fd947faf`

- Original validation: 1 pass, 0 fail, 1 error, 3 skip, 0 incomplete; no validation replay.
- Application objective remains blocked: no shared supervisor attached; root cause unknown.
- Sealed input: `/workspace/render-inputs.zip`, regular file, SHA-256 `647ad00eed09ce632f279470b53dfb6ce5da6c724b7eaaa394ea35719ec5c882`.
- Story/schema/template/policy: nine slides, 3/4/2; Kokoro Heart, speed 0.95; actual audio timing not measured.
- Exact renderer image: `quay.io/aicatalyst/autopoc-executive-renderer@sha256:1c1dc7b1510b25c113eb28a053d1e9f01fe449860171ba9397a62eab6964f215`.
- Independent content approval: `/workspace/review.json`; full actual response `/workspace/review-response.json`; reasoning `/workspace/review-notes.md`.
- Source files: `/workspace/narrative.json`, `/workspace/scenes.json`, `/workspace/visuals.zip`, `/workspace/executive-visuals/manifest.json` and its regular PNG asset.
- Canonical report: `/workspace/evidence/c00040c2196d4919b3e5b0a7fd947faf/staging/poc-report.md`.
- Source revision: `f4a6137513b777c9b362be54baf388f7d45398aa`; packaging/tests branch head `803fba14`.
- Evidence archive: `/workspace/evidence-bundles/c00040c2196d4919b3e5b0a7fd947faf/4bbfe024bdc4abc896cf417543e4bd561c666f2ca9596b8a51254b0273be2386.zip`.
- Public README source context was model-visually inspected; independent reviewer reviewed manifest/text only. No human visual acceptance or listening occurred.
- No deck, PDF, video, rendered browser/source archive, renderer deployment, or Drive publication is claimed.
- Cloud publishing is outside authorization. Prior Drive refresh failed; no refresh or upload was attempted.
- Any isolated-PVC offline-render transfer is operator-assisted transport, not fully unattended execution. This worker did not perform that transfer.

The sealed file binds the reviewed narrative, evidence, scene policy, visual manifest/PNG, and digest-pinned renderer. A separate authorized renderer must use those exact bytes without replaying PoC tests. Renderer execution, media validation, listening and publication remain separate gates.
