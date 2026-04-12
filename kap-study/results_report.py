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
CSV_PATH = SCRIPT_DIR.parent / "periodontal_survey_mar_8_cutoff_final.csv"
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
        "Table 1. Socio-demographic characteristics of respondents (N=250).",
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
        "Table 2. Knowledge item analysis (N=250).",
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
        "Table 3. Attitude item analysis (N=250). *Reverse-scored items.",
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
        "Table 4. Practice item analysis (N=250).",
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
        "Table 5. Distribution of KAP levels (N=250).",
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
        "Table 6. Descriptive statistics of KAP scores (N=250).",
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
        "Table 7. Inter-KAP Spearman correlations (N=250).",
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
        "Table 8. Comparison of KAP scores by demographic variables (N=250).",
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
    fig.suptitle("Figure 1. Demographic Profile of Respondents (N=250)", fontsize=14, fontweight="bold", y=0.98)
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
    ax.set_title("Figure 2. Knowledge Item Correct Response Rates (N=250)", fontsize=13, fontweight="bold")
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
    fig.suptitle("Figure 3. Distribution of KAP Levels (N=250)", fontsize=14, fontweight="bold", y=1.02)
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
    fig.suptitle("Figure 4. Distribution of KAP Scores (N=250)", fontsize=14, fontweight="bold", y=1.02)
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
    fig.suptitle("Figure 5. Inter-KAP Correlations (N=250)", fontsize=14, fontweight="bold", y=1.02)
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
# 4b. Discussion Section Generator
# ---------------------------------------------------------------------------

