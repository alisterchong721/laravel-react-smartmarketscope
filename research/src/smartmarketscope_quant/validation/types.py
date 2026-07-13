from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SampleInterval:
    sample_id: str
    information_start: datetime
    information_end: datetime
    decision_timestamp: datetime
    label_start: datetime
    label_end: datetime

    def __post_init__(self) -> None:
        if not (
            self.information_start
            <= self.information_end
            <= self.decision_timestamp
            <= self.label_start
            <= self.label_end
        ):
            raise ValueError("Sample information/decision/label timestamps are not point-in-time ordered")

    @property
    def interval_start(self) -> datetime:
        return self.information_start

    @property
    def interval_end(self) -> datetime:
        return self.label_end


@dataclass(frozen=True, slots=True)
class ValidationSplit:
    split_id: str
    train_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    purged_ids: tuple[str, ...]
    embargoed_ids: tuple[str, ...]
    train_end: datetime | None
    test_start: datetime
    test_end: datetime
    model_frozen: bool = True


@dataclass(frozen=True, slots=True)
class CPCVPath:
    path_id: int
    group_to_split: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class CPCVResult:
    n_groups: int
    k_test_groups: int
    split_count: int
    path_count: int
    identity_left: int
    identity_right: int
    splits: tuple[ValidationSplit, ...]
    paths: tuple[CPCVPath, ...]
