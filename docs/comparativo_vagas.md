# Comparativo de busca de vagas: antes e depois do Arbeitnow

- **Gerado em:** 2026-11-05T15:06:45+00:00
- **Modo:** `live`
- **Commit:** `e9b4642`
- **Versão do PyScrappy:** `1.6.4`
- **Python:** `3.14.8`

## Escopo

O **antes** é representado pelo `LinkedInJobsScraper`, o único scraper de vagas disponível no PyScrappy antes da feature. O **depois** é representado pelo `ArbeitnowScraper`, novo cliente da API JSON pública do Arbeitnow. O LinkedIn continua disponível, então as duas fontes foram executadas no mesmo ambiente para uma comparação direta.

Este comparativo cobre apenas a API Python. A integração no registro do pacote e a ferramenta MCP `search_arbeitnow_jobs` ainda não fazem parte deste commit, então o Arbeitnow é importado diretamente do módulo.

## Capacidades

| Recurso | LinkedIn (antes) | Arbeitnow (depois) |
|---|---|---|
| Fonte | HTML público, experimental | API JSON pública |
| Autenticação | Nenhuma, mas sujeita a authwall | Nenhuma |
| Filtros | `query`, `location` | `query`, `location`, `remote`, `job_type` |
| Paginação | `max_pages` (~25 vagas/página) | `links.next`, `max_pages` |
| Limite de resultados | Não possui | `max_results` |
| Campos | `title`, `company`, `location`, `url`, `posted`, `salary` | `title`, `company`, `location`, `url`, `tags`, `job_type`, `job_types`, `remote`, `created_at`, `description` |
| Erros | Authwall e rate-limit | Erros tipados em `ScrapeResult.errors` |

## Resumo

| Fonte | Vagas brutas | URLs únicas | Execuções | Execuções com erro | Tempo total (s) |
|---|---:|---:|---:|---:|---:|
| LinkedIn | 180 | 180 | 3 | 0 | 6.81 |
| Arbeitnow | 25 | 25 | 3 | 0 | 16.25 |

## Resultados por consulta

| Fonte | Consulta | Local | Vagas | Únicas | Páginas | Tempo (s) | Erros |
|---|---|---|---:|---:|---:|---:|---|
| LinkedIn | software engineer | (vazio) | 60 | 60 | 1 | 3.32 | - |
| Arbeitnow | software engineer | (vazio) | 17 | 17 | 1 | 7.27 | - |
| LinkedIn | backend | (vazio) | 60 | 60 | 1 | 1.81 | - |
| Arbeitnow | backend | (vazio) | 3 | 3 | 1 | 4.69 | - |
| LinkedIn | engineer | Berlin | 60 | 60 | 1 | 1.68 | - |
| Arbeitnow | engineer | Berlin | 5 | 5 | 1 | 4.29 | - |

## Campos observados

| Fonte | Campos retornados |
|---|---|
| LinkedIn | company, location, posted, title, url |
| Arbeitnow | company, created_at, description, job_type, job_types, location, remote, tags, title, url |

## Amostras

### LinkedIn

```json
[
  {
    "title": "Software Engineer II (Java/AWS)",
    "company": "JPMorganChase",
    "location": "New York, NY",
    "url": "https://www.linkedin.com/jobs/view/software-engineer-ii-java-aws-at-jpmorganchase-4476983365",
    "posted": "2026-10-29"
  },
  {
    "title": "Software Development Engineer, AWS IAM Distributed Database System",
    "company": "Amazon Web Services (AWS)",
    "location": "Seattle, WA",
    "url": "https://www.linkedin.com/jobs/view/software-development-engineer-aws-iam-distributed-database-system-at-amazon-web-services-aws-4455931376",
    "posted": "2026-10-23"
  },
  {
    "title": "Software Dev Engineer II, AWS STS",
    "company": "Amazon Web Services (AWS)",
    "location": "Seattle, WA",
    "url": "https://www.linkedin.com/jobs/view/software-dev-engineer-ii-aws-sts-at-amazon-web-services-aws-4455914852",
    "posted": "2026-10-23"
  }
]
```

