"""Statistical summaries and inference for the periodontal survey."""

from __future__ import annotations

import itertools
import math
import re
from typing import Iterable

import numpy as np
import pandas as pd
import scipy.stats as sp_stats
import statsmodels.formula.api as smf

from analysis.config import (
    ATTITUDE_ITEMS,
    ATTITUDE_RESPONSE_ORDER,
    GROUP_VARS,
    KAP_SCORE_COLUMNS,
    KNOWLEDGE_ITEMS,
    PRACTICE_ITEMS,
    SAMPLE_SOURCE_ORDER,
)


def cronbach_alpha(items: pd.DataFrame) -> float:
    clean = items.dropna()
    if clean.empty or clean.shape[1] < 2:
        return float("nan")
    item_variances = clean.var(axis=0, ddof=1)
    total_scores = clean.sum(axis=1)
    total_variance = total_scores.var(ddof=1)
    if total_variance == 0:
        return float("nan")
    k = clean.shape[1]
    return float((k / (k - 1)) * (1 - item_variances.sum() / total_variance))


def _fmt_count_pct(count: int, total: int) -> str:
    if total == 0:
        return "0 (0.0%)"
    return f"{count} ({count / total * 100:.1f}%)"


def _fmt_continuous(series: pd.Series) -> str:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return "NA"
    return (
        f"{clean.mean():.2f} ± {clean.std(ddof=1):.2f}; "
        f"median {clean.median():.2f} [IQR {clean.quantile(0.25):.2f}, {clean.quantile(0.75):.2f}]"
    )


def build_table_one(df: pd.DataFrame) -> pd.DataFrame:
    overall_n = len(df)
    observed = df.loc[df["sample_source"].astype(str) == "observed"]
    generated = df.loc[df["sample_source"].astype(str) == "generated"]

    rows: list[dict[str, object]] = []
    categorical_fields = [
        ("Demographics", "age_range", "Age range"),
        ("Demographics", "gender", "Gender"),
        ("Demographics", "professional_experience", "Professional experience"),
        ("Demographics", "work_mode", "Work mode"),
        ("Clinical history", "previous_treatment", "Previous treatment"),
        ("Clinical history", "locality_group", "Locality group"),
    ]

    for section, column, label in categorical_fields:
        ordered_levels = (
            list(df[column].cat.categories)
            if hasattr(df[column].dtype, "categories")
            else sorted(df[column].dropna().astype(str).unique())
        )
        for level in ordered_levels:
            if pd.isna(level):
                continue
            rows.append(
                {
                    "section": section,
                    "variable": label,
                    "level": str(level),
                    "overall": _fmt_count_pct(int((df[column].astype(str) == str(level)).sum()), overall_n),
                    "observed": _fmt_count_pct(int((observed[column].astype(str) == str(level)).sum()), len(observed)),
                    "generated": _fmt_count_pct(int((generated[column].astype(str) == str(level)).sum()), len(generated)),
                }
            )

    continuous_fields = [
        ("Behavior and scores", "duration_minutes", "Survey duration (minutes, trimmed)", ~df["duration_artifact"]),
        ("Behavior and scores", "knowledge_score", "Knowledge score", pd.Series(True, index=df.index)),
        ("Behavior and scores", "attitude_score", "Attitude score", pd.Series(True, index=df.index)),
        ("Behavior and scores", "practice_index", "Practice index", pd.Series(True, index=df.index)),
    ]
    for section, column, label, mask in continuous_fields:
        rows.append(
            {
                "section": section,
                "variable": label,
                "level": "Summary",
                "overall": _fmt_continuous(df.loc[mask, column]),
                "observed": _fmt_continuous(observed.loc[mask.reindex(observed.index, fill_value=False), column]),
                "generated": _fmt_continuous(generated.loc[mask.reindex(generated.index, fill_value=False), column]),
            }
        )

    return pd.DataFrame(rows)


def summarize_treatments(df: pd.DataFrame) -> pd.DataFrame:
    summaries = []
    subsets = {
        "overall": df,
        "observed": df.loc[df["sample_source"].astype(str) == "observed"],
        "generated": df.loc[df["sample_source"].astype(str) == "generated"],
    }
    for dataset, subset in subsets.items():
        counts = subset["treatments_normalized"].replace("", "No treatment specified").value_counts(dropna=False)
        total = len(subset)
        for treatment, count in counts.items():
            summaries.append(
                {
                    "dataset": dataset,
                    "treatment_group": treatment,
                    "count": int(count),
                    "percent": round(count / total * 100, 2) if total else np.nan,
                }
            )
    return pd.DataFrame(summaries)


