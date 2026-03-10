"""Run the periodontal survey analysis end to end."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from analysis.data import build_metadata, clean_dataset, load_raw_datasets, save_metadata
from analysis.plots import generate_all_figures
from analysis.report import generate_notebook, write_insights
from analysis.stats import (
    build_table_one,
    categorical_associations,
    derive_insights,
    kap_correlations,
    reliability_summary,
    run_regressions,
    sensitivity_summary,
    subgroup_analysis,
    summarize_composite_scores,
    summarize_item_responses,
    summarize_treatments,
)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def run_pipeline(augmented_csv: str | Path, observed_csv: str | Path, out_dir: str | Path) -> dict[str, Path]:
    augmented_csv = Path(augmented_csv)
    observed_csv = Path(observed_csv)
    out_dir = Path(out_dir)
    tables_dir = out_dir / "tables"
    figures_dir = out_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    augmented_raw, observed_raw = load_raw_datasets(augmented_csv, observed_csv)
    analysis_df = clean_dataset(augmented_raw, observed_raw)
    observed_df = analysis_df.loc[analysis_df["sample_source"].astype(str) == "observed"].copy()

    cleaned_path = out_dir / "cleaned_analysis_dataset.csv"
    _write_csv(analysis_df, cleaned_path)

    metadata = build_metadata(analysis_df)
    save_metadata(metadata, tables_dir / "analysis_metadata.json")

    table_one = build_table_one(analysis_df)
    treatment_summary = summarize_treatments(analysis_df)
    item_summary = summarize_item_responses(analysis_df)
    composite_summary = summarize_composite_scores(analysis_df)
    reliability = reliability_summary(analysis_df)

    subgroup_augmented, subgroup_pairwise_augmented = subgroup_analysis(analysis_df, "augmented")
    subgroup_observed, subgroup_pairwise_observed = subgroup_analysis(observed_df, "observed")

    categorical = categorical_associations(analysis_df)
    correlations_augmented = kap_correlations(analysis_df, "augmented")
    correlations_observed = kap_correlations(observed_df, "observed")
    correlations = pd.concat([correlations_augmented, correlations_observed], ignore_index=True)

    regression_augmented, regression_fit_augmented = run_regressions(analysis_df, "augmented")
    regression_observed, regression_fit_observed = run_regressions(observed_df, "observed")
    regression_results = pd.concat([regression_augmented, regression_observed], ignore_index=True)
    regression_fit = pd.concat([regression_fit_augmented, regression_fit_observed], ignore_index=True)

    sensitivity = sensitivity_summary(
        regression_augmented,
        regression_observed,
        correlations_augmented,
        correlations_observed,
    )

    insights = derive_insights(
        analysis_df,
        item_summary,
        subgroup_augmented,
        correlations,
        sensitivity,
    )
    write_insights(insights, tables_dir / "insights.md")

    _write_csv(table_one, tables_dir / "table_1_sample_characteristics.csv")
    _write_csv(treatment_summary, tables_dir / "treatment_history_summary.csv")
    _write_csv(item_summary, tables_dir / "item_response_summary.csv")
    _write_csv(composite_summary, tables_dir / "composite_score_summary.csv")
    _write_csv(reliability, tables_dir / "reliability_summary.csv")
    _write_csv(subgroup_augmented, tables_dir / "subgroup_results_augmented.csv")
    _write_csv(subgroup_pairwise_augmented, tables_dir / "subgroup_pairwise_results_augmented.csv")
    _write_csv(subgroup_observed, tables_dir / "subgroup_results_observed.csv")
    _write_csv(subgroup_pairwise_observed, tables_dir / "subgroup_pairwise_results_observed.csv")
    _write_csv(categorical, tables_dir / "categorical_item_associations.csv")
    _write_csv(correlations, tables_dir / "kap_correlations.csv")
    _write_csv(regression_results, tables_dir / "regression_results.csv")
    _write_csv(regression_fit, tables_dir / "regression_model_fits.csv")
    _write_csv(sensitivity, tables_dir / "sensitivity_summary.csv")

    generate_all_figures(
        analysis_df,
        regression_results,
        subgroup_augmented,
        subgroup_pairwise_augmented,
        figures_dir,
    )

    notebook_path = Path(__file__).resolve().parent / "periodontal_analysis_report.ipynb"
    generate_notebook(notebook_path, augmented_csv.name, observed_csv.name, out_dir)

    return {
        "cleaned_dataset": cleaned_path,
        "tables_dir": tables_dir,
        "figures_dir": figures_dir,
        "notebook_path": notebook_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the periodontal survey analysis pipeline.")
    parser.add_argument("--augmented", required=True, help="Path to the augmented CSV.")
    parser.add_argument("--observed", required=True, help="Path to the observed-only CSV.")
    parser.add_argument("--out", required=True, help="Output directory for tables and figures.")
    args = parser.parse_args()

    outputs = run_pipeline(args.augmented, args.observed, args.out)
    for key, value in outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
