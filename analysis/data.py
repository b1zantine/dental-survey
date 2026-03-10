"""Data loading, cleaning, and score construction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from analysis.config import (
    AGE_ORDER,
    ATTITUDE_ITEMS,
    ATTITUDE_REVERSE_ITEMS,
    ATTITUDE_RESPONSE_ORDER,
    ATTITUDE_VALUE_MAP,
    EXPERIENCE_ORDER,
    GENDER_ORDER,
    GROUP_VARS,
    KNOWLEDGE_ITEMS,
    LOCALITY_NORMALIZATION,
    MAJOR_LOCALITY_MIN_COUNT,
    PRACTICE_ITEMS,
    PREVIOUS_TREATMENT_ORDER,
    RAW_TO_SNAKE,
    SAMPLE_SOURCE_ORDER,
    STANDARD_TREATMENT_ORDER,
    WORK_MODE_ORDER,
)


def _trim_strings(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    object_columns = result.select_dtypes(include=["object"]).columns
    for column in object_columns:
        result[column] = (
            result[column]
            .fillna("")
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    return result


def normalize_locality(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return "Unknown"
    folded = re.sub(r"[^a-z0-9 ]+", "", cleaned.casefold())
    folded = re.sub(r"\s+", " ", folded).strip()
    if folded in LOCALITY_NORMALIZATION:
        return LOCALITY_NORMALIZATION[folded]
    titled = cleaned.title()
    titled = titled.replace("Jp ", "JP ").replace("Cv ", "CV ")
    return titled


def normalize_treatments(value: str, other: str) -> str:
    parts = []
    if value:
        parts.extend(part.strip() for part in value.split(",") if part.strip())
    if other:
        parts.append(f"Other: {other.strip()}")

    seen = []
    for part in parts:
        if part not in seen:
            seen.append(part)

    base = [part for part in seen if not part.startswith("Other: ")]
    base.sort(key=lambda item: STANDARD_TREATMENT_ORDER.index(item) if item in STANDARD_TREATMENT_ORDER else len(STANDARD_TREATMENT_ORDER))
    extras = [part for part in seen if part.startswith("Other: ")]
    return ", ".join(base + extras)


def _categorical(series: pd.Series, categories: Iterable[str]) -> pd.Series:
    return pd.Categorical(series, categories=list(categories), ordered=True)


def load_raw_datasets(augmented_csv: str | Path, observed_csv: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    augmented_df = pd.read_csv(augmented_csv)
    observed_df = pd.read_csv(observed_csv)
    return augmented_df, observed_df


def validate_prefix_alignment(augmented_raw: pd.DataFrame, observed_raw: pd.DataFrame) -> None:
    if len(observed_raw) != 101:
        raise ValueError(f"Expected 101 observed rows, found {len(observed_raw)}.")
    if len(augmented_raw) - len(observed_raw) != 150:
        raise ValueError(f"Expected 150 generated rows, found {len(augmented_raw) - len(observed_raw)}.")

    normalized_aug = _trim_strings(augmented_raw.rename(columns=RAW_TO_SNAKE)).fillna("")
    normalized_obs = _trim_strings(observed_raw.rename(columns=RAW_TO_SNAKE)).fillna("")
    common_columns = [column for column in normalized_obs.columns if column in normalized_aug.columns]
    if not normalized_aug.loc[: len(normalized_obs) - 1, common_columns].reset_index(drop=True).equals(
        normalized_obs.loc[:, common_columns].reset_index(drop=True)
    ):
        raise ValueError("The observed file is not an exact prefix of the augmented file.")


def _decode_index_response(code: str, options: list[str]) -> str:
    if pd.isna(code) or code == "":
        return ""
    try:
        return options[int(code)]
    except (IndexError, TypeError, ValueError):
        return ""


def clean_dataset(augmented_raw: pd.DataFrame, observed_raw: pd.DataFrame) -> pd.DataFrame:
    validate_prefix_alignment(augmented_raw, observed_raw)

    df = augmented_raw.rename(columns=RAW_TO_SNAKE).copy()
    df = _trim_strings(df)

    df["sample_source"] = np.where(np.arange(len(df)) < len(observed_raw), "observed", "generated")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce")
    df["knowledge_score_raw"] = pd.to_numeric(df["knowledge_score_raw"], errors="coerce")
    df["knowledge_total_raw"] = pd.to_numeric(df["knowledge_total_raw"], errors="coerce")

    df["locality_normalized"] = df["locality"].apply(normalize_locality)
    locality_counts = df["locality_normalized"].value_counts()
    df["locality_group"] = df["locality_normalized"].where(
        df["locality_normalized"].map(locality_counts).ge(MAJOR_LOCALITY_MIN_COUNT),
        other="Other",
    )
    df["designation_clean"] = df["designation"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    df["treatments_normalized"] = [
        normalize_treatments(treatment, other)
        for treatment, other in zip(df["treatments"], df["treatments_other"])
    ]
    df["treatment_any"] = np.where(df["previous_treatment"].eq("Yes"), "Yes", "No")
    df["duration_artifact"] = df["duration_minutes"].gt(60)

    knowledge_score = np.zeros(len(df), dtype=int)
    for item in KNOWLEDGE_ITEMS:
        item_id = item["id"]
        df[f"{item_id}_label"] = df[item_id].apply(lambda code: _decode_index_response(code, item["options"]))
        df[f"{item_id}_is_correct"] = df[item_id].astype(str).eq(item["correct_code"]).astype(int)
        knowledge_score += df[f"{item_id}_is_correct"].to_numpy()
    df["knowledge_score"] = knowledge_score
    df["knowledge_pct"] = df["knowledge_score"] / len(KNOWLEDGE_ITEMS) * 100.0

    attitude_score = np.zeros(len(df), dtype=int)
    for item in ATTITUDE_ITEMS:
        item_id = item["id"]
        values = df[item_id].map(ATTITUDE_VALUE_MAP)
        if values.isna().any():
            missing = sorted(df.loc[values.isna(), item_id].dropna().unique())
            raise ValueError(f"Unmapped attitude responses in {item_id}: {missing}")
        if item_id in ATTITUDE_REVERSE_ITEMS:
            values = 5 - values
        df[f"{item_id}_score"] = values.astype(int)
        attitude_score += df[f"{item_id}_score"].to_numpy()
    df["attitude_score"] = attitude_score
    df["attitude_pct"] = df["attitude_score"] / (len(ATTITUDE_ITEMS) * 4) * 100.0

    practice_score = np.zeros(len(df), dtype=int)
    for item in PRACTICE_ITEMS:
        item_id = item["id"]
        df[f"{item_id}_label"] = df[item_id].apply(lambda code: _decode_index_response(code, item["options"]))
        mapped = df[item_id].astype(str).map(item["score_map"])
        if mapped.isna().any():
            missing = sorted(df.loc[mapped.isna(), item_id].dropna().astype(str).unique())
            raise ValueError(f"Unmapped practice responses in {item_id}: {missing}")
        df[f"{item_id}_score"] = mapped.astype(int)
        practice_score += df[f"{item_id}_score"].to_numpy()
    df["practice_index"] = practice_score
    df["practice_pct"] = df["practice_index"] / (len(PRACTICE_ITEMS) * 3) * 100.0

    df["age_range"] = _categorical(df["age_range"], AGE_ORDER)
    df["gender"] = _categorical(df["gender"], GENDER_ORDER)
    df["professional_experience"] = _categorical(df["professional_experience"], EXPERIENCE_ORDER)
    df["work_mode"] = _categorical(df["work_mode"], WORK_MODE_ORDER)
    df["previous_treatment"] = _categorical(df["previous_treatment"], PREVIOUS_TREATMENT_ORDER)
    df["sample_source"] = _categorical(df["sample_source"], SAMPLE_SOURCE_ORDER)
    df["locality_group"] = pd.Categorical(df["locality_group"])

    recomputed = (
        sum(df[item["id"]].astype(str).eq(item["correct_code"]).astype(int) for item in KNOWLEDGE_ITEMS)
        .astype(int)
    )
    if not df["knowledge_score"].equals(recomputed):
        raise ValueError("Knowledge score validation failed.")
    if pd.Series(df["knowledge_score_raw"]).fillna(-1).astype(int).equals(df["knowledge_score"]):
        raise ValueError("Recomputed knowledge score still matches the raw score field unexpectedly.")

    return df


def build_metadata(df: pd.DataFrame) -> dict[str, object]:
    observed = df.loc[df["sample_source"].astype(str) == "observed"]
    generated = df.loc[df["sample_source"].astype(str) == "generated"]
    metadata = {
        "observed_rows": int(len(observed)),
        "generated_rows": int(len(generated)),
        "total_rows": int(len(df)),
        "observed_last_timestamp": observed["timestamp"].max().isoformat() if not observed.empty else None,
        "augmented_last_timestamp": df["timestamp"].max().isoformat() if not df.empty else None,
        "duration_artifact_rows": int(df["duration_artifact"].sum()),
        "major_localities": sorted(
            locality for locality in df["locality_group"].astype(str).unique() if locality != "Other"
        ),
        "group_variables": [item["column"] for item in GROUP_VARS],
    }
    return metadata


def save_metadata(metadata: dict[str, object], path: str | Path) -> None:
    path = Path(path)
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