def summarize_item_responses(df: pd.DataFrame) -> pd.DataFrame:
    subsets = {
        "overall": df,
        "observed": df.loc[df["sample_source"].astype(str) == "observed"],
        "generated": df.loc[df["sample_source"].astype(str) == "generated"],
    }
    rows: list[dict[str, object]] = []

    for item in KNOWLEDGE_ITEMS:
        response_options = item["options"]
        for dataset_name, subset in subsets.items():
            counts = subset[f"{item['id']}_label"].value_counts(dropna=False)
            total = len(subset)
            for code, label in enumerate(response_options):
                rows.append(
                    {
                        "domain": "knowledge",
                        "item_id": item["id"],
                        "question": item["question"],
                        "dataset": dataset_name,
                        "response_code": str(code),
                        "response_label": label,
                        "health_score": int(code == int(item["correct_code"])),
                        "is_correct_option": code == int(item["correct_code"]),
                        "count": int(counts.get(label, 0)),
                        "percent": round(counts.get(label, 0) / total * 100, 2) if total else np.nan,
                    }
                )

    for item in ATTITUDE_ITEMS:
        for dataset_name, subset in subsets.items():
            counts = subset[item["id"]].value_counts(dropna=False)
            total = len(subset)
            for response in ATTITUDE_RESPONSE_ORDER:
                rows.append(
                    {
                        "domain": "attitude",
                        "item_id": item["id"],
                        "question": item["statement"],
                        "dataset": dataset_name,
                        "response_code": response,
                        "response_label": response,
                        "health_score": np.nan,
                        "is_correct_option": np.nan,
                        "count": int(counts.get(response, 0)),
                        "percent": round(counts.get(response, 0) / total * 100, 2) if total else np.nan,
                    }
                )

    for item in PRACTICE_ITEMS:
        response_options = item["options"]
        for dataset_name, subset in subsets.items():
            counts = subset[f"{item['id']}_label"].value_counts(dropna=False)
            total = len(subset)
            for code, label in enumerate(response_options):
                rows.append(
                    {
                        "domain": "practice",
                        "item_id": item["id"],
                        "question": item["question"],
                        "dataset": dataset_name,
                        "response_code": str(code),
                        "response_label": label,
                        "health_score": item["score_map"][str(code)],
                        "is_correct_option": np.nan,
                        "count": int(counts.get(label, 0)),
                        "percent": round(counts.get(label, 0) / total * 100, 2) if total else np.nan,
                    }
                )

    return pd.DataFrame(rows)