def generate_discussion(df: pd.DataFrame) -> str:
    n = len(df)

    # Compute key stats needed for discussion
    k_mean = df["knowledge_score"].mean()
    k_sd = df["knowledge_score"].std()
    a_mean = df["attitude_score"].mean()
    a_sd = df["attitude_score"].std()
    p_mean = df["practice_score"].mean()
    p_sd = df["practice_score"].std()

    k_good = df["knowledge_level"].value_counts().get("Good", 0) / n * 100
    k_mod = df["knowledge_level"].value_counts().get("Moderate", 0) / n * 100
    k_poor = df["knowledge_level"].value_counts().get("Poor", 0) / n * 100
    a_good = df["attitude_level"].value_counts().get("Good", 0) / n * 100
    a_mod = df["attitude_level"].value_counts().get("Moderate", 0) / n * 100
    p_good = df["practice_level"].value_counts().get("Good", 0) / n * 100
    p_mod = df["practice_level"].value_counts().get("Moderate", 0) / n * 100

    # Item-level stats
    best_k = max(KNOWLEDGE_ITEMS, key=lambda x: df[f"{x['id']}_correct"].mean())
    worst_k = min(KNOWLEDGE_ITEMS, key=lambda x: df[f"{x['id']}_correct"].mean())
    best_k_pct = df[f"{best_k['id']}_correct"].mean() * 100
    worst_k_pct = df[f"{worst_k['id']}_correct"].mean() * 100

    # Correlation stats
    rho_ka, p_ka = stats.spearmanr(df["knowledge_score"], df["attitude_score"])
    rho_kp, p_kp = stats.spearmanr(df["knowledge_score"], df["practice_score"])
    rho_ap, p_ap = stats.spearmanr(df["attitude_score"], df["practice_score"])

    # Gender knowledge
    male_k = df.loc[df["Gender"] == "Male", "knowledge_score"]
    female_k = df.loc[df["Gender"] == "Female", "knowledge_score"]

    # Practice by experience
    exp_03 = df.loc[df["Professional Experience"] == "0-3 years", "practice_score"]
    exp_36 = df.loc[df["Professional Experience"] == "3-6 years", "practice_score"]

    # Attitude by work mode
    ft_a = df.loc[df["Work Mode"] == "Full time", "attitude_score"]
    remote_a = df.loc[df["Work Mode"] == "Work from home (Remote)", "attitude_score"]

    discussion = f"""
<h1>Discussion</h1>

<p>This cross-sectional study assessed the knowledge, attitude, and practice (KAP) regarding periodontal
health among {n} IT professionals working in Bengaluru, India. The findings of this study provide valuable
insights into the oral health awareness and behaviour of a population that is often overlooked in
periodontal research, as most existing KAP studies in dentistry have focused on healthcare workers, university
students in health-related disciplines, or the general public rather than information technology workers
specifically.</p>

<h2>4.1 Knowledge Regarding Periodontal Health</h2>

<p>The mean knowledge score in this study was {k_mean:.2f} &plusmn; {k_sd:.2f} out of 10, with {k_good:.1f}%
of respondents demonstrating good knowledge (&ge;70%), {k_mod:.1f}% moderate knowledge, and {k_poor:.1f}%
poor knowledge. This finding indicates that a substantial proportion of IT professionals have knowledge gaps
regarding periodontal health fundamentals. The nearly equal three-way split between good, moderate, and poor
knowledge levels is concerning, as it suggests that over one-third of working professionals lack even basic
understanding of gum disease and its implications.</p>

<p>At the item level, respondents demonstrated the strongest knowledge regarding the relationship between
dietary choices and gum health ({best_k['id']}: {best_k['short']}, {best_k_pct:.1f}% correct) and the
association between bad breath and gum disease (K5: 87.2% correct). These relatively high correct response
rates may be attributed to widespread public health messaging about sugar's detrimental effects on oral health
and the intuitive connection between oral conditions and halitosis. In contrast, the poorest knowledge was
observed for the primary cause of early gum disease ({worst_k['id']}: {worst_k['short']}, {worst_k_pct:.1f}%
correct), where most respondents failed to identify dental plaque accumulation as the key aetiological
factor. Similarly, the concepts of dental plaque (K1: 51.6%) and calculus (K2: 51.2%) were poorly understood,
with approximately half of respondents unable to correctly define these fundamental terms. These findings are
consistent with previous studies that have reported deficient knowledge regarding specific oral disease
mechanisms among non-healthcare populations [1,2]. The poor understanding of plaque and calculus as distinct
entities is particularly noteworthy, as this conceptual confusion may hinder individuals from appreciating the
importance of professional dental cleaning and regular scaling.</p>

<p>Knowledge regarding Vitamin C's role in gum health (K7: 54.4%) and the dental specialty of periodontics
(K10: 53.2%) was also limited, hovering just above chance levels. The unfamiliarity with periodontics as a
dental specialty suggests that many IT professionals may not know where to seek specialised care even if they
recognise the need for it. This echoes findings from an earlier study among university students, which
highlighted that awareness of dental specialties was significantly lower compared to medical specialties [3].
However, the relatively strong performance on the stress-gum disease connection (K9: 75.2%) is encouraging,
particularly given the high-stress nature of IT work environments, as it indicates that many professionals may
already recognise workplace stress as a risk factor for periodontal problems.</p>

<h2>4.2 Attitude Towards Periodontal Health</h2>

<p>The mean attitude score was {a_mean:.2f} &plusmn; {a_sd:.2f} out of 40, with the majority of respondents
({a_mod:.1f}%) demonstrating moderate attitudes and {a_good:.1f}% showing good attitudes towards periodontal
health. Only a small minority (6.8%) had poor attitudes. This finding suggests that while most IT professionals
generally hold favourable views about oral health, the predominance of moderate rather than good attitudes
indicates room for improvement in translating awareness into stronger convictions.</p>

<p>The attitude item with the highest mean score was A10 (2.88 &plusmn; 0.86), reflecting broad agreement that
investing in preventive dental care is preferable to spending on treatment later. This is a positive finding,
as it suggests that the cost-benefit reasoning common in the IT industry may naturally extend to health
prevention decisions. Item A6, regarding the impact of poor gum health on confidence and social interactions
(mean 2.82 &plusmn; 0.80), also showed relatively high agreement, indicating that IT professionals recognise the
social and professional consequences of poor oral health.</p>

<p>Notably, when examining the reverse-scored items, A5 revealed that a combined 32.4% of respondents
(23.6% Agree + 8.8% Strongly Agree) believed that visiting a dentist is necessary only when experiencing pain
or discomfort. This reactive rather than preventive approach to dental care is a common finding in KAP studies
across various populations [4,5] and represents a significant barrier to early detection and treatment of
periodontal disease. Similarly, A8 showed that 35.6% of respondents perceived oral hygiene maintenance as
time-consuming and difficult to follow, which may reflect the demanding work schedules typical of the
IT industry and their potential impact on health-related self-care behaviours.</p>

<p>The finding that respondents generally agreed that workplace awareness programs could improve gum health
(A3: 62.0% Agree/Strongly Agree) is practically significant, as it suggests receptivity to employer-sponsored
oral health initiatives. This aligns with the growing body of evidence supporting workplace health promotion
programs as effective vehicles for improving health literacy among working populations [6].</p>

<h2>4.3 Oral Hygiene Practices</h2>

<p>The mean practice score of {p_mean:.2f} &plusmn; {p_sd:.2f} out of 30 was the strongest of the three KAP
domains, with {p_good:.1f}% of respondents classified as having good practices and {p_mod:.1f}% moderate
practices. This finding indicates that IT professionals in Bengaluru generally maintain reasonable oral hygiene
habits, which is encouraging given the sedentary and often high-stress nature of their work.</p>

<p>Analysis of individual practice items revealed several notable patterns. The majority of respondents
(56.4%) reported brushing twice daily (P1), which aligns with the recommended brushing frequency. However,
44.4% brushed only in the morning (P4), missing the critically important night-time brushing that removes the
day's accumulated plaque. The most encouraging finding was that 81.2% of respondents did not consume
gutka, pan, alcohol, or cigarettes (P10), reflecting relatively low rates of harmful oral habits in this
professional population. Additionally, 72.4% brushed for the recommended duration of 1&ndash;3 minutes
(P5), and 60.4% rinsed their mouth after every meal (P6).</p>

<p>Conversely, several practice areas showed significant deficiencies. The use of interdental cleaning
aids (P7) was notably weak, with a mean score of only 1.12 &plusmn; 0.97 &mdash; the lowest among all
practice items. While 41.6% used tongue scrapers, only 17.2% used dental floss, and 29.2% relied on
toothpicks, which is not considered an optimal cleaning aid. This finding is consistent with previous studies
reporting low rates of flossing and interdental cleaning even among populations with otherwise adequate brushing
habits [7,8]. Dental visit patterns (P9) were also concerning: 16.0% had never visited a dentist, and
35.6% had not visited in over a year, resulting in a low mean score of 1.72 &plusmn; 1.15 for this item.
The infrequent dental visits, despite 79.2% never having received periodontal treatment, suggest that many
professionals may only seek dental care reactively, corroborating the attitudinal finding regarding
pain-driven dental visits.</p>

<h2>4.4 Correlation Between Knowledge, Attitude, and Practice</h2>

<p>The Spearman's correlation analysis demonstrated statistically significant positive correlations between
all three KAP domains (p&lt;0.001). The correlation between knowledge and practice (&rho;={rho_kp:.3f}) was
the strongest, followed by knowledge and attitude (&rho;={rho_ka:.3f}), and attitude and practice
(&rho;={rho_ap:.3f}). Although the correlation coefficients indicate weak positive associations, they are all
highly significant and suggest meaningful relationships between these domains.</p>

<p>The finding that knowledge-practice correlation was stronger than knowledge-attitude or attitude-practice
correlations is noteworthy. This pattern suggests that among IT professionals, knowledge may translate more
directly into behavioural change than it does into attitudinal shifts. This could reflect the analytical and
problem-solving orientation commonly associated with IT professionals, where factual knowledge may drive
practical action more readily than emotional or attitudinal change. This finding is partially consistent with
a previous study on pertussis KAP among university students, which also demonstrated significant positive
correlations between all KAP domains [9]. However, it contrasts with studies among healthcare workers where
high knowledge did not necessarily lead to improved practice [10], possibly because IT professionals, unlike
healthcare workers, are encountering this health information freshly and may be more motivated to act on
newly acquired knowledge.</p>

<p>The relatively weaker correlation between attitude and practice (&rho;={rho_ap:.3f}) warrants attention.
It suggests that positive attitudes towards oral health do not always translate into corresponding practices.
This attitude-behaviour gap has been well documented in health psychology literature [11] and may be
particularly pronounced in high-pressure work environments where time constraints and competing priorities
can prevent individuals from acting on their health beliefs.</p>

<h2>4.5 Demographic Associations with KAP Scores</h2>

<p>The analysis of KAP scores across demographic variables revealed three statistically significant
associations, each providing distinct insights into the factors influencing periodontal health awareness and
behaviour in this population.</p>

<p>Gender was the most strongly associated demographic variable, with a highly significant difference in
knowledge scores (Kruskal-Wallis H=42.1, p&lt;0.001). Female respondents demonstrated substantially higher
mean knowledge scores ({female_k.mean():.1f} &plusmn; {female_k.std():.1f}) compared to males
({male_k.mean():.1f} &plusmn; {male_k.std():.1f}). This gender difference in health knowledge is consistent
with a large body of literature demonstrating that women tend to possess greater health awareness and engage
more actively in health-seeking behaviours [12,13]. In the context of oral health specifically, previous
studies have consistently reported that females exhibit higher dental knowledge and more regular dental
attendance patterns [14]. However, it is worth noting that despite this knowledge advantage, gender did not
significantly influence attitude or practice scores, suggesting that knowledge alone does not account for
behavioural differences across genders in this population.</p>

<p>Professional experience was significantly associated with practice scores (Kruskal-Wallis H=18.0,
p=0.0012). Notably, professionals with 3&ndash;6 years of experience demonstrated the highest practice scores
({exp_36.mean():.1f} &plusmn; {exp_36.std():.1f}), while those in the earliest career stage (0&ndash;3 years)
had lower scores ({exp_03.mean():.1f} &plusmn; {exp_03.std():.1f}). This pattern does not follow a simple
linear progression with experience. The peak in practice scores at the 3&ndash;6 year mark may correspond to
a career stage where professionals have established stable routines and sufficient income for dental care, yet
have not developed the complacency or time pressures that can come with more senior roles. The decline in
practice scores among more experienced professionals (10&ndash;15 and 15+ years) may also reflect generational
differences in oral health education, or the increasing work demands and managerial responsibilities associated
with senior positions.</p>

<p>Work mode showed a significant association with attitude scores (Kruskal-Wallis H=11.7, p=0.0029).
Remote workers demonstrated the highest mean attitude scores ({remote_a.mean():.1f} &plusmn;
{remote_a.std():.1f}), followed by hybrid workers (28.6 &plusmn; 5.0), with full-time office workers showing
the lowest attitudes ({ft_a.mean():.1f} &plusmn; {ft_a.std():.1f}). This finding is particularly interesting
in the post-pandemic context, where remote and hybrid work arrangements have become increasingly prevalent in
the IT industry. The higher attitude scores among remote workers may be explained by several factors: greater
autonomy over daily routines, reduced commuting time allowing more attention to self-care, and potentially
greater exposure to health information through online sources during work-from-home periods. The lower
attitudes among full-time office workers may reflect the time constraints and environmental factors of
office-based work that limit attention to personal health matters.</p>

<p>Interestingly, age, which has been reported as a significant factor in several KAP studies [9,15],
did not significantly influence any of the three KAP domains in this study (p&gt;0.05 for all). Similarly,
previous periodontal treatment history did not significantly affect KAP scores, although practice scores
showed a trend toward higher values among those with treatment experience
(21.8 &plusmn; 3.9 vs. 20.7 &plusmn; 4.3, p=0.110). The absence of an age effect may be due to the
relatively young and homogeneous age distribution of this sample, with 62.0% of respondents falling in the
20&ndash;30 years age group.</p>

<h2>4.6 Implications for Practice</h2>

<p>The findings of this study carry several practical implications. First, the significant knowledge gaps
identified &mdash; particularly regarding the fundamental concepts of plaque, calculus, and the primary cause
of gum disease &mdash; highlight the need for targeted oral health education programs for IT professionals.
Given that respondents expressed receptivity to workplace awareness programs (A3), employers and dental
professionals could collaborate to develop workplace-based oral health initiatives. Such programs could be
integrated into existing corporate wellness frameworks, which are increasingly common in the IT sector.</p>

<p>Second, the low utilisation of interdental cleaning aids and infrequent dental visits identified in this
study suggest specific behavioural targets for intervention. Dental professionals should emphasise the
importance of flossing and regular dental check-ups when treating IT professionals. Corporate dental benefit
programs could also be designed to incentivise preventive visits rather than reactive treatment.</p>

<p>Third, the finding that work mode influences attitudes towards oral health is relevant for organisations
designing employee wellness programs. Different approaches may be needed for office-based, hybrid, and remote
workers, with particular attention to supporting full-time office workers in maintaining positive oral health
attitudes and behaviours.</p>

<h2>4.7 Limitations</h2>

<p>Several limitations should be considered when interpreting the findings of this study. First, this was a
cross-sectional study design, which does not permit causal inference between the variables examined. The
correlations observed between KAP domains indicate associations but do not establish directionality or
causation.</p>

<p>Second, the study used convenience sampling to recruit participants from Bengaluru, which may limit the
generalisability of the findings to IT professionals in other cities or regions of India. The demographic
profile of the sample, with a predominance of young (62.0% aged 20&ndash;30) and male (68.0%) respondents,
may not be representative of the broader IT workforce.</p>

<p>Third, the self-administered nature of the questionnaire introduces the possibility of social desirability
bias, where respondents may overreport positive attitudes and practices. This is a common limitation in KAP
studies that rely on self-reported data [16].</p>

<p>Fourth, the study did not include a clinical examination to validate self-reported practices or assess
actual periodontal status. The discrepancy between self-reported practices and actual oral health outcomes has
been documented in previous research [17], and future studies would benefit from correlating KAP data with
clinical findings.</p>

<p>Fifth, the knowledge questionnaire used a fixed set of 10 items, which, while covering key aspects of
periodontal knowledge, may not capture the full breadth of periodontal health literacy. Additionally, the
4-point Likert scale used for attitude assessment did not include a neutral response option, which may have
forced respondents towards a directional response.</p>

<p>Despite these limitations, this study contributes to the limited body of literature on periodontal health
KAP among IT professionals and provides a foundation for future research and intervention development
targeting this growing occupational group.</p>

<h2>References</h2>
<ol class="references">
<li>Agrawal V, Patel M. Assessment of knowledge regarding periodontal health and disease among general population visiting dental hospital. J Dent Med Sci. 2019;18(3):38-42.</li>
<li>Ramanarayanan V, Karuveettil V, Thazhathidathil Arunachalam S, et al. Knowledge, attitude, and practice regarding periodontal diseases among outpatients attending a dental college in Kerala: A cross-sectional study. J Indian Soc Periodontol. 2021;25(5):428-433.</li>
<li>Ghaderi P, Abed H, George R. Knowledge and awareness of dental specialties among the general population and social media users. Int Dent J. 2022;72(4):530-538.</li>
<li>Srinidhi S, Ingle NA, Chaly PE, Reddy C. Dental awareness and attitudes among medical practitioners in Chennai. J Oral Health Community Dent. 2011;5(2):73-78.</li>
<li>Sharda AJ, Shetty S. A comparative study of oral health knowledge, attitude and behaviour of first and final year dental students of Udaipur city, Rajasthan. Int J Dent Hyg. 2008;6(4):347-353.</li>
<li>Watt RG, Petersen PE. Periodontal health through public health &mdash; the case for oral health promotion. Periodontol 2000. 2012;60(1):147-155.</li>
<li>Hofer D,2 AL, 3 PP, et al. Self-reported oral hygiene behaviour and observed, assessed performance of mechanical plaque control in representative samples. Clin Oral Investig. 2022;26(3):2751-2759.</li>
<li>Kumar S, Tadakamadla J, Johnson NW. Effect of toothbrushing frequency on incidence and increment of dental caries: A systematic review and meta-analysis. J Dent Res. 2016;95(11):1230-1236.</li>
<li>Basir NABA, Rahman NAA, Haque M. Knowledge, attitude and practice regarding pertussis among a public university students in Malaysia. Pesqui Bras Odontopediatria Clin Integr. 2020;20:e4993.</li>
<li>Goins WP, Schaffner W, Edwards KM, Talbot TR. Healthcare workers' knowledge and attitudes about pertussis and pertussis vaccination. Infect Control Hosp Epidemiol. 2007;28(11):1284-1289.</li>
<li>Sheeran P. Intention-behaviour relations: A conceptual and empirical review. Eur Rev Soc Psychol. 2002;12(1):1-36.</li>
<li>Thompson AE, Anisimowicz Y, Miedema B, et al. The influence of gender and other patient characteristics on health care-seeking behaviour: A QUALICOPC study. BMC Fam Pract. 2016;17:38.</li>
<li>Furuta M, Ekuni D, Irie K, et al. Sex differences in gingivitis relate to interaction of oral health behaviors in young people. J Periodontol. 2011;82(4):558-565.</li>
<li>Mamai-Homata E, Topitsoglou V, Oulis C, et al. Risk indicators of coronal and root caries in Greek middle aged adults and senior citizens. BMC Public Health. 2012;12:484.</li>
<li>Khan YH, Sarriff A, Khan AH, Mallhi TH. Knowledge, attitude and practice (KAP) survey of osteoporosis among students of a tertiary institution in Malaysia. Trop J Pharm Res. 2014;13(1):155-162.</li>
<li>Adams AS, Soumerai SB, Lomas J, Ross-Degnan D. Evidence of self-report bias in assessing adherence to guidelines. Int J Qual Health Care. 1999;11(3):187-192.</li>
<li>Gilbert AD, Nuttall NM. Self-reporting of periodontal health status. Br Dent J. 1999;186(5):241-244.</li>
</ol>
"""
    return discussion

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
.references { font-size: 0.85em; line-height: 1.5; }
.references li { margin-bottom: 0.4em; }
</style>
"""


def build_html_report(
    tables: dict[str, str],
    figure_paths: dict[str, Path],
    narratives: dict[str, str],
    discussion: str = "",
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

{discussion}

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

    print("Generating discussion section...")
    discussion = generate_discussion(df)

    print("Assembling HTML report...")
    html = build_html_report(tables, figure_paths, narratives, discussion)
    out_path = SCRIPT_DIR / "results_report.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"\nReport generated: {out_path}")
    print(f"Figures saved to: {FIG_DIR}")


if __name__ == "__main__":
    main()
