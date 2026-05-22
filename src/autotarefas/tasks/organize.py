"""
Task de organizacao: move/copia arquivos conforme regras declarativas YAML.

Terceira subclasse real de BaseTask (depois de ValidateTask e BackupTask).

Features:
- Regras em YAML com Pydantic (similar ao Schema da Fase 3)
- Variaveis no destination: {year}, {month:02d}, {day}, {ext}
- Conflict handling: skip (default), rename, overwrite
- Move ou copy (action no RuleSet)
- Dry-run (lista operacoes sem executar)
- Audit detalhado (cada arquivo na operations list)
- NAO recursivo — so arquivos diretos do source_dir
- Primeira rule que bate ganha (ordem importa)

Uso tipico:
    from pathlib import Path
    from autotarefas.tasks.organize import OrganizeTask, load_rules

    rules = load_rules(Path("downloads.yaml"))
    task = OrganizeTask(
        source_dir=Path("D:/Downloads"),
        rules=rules,
        dry_run=True,  # SEMPRE roda dry-run primeiro!
    )
    result = task.run()

    print(f"Moveria: {result.data['moved_count']} arquivos")
    print(f"Sem regra: {result.data['unmatched_count']}")
"""

from __future__ import annotations

import fnmatch
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from autotarefas.core import BaseTask, TaskResult, TaskStatus, ValidationError
from autotarefas.core.exceptions import SecurityError
from autotarefas.core.security import safe_path

# Tipos literais usados no RuleSet
ConflictAction = Literal["skip", "rename", "overwrite"]
OrganizeAction = Literal["move", "copy"]


# ============================================================
# Modelos Pydantic
# ============================================================


