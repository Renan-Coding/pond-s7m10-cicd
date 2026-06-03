"""Gera gráficos a partir dos CSVs produzidos por collect_metrics.py.

4 gráficos obrigatórios + 3 extras (salvos em prints/):
  1_duracao_pipeline.png         — duração total por run (cor por status)
  2_tempo_por_job.png            — tempo por job (lint vs test) por run
  3_taxa_sucesso.png             — sucesso vs falha agregado
  4_testes_vs_duracao.png        — test_count × workflow_duration + tendência
  5_impacto_cache_leve.png       — cache ON vs OFF deps leves (Runs 6/7/8)
  6_paralelo_vs_sequencial.png   — sequencial (Run 8) vs paralelo (Run 9)
  7_impacto_cache_pesado.png     — Run 11 (cache miss pesado) vs Run 12 (cache hit)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

GREEN = "#2ea043"
RED = "#cf222e"
BLUE = "#0969da"
ORANGE = "#fb8500"
GREY = "#8b949e"


def status_color(status: str) -> str:
    return GREEN if status == "success" else RED


def short_label(row: pd.Series) -> str:
    """Label compacto: 'NN: descrição curta'."""
    msg = row["commit_message"]
    if "run " in msg.lower():
        # extrai parte após 'run NN - '
        try:
            tail = msg.split("-", 1)[1].strip()
        except IndexError:
            tail = msg
    else:
        tail = msg
    tail = tail[:32]
    return f"{int(row['run_number']):02d}: {tail}"


def fig1_pipeline_duration(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    labels = df.apply(short_label, axis=1)
    colors = [status_color(s) for s in df["status"]]
    bars = ax.barh(labels, df["workflow_duration"], color=colors, edgecolor="black", linewidth=0.5)
    for bar, dur in zip(bars, df["workflow_duration"]):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{dur:.0f}s",
            va="center",
            fontsize=9,
        )
    ax.set_xlabel("Duração total (s)")
    ax.set_title("Duração total do pipeline por execução")
    ax.invert_yaxis()
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=GREEN, label="success"),
        plt.Rectangle((0, 0), 1, 1, color=RED, label="failure"),
    ]
    ax.legend(handles=handles, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "1_duracao_pipeline.png", dpi=140)
    plt.close(fig)


def fig2_job_breakdown(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    labels = df.apply(short_label, axis=1)
    ax.barh(labels, df["lint_duration"], color=BLUE, label="lint", edgecolor="black", linewidth=0.5)
    ax.barh(
        labels,
        df["test_duration"],
        left=df["lint_duration"],
        color=ORANGE,
        label="test",
        edgecolor="black",
        linewidth=0.5,
    )
    ax.set_xlabel("Tempo por job (s) — empilhado para visualização (jobs paralelos rodam concorrentemente)")
    ax.set_title("Tempo por job (lint vs test) em cada execução")
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "2_tempo_por_job.png", dpi=140)
    plt.close(fig)


def fig3_success_rate(df: pd.DataFrame, out: Path) -> None:
    counts = df["status"].value_counts()
    success = int(counts.get("success", 0))
    failure = int(counts.get("failure", 0))
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    wedges, texts, autotexts = ax.pie(
        [success, failure],
        labels=[f"success ({success})", f"failure ({failure})"],
        colors=[GREEN, RED],
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")
    ax.set_title(f"Taxa de sucesso × falha ({len(df)} execuções)")
    fig.tight_layout()
    fig.savefig(out / "3_taxa_sucesso.png", dpi=140)
    plt.close(fig)


def fig4_tests_vs_duration(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    successes = df[df["status"] == "success"]
    failures = df[df["status"] == "failure"]
    ax.scatter(
        successes["test_count"],
        successes["workflow_duration"],
        c=GREEN,
        s=80,
        edgecolor="black",
        label="success",
        zorder=3,
    )
    ax.scatter(
        failures["test_count"],
        failures["workflow_duration"],
        c=RED,
        s=80,
        edgecolor="black",
        label="failure",
        zorder=3,
    )
    # tendência linear apenas em sucessos com testes > 0
    fit_df = successes[successes["test_count"] > 0]
    if len(fit_df) >= 2:
        slope, intercept = np.polyfit(fit_df["test_count"], fit_df["workflow_duration"], 1)
        x = np.linspace(fit_df["test_count"].min(), fit_df["test_count"].max(), 50)
        ax.plot(
            x,
            slope * x + intercept,
            color=GREY,
            linestyle="--",
            label=f"tendência linear: {slope:.3f}s/teste + {intercept:.1f}s",
        )
    for _, row in df.iterrows():
        ax.annotate(
            f"#{int(row['run_number'])}",
            (row["test_count"], row["workflow_duration"]),
            xytext=(6, 4),
            textcoords="offset points",
            fontsize=8,
            color="black",
        )
    ax.set_xlabel("Quantidade de testes (test_count)")
    ax.set_ylabel("Duração do workflow (s)")
    ax.set_title("Quantidade de testes × duração do pipeline")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "4_testes_vs_duracao.png", dpi=140)
    plt.close(fig)


def fig5_cache_impact(df: pd.DataFrame, out: Path) -> None:
    subset = df[df["run_number"].isin([6, 7, 8])].copy()
    labels = ["Run 6\ncache ON", "Run 7\ncache OFF", "Run 8\ncache ON (religado)"]
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(subset))
    ax.bar(x - 0.2, subset["lint_duration"], width=0.4, color=BLUE, label="lint")
    ax.bar(x + 0.2, subset["test_duration"], width=0.4, color=ORANGE, label="test")
    for i, row in enumerate(subset.itertuples()):
        ax.text(i - 0.2, row.lint_duration + 0.3, f"{row.lint_duration:.0f}s", ha="center", fontsize=9)
        ax.text(i + 0.2, row.test_duration + 0.3, f"{row.test_duration:.0f}s", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Duração do job (s)")
    ax.set_title("Impacto do cache pip (deps leves) — Runs 6, 7, 8")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "5_impacto_cache_leve.png", dpi=140)
    plt.close(fig)


def fig6_parallel_vs_sequential(df: pd.DataFrame, out: Path) -> None:
    subset = df[df["run_number"].isin([8, 9])].copy()
    if len(subset) < 2:
        return
    fig, ax = plt.subplots(figsize=(9, 6))
    labels = ["Run 8\nsequencial (needs: lint)", "Run 9\nparalelo (sem needs)"]
    totals = subset["workflow_duration"].tolist()
    lint = subset["lint_duration"].tolist()
    test = subset["test_duration"].tolist()
    x = np.arange(len(subset))
    bars = ax.bar(x, totals, color=[GREY, GREEN], edgecolor="black")
    for i, (b, lnt, tst, tot) in enumerate(zip(bars, lint, test, totals)):
        ax.text(b.get_x() + b.get_width() / 2, tot + 0.5, f"total: {tot:.0f}s", ha="center", fontweight="bold")
        ax.text(b.get_x() + b.get_width() / 2, tot / 2, f"lint {lnt:.0f}s\ntest {tst:.0f}s", ha="center", color="white", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Duração total do pipeline (s)")
    ax.set_title("Sequencial × paralelo — Run 8 vs Run 9")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "6_paralelo_vs_sequencial.png", dpi=140)
    plt.close(fig)


def fig7_cache_heavy_vs_light(df: pd.DataFrame, out: Path) -> None:
    subset = df[df["run_number"].isin([11, 12])].copy()
    if len(subset) < 2:
        return
    fig, ax = plt.subplots(figsize=(9, 6))
    labels = ["Run 11\ncache MISS (deps pesadas)", "Run 12\ncache HIT (mesmo commit)"]
    x = np.arange(len(subset))
    ax.bar(x - 0.2, subset["lint_duration"], width=0.4, color=BLUE, label="lint")
    ax.bar(x + 0.2, subset["test_duration"], width=0.4, color=ORANGE, label="test")
    for i, row in enumerate(subset.itertuples()):
        ax.text(i - 0.2, row.lint_duration + 0.5, f"{row.lint_duration:.0f}s", ha="center", fontsize=9)
        ax.text(i + 0.2, row.test_duration + 0.5, f"{row.test_duration:.0f}s", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Duração do job (s)")
    ax.set_title("Impacto do cache pip (deps pesadas: pandas+numpy) — Runs 11 vs 12")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "7_impacto_cache_pesado.png", dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera gráficos a partir dos CSVs.")
    parser.add_argument("--summary", default="data/runs_summary.csv")
    parser.add_argument("--long", default="data/runs_long.csv")
    parser.add_argument("--out", default="prints")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.summary)
    df = df.sort_values("run_number").reset_index(drop=True)

    fig1_pipeline_duration(df, out)
    fig2_job_breakdown(df, out)
    fig3_success_rate(df, out)
    fig4_tests_vs_duration(df, out)
    fig5_cache_impact(df, out)
    fig6_parallel_vs_sequential(df, out)
    fig7_cache_heavy_vs_light(df, out)

    print(f"[*] Gráficos salvos em {out}/")


if __name__ == "__main__":
    main()
