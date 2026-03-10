"""Plotting helpers for the periodontal survey analysis."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent.parent / ".matplotlib"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis.config import (
    ATTITUDE_ITEMS,
    ATTITUDE_RESPONSE_ORDER,
    GROUP_VARS,
    KNOWLEDGE_ITEMS,
    PRACTICE_ITEMS,
    PRACTICE_SCORE_LABELS,
    SAMPLE_SOURCE_ORDER,
    THEME,
)


FIGURE_SIZE = (14, 8)
SAMPLE_PALETTE = {"observed": THEME["navy"], "generated": THEME["coral"]}


def apply_plot_theme() -> None:
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update(
        {
            "figure.facecolor": THEME["ivory"],
            "axes.facecolor": THEME["ivory"],
            "savefig.facecolor": THEME["ivory"],
            "axes.edgecolor": THEME["slate"],
            "axes.labelcolor": THEME["ink"],
            "axes.titleweight": "bold",
            "axes.titlesize": 16,
            "axes.labelsize": 12,
            "xtick.color": THEME["ink"],
            "ytick.color": THEME["ink"],
            "grid.color": "#CFD8DC",
            "font.family": "DejaVu Sans",
            "legend.frameon": False,
        }
    )


def _save(fig: plt.Figure, output_dir: Path, name: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{name}.png"
    svg_path = output_dir / f"{name}.svg"
    fig.savefig(png_path, dpi=320, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)


def _wrap(text: str, width: int = 38) -> str:
    return "\n".join(textwrap.wrap(text, width=width))


def demographic_profile_panel(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    columns = [
        ("age_range", "Age Range"),
        ("gender", "Gender"),
        ("professional_experience", "Professional Experience"),
        ("work_mode", "Work Mode"),
        ("previous_treatment", "Previous Treatment"),
        ("locality_group", "Locality Group"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.ravel()
    for ax, (column, title) in zip(axes, columns):
        order = (
            [category for category in df[column].cat.categories if str(category) in df[column].astype(str).unique()]
            if hasattr(df[column].dtype, "categories")
            else df[column].value_counts().index.tolist()
        )
        sns.countplot(
            data=df,
            x=column,
            hue="sample_source",
            order=order,
            palette=SAMPLE_PALETTE,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("Participants")
        ax.tick_params(axis="x", rotation=30)
        if ax.legend_:
            ax.legend_.set_title("")
    fig.suptitle("Demographic and Sample Composition Profile", color=THEME["ink"], fontsize=20, y=1.02)
    _save(fig, output_dir, "demographic_profile_panel")


def duration_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    trimmed = df.loc[~df["duration_artifact"]].copy()
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [2.2, 1]})

    sns.histplot(
        data=trimmed,
        x="duration_minutes",
        hue="sample_source",
        kde=True,
        bins=18,
        palette=SAMPLE_PALETTE,
        alpha=0.45,
        ax=axes[0],
    )
    axes[0].set_title("Survey Completion Time (Trimmed to <=60 minutes)")
    axes[0].set_xlabel("Minutes")
    axes[0].set_ylabel("Count")

    sns.boxplot(
        data=trimmed,
        x="sample_source",
        y="duration_minutes",
        hue="sample_source",
        palette=SAMPLE_PALETTE,
        dodge=False,
        width=0.45,
        ax=axes[1],
    )
    if axes[1].legend_:
        axes[1].legend_.remove()
    axes[1].set_title("Duration by Sample Source")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Minutes")

    fig.suptitle("Completion Time Quality Check", color=THEME["ink"], fontsize=20)
    _save(fig, output_dir, "trimmed_duration_distribution")


def knowledge_lollipop(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    rows = []
    for item in KNOWLEDGE_ITEMS:
        row = {
            "item_id": item["id"].upper(),
            "short": item["short"],
            "question": item["question"],
        }
        for source in SAMPLE_SOURCE_ORDER:
            subset = df.loc[df["sample_source"].astype(str) == source]
            row[source] = subset[f"{item['id']}_is_correct"].mean() * 100
        row["overall"] = df[f"{item['id']}_is_correct"].mean() * 100
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values("overall")

    fig, ax = plt.subplots(figsize=(12, 8))
    y_positions = np.arange(len(summary))
    ax.hlines(y_positions, xmin=0, xmax=summary["overall"], color=THEME["mist"], linewidth=4)
    ax.scatter(summary["overall"], y_positions, s=150, color=THEME["teal"], label="Overall", zorder=3)
    ax.scatter(summary["observed"], y_positions, s=80, color=THEME["navy"], label="Observed")
    ax.scatter(summary["generated"], y_positions, s=80, color=THEME["coral"], label="Generated")
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{row.item_id}: {row.short}" for row in summary.itertuples()])
    ax.set_xlabel("Percent correct")
    ax.set_xlim(0, 100)
    ax.set_title("Knowledge Item Performance")
    for idx, pct in enumerate(summary["overall"]):
        ax.text(pct + 1.5, idx, f"{pct:.1f}%", va="center", fontsize=10, color=THEME["ink"])
    ax.legend(loc="lower right")
    _save(fig, output_dir, "knowledge_item_lollipop")


def attitude_diverging_likert(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    rows = []
    for item in ATTITUDE_ITEMS:
        counts = (
            df[item["id"]]
            .value_counts(normalize=True)
            .reindex(ATTITUDE_RESPONSE_ORDER, fill_value=0)
            .mul(100)
        )
        rows.append(
            {
                "item": _wrap(item["statement"], 42),
                "Strongly Disagree": -counts["Strongly Disagree"],
                "Disagree": -counts["Disagree"],
                "Agree": counts["Agree"],
                "Strongly Agree": counts["Strongly Agree"],
            }
        )
    plot_df = pd.DataFrame(rows).set_index("item")
    plot_df = plot_df.iloc[::-1]

    fig, ax = plt.subplots(figsize=(16, 9))
    left = np.zeros(len(plot_df))
    for label, color in [
        ("Strongly Disagree", THEME["coral"]),
        ("Disagree", THEME["gold"]),
        ("Agree", THEME["teal"]),
        ("Strongly Agree", THEME["navy"]),
    ]:
        values = plot_df[label].values
        ax.barh(plot_df.index, values, left=left, color=color, label=label)
        left = left + values

    ax.axvline(0, color=THEME["slate"], linewidth=1.5)
    ax.set_xlabel("Percent of responses")
    ax.set_title("Attitude Toward Periodontal Health")
    ax.set_xlim(-100, 100)
    tick_values = np.arange(-100, 101, 25)
    ax.set_xticks(tick_values)
    ax.set_xticklabels([f"{abs(value)}%" for value in tick_values])
    ax.legend(ncol=4, bbox_to_anchor=(0.5, 1.02), loc="lower center")
    _save(fig, output_dir, "attitude_diverging_likert")


def practice_heatmap(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    heatmap_rows = []
    adherence_rows = []
    for item in PRACTICE_ITEMS:
        score_col = f"{item['id']}_score"
        distribution = (
            df[score_col]
            .value_counts(normalize=True)
            .reindex([0, 1, 2, 3], fill_value=0)
            .mul(100)
        )
        heatmap_rows.append(
            {
                "item": item["short"],
                **{PRACTICE_SCORE_LABELS[idx]: distribution[idx] for idx in [0, 1, 2, 3]},
            }
        )
        for source in SAMPLE_SOURCE_ORDER:
            subset = df.loc[df["sample_source"].astype(str) == source]
            adherence_rows.append(
                {
                    "item": item["short"],
                    "sample_source": source,
                    "mean_score": subset[score_col].mean(),
                }
            )

    heatmap_df = pd.DataFrame(heatmap_rows).set_index("item")
    adherence_df = pd.DataFrame(adherence_rows)

    fig, axes = plt.subplots(1, 2, figsize=(17, 8), gridspec_kw={"width_ratios": [1.25, 1]})
    sns.heatmap(
        heatmap_df,
        cmap=sns.color_palette([THEME["ivory"], THEME["gold"], THEME["teal"], THEME["navy"]], as_cmap=True),
        annot=True,
        fmt=".1f",
        linewidths=0.8,
        cbar_kws={"label": "% of respondents"},
        ax=axes[0],
    )
    axes[0].set_title("Practice Response Heatmap by Health Score")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("")

    sns.barplot(
        data=adherence_df,
        y="item",
        x="mean_score",
        hue="sample_source",
        palette=SAMPLE_PALETTE,
        ax=axes[1],
    )
    axes[1].set_title("Mean Item Score by Sample Source")
    axes[1].set_xlabel("Mean score (0-3)")
    axes[1].set_ylabel("")
    axes[1].legend(title="")

    fig.suptitle("Periodontal Practice Patterns", color=THEME["ink"], fontsize=20)
    _save(fig, output_dir, "practice_response_heatmap")


def composite_score_distributions(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    score_map = {
        "knowledge_score": "Knowledge score",
        "attitude_score": "Attitude score",
        "practice_index": "Practice index",
    }
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, (column, title) in zip(axes, score_map.items()):
        sns.violinplot(
            data=df,
            x="sample_source",
            y=column,
            hue="sample_source",
            palette=SAMPLE_PALETTE,
            inner=None,
            cut=0,
            dodge=False,
            ax=ax,
        )
        if ax.legend_:
            ax.legend_.remove()
        sns.boxplot(
            data=df,
            x="sample_source",
            y=column,
            width=0.24,
            showcaps=False,
            boxprops={"facecolor": "white", "zorder": 3},
            whiskerprops={"linewidth": 0},
            fliersize=0,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
    fig.suptitle("Composite Score Distributions", color=THEME["ink"], fontsize=20)
    _save(fig, output_dir, "composite_score_distributions")


def kap_correlation_matrix(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    corr = df[["knowledge_score", "attitude_score", "practice_index"]].corr(method="spearman")
    labels = ["Knowledge", "Attitude", "Practice"]
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap=sns.diverging_palette(18, 220, as_cmap=True),
        center=0,
        linewidths=0.75,
        square=True,
        xticklabels=labels,
        yticklabels=labels,
        cbar_kws={"label": "Spearman rho"},
        ax=ax,
    )
    ax.set_title("KAP Correlation Structure")
    _save(fig, output_dir, "kap_correlation_matrix")


def observed_vs_generated_panel(df: pd.DataFrame, output_dir: Path) -> None:
    apply_plot_theme()
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    score_df = (
        df.groupby("sample_source", observed=True)[["knowledge_score", "attitude_score", "practice_index"]]
        .mean()
        .reset_index()
        .melt(id_vars="sample_source", var_name="metric", value_name="mean_score")
    )
    sns.barplot(
        data=score_df,
        x="metric",
        y="mean_score",
        hue="sample_source",
        palette=SAMPLE_PALETTE,
        ax=axes[0, 0],
    )
    axes[0, 0].set_title("Mean Score Comparison")
    axes[0, 0].set_xlabel("")
    axes[0, 0].set_ylabel("Mean score")
    axes[0, 0].tick_params(axis="x", rotation=20)

    age_df = (
        df.groupby(["sample_source", "age_range"], observed=True)
        .size()
        .reset_index(name="count")
        .pivot(index="sample_source", columns="age_range", values="count")
        .fillna(0)
    )
    age_df = age_df.div(age_df.sum(axis=1), axis=0) * 100
    age_df.plot(kind="barh", stacked=True, ax=axes[0, 1], color=[THEME["navy"], THEME["teal"], THEME["gold"], THEME["coral"]])
    axes[0, 1].set_title("Age Distribution by Source")
    axes[0, 1].set_xlabel("Percent")
    axes[0, 1].set_ylabel("")
    axes[0, 1].legend(title="Age range", bbox_to_anchor=(1.02, 1), loc="upper left")

    treatment_df = (
        df.groupby(["sample_source", "previous_treatment"], observed=True)
        .size()
        .reset_index(name="count")
    )
    sns.barplot(
        data=treatment_df,
        x="previous_treatment",
        y="count",
        hue="sample_source",
        palette=SAMPLE_PALETTE,
        ax=axes[1, 0],
    )
    axes[1, 0].set_title("Previous Gum Treatment")
    axes[1, 0].set_xlabel("")
    axes[1, 0].set_ylabel("Count")

    locality_df = (
        df.groupby(["sample_source", "locality_group"], observed=True)
        .size()
        .reset_index(name="count")
    )
    locality_df = locality_df.loc[locality_df["locality_group"] != "Other"]
    sns.barplot(
        data=locality_df,
        x="locality_group",
        y="count",
        hue="sample_source",
        palette=SAMPLE_PALETTE,
        ax=axes[1, 1],
    )
    axes[1, 1].set_title("Major Locality Representation")
    axes[1, 1].set_xlabel("")
    axes[1, 1].set_ylabel("Count")
    axes[1, 1].tick_params(axis="x", rotation=25)

    fig.suptitle("Observed vs Generated Sample Comparison", color=THEME["ink"], fontsize=20)
    _save(fig, output_dir, "observed_vs_generated_comparison")


def regression_effect_forest(
    regression_results: pd.DataFrame,
    subgroup_results: pd.DataFrame,
    pairwise_results: pd.DataFrame,
    output_dir: Path,
) -> None:
    apply_plot_theme()
    reg = regression_results.loc[
        (regression_results["dataset"] == "augmented")
        & (regression_results["term"] != "Intercept")
        & (regression_results["p_value"] <= 0.1)
    ].copy()
    reg["abs_coef"] = reg["coef"].abs()
    reg = reg.sort_values(["model", "abs_coef"], ascending=[True, False]).groupby("model").head(5)
    reg["label"] = reg["model"].str.replace("_", " ").str.title() + " | " + reg["term_label"]

    effects = subgroup_results.loc[
        (subgroup_results["dataset"] == "augmented") & subgroup_results["effect_size"].notna()
    ].copy()
    effects["label"] = effects["outcome"].str.replace("_", " ").str.title() + " | " + effects["group_var"].str.replace("_", " ").str.title()
    effects = effects.sort_values("effect_size", ascending=False).head(8)

    fig, axes = plt.subplots(1, 2, figsize=(18, 10), gridspec_kw={"width_ratios": [1.2, 0.8]})

    if not reg.empty:
        y = np.arange(len(reg))
        axes[0].hlines(y, reg["ci_low"], reg["ci_high"], color=THEME["mist"], linewidth=3)
        axes[0].scatter(reg["coef"], y, color=THEME["navy"], s=90)
        axes[0].axvline(0, color=THEME["slate"], linewidth=1.5)
        axes[0].set_yticks(y)
        axes[0].set_yticklabels([_wrap(label, 38) for label in reg["label"]])
        axes[0].set_title("Exploratory Regression Coefficients (HC3)")
        axes[0].set_xlabel("Coefficient with 95% CI")
    else:
        axes[0].text(0.5, 0.5, "No coefficients met the display threshold.", ha="center", va="center")
        axes[0].set_axis_off()

    if not effects.empty:
        y = np.arange(len(effects))
        axes[1].barh(y, effects["effect_size"], color=THEME["teal"])
        axes[1].set_yticks(y)
        axes[1].set_yticklabels([_wrap(label, 28) for label in effects["label"]])
        axes[1].invert_yaxis()
        axes[1].set_title("Largest Nonparametric Effect Sizes")
        axes[1].set_xlabel("Effect size")
    else:
        axes[1].text(0.5, 0.5, "No subgroup effect sizes available.", ha="center", va="center")
        axes[1].set_axis_off()

    fig.suptitle("Regression and Effect Size Forest Plot", color=THEME["ink"], fontsize=20)
    _save(fig, output_dir, "regression_effect_forest")


def generate_all_figures(
    df: pd.DataFrame,
    regression_results: pd.DataFrame,
    subgroup_results: pd.DataFrame,
    pairwise_results: pd.DataFrame,
    output_dir: Path,
) -> None:
    demographic_profile_panel(df, output_dir)
    duration_distribution(df, output_dir)
    knowledge_lollipop(df, output_dir)
    attitude_diverging_likert(df, output_dir)
    practice_heatmap(df, output_dir)
    composite_score_distributions(df, output_dir)
    kap_correlation_matrix(df, output_dir)
    observed_vs_generated_panel(df, output_dir)
    regression_effect_forest(regression_results, subgroup_results, pairwise_results, output_dir)