class Rule(BaseModel):
    """
    Uma regra individual de organizacao.

    Attributes:
        name: Nome amigavel (aparece em log/audit).
        patterns: Lista de padroes fnmatch que devem bater no nome
            do arquivo (case-insensitive em fnmatch). Ex: ["*.jpg", "*.png"].
        destination: Caminho relativo dentro do target_root. Pode conter
            variaveis: {year}, {month:02d}, {day:02d}, {ext}.
            Ex: "imagens/{year}/{month:02d}".
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    patterns: list[str] = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)

    @field_validator("patterns")
    @classmethod
    def _patterns_nao_vazios(cls, v: list[str]) -> list[str]:
        """Cada pattern deve ter conteudo (nao so espacos)."""
        for pattern in v:
            if not pattern.strip():
                raise ValueError("Patterns nao podem ser strings vazias")
        return v


class RuleSet(BaseModel):
    """
    Conjunto completo de regras + comportamentos.

    Attributes:
        target_root: Pasta raiz onde os arquivos vao ser organizados.
            Os destinations das regras sao relativos a esta pasta.
        rules: Lista de regras a aplicar (ordem importa — primeira que
            bate ganha).
        on_conflict: O que fazer se arquivo ja existe no destino.
        action: 'move' (default) ou 'copy'.
    """

    model_config = ConfigDict(extra="forbid")

    target_root: Path
    rules: list[Rule] = Field(..., min_length=1)
    on_conflict: ConflictAction = "skip"
    action: OrganizeAction = "move"


# ============================================================
# Carregamento de YAML
# ============================================================


def load_rules(yaml_path: Path) -> RuleSet:
    """
    Carrega RuleSet de arquivo YAML.

    Args:
        yaml_path: Caminho do arquivo YAML.

    Returns:
        RuleSet validado.

    Raises:
        ValidationError: Se arquivo nao existe, YAML invalido,
            ou estrutura nao bate com o schema.
    """
    if not yaml_path.exists():
        raise ValidationError(
            f"Arquivo de regras nao encontrado: {yaml_path}",
            field="yaml_path",
            value=str(yaml_path),
        )

    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValidationError(
            f"YAML invalido em {yaml_path}: {e}",
            field="yaml_path",
            value=str(yaml_path),
        ) from e

    if not isinstance(data, dict):
        raise ValidationError(
            f"YAML deve ter estrutura de dicionario, recebeu: {type(data).__name__}",
            field="yaml_path",
            value=str(yaml_path),
        )

    try:
        return RuleSet(**data)
    except Exception as e:
        raise ValidationError(
            f"Estrutura invalida em {yaml_path}: {e}",
            field="yaml_path",
            value=str(yaml_path),
        ) from e


# ============================================================
# OrganizeTask
# ============================================================


class OrganizeTask(BaseTask):
    """
    Organiza arquivos de uma pasta em sub-pastas conforme regras.

    Cada arquivo do source_dir e testado contra as regras (em ordem).
    A primeira regra cujos patterns batem com o nome do arquivo eh
    aplicada — o arquivo eh movido (ou copiado) pro destino resolvido.

    NAO eh recursivo: so processa arquivos diretamente no source_dir.
    Subpastas sao ignoradas (nao sao movidas nem recursionadas).
    """

    name = "organize"
    description = "Organiza arquivos em pastas conforme regras YAML"

    #: Limite de operacoes registradas no audit (evita dict gigante).
    _MAX_OPERATIONS_RECORDED: ClassVar[int] = 100

    #: Limite de tentativas em on_conflict='rename'.
    _MAX_RENAME_ATTEMPTS: ClassVar[int] = 1000

    def __init__(
        self,
        source_dir: Path,
        rules: RuleSet,
        *,
        dry_run: bool = False,
    ) -> None:
        """
        Inicializa OrganizeTask.

        Args:
            source_dir: Pasta com arquivos bagunçados a organizar.
            rules: Conjunto de regras (carregado via load_rules).
            dry_run: Se True, nao move/copia nada — so registra operacoes.
        """
        super().__init__(dry_run=dry_run)
        self.source_dir = source_dir
        self.rules = rules

    def execute(self) -> TaskResult:
        """Executa a organizacao."""
        started_at = datetime.now(UTC)

        # 1. Valida source_dir
        self._validate_source()

        # 2. Coleta arquivos diretos do source_dir
        files = self._collect_files()

        if not files:
            return self._make_result(
                status=TaskStatus.SKIPPED,
                started_at=started_at,
                error_message="Nenhum arquivo para organizar",
                data={
                    "source_dir": str(self.source_dir),
                    "target_root": str(self.rules.target_root),
                    "total_files": 0,
                },
            )

        # 3. Processa cada arquivo
        operations: list[dict[str, Any]] = []
        moved_count = 0
        skipped_count = 0
        error_count = 0
        unmatched_count = 0

        for file_path in files:
            op = self._process_file(file_path)
            operations.append(op)

            status = op["status"]
            if status == "success":
                moved_count += 1
            elif status == "skipped":
                skipped_count += 1
            elif status == "error":
                error_count += 1
            elif status == "unmatched":
                unmatched_count += 1

        # 4. Retorna resultado
        result_status = TaskStatus.DRY_RUN if self.dry_run else TaskStatus.SUCCESS

        return self._make_result(
            status=result_status,
            started_at=started_at,
            rows_affected=moved_count,
            data={
                "source_dir": str(self.source_dir),
                "target_root": str(self.rules.target_root),
                "action": self.rules.action,
                "total_files": len(files),
                "moved_count": moved_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "unmatched_count": unmatched_count,
                # Limita pra audit nao virar dict gigante
                "operations": operations[: self._MAX_OPERATIONS_RECORDED],
            },
        )

    # ========================================================
    # Validacao
    # ========================================================

    def _validate_source(self) -> None:
        """Garante que source_dir existe e e diretorio."""
        if not self.source_dir.exists():
            raise ValidationError(
                f"source_dir nao encontrado: {self.source_dir}",
                field="source_dir",
                value=str(self.source_dir),
            )

        if not self.source_dir.is_dir():
            raise ValidationError(
                f"source_dir nao e diretorio: {self.source_dir}",
                field="source_dir",
                value=str(self.source_dir),
            )

    # ========================================================
    # Coleta de arquivos
    # ========================================================

    def _collect_files(self) -> list[Path]:
        """
        Coleta arquivos diretos do source_dir.

        NAO eh recursivo (iterdir, nao rglob). Subpastas sao ignoradas.

        Returns:
            Lista ordenada por nome (determinismo).
        """
        return sorted(
            (p for p in self.source_dir.iterdir() if p.is_file()),
            key=lambda p: p.name,
        )

    # ========================================================
    # Processamento de UM arquivo
    # ========================================================

    def _process_file(self, file_path: Path) -> dict[str, Any]:
        """
        Processa um arquivo:
        1. Encontra rule que bate
        2. Resolve destination (com variaveis)
        3. Trata conflito
        4. Move/copia (ou registra em dry-run)

        Returns:
            Dict com info da operacao (source, destination, rule_name,
            action, status, error).
        """
        base_op: dict[str, Any] = {
            "source": str(file_path),
            "destination": None,
            "rule_name": None,
            "action": None,
            "status": "unmatched",
            "error": None,
        }

        # 1. Encontra rule
        rule = self._match_rule(file_path)
        if rule is None:
            return base_op

        base_op["rule_name"] = rule.name

        # 2. Resolve destination
        try:
            dest = self._resolve_destination(file_path, rule)
        except (KeyError, ValueError, OSError, SecurityError) as e:
            base_op["status"] = "error"
            base_op["error"] = f"resolucao de destination falhou: {e}"
            return base_op

        base_op["destination"] = str(dest)

        # 3. Resolve conflito
        try:
            final_dest = self._resolve_conflict(dest)
        except ValidationError as e:
            base_op["status"] = "error"
            base_op["error"] = str(e)
            return base_op

        if final_dest is None:
            # Pula (on_conflict=skip + destino existe)
            base_op["action"] = "skip"
            base_op["status"] = "skipped"
            base_op["error"] = "destino ja existe (on_conflict=skip)"
            return base_op

        base_op["destination"] = str(final_dest)
        base_op["action"] = self.rules.action

        # 4. Executa (ou simula em dry-run)
        if self.dry_run:
            base_op["status"] = "success"
            return base_op

        try:
            final_dest.parent.mkdir(parents=True, exist_ok=True)
            if self.rules.action == "move":
                shutil.move(str(file_path), str(final_dest))
            else:  # copy
                shutil.copy2(str(file_path), str(final_dest))
            base_op["status"] = "success"
        except OSError as e:
            base_op["status"] = "error"
            base_op["error"] = str(e)

        return base_op

    # ========================================================
    # Helpers
    # ========================================================

    def _match_rule(self, file_path: Path) -> Rule | None:
        """
        Encontra a primeira rule cujos patterns batem com o nome do arquivo.

        Returns:
            A Rule, ou None se nenhuma bate.
        """
        for rule in self.rules.rules:
            for pattern in rule.patterns:
                if fnmatch.fnmatch(file_path.name, pattern):
                    return rule
        return None

    def _resolve_destination(self, file_path: Path, rule: Rule) -> Path:
        """
        Resolve o destination de uma rule aplicando as variaveis.

        Pega mtime do arquivo pra calcular year/month/day. Combina com
        target_root e nome do arquivo.

        Returns:
            Path absoluto do destino final (incluindo nome do arquivo).
        """
        # mtime do arquivo (pode lancar OSError se permissao negada)
        mtime_timestamp = file_path.stat().st_mtime
        mtime = datetime.fromtimestamp(mtime_timestamp, tz=UTC)

        variables: dict[str, Any] = {
            "year": mtime.year,
            "month": mtime.month,
            "day": mtime.day,
            "ext": file_path.suffix.lstrip(".").lower(),
        }

        # Formata destination com format spec do Python
        # (suporta {month:02d} etc)
        try:
            relative_dest = rule.destination.format(**variables)
        except KeyError as e:
            # Variavel desconhecida no template
            raise KeyError(f"variavel desconhecida no destination: {e}") from e

        # Junta: target_root / destination_resolvido / nome_do_arquivo
        candidate = self.rules.target_root / relative_dest / file_path.name

        # SEGURANCA: bloqueia path traversal via destination malicioso
        try:
            return safe_path(candidate, [self.rules.target_root])
        except SecurityError as e:
            raise SecurityError(
                f"Destination escapa de target_root: {candidate}. "
                f"Rule '{rule.name}' tem destination suspeito: '{rule.destination}'"
            ) from e

    def _resolve_conflict(self, target: Path) -> Path | None:
        """
        Resolve conflito se target ja existe.

        Returns:
            - Path final a usar (pode ser target ou renomeado)
            - None se on_conflict=skip e target existe
        """
        if not target.exists():
            return target

        if self.rules.on_conflict == "overwrite":
            return target

        if self.rules.on_conflict == "skip":
            return None

        # on_conflict == "rename"
        stem = target.stem
        suffix = target.suffix
        parent = target.parent

        for counter in range(1, self._MAX_RENAME_ATTEMPTS + 1):
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate

        raise ValidationError(
            f"Muitos conflitos para {target} " f"(tentou ate _{self._MAX_RENAME_ATTEMPTS})",
            field="destination",
            value=str(target),
        )


__all__ = [
    "ConflictAction",
    "OrganizeAction",
    "OrganizeTask",
    "Rule",
    "RuleSet",
    "load_rules",
]
