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
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from autotarefas.core.exceptions import AutoTarefasError
from autotarefas.profiles import (
    MappingError,
    ProfileError,
    export_schema,
    list_profiles,
    load_profile,
)
from autotarefas.services import analyze_spreadsheet
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
async def validate(
    token: str,
    strict_warnings: bool = Form(default=False),
    max_issues: int | None = Form(default=None),
    apply_cleaning: bool = Form(default=False),
) -> JSONResponse:
    """
    Executa a validacao com as escolhas CONFIRMADAS e gera as evidencias.

    Roda pelo mesmo subprocesso isolado da 1.8A (sem shell, argv por
    allowlist), com o arquivo interno do workspace, o schema confirmado e as
    escolhas de aba/cabecalho que o visitante viu na analise. Nada de argv
    vindo do navegador: `strict_warnings`, `max_issues` e `apply_cleaning`
    sao campos tipados que o servidor traduz em opcao.

    `apply_cleaning` e a confirmacao das CORRECOES SEGURAS. Sem ela a jornada
    apenas audita; com ela, o nucleo normaliza o que e seguro (espacos, caixa,
    formato), registra cada mudanca no antes/depois e, para XLSX, entrega a
    `planilha_tratada.xlsx` com a apresentacao original preservada. O arquivo
    de entrada continua intocado nos dois casos.

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
    if journey.schema_path is None or journey.status != "schema_ready":
        return _error(
            _HTTP_BAD_REQUEST,
            "confirme o schema antes de validar",
            code="schema_pending",
        )
    if jobs.active_count() >= settings.max_concurrent_runs:
        return _error(_HTTP_BUSY, "servidor ocupado, tente em instantes", code="busy")
    if max_issues is not None and max_issues < 1:
        return _error(
            _HTTP_BAD_REQUEST, "o limite de problemas comeca em 1", code="invalid_max_issues"
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


def pending_tasks() -> set[asyncio.Task[None]]:
    """Tarefas de validacao em andamento, para o shutdown aguardar/cancelar."""
    return set(_background)


__all__ = ["pending_tasks", "router"]
