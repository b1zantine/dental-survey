"""Report assembly helpers, including notebook generation."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


def write_insights(insights: list[str], path: str | Path) -> None:
    output = Path(path)
    output.write_text("\n".join(f"- {line}" for line in insights) + "\n", encoding="utf-8")


def generate_notebook(notebook_path: str | Path, augmented_csv: str, observed_csv: str, out_dir: str | Path) -> None:
    notebook_path = Path(notebook_path)
    out_dir = Path(out_dir)

    nb = nbf.v4.new_notebook()
    cells = []

    cells.append(
        nbf.v4.new_markdown_cell(
            "# Periodontal Survey Analysis Report\n\n"
            "This notebook presents a research-style exploratory analysis of the periodontal survey among IT professionals. "
            "The augmented `plus_generated` dataset is used for primary visuals and exploratory inference, while the observed-only "
            "dataset is loaded again for sensitivity checks."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "from __future__ import annotations\n\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            "import pandas as pd\n"
            "from IPython.display import Markdown, SVG, display\n\n"
            "def find_root() -> Path:\n"
            "    for candidate in [Path.cwd(), *Path.cwd().parents]:\n"
            "        if (candidate / 'periodontal_survey_mar_8_cutoff.csv').exists():\n"
            "            return candidate\n"
            "    raise FileNotFoundError('Could not locate the project root.')\n\n"
            "ROOT = find_root()\n"
            "if str(ROOT) not in sys.path:\n"
            "    sys.path.insert(0, str(ROOT))\n\n"
            "from analysis.run_analysis import run_pipeline\n\n"
            "AUGMENTED_CSV = ROOT / %r\n"
            "OBSERVED_CSV = ROOT / %r\n"
            "OUT_DIR = ROOT / %r\n"
            "TABLES_DIR = OUT_DIR / 'tables'\n"
            "FIGURES_DIR = OUT_DIR / 'figures'\n"
            "FORCE_REGENERATE = False\n\n"
            "required_outputs = [\n"
            "    OUT_DIR / 'cleaned_analysis_dataset.csv',\n"
            "    TABLES_DIR / 'analysis_metadata.json',\n"
            "    TABLES_DIR / 'insights.md',\n"
            "]\n\n"
            "if FORCE_REGENERATE or not all(path.exists() for path in required_outputs):\n"
            "    run_pipeline(AUGMENTED_CSV, OBSERVED_CSV, OUT_DIR)\n"
            % (augmented_csv, observed_csv, str(out_dir))
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Data provenance\n\n"
            "The notebook reconstructs the score variables directly from item responses. "
            "This is necessary because the source app writes a `Knowledge Score` field but does not actually compute it."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "metadata = json.loads((TABLES_DIR / 'analysis_metadata.json').read_text())\n"
            "metadata"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Analysis-ready dataset\n\n"
            "The cleaned dataset adds `sample_source`, recomputed score columns, response labels, locality normalization, "
            "and a duration artifact flag."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "analysis_df = pd.read_csv(OUT_DIR / 'cleaned_analysis_dataset.csv', parse_dates=['timestamp'])\n"
            "analysis_df[['sample_source', 'age_range', 'gender', 'professional_experience', 'work_mode', 'previous_treatment', 'knowledge_score', 'attitude_score', 'practice_index']].head()"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Descriptive tables"
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "table_one = pd.read_csv(TABLES_DIR / 'table_1_sample_characteristics.csv')\n"
            "composite_summary = pd.read_csv(TABLES_DIR / 'composite_score_summary.csv')\n"
            "reliability_summary = pd.read_csv(TABLES_DIR / 'reliability_summary.csv')\n"
            "display(table_one.head(20))\n"
            "display(composite_summary)\n"
            "display(reliability_summary)"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Statistical analysis outputs"
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "subgroup_results = pd.read_csv(TABLES_DIR / 'subgroup_results_augmented.csv')\n"
            "pairwise_results = pd.read_csv(TABLES_DIR / 'subgroup_pairwise_results_augmented.csv')\n"
            "kap_correlations = pd.read_csv(TABLES_DIR / 'kap_correlations.csv')\n"
            "regression_results = pd.read_csv(TABLES_DIR / 'regression_results.csv')\n"
            "sensitivity_summary = pd.read_csv(TABLES_DIR / 'sensitivity_summary.csv')\n"
            "display(subgroup_results.head(15))\n"
            "display(kap_correlations)\n"
            "display(regression_results.head(15))\n"
            "display(sensitivity_summary.head(15))"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Figures"
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "figure_names = [\n"
            "    'demographic_profile_panel',\n"
            "    'trimmed_duration_distribution',\n"
            "    'knowledge_item_lollipop',\n"
            "    'attitude_diverging_likert',\n"
            "    'practice_response_heatmap',\n"
            "    'composite_score_distributions',\n"
            "    'kap_correlation_matrix',\n"
            "    'observed_vs_generated_comparison',\n"
            "    'regression_effect_forest',\n"
            "]\n"
            "for name in figure_names:\n"
            "    display(Markdown(f'### {name.replace(\"_\", \" \").title()}'))\n"
            "    display(SVG(filename=str(FIGURES_DIR / f'{name}.svg')))"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Interpretation and caveats\n\n"
            "The key takeaways below are generated after the analysis pipeline writes the final summary tables. "
            "Keep the exploratory label attached to any finding that depends on the synthetic augmentation."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "display(Markdown((TABLES_DIR / 'insights.md').read_text()))"
        )
    )

    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    }
    notebook_path.write_text(nbf.writes(nb), encoding="utf-8")