def summarize_composite_scores(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    subsets = {
        "overall": df,
        "observed": df.loc[df["sample_source"].astype(str) == "observed"],
        "generated": df.loc[df["sample_source"].astype(str) == "generated"],
    }
    for metric in KAP_SCORE_COLUMNS:
        for dataset_name, subset in subsets.items():
            series = subset[metric].dropna()
            rows.append(
                {
                    "metric": metric,
                    "dataset": dataset_name,
                    "n": int(series.shape[0]),
                    "mean": round(series.mean(), 3),
                    "sd": round(series.std(ddof=1), 3),
                    "median": round(series.median(), 3),
                    "q1": round(series.quantile(0.25), 3),
                    "q3": round(series.quantile(0.75), 3),
                    "minimum": round(series.min(), 3),
                    "maximum": round(series.max(), 3),
                }
            )
    return pd.DataFrame(rows)


def reliability_summary(df: pd.DataFrame) -> pd.DataFrame:
    datasets = {
        "augmented": df,
        "observed": df.loc[df["sample_source"].astype(str) == "observed"],
    }
    rows = []
    for name, subset in datasets.items():
        knowledge_cols = [f"{item['id']}_is_correct" for item in KNOWLEDGE_ITEMS]
        attitude_cols = [f"{item['id']}_score" for item in ATTITUDE_ITEMS]
        practice_cols = [f"{item['id']}_score" for item in PRACTICE_ITEMS]
        rows.extend(
            [
                {
                    "dataset": name,
                    "scale": "knowledge",
                    "alpha": round(cronbach_alpha(subset[knowledge_cols]), 4),
                    "note": "Binary correctness scale.",
                },
                {
                    "dataset": name,
                    "scale": "attitude",
                    "alpha": round(cronbach_alpha(subset[attitude_cols]), 4),
                    "note": "Likert scale with A5 and A8 reverse-coded.",
                },
                {
                    "dataset": name,
                    "scale": "practice_index",
                    "alpha": round(cronbach_alpha(subset[practice_cols]), 4),
                    "note": "Behavior index quality check only; not treated as a latent scale.",
                },
            ]
        )
    return pd.DataFrame(rows)


def cliffs_delta(x: Iterable[float], y: Iterable[float]) -> float:
    a = np.asarray(list(x), dtype=float)
    b = np.asarray(list(y), dtype=float)
    diffs = np.subtract.outer(a, b)
    return float((np.sum(diffs > 0) - np.sum(diffs < 0)) / diffs.size)


def holm_adjust(p_values: list[float]) -> list[float]:
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running_max = 0.0
    total = len(p_values)
    for rank, (idx, p_value) in enumerate(indexed, start=1):
        candidate = min((total - rank + 1) * p_value, 1.0)
        running_max = max(running_max, candidate)
        adjusted[idx] = running_max
    return adjusted


def epsilon_squared(h_stat: float, sample_size: int, group_count: int) -> float:
    if sample_size <= group_count:
        return float("nan")
    return max((h_stat - group_count + 1) / (sample_size - group_count), 0.0)


def subgroup_analysis(df: pd.DataFrame, dataset_label: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    omnibus_rows: list[dict[str, object]] = []
    pairwise_rows: list[dict[str, object]] = []

    for outcome in KAP_SCORE_COLUMNS:
        for group in GROUP_VARS:
            column = group["column"]
            subset = df[[column, outcome]].dropna().copy()
            subset[column] = subset[column].astype(str)
            levels = [level for level in group["order"] if level in subset[column].unique()]
            if len(levels) < 2:
                continue

            samples = [subset.loc[subset[column] == level, outcome].to_numpy(dtype=float) for level in levels]
            sizes = {level: int(len(sample)) for level, sample in zip(levels, samples)}
            medians = {level: float(np.median(sample)) for level, sample in zip(levels, samples)}
            means = {level: float(np.mean(sample)) for level, sample in zip(levels, samples)}

            if len(levels) == 2:
                left, right = samples
                stat, p_value = sp_stats.mannwhitneyu(left, right, alternative="two-sided", method="auto")
                effect = cliffs_delta(left, right)
                direction = f"{levels[0]} > {levels[1]}" if medians[levels[0]] >= medians[levels[1]] else f"{levels[1]} > {levels[0]}"
                omnibus_rows.append(
                    {
                        "dataset": dataset_label,
                        "outcome": outcome,
                        "group_var": column,
                        "test_type": "Mann-Whitney U",
                        "levels": " vs ".join(levels),
                        "n_total": int(sum(sizes.values())),
                        "group_sizes": "; ".join(f"{level}={sizes[level]}" for level in levels),
                        "group_means": "; ".join(f"{level}={means[level]:.2f}" for level in levels),
                        "group_medians": "; ".join(f"{level}={medians[level]:.2f}" for level in levels),
                        "statistic": float(stat),
                        "p_value": float(p_value),
                        "effect_size": float(effect),
                        "effect_size_name": "Cliff's delta",
                        "direction": direction,
                    }
                )
                continue

            stat, p_value = sp_stats.kruskal(*samples, nan_policy="omit")
            effect = epsilon_squared(float(stat), int(sum(sizes.values())), len(levels))
            omnibus_rows.append(
                {
                    "dataset": dataset_label,
                    "outcome": outcome,
                    "group_var": column,
                    "test_type": "Kruskal-Wallis",
                    "levels": ", ".join(levels),
                    "n_total": int(sum(sizes.values())),
                    "group_sizes": "; ".join(f"{level}={sizes[level]}" for level in levels),
                    "group_means": "; ".join(f"{level}={means[level]:.2f}" for level in levels),
                    "group_medians": "; ".join(f"{level}={medians[level]:.2f}" for level in levels),
                    "statistic": float(stat),
                    "p_value": float(p_value),
                    "effect_size": float(effect),
                    "effect_size_name": "epsilon-squared",
                    "direction": "Omnibus",
                }
            )

            if p_value >= 0.05:
                continue

            raw_p_values = []
            comparisons = []
            for left_level, right_level in itertools.combinations(levels, 2):
                left = subset.loc[subset[column] == left_level, outcome].to_numpy(dtype=float)
                right = subset.loc[subset[column] == right_level, outcome].to_numpy(dtype=float)
                stat_pair, p_pair = sp_stats.mannwhitneyu(left, right, alternative="two-sided", method="auto")
                raw_p_values.append(float(p_pair))
                comparisons.append(
                    {
                        "dataset": dataset_label,
                        "outcome": outcome,
                        "group_var": column,
                        "comparison": f"{left_level} vs {right_level}",
                        "left_level": left_level,
                        "right_level": right_level,
                        "left_n": int(len(left)),
                        "right_n": int(len(right)),
                        "left_mean": float(np.mean(left)),
                        "right_mean": float(np.mean(right)),
                        "left_median": float(np.median(left)),
                        "right_median": float(np.median(right)),
                        "statistic": float(stat_pair),
                        "raw_p_value": float(p_pair),
                        "effect_size": float(cliffs_delta(left, right)),
                        "effect_size_name": "Cliff's delta",
                    }
                )
            adjusted = holm_adjust(raw_p_values)
            for row, adjusted_p in zip(comparisons, adjusted):
                row["holm_p_value"] = float(adjusted_p)
                pairwise_rows.append(row)

    return pd.DataFrame(omnibus_rows), pd.DataFrame(pairwise_rows)


def cramer_v(chi2: float, n: int, table_shape: tuple[int, int]) -> float:
    if n == 0:
        return float("nan")
    denom = min(table_shape[0] - 1, table_shape[1] - 1)
    if denom <= 0:
        return float("nan")
    return math.sqrt(chi2 / (n * denom))


def categorical_associations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_columns = [group["column"] for group in GROUP_VARS]
    item_columns = (
        [item["id"] for item in KNOWLEDGE_ITEMS]
        + [item["id"] for item in ATTITUDE_ITEMS]
        + [item["id"] for item in PRACTICE_ITEMS]
    )

    for group_column in group_columns:
        for item_column in item_columns:
            subset = df[[group_column, item_column]].dropna().copy()
            subset[group_column] = subset[group_column].astype(str)
            subset[item_column] = subset[item_column].astype(str)
            subset = subset.loc[(subset[group_column] != "") & (subset[item_column] != "")]
            if subset.empty:
                continue

            contingency = pd.crosstab(subset[group_column], subset[item_column])
            if contingency.shape[0] < 2 or contingency.shape[1] < 2:
                continue

            chi2, chi_p, dof, expected = sp_stats.chi2_contingency(contingency, correction=False)
            test_name = "Chi-square"
            stat_value = float(chi2)
            p_value = float(chi_p)
            if contingency.shape == (2, 2) and (expected < 5).any():
                odds_ratio, fisher_p = sp_stats.fisher_exact(contingency.to_numpy())
                test_name = "Fisher exact"
                stat_value = float(odds_ratio)
                p_value = float(fisher_p)

            rows.append(
                {
                    "dataset": "augmented",
                    "group_var": group_column,
                    "item_id": item_column,
                    "test_type": test_name,
                    "n": int(contingency.to_numpy().sum()),
                    "rows": int(contingency.shape[0]),
                    "columns": int(contingency.shape[1]),
                    "statistic": stat_value,
                    "p_value": p_value,
                    "chi2_for_effect": float(chi2),
                    "degrees_freedom": int(dof),
                    "cramers_v": float(cramer_v(float(chi2), int(contingency.to_numpy().sum()), contingency.shape)),
                    "min_expected": float(expected.min()),
                }
            )

    results = pd.DataFrame(rows)
    if not results.empty:
        results["holm_p_value"] = holm_adjust(results["p_value"].tolist())
    return results


def bootstrap_spearman_ci(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    draws: int = 2000,
    seed: int = 20260308,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    clean = df[[x_col, y_col]].dropna().to_numpy(dtype=float)
    if len(clean) < 8:
        return float("nan"), float("nan")
    estimates = []
    for _ in range(draws):
        indices = rng.integers(0, len(clean), len(clean))
        sample = clean[indices]
        estimates.append(sp_stats.spearmanr(sample[:, 0], sample[:, 1]).statistic)
    return float(np.nanpercentile(estimates, 2.5)), float(np.nanpercentile(estimates, 97.5))


def kap_correlations(df: pd.DataFrame, dataset_label: str) -> pd.DataFrame:
    rows = []
    for left, right in itertools.combinations(KAP_SCORE_COLUMNS, 2):
        rho, p_value = sp_stats.spearmanr(df[left], df[right], nan_policy="omit")
        ci_low, ci_high = bootstrap_spearman_ci(df, left, right)
        rows.append(
            {
                "dataset": dataset_label,
                "pair": f"{left}__{right}",
                "left_metric": left,
                "right_metric": right,
                "rho": float(rho),
                "p_value": float(p_value),
                "ci_low": ci_low,
                "ci_high": ci_high,
                "n": int(df[[left, right]].dropna().shape[0]),
            }
        )
    return pd.DataFrame(rows)


REFERENCE_MAP = {group["column"]: group["order"][0] for group in GROUP_VARS}


def _formula_term(column: str, df: pd.DataFrame) -> str | None:
    if column not in df.columns:
        return None
    if df[column].dropna().nunique() < 2:
        return None
    if str(df[column].dtype) == "category":
        reference = REFERENCE_MAP.get(column)
        return f"C({column}, Treatment(reference='{reference}'))"
    return column


def _clean_term(term: str) -> str:
    if term == "Intercept":
        return "Intercept"
    match = re.match(r"C\(([^,]+), Treatment\(reference='([^']+)'\)\)\[T\.(.+)\]", term)
    if match:
        column, reference, level = match.groups()
        label = column.replace("_", " ").title()
        return f"{label}: {level} vs {reference}"
    return term.replace("_", " ").title()


def run_regressions(df: pd.DataFrame, dataset_label: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    specifications = {
        "knowledge_model": {
            "outcome": "knowledge_score",
            "predictors": ["age_range", "gender", "professional_experience", "work_mode", "previous_treatment", "sample_source"],
        },
        "attitude_model": {
            "outcome": "attitude_score",
            "predictors": [
                "age_range",
                "gender",
                "professional_experience",
                "work_mode",
                "previous_treatment",
                "knowledge_score",
                "sample_source",
            ],
        },
        "practice_model": {
            "outcome": "practice_index",
            "predictors": [
                "age_range",
                "gender",
                "professional_experience",
                "work_mode",
                "previous_treatment",
                "knowledge_score",
                "attitude_score",
                "sample_source",
            ],
        },
    }

    term_rows = []
    fit_rows = []

    for model_name, spec in specifications.items():
        active_predictors = [term for term in (_formula_term(column, df) for column in spec["predictors"]) if term]
        formula = f"{spec['outcome']} ~ {' + '.join(active_predictors)}"
        model_df = df[[spec["outcome"], *spec["predictors"]]].dropna().copy()
        fitted = smf.ols(formula=formula, data=model_df).fit(cov_type="HC3")
        confidence = fitted.conf_int()

        fit_rows.append(
            {
                "dataset": dataset_label,
                "model": model_name,
                "formula": formula,
                "n_obs": int(fitted.nobs),
                "r_squared": float(fitted.rsquared),
                "adj_r_squared": float(fitted.rsquared_adj),
                "aic": float(fitted.aic),
                "bic": float(fitted.bic),
            }
        )

        for term, coefficient in fitted.params.items():
            term_rows.append(
                {
                    "dataset": dataset_label,
                    "model": model_name,
                    "outcome": spec["outcome"],
                    "term": term,
                    "term_label": _clean_term(term),
                    "coef": float(coefficient),
                    "std_err": float(fitted.bse[term]),
                    "t_value": float(fitted.tvalues[term]),
                    "p_value": float(fitted.pvalues[term]),
                    "ci_low": float(confidence.loc[term, 0]),
                    "ci_high": float(confidence.loc[term, 1]),
                }
            )

    return pd.DataFrame(term_rows), pd.DataFrame(fit_rows)


def sensitivity_summary(
    augmented_regression: pd.DataFrame,
    observed_regression: pd.DataFrame,
    augmented_corr: pd.DataFrame,
    observed_corr: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    augmented_terms = augmented_regression.loc[augmented_regression["term"] != "Intercept"].copy()
    observed_terms = observed_regression.loc[observed_regression["term"] != "Intercept"].copy()
    merged_terms = augmented_terms.merge(
        observed_terms,
        on=["model", "term_label"],
        how="inner",
        suffixes=("_augmented", "_observed"),
    )
    for _, row in merged_terms.iterrows():
        sign_aug = np.sign(row["coef_augmented"])
        sign_obs = np.sign(row["coef_observed"])
        rows.append(
            {
                "comparison_type": "regression_term",
                "subject": f"{row['model']} | {row['term_label']}",
                "augmented_value": row["coef_augmented"],
                "observed_value": row["coef_observed"],
                "direction_changed": bool(sign_aug != sign_obs),
                "note": (
                    "Sign changed between augmented and observed-only models."
                    if sign_aug != sign_obs
                    else "Coefficient direction was stable."
                ),
            }
        )

    merged_corr = augmented_corr.merge(
        observed_corr,
        on=["pair"],
        how="inner",
        suffixes=("_augmented", "_observed"),
    )
    for _, row in merged_corr.iterrows():
        sign_aug = np.sign(row["rho_augmented"])
        sign_obs = np.sign(row["rho_observed"])
        rows.append(
            {
                "comparison_type": "correlation",
                "subject": row["pair"],
                "augmented_value": row["rho_augmented"],
                "observed_value": row["rho_observed"],
                "direction_changed": bool(sign_aug != sign_obs),
                "note": "Correlation sign changed." if sign_aug != sign_obs else "Correlation direction was stable.",
            }
        )

    return pd.DataFrame(rows)


def derive_insights(
    df: pd.DataFrame,
    item_summary: pd.DataFrame,
    subgroup_summary: pd.DataFrame,
    kap_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> list[str]:
    augmented_items = item_summary.loc[(item_summary["dataset"] == "overall") & (item_summary["domain"] == "knowledge")]
    knowledge_gaps = (
        augmented_items.loc[augmented_items["is_correct_option"]]
        .sort_values("percent")
        .head(3)[["item_id", "question", "percent"]]
    )
    gap_text = "; ".join(
        f"{row.item_id.upper()} ({row.percent:.1f}% correct, {row.question})"
        for row in knowledge_gaps.itertuples()
    )

    correlations = {
        row["pair"]: row
        for _, row in kap_summary.loc[kap_summary["dataset"] == "augmented"].iterrows()
    }
    kp = correlations.get("knowledge_score__practice_index")
    ka = correlations.get("knowledge_score__attitude_score")

    weakest_rows = []
    for outcome in KAP_SCORE_COLUMNS:
        grouped = []
        for group in GROUP_VARS:
            if group["column"] == "sample_source":
                continue
            summary = (
                df.groupby(group["column"], observed=True)[outcome]
                .agg(["mean", "count"])
                .reset_index()
                .query("count >= 10")
                .sort_values("mean")
            )
            if not summary.empty:
                weakest = summary.iloc[0]
                grouped.append(
                    f"{group['label']}: {weakest[group['column']]} (mean {weakest['mean']:.2f}, n={int(weakest['count'])})"
                )
        weakest_rows.append(f"Weakest {outcome.replace('_', ' ')} groups among categories with n>=10: " + "; ".join(grouped[:3]) + ".")

    prior_treatment = subgroup_summary.loc[
        (subgroup_summary["group_var"] == "previous_treatment") & (subgroup_summary["outcome"] == "practice_index")
    ]
    if not prior_treatment.empty:
        treatment_row = prior_treatment.iloc[0]
        treatment_text = (
            f"Prior treatment showed {treatment_row['direction'].lower()} for practice "
            f"(p={treatment_row['p_value']:.3f}, effect={treatment_row['effect_size']:.3f})."
        )
    else:
        treatment_text = "Prior treatment did not yield a two-group practice comparison."

    changed = sensitivity.loc[sensitivity["direction_changed"]]
    if changed.empty:
        sensitivity_text = "Observed-only sensitivity checks preserved the direction of the main correlations and shared regression terms."
    else:
        examples = "; ".join(changed["subject"].head(3).tolist())
        sensitivity_text = f"Sensitivity analysis found direction changes in {len(changed)} comparisons, including {examples}."

    return [
        f"Biggest knowledge gaps in the augmented sample were {gap_text}.",
        f"Knowledge aligned positively with attitude (rho={ka['rho']:.3f}, 95% CI {ka['ci_low']:.3f} to {ka['ci_high']:.3f}) and practice (rho={kp['rho']:.3f}, 95% CI {kp['ci_low']:.3f} to {kp['ci_high']:.3f}).",
        *weakest_rows,
        treatment_text,
        sensitivity_text,
        "All augmented-sample inferential findings should be presented as exploratory because 150 appended rows are synthetic augmentations beyond the 101 observed survey responses.",
    ]
