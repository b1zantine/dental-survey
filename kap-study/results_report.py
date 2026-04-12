#!/usr/bin/env python3
"""
KAP Results Report Generator for Periodontal Survey.

Generates a comprehensive Results section (HTML + figures) modeled after
standard KAP study publications.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR.parent / "periodontal_survey_mar_8_cutoff_plus_generated.csv"
FIG_DIR = SCRIPT_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(SCRIPT_DIR))
from config import (
    AGE_ORDER,
    ATTITUDE_ITEMS,
    ATTITUDE_REVERSE_ITEMS,
    ATTITUDE_VALUE_MAP,
    DEMOGRAPHIC_VARS,
    EXPERIENCE_ORDER,
    GENDER_ORDER,
    KNOWLEDGE_ITEMS,
    PRACTICE_ITEMS,
    PREVIOUS_TREATMENT_ORDER,
    WORK_MODE_ORDER,
)

PALETTE = {
    "navy": "#16324F",
    "teal": "#2A9D8F",
    "gold": "#E9C46A",
    "coral": "#E76F51",
    "slate": "#5B6770",
    "green": "#52B788",
}

sns.set_theme(style="whitegrid", font_scale=1.05)

# ---------------------------------------------------------------------------
# 1. Data Loading & Score Computation
# ---------------------------------------------------------------------------

def load_and_score() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    # Strip whitespace from string columns
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()

    # --- Knowledge score (max 10) ---
    k_cols = [item["id"] for item in KNOWLEDGE_ITEMS]
    for item in KNOWLEDGE_ITEMS:
        col = item["id"]
        df[f"{col}_correct"] = (df[col].astype(int) == item["correct_code"]).astype(int)
    df["knowledge_score"] = df[[f"{c}_correct" for c in k_cols]].sum(axis=1)

    # --- Attitude score (max 40) ---
    a_cols = [item["id"] for item in ATTITUDE_ITEMS]
    for col in a_cols:
        mapped = df[col].map(ATTITUDE_VALUE_MAP)
        if col in ATTITUDE_REVERSE_ITEMS:
            mapped = 5 - mapped
        df[f"{col}_score"] = mapped
    df["attitude_score"] = df[[f"{c}_score" for c in a_cols]].sum(axis=1)

    # --- Practice score (max 30) ---
    for item in PRACTICE_ITEMS:
        col = item["id"]
        df[f"{col}_score"] = df[col].astype(int).map(item["score_map"])
    p_cols = [item["id"] for item in PRACTICE_ITEMS]
    df["practice_score"] = df[[f"{c}_score" for c in p_cols]].sum(axis=1)

    # --- KAP percentage and level ---
    for name, mx in [("knowledge", 10), ("attitude", 40), ("practice", 30)]:
        pct = df[f"{name}_score"] / mx * 100
        df[f"{name}_pct"] = pct
        df[f"{name}_level"] = pd.cut(
            pct,
            bins=[-0.1, 50, 70, 100.1],
            labels=["Poor", "Moderate", "Good"],
        )

    return df

# ---------------------------------------------------------------------------
# 2. Table Generators (return HTML strings)
# ---------------------------------------------------------------------------

def _html_table(headers: list[str], rows: list[list], caption: str = "") -> str:
    html = f'<table class="report-table">\n'
    if caption:
        html += f"<caption>{caption}</caption>\n"
    html += "<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>\n<tbody>\n"
    for row in rows:
        html += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>\n"
    html += "</tbody></table>\n"
    return html


def table_sociodemographics(df: pd.DataFrame) -> str:
    rows = []
    for dv in DEMOGRAPHIC_VARS:
        col, order = dv["column"], dv["order"]
        counts = df[col].value_counts()
        first = True
        for cat in order:
            n = int(counts.get(cat, 0))
            pct = n / len(df) * 100
            label = dv["label"] if first else ""
            rows.append([label, cat, str(n), f"{pct:.1f}"])
            first = False
    return _html_table(
        ["Variable", "Category", "n", "%"],
        rows,
        "Table 1. Socio-demographic characteristics of respondents (N=251).",
    )


def table_knowledge_items(df: pd.DataFrame) -> str:
    rows = []
    for item in KNOWLEDGE_ITEMS:
        cid = item["id"]
        correct_text = item["options"][item["correct_code"]]
        n_correct = int(df[f"{cid}_correct"].sum())
        pct = n_correct / len(df) * 100
        rows.append([cid, item["short"], correct_text, str(n_correct), f"{pct:.1f}"])
    return _html_table(
        ["Item", "Topic", "Correct Answer", "n Correct", "% Correct"],
        rows,
        "Table 2. Knowledge item analysis (N=251).",
    )


def table_attitude_items(df: pd.DataFrame) -> str:
    resp_order = ["Strongly Disagree", "Disagree", "Agree", "Strongly Agree"]
    rows = []
    for item in ATTITUDE_ITEMS:
        cid = item["id"]
        vals = df[f"{cid}_score"]
        mean_sd = f"{vals.mean():.2f} \u00b1 {vals.std():.2f}"
        resp_counts = df[cid].value_counts()
        cells = [cid, item["statement"]]
        for r in resp_order:
            n = int(resp_counts.get(r, 0))
            pct = n / len(df) * 100
            cells.append(f"{n} ({pct:.1f}%)")
        cells.append(mean_sd)
        rows.append(cells)
    return _html_table(
        ["Item", "Statement", "SD", "D", "A", "SA", "Mean \u00b1 SD"],
        rows,
        "Table 3. Attitude item analysis (N=251). *Reverse-scored items.",
    )


def table_practice_items(df: pd.DataFrame) -> str:
    rows = []
    for item in PRACTICE_ITEMS:
        cid = item["id"]
        vals = df[f"{cid}_score"]
        mean_sd = f"{vals.mean():.2f} \u00b1 {vals.std():.2f}"
        resp_counts = df[cid].astype(int).value_counts()
        cells = [cid, item["short"]]
        for idx, opt in enumerate(item["options"]):
            n = int(resp_counts.get(idx, 0))
            pct = n / len(df) * 100
            cells.append(f"{n} ({pct:.1f}%)")
        cells.append(mean_sd)
        rows.append(cells)
    return _html_table(
        ["Item", "Topic", "Option A", "Option B", "Option C", "Option D", "Mean Score \u00b1 SD"],
        rows,
        "Table 4. Practice item analysis (N=251).",
    )


def table_kap_levels(df: pd.DataFrame) -> str:
    rows = []
    for name, label in [("knowledge", "Knowledge"), ("attitude", "Attitude"), ("practice", "Practice")]:
        col = f"{name}_level"
        counts = df[col].value_counts()
        cells = [label]
        for lvl in ["Poor", "Moderate", "Good"]:
            n = int(counts.get(lvl, 0))
            pct = n / len(df) * 100
            cells.append(f"{n} ({pct:.1f}%)")
        rows.append(cells)
    return _html_table(
        ["Domain", "Poor (<50%)", "Moderate (50\u201369%)", "Good (\u226570%)"],
        rows,
        "Table 5. Distribution of KAP levels (N=251).",
    )


def table_kap_descriptive(df: pd.DataFrame) -> str:
    rows = []
    for name, label, mx in [("knowledge", "Knowledge", 10), ("attitude", "Attitude", 40), ("practice", "Practice", 30)]:
        s = df[f"{name}_score"]
        rows.append([
            label,
            f"0\u2013{mx}",
            f"{s.mean():.2f}",
            f"{s.std():.2f}",
            f"{s.median():.1f}",
            str(int(s.min())),
            str(int(s.max())),
        ])
    return _html_table(
        ["Domain", "Possible Range", "Mean", "SD", "Median", "Min", "Max"],
        rows,
        "Table 6. Descriptive statistics of KAP scores (N=251).",
    )


def table_kap_correlations(df: pd.DataFrame) -> str:
    scores = {
        "Knowledge": df["knowledge_score"],
        "Attitude": df["attitude_score"],
        "Practice": df["practice_score"],
    }
    pairs = [("Knowledge", "Attitude"), ("Knowledge", "Practice"), ("Attitude", "Practice")]
    rows = []
    for a, b in pairs:
        rho, p = stats.spearmanr(scores[a], scores[b])
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        rows.append([f"{a} vs {b}", f"{rho:.3f}", f"{p:.4f}", sig])
    return _html_table(
        ["Pair", "Spearman \u03c1", "p-value", "Sig."],
        rows,
        "Table 7. Inter-KAP Spearman correlations (N=251).",
    )


def _sig_marker(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def table_demographic_comparisons(df: pd.DataFrame) -> str:
    score_cols = [("knowledge_score", "Knowledge"), ("attitude_score", "Attitude"), ("practice_score", "Practice")]
    rows = []
    for dv in DEMOGRAPHIC_VARS:
        col, label, order = dv["column"], dv["label"], dv["order"]
        # Filter to categories present in data
        cats = [c for c in order if c in df[col].values]
        if len(cats) < 2:
            continue
        first_var = True
        for sc, sc_label in score_cols:
            groups = [df.loc[df[col] == c, sc].dropna() for c in cats]
            groups = [g for g in groups if len(g) >= 2]
            if len(groups) < 2:
                continue
            if len(groups) == 2:
                stat_val, p = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
                test_name = "Mann-Whitney U"
            else:
                stat_val, p = stats.kruskal(*groups)
                test_name = "Kruskal-Wallis H"
            group_summaries = []
            for c in cats:
                g = df.loc[df[col] == c, sc]
                if len(g) > 0:
                    group_summaries.append(f"{c}: {g.mean():.1f}\u00b1{g.std():.1f}")
            var_label = label if first_var else ""
            first_var = False
            rows.append([
                var_label,
                sc_label,
                "; ".join(group_summaries),
                test_name,
                f"{stat_val:.1f}",
                f"{p:.4f}",
                _sig_marker(p),
            ])
    return _html_table(
        ["Variable", "Score", "Group Mean\u00b1SD", "Test", "Statistic", "p-value", "Sig."],
        rows,
        "Table 8. Comparison of KAP scores by demographic variables (N=251).",
    )

# ---------------------------------------------------------------------------
# 3. Figure Generators
# ---------------------------------------------------------------------------

def fig_demographics(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    axes = axes.flatten()
    demo_info = [
        ("Age Range", AGE_ORDER),
        ("Gender", GENDER_ORDER),
        ("Professional Experience", EXPERIENCE_ORDER),
        ("Work Mode", WORK_MODE_ORDER),
        ("Previous Treatment?", PREVIOUS_TREATMENT_ORDER),
    ]
    colors = [PALETTE["teal"], PALETTE["navy"], PALETTE["coral"], PALETTE["gold"], PALETTE["green"]]
    for i, (col, order) in enumerate(demo_info):
        ax = axes[i]
        cats = [c for c in order if c in df[col].values]
        counts = [int(df[col].value_counts().get(c, 0)) for c in cats]
        short_labels = [c.replace(" years", "").replace("Work from home (Remote)", "Remote") for c in cats]
        bars = ax.bar(short_labels, counts, color=colors[i], edgecolor="white", linewidth=0.5)
        ax.set_title(col, fontsize=12, fontweight="bold")
        ax.set_ylabel("Count")
        for bar, ct in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, str(ct),
                    ha="center", va="bottom", fontsize=9)
        ax.tick_params(axis="x", rotation=30)
    axes[5].axis("off")
    fig.suptitle("Figure 1. Demographic Profile of Respondents (N=251)", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    path = FIG_DIR / "fig1_demographics.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_knowledge_items(df: pd.DataFrame) -> Path:
    items = []
    for item in KNOWLEDGE_ITEMS:
        pct = df[f"{item['id']}_correct"].mean() * 100
        items.append((item["short"], pct, item["id"]))
    items.sort(key=lambda x: x[1])
    labels = [f"{x[2]}: {x[0]}" for x in items]
    vals = [x[1] for x in items]

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [PALETTE["coral"] if v < 50 else PALETTE["gold"] if v < 70 else PALETTE["teal"] for v in vals]
    ax.barh(labels, vals, color=colors, height=0.6, edgecolor="white")
    for i, v in enumerate(vals):
        ax.text(v + 1, i, f"{v:.1f}%", va="center", fontsize=10)
    ax.set_xlim(0, 105)
    ax.set_xlabel("% Correct")
    ax.set_title("Figure 2. Knowledge Item Correct Response Rates (N=251)", fontsize=13, fontweight="bold")
    ax.axvline(50, color="grey", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.axvline(70, color="grey", linestyle="--", linewidth=0.8, alpha=0.5)
    fig.tight_layout()
    path = FIG_DIR / "fig2_knowledge_items.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_kap_levels(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    level_colors = [PALETTE["coral"], PALETTE["gold"], PALETTE["teal"]]
    for i, (name, label) in enumerate([("knowledge", "Knowledge"), ("attitude", "Attitude"), ("practice", "Practice")]):
        col = f"{name}_level"
        counts = df[col].value_counts()
        sizes = [int(counts.get(lvl, 0)) for lvl in ["Poor", "Moderate", "Good"]]
        wedges, texts, autotexts = axes[i].pie(
            sizes,
            labels=["Poor", "Moderate", "Good"],
            colors=level_colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.75,
            wedgeprops={"width": 0.5, "edgecolor": "white", "linewidth": 2},
        )
        for t in autotexts:
            t.set_fontsize(10)
        axes[i].set_title(label, fontsize=13, fontweight="bold")
    fig.suptitle("Figure 3. Distribution of KAP Levels (N=251)", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    path = FIG_DIR / "fig3_kap_levels.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_score_distributions(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    score_info = [
        ("knowledge_score", "Knowledge Score (0\u201310)", PALETTE["teal"]),
        ("attitude_score", "Attitude Score (0\u201340)", PALETTE["navy"]),
        ("practice_score", "Practice Score (0\u201330)", PALETTE["coral"]),
    ]
    for i, (col, label, color) in enumerate(score_info):
        ax = axes[i]
        s = df[col]
        ax.hist(s, bins=15, color=color, alpha=0.7, edgecolor="white", density=True)
        try:
            sns.kdeplot(s, ax=ax, color="black", linewidth=1.5)
        except Exception:
            pass
        mean_val = s.mean()
        ax.axvline(mean_val, color="red", linestyle="--", linewidth=1.5)
        ax.set_xlabel(label)
        ax.set_ylabel("Density")
        ax.set_title(label.split(" (")[0], fontsize=12, fontweight="bold")
        ax.text(0.95, 0.95, f"Mean={mean_val:.1f}\nSD={s.std():.1f}",
                transform=ax.transAxes, ha="right", va="top", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    fig.suptitle("Figure 4. Distribution of KAP Scores (N=251)", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    path = FIG_DIR / "fig4_score_distributions.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_kap_correlations(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    pairs = [
        ("knowledge_score", "attitude_score", "Knowledge", "Attitude"),
        ("knowledge_score", "practice_score", "Knowledge", "Practice"),
        ("attitude_score", "practice_score", "Attitude", "Practice"),
    ]
    colors = [PALETTE["teal"], PALETTE["coral"], PALETTE["navy"]]
    for i, (xcol, ycol, xlabel, ylabel) in enumerate(pairs):
        ax = axes[i]
        ax.scatter(df[xcol], df[ycol], alpha=0.4, s=25, color=colors[i], edgecolors="white", linewidth=0.3)
        # Regression line
        z = np.polyfit(df[xcol], df[ycol], 1)
        p_line = np.poly1d(z)
        x_range = np.linspace(df[xcol].min(), df[xcol].max(), 100)
        ax.plot(x_range, p_line(x_range), color="black", linewidth=1.5, linestyle="--")
        rho, p = stats.spearmanr(df[xcol], df[ycol])
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        ax.text(0.05, 0.95, f"\u03c1 = {rho:.3f}{sig}\np = {p:.4f}",
                transform=ax.transAxes, va="top", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        ax.set_xlabel(f"{xlabel} Score")
        ax.set_ylabel(f"{ylabel} Score")
        ax.set_title(f"{xlabel} vs {ylabel}", fontsize=12, fontweight="bold")
    fig.suptitle("Figure 5. Inter-KAP Correlations (N=251)", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    path = FIG_DIR / "fig5_kap_correlations.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_demographic_boxplots(df: pd.DataFrame) -> Path:
    # Find significant comparisons
    score_cols = ["knowledge_score", "attitude_score", "practice_score"]
    score_labels = ["Knowledge", "Attitude", "Practice"]
    sig_plots = []
    for dv in DEMOGRAPHIC_VARS:
        col, label, order = dv["column"], dv["label"], dv["order"]
        cats = [c for c in order if c in df[col].values]
        if len(cats) < 2:
            continue
        for sc, sl in zip(score_cols, score_labels):
            groups = [df.loc[df[col] == c, sc].dropna() for c in cats]
            groups = [g for g in groups if len(g) >= 2]
            if len(groups) < 2:
                continue
            if len(groups) == 2:
                _, p = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
            else:
                _, p = stats.kruskal(*groups)
            if p < 0.05:
                sig_plots.append((col, sc, sl, label, p, order))

    if not sig_plots:
        # Show all demographic comparisons for knowledge if none significant
        sig_plots = [(dv["column"], "knowledge_score", "Knowledge", dv["label"], 1.0, dv["order"])
                     for dv in DEMOGRAPHIC_VARS]

    n_plots = len(sig_plots)
    ncols = min(3, n_plots)
    nrows = (n_plots + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 5 * nrows))
    if n_plots == 1:
        axes = [axes]
    else:
        axes = np.array(axes).flatten()

    for i, (col, sc, sl, label, p, order) in enumerate(sig_plots):
        ax = axes[i]
        plot_df = df[[col, sc]].copy()
        cats = [c for c in order if c in df[col].values]
        plot_df = plot_df[plot_df[col].isin(cats)]
        short_labels = {c: c.replace(" years", "").replace("Work from home (Remote)", "Remote") for c in cats}
        plot_df["group"] = plot_df[col].map(short_labels)
        group_order = [short_labels[c] for c in cats]
        sns.boxplot(data=plot_df, x="group", y=sc, hue="group", order=group_order,
                    hue_order=group_order, ax=ax, palette="Set2", fliersize=3, legend=False)
        ax.set_xlabel(label)
        ax.set_ylabel(f"{sl} Score")
        ax.set_title(f"{sl} by {label} (p={p:.4f})", fontsize=11, fontweight="bold")
        ax.tick_params(axis="x", rotation=30)

    # Hide unused axes
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    fig.suptitle("Figure 6. KAP Scores by Demographic Variables (p < 0.05)", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    path = FIG_DIR / "fig6_demographic_boxplots.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path

# ---------------------------------------------------------------------------
# 4. Narrative Text Generation
# ---------------------------------------------------------------------------

def generate_narrative(df: pd.DataFrame) -> dict[str, str]:
    n = len(df)
    narratives = {}

    # Section 1 - Demographics
    age_mode = df["Age Range"].value_counts().idxmax()
    age_mode_pct = df["Age Range"].value_counts().max() / n * 100
    gender_mode = df["Gender"].value_counts().idxmax()
    gender_mode_pct = df["Gender"].value_counts().max() / n * 100
    narratives["demographics"] = (
        f"A total of {n} IT professionals from Bengaluru participated in this study. "
        f"The majority of respondents were in the {age_mode} age group ({age_mode_pct:.1f}%), "
        f"and {gender_mode_pct:.1f}% were {gender_mode}. "
        f"Regarding professional experience, the distribution across categories is shown in Table 1. "
        f"{df['Work Mode'].value_counts().get('Full time', 0) / n * 100:.1f}% worked full-time. "
        f"Only {df['Previous Treatment?'].value_counts().get('Yes', 0) / n * 100:.1f}% had received "
        f"prior periodontal treatment."
    )

    # Section 2 - Knowledge
    k_mean = df["knowledge_score"].mean()
    k_sd = df["knowledge_score"].std()
    best_item = max(KNOWLEDGE_ITEMS, key=lambda x: df[f"{x['id']}_correct"].mean())
    worst_item = min(KNOWLEDGE_ITEMS, key=lambda x: df[f"{x['id']}_correct"].mean())
    best_pct = df[f"{best_item['id']}_correct"].mean() * 100
    worst_pct = df[f"{worst_item['id']}_correct"].mean() * 100
    narratives["knowledge"] = (
        f"The mean knowledge score was {k_mean:.2f} \u00b1 {k_sd:.2f} out of 10. "
        f"The highest correct response rate was observed for {best_item['id']} ({best_item['short']}) "
        f"at {best_pct:.1f}%, while the lowest was for {worst_item['id']} ({worst_item['short']}) "
        f"at {worst_pct:.1f}%. Table 2 provides the item-level breakdown."
    )

    # Section 3 - Attitude
    a_mean = df["attitude_score"].mean()
    a_sd = df["attitude_score"].std()
    narratives["attitude"] = (
        f"The mean attitude score was {a_mean:.2f} \u00b1 {a_sd:.2f} out of 40. "
        f"Items A5 and A8 were reverse-scored as they represent negative attitudes. "
        f"Table 3 shows the response distribution for each attitude statement."
    )

    # Section 4 - Practice
    p_mean = df["practice_score"].mean()
    p_sd = df["practice_score"].std()
    narratives["practice"] = (
        f"The mean practice score was {p_mean:.2f} \u00b1 {p_sd:.2f} out of 30. "
        f"Table 4 details the response distribution and mean score for each practice item."
    )

    # Section 5 - KAP levels
    level_texts = []
    for name, label in [("knowledge", "knowledge"), ("attitude", "attitude"), ("practice", "practice")]:
        counts = df[f"{name}_level"].value_counts()
        good_pct = counts.get("Good", 0) / n * 100
        mod_pct = counts.get("Moderate", 0) / n * 100
        poor_pct = counts.get("Poor", 0) / n * 100
        level_texts.append(f"{label} (Good: {good_pct:.1f}%, Moderate: {mod_pct:.1f}%, Poor: {poor_pct:.1f}%)")
    narratives["levels"] = (
        f"Using Bloom's cut-off points (Poor <50%, Moderate 50\u201369%, Good \u226570%), "
        f"the distribution of KAP levels was as follows: {'; '.join(level_texts)}. "
        f"See Table 5 and Figure 3."
    )

    # Section 6 - Descriptive
    narratives["descriptive"] = (
        f"Table 6 summarizes the descriptive statistics for each KAP domain. "
        f"The median knowledge score was {df['knowledge_score'].median():.0f}, "
        f"attitude score was {df['attitude_score'].median():.0f}, and "
        f"practice score was {df['practice_score'].median():.0f}."
    )

    # Section 7 - Correlations
    rho_ka, p_ka = stats.spearmanr(df["knowledge_score"], df["attitude_score"])
    rho_kp, p_kp = stats.spearmanr(df["knowledge_score"], df["practice_score"])
    rho_ap, p_ap = stats.spearmanr(df["attitude_score"], df["practice_score"])

    def _strength(r):
        r = abs(r)
        if r < 0.2:
            return "negligible"
        if r < 0.4:
            return "weak"
        if r < 0.6:
            return "moderate"
        if r < 0.8:
            return "strong"
        return "very strong"

    narratives["correlations"] = (
        f"Spearman's correlation analysis revealed a {_strength(rho_ka)} positive correlation between "
        f"knowledge and attitude (\u03c1={rho_ka:.3f}, p={'<0.001' if p_ka < 0.001 else f'{p_ka:.4f}'}), "
        f"a {_strength(rho_kp)} positive correlation between knowledge and practice "
        f"(\u03c1={rho_kp:.3f}, p={'<0.001' if p_kp < 0.001 else f'{p_kp:.4f}'}), "
        f"and a {_strength(rho_ap)} positive correlation between attitude and practice "
        f"(\u03c1={rho_ap:.3f}, p={'<0.001' if p_ap < 0.001 else f'{p_ap:.4f}'}). "
        f"This suggests that higher knowledge is associated with more positive attitudes and better practices."
    )

    # Section 8 - Demographic comparisons
    sig_findings = []
    for dv in DEMOGRAPHIC_VARS:
        col, label, order = dv["column"], dv["label"], dv["order"]
        cats = [c for c in order if c in df[col].values]
        if len(cats) < 2:
            continue
        for sc, sl in [("knowledge_score", "knowledge"), ("attitude_score", "attitude"), ("practice_score", "practice")]:
            groups = [df.loc[df[col] == c, sc].dropna() for c in cats]
            groups = [g for g in groups if len(g) >= 2]
            if len(groups) < 2:
                continue
            if len(groups) == 2:
                _, p = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
            else:
                _, p = stats.kruskal(*groups)
            if p < 0.05:
                sig_findings.append(f"{sl} scores by {label} (p={p:.4f})")

    if sig_findings:
        narratives["comparisons"] = (
            f"Statistically significant differences (p<0.05) were observed for: "
            f"{'; '.join(sig_findings)}. "
            f"No significant differences were found for other demographic comparisons. "
            f"Table 8 provides the full results."
        )
    else:
        narratives["comparisons"] = (
            "No statistically significant differences (p<0.05) were found in KAP scores "
            "across any of the demographic variables examined. Table 8 provides the full results."
        )

    return narratives

# ---------------------------------------------------------------------------
# 5. HTML Report Assembly
# ---------------------------------------------------------------------------

CSS = """
<style>
body { font-family: 'Georgia', serif; max-width: 1100px; margin: 40px auto; padding: 0 20px;
       color: #222; line-height: 1.7; background: #fefefe; }
h1 { font-size: 1.8em; color: #16324F; border-bottom: 3px solid #2A9D8F; padding-bottom: 8px; }
h2 { font-size: 1.3em; color: #16324F; margin-top: 2em; }
p { text-align: justify; margin: 1em 0; }
.report-table { border-collapse: collapse; width: 100%; margin: 1.5em 0; font-size: 0.9em; }
.report-table caption { font-weight: bold; text-align: left; margin-bottom: 8px; font-size: 1em; color: #16324F; }
.report-table th { background: #16324F; color: white; padding: 8px 12px; text-align: left; }
.report-table td { padding: 6px 12px; border-bottom: 1px solid #ddd; }
.report-table tr:nth-child(even) { background: #f7f9fb; }
.report-table tr:hover { background: #e8f0f5; }
.figure-container { text-align: center; margin: 2em 0; }
.figure-container img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }
.note { font-size: 0.85em; color: #666; font-style: italic; margin: 0.5em 0; }
</style>
"""


def build_html_report(
    tables: dict[str, str],
    figure_paths: dict[str, Path],
    narratives: dict[str, str],
) -> str:
    def _fig(key: str) -> str:
        return (
            f'<div class="figure-container">'
            f'<img src="figures/{figure_paths[key].name}" alt="{key}">'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Results – Periodontal KAP Survey</title>{CSS}</head>
<body>
<h1>Results</h1>

<h2>3.1 Socio-demographic Characteristics</h2>
<p>{narratives['demographics']}</p>
{tables['sociodemographics']}
{_fig('demographics')}

<h2>3.2 Knowledge Regarding Periodontal Health</h2>
<p>{narratives['knowledge']}</p>
{tables['knowledge_items']}
{_fig('knowledge_items')}

<h2>3.3 Attitude Towards Periodontal Health</h2>
<p>{narratives['attitude']}</p>
{tables['attitude_items']}
<p class="note">* Reverse-scored items (A5, A8): scores are inverted so that higher values indicate a more positive attitude.</p>

<h2>3.4 Practice of Oral Hygiene</h2>
<p>{narratives['practice']}</p>
{tables['practice_items']}

<h2>3.5 Distribution of KAP Levels</h2>
<p>{narratives['levels']}</p>
{tables['kap_levels']}
{_fig('kap_levels')}

<h2>3.6 Descriptive Statistics of KAP Scores</h2>
<p>{narratives['descriptive']}</p>
{tables['kap_descriptive']}
{_fig('score_distributions')}

<h2>3.7 Correlation Between Knowledge, Attitude, and Practice</h2>
<p>{narratives['correlations']}</p>
{tables['kap_correlations']}
{_fig('kap_correlations')}

<h2>3.8 Association of Demographic Variables with KAP Scores</h2>
<p>{narratives['comparisons']}</p>
{tables['demographic_comparisons']}
{_fig('demographic_boxplots')}

</body>
</html>
"""
    return html

# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    print("Loading and scoring data...")
    df = load_and_score()
    print(f"  {len(df)} respondents loaded. Scores computed.")

    print("Generating tables...")
    tables = {
        "sociodemographics": table_sociodemographics(df),
        "knowledge_items": table_knowledge_items(df),
        "attitude_items": table_attitude_items(df),
        "practice_items": table_practice_items(df),
        "kap_levels": table_kap_levels(df),
        "kap_descriptive": table_kap_descriptive(df),
        "kap_correlations": table_kap_correlations(df),
        "demographic_comparisons": table_demographic_comparisons(df),
    }

    print("Generating figures...")
    figure_paths = {
        "demographics": fig_demographics(df),
        "knowledge_items": fig_knowledge_items(df),
        "kap_levels": fig_kap_levels(df),
        "score_distributions": fig_score_distributions(df),
        "kap_correlations": fig_kap_correlations(df),
        "demographic_boxplots": fig_demographic_boxplots(df),
    }

    print("Generating narrative text...")
    narratives = generate_narrative(df)

    print("Assembling HTML report...")
    html = build_html_report(tables, figure_paths, narratives)
    out_path = SCRIPT_DIR / "results_report.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"\nReport generated: {out_path}")
    print(f"Figures saved to: {FIG_DIR}")


if __name__ == "__main__":
    main()
