from __future__ import annotations

import itertools
import math

from .splits import apply_embargo_blocks, balanced_groups, purge_overlaps
from .types import CPCVPath, CPCVResult, SampleInterval, ValidationSplit


class CPCVError(ValueError):
    pass


def build_cpcv(
    samples: list[SampleInterval],
    n_groups: int,
    k_test_groups: int,
    embargo_mode: str = "BARS",
    embargo_value=0,
) -> CPCVResult:
    if not (2 <= n_groups <= len(samples)) or not (1 <= k_test_groups < n_groups):
        raise CPCVError("Invalid CPCV group parameters")
    groups = balanced_groups(samples, n_groups)
    combinations = list(itertools.combinations(range(n_groups), k_test_groups))
    expected_splits = math.comb(n_groups, k_test_groups)
    phi = math.comb(n_groups - 1, k_test_groups - 1)
    splits = []
    group_occurrences: dict[int, list[int]] = {group: [] for group in range(n_groups)}

    for split_index, test_groups in enumerate(combinations):
        test_blocks = [groups[group] for group in test_groups]
        test = [sample for block in test_blocks for sample in block]
        train = [sample for group in range(n_groups) if group not in test_groups for sample in groups[group]]
        retained, purged = purge_overlaps(train, test)
        retained, embargoed = apply_embargo_blocks(retained, test_blocks, embargo_mode, embargo_value)
        if not retained:
            raise CPCVError("CPCV_VALIDATION_ENGINE_INVARIANT_FAILED: split has no training data")
        split = ValidationSplit(
            split_id=f"CPCV-{split_index:03d}",
            train_ids=tuple(item.sample_id for item in retained),
            test_ids=tuple(item.sample_id for item in test),
            purged_ids=tuple(item.sample_id for item in purged),
            embargoed_ids=tuple(item.sample_id for item in embargoed),
            train_end=max(item.label_end for item in retained),
            test_start=min(item.decision_timestamp for item in test),
            test_end=max(item.label_end for item in test),
        )
        splits.append(split)
        for group in test_groups:
            group_occurrences[group].append(split_index)

    if len(splits) != expected_splits:
        raise CPCVError("CPCV split count invariant failed")
    if any(len(occurrences) != phi for occurrences in group_occurrences.values()):
        raise CPCVError("CPCV group reuse invariant failed")

    paths = []
    used_segments = set()
    for path_id in range(phi):
        segments = []
        for group in range(n_groups):
            split_id = group_occurrences[group][path_id]
            segment = (group, split_id)
            if segment in used_segments:
                raise CPCVError("CPCV segment reused")
            used_segments.add(segment)
            segments.append(segment)
        paths.append(CPCVPath(path_id=path_id, group_to_split=tuple(segments)))

    identity_left = n_groups * phi
    identity_right = k_test_groups * expected_splits
    if identity_left != identity_right or len(used_segments) != identity_left:
        raise CPCVError("CPCV coverage identity failed")
    return CPCVResult(
        n_groups=n_groups,
        k_test_groups=k_test_groups,
        split_count=expected_splits,
        path_count=phi,
        identity_left=identity_left,
        identity_right=identity_right,
        splits=tuple(splits),
        paths=tuple(paths),
    )
