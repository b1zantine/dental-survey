"""Build Bangalore-first analysis summaries for the premium report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as sp_stats
import statsmodels.formula.api as smf

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.config import (  # noqa: E402
    AGE_ORDER,
    ATTITUDE_ITEMS,
    ATTITUDE_RESPONSE_ORDER,
    ATTITUDE_REVERSE_ITEMS,
    ATTITUDE_VALUE_MAP,
    EXPERIENCE_ORDER,
    GENDER_ORDER,
    KNOWLEDGE_ITEMS,
    PRACTICE_ITEMS,
    PRACTICE_SCORE_LABELS,
    PREVIOUS_TREATMENT_ORDER,
    RAW_TO_SNAKE,
    WORK_MODE_ORDER,
)
from analysis.stats import bootstrap_spearman_ci, cliffs_delta, epsilon_squared  # noqa: E402


BANGALORE_DETAIL_FALLBACK = "Bangalore (Unspecified)"
BANGALORE_SCOPE_ORDER = ["Bangalore", "Outside Bangalore"]
BANGALORE_DISPLAY_MIN_COUNT = 3
BANGALORE_CLAIM_MIN_COUNT = 5

BANGALORE_EXACT_MAP = {
    "bangalore": BANGALORE_DETAIL_FALLBACK,
    "bengaluru": BANGALORE_DETAIL_FALLBACK,
    "banglore": BANGALORE_DETAIL_FALLBACK,
    "bangalore urban": BANGALORE_DETAIL_FALLBACK,
    "bangalore rural": BANGALORE_DETAIL_FALLBACK,
    "bellandur": "Bellandur",
    "jp nagar": "JP Nagar",
    "jp nagara": "JP Nagar",
    "j p nagar": "JP Nagar",
    "jp nagar 2nd phase": "JP Nagar",
    "whitefield": "Whitefield",
    "ulsoor": "Ulsoor",
    "hsr layout": "HSR Layout",
    "cv raman nagar": "CV Raman Nagar",
    "rr nagar": "RR Nagar",
    "rr nagar bangalore": "RR Nagar",
    "bommanahalli": "Bommanahalli",
    "hal": "HAL",
    "harlur": "Harlur",
    "haralur": "Harlur",
    "harlur bangalore": "Harlur",
    "kengeri": "Kengeri",
    "shanti nagar": "Shanti Nagar",
    "doddaballapura": "Doddaballapura",
    "chikkanayakanahalli": "Chikkanayakanahalli",
    "yelahanka": "Yelahanka",
    "gottigere": "Gottigere",
    "ramamurthy nagar": "Ramamurthy Nagar",
    "ramamurthy nagar bangalore": "Ramamurthy Nagar",
    "madiwala": "Madiwala",
    "indiranagar": "Indiranagar",
    "marathahalli": "Marathahalli",
    "hebbal": "Hebbal",
    "horamavu": "Horamavu",
    "yeshwantpur": "Yeshwantpur",
    "koramangala": "Koramangala",
}

BANGALORE_CONTAINS_RULES = [
    ("jp nagar", "JP Nagar"),
    ("hsr layout", "HSR Layout"),
    ("rr nagar", "RR Nagar"),
    ("cv raman nagar", "CV Raman Nagar"),
    ("ramamurthy nagar", "Ramamurthy Nagar"),
    ("whitefield", "Whitefield"),
    ("bellandur", "Bellandur"),
    ("ulsoor", "Ulsoor"),
    ("bommanahalli", "Bommanahalli"),
    ("marathahalli", "Marathahalli"),
    ("indiranagar", "Indiranagar"),
    ("koramangala", "Koramangala"),
    ("hebbal", "Hebbal"),
    ("horamavu", "Horamavu"),
    ("yelahanka", "Yelahanka"),
    ("yeshwantpur", "Yeshwantpur"),
    ("gottigere", "Gottigere"),
    ("madiwala", "Madiwala"),
    ("kengeri", "Kengeri"),
    ("harlur", "Harlur"),
    ("haralur", "Harlur"),
    ("hal", "HAL"),
]

OUTSIDE_EXACT_MAP = {
    "guduvanchery": "Guduvancheri",
    "guduvancheri": "Guduvancheri",
    "chromepet": "Chromepet",
    "united states of america": "United States of America",
}

GROUP_CONFIGS = [
    {"column": "age_range", "label": "Age Range", "order": AGE_ORDER},
    {"column": "gender", "label": "Gender", "order": GENDER_ORDER},
    {"column": "professional_experience", "label": "Professional Experience", "order": EXPERIENCE_ORDER},
    {"column": "work_mode", "label": "Work Mode", "order": WORK_MODE_ORDER},
    {"column": "previous_treatment", "label": "Previous Treatment", "order": PREVIOUS_TREATMENT_ORDER},
    {"column": "geo_scope", "label": "Geo Scope", "order": BANGALORE_SCOPE_ORDER},
]
REFERENCE_MAP = {item["column"]: item["order"][0] for item in GROUP_CONFIGS}
METRIC_CONFIGS = [
    {"column": "knowledge_pct", "label": "Knowledge", "raw_label": "Knowledge Score", "max_score": 10},
    {"column": "attitude_pct", "label": "Attitude", "raw_label": "Attitude Score", "max_score": 40},
    {"column": "practice_pct", "label": "Practice", "raw_label": "Practice Index", "max_score": 30},
]


def trim_strings(df: pd.DataFrame) -> pd.DataFrame:
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


def normalize_key(value: str) -> str:
    folded = re.sub(r"[^a-z0-9 ]+", " ", (value or "").casefold())
    return re.sub(r"\s+", " ", folded).strip()


def prettify_label(value: str) -> str:
    label = re.sub(r"\s+", " ", (value or "").strip()).title()
    replacements = {
        "Jp ": "JP ",
        "Hsr": "HSR",
        "Cv ": "CV ",
        "Rr ": "RR ",
        "Usa": "USA",
        "Hal": "HAL",
    }
    for left, right in replacements.items():
        label = label.replace(left, right)
    return label


def normalize_outside_location(raw_value: str, normalized_value: str) -> str:
    if normalized_value in OUTSIDE_EXACT_MAP:
        return OUTSIDE_EXACT_MAP[normalized_value]
    return prettify_label(raw_value) or "Unknown"


def normalize_locality(raw_value: str) -> dict[str, str]:
    raw = re.sub(r"\s+", " ", (raw_value or "").strip())
    normalized = normalize_key(raw)
    if not normalized:
        return {
            "geo_scope": "Outside Bangalore",
            "city_cluster": "Unknown",
            "locality_detail": "Unknown",
            "mapping_reason": "blank locality",
            "normalized_input": normalized,
        }

    if normalized in BANGALORE_EXACT_MAP:
        locality_detail = BANGALORE_EXACT_MAP[normalized]
        return {
            "geo_scope": "Bangalore",
            "city_cluster": "Bangalore",
            "locality_detail": locality_detail,
            "mapping_reason": f"exact Bangalore mapping: {locality_detail}",
            "normalized_input": normalized,
        }

    if any(token in normalized for token in ("bangalore", "bengaluru", "banglore")):
        locality_detail = BANGALORE_DETAIL_FALLBACK
        for token, canonical in BANGALORE_CONTAINS_RULES:
            if token in normalized:
                locality_detail = canonical
                break
        return {
            "geo_scope": "Bangalore",
            "city_cluster": "Bangalore",
            "locality_detail": locality_detail,
            "mapping_reason": f"contains Bangalore token: {locality_detail}",
            "normalized_input": normalized,
        }

    for token, canonical in BANGALORE_CONTAINS_RULES:
        if normalized == token:
            return {
                "geo_scope": "Bangalore",
                "city_cluster": "Bangalore",
                "locality_detail": canonical,
                "mapping_reason": f"exact Bangalore neighborhood: {canonical}",
                "normalized_input": normalized,
            }

    outside_label = normalize_outside_location(raw, normalized)
    return {
        "geo_scope": "Outside Bangalore",
        "city_cluster": outside_label,
        "locality_detail": outside_label,
        "mapping_reason": "outside Bangalore or no Bangalore marker",
        "normalized_input": normalized,
    }


def decode_index_response(code: str, options: list[str]) -> str:
    if pd.isna(code) or code == "":
        return ""
    try:
        return options[int(code)]
    except (IndexError, TypeError, ValueError):
        return ""


def count_rows(
    df: pd.DataFrame,
    column: str,
    *,
    total: int | None = None,
    order: list[str] | None = None,
    count_label: str = "count",
    pct_label: str = "percent",
) -> list[dict[str, object]]:
    total = len(df) if total is None else total
    counts = df[column].astype(str).replace("nan", "").value_counts()
    labels = order or counts.index.tolist()
    rows = []
    for label in labels:
        count = int(counts.get(label, 0))
        if count == 0:
            continue
        rows.append(
            {
                "label": str(label),
                count_label: count,
                pct_label: round(count / total * 100, 1) if total else 0.0,
            }
        )
    return rows


def summarize_metric(df: pd.DataFrame, raw_column: str, pct_column: str, label: str, max_score: int) -> dict[str, object]:
    raw_series = df[raw_column].dropna().astype(float)
    pct_series = df[pct_column].dropna().astype(float)
    return {
        "metric": pct_column,
        "label": label,
        "max_score": max_score,
        "mean_raw": round(raw_series.mean(), 2),
        "sd_raw": round(raw_series.std(ddof=1), 2),
        "median_raw": round(raw_series.median(), 2),
        "q1_raw": round(raw_series.quantile(0.25), 2),
        "q3_raw": round(raw_series.quantile(0.75), 2),
        "min_raw": round(raw_series.min(), 2),
        "max_raw": round(raw_series.max(), 2),
        "mean_pct": round(pct_series.mean(), 1),
        "median_pct": round(pct_series.median(), 1),
        "q1_pct": round(pct_series.quantile(0.25), 1),
        "q3_pct": round(pct_series.quantile(0.75), 1),
        "min_pct": round(pct_series.min(), 1),
        "max_pct": round(pct_series.max(), 1),
    }


def build_analysis_dataset(input_csv: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = pd.read_csv(input_csv)
    df = trim_strings(raw_df.rename(columns=RAW_TO_SNAKE))

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce")
    df["knowledge_score_raw"] = pd.to_numeric(df["knowledge_score_raw"], errors="coerce")
    df["knowledge_total_raw"] = pd.to_numeric(df["knowledge_total_raw"], errors="coerce")

    location_rows = df["locality"].apply(normalize_locality).apply(pd.Series)
    df = pd.concat([df, location_rows], axis=1)

    knowledge_score = np.zeros(len(df), dtype=int)
    for item in KNOWLEDGE_ITEMS:
        item_id = item["id"]
        df[f"{item_id}_label"] = df[item_id].apply(lambda value: decode_index_response(value, item["options"]))
        df[f"{item_id}_is_correct"] = df[item_id].astype(str).eq(item["correct_code"]).astype(int)
        knowledge_score += df[f"{item_id}_is_correct"].to_numpy()
    df["knowledge_score"] = knowledge_score
    df["knowledge_pct"] = df["knowledge_score"] / len(KNOWLEDGE_ITEMS) * 100.0

    attitude_score = np.zeros(len(df), dtype=int)
    for item in ATTITUDE_ITEMS:
        item_id = item["id"]
        values = df[item_id].map(ATTITUDE_VALUE_MAP)
        if values.isna().any():
            missing = sorted(df.loc[values.isna(), item_id].dropna().astype(str).unique())
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
        df[f"{item_id}_label"] = df[item_id].apply(lambda value: decode_index_response(value, item["options"]))
        mapped = df[item_id].astype(str).map(item["score_map"])
        if mapped.isna().any():
            missing = sorted(df.loc[mapped.isna(), item_id].dropna().astype(str).unique())
            raise ValueError(f"Unmapped practice responses in {item_id}: {missing}")
        df[f"{item_id}_score"] = mapped.astype(int)
        practice_score += df[f"{item_id}_score"].to_numpy()
    df["practice_index"] = practice_score
    df["practice_pct"] = df["practice_index"] / (len(PRACTICE_ITEMS) * 3) * 100.0

    df["knowledge_practice_gap"] = df["knowledge_pct"] - df["practice_pct"]
    df["attitude_practice_gap"] = df["attitude_pct"] - df["practice_pct"]

    df["age_range"] = pd.Categorical(df["age_range"], categories=AGE_ORDER, ordered=True)
    df["gender"] = pd.Categorical(df["gender"], categories=GENDER_ORDER, ordered=True)
    df["professional_experience"] = pd.Categorical(
        df["professional_experience"],
        categories=EXPERIENCE_ORDER,
        ordered=True,
    )
    df["work_mode"] = pd.Categorical(df["work_mode"], categories=WORK_MODE_ORDER, ordered=True)
    df["previous_treatment"] = pd.Categorical(
        df["previous_treatment"],
        categories=PREVIOUS_TREATMENT_ORDER,
        ordered=True,
    )
    df["geo_scope"] = pd.Categorical(df["geo_scope"], categories=BANGALORE_SCOPE_ORDER, ordered=True)

    mapping_review = (
        df[["locality", "normalized_input", "geo_scope", "city_cluster", "locality_detail", "mapping_reason"]]
        .drop_duplicates()
        .sort_values(["geo_scope", "city_cluster", "locality_detail", "locality"])
        .reset_index(drop=True)
    )
    return df, mapping_review


def build_knowledge_items(df: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for item in KNOWLEDGE_ITEMS:
        item_id = item["id"]
        correct_pct = float(df[f"{item_id}_is_correct"].mean() * 100.0)
        rows.append(
            {
                "id": item_id,
                "short": item["short"],
                "question": item["question"],
                "correct_pct": round(correct_pct, 1),
                "incorrect_pct": round(100.0 - correct_pct, 1),
            }
        )
    return sorted(rows, key=lambda row: row["correct_pct"])


def build_attitude_items(df: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for item in ATTITUDE_ITEMS:
        counts = (
            df[item["id"]]
            .value_counts(normalize=True)
            .reindex(ATTITUDE_RESPONSE_ORDER, fill_value=0.0)
            .mul(100.0)
        )
        positive_pct = float(counts["Agree"] + counts["Strongly Agree"])
        negative_pct = float(counts["Disagree"] + counts["Strongly Disagree"])
        rows.append(
            {
                "id": item["id"],
                "statement": item["statement"],
                "strongly_disagree": round(float(counts["Strongly Disagree"]), 1),
                "disagree": round(float(counts["Disagree"]), 1),
                "agree": round(float(counts["Agree"]), 1),
                "strongly_agree": round(float(counts["Strongly Agree"]), 1),
                "positive_pct": round(positive_pct, 1),
                "negative_pct": round(negative_pct, 1),
                "net_favorability": round(positive_pct - negative_pct, 1),
            }
        )
    return sorted(rows, key=lambda row: row["net_favorability"])


def build_practice_items(df: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for item in PRACTICE_ITEMS:
        score_col = f"{item['id']}_score"
        distribution = (
            df[score_col]
            .value_counts(normalize=True)
            .reindex([0, 1, 2, 3], fill_value=0.0)
            .mul(100.0)
        )
        rows.append(
            {
                "id": item["id"],
                "short": item["short"],
                "question": item["question"],
                "least_healthy": round(float(distribution[0]), 1),
                "needs_work": round(float(distribution[1]), 1),
                "reasonable": round(float(distribution[2]), 1),
                "best_practice": round(float(distribution[3]), 1),
                "low_quality_pct": round(float(distribution[0] + distribution[1]), 1),
            }
        )
    return sorted(rows, key=lambda row: row["best_practice"])


def build_group_metric_rows(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in GROUP_CONFIGS:
        column = group["column"]
        for level in group["order"]:
            subset = df.loc[df[column].astype(str) == str(level)]
            if subset.empty:
                continue
            rows.append(
                {
                    "group": group["label"],
                    "level": str(level),
                    "n": int(len(subset)),
                    "knowledge_pct": round(float(subset["knowledge_pct"].mean()), 1),
                    "attitude_pct": round(float(subset["attitude_pct"].mean()), 1),
                    "practice_pct": round(float(subset["practice_pct"].mean()), 1),
                    "knowledge_practice_gap": round(float(subset["knowledge_practice_gap"].mean()), 1),
                    "attitude_practice_gap": round(float(subset["attitude_practice_gap"].mean()), 1),
                }
            )
    return rows


def build_locality_display_counts(df: pd.DataFrame) -> list[dict[str, object]]:
    bangalore_df = df.loc[df["geo_scope"].astype(str) == "Bangalore"].copy()
    counts = bangalore_df["locality_detail"].value_counts()
    bangalore_df["locality_display"] = bangalore_df["locality_detail"].where(
        bangalore_df["locality_detail"].map(counts).ge(BANGALORE_DISPLAY_MIN_COUNT),
        other="Other Bangalore localities",
    )
    grouped = bangalore_df["locality_display"].value_counts()
    total = len(bangalore_df)
    rows = []
    for label, count in grouped.items():
        rows.append(
            {
                "label": label,
                "count": int(count),
                "percent_of_bangalore": round(count / total * 100.0, 1) if total else 0.0,
                "percent_of_total": round(count / len(df) * 100.0, 1) if len(df) else 0.0,
            }
        )
    return sorted(rows, key=lambda row: (-row["count"], row["label"]))


def build_locality_comparison_rows(df: pd.DataFrame) -> list[dict[str, object]]:
    bangalore_df = df.loc[df["geo_scope"].astype(str) == "Bangalore"].copy()
    counts = bangalore_df["locality_detail"].value_counts()
    bangalore_df["comparison_locality"] = bangalore_df["locality_detail"].where(
        bangalore_df["locality_detail"].map(counts).ge(BANGALORE_CLAIM_MIN_COUNT),
        other="Other Bangalore localities",
    )
    grouped = (
        bangalore_df.groupby("comparison_locality", observed=True)
        .agg(
            n=("comparison_locality", "size"),
            knowledge_pct=("knowledge_pct", "mean"),
            attitude_pct=("attitude_pct", "mean"),
            practice_pct=("practice_pct", "mean"),
            knowledge_practice_gap=("knowledge_practice_gap", "mean"),
            attitude_practice_gap=("attitude_practice_gap", "mean"),
        )
        .reset_index()
        .rename(columns={"comparison_locality": "label"})
        .sort_values("practice_pct", ascending=False)
    )
    rows = []
    for row in grouped.itertuples():
        rows.append(
            {
                "label": row.label,
                "n": int(row.n),
                "knowledge_pct": round(float(row.knowledge_pct), 1),
                "attitude_pct": round(float(row.attitude_pct), 1),
                "practice_pct": round(float(row.practice_pct), 1),
                "knowledge_practice_gap": round(float(row.knowledge_practice_gap), 1),
                "attitude_practice_gap": round(float(row.attitude_practice_gap), 1),
                "claimable": bool(row.label != "Other Bangalore localities" and row.n >= BANGALORE_CLAIM_MIN_COUNT),
            }
        )
    return rows


def build_correlation_rows(df: pd.DataFrame) -> list[dict[str, object]]:
    pairs = [
        ("knowledge_pct", "attitude_pct", "Knowledge vs Attitude"),
        ("knowledge_pct", "practice_pct", "Knowledge vs Practice"),
        ("attitude_pct", "practice_pct", "Attitude vs Practice"),
    ]
    rows = []
    for left, right, label in pairs:
        rho, p_value = sp_stats.spearmanr(df[left], df[right], nan_policy="omit")
        ci_low, ci_high = bootstrap_spearman_ci(df, left, right)
        rows.append(
            {
                "left": left,
                "right": right,
                "label": label,
                "rho": round(float(rho), 3),
                "p_value": round(float(p_value), 6),
                "ci_low": round(float(ci_low), 3),
                "ci_high": round(float(ci_high), 3),
                "n": int(df[[left, right]].dropna().shape[0]),
            }
        )
    return sorted(rows, key=lambda row: abs(row["rho"]), reverse=True)


def build_geo_scope_comparison(df: pd.DataFrame) -> list[dict[str, object]]:
    bangalore = df.loc[df["geo_scope"].astype(str) == "Bangalore"]
    outside = df.loc[df["geo_scope"].astype(str) == "Outside Bangalore"]
    rows = []
    for metric in METRIC_CONFIGS:
        left = bangalore[metric["column"]]
        right = outside[metric["column"]]
        stat, p_value = sp_stats.mannwhitneyu(left, right, alternative="two-sided", method="auto")
        effect = cliffs_delta(left, right)
        rows.append(
            {
                "metric": metric["column"],
                "label": metric["label"],
                "bangalore_mean": round(float(left.mean()), 1),
                "outside_mean": round(float(right.mean()), 1),
                "difference": round(float(left.mean() - right.mean()), 1),
                "p_value": round(float(p_value), 4),
                "effect_size": round(float(effect), 3),
                "statistic": round(float(stat), 1),
            }
        )
    return rows


def build_subgroup_tests(df: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for metric in METRIC_CONFIGS:
        for group in GROUP_CONFIGS:
            column = group["column"]
            subset = df[[column, metric["column"]]].dropna().copy()
            subset[column] = subset[column].astype(str)
            levels = [level for level in group["order"] if level in subset[column].unique()]
            if len(levels) < 2:
                continue
            samples = [subset.loc[subset[column] == level, metric["column"]].to_numpy(dtype=float) for level in levels]
            means = [float(np.mean(sample)) for sample in samples]
            counts = [int(len(sample)) for sample in samples]
            if len(levels) == 2:
                statistic, p_value = sp_stats.mannwhitneyu(samples[0], samples[1], alternative="two-sided", method="auto")
                effect = cliffs_delta(samples[0], samples[1])
                direction = levels[0] if means[0] >= means[1] else levels[1]
                effect_name = "Cliff's delta"
            else:
                statistic, p_value = sp_stats.kruskal(*samples, nan_policy="omit")
                effect = epsilon_squared(float(statistic), int(sum(counts)), len(levels))
                direction = max(zip(levels, means), key=lambda item: item[1])[0]
                effect_name = "epsilon-squared"
            rows.append(
                {
                    "metric": metric["label"],
                    "group": group["label"],
                    "test_type": "Mann-Whitney U" if len(levels) == 2 else "Kruskal-Wallis",
                    "levels": levels,
                    "counts": counts,
                    "means": [round(value, 1) for value in means],
                    "p_value": round(float(p_value), 4),
                    "effect_size": round(float(effect), 3),
                    "effect_size_name": effect_name,
                    "top_level": direction,
                }
            )
    return rows


def formula_term(column: str, df: pd.DataFrame) -> str | None:
    if column not in df.columns:
        return None
    if df[column].dropna().nunique() < 2:
        return None
    if str(df[column].dtype) == "category":
        reference = REFERENCE_MAP.get(column)
        return f"C({column}, Treatment(reference='{reference}'))"
    return column


def clean_term(term: str) -> str:
    if term == "Intercept":
        return "Intercept"
    match = re.match(r"C\(([^,]+), Treatment\(reference='([^']+)'\)\)\[T\.(.+)\]", term)
    if match:
        column, reference, level = match.groups()
        label = column.replace("_", " ").title()
        return f"{label}: {level} vs {reference}"
    return term.replace("_", " ").title()


def build_regression_summary(df: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    specs = {
        "knowledge_model": {
            "outcome": "knowledge_pct",
            "predictors": [
                "age_range",
                "gender",
                "professional_experience",
                "work_mode",
                "previous_treatment",
                "geo_scope",
            ],
        },
        "attitude_model": {
            "outcome": "attitude_pct",
            "predictors": [
                "age_range",
                "gender",
                "professional_experience",
                "work_mode",
                "previous_treatment",
                "geo_scope",
                "knowledge_pct",
            ],
        },
        "practice_model": {
            "outcome": "practice_pct",
            "predictors": [
                "age_range",
                "gender",
                "professional_experience",
                "work_mode",
                "previous_treatment",
                "geo_scope",
                "knowledge_pct",
                "attitude_pct",
            ],
        },
    }

    fits = []
    highlights = []
    for model_name, spec in specs.items():
        active_predictors = [term for term in (formula_term(column, df) for column in spec["predictors"]) if term]
        model_df = df[[spec["outcome"], *spec["predictors"]]].dropna().copy()
        formula = f"{spec['outcome']} ~ {' + '.join(active_predictors)}"
        fitted = smf.ols(formula=formula, data=model_df).fit(cov_type="HC3")
        confidence = fitted.conf_int()

        fits.append(
            {
                "model": model_name,
                "outcome": spec["outcome"],
                "n_obs": int(fitted.nobs),
                "r_squared": round(float(fitted.rsquared), 3),
                "adj_r_squared": round(float(fitted.rsquared_adj), 3),
                "aic": round(float(fitted.aic), 1),
                "bic": round(float(fitted.bic), 1),
            }
        )

        term_rows = []
        for term, coefficient in fitted.params.items():
            if term == "Intercept":
                continue
            term_rows.append(
                {
                    "model": model_name,
                    "outcome": spec["outcome"],
                    "term_label": clean_term(term),
                    "coef": round(float(coefficient), 3),
                    "p_value": round(float(fitted.pvalues[term]), 4),
                    "ci_low": round(float(confidence.loc[term, 0]), 3),
                    "ci_high": round(float(confidence.loc[term, 1]), 3),
                }
            )
        significant_rows = [row for row in term_rows if row["p_value"] <= 0.05]
        highlights.extend(sorted(significant_rows, key=lambda row: row["p_value"])[:5])
    return {"fits": fits, "highlights": highlights[:12]}


def top_named_bangalore_locality(locality_counts: list[dict[str, object]]) -> dict[str, object]:
    named_rows = [
        row
        for row in locality_counts
        if row["label"] not in {BANGALORE_DETAIL_FALLBACK, "Other Bangalore localities"}
    ]
    return named_rows[0] if named_rows else locality_counts[0]


def build_insights(
    *,
    df: pd.DataFrame,
    knowledge_items: list[dict[str, object]],
    practice_items: list[dict[str, object]],
    locality_counts: list[dict[str, object]],
    locality_comparison: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    geo_scope_comparison: list[dict[str, object]],
    correlations: list[dict[str, object]],
) -> list[dict[str, object]]:
    bangalore_count = int((df["geo_scope"].astype(str) == "Bangalore").sum())
    total_count = int(len(df))
    top_named = top_named_bangalore_locality(locality_counts)
    practice_bangalore = [
        row
        for row in locality_comparison
        if row["claimable"] and row["label"] != BANGALORE_DETAIL_FALLBACK
    ]
    locality_practice_leaders = sorted(practice_bangalore, key=lambda row: row["practice_pct"], reverse=True)[:3]
    locality_gap_leader = max(practice_bangalore, key=lambda row: row["knowledge_practice_gap"])
    weakest_practice_segments = sorted(
        [row for row in group_rows if row["n"] >= 10],
        key=lambda row: row["practice_pct"],
    )[:5]
    strongest_correlation = correlations[0]
    geo_attitude = next(row for row in geo_scope_comparison if row["metric"] == "attitude_pct")

    insights = [
        {
            "id": "bangalore-footprint",
            "scope": "Bangalore",
            "title": "Bangalore drives the dataset, but the city is not a single cluster.",
            "summary": "The report should treat Bangalore as the main lens while still showing that responses come from several visible Bengaluru pockets.",
            "evidence": [
                f"Bangalore contributes {bangalore_count} of {total_count} responses ({bangalore_count / total_count * 100:.1f}%).",
                f"{top_named['label']} is the largest named Bangalore locality with {top_named['count']} responses.",
                "Bellandur, Whitefield, and HSR Layout each contribute meaningful local pockets of responses.",
            ],
            "why_it_matters": "Presentation should not talk about Bangalore as if it were one homogeneous block; locality cuts are needed for a credible city-specific story.",
            "chart": {
                "id": "insight-bangalore-footprint",
                "kind": "horizontal-bar",
                "title": "Top Bangalore localities in the sample",
                "subtitle": "Displayed individually once a locality reaches at least three responses.",
                "caption": f"Bangalore accounts for {bangalore_count / total_count * 100:.1f}% of the full sample, with {top_named['label']} leading the named localities.",
                "data": locality_counts[:8],
                "x_label": "Respondents",
                "format": "count",
            },
        },
        {
            "id": "bangalore-practice-leaders",
            "scope": "Bangalore",
            "title": "Named Bangalore localities differ more in behavior than in awareness.",
            "summary": "Practice is strongest in a few named Bangalore pockets even when knowledge stays closer to the city average.",
            "evidence": [
                f"{locality_practice_leaders[0]['label']} posts the highest reported practice score among claimable Bangalore localities at {locality_practice_leaders[0]['practice_pct']:.1f}%.",
                f"{locality_practice_leaders[1]['label']} and {locality_practice_leaders[2]['label']} also clear 75% on practice.",
                f"The Bangalore-wide practice mean is {df.loc[df['geo_scope'].astype(str) == 'Bangalore', 'practice_pct'].mean():.1f}%.",
            ],
            "why_it_matters": "Locality messaging can highlight where good routines already exist and use those pockets as proof that stronger behavior is achievable inside the same city context.",
            "chart": {
                "id": "insight-bangalore-practice-leaders",
                "kind": "multi-dot",
                "title": "KAP by Bangalore locality",
                "subtitle": "Localities shown individually once they reach at least five responses.",
                "caption": f"{locality_practice_leaders[0]['label']} leads the claimable Bangalore localities on practice, not on knowledge alone.",
                "data": locality_comparison,
                "series": ["knowledge_pct", "attitude_pct", "practice_pct"],
                "format": "percent",
            },
        },
        {
            "id": "bangalore-gap-pocket",
            "scope": "Bangalore",
            "title": f"{locality_gap_leader['label']} stands out as a small pocket where knowledge is not turning into routine practice.",
            "summary": "The biggest knowledge-to-behavior mismatch inside Bangalore appears in a locality-sized pocket, not in the city average.",
            "evidence": [
                f"{locality_gap_leader['label']} records {locality_gap_leader['knowledge_pct']:.1f}% on knowledge and {locality_gap_leader['practice_pct']:.1f}% on practice.",
                f"That creates a {locality_gap_leader['knowledge_practice_gap']:.1f}-point knowledge-practice gap.",
                f"This comparison is based on {locality_gap_leader['n']} respondents, so it should be presented as a directional pocket rather than a citywide conclusion.",
            ],
            "why_it_matters": "This is the clearest example that awareness alone does not guarantee daily action, which points toward behavior-focused interventions rather than awareness messaging alone.",
            "chart": {
                "id": "insight-bangalore-gap-pocket",
                "kind": "dumbbell",
                "title": "Knowledge-to-practice gaps across Bangalore localities",
                "subtitle": "Positive values mean knowledge is running ahead of behavior.",
                "caption": f"{locality_gap_leader['label']} has the largest knowledge-practice gap among localities with at least five respondents.",
                "data": locality_comparison,
                "left_key": "practice_pct",
                "right_key": "knowledge_pct",
                "format": "percent",
            },
        },
        {
            "id": "knowledge-blind-spots",
            "scope": "Overall",
            "title": "The weakest knowledge area is not advanced care; it is the basic cause of gum disease.",
            "summary": "The biggest misconception sits at the foundation of periodontal understanding, which makes it especially important for public messaging.",
            "evidence": [
                f"Only {knowledge_items[0]['correct_pct']:.1f}% answered the early gum disease cause question correctly.",
                f"Plaque and tartar questions also stay near the halfway mark at {knowledge_items[1]['correct_pct']:.1f}% and {knowledge_items[2]['correct_pct']:.1f}%.",
                f"The overall knowledge average is {df['knowledge_pct'].mean():.1f}%.",
            ],
            "why_it_matters": "If the basics are still unclear, communication should start with plain explanations of plaque, tartar, and disease causation before moving to treatment messaging.",
            "chart": {
                "id": "insight-knowledge-blind-spots",
                "kind": "lollipop",
                "title": "Weakest knowledge items",
                "subtitle": "Percent answering each question correctly.",
                "caption": f"The disease-cause question is the lowest-scoring knowledge item at {knowledge_items[0]['correct_pct']:.1f}% correct.",
                "data": knowledge_items[:5],
                "value_key": "correct_pct",
                "label_key": "short",
            },
        },
        {
            "id": "practice-bottlenecks",
            "scope": "Overall",
            "title": "Daily routines weaken most on interdental cleaning and dentist follow-up.",
            "summary": "The weakest behaviors are not brushing basics alone; they are the routines people skip once a toothbrush is no longer enough.",
            "evidence": [
                f"Only {practice_items[0]['best_practice']:.1f}% land in the best-practice band for cleaning aids.",
                f"Dental visit recency reaches only {practice_items[2]['best_practice']:.1f}% best-practice adherence.",
                f"Half or more of respondents remain in the low-quality bands for brushing direction and dentist visits.",
            ],
            "why_it_matters": "This points to a concrete behavior agenda: move beyond brushing frequency and focus on interdental cleaning and regular dental follow-up.",
            "chart": {
                "id": "insight-practice-bottlenecks",
                "kind": "horizontal-bar",
                "title": "Practice items with the lowest best-practice share",
                "subtitle": "Lower bars indicate the hardest routines to sustain.",
                "caption": f"Cleaning aids is the weakest behavior area, with only {practice_items[0]['best_practice']:.1f}% in the best-practice band.",
                "data": practice_items[:5],
                "value_key": "best_practice",
                "label_key": "short",
                "format": "percent",
            },
        },
        {
            "id": "geo-context",
            "scope": "Outside Bangalore",
            "title": "Bangalore respondents are more attitude-positive, but knowledge and behavior look broadly similar to the outside-Bangalore sample.",
            "summary": "The geography story is more about attitude tone than about a dramatic difference in knowledge or practice.",
            "evidence": [
                f"Bangalore averages {geo_attitude['bangalore_mean']:.1f}% on attitude versus {geo_attitude['outside_mean']:.1f}% outside Bangalore.",
                f"The attitude gap is {geo_attitude['difference']:.1f} points with a small effect size of {geo_attitude['effect_size']:.3f}.",
                "Knowledge and practice differences are directionally smaller than the attitude split.",
            ],
            "why_it_matters": "Outside-Bangalore respondents still belong in the story because the differences are not large enough to dismiss them as a separate population.",
            "chart": {
                "id": "insight-geo-context",
                "kind": "dumbbell",
                "title": "Bangalore versus outside Bangalore",
                "subtitle": "Mean standardized scores by geo scope.",
                "caption": f"Attitude shows the clearest Bangalore-versus-outside contrast, while knowledge and practice stay closer together.",
                "data": geo_scope_comparison,
                "left_key": "outside_mean",
                "right_key": "bangalore_mean",
                "label_key": "label",
                "format": "percent",
            },
        },
        {
            "id": "kap-link",
            "scope": "Overall",
            "title": "Knowledge aligns most strongly with practice, more than with attitude alone.",
            "summary": "Among the three composite domains, the cleanest statistical relationship is between knowing more and reporting better routines.",
            "evidence": [
                f"{strongest_correlation['label']} has the strongest Spearman rho at {strongest_correlation['rho']:.3f}.",
                f"The 95% bootstrap interval runs from {strongest_correlation['ci_low']:.3f} to {strongest_correlation['ci_high']:.3f}.",
                f"Attitude also matters, but the practice link is weaker when attitude is paired with practice directly.",
            ],
            "why_it_matters": "This connects awareness-building with behavior change, while still acknowledging that knowledge alone is not sufficient in every locality or segment.",
            "chart": {
                "id": "insight-kap-link",
                "kind": "correlation-circles",
                "title": "Relationships among knowledge, attitude, and practice",
                "subtitle": "Darker circles represent stronger monotonic relationships.",
                "caption": f"Knowledge shows its strongest alignment with practice at rho={strongest_correlation['rho']:.3f}.",
                "data": correlations,
            },
        },
        {
            "id": "weakest-segments",
            "scope": "Overall",
            "title": "The weakest reported practice is concentrated in a few work and career segments, not across the whole sample.",
            "summary": "Behavior challenges are concentrated enough to support more targeted messaging instead of a single blanket intervention.",
            "evidence": [
                f"{weakest_practice_segments[0]['level']} has the lowest practice score among segments with at least 10 respondents at {weakest_practice_segments[0]['practice_pct']:.1f}%.",
                f"{weakest_practice_segments[1]['level']} follows close behind at {weakest_practice_segments[1]['practice_pct']:.1f}%.",
                f"{weakest_practice_segments[2]['level']} rounds out the bottom three practice segments.",
            ],
            "why_it_matters": "This makes the case for segment-aware outreach, especially when presenting recommendations to workplace or community stakeholders.",
            "chart": {
                "id": "insight-weakest-segments",
                "kind": "horizontal-bar",
                "title": "Lowest-practice respondent segments",
                "subtitle": "Segments shown only when they include at least 10 respondents.",
                "caption": f"{weakest_practice_segments[0]['level']} is the lowest-practice segment in the dataset.",
                "data": weakest_practice_segments,
                "value_key": "practice_pct",
                "label_key": "level",
                "format": "percent",
            },
        },
    ]
    return insights


def section(
    section_id: str,
    eyebrow: str,
    title: str,
    summary: str,
    figures: list[dict[str, object]],
    highlights: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": section_id,
        "eyebrow": eyebrow,
        "title": title,
        "summary": summary,
        "highlights": highlights or [],
        "figures": figures,
    }


REPORT_TITLE = (
    "Assessment of knowledge, Attitude and Practice regarding Periodontal health "
    "among IT Professionals in Bangalore City- a cross sectional questionnaire survey"
)


def build_report_data(df: pd.DataFrame, source_csv: str) -> dict[str, object]:
    bangalore_count = int((df["geo_scope"].astype(str) == "Bangalore").sum())
    outside_count = int((df["geo_scope"].astype(str) == "Outside Bangalore").sum())

    knowledge_items = build_knowledge_items(df)
    attitude_items = build_attitude_items(df)
    practice_items = build_practice_items(df)
    group_rows = build_group_metric_rows(df)
    locality_counts = build_locality_display_counts(df)
    locality_comparison = build_locality_comparison_rows(df)
    correlations = build_correlation_rows(df)
    geo_scope_comparison = build_geo_scope_comparison(df)
    subgroup_tests = build_subgroup_tests(df)
    regression_summary = build_regression_summary(df)

    overall_city_counts = (
        df["city_cluster"]
        .astype(str)
        .value_counts()
        .head(10)
        .rename_axis("label")
        .reset_index(name="count")
    )
    overall_city_rows = [
        {
            "label": str(row.label),
            "count": int(row.count),
            "percent": round(float(row.count) / len(df) * 100.0, 1),
        }
        for row in overall_city_counts.itertuples()
    ]
    outside_rows = count_rows(
        df.loc[df["geo_scope"].astype(str) == "Outside Bangalore"],
        "city_cluster",
        total=outside_count,
    )[:10]

    score_summaries = [
        summarize_metric(df, "knowledge_score", "knowledge_pct", "Knowledge", 10),
        summarize_metric(df, "attitude_score", "attitude_pct", "Attitude", 40),
        summarize_metric(df, "practice_index", "practice_pct", "Practice", 30),
    ]

    insights = build_insights(
        df=df,
        knowledge_items=knowledge_items,
        practice_items=practice_items,
        locality_counts=locality_counts,
        locality_comparison=locality_comparison,
        group_rows=group_rows,
        geo_scope_comparison=geo_scope_comparison,
        correlations=correlations,
    )

    executive_bullets = [insight["title"] for insight in insights[:5]]
    profile_highlights = [
        f"{bangalore_count} respondents are from Bangalore and {outside_count} are outside Bangalore.",
        f"The sample skews toward 20-30 years ({count_rows(df, 'age_range', order=AGE_ORDER)[0]['percent']:.1f}%) and full-time workers ({count_rows(df, 'work_mode', order=WORK_MODE_ORDER)[0]['percent']:.1f}%).",
        f"{count_rows(df, 'previous_treatment', order=PREVIOUS_TREATMENT_ORDER)[1]['percent']:.1f}% report a previous treatment history.",
    ]
    top_named = top_named_bangalore_locality(locality_counts)

    sections = [
        section(
            "sample-profile",
            "Executive Summary",
            "Sample profile and survey footing",
            "The report stays Bangalore-first because most respondents are from Bangalore, but it keeps the outside-Bangalore sample visible throughout the analysis.",
            [
                {
                    "id": "geo-scope-donut",
                    "kind": "donut",
                    "title": "Bangalore versus outside Bangalore",
                    "subtitle": "All 251 respondents grouped by primary geographic scope.",
                    "caption": f"Bangalore contributes {bangalore_count / len(df) * 100.0:.1f}% of the full sample.",
                    "data": count_rows(df, "geo_scope", order=BANGALORE_SCOPE_ORDER),
                    "center_label": "251\nrespondents",
                },
                {
                    "id": "gender-donut",
                    "kind": "donut",
                    "title": "Gender mix",
                    "subtitle": "Simple share-of-sample composition.",
                    "caption": f"Male respondents account for {count_rows(df, 'gender', order=GENDER_ORDER)[0]['percent']:.1f}% of the sample.",
                    "data": count_rows(df, "gender", order=GENDER_ORDER),
                    "center_label": "Gender",
                },
                {
                    "id": "age-bars",
                    "kind": "horizontal-bar",
                    "title": "Age range distribution",
                    "subtitle": "Younger respondents dominate the sample.",
                    "caption": f"The 20-30 years band makes up {count_rows(df, 'age_range', order=AGE_ORDER)[0]['percent']:.1f}% of respondents.",
                    "data": count_rows(df, "age_range", order=AGE_ORDER),
                    "x_label": "Respondents",
                    "format": "count",
                },
                {
                    "id": "work-mode-donut",
                    "kind": "donut",
                    "title": "Work mode",
                    "subtitle": "Work context for the respondents.",
                    "caption": f"Full-time work is the dominant mode at {count_rows(df, 'work_mode', order=WORK_MODE_ORDER)[0]['percent']:.1f}%.",
                    "data": count_rows(df, "work_mode", order=WORK_MODE_ORDER),
                    "center_label": "Work\nmode",
                },
            ],
            profile_highlights,
        ),
        section(
            "geography-overview",
            "Geography Overview",
            "Bangalore is the core geography, but outside-Bangalore responses matter too.",
            "Geography is shown in two layers: a whole-sample view that keeps outside-Bangalore responses visible, and a Bangalore-locality view that does not flatten the city into one bucket.",
            [
                {
                    "id": "overall-cities",
                    "kind": "horizontal-bar",
                    "title": "Top city or location clusters",
                    "subtitle": "Whole-sample geography after Bangalore normalization.",
                    "caption": f"Bangalore is the dominant location cluster, followed by Chennai at {overall_city_rows[1]['count']} respondents.",
                    "data": overall_city_rows,
                    "x_label": "Respondents",
                    "format": "count",
                },
                {
                    "id": "bangalore-localities",
                    "kind": "horizontal-bar",
                    "title": "Bangalore locality distribution",
                    "subtitle": "Localities displayed individually once they reach three responses.",
                    "caption": f"{top_named['label']} is the largest named Bangalore locality in the sample.",
                    "data": locality_counts[:10],
                    "x_label": "Respondents",
                    "format": "count",
                },
                {
                    "id": "outside-locations",
                    "kind": "horizontal-bar",
                    "title": "Top outside-Bangalore locations",
                    "subtitle": "Outside-Bangalore responses remain part of the story.",
                    "caption": f"Chennai leads the outside-Bangalore sample with {outside_rows[0]['count']} respondents.",
                    "data": outside_rows,
                    "x_label": "Respondents",
                    "format": "count",
                },
            ],
            [
                f"Bangalore contributes {bangalore_count} responses, but {outside_count} respondents are still outside Bangalore.",
                f"{top_named['label']} is the largest named Bangalore locality, while Chennai anchors the outside-Bangalore sample.",
            ],
        ),
        section(
            "bangalore-locality-deep-dive",
            "Bangalore Deep Dive",
            "Named Bangalore localities do not all behave the same way.",
            "The Bangalore locality section keeps the city-specific focus honest by showing where behavior is stronger, where knowledge leads action, and where small local pockets need caution.",
            [
                {
                    "id": "bangalore-locality-kap",
                    "kind": "multi-dot",
                    "title": "KAP by Bangalore locality",
                    "subtitle": "Localities shown individually once they reach at least five responses.",
                    "caption": f"Practice varies more than knowledge across the claimable Bangalore localities.",
                    "data": locality_comparison,
                    "series": ["knowledge_pct", "attitude_pct", "practice_pct"],
                    "format": "percent",
                },
                {
                    "id": "bangalore-gap-dumbbell",
                    "kind": "dumbbell",
                    "title": "Knowledge vs practice in Bangalore localities",
                    "subtitle": "Positive gaps indicate knowledge running ahead of behavior.",
                    "caption": f"The sharpest locality gap appears in {max(locality_comparison, key=lambda row: row['knowledge_practice_gap'])['label']}.",
                    "data": locality_comparison,
                    "left_key": "practice_pct",
                    "right_key": "knowledge_pct",
                    "format": "percent",
                },
            ],
            [
                "Use this section for Bangalore-specific commentary rather than citywide generalization.",
                "Locality comparisons are descriptive unless a locality reaches at least five respondents.",
            ],
        ),
        section(
            "knowledge",
            "Knowledge",
            "The knowledge story is about basic gum disease understanding, not specialist detail.",
            "The lowest-scoring knowledge items concern the primary cause of gum disease and the definitions of plaque and tartar.",
            [
                {
                    "id": "knowledge-lollipop",
                    "kind": "lollipop",
                    "title": "Knowledge items ranked by percent correct",
                    "subtitle": "Lower values indicate the strongest misconceptions.",
                    "caption": f"The cause-of-disease item is lowest at {knowledge_items[0]['correct_pct']:.1f}% correct.",
                    "data": knowledge_items,
                    "value_key": "correct_pct",
                    "label_key": "short",
                }
            ],
            [
                f"{knowledge_items[0]['short']} is the weakest knowledge item at {knowledge_items[0]['correct_pct']:.1f}% correct.",
                f"The next weakest items are {knowledge_items[1]['short']} and {knowledge_items[2]['short']}.",
            ],
        ),
        section(
            "attitude",
            "Attitude",
            "Attitudes are generally favorable, but a few items show friction.",
            "The diverging view makes it easy to see which statements generate strong agreement and which still face skepticism or convenience-based resistance.",
            [
                {
                    "id": "attitude-diverging",
                    "kind": "diverging-likert",
                    "title": "Attitude toward periodontal health",
                    "subtitle": "Agreement sits on the right; disagreement sits on the left.",
                    "caption": f"The weakest net favorability appears on the statement '{attitude_items[0]['statement']}'.",
                    "data": attitude_items,
                }
            ],
            [
                "The pain-only dentist-visit statement is the least favorable attitude item after reverse coding.",
                "Time and effort concerns remain visible even when oral-health attitudes are broadly positive.",
            ],
        ),
        section(
            "practice",
            "Practice",
            "Reported behavior is strongest on some daily basics and weakest on follow-through routines.",
            "The practice view separates broad adherence from the specific routines that still lag, especially cleaning aids and regular dentist visits.",
            [
                {
                    "id": "practice-heatmap",
                    "kind": "heatmap",
                    "title": "Practice response quality mix",
                    "subtitle": "Each row shows how the item splits across the four practice-quality bands.",
                    "caption": f"Cleaning aids is the weakest practice area, with only {practice_items[0]['best_practice']:.1f}% in the best-practice band.",
                    "data": practice_items,
                    "columns": list(PRACTICE_SCORE_LABELS.values()),
                },
                {
                    "id": "practice-weak-bars",
                    "kind": "horizontal-bar",
                    "title": "Lowest best-practice adherence",
                    "subtitle": "Bottom five practice items by best-practice share.",
                    "caption": f"Cleaning aids and dentist visits are the two main behavior bottlenecks.",
                    "data": practice_items[:5],
                    "value_key": "best_practice",
                    "label_key": "short",
                    "format": "percent",
                },
            ],
            [
                f"Only {practice_items[0]['best_practice']:.1f}% report best-practice use of cleaning aids.",
                f"Dentist visit recency reaches just {practice_items[2]['best_practice']:.1f}% in the top band.",
            ],
        ),
        section(
            "cross-domain-relationships",
            "Cross-Domain Relationships",
            "The cross-domain view shows how knowledge, attitude, and practice move together and where subgroup differences are large enough to notice.",
            "Knowledge, attitude, and practice should be read as connected but not interchangeable domains; the charts below show both their overall score ranges and their subgroup differences.",
            [
                {
                    "id": "kap-range-panel",
                    "kind": "range-panel",
                    "title": "Composite score distributions",
                    "subtitle": "All three domains are shown on a common 0-100 scale.",
                    "caption": f"Practice has the highest average standardized score at {score_summaries[2]['mean_pct']:.1f}%.",
                    "data": score_summaries,
                },
                {
                    "id": "subgroup-heatmap",
                    "kind": "subgroup-heatmap",
                    "title": "Subgroup score profile",
                    "subtitle": "Rows combine the main demographic and context segments.",
                    "caption": "Remote workers and 10-15 year professionals sit near the bottom of the practice distribution.",
                    "data": [row for row in group_rows if row["n"] >= 10],
                },
                {
                    "id": "geo-scope-dumbbell",
                    "kind": "dumbbell",
                    "title": "Bangalore versus outside Bangalore",
                    "subtitle": "Mean domain scores by geo scope.",
                    "caption": f"Attitude is the clearest Bangalore-versus-outside difference at {geo_scope_comparison[1]['difference']:.1f} points.",
                    "data": geo_scope_comparison,
                    "left_key": "outside_mean",
                    "right_key": "bangalore_mean",
                    "label_key": "label",
                    "format": "percent",
                },
                {
                    "id": "correlation-circles",
                    "kind": "correlation-circles",
                    "title": "KAP relationship map",
                    "subtitle": "Circle size and color reflect the strength of the association.",
                    "caption": f"{correlations[0]['label']} is the strongest pair with rho={correlations[0]['rho']:.3f}.",
                    "data": correlations,
                },
            ],
            [
                f"Knowledge and practice move together most closely at rho={correlations[0]['rho']:.3f}.",
                f"The clearest geo-scope difference is in attitude, where Bangalore is higher by {geo_scope_comparison[1]['difference']:.1f} points.",
            ],
        ),
    ]

    return {
        "meta": {
            "title": REPORT_TITLE,
            "subtitle": "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "respondent_count": int(len(df)),
            "bangalore_count": bangalore_count,
            "outside_bangalore_count": outside_count,
            "bangalore_share_pct": round(bangalore_count / len(df) * 100.0, 1),
        },
        "kpis": [
            {"label": "Total respondents", "value": str(len(df)), "detail": "Single source of truth dataset"},
            {"label": "Bangalore respondents", "value": str(bangalore_count), "detail": f"{bangalore_count / len(df) * 100.0:.1f}% of sample"},
            {"label": "Outside Bangalore", "value": str(outside_count), "detail": f"{outside_count / len(df) * 100.0:.1f}% of sample"},
            {"label": "Top named Bangalore locality", "value": top_named["label"], "detail": f"{top_named['count']} respondents"},
        ],
        "hero": {
            "summary": "This report keeps Bangalore at the center of the analysis without discarding the outside-Bangalore respondents who also contributed useful signal.",
            "executive_bullets": executive_bullets,
        },
        "sections": sections,
        "insights": insights,
        "tables": {
            "score_summaries": score_summaries,
            "subgroup_tests": subgroup_tests,
            "regression_fits": regression_summary["fits"],
            "regression_highlights": regression_summary["highlights"],
            "correlations": correlations,
            "geo_scope_comparison": geo_scope_comparison,
        },
        "appendix": {
            "method_notes": [
                "Knowledge, attitude, and practice scores are recomputed directly from the raw item responses in the source CSV.",
                "Bangalore-specific locality analysis preserves named Bengaluru localities whenever a locality reaches at least three responses; smaller pockets roll into Other Bangalore localities.",
                "Locality-level claims are only elevated when a Bangalore locality reaches at least five responses.",
                "Subgroup comparisons use non-parametric tests, and the regression appendix is included only as a supporting validation layer.",
            ],
            "mapping_review_head": "A reviewed locality-mapping table is written alongside the report data for inspection.",
        },
    }


def write_outputs(
    report_data: dict[str, object],
    mapping_review: pd.DataFrame,
    analysis_df: pd.DataFrame,
    *,
    json_path: Path,
    mapping_csv_path: Path,
    analysis_csv_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_csv_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_csv_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    mapping_review.to_csv(mapping_csv_path, index=False)
    analysis_df.to_csv(analysis_csv_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Bangalore-first report data.")
    parser.add_argument("--input", required=True, help="Path to the source CSV.")
    parser.add_argument("--out-json", required=True, help="Path to the report JSON output.")
    parser.add_argument("--out-mapping", required=True, help="Path to the locality mapping review CSV.")
    parser.add_argument("--out-analysis", required=True, help="Path to the cleaned analysis CSV.")
    args = parser.parse_args()

    analysis_df, mapping_review = build_analysis_dataset(args.input)
    report_data = build_report_data(analysis_df, source_csv=Path(args.input).name)
    write_outputs(
        report_data,
        mapping_review,
        analysis_df,
        json_path=Path(args.out_json),
        mapping_csv_path=Path(args.out_mapping),
        analysis_csv_path=Path(args.out_analysis),
    )


if __name__ == "__main__":
    main()
