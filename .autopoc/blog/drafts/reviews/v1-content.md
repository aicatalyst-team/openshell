# Content Review -- v1

## Scores
| Dimension | Raw (1-10) | Weight | Weighted |
|---|---|---|---|
| Technical accuracy | 9 | 2x | 18 |
| Red Hat voice | 9 | 2x | 18 |
| Audience alignment | 8 | 1x | 8 |
| Originality | 9 | 1x | 9 |
| Evidence & examples | 9 | 2x | 18 |
| Product positioning | 8 | 1x | 8 |
| Human authenticity | 9 | 2x | 18 |
| **Total** | | | **97 / 110 -> 8.8** |

## Verified Technical Claims
- **(a) Failure attribution** -- CORRECT. Line 75 attributes the sandbox-lifecycle error to a storage/volume-attachment quota: volume bound but attachment incomplete, CSI driver over-quota at 12 secondary volumes on the GPU node, `FailedAttachVolume` for the 240s wait, explicitly "not a readiness race in the client." No SDK/cold-start blame.
- **(b) Recovery credited to operator, not self-healing** -- CORRECT. Line 42 "Neither was the software healing itself." PDB Role/RoleBinding provisioned by the operator + Helm upgrade to revision 2 (line 44); operator pinned the gateway to a worker node via `nodeSelector` (line 45).
- **(c) Auth caveat stated** -- CORRECT. Line 94: mTLS required, but a cert-verified caller is promoted to a local-development principal; "It is not the same as production identity, and we did not test production OIDC here."
- **No overclaim of isolation** -- Line 90 explicitly does NOT claim kernel-mediated network/filesystem boundaries are proven.
- **No overclaim of production readiness** -- Scoped to "the gateway works on OpenShift" (line 73); production OIDC left untested.

## Line-Level Feedback
### Technical accuracy
- **Location**: "Running the PoC tests" (line 75) vs "Deploying to the cluster" (line 45)
- **Issue**: The gateway was moved OFF the GPU node to a worker node (freeing a volume slot), yet the sandbox pod then still hit the 12-secondary-volume limit on that same GPU node. A careful reader will ask why freeing one slot did not help. The causal chain is left implicit.
- **Current**: "the pod emitted `FailedAttachVolume` for the entire 240-second wait."
- **Suggested**: "Freeing the gateway's slot alone was not enough; the GPU node's remaining workloads still consumed all twelve secondary-volume slots, so the sandbox's attachment never completed."

### Audience alignment
- **Location**: "What is OpenShell?" (line 7)
- **Issue**: "nested seccomp user-notification" and "SO_BINDTODEVICE" are kernel-level terms the ML-engine half of the target audience may not decode. One short parenthetical each would close the gap without slowing the platform engineer.
- **Current**: "nested seccomp user-notification for syscall and network mediation, and `SO_BINDTODEVICE` to pin sockets."
- **Suggested**: "nested seccomp user-notification (a trap that hands each syscall to the supervisor for a yes/no decision) for syscall and network mediation, and `SO_BINDTODEVICE` to bind each socket to a single network device."

### Product positioning
- **Location**: "Setting up for deployment" (line 17) vs "Deploying to the cluster" (line 40)
- **Issue**: Three components are named as deployable (gateway, supervisor, sandbox runtime), but only two appear as chart workloads (StatefulSet + Deployment). The sandbox runtime actually materializes via the Agent Sandbox CR. Readers may expect a third workload they cannot find.
- **Current**: "we treated three of them as deployable components: the gateway, the supervisor, and the sandbox runtime."
- **Suggested**: "...and the sandbox runtime, which the sandbox pod instantiates through the Agent Sandbox controller rather than the chart."

## AI Writing Flags
### Em Dashes: 1 (body: 0; the single occurrence is in the ignored CHANGELOG comment, line 1)
### Formulaic Phrases: none. No "That changes today", "Enter [product]", "We are pleased to announce", "Moreover/Furthermore", "powerful/seamless/robust", or "Let's". Rhythm is varied and reads clearly human.

## Summary
The post is candid, evidence-rich, and correctly scoped. The single most important content change is closing the causal gap in the error narrative (line 75): explain that moving the gateway off the GPU node freed a slot but the node's other workloads still filled all twelve, so the sandbox still hit the quota. Without that, the recovery section and the failure section read as slightly contradictory.
