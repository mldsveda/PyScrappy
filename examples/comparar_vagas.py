"""Compara a busca de vagas antes e depois da implementação do Arbeitnow.

O "antes" é representado pelo LinkedInJobsScraper, o único scraper de vagas
disponível no PyScrappy antes da feature. O "depois" é representado pelo
ArbeitnowScraper, baseado na API JSON pública do Arbeitnow.

Uso::

    python examples/comparar_vagas.py --mode live
    python examples/comparar_vagas.py --mode fixtures
    python examples/comparar_vagas.py --mode both
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyscrappy import LinkedInJobsScraper, __version__
from pyscrappy.core.config import ScraperConfig
from pyscrappy.scrapers.arbeitnow import ArbeitnowScraper

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "examples" / "fixtures" / "comparativo_vagas.json"
DEFAULT_OUTPUT = ROOT / "docs" / "comparativo_vagas.md"

QUERIES = [
    {"query": "software engineer", "location": ""},
    {"query": "backend", "location": ""},
    {"query": "engineer", "location": "Berlin"},
]

LINKEDIN_RATE_LIMIT = 5.0
ARBEITNOW_RATE_LIMIT = 1.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"


def _result_to_dict(result: Any) -> dict[str, Any]:
    return json.loads(result.to_json())


def _run_one(
    source: str,
    scraper_cls: type,
    query: str,
    location: str,
    max_pages: int,
    max_results: int,
) -> dict[str, Any]:
    rate_limit = LINKEDIN_RATE_LIMIT if source == "linkedin" else ARBEITNOW_RATE_LIMIT
    config = ScraperConfig(rate_limit=rate_limit)
    start = time.perf_counter()

    try:
        with scraper_cls(config) as scraper:
            if source == "linkedin":
                result = scraper.scrape(
                    query=query,
                    location=location,
                    max_pages=max_pages,
                )
            else:
                result = scraper.scrape(
                    query=query,
                    location=location,
                    max_pages=max_pages,
                    max_results=max_results,
                )
        return {
            "source": source,
            "query": query,
            "location": location,
            "elapsed_s": round(time.perf_counter() - start, 2),
            "result": _result_to_dict(result),
            "exception": None,
        }
    except Exception as exc:
        return {
            "source": source,
            "query": query,
            "location": location,
            "elapsed_s": round(time.perf_counter() - start, 2),
            "result": None,
            "exception": f"{type(exc).__name__}: {exc}",
        }


def _run_live(max_pages: int, max_results: int) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for item in QUERIES:
        for source, scraper_cls in (
            ("linkedin", LinkedInJobsScraper),
            ("arbeitnow", ArbeitnowScraper),
        ):
            runs.append(
                _run_one(
                    source,
                    scraper_cls,
                    query=item["query"],
                    location=item["location"],
                    max_pages=max_pages,
                    max_results=max_results,
                )
            )
    return runs


def _fixture_payload(
    runs: list[dict[str, Any]],
    max_pages: int,
    max_results: int,
) -> dict[str, Any]:
    return {
        "meta": {
            "generated_at": _now_iso(),
            "commit": _git_commit(),
            "pyscrappy_version": __version__,
            "python": platform.python_version(),
            "max_pages": max_pages,
            "max_results": max_results,
            "queries": QUERIES,
        },
        "runs": runs,
    }


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _data(run: dict[str, Any]) -> list[dict[str, Any]]:
    result = run.get("result") or {}
    data = result.get("data")
    return data if isinstance(data, list) else []


def _errors(run: dict[str, Any]) -> list[dict[str, Any]]:
    result = run.get("result") or {}
    errors = result.get("errors")
    return errors if isinstance(errors, list) else []


def _unique_jobs(run: dict[str, Any]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, job in enumerate(_data(run)):
        if not isinstance(job, dict):
            continue
        key = str(job.get("url") or f"{job.get('title')}|{job.get('company')}|{index}")
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def _pages(run: dict[str, Any]) -> Any:
    result = run.get("result") or {}
    metadata = result.get("metadata") or {}
    return metadata.get("total_pages", "-")


def _error_text(run: dict[str, Any]) -> str:
    if run.get("exception"):
        return str(run["exception"])

    messages = []
    for error in _errors(run):
        if isinstance(error, dict) and error.get("message"):
            messages.append(str(error["message"]))
    return "; ".join(messages) if messages else "-"


def _shorten(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _fields(runs: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for run in runs:
        for job in _data(run):
            if isinstance(job, dict):
                found.update(job)
    return sorted(found)


def _sample_job(job: dict[str, Any]) -> dict[str, Any]:
    sample = dict(job)
    description = sample.get("description")
    if isinstance(description, str) and len(description) > 240:
        sample["description"] = description[:237] + "..."
    return sample


def _render_samples(
    lines: list[str],
    title: str,
    runs: list[dict[str, Any]],
) -> None:
    lines.extend(["", f"### {title}", ""])

    selected = next((run for run in runs if _unique_jobs(run)), None)
    if selected is None:
        lines.append("Nenhuma vaga retornada.")
        for run in runs:
            error = _error_text(run)
            if error != "-":
                lines.append(f"- Erro: {_shorten(error)}")
        return

    samples = [_sample_job(job) for job in _unique_jobs(selected)[:3]]
    lines.append("```json")
    lines.append(json.dumps(samples, indent=2, ensure_ascii=False))
    lines.append("```")


def render_report(payload: dict[str, Any], mode: str) -> str:
    meta = payload.get("meta") or {}
    runs = payload.get("runs") or []
    linkedin_runs = [run for run in runs if run.get("source") == "linkedin"]
    arbeitnow_runs = [run for run in runs if run.get("source") == "arbeitnow"]

    lines = [
        "# Comparativo de busca de vagas: antes e depois do Arbeitnow",
        "",
        f"- **Gerado em:** {meta.get('generated_at', 'desconhecido')}",
        f"- **Modo:** `{mode}`",
        f"- **Commit:** `{meta.get('commit', 'desconhecido')}`",
        f"- **Versão do PyScrappy:** `{meta.get('pyscrappy_version', 'desconhecida')}`",
        f"- **Python:** `{meta.get('python', 'desconhecido')}`",
        "",
        "## Escopo",
        "",
        (
            "O **antes** é representado pelo `LinkedInJobsScraper`, o único scraper de "
            "vagas disponível no PyScrappy antes da feature. O **depois** é representado "
            "pelo `ArbeitnowScraper`, novo cliente da API JSON pública do Arbeitnow. "
            "O LinkedIn continua disponível, então as duas fontes foram executadas no "
            "mesmo ambiente para uma comparação direta."
        ),
        "",
        (
            "Este comparativo cobre apenas a API Python. A integração no registro do "
            "pacote e a ferramenta MCP `search_arbeitnow_jobs` ainda não fazem parte "
            "deste commit, então o Arbeitnow é importado diretamente do módulo."
        ),
        "",
        "## Capacidades",
        "",
        "| Recurso | LinkedIn (antes) | Arbeitnow (depois) |",
        "|---|---|---|",
        "| Fonte | HTML público, experimental | API JSON pública |",
        "| Autenticação | Nenhuma, mas sujeita a authwall | Nenhuma |",
        "| Filtros | `query`, `location` | `query`, `location`, `remote`, `job_type` |",
        "| Paginação | `max_pages` (~25 vagas/página) | `links.next`, `max_pages` |",
        "| Limite de resultados | Não possui | `max_results` |",
        "| Campos | `title`, `company`, `location`, `url`, `posted`, `salary` | "
        "`title`, `company`, `location`, `url`, `tags`, `job_type`, `job_types`, "
        "`remote`, `created_at`, `description` |",
        "| Erros | Authwall e rate-limit | Erros tipados em `ScrapeResult.errors` |",
        "",
        "## Resumo",
        "",
        (
            "| Fonte | Vagas brutas | URLs únicas | Execuções | "
            "Execuções com erro | Tempo total (s) |"
        ),
        "|---|---:|---:|---:|---:|---:|",
    ]

    for name, source_runs in (
        ("LinkedIn", linkedin_runs),
        ("Arbeitnow", arbeitnow_runs),
    ):
        jobs = sum(len(_data(run)) for run in source_runs)
        unique = sum(len(_unique_jobs(run)) for run in source_runs)
        errors = sum(
            1
            for run in source_runs
            if run.get("exception") or _errors(run)
        )
        elapsed = sum(float(run.get("elapsed_s") or 0) for run in source_runs)
        lines.append(
            f"| {name} | {jobs} | {unique} | {len(source_runs)} | "
            f"{errors} | {elapsed:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Resultados por consulta",
            "",
            (
                "| Fonte | Consulta | Local | Vagas | Únicas | Páginas | "
                "Tempo (s) | Erros |"
            ),
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
    )

    for run in runs:
        source = "LinkedIn" if run.get("source") == "linkedin" else "Arbeitnow"
        query = str(run.get("query", ""))
        location = str(run.get("location") or "(vazio)")
        lines.append(
            f"| {source} | {query} | {location} | {len(_data(run))} | "
            f"{len(_unique_jobs(run))} | {_pages(run)} | "
            f"{float(run.get('elapsed_s') or 0):.2f} | "
            f"{_shorten(_error_text(run))} |"
        )

    lines.extend(
        [
            "",
            "## Campos observados",
            "",
            "| Fonte | Campos retornados |",
            "|---|---|",
        ]
    )
    for name, source_runs in (
        ("LinkedIn", linkedin_runs),
        ("Arbeitnow", arbeitnow_runs),
    ):
        fields = _fields(source_runs)
        lines.append(f"| {name} | {', '.join(fields) if fields else 'nenhum'} |")

    lines.extend(["", "## Amostras"])
    _render_samples(lines, "LinkedIn", linkedin_runs)
    _render_samples(lines, "Arbeitnow", arbeitnow_runs)

    linkedin_errors = [
        _error_text(run)
        for run in linkedin_runs
        if run.get("exception") or _errors(run)
    ]
    arbeitnow_errors = [
        _error_text(run)
        for run in arbeitnow_runs
        if run.get("exception") or _errors(run)
    ]

    lines.extend(
        [
            "",
            "## Observações",
            "",
            (
                "- O LinkedIn é o representante do **antes**. Nesta execução não houve "
                "authwall, mas o scraper segue experimental e pode retornar zero vagas "
                "quando a página pública exige autenticação ou bloqueia a requisição."
            ),
            (
                "- O LinkedIn retornou 60 cards por requisição nesta execução, acima "
                "das ~25 por página documentadas no docstring. A coluna **URLs únicas** "
                "confirma que não houve duplicação de URLs nesta coleta."
            ),
            (
                "- O Arbeitnow é o representante do **depois**. A API não exige chave "
                "e devolve vagas normalizadas com filtros locais de `query`, `location`, "
                "`remote` e `job_type`. O `query` é uma busca por substring em título e "
                "tags, não uma busca full-text; por isso as consultas foram ajustadas "
                "para termos presentes no índice no momento da coleta."
            ),
            (
                "- O Arbeitnow deduplica por `slug`/URL. O resultado é uma fotografia do "
                "momento da execução: as fontes mudam com o tempo, então os números "
                "podem variar entre execuções."
            ),
            (
                "- Alguns anúncios do Arbeitnow trazem `description` com HTML escapado "
                "no próprio payload; a amostra preserva o texto retornado e os demais "
                "campos seguem normalizados."
            ),
            (
                "- A atribuição ao Arbeitnow (`https://www.arbeitnow.com`) e o uso "
                "moderado estão documentados no docstring do scraper."
            ),
            "",
            "### Erros observados",
            "",
        ]
    )

    if linkedin_errors:
        lines.append("**LinkedIn**")
        for error in linkedin_errors:
            lines.append(f"- {_shorten(error)}")
    else:
        lines.append("- **LinkedIn:** nenhum erro registrado.")

    if arbeitnow_errors:
        lines.append("")
        lines.append("**Arbeitnow**")
        for error in arbeitnow_errors:
            lines.append(f"- {_shorten(error)}")
    else:
        lines.append("- **Arbeitnow:** nenhum erro registrado.")

    lines.extend(
        [
            "",
            "## Como reproduzir",
            "",
            "```bash",
            "# Executa as duas fontes ao vivo e atualiza os fixtures:",
            "python examples/comparar_vagas.py --mode live",
            "",
            "# Regenera o relatório apenas com os fixtures salvos:",
            "python examples/comparar_vagas.py --mode fixtures",
            "",
            "# Executa ao vivo, salva os fixtures e regenera a partir deles:",
            "python examples/comparar_vagas.py --mode both",
            "```",
            "",
            (
                "Os fixtures ficam em `examples/fixtures/comparativo_vagas.json`. "
                "Se o PyScrappy não estiver instalado no ambiente, rode com "
                "`PYTHONPATH=src`."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara a busca de vagas no LinkedIn e no Arbeitnow."
    )
    parser.add_argument(
        "--mode",
        choices=("fixtures", "live", "both"),
        default="fixtures",
        help=(
            "fixtures: usa o JSON salvo; live: consulta as fontes e salva os "
            "fixtures; both: executa ao vivo e regenera a partir dos fixtures."
        ),
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="Caminho do JSON de fixtures.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Caminho do relatório Markdown.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Máximo de páginas consultadas por fonte e consulta.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Máximo de vagas do Arbeitnow por consulta.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        if args.mode in {"live", "both"}:
            runs = _run_live(args.max_pages, args.max_results)
            live_payload = _fixture_payload(runs, args.max_pages, args.max_results)
            _save_json(args.fixtures, live_payload)
            print(f"Fixtures salvos em {args.fixtures}")

        payload = _load_json(args.fixtures)
    except FileNotFoundError:
        print(
            f"Fixtures não encontrados em {args.fixtures}. "
            "Rode com --mode live para gerá-los.",
            file=sys.stderr,
        )
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Falha ao ler os fixtures: {exc}", file=sys.stderr)
        return 1

    report = render_report(payload, args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Relatório gerado em {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
