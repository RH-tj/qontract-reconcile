# OpenShift Secret deletion safety: failure analysis and reimplementation plan

## Incident and evidence

Qontract-reconcile PR
[#5891](https://github.com/app-sre/qontract-reconcile/pull/5891), merged as
`fa21933730e781faa83a084de31b20e3063001cf`, added a fail-closed guard intended
to block `openshift-vault-secrets` from deleting a Secret referenced by a live
Pod at inventory time. It also widened
`OCCli.get_resources_used_in_pod_spec()` to recognize projected volumes,
in-tree storage plugin references, ephemeral containers, and `imagePullSecrets`.

The same helper is used by `openshift_base.validate_planned_data()` to verify that
resources referenced by planned Deployments and DeploymentConfigs exist. That
preflight has a different contract from deletion safety. After the helper began
returning `imagePullSecrets`, `openshift-saas-deploy-change-tester` required every
pull Secret to exist on each validation cluster. The `thanos-querier` Deployment
in `coo-per-cluster` referenced `quayio`, which was legitimately absent from
several integration clusters, so the preflight registered errors and blocked
App-Interface MR `!217561`. PR
[#5912](https://github.com/app-sre/qontract-reconcile/pull/5912), merged as
`713d77fe32dd5f896b7f74d88effb1b5f804954d`, reverted the feature.

## Broad failure pattern

The defect was semantic coupling through a shared utility:

1. A safety feature needed a broader definition of "Secret reference."
2. That definition was added to a generic parser already used as policy by other
   callers.
3. Focused tests proved the new deletion gate and parser, but mocked or omitted
   the independent preflight consumer.
4. Dry-run review concentrated on the changed integration's shards, so a failure
   in a different integration (`openshift-saas-deploy-change-tester`) was outside
   the observed proof boundary.
5. A green feature test was treated as evidence for a shared-runtime change even
   though no caller inventory or contract matrix had been retained.

This pattern applies to any shared helper whose return value drives validation,
authorization, deletion, or rollout policy. Expanding syntax support is a
behavior change for every caller, even when the function signature is unchanged.

## Required design guidance

### Separate facts from policy

Do not make `get_resources_used_in_pod_spec()` simultaneously define:

- references that planned-resource validation requires to exist; and
- references that make deleting an existing Secret unsafe.

Keep the existing helper's preflight contract stable. Add a deletion-specific
detector with a name and return type that express its policy, for example
`get_secret_references_for_deletion_guard()`. The deletion detector may share
private parsing primitives, but its public semantics must not leak into generic
validation.

### Consumer contract matrix

| Consumer | Purpose | Reference forms | Failure behavior |
| --- | --- | --- | --- |
| Planned-resource validation | Reject deployable objects whose required mounted/env data is unavailable | Direct Secret/ConfigMap volumes, `envFrom`, and `env.valueFrom`; non-optional only | Register a validation error; preserve cluster/RBAC exceptions |
| Pod recycling | Find workloads affected by a changed managed dependency | Existing historical helper contract | Skip unrelated Pods; preserve current rollout behavior |
| Vault Secret deletion guard | Block deletion when the final Pod inventory snapshot contains a supported Secret reference | Every path in the deletion-detector matrix below | Fail closed on observed references and inventory/RBAC/parser errors |

Any change to this matrix requires caller-level tests before implementation.

### Deletion-detector path matrix

The deletion detector and its parameterized tests must enumerate these exact
Pod-spec paths. Optional references are included because they still express a
configured dependency when the Secret exists.

- `volumes[].secret.secretName`
- `volumes[].projected.sources[].secret.name`
- `volumes[].azureFile.secretName`
- `volumes[].cephfs.secretRef.name`
- `volumes[].cinder.secretRef.name`
- `volumes[].flexVolume.secretRef.name`
- `volumes[].iscsi.secretRef.name`
- `volumes[].rbd.secretRef.name`
- `volumes[].scaleIO.secretRef.name`
- `volumes[].storageos.secretRef.name`
- `volumes[].csi.nodePublishSecretRef.name`
- `containers[].envFrom[].secretRef.name`
- `containers[].env[].valueFrom.secretKeyRef.name`
- `initContainers[].envFrom[].secretRef.name`
- `initContainers[].env[].valueFrom.secretKeyRef.name`
- `ephemeralContainers[].envFrom[].secretRef.name`
- `ephemeralContainers[].env[].valueFrom.secretKeyRef.name`
- `imagePullSecrets[].name`

Adding or removing a path is a contract change and requires updating this matrix,
the detector, the parameterized detector tests, and caller-level gate tests in
the same changeset.

### Proof boundary

Trusted inputs are Kubernetes Pod specs returned by the target cluster and
planned Deployment/DeploymentConfig Pod templates. Supported reference forms
must be enumerated from the Kubernetes API schema. Malformed supported forms and
unavailable Pod inventory are ambiguous and therefore block deletion. Terminal
Pods (`Succeeded` and `Failed`) do not block; all other or missing phases do.
For an inline CSI ephemeral volume, `csi.nodePublishSecretRef` is a
[`LocalObjectReference`](https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/pod-v1/#CSIVolumeSource);
the detector must therefore treat its `name` as a Secret reference in the Pod's
namespace. CSI Secret references owned by a PersistentVolume have a different
cluster-scoped lifecycle and are outside this Pod-spec detector.

### Concurrency contract

The guard is a snapshot-based mitigation, not an atomic Kubernetes invariant.
Kubernetes provides no transaction that both lists Pods and deletes a Secret, so
a Pod may be admitted after the final inventory read and before the Secret delete.
The supported guarantee is therefore deliberately narrow:

> Deletion is blocked when the last successful Pod inventory immediately before
> the delete contains a non-terminal Pod with a supported reference to the Secret.

The implementation must perform that inventory check at the last responsible
moment, with no unrelated I/O between the check and delete, and fail closed when
the inventory cannot be read or parsed. Tests must verify this ordering and name
the residual race; reviews, logs, and rollout documentation must not claim
continuous or atomic protection.

If continuous protection against concurrently admitted Pods becomes a
requirement, this design is insufficient. Reimplementation must stop until a
separate admission/coordination design can reject new references while deletion
is pending and can prove ordering relative to other mutating admission. A Secret
finalizer or delete precondition alone does not close the Pod-admission race.

Required retained evidence:

- a complete `rg`-based caller inventory for every modified shared helper;
- parameterized unit tests for every path in the deletion-detector matrix;
- caller-level tests using the real parser for planned validation, recycling,
  and deletion safety;
- the MR `!215615` base-to-head offline deletion replay;
- the PR #5912 `thanos-querier`/`quayio` preflight regression;
- dry-run evidence for every affected `openshift-vault-secrets` shard and the
  full change-tester result, including unaffected integrations.

## Reimplementation plan

1. **Freeze the existing contract.** Keep
   `get_resources_used_in_pod_spec()` behavior unchanged and land the PR #5912
   offline preflight regression first.
2. **Inventory destructive paths and adopt the snapshot contract.** Trace ordinary
   Secret deletion plus delete/recreate recovery in `openshift_base`; require the
   final Pod inventory check immediately before every `oc delete`, in dry-run and
   wet execution. Do not describe this as atomic protection.
3. **Introduce a dedicated detector.** Parse deletion-relevant Secret references
   without changing planned-resource validation or Pod-recycle semantics. Include
   inline CSI `nodePublishSecretRef` as a same-namespace reference. Use an explicit
   typed result if reference source and ambiguity must be reported.
4. **Implement a fail-closed integration-owned gate.** Enable it only for
   `openshift-vault-secrets`. List Pods in the candidate Secret's namespace,
   ignore terminal Pods, block on a matching observed live Pod, and convert
   inventory, RBAC, or parser failures into integration errors without leaking
   Secret data.
5. **Add complete tests.** Parameterize over every exact path in the
   deletion-detector matrix and cover optional and malformed forms,
   terminal/non-terminal Pods, unrelated resources, an unreferenced Secret,
   Pod-list/RBAC failure, ordinary deletion, and delete/recreate. Assert that the
   final inventory call immediately precedes deletion and document with a
   deterministic concurrent-change test that this is snapshot protection rather
   than an atomic guarantee. Ensure consumer tests call real parsers rather than
   mocking their outputs.
6. **Replay both incidents offline.** Prove MR `!215615` would delete without the
   gate and is blocked with it. Prove `thanos-querier` with an absent `quayio`
   pull Secret still passes `validate_planned_data()`.
7. **Run repository gates.** Run targeted pytest first, then linter, types, and
   `make all-tests` because shared runtime code is affected. Record exact
   commands and results.
8. **Validate the compatibility cohort.** Run the App-Interface change tester
   against the same schema/server/reconcile revisions. Require all affected
   `openshift-vault-secrets` dry-runs and all unrelated integration checks to be
   clean; do not infer success from the vault-secrets shards alone.
9. **Roll out incrementally.** Promote the immutable image, verify its digest,
   observe all vault-secret shards plus change-tester/preflight signals, and keep
   the prior digest ready for rollback. Stop promotion on any new cluster-scoped,
   inventory, RBAC, or unexpected deletion error. Describe the production control
   as observed-reference protection, not as prevention of every concurrent
   Pod/Secret race.

## Local regression added with this analysis

`test_validate_planned_data_ignores_non_preflight_reference_forms` parameterizes
every shared-parser expansion reverted by PR #5912: projected Secret and
ConfigMap volumes, each of the eight in-tree Secret plugins, Secret and ConfigMap
references in ephemeral containers, and `imagePullSecrets`. It invokes
`validate_planned_data()` through the real
`OCCli.get_resources_used_in_pod_spec()` implementation and asserts that none of
those forms causes a namespace lookup, resource lookup, or registered error. The
`quayio` case is the narrowest faithful replay of the production symptom; the
remaining cases enforce the broad cross-consumer contract. This offline test does
not claim to prove live API discovery, RBAC, or cluster admission behavior.
`test_validate_planned_data_preserves_preflight_reference_forms` supplies the
positive controls: direct non-optional Secret and ConfigMap volumes, `envFrom`,
and `env.valueFrom` in both regular and init containers must still produce
resource lookups and missing-resource errors through the real parser. Together,
the positive and negative matrices prevent both accidental contract widening,
loss of an established reference path, and a fail-open always-empty parser.
