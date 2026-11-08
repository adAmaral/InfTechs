"""Gera a landing page estática a partir dos JSON de reports/."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InfTechs — bancada de peças</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #d7e0e6;
      --ink: #14202b;
      --muted: #4d5d6b;
      --panel: #f5f8fa;
      --line: #8fa0ad;
      --accent: #0f4c81;
      --solder: #c45c26;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--ink); font-family: "IBM Plex Sans", sans-serif; }
    body { min-height: 100vh; }
    .wrap { display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; }
    aside {
      background: #14202b;
      color: #d7e0e6;
      padding: 2rem 1.25rem;
      position: sticky;
      top: 0;
      height: 100vh;
    }
    aside .mark { font-family: "IBM Plex Mono", monospace; font-size: 0.85rem; letter-spacing: 0.08em; color: #9ec0df; }
    aside h1 { font-size: 1.35rem; font-weight: 600; margin: 0.4rem 0 1.5rem; line-height: 1.2; }
    aside p { color: #b7c4ce; font-size: 0.92rem; line-height: 1.45; }
    aside nav { margin-top: 2rem; display: flex; flex-direction: column; gap: 0.55rem; }
    aside a { color: #d7e0e6; text-decoration: none; font-size: 0.95rem; border-bottom: 1px solid transparent; }
    aside a:hover, aside a:focus { border-bottom-color: #c45c26; }
    main { padding: 2rem 2.2rem 4rem; max-width: 1100px; }
    h2 { font-size: 1.35rem; font-weight: 600; margin: 2.2rem 0 0.6rem; }
    p.lead { font-size: 1.05rem; max-width: 62ch; line-height: 1.5; color: var(--muted); }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; border: 1px solid var(--ink); background: var(--panel); margin-top: 1.4rem; }
    .kpi { padding: 1rem 1.1rem; border-right: 1px solid var(--line); }
    .kpi:last-child { border-right: 0; }
    .kpi b { display: block; font-family: "IBM Plex Mono", monospace; font-size: 1.45rem; font-weight: 500; }
    .kpi span { color: var(--muted); font-size: 0.88rem; }
    table { width: 100%; border-collapse: collapse; background: var(--panel); font-size: 0.92rem; }
    th, td { text-align: left; padding: 0.55rem 0.7rem; border-bottom: 1px solid var(--line); }
    th { font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; font-weight: 500; color: var(--accent); }
    .toolbar { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 0.8rem 0; }
    input, select { font: inherit; padding: 0.4rem 0.55rem; border: 1px solid var(--ink); background: #fff; }
    .note { border-left: 4px solid var(--solder); padding: 0.4rem 0 0.4rem 0.8rem; color: var(--muted); max-width: 70ch; }
    figure { margin: 1rem 0 0; }
    figure img { max-width: 100%; height: auto; border: 1px solid var(--ink); background: #fff; }
    figcaption { font-size: 0.85rem; color: var(--muted); margin-top: 0.35rem; }
    .empty { padding: 1rem; background: var(--panel); border: 1px dashed var(--line); }
    @media (max-width: 900px) {
      .wrap { grid-template-columns: 1fr; }
      aside { height: auto; position: relative; }
      .kpis { grid-template-columns: 1fr 1fr; }
      .kpi { border-bottom: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <aside>
      <div class="mark">INFTECHS / CRISP-DM</div>
      <h1>Bancada de peças</h1>
      <p>Comparação de componentes a partir de avaliações Amazon Reviews 2023. Preço isolado é snapshot, não inflação.</p>
      <nav>
        <a href="#familia">Famílias</a>
        <a href="#figuras">Figuras</a>
        <a href="#modelo">Modelo</a>
      </nav>
    </aside>
    <main>
      <p class="lead" id="resumo"></p>
      <div class="kpis" id="kpis"></div>
      <p class="note" id="preco-nota"></p>

      <h2 id="familia">Famílias e equivalências</h2>
      <div class="toolbar">
        <label>Família <select id="family"></select></label>
        <label>Busca <input id="q" type="search" placeholder="marca ou família"></label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Família</th><th>Período</th><th>Avaliações</th><th>Nota</th><th>% positivas</th><th>% verificadas</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>

      <h2 id="figuras">Comportamento dos dados</h2>
      <figure>
        <img src="../reports/figures/01_rating_distribution.png" alt="Distribuição das notas">
        <figcaption>Notas concentradas em 4 e 5 — motivo para acurácia balanceada.</figcaption>
      </figure>
      <figure>
        <img src="../reports/figures/04_rating_old_recent.png" alt="Notas antigas versus recentes">
        <figcaption>Mudança de nota entre o quantil antigo e o recente das avaliações.</figcaption>
      </figure>
      <figure>
        <img src="../reports/figures/09_model_comparison.png" alt="Comparação de modelos">
        <figcaption>Baseline majoritário, modelos estruturados e TF-IDF + regressão logística.</figcaption>
      </figure>

      <h2 id="modelo">Escolha do modelo</h2>
      <p id="winner"></p>
      <table>
        <thead><tr><th>Modelo</th><th>Acurácia bal.</th><th>F1</th><th>Precisão</th><th>Revocação</th></tr></thead>
        <tbody id="models"></tbody>
      </table>
      <p class="note">API FastAPI ficou fora deste ciclo (item opcional da disciplina).</p>
    </main>
  </div>
  <script>
    const DATA = __DASHBOARD__;
    const METRICS = __METRICS__;
    document.getElementById("resumo").textContent =
      DATA.reviews.toLocaleString("pt-BR") + " avaliações de " +
      DATA.products.toLocaleString("pt-BR") + " produtos (" + DATA.source + "). Status " + DATA.report_status + ".";
    const kpis = [
      ["Produtos", DATA.products],
      ["Avaliações", DATA.reviews],
      ["% positivas", DATA.positive_pct + "%"],
      ["Preço imputado", DATA.price_missing_pct + "%"]
    ];
    document.getElementById("kpis").innerHTML = kpis.map(([l,v]) =>
      `<div class="kpi"><b>${v}</b><span>${l}</span></div>`).join("");
    const infl = DATA.inflation_estimate_pct;
    document.getElementById("preco-nota").textContent = infl == null
      ? DATA.price_note + " Comparação temporal de preço indisponível neste snapshot."
      : "Estimativa de variação observada nos pares históricos: " + infl.toFixed(2) + "%. Não é índice oficial de inflação.";

    const families = ["todas", ...new Set((DATA.families || []).map(r => r.component_family))];
    const sel = document.getElementById("family");
    families.forEach(f => { const o = document.createElement("option"); o.value = f; o.textContent = f; sel.appendChild(o); });
    function render() {
      const q = document.getElementById("q").value.toLowerCase();
      const fam = sel.value;
      const rows = (DATA.families || []).filter(r =>
        (fam === "todas" || r.component_family === fam) &&
        (r.component_family + " " + r.period).toLowerCase().includes(q)
      );
      document.getElementById("rows").innerHTML = rows.length ? rows.map(r =>
        `<tr><td>${r.component_family}</td><td>${r.period}</td><td>${r.reviews}</td><td>${r.avg_rating}</td><td>${r.positive_pct}</td><td>${r.verified_pct}</td></tr>`
      ).join("") : `<tr><td colspan="6" class="empty">Nenhuma linha neste filtro.</td></tr>`;
    }
    sel.addEventListener("change", render);
    document.getElementById("q").addEventListener("input", render);
    render();

    document.getElementById("winner").textContent = METRICS.justification
      ? ("Modelo adotado: " + METRICS.winner + ". " + METRICS.justification.why)
      : "Métricas ainda não geradas.";
    document.getElementById("models").innerHTML = (METRICS.metrics || []).map(m =>
      `<tr><td>${m.model}</td><td>${m.balanced_accuracy}</td><td>${m.f1}</td><td>${m.precision}</td><td>${m.recall}</td></tr>`
    ).join("");
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, default=Path("web/index.html"))
    args = parser.parse_args()
    dashboard = json.loads((args.reports / "dashboard.json").read_text(encoding="utf-8"))
    metrics_path = args.reports / "model_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if metrics and dashboard.get("run_id") != metrics.get("run_id"):
        raise SystemExit(
            "Os relatórios do dashboard e do modelo pertencem a execuções diferentes; "
            "execute scripts/run_pipeline.py novamente."
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    html = HTML.replace("__DASHBOARD__", json.dumps(dashboard, ensure_ascii=False)).replace("__METRICS__", json.dumps(metrics, ensure_ascii=False))
    args.output.write_text(html, encoding="utf-8")
    print(f"Dashboard em {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