### Arbeitnow

```json
[
  {
    "title": "Senior Software Engineer",
    "company": "Matelify",
    "location": "Rödental",
    "url": "https://www.arbeitnow.com/jobs/companies/matelify/senior-software-engineer-rodental-90924",
    "tags": [
      "Web Development"
    ],
    "job_type": "Unbefristeter arbeitsvertrag",
    "job_types": [
      "Unbefristeter arbeitsvertrag",
      "berufserfahren"
    ],
    "remote": false,
    "created_at": "2026-11-05T13:30:59+00:00",
    "description": "Du willst Software bauen, die echte Menschen jeden Tag nutzen und nicht das zwölfte Ticket in einem Konzern abarbeiten? Dann komm zu Matelify. Wir sind ein Startup aus Rödental bei Coburg. Mit Matelify helfen wir Unternehmen, auf Social ..."
  },
  {
    "title": "Senior Software Engineer, Search & AI",
    "company": "Muckrack",
    "location": "Remote (Bulgaria, Canada, Ireland, United States)",
    "url": "https://www.arbeitnow.co.uk/jobs/companies/muckrack/remote-senior-software-engineer-search-ai-82663",
    "tags": [
      "Engineering - Software Engineering"
    ],
    "job_type": null,
    "job_types": [],
    "remote": false,
    "created_at": "2026-11-05T12:55:17+00:00",
    "description": "Muck Rack is trusted by thousands of organizations around the world to understand how their brands show up across news, social media and AI-generated answers. Our AI-powered platform connects the entire PR workflow in one place, helping ..."
  },
  {
    "title": "Staff Software Engineer",
    "company": "Axon",
    "location": "London",
    "url": "https://www.arbeitnow.co.uk/jobs/companies/axon/staff-software-engineer-london-493401",
    "tags": [
      "2012 Sensors - DEMS"
    ],
    "job_type": null,
    "job_types": [],
    "remote": false,
    "created_at": "2026-11-05T09:55:14+00:00",
    "description": "Join Axon and be a Force for Good. At Axon, we’re on a mission to Protect Life. We’re explorers, pursuing society’s most critical safety and justice issues with our ecosystem of devices and cloud software. Like our products, we work bett..."
  }
]
```

## Observações

- O LinkedIn é o representante do **antes**. Nesta execução não houve authwall, mas o scraper segue experimental e pode retornar zero vagas quando a página pública exige autenticação ou bloqueia a requisição.
- O LinkedIn retornou 60 cards por requisição nesta execução, acima das ~25 por página documentadas no docstring. A coluna **URLs únicas** confirma que não houve duplicação de URLs nesta coleta.
- O Arbeitnow é o representante do **depois**. A API não exige chave e devolve vagas normalizadas com filtros locais de `query`, `location`, `remote` e `job_type`. O `query` é uma busca por substring em título e tags, não uma busca full-text; por isso as consultas foram ajustadas para termos presentes no índice no momento da coleta.
- O Arbeitnow deduplica por `slug`/URL. O resultado é uma fotografia do momento da execução: as fontes mudam com o tempo, então os números podem variar entre execuções.
- As descrições HTML do Arbeitnow, inclusive quando vêm escapadas pelo payload, são convertidas para texto simples pelo scraper.
- A atribuição ao Arbeitnow (`https://www.arbeitnow.com`) e o uso moderado estão documentados no docstring do scraper.

### Erros observados

- **LinkedIn:** nenhum erro registrado.
- **Arbeitnow:** nenhum erro registrado.

## Como reproduzir

```bash
# Executa as duas fontes ao vivo e atualiza os fixtures:
python examples/comparar_vagas.py --mode live

# Regenera o relatório apenas com os fixtures salvos:
python examples/comparar_vagas.py --mode fixtures

# Executa ao vivo, salva os fixtures e regenera a partir deles:
python examples/comparar_vagas.py --mode both
```

Os fixtures ficam em `examples/fixtures/comparativo_vagas.json`. Se o PyScrappy não estiver instalado no ambiente, rode com `PYTHONPATH=src`.
