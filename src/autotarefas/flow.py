"""
Configuracao de fluxo reutilizavel (RF-CORE-006 recorte + RF-REC-004).

A conferencia mensal e sempre a mesma sequencia de comandos, com os mesmos
parametros. Digitar tudo de novo todo mes e onde o erro entra. Este modulo
troca isso por um arquivo::

    nome: Conferencia mensal
    passos:
      - tipo: comparar
        a: sistema.xlsx
        b: planilha.xlsx
        chave: [codigo]
        tolerancia: ["valor=0,01"]

      - tipo: conciliar
        a: sistema.xlsx
        b: planilha.xlsx
        chave: [codigo]
        principal: a
        atualizar: [valor]

      - tipo: corrigir
        arquivo: planilha.xlsx
        regras: regras.yaml

Tres decisoes que valem mais que o formato em si:

1. **Nenhum segredo no arquivo.** Chave de API, token e senha sao
   recusados na leitura, com a mensagem dizendo qual variavel de ambiente
   usar. O fluxo guarda o QUE fazer, nunca a credencial.

2. **Precedencia CLI > configuracao > padrao.** O que voce digita agora
   vence o que estava escrito no arquivo (hoje: `--out-dir`).

3. **Cada passo grava em seu proprio diretorio** (`out/1-comparar/`), para
   que o resultado de um passo nao apague o do outro.

O executor nao reimplementa nada: ele chama as mesmas tasks dos comandos
`comparar`, `conciliar`, `transferir` e `corrigir`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from autotarefas.core.exceptions import ConfigError

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Tipos de passo aceitos no recorte V1.
StepKind = Literal["comparar", "conciliar", "transferir", "corrigir"]

#: Nomes de chave que denunciam segredo embutido no arquivo de fluxo.
SECRET_HINTS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "token",
    "bearer",
    "senha",
    "password",
    "secret",
    "credencial",
)


class FlowStep(BaseModel):
    """Um passo do fluxo: o tipo e os parametros daquele comando."""

    model_config = ConfigDict(extra="allow")

    tipo: StepKind
    nome: str = ""

    def params(self) -> dict[str, Any]:
        """Os parametros do passo (tudo que nao e metadado)."""
        return dict(self.__pydantic_extra__ or {})


class FlowConfig(BaseModel):
    """O fluxo inteiro, validado."""

    model_config = ConfigDict(extra="forbid")

    nome: str = "Fluxo"
    out_dir: Path | None = None
    passos: list[FlowStep] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class StepResult:
    """O que aconteceu em um passo."""

    index: int
    kind: str
    name: str
    ok: bool
    summary: str = ""
    artifacts: tuple[Path, ...] = ()
    error: str = ""


@dataclass(frozen=True, slots=True)
class FlowResult:
    """O resultado do fluxo inteiro."""

    config_name: str
    steps: tuple[StepResult, ...] = ()
    out_dir: Path | None = None
    dry_run: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "passos": len(self.steps),
            "concluidos": sum(1 for s in self.steps if s.ok),
            "falhos": sum(1 for s in self.steps if not s.ok),
        }


# ============================================================
# Leitura
# ============================================================


def _reject_secrets(node: Any, caminho: str = "") -> None:
    """
    Recusa segredo embutido, em qualquer profundidade do arquivo.

    O fluxo circula por e-mail e por repositorio: uma chave de API aqui
    dentro vaza junto. A mensagem diz o que fazer no lugar.
    """
    if isinstance(node, dict):
        for chave, valor in node.items():
            nome = str(chave).lower()
            if any(pista in nome for pista in SECRET_HINTS):
                onde = f"{caminho}.{chave}" if caminho else str(chave)
                msg = (
                    f"segredo embutido no fluxo em '{onde}'. Configure a credencial por "
                    "variavel de ambiente (arquivo .env ou ambiente do sistema) e deixe "
                    "o fluxo apenas com o que fazer."
                )
                raise ConfigError(msg)
            _reject_secrets(valor, f"{caminho}.{chave}" if caminho else str(chave))
    elif isinstance(node, list):
        for indice, item in enumerate(node):
            _reject_secrets(item, f"{caminho}[{indice}]")


def load_flow(path: Path) -> FlowConfig:
    """
    Le e valida o arquivo de fluxo.

    Raises:
        ConfigError: arquivo ilegivel, estrutura invalida (pydantic) ou
            segredo embutido.
    """
    try:
        conteudo = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        msg = f"nao foi possivel ler o fluxo {path.name}: {exc}"
        raise ConfigError(msg) from exc

    if not isinstance(conteudo, dict):
        msg = f"{path.name}: o fluxo precisa ser um mapa com a chave 'passos'."
        raise ConfigError(msg)

    _reject_secrets(conteudo)

    try:
        return FlowConfig.model_validate(conteudo)
    except ValidationError as exc:
        detalhes = "; ".join(
            f"{'.'.join(str(p) for p in erro['loc'])}: {erro['msg']}" for erro in exc.errors()
        )
        msg = f"{path.name}: fluxo invalido — {detalhes}"
        raise ConfigError(msg) from exc


# ============================================================
# Execucao
# ============================================================


def _resolve(base: Path, valor: Any) -> Path:
    """Caminho do passo, relativo ao diretorio do proprio arquivo de fluxo."""
    caminho = Path(str(valor))
    return caminho if caminho.is_absolute() else (base / caminho)


def _as_list(valor: Any) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        return [str(item) for item in valor]
    return [str(valor)]


def _step_dir(out_dir: Path | None, index: int, kind: str) -> Path | None:
    return None if out_dir is None else out_dir / f"{index}-{kind}"


def _run_comparar(
    params: dict[str, Any], base: Path, destino: Path | None
) -> tuple[str, list[Path]]:
    from autotarefas.reconcile.artifacts import generate_summary, write_comparison_artifacts
    from autotarefas.reconcile.task import ComparisonTask, SourceSelection
    from autotarefas.reconcile.tolerance import parse_tolerances

    task = ComparisonTask(
        SourceSelection(path=_resolve(base, params["a"])),
        SourceSelection(path=_resolve(base, params["b"])),
        key_columns=_as_list(params.get("chave")),
        columns=_as_list(params.get("colunas")) or None,
        normalizations=_as_list(params.get("normalizar")),
        tolerances=parse_tolerances(_as_list(params.get("tolerancia"))),
    )
    resultado = task.run()
    if resultado.is_failure or task.comparison is None:
        raise ConfigError(str(resultado.error_message))

    artefatos: list[Path] = []
    if destino is not None and task.table_a is not None and task.table_b is not None:
        artefatos = list(
            write_comparison_artifacts(task.comparison, task.table_a, task.table_b, destino)
        )
    return generate_summary(task.comparison, max_rows=5), artefatos


def _run_conciliar(
    params: dict[str, Any], base: Path, destino: Path | None
) -> tuple[str, list[Path]]:
    from autotarefas.reconcile.merge import ReconcilePolicy
    from autotarefas.reconcile.merge_artifacts import (
        generate_summary,
        write_reconciliation_artifacts,
    )
    from autotarefas.reconcile.task import ReconciliationTask, SourceSelection
    from autotarefas.reconcile.tolerance import parse_tolerances

    principal = str(params.get("principal", "a")).lower()
    if principal not in ("a", "b"):
        msg = f"conciliar: 'principal' aceita 'a' ou 'b' (recebido: {principal})."
        raise ConfigError(msg)

    task = ReconciliationTask(
        SourceSelection(path=_resolve(base, params["a"])),
        SourceSelection(path=_resolve(base, params["b"])),
        key_columns=_as_list(params.get("chave")),
        policy=ReconcilePolicy(
            primary=principal,  # type: ignore[arg-type]
            updatable_columns=tuple(_as_list(params.get("atualizar"))),
            include_new=bool(params.get("manter_novos", True)),
        ),
        normalizations=_as_list(params.get("normalizar")),
        tolerances=parse_tolerances(_as_list(params.get("tolerancia"))),
    )
    resultado = task.run()
    if resultado.is_failure or task.reconciliation is None:
        raise ConfigError(str(resultado.error_message))

    artefatos: list[Path] = []
    if destino is not None:
        artefatos = list(write_reconciliation_artifacts(task.reconciliation, destino))
    return generate_summary(task.reconciliation, max_rows=5), artefatos


def _run_transferir(
    params: dict[str, Any], base: Path, destino: Path | None
) -> tuple[str, list[Path]]:
    from autotarefas.reconcile.task import SourceSelection, TransferTask
    from autotarefas.reconcile.transfer import TransferPolicy
    from autotarefas.reconcile.transfer_artifacts import (
        generate_summary,
        write_transfer_artifacts,
    )

    task = TransferTask(
        SourceSelection(path=_resolve(base, params["destino"])),
        SourceSelection(path=_resolve(base, params["fonte"])),
        key_columns=_as_list(params.get("chave")),
        policy=TransferPolicy(
            fields=tuple(_as_list(params.get("campos"))),
            only_empty=bool(params.get("somente_vazios", False)),
            mark_origin=bool(params.get("marcar_origem", False)),
        ),
        normalizations=_as_list(params.get("normalizar")),
    )
    resultado = task.run()
    if resultado.is_failure or task.transfer is None:
        raise ConfigError(str(resultado.error_message))

    artefatos: list[Path] = []
    if destino is not None:
        artefatos = list(write_transfer_artifacts(task.transfer, destino, task.table_b))
    return generate_summary(task.transfer, max_rows=5), artefatos


def _run_corrigir(
    params: dict[str, Any], base: Path, destino: Path | None
) -> tuple[str, list[Path]]:
    from autotarefas.reader import read_workbook
    from autotarefas.tasks.correction_artifacts import (
        corrected_frame,
        generate_summary,
        write_correction_artifacts,
    )
    from autotarefas.tasks.corrections import apply_rules, load_rules

    arquivo = _resolve(base, params["arquivo"])
    regras = load_rules(_resolve(base, params["regras"]))

    leitura = read_workbook(arquivo)
    if not leitura.ok or leitura.original_dataframe is None:
        raise ConfigError(str(leitura.rejected_reason or "arquivo nao processado"))

    frame = leitura.original_dataframe
    colunas = [str(c) for c in frame.columns]
    linhas = [
        {coluna: str(frame.iloc[posicao][coluna]) for coluna in colunas}
        for posicao in range(len(frame))
    ]
    corrigidas, resultado = apply_rules(linhas, regras, first_data_row=leitura.data_start_row)

    artefatos: list[Path] = []
    if destino is not None:
        artefatos = list(
            write_correction_artifacts(
                arquivo,
                destino,
                resultado,
                corrected_frame(corrigidas, colunas),
                header_row=leitura.header_row or 1,
                sheet=leitura.selected_sheet if arquivo.suffix.lower() != ".csv" else None,
                reader_conversions=len(leitura.conversions),
            )
        )
    return generate_summary(resultado, max_rows=5), artefatos


_RUNNERS = {
    "comparar": _run_comparar,
    "conciliar": _run_conciliar,
    "transferir": _run_transferir,
    "corrigir": _run_corrigir,
}


def run_flow(
    config: FlowConfig,
    *,
    base_dir: Path,
    out_dir: Path | None = None,
    dry_run: bool = False,
) -> FlowResult:
    """
    Executa os passos na ordem declarada.

    Args:
        config: fluxo ja validado.
        base_dir: diretorio do arquivo de fluxo (os caminhos relativos
            do arquivo sao resolvidos a partir dele).
        out_dir: saida efetiva. **Precedencia CLI > configuracao > padrao**.
        dry_run: nao grava artefato nenhum; ainda assim executa a leitura e
            a analise, para que o resumo seja verdadeiro.

    Returns:
        FlowResult. Um passo que falha interrompe o fluxo: os seguintes
        provavelmente dependem do resultado dele.
    """
    destino_base = out_dir if out_dir is not None else config.out_dir
    passos: list[StepResult] = []
    avisos: list[str] = []

    if dry_run and destino_base is not None:
        avisos.append(f"[DRY-RUN] nenhum artefato foi gravado em {destino_base}")

    for indice, passo in enumerate(config.passos, start=1):
        destino = None if dry_run else _step_dir(destino_base, indice, passo.tipo)
        runner = _RUNNERS[passo.tipo]
        nome = passo.nome or passo.tipo
        try:
            resumo, artefatos = runner(passo.params(), base_dir, destino)
        except (ConfigError, KeyError, OSError, ValueError) as exc:
            detalhe = f"parametro obrigatorio ausente: {exc}" if isinstance(exc, KeyError) else exc
            passos.append(
                StepResult(
                    index=indice,
                    kind=passo.tipo,
                    name=nome,
                    ok=False,
                    error=str(detalhe),
                )
            )
            break

        passos.append(
            StepResult(
                index=indice,
                kind=passo.tipo,
                name=nome,
                ok=True,
                summary=resumo,
                artifacts=tuple(artefatos),
            )
        )

    return FlowResult(
        config_name=config.nome,
        steps=tuple(passos),
        out_dir=destino_base,
        dry_run=dry_run,
        warnings=tuple(avisos),
    )


def describe_flow(config: FlowConfig) -> str:
    """Uma linha por passo, para o usuario conferir antes de rodar."""
    linhas = [f"Fluxo: {config.nome} ({len(config.passos)} passo(s))"]
    linhas.extend(
        f"  {indice}. {passo.nome or passo.tipo} [{passo.tipo}]"
        for indice, passo in enumerate(config.passos, start=1)
    )
    return "\n".join(linhas)


def available_steps() -> Sequence[str]:
    """Tipos de passo aceitos (recorte V1)."""
    return tuple(_RUNNERS)


__all__ = [
    "SECRET_HINTS",
    "FlowConfig",
    "FlowResult",
    "FlowStep",
    "StepKind",
    "StepResult",
    "available_steps",
    "describe_flow",
    "load_flow",
    "run_flow",
]
