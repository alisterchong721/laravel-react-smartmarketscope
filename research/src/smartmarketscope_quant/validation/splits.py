from __future__ import annotations

import bisect
from datetime import timedelta

from .types import SampleInterval, ValidationSplit


class ValidationSplitError(ValueError):
    pass


def intervals_overlap(left: SampleInterval, right: SampleInterval) -> bool:
    return left.interval_start <= right.interval_end and left.interval_end >= right.interval_start


def purge_overlaps(
    train: list[SampleInterval], test: list[SampleInterval]
) -> tuple[list[SampleInterval], list[SampleInterval]]:
    if not test:
        raise ValidationSplitError("Purging requires at least one test interval")
    ordered_test = sorted(
        ((sample.interval_start, sample.interval_end) for sample in test),
        key=lambda interval: (interval[0], interval[1]),
    )
    merged: list[list] = []
    for start, end in ordered_test:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    starts = [interval[0] for interval in merged]

    def overlaps_test(candidate: SampleInterval) -> bool:
        index = bisect.bisect_right(starts, candidate.interval_end) - 1
        return index >= 0 and merged[index][1] >= candidate.interval_start

    retained = []
    purged = []
    for candidate in train:
        if overlaps_test(candidate):
            purged.append(candidate)
        else:
            retained.append(candidate)
    if any(overlaps_test(candidate) for candidate in retained):
        raise ValidationSplitError("PURGED_K_FOLD_VALIDATION_INVARIANT_FAILED: overlap remains")
    return retained, purged


def apply_embargo(
    train: list[SampleInterval],
    test: list[SampleInterval],
    mode: str,
    value,
) -> tuple[list[SampleInterval], list[SampleInterval]]:
    if not test:
        raise ValidationSplitError("Embargo requires test samples")
    test_end = max(item.label_end for item in test)
    if mode == "TIME":
        if not isinstance(value, timedelta) or value < timedelta(0):
            raise ValidationSplitError("TIME embargo requires a nonnegative timedelta")
        boundary = test_end + value
        embargoed = [item for item in train if test_end < item.decision_timestamp <= boundary]
    elif mode == "BARS":
        if not isinstance(value, int) or value < 0:
            raise ValidationSplitError("BARS embargo requires a nonnegative integer")
        future = sorted(
            (item for item in train if item.decision_timestamp > test_end),
            key=lambda item: item.decision_timestamp,
        )
        embargoed = future[:value]
    elif mode == "SESSIONS":
        raise ValidationSplitError(
            "EMBARGO_MANAGER_EVIDENCE_INSUFFICIENT: source session calendar and timezone are unknown"
        )
    else:
        raise ValidationSplitError(f"Unsupported embargo mode: {mode}")
    embargoed_ids = {item.sample_id for item in embargoed}
    return [item for item in train if item.sample_id not in embargoed_ids], embargoed


def apply_embargo_blocks(
    train: list[SampleInterval],
    test_blocks: list[list[SampleInterval]],
    mode: str,
    value,
) -> tuple[list[SampleInterval], list[SampleInterval]]:
    if not test_blocks or any(not block for block in test_blocks):
        raise ValidationSplitError("Block embargo requires nonempty test blocks")
    retained = list(train)
    embargoed_by_id: dict[str, SampleInterval] = {}
    for block in test_blocks:
        retained, embargoed = apply_embargo(retained, block, mode, value)
        for sample in embargoed:
            embargoed_by_id[sample.sample_id] = sample
    embargoed_ids = set(embargoed_by_id)
    return (
        [sample for sample in train if sample.sample_id not in embargoed_ids],
        sorted(embargoed_by_id.values(), key=lambda sample: sample.decision_timestamp),
    )


def _balanced_groups(samples: list[SampleInterval], n_groups: int) -> list[list[SampleInterval]]:
    if n_groups < 2 or len(samples) < n_groups:
        raise ValidationSplitError("Not enough samples for requested groups")
    base, extra = divmod(len(samples), n_groups)
    groups = []
    cursor = 0
    for group_index in range(n_groups):
        size = base + int(group_index < extra)
        groups.append(samples[cursor : cursor + size])
        cursor += size
    return groups


def build_walk_forward(
    samples: list[SampleInterval],
    minimum_train_samples: int,
    test_samples: int,
    retraining_delay: timedelta,
) -> list[ValidationSplit]:
    ordered = sorted(samples, key=lambda item: item.decision_timestamp)
    if ordered != samples:
        raise ValidationSplitError("Samples must be supplied chronologically")
    if minimum_train_samples < 1 or test_samples < 1 or retraining_delay < timedelta(0):
        raise ValidationSplitError("Walk-forward sizes and delay are invalid")
    splits = []
    cursor = minimum_train_samples
    while cursor < len(samples):
        test = samples[cursor : cursor + test_samples]
        if not test:
            break
        test_start = min(item.decision_timestamp for item in test)
        train_candidates = [
            item
            for item in samples[:cursor]
            if item.label_end + retraining_delay <= test_start
        ]
        retained, purged = purge_overlaps(train_candidates, test)
        if not retained:
            raise ValidationSplitError("CHRONOLOGICAL_WALK_FORWARD_VALIDATION_INVARIANT_FAILED: no training data")
        train_end = max(item.label_end for item in retained)
        if train_end + retraining_delay > test_start:
            raise ValidationSplitError("Retraining delay invariant failed")
        splits.append(
            ValidationSplit(
                split_id=f"WF-{len(splits):03d}",
                train_ids=tuple(item.sample_id for item in retained),
                test_ids=tuple(item.sample_id for item in test),
                purged_ids=tuple(item.sample_id for item in purged),
                embargoed_ids=(),
                train_end=train_end,
                test_start=test_start,
                test_end=max(item.label_end for item in test),
            )
        )
        cursor += test_samples
    if not splits:
        raise ValidationSplitError("No walk-forward splits could be constructed")
    for previous, current in zip(splits, splits[1:]):
        if current.test_start <= previous.test_end:
            raise ValidationSplitError("Walk-forward test windows overlap")
    return splits


def build_purged_kfold(
    samples: list[SampleInterval],
    n_splits: int,
    embargo_mode: str = "BARS",
    embargo_value=0,
) -> list[ValidationSplit]:
    ordered = sorted(samples, key=lambda item: item.decision_timestamp)
    if ordered != samples:
        raise ValidationSplitError("Samples must be supplied chronologically")
    groups = _balanced_groups(samples, n_splits)
    splits = []
    for index, test in enumerate(groups):
        test_ids = {item.sample_id for item in test}
        train = [item for item in samples if item.sample_id not in test_ids]
        retained, purged = purge_overlaps(train, test)
        retained, embargoed = apply_embargo(retained, test, embargo_mode, embargo_value)
        if not retained:
            raise ValidationSplitError("PURGED_K_FOLD_VALIDATION_INVARIANT_FAILED: no training data")
        splits.append(
            ValidationSplit(
                split_id=f"PKF-{index:03d}",
                train_ids=tuple(item.sample_id for item in retained),
                test_ids=tuple(item.sample_id for item in test),
                purged_ids=tuple(item.sample_id for item in purged),
                embargoed_ids=tuple(item.sample_id for item in embargoed),
                train_end=max(item.label_end for item in retained),
                test_start=min(item.decision_timestamp for item in test),
                test_end=max(item.label_end for item in test),
            )
        )
    return splits


def balanced_groups(samples: list[SampleInterval], n_groups: int) -> list[list[SampleInterval]]:
    return _balanced_groups(samples, n_groups)
