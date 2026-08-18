"""
Jornada guiada de planilhas: analisar antes de validar (1.8B-2B).

O card antigo fazia tudo numa requisicao: subia o arquivo e ja validava, com
um schema fixo. Aqui a jornada tem etapas, e a pessoa ve o diagnostico antes
de decidir como validar:

    POST /api/spreadsheets/analyze              upload OU exemplo -> diagnostico
    POST /api/spreadsheets/{token}/selection    aba / linha de cabecalho
    POST /api/spreadsheets/{token}/schema       sugerido OU YAML proprio
    POST /api/spreadsheets/{token}/validate     executa e gera as evidencias

O TOKEN E O MESMO do inicio ao fim: o mesmo `Job` do Live carrega a jornada,
entao SSE (`/api/stream`), resultado (`/api/result`) e downloads
(`/api/download`) continuam funcionando sem que o frontend precise
relacionar dois identificadores.

ONDE FICAM OS ARQUIVOS (nenhum caminho destes aparece em resposta da API):

    <workspace>/in/<arquivo>                 o upload. NUNCA alterado, NUNCA baixavel.
    <workspace>/out/schema_sugerido.yaml     gerado na analise; baixavel.
    <workspace>/config/schema_confirmado.yaml o schema escolhido; interno.
    <workspace>/out/...                      artefatos e pacote, apos validar.

`config/` fica FORA de `out/` de proposito: o download so serve arquivos de
`out/`, entao o schema confirmado nao vira baixavel por acidente enquanto e
apenas uma escolha. O que a validacao realmente aplicou aparece depois como
`schema_efetivo.yaml` DENTRO do pacote — esse nome pertence ao que executou,
nao ao que foi selecionado.

O QUE NAO ACONTECE AQUI: nenhuma regra de leitura, perfilagem ou validacao e
reimplementada. A analise chama o servico da 1.8B-1; a validacao roda pelo
mesmo subprocesso isolado da 1.8A, com argv montado por allowlist.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import yaml
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from autotarefas.core.exceptions import AutoTarefasError
from autotarefas.core.logger import logger
from autotarefas.organize import (
    ANALYSIS_REPORT_NAME,
    ORGANIZED_XLSX_NAME,
    IndicatorRequest,
    ReportInput,
    SortRequest,
    audit_presentation,
    build_indicators,
    date_format_notes,
    default_request,
    needs_sheet_choice,
    organize_workbook,
    suggest_roles,
    summary_is_offerable,
    survey_sheets,
    text_number_notes,
    write_analysis_report,
)
from autotarefas.profiles import (
    MappingError,
    ProfileError,
    export_schema,
    list_profiles,
    load_profile,
)
from autotarefas.services import analyze_spreadsheet
from autotarefas.tasks.execution_package import build_review_rows
from autotarefas.tasks.validate import load_schema

from . import engine, jobs, ratelimit, recipes, samples, uploads
from .config import settings

if TYPE_CHECKING:
    from autotarefas.services.analysis import AnalysisOutcome

router = APIRouter(prefix="/api/spreadsheets", tags=["spreadsheets"])

#: Formatos que o leitor trata com seguranca. Nao basta a extensao: o proprio
#: leitor recusa conteudo que nao forme uma tabela.
_ALLOWED_EXTS = (".csv", ".xlsx")

#: Um schema YAML de validacao e um arquivo pequeno. Este teto existe para
#: que um envio grande nao ocupe o servidor nem o parser.
_MAX_SCHEMA_BYTES = 256 * 1024

#: Extensoes aceitas para o schema enviado.
_SCHEMA_EXTS = (".yaml", ".yml")

#: Automacao usada na execucao final. Reaproveitar "validate" mantem intactas
#: as decisoes da 1.8A: o mapeamento de exit code para `outcome` e a matriz de
#: pos-processamento (que zipa o pacote em caught_issue) valem sem alteracao.
_VALIDATE_AUTOMATION = "validate"

#: Onde o exemplo da jornada vem. Reusa o mesmo mecanismo do card antigo,
#: entao exemplo e upload seguem exatamente o mesmo caminho depois daqui.
_SAMPLE_AUTOMATION = "validate"

_HTTP_BAD_REQUEST = 400
_HTTP_NOT_FOUND = 404
_HTTP_CONFLICT = 409
_HTTP_PAYLOAD_TOO_LARGE = 413
_HTTP_UNSUPPORTED_MEDIA = 415
_HTTP_TOO_MANY = 429
_HTTP_BUSY = 503

_background: set[asyncio.Task[None]] = set()


def _error(status: int, detail: str, *, code: str) -> JSONResponse:
    """
    Erro estruturado: `code` para a interface decidir o que fazer, `detail`
    para a pessoa ler. Nunca traceback, nunca caminho de arquivo.
    """
    return JSONResponse({"detail": detail, "code": code}, status_code=status)


def _journey_of(token: str) -> tuple[jobs.Job, jobs.Journey] | JSONResponse:
    """
    Recupera o job e a jornada de um token, ou devolve o erro apropriado.

    Um token de outra automacao (ou de outra pessoa) nao tem jornada, entao
    cai em 404 igual a um token inexistente: nao confirmamos a existencia de
    execucoes que nao pertencem a esta jornada.
    """
    job = jobs.get(token)
    if job is None:
        return _error(_HTTP_NOT_FOUND, "sessao nao encontrada ou expirada", code="expired")
    if job.journey is None:
        return _error(_HTTP_NOT_FOUND, "sessao nao encontrada ou expirada", code="expired")
    return job, job.journey


def _duplicate_rows_found(journey: jobs.Journey) -> int:
    """
    Quantas linhas COMPLETAMENTE identicas a analise encontrou.

    Vem do achado estrutural do leitor (`linhas_duplicadas`), que conta as
    ocorrencias EXCEDENTES — a primeira de cada grupo e o original. Nao
    confundir com chave repetida: numa planilha de vendas o mesmo codigo
    aparece varias vezes por item da venda, e isso e esperado.
    """
    for achado in journey.analysis.get("findings") or []:
        if not isinstance(achado, dict) or achado.get("code") != "linhas_duplicadas":
            continue
        quantidade = achado.get("count")
        if isinstance(quantidade, int) and quantidade > 0:
            return quantidade
        # `count` nem sempre vem preenchido neste achado; o numero abre a
        # mensagem ("16 linha(s) completamente identica(s)...").
        primeiro = str(achado.get("message", "")).split(" ", 1)[0]
        return int(primeiro) if primeiro.isdigit() else 0
    return 0


def _ativar_deteccao_de_duplicadas(schema_path: Path) -> None:
    """
    Liga `detect_duplicate_rows` no schema CONFIRMADO.

    O schema sugerido deixa essa regra comentada de proposito: o nucleo nao
    inventa regra de negocio. Aqui ela so e ligada porque a PESSOA confirmou
    na tela de revisao, depois de ver quantas linhas repetidas existem. O
    arquivo alterado e o mesmo que vira `schema_efetivo.yaml` no pacote, entao
    a evidencia mostra exatamente o que rodou.
    """
    conteudo = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    if not isinstance(conteudo, dict):  # pragma: no cover - schema ja validado
        return
    if conteudo.get("detect_duplicate_rows") is True:
        return
    conteudo["detect_duplicate_rows"] = True
    schema_path.write_text(
        yaml.safe_dump(conteudo, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _e_xlsx(caminho: Path) -> bool:
    return caminho.suffix.lower() in {".xlsx", ".xlsm"}


def _ler_frame(journey: jobs.Journey) -> pd.DataFrame | None:
    """
    Le a tabela FIEL do arquivo, sob demanda.

    A jornada nao guarda o DataFrame de proposito (seria uma copia grande
    presa ate o TTL). Reler custa pouco no teto de 10 MB do Live e mantem
    uma fonte de verdade so: o arquivo no workspace.
    """
    from autotarefas.reader import read_workbook

    try:
        leitura = read_workbook(
            journey.source_path, sheet=journey.sheet, header_row=journey.header_row
        )
    except Exception:  # noqa: BLE001 - arquivo ruim ja foi tratado na analise
        return None
    return leitura.original_dataframe if leitura.ok else None


def _diagnostico_estendido(journey: jobs.Journey) -> dict[str, Any]:
    """
    O que a analise geral acrescenta ao diagnostico estrutural.

    Quatro coisas que a pessoa precisa ANTES de decidir: como estao as abas,
    como esta a apresentacao, o que chama atencao nos dados e se da para
    propor um resumo com seguranca. Nada aqui altera o arquivo, e nada e
    aplicado — e diagnostico.

    Em CSV nao ha apresentacao nem abas para avaliar: o payload sai vazio,
    e a interface simplesmente nao oferece a organizacao visual.
    """
    origem = journey.source_path
    if not _e_xlsx(origem):
        return {"sheets": [], "presentation": None, "multiple_sheets": False, "notes": []}

    try:
        abas = survey_sheets(origem)
        auditoria = audit_presentation(
            origem, sheet=journey.sheet, header_row=journey.header_row or 1
        )
    except (OSError, ValueError, KeyError):  # pragma: no cover - arquivo ilegivel
        return {"sheets": [], "presentation": None, "multiple_sheets": False, "notes": []}

    journey.presentation_verdict = auditoria.verdict
    return {
        "sheets": [info.as_dict() for info in abas],
        "presentation": auditoria.as_dict(),
        "multiple_sheets": needs_sheet_choice(abas),
        # Observacoes que mudam a decisao de quem esta olhando a tela agora.
        # Estavam so no relatorio, depois de executar — tarde demais.
        "notes": [*_observacoes_dos_dados(journey)],
    }


def _observacoes_dos_dados(journey: jobs.Journey) -> list[str]:
    """O que chama atencao nos dados, sem alterar nada."""
    if not _e_xlsx(journey.source_path):
        return []
    argumentos = {"sheet": journey.sheet, "header_row": journey.header_row or 1}
    try:
        return [
            *date_format_notes(journey.source_path, **argumentos),
            *text_number_notes(journey.source_path, **argumentos),
        ]
    except (OSError, ValueError, KeyError):  # pragma: no cover - arquivo ilegivel
        return []


def _papeis_payload(journey: jobs.Journey) -> dict[str, Any]:
    """
    Sugestao de papeis das colunas — para a pessoa CONFIRMAR, nunca aplicar.

    Se nao houver dimensao e medida confiaveis, `offerable` sai False e a
    interface nem oferece o resumo: melhor nenhum indicador do que um
    numero com cara de verdade.
    """
    frame = _ler_frame(journey)
    if frame is None:
        return {"roles": [], "offerable": False, "suggestion": {}}

    sugestoes = suggest_roles(frame, journey.analysis.get("columns") or [])
    proposta = default_request(sugestoes)
    return {
        "roles": [
            {
                "coluna": s.column,
                "papel": s.role,
                "confianca": round(s.confidence, 2),
                "motivo": s.reason,
            }
            for s in sugestoes
        ],
        "offerable": summary_is_offerable(sugestoes),
        "suggestion": {
            "valor": proposta.value_column,
            "categoria": proposta.category_column,
            "data": proposta.date_column,
        },
    }


def _analysis_payload(token: str, journey: jobs.Journey) -> dict[str, Any]:
    """
    Resposta das etapas de analise.

    So dados estruturados: nada e derivado de stdout, e nenhum caminho do
    servidor entra aqui. O nome do arquivo vem do proprio payload do
    relatorio, que ja guarda apenas o nome.
    """
    return {
        "token": token,
        "status": journey.status,
        "needs_choice": bool(journey.ambiguities),
        "analysis": journey.analysis,
        "preview": journey.preview,
        "ambiguities": journey.ambiguities,
        "selected_sheet": journey.sheet,
        "header_row": journey.header_row,
        "schema_suggestion_available": (
            journey.status in {"analysis_ready", "schema_ready", "validating"}
        ),
        # Linhas 100% identicas encontradas na leitura. A verificacao e
        # SEMPRE feita (nao depende de schema nem de opcao): este numero so
        # antecipa na tela o que a execucao vai detalhar.
        "duplicate_rows": _duplicate_rows_found(journey),
        **_diagnostico_estendido(journey),
        "column_roles": _papeis_payload(journey),
    }


def _ambiguities_as_dicts(outcome: AnalysisOutcome) -> list[dict[str, Any]]:
    return [
        {
            "kind": a.kind,
            "confidence": a.confidence,
            "sheet_options": [
                {"name": o.name, "score": o.score, "rows": o.rows, "cols": o.cols}
                for o in a.sheet_options
            ],
            "header_options": list(a.header_options),
        }
        for a in outcome.ambiguities
    ]


def _apply_outcome(job: jobs.Job, journey: jobs.Journey, outcome: AnalysisOutcome) -> None:
    """
    Grava o resultado de uma analise na jornada.

    Uma recusa por "varias abas parecem tabela" e RECUPERAVEL: vira
    `needs_selection`, nao `rejected_file`, porque falta apenas uma escolha.
    Ver o servico da 1.8B-1.
    """
    journey.ambiguities = _ambiguities_as_dicts(outcome)
    journey.sheet_options = [o["name"] for a in journey.ambiguities for o in a["sheet_options"]]
    journey.header_options = [n for a in journey.ambiguities for n in a["header_options"]]

    if outcome.ambiguities:
        journey.status = "needs_selection"
        journey.rejection = None
        _descartar_sugestao(job)
        return

    if not outcome.ok:
        journey.status = "rejected_file"
        journey.rejection = outcome.rejection
        journey.analysis = {}
        _descartar_sugestao(job)
        return

    journey.status = "analysis_ready"
    journey.rejection = None
    journey.analysis = outcome.report
    journey.preview = outcome.preview
    journey.sheet = outcome.selected_sheet
    journey.header_row = outcome.header_row

    # O schema sugerido vai para out/ porque o visitante pode querer baixa-lo
    # e editar. Ele NAO e o schema efetivo: e uma sugestao, e so passa a valer
    # se for confirmado na etapa seguinte.
    sugerido = job.workspace / "out" / "schema_sugerido.yaml"
    sugerido.parent.mkdir(parents=True, exist_ok=True)
    sugerido.write_text(outcome.schema_suggestion, encoding="utf-8")


def _descartar_sugestao(job: jobs.Job) -> None:
    """Remove o schema sugerido: ele descrevia uma leitura que nao vale mais."""
    (job.workspace / "out" / "schema_sugerido.yaml").unlink(missing_ok=True)


def _invalidar_schema_confirmado(job: jobs.Job, journey: jobs.Journey) -> None:
    """
    Descarta o schema confirmado quando a leitura muda.

    Um schema confirmado para a aba A descreve as colunas de A. Se a pessoa
    volta e escolhe a aba B, aquele schema deixa de fazer sentido — mante-lo
    validaria B com o contrato de A, que e o pior erro possivel aqui: um
    resultado que parece legitimo e nao e. Por isso a validacao volta a exigir
    confirmacao explicita.
    """
    if journey.schema_path is not None:
        journey.schema_path.unlink(missing_ok=True)
    journey.schema_path = None
    journey.schema_origin = None


def _run_analysis(job: jobs.Job, journey: jobs.Journey) -> None:
    """Roda o servico da 1.8B-1 com as escolhas atuais da jornada."""
    outcome = analyze_spreadsheet(
        journey.source_path, sheet=journey.sheet, header_row=journey.header_row
    )
    _apply_outcome(job, journey, outcome)


# ==========================================================================
# 1. Analisar
# ==========================================================================


def _profile_payload(profile_id: str) -> dict[str, Any]:
    """
    Metadados de um perfil, no formato que a interface precisa.

    So o que e seguro e util: id, titulo, versao, resumo e os campos
    conceituais com sua documentacao. Nada de caminho de arquivo, YAML bruto
    ou objeto interno — a interface nao precisa disso e expor amplia a
    superficie a toa.
    """
    perfil = load_profile(profile_id)
    requeridos = set(perfil.required_fields)
    return {
        "id": perfil.id,
        "title": perfil.title,
        "version": perfil.version,
        "summary": perfil.summary.strip(),
        "fields": [
            {
                "name": campo,
                "required": campo in requeridos,
                "doc": (perfil.fields[campo].doc if campo in perfil.fields else ""),
            }
            for campo in perfil.concept_fields
        ],
    }


@router.get("/profiles")
async def profiles() -> JSONResponse:
    """
    Perfis disponiveis no pacote instalado.

    Endpoint PUBLICO e somente leitura de proposito: o catalogo e conteudo do
    proprio pacote, igual ao `/api/catalog` dos cards — nao depende de arquivo
    de ninguem, nao toca workspace e nao revela nada de nenhuma sessao. Exigir
    token aqui obrigaria a interface a subir um arquivo so para saber o que
    existe.
    """
    itens = []
    for pid in list_profiles():
        try:
            itens.append(_profile_payload(pid))
        except ProfileError:  # pragma: no cover - recurso corrompido no pacote
            continue
    return JSONResponse({"profiles": itens})


@router.get("/profiles/{profile_id}")
async def profile_detail(profile_id: str) -> JSONResponse:
    """Metadados de um perfil. O id e validado pelo catalogo do nucleo."""
    try:
        return JSONResponse(_profile_payload(profile_id))
    except ProfileError as exc:
        # `load_profile` recusa id com barra, `..` ou fora do padrao: a
        # validacao de nome vive no nucleo, nao duplicada aqui.
        return _error(_HTTP_NOT_FOUND, str(exc), code="profile_not_found")


@router.post("/analyze")
async def analyze(  # noqa: PLR0911 - cada recusa tem sua propria mensagem e codigo
    request: Request,
    files: list[UploadFile] = File(default=[]),  # noqa: B008
    use_sample: bool = False,
) -> JSONResponse:
    """
    Recebe o arquivo (ou usa o exemplo) e devolve o diagnostico estrutural.

    Exemplo e upload seguem o MESMO caminho a partir daqui: a unica diferenca
    e a origem do arquivo, exatamente como a etapa exige.
    """
    if not ratelimit.limiter.allow(ratelimit.client_ip(request)):
        return _error(_HTTP_TOO_MANY, "muitas requisicoes, aguarde um momento", code="rate_limit")
    # Sem checagem de concorrencia aqui: a analise roda EM PROCESSO e nao
    # ocupa slot de subprocesso. O teto de execucoes simultaneas vale no
    # /validate, que e quem dispara processo. O numero de workspaces
    # continua limitado por `engine.create_workspace()`.
    enviados = [f for f in files if f.filename]
    if use_sample and enviados:
        return _error(
            _HTTP_BAD_REQUEST,
            "escolha uma origem: o exemplo OU um arquivo seu, nao os dois",
            code="ambiguous_source",
        )
    if not use_sample and not enviados:
        return _error(_HTTP_BAD_REQUEST, "nenhum arquivo enviado", code="no_file")
    if len(enviados) > 1:
        # Salvar varios e usar so o primeiro faria a pessoa acreditar que
        # analisamos algo que nem abrimos.
        return _error(
            _HTTP_BAD_REQUEST,
            "envie um arquivo por vez",
            code="too_many_files",
        )

    try:
        token, workspace = engine.create_workspace()
    except engine.WorkspaceFull:
        return _error(_HTTP_BUSY, "servidor ocupado, tente em instantes", code="busy")

    try:
        if use_sample:
            entradas = samples.copy_sample_to(_SAMPLE_AUTOMATION, workspace / "in")
        else:
            entradas = await uploads.save_uploads(
                enviados, workspace / "in", allowed_exts=_ALLOWED_EXTS
            )
    except uploads.UploadError as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        return _error(exc.status_code, exc.detail, code="invalid_upload")

    if not entradas:
        shutil.rmtree(workspace, ignore_errors=True)
        return _error(_HTTP_BAD_REQUEST, "nenhum arquivo utilizavel", code="no_file")

    job = jobs.create(token, _VALIDATE_AUTOMATION, workspace)
    job.status = "analyzing"
    journey = jobs.Journey(status="analyzing", source_path=entradas[0])
    job.journey = journey

    _run_analysis(job, journey)

    if journey.status == "rejected_file":
        return JSONResponse(
            {
                "token": token,
                "status": journey.status,
                "needs_choice": False,
                "detail": journey.rejection,
                "code": "rejected_file",
            },
            status_code=200,
        )

    return JSONResponse(_analysis_payload(token, journey))


# ==========================================================================
# 2. Selecao de aba / cabecalho
# ==========================================================================


@router.post("/{token}/selection")
async def selection(
    token: str,
    sheet: str | None = Form(default=None),
    header_row: int | None = Form(default=None),
) -> JSONResponse:
    """
    Registra a escolha do visitante e reanalisa com ela.

    A aba e conferida contra as candidatas que a ANALISE ofereceu — nao
    aceitamos um nome qualquer, nem caminho, nem expressao. O cabecalho tem
    de ser inteiro >= 1 (a mesma numeracao do Excel).
    """
    achado = _journey_of(token)
    if isinstance(achado, JSONResponse):
        return achado
    job, journey = achado

    if sheet is None and header_row is None:
        return _error(
            _HTTP_BAD_REQUEST, "informe a aba ou a linha do cabecalho", code="no_selection"
        )

    if sheet is not None:
        escolha = sheet.strip()
        if not escolha:
            return _error(_HTTP_BAD_REQUEST, "a aba veio vazia", code="invalid_sheet")
        if journey.sheet_options and escolha not in journey.sheet_options:
            return _error(
                _HTTP_BAD_REQUEST,
                f"a aba '{escolha}' nao esta entre as opcoes desta analise",
                code="invalid_sheet",
            )
        journey.sheet = escolha

    if header_row is not None:
        if header_row < 1:
            return _error(
                _HTTP_BAD_REQUEST,
                "a linha do cabecalho comeca em 1 (a mesma numeracao do Excel)",
                code="invalid_header_row",
            )
        journey.header_row = header_row

    # A leitura mudou: o que foi confirmado sobre a leitura anterior cai.
    _invalidar_schema_confirmado(job, journey)
    _run_analysis(job, journey)
    return JSONResponse(_analysis_payload(token, journey))


# ==========================================================================
# 3. Schema (sugerido ou proprio)
# ==========================================================================


def _schema_summary(caminho: Path) -> dict[str, Any]:
    """
    Resumo das regras, para o visitante revisar ANTES de executar.

    Sai do modelo Pydantic real (`load_schema`), nao de leitura de texto.
    `generated_from` aparece so quando existe: schema escrito a mao nao
    ganha procedencia inventada.
    """
    schema = load_schema(caminho)
    resumo: dict[str, Any] = {
        "columns": [
            {
                "name": c.name,
                "type": c.type,
                "required": c.required,
                "format": c.format,
                "validator_br": c.validator_br,
                "unique": c.unique,
            }
            for c in schema.columns
        ],
        "detect_duplicate_rows": schema.detect_duplicate_rows,
        "group_keys": [{"name": k.name, "columns": list(k.columns)} for k in schema.group_keys],
        "group_checks": [
            {
                "name": g.name,
                "group_key": g.group_key,
                "consistent": list(g.consistent),
                "severity": g.severity,
            }
            for g in schema.group_checks
        ],
        "derived_checks": [
            {
                "name": d.name,
                "target": d.target,
                "expression": d.expression,
                "tolerance": str(d.tolerance),
                "severity": d.severity,
            }
            for d in schema.derived_checks
        ],
    }
    if schema.generated_from is not None:
        resumo["generated_from"] = schema.generated_from.model_dump(exclude_none=True)
    return resumo


@router.post("/{token}/schema")
async def choose_schema(  # noqa: PLR0911, PLR0912 - cada recusa tem mensagem propria
    token: str,
    source: str = Form(default="suggested"),
    profile_id: str = Form(default=""),
    mapping: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),  # noqa: B008
) -> JSONResponse:
    """
    Confirma o schema da validacao: o sugerido pela analise ou um YAML proprio.

    O YAML enviado e conteudo NAO confiavel: tem teto de tamanho, e carregado
    com `yaml.safe_load` (sem tags executaveis, sem include, sem referencia
    externa) e validado pelo modelo Pydantic do projeto. Nenhum caminho do
    cliente e aceito — o arquivo entra por upload e fica no workspace.
    """
    achado = _journey_of(token)
    if isinstance(achado, JSONResponse):
        return achado
    job, journey = achado

    if journey.status not in {"analysis_ready", "schema_ready"}:
        return _error(
            _HTTP_BAD_REQUEST,
            "conclua a analise antes de escolher o schema",
            code="analysis_pending",
        )

    destino = job.workspace / "config" / "schema_confirmado.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Escreve num temporario, VALIDA, e so entao substitui. Politica escolhida:
    # um schema invalido NAO derruba o anterior. A alternativa (limpar antes de
    # tentar) deixaria a pessoa sem nada por causa de um erro de digitacao, e
    # sem meio de voltar — o arquivo dela ja foi embora do formulario.
    parcial = destino.with_suffix(".parcial")

    enviados = [f for f in files if f.filename]

    if source == "suggested":
        if enviados:
            return _error(
                _HTTP_BAD_REQUEST,
                "voce escolheu o schema sugerido, mas tambem enviou um arquivo; "
                "use source=uploaded para enviar o seu",
                code="unexpected_file",
            )
        sugerido = job.workspace / "out" / "schema_sugerido.yaml"
        if not sugerido.is_file():
            return _error(
                _HTTP_BAD_REQUEST, "nao ha schema sugerido nesta sessao", code="no_suggestion"
            )
        parcial.write_text(sugerido.read_text(encoding="utf-8"), encoding="utf-8")
        origem = "suggested"
    elif source == "profile":
        erro = _escrever_schema_de_perfil(journey, profile_id, mapping, parcial)
        if erro is not None:
            parcial.unlink(missing_ok=True)
            return erro
        origem = "profile"
    elif source == "uploaded":
        if not enviados:
            return _error(_HTTP_BAD_REQUEST, "nenhum schema enviado", code="no_file")
        if len(enviados) > 1:
            return _error(_HTTP_BAD_REQUEST, "envie um schema por vez", code="too_many_files")
        nome = enviados[0].filename or ""
        if Path(nome).suffix.lower() not in _SCHEMA_EXTS:
            return _error(
                _HTTP_UNSUPPORTED_MEDIA,
                f"o schema precisa ser {' ou '.join(_SCHEMA_EXTS)}",
                code="invalid_extension",
            )
        bruto = await enviados[0].read(_MAX_SCHEMA_BYTES + 1)
        if len(bruto) > _MAX_SCHEMA_BYTES:
            return _error(
                _HTTP_PAYLOAD_TOO_LARGE,
                f"o schema excede {_MAX_SCHEMA_BYTES // 1024} KB",
                code="schema_too_large",
            )
        try:
            texto = bruto.decode("utf-8")
        except UnicodeDecodeError:
            return _error(
                _HTTP_BAD_REQUEST, "o schema precisa estar em UTF-8", code="invalid_schema"
            )
        parcial.write_text(texto, encoding="utf-8")
        origem = "uploaded"
    else:
        return _error(
            _HTTP_BAD_REQUEST,
            "origem do schema invalida: use 'suggested', 'profile' ou 'uploaded'",
            code="invalid_source",
        )

    try:
        resumo = _schema_summary(parcial)
    except (AutoTarefasError, yaml.YAMLError, ValueError, OSError) as exc:
        parcial.unlink(missing_ok=True)
        # A mensagem do loader e escrita para pessoas; nao vaza traceback nem
        # caminho. Cortamos o tamanho para nao devolver um dump enorme.
        return _error(
            _HTTP_BAD_REQUEST,
            f"schema invalido: {str(exc).splitlines()[0][:300]}",
            code="invalid_schema",
        )

    # Validou: agora sim substitui o anterior, de uma vez.
    parcial.replace(destino)
    journey.schema_path = destino
    journey.schema_origin = origem
    journey.status = "schema_ready"
    corpo: dict[str, Any] = {
        "token": token,
        "status": journey.status,
        "schema_origin": journey.schema_origin,
        "summary": resumo,
    }
    if journey.profile_id:
        corpo["profile"] = {
            "id": journey.profile_id,
            "version": journey.profile_version,
            "mapping": dict(journey.profile_mapping),
            "omitted": list(journey.profile_omitted),
        }
    return JSONResponse(corpo)


# ==========================================================================
# 4. Validar
# ==========================================================================


def _confirmar_schema_sugerido(job: jobs.Job, journey: jobs.Journey) -> JSONResponse | None:
    """
    Adota o schema sugerido pela analise, sem pedir nada a pessoa.

    O sugerido descreve apenas a ESTRUTURA OBSERVADA (nomes e tipos): nao
    inventa regra de negocio, entao adota-lo por padrao nao decide nada
    pelo usuario. Quem tem regras proprias envia um YAML na opcao avancada.
    """
    sugerido = job.workspace / "out" / "schema_sugerido.yaml"
    if not sugerido.is_file():
        return _error(
            _HTTP_BAD_REQUEST,
            "conclua a analise antes de executar",
            code="analysis_pending",
        )
    destino = job.workspace / "config" / "schema_confirmado.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(sugerido.read_text(encoding="utf-8"), encoding="utf-8")
    journey.schema_path = destino
    journey.schema_origin = "suggested"
    journey.status = "schema_ready"
    return None


def _pos_processar(job: jobs.Job, journey: jobs.Journey) -> None:
    """
    Gera os artefatos PRINCIPAIS depois que a validacao termina.

    A validacao roda em subprocesso isolado e produz as evidencias tecnicas.
    Aqui, em processo (so openpyxl sobre arquivos do proprio workspace),
    montamos o que o usuario final realmente quer:

        planilha_organizada.xlsx   so quando algo foi confirmado E aplicado
        relatorio_analise.xlsx     sempre — e o laudo da execucao

    Falha aqui NAO derruba a execucao: as evidencias tecnicas ja existem, e
    a jornada continua util. O motivo vai para o relatorio como observacao.
    """
    saida = job.workspace / "out"
    relatorio_json = saida / "validacao_report.json"
    dados: dict[str, Any] = {}
    if relatorio_json.is_file():
        try:
            dados = json.loads(relatorio_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # pragma: no cover - arquivo do proprio processo
            dados = {}

    observacoes: list[str] = []
    # Os indicadores vem primeiro: a aba de Dashboard da planilha organizada e
    # desenhada a partir deles.
    indicadores = _calcular_indicadores(journey)
    organizacao = None
    if journey.organize and _e_xlsx(journey.source_path):
        pedido = (
            SortRequest(journey.sort_column, ascending=not journey.sort_desc)
            if journey.sort_column
            else None
        )
        try:
            organizacao = organize_workbook(
                journey.source_path,
                saida / ORGANIZED_XLSX_NAME,
                sheet=journey.sheet,
                header_row=journey.header_row or 1,
                sort=pedido,
                value_changes=dados.get("cleaning_changes", []),
                dashboard=indicadores if journey.dashboard else (),
                dashboard_request=IndicatorRequest(
                    value_column=journey.indicator_request[0],
                    category_column=journey.indicator_request[1],
                    date_column=journey.indicator_request[2],
                ),
            )
        except (OSError, ValueError) as exc:  # pragma: no cover - defesa
            observacoes.append(f"a versão organizada não pôde ser gerada: {exc}")
    elif journey.organize:
        observacoes.append(
            "arquivos CSV não têm apresentação para organizar; os dados tratados "
            "seguem no pacote técnico"
        )

    if journey.dashboard and not indicadores:
        observacoes.append(
            "a aba de Dashboard não foi criada: nenhuma coluna de valor foi confirmada"
        )

    auditoria = None
    if _e_xlsx(journey.source_path):
        try:
            auditoria = audit_presentation(
                journey.source_path, sheet=journey.sheet, header_row=journey.header_row or 1
            )
            # As mesmas observacoes que a tela mostrou antes de executar
            # entram no relatorio, para quem so recebe o arquivo.
            observacoes.extend(_observacoes_dos_dados(journey))
        except (OSError, ValueError):  # pragma: no cover
            auditoria = None

    entrada = ReportInput(
        source_name=journey.source_path.name,
        sheet=journey.sheet or "",
        rows=int(dados.get("rows", 0)),
        columns=len(dados.get("columns", []) or []),
        audit=auditoria,
        sheets=survey_sheets(journey.source_path) if _e_xlsx(journey.source_path) else (),
        issues=dados.get("issues", []),
        cleaning_changes=dados.get("cleaning_changes", []),
        review_rows=build_review_rows(_ResultadoLido(dados)),
        organize=organizacao,
        indicators=indicadores,
        notes=observacoes,
    )
    try:
        write_analysis_report(saida / ANALYSIS_REPORT_NAME, entrada)
    except (OSError, ValueError) as exc:  # pragma: no cover - defesa
        logger.warning(f"relatorio de analise nao gerado: {exc}")


@dataclass(frozen=True, slots=True)
class _ResultadoLido:
    """Adaptador: o `build_review_rows` do nucleo só precisa de `.data`."""

    data: dict[str, Any]


def _calcular_indicadores(journey: jobs.Journey) -> tuple[Any, ...]:
    """Indicadores SO com os papeis confirmados pela pessoa."""
    valor, categoria, data = journey.indicator_request
    if not valor:
        return ()
    frame = _ler_frame(journey)
    if frame is None:  # pragma: no cover - arquivo ja validado antes
        return ()
    return build_indicators(
        frame,
        IndicatorRequest(value_column=valor, category_column=categoria, date_column=data),
    )


async def _safe_journey_run(
    job: jobs.Job, journey: jobs.Journey, options: recipes.JourneyOptions
) -> None:
    """Executa a validacao protegendo o registry de excecao inesperada."""
    try:
        await engine.run_streaming(_VALIDATE_AUTOMATION, [journey.source_path], job, options)
    except Exception:  # noqa: BLE001
        job.status = "error"
        journey.status = "technical_failure"
        job.result = engine.RunResult(
            token=job.token,
            outcome="error",
            exit_code=-1,
            duration_ms=0,
            stdout="falha ao executar a validacao",
            artifacts=[],
        )
        job.queue.put_nowait(None)
        return

    resultado = job.result
    if resultado is None:  # pragma: no cover - run_streaming sempre preenche
        journey.status = "technical_failure"
        return
    journey.status = _journey_status_for(resultado.outcome, resultado.exit_code)

    # Os artefatos principais sao montados DEPOIS da execucao, sobre o que
    # ela produziu. Uma falha aqui nao pode derrubar o que ja deu certo.
    try:
        _pos_processar(job, journey)
    except Exception as exc:  # noqa: BLE001 - defesa do registry
        logger.warning(f"pos-processamento da jornada falhou: {exc}")
    else:
        job.result = engine.refresh_artifacts(job)


def _journey_status_for(outcome: str, exit_code: int) -> jobs.JourneyStatus:
    """
    Traduz o resultado da execucao em estado da jornada.

    A distincao que importa: exit 1 e "a validacao terminou e achou problemas
    nos dados" (com evidencias completas), enquanto exit 2 e "voce pediu algo
    invalido" — configuracao, nao dados. Nenhum dos dois e falha tecnica.
    """
    if outcome == "timeout":
        return "timed_out"
    if exit_code == 0:
        return "completed"
    if exit_code == 1:
        return "completed_with_issues"
    if exit_code == 2:  # noqa: PLR2004 - contrato de uso/configuracao do validate
        return "invalid_configuration"
    return "technical_failure"


def _escrever_schema_de_perfil(  # noqa: PLR0911 - cada recusa tem mensagem propria
    journey: jobs.Journey,
    profile_id: str,
    mapping_bruto: str,
    destino: Path,
) -> JSONResponse | None:
    """
    Gera o schema a partir de um perfil e do mapeamento confirmado.

    Toda a regra vive no nucleo (`export_schema`): validacao do id, do campo
    conceitual, da coluna contra as colunas REAIS, recusa de duas associacoes
    para a mesma coluna, omissao de opcionais e `generated_from`. Aqui so
    traduzimos o payload e os erros.

    As colunas conferidas sao as da analise ATUAL — a aba e o cabecalho que o
    visitante confirmou. Assim um mapeamento nao sobrevive a troca de aba.

    Returns:
        None em caso de sucesso; a resposta de erro caso contrario.
    """
    if not profile_id.strip():
        return _error(_HTTP_BAD_REQUEST, "informe o perfil", code="no_profile")

    try:
        perfil = load_profile(profile_id.strip())
    except ProfileError as exc:
        return _error(_HTTP_NOT_FOUND, str(exc), code="profile_not_found")

    try:
        pedido = json.loads(mapping_bruto or "{}")
    except json.JSONDecodeError:
        return _error(_HTTP_BAD_REQUEST, "mapeamento invalido", code="invalid_mapping")
    if not isinstance(pedido, dict):
        return _error(_HTTP_BAD_REQUEST, "mapeamento invalido", code="invalid_mapping")

    # So pares texto->texto entram; qualquer outra coisa e descartada antes de
    # chegar ao nucleo.
    escolhas = {
        str(k): str(v).strip()
        for k, v in pedido.items()
        if isinstance(k, str) and isinstance(v, str) and str(v).strip()
    }

    colunas = _colunas_da_analise(journey)
    try:
        resultado = export_schema(perfil, escolhas, available_columns=colunas)
    except MappingError as exc:
        return _error(_HTTP_BAD_REQUEST, str(exc), code="invalid_mapping")

    if not resultado.is_complete:
        faltando = ", ".join(resultado.unmapped_required)
        return _error(
            _HTTP_BAD_REQUEST,
            f"mapeie os campos obrigatorios antes de continuar: {faltando}",
            code="incomplete_mapping",
        )

    destino.write_text(resultado.yaml_text, encoding="utf-8")
    journey.profile_id = perfil.id
    journey.profile_version = perfil.version
    journey.profile_mapping = dict(resultado.mapping_applied)
    journey.profile_omitted = list(resultado.unmapped_optional)
    return None


def _colunas_da_analise(journey: jobs.Journey) -> list[str]:
    """Colunas da leitura ATUAL (aba e cabecalho confirmados)."""
    colunas = journey.analysis.get("columns") or []
    return [str(c["name"]) for c in colunas if isinstance(c, dict) and c.get("name")]


@router.post("/{token}/validate")
async def validate(  # noqa: PLR0913 - um campo tipado por confirmacao da tela
    token: str,
    strict_warnings: bool = Form(default=False),
    max_issues: int | None = Form(default=None),
    apply_cleaning: bool = Form(default=False),
    organize: bool = Form(default=False),
    sort_column: str = Form(default=""),
    sort_desc: bool = Form(default=False),
    indicator_value: str = Form(default=""),
    indicator_category: str = Form(default=""),
    indicator_date: str = Form(default=""),
    dashboard: bool = Form(default=False),
) -> JSONResponse:
    """
    Executa a validacao com as escolhas CONFIRMADAS e gera as evidencias.

    Roda pelo mesmo subprocesso isolado da 1.8A (sem shell, argv por
    allowlist), com o arquivo interno do workspace, o schema confirmado e as
    escolhas de aba/cabecalho que o visitante viu na analise. Nada de argv
    vindo do navegador: `strict_warnings`, `max_issues` e `apply_cleaning`
    sao campos tipados que o servidor traduz em opcao.

    Cada opcao e uma CONFIRMACAO explicita, e todas comecam desligadas:

        apply_cleaning     normaliza o que e seguro (espacos, caixa, formato)
        organize           gera a versao com apresentacao profissional
        sort_column/desc   reordena as linhas (sem isto, a ordem e a original)
        dashboard          aba de painel na planilha organizada (exige
                           indicator_value)
        indicator_*        papeis confirmados para o resumo (sem isto, nenhum
                           numero e somado e nenhum grafico e desenhado)

    A verificacao de linhas 100% repetidas NAO e opcional: ela sempre roda.

    Sem schema proprio, o servidor confirma sozinho o schema SUGERIDO pela
    analise — que so descreve a estrutura observada. E o que permite a
    jornada ir do diagnostico direto para a revisao, sem exigir que a pessoa
    entenda schema.

    O acompanhamento continua nos endpoints existentes: `/api/stream/{token}`,
    `/api/result/{token}` e `/api/download/{token}/{nome}`.
    """
    achado = _journey_of(token)
    if isinstance(achado, JSONResponse):
        return achado
    job, journey = achado

    if journey.status == "validating":
        # Dois cliques no botao nao podem virar dois subprocessos escrevendo
        # no mesmo out/ — o pacote sairia com arquivos de duas execucoes.
        return _error(
            _HTTP_CONFLICT,
            "esta validacao ja esta em andamento",
            code="already_validating",
        )
    if journey.schema_path is None:
        # Caminho PADRAO do card: sem schema proprio, vale o sugerido pela
        # analise. Ninguem precisa entender schema para organizar a planilha.
        erro = _confirmar_schema_sugerido(job, journey)
        if erro is not None:
            return erro
    if jobs.active_count() >= settings.max_concurrent_runs:
        return _error(_HTTP_BUSY, "servidor ocupado, tente em instantes", code="busy")
    if max_issues is not None and max_issues < 1:
        return _error(
            _HTTP_BAD_REQUEST, "o limite de problemas comeca em 1", code="invalid_max_issues"
        )

    # Linhas 100% repetidas sao SEMPRE verificadas — nao dependem de schema,
    # perfil nem opcao escondida. Nenhuma e removida: viram aviso com o
    # numero da linha e o par, para uma pessoa decidir.
    if journey.schema_path is not None:
        _ativar_deteccao_de_duplicadas(journey.schema_path)

    journey.organize = organize
    journey.sort_column = sort_column.strip()
    journey.sort_desc = sort_desc
    journey.dashboard = dashboard
    journey.indicator_request = (
        indicator_value.strip(),
        indicator_category.strip(),
        indicator_date.strip(),
    )

    options = recipes.JourneyOptions(
        schema_path=journey.schema_path,
        sheet=journey.sheet if journey.source_path.suffix.lower() != ".csv" else None,
        header_row=journey.header_row,
        strict_warnings=strict_warnings,
        max_issues=max_issues,
        apply_cleaning=apply_cleaning,
    )
    journey.apply_cleaning = apply_cleaning

    journey.status = "validating"
    job.status = "running"
    tarefa = asyncio.create_task(_safe_journey_run(job, journey, options))
    _background.add(tarefa)
    tarefa.add_done_callback(_background.discard)

    return JSONResponse(
        {
            "token": token,
            "status": journey.status,
            "stream_url": f"/api/stream/{token}",
            "result_url": f"/api/result/{token}",
        }
    )


@router.get("/{token}/original", response_model=None)
async def original(token: str) -> FileResponse | JSONResponse:
    """
    Devolve o arquivo que a pessoa enviou, exatamente como enviou.

    E o primeiro item da area de downloads: ter o original ao lado da
    versao organizada e o que torna a comparacao possivel. O caminho e
    montado pelo SERVIDOR a partir do token da sessao — o cliente nunca
    informa caminho, entao nao ha superficie para path traversal, e uma
    sessao nao alcanca o arquivo de outra.
    """
    achado = _journey_of(token)
    if isinstance(achado, JSONResponse):
        return achado
    _, journey = achado

    origem = journey.source_path
    if not origem.is_file():  # pragma: no cover - expurgo entre a chamada e o disco
        return _error(
            _HTTP_NOT_FOUND, "arquivo desta sessao nao esta mais disponivel", code="expired"
        )
    return FileResponse(origem, filename=origem.name, media_type="application/octet-stream")


def pending_tasks() -> set[asyncio.Task[None]]:
    """Tarefas de validacao em andamento, para o shutdown aguardar/cancelar."""
    return set(_background)


__all__ = ["pending_tasks", "router"]
