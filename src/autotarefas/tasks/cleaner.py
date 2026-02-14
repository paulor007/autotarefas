"""
Task de Limpeza do AutoTarefas.

Fornece funcionalidades para limpeza de arquivos temporários e lixo:
    - CleanerTask: Remove arquivos temporários e lixo
    - CleaningProfile: Perfil de limpeza configurável
    - CleaningProfiles: Perfis pré-definidos

Uso:
    from autotarefas.tasks import CleanerTask, CleaningProfiles

    task = CleanerTask()
    result = task.run(
        paths=["/tmp", "~/Downloads"],
        profile=CleaningProfiles.TEMP_FILES
    )
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from autotarefas.core.base import BaseTask, TaskResult
from autotarefas.core.logger import logger
from autotarefas.utils.helpers import format_size, safe_path

# =============================================================================
# Helpers internos (somente o que é realmente específico desta task)
# =============================================================================


def _normalize_extensions(exts: list[str]) -> list[str]:
    """
    Normaliza uma lista de extensões de arquivo.

    Regras:
        - Remove espaços e converte para minúsculas
        - Ignora itens vazios
        - Garante que cada extensão comece com "."

    Args:
        exts: Lista de extensões (ex: ["png", ".JPG", "  pdf  ", ""]).

    Returns:
        Lista de extensões normalizadas (ex: [".png", ".jpg", ".pdf"]).
    """
    normalized: list[str] = []
    for e in exts:
        e = (e or "").strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        normalized.append(e)
    return normalized


def _normalize_patterns(pats: list[str]) -> list[str]:
    """
    Normaliza uma lista de padrões (patterns) de filtragem.

    Regras:
        - Remove espaços nas extremidades
        - Ignora itens vazios

    Args:
        pats: Lista de padrões (ex: [" *.tmp ", "", "cache/*", None]).

    Returns:
        Lista de padrões normalizados (ex: ["*.tmp", "cache/*"]).
    """
    normalized: list[str] = []
    for p in pats:
        p = (p or "").strip()
        if p:
            normalized.append(p)
    return normalized


def _matches_any_pattern(path: Path, patterns: list[str]) -> bool:
    """
    Verifica se um caminho corresponde a qualquer padrão informado.

    A checagem é feita contra:
        - o nome do arquivo/pasta (path.name)
        - o caminho em formato POSIX (path.as_posix())

    Usa `fnmatch`, então suporta curingas como "*", "?", e padrões tipo "cache/*.tmp".

    Args:
        path: Caminho a ser testado.
        patterns: Lista de padrões glob (ex: ["*.tmp", "cache/*", "docs/**/*.md"]).

    Returns:
        True se algum padrão casar com o nome ou com o caminho POSIX;
        caso contrário, False.
    """
    name = path.name
    posix = path.as_posix()
    return any(
        fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(posix, pat) for pat in patterns
    )


def _is_dangerous_clean_target(p: Path) -> bool:
    """
    Verifica se um alvo de limpeza é potencialmente perigoso.

    A ideia é evitar acidentes como tentar limpar diretórios críticos do sistema
    (ex.: "/", "C:\\Windows") ou a HOME inteira do usuário. Subpastas (ex.: ~/Downloads)
    continuam permitidas, mas o diretório "raiz" e alguns caminhos sensíveis
    são bloqueados.

    Regras principais:
        - Se não conseguir resolver o caminho, considera perigoso (fail-safe).
        - Bloqueia a raiz do filesystem ("/" ou "C:\\").
        - Bloqueia a HOME inteira.
        - Bloqueia alguns diretórios de sistema comuns (Linux/macOS).
        - Faz uma checagem simples para caminhos típicos perigosos no Windows.

    Args:
        p: Caminho candidato a ser limpo.

    Returns:
        True se o caminho for considerado perigoso para limpeza; caso contrário, False.
    """
    try:
        rp = p.resolve()
    except OSError:
        return True

    # raiz do filesystem
    root = Path(rp.anchor).resolve()
    if rp == root:
        return True

    # HOME inteira (limpar home pode ser catastrófico; subpastas como Downloads ok)
    home = Path.home().resolve()
    if rp == home:
        return True

    # Alguns diretórios de sistema comuns (Linux/macOS)
    dangerous = {
        Path("/").resolve(),
        Path("/bin").resolve(),
        Path("/sbin").resolve(),
        Path("/usr").resolve(),
        Path("/etc").resolve(),
        Path("/var").resolve(),
        Path("/lib").resolve(),
        Path("/proc").resolve(),
        Path("/sys").resolve(),
    }
    if rp in dangerous:
        return True

    # Windows (melhor esforço sem depender do OS explicitamente)
    rp_str = str(rp).lower()
    if (
        "windows" in rp_str
        and ("\\windows" in rp_str or "/windows" in rp_str)
        and (
            rp_str.endswith("windows")
            or "\\windows\\" in rp_str
            or "/windows/" in rp_str
        )
    ):
        return True

    return "program files" in rp_str


# =============================================================================
# Modelos
# =============================================================================


@dataclass(frozen=True)
class CleaningProfile:
    """
    Perfil de limpeza configurável.

    Define quais arquivos devem ser limpos com base em:
        - Extensões de arquivo
        - Padrões de nome
        - Idade mínima
        - Tamanho mínimo

    Attributes:
        name: Nome do perfil
        description: Descrição do perfil
        extensions: Extensões a limpar (ex: [".tmp", ".log"])
        patterns: Padrões de nome a limpar (ex: ["*.bak", "~*"])
        min_age_days: Idade mínima em dias para limpeza
        min_size_bytes: Tamanho mínimo para limpeza
        include_hidden: Se deve incluir arquivos ocultos
        recursive: Se deve limpar subdiretórios
    """

    name: str
    description: str = ""
    extensions: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    min_age_days: int = 0
    min_size_bytes: int = 0
    include_hidden: bool = False
    recursive: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))
        object.__setattr__(self, "patterns", _normalize_patterns(self.patterns))

    def matches(self, path: Path, *, now: datetime | None = None) -> bool:
        """
        Verifica se um arquivo corresponde ao perfil.

        Args:
            path: Caminho do arquivo
            now: Timestamp atual (opcional). Se None, usa datetime.now().

        Returns:
            True se o arquivo corresponde aos critérios do perfil; caso contrário False.
        """
        now = now or datetime.now()

        # arquivo oculto
        if not self.include_hidden and path.name.startswith("."):
            return False

        # extensão
        if self.extensions and path.suffix.lower() not in self.extensions:
            return False

        # patterns
        if self.patterns and not _matches_any_pattern(path, self.patterns):
            return False

        # idade mínima
        if self.min_age_days > 0:
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                return False
            if (now - mtime).days < self.min_age_days:
                return False

        # tamanho mínimo
        if self.min_size_bytes > 0:
            try:
                if path.stat().st_size < self.min_size_bytes:
                    return False
            except OSError:
                return False

        return True


class CleaningProfiles:
    """
    Perfis de limpeza pré-definidos.

    Perfis disponíveis:
        - TEMP_FILES: Arquivos temporários do sistema
        - LOG_FILES: Arquivos de log antigos
        - CACHE_FILES: Arquivos de cache
        - DOWNLOADS: Downloads antigos
        - THUMBNAILS: Miniaturas e lixo comum do sistema
    """

    TEMP_FILES = CleaningProfile(
        name="temp_files",
        description="Arquivos temporários do sistema",
        extensions=[".tmp", ".temp", ".bak", ".swp", ".swo"],
        patterns=["*.tmp", "~*", "*.old"],
        min_age_days=1,
        include_hidden=True,
        recursive=True,
    )

    LOG_FILES = CleaningProfile(
        name="log_files",
        description="Arquivos de log antigos",
        extensions=[".log"],
        patterns=["*.log", "*.log.*"],
        min_age_days=30,
        include_hidden=False,
        recursive=True,
    )

    CACHE_FILES = CleaningProfile(
        name="cache_files",
        description="Arquivos de cache",
        extensions=[".cache", ".pyc"],
        patterns=["*cache*", "__pycache__/*"],
        min_age_days=7,
        include_hidden=True,
        recursive=True,
    )

    DOWNLOADS = CleaningProfile(
        name="downloads",
        description="Downloads antigos",
        patterns=["*"],
        min_age_days=90,
        include_hidden=False,
        recursive=True,
    )

    THUMBNAILS = CleaningProfile(
        name="thumbnails",
        description="Miniaturas de imagens / lixo comum do sistema",
        patterns=["*.thumb", "Thumbs.db", ".DS_Store"],
        include_hidden=True,
        recursive=True,
    )

    @classmethod
    def get_by_name(cls, name: str) -> CleaningProfile | None:
        """
        Obtém um perfil por nome.

        Args:
            name: Nome do perfil

        Returns:
            CleaningProfile ou None se não encontrado.
        """
        profiles = {
            "temp_files": cls.TEMP_FILES,
            "log_files": cls.LOG_FILES,
            "cache_files": cls.CACHE_FILES,
            "downloads": cls.DOWNLOADS,
            "thumbnails": cls.THUMBNAILS,
        }
        return profiles.get((name or "").strip().lower())

    @classmethod
    def list_profiles(cls) -> list[str]:
        """Lista nomes dos perfis disponíveis."""
        return ["temp_files", "log_files", "cache_files", "downloads", "thumbnails"]


@dataclass
class CleaningResult:
    """
    Resultado detalhado da limpeza.

    Attributes:
        files_removed: Número de arquivos removidos
        dirs_removed: Número de diretórios removidos
        bytes_freed: Bytes liberados
        errors: Lista de erros encontrados
        skipped: Arquivos/pastas pulados
    """

    files_removed: int = 0
    dirs_removed: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def bytes_freed_formatted(self) -> str:
        """Retorna bytes liberados formatados."""
        return format_size(self.bytes_freed)

    def to_dict(self) -> dict[str, Any]:
        """Converte estatísticas para dicionário."""
        return {
            "files_removed": self.files_removed,
            "dirs_removed": self.dirs_removed,
            "bytes_freed": self.bytes_freed,
            "bytes_freed_formatted": self.bytes_freed_formatted,
            "errors_count": len(self.errors),
            "skipped_count": len(self.skipped),
        }


# =============================================================================
# Task
# =============================================================================


class CleanerTask(BaseTask):
    """
    Task para limpeza de arquivos temporários e lixo.

    Remove arquivos baseado em perfis de limpeza configuráveis,
    suportando múltiplos diretórios e critérios.

    Exemplo:
        >>> task = CleanerTask()
        >>> result = task.run(
        ...     paths=["/tmp", "~/.cache"],
        ...     profile="temp_files",
        ...     min_age_days=7
        ... )
        >>> print(result)
        [success] Limpeza concluída: 42 arquivos removidos (156.3 MB liberados)
    """

    @property
    def name(self) -> str:
        return "cleaner"

    @property
    def description(self) -> str:
        return "Remove arquivos temporários e lixo do sistema"

    def validate(self, **kwargs: Any) -> tuple[bool, str]:
        """
        Valida parâmetros da limpeza.

        Espera o parâmetro obrigatório:
            - paths: list[str|Path]

        E respeita:
            - allow_system_paths: bool (default False)
        """
        paths = kwargs.get("paths", [])
        allow_system_paths = bool(kwargs.get("allow_system_paths", False))

        if not paths:
            return False, "Parâmetro 'paths' é obrigatório (lista de diretórios)"

        for raw in paths:
            p = safe_path(raw)
            if not p.exists():
                return False, f"Diretório não existe: {p}"
            if not p.is_dir():
                return False, f"Path não é diretório: {p}"

            if not allow_system_paths and _is_dangerous_clean_target(p):
                return (
                    False,
                    f"Diretório perigoso para limpeza: {p} (se realmente quiser, use allow_system_paths=True)",
                )

        return True, ""

    def execute(
        self,
        paths: list[str | Path],
        profile: str | CleaningProfile | None = None,
        min_age_days: int | None = None,
        extensions: list[str] | None = None,
        patterns: list[str] | None = None,
        recursive: bool | None = None,
        include_hidden: bool | None = None,
        remove_empty_dirs: bool = True,
        allow_system_paths: bool = False,
        max_files: int = 200_000,
    ) -> TaskResult:
        """
        Executa a limpeza.

        Args:
            paths: Lista de diretórios para limpar
            profile: Perfil de limpeza (nome, objeto CleaningProfile, ou None)
            min_age_days: Idade mínima dos arquivos em dias
            extensions: Extensões específicas a remover
            patterns: Padrões de arquivo a remover
            recursive: Se deve limpar subdiretórios (override do perfil)
            include_hidden: Se deve incluir ocultos (override do perfil)
            remove_empty_dirs: Se deve remover diretórios vazios após limpar
            allow_system_paths: Se permite limpar caminhos perigosos (NÃO recomendado)
            max_files: Limite de arquivos inspecionados por diretório (proteção)

        Returns:
            TaskResult com estatísticas da limpeza
        """
        started_at = datetime.now()
        now = datetime.now()

        cleaning_profile = self._resolve_profile(
            profile=profile,
            min_age_days=min_age_days,
            extensions=extensions,
            patterns=patterns,
            recursive=recursive,
            include_hidden=include_hidden,
        )

        logger.info("Iniciando limpeza com perfil '%s'", cleaning_profile.name)

        result = CleaningResult()

        for raw in paths:
            base = safe_path(raw)

            if not allow_system_paths and _is_dangerous_clean_target(base):
                msg = f"Diretório perigoso pulado: {base}"
                result.skipped.append(str(base))
                logger.warning("[cleaner] %s", msg)
                continue

            logger.info("Limpando: %s", base)

            self._clean_directory(
                base=base,
                profile=cleaning_profile,
                result=result,
                now=now,
                max_files=max_files,
            )

            if remove_empty_dirs:
                self._remove_empty_dirs(base, result)

        message = f"Limpeza concluída: {result.files_removed} arquivos removidos ({result.bytes_freed_formatted} liberados)"
        if result.errors:
            message += f" - {len(result.errors)} erros"

        return TaskResult.success(
            message=message,
            data=result.to_dict(),
            started_at=started_at,
        )

    def _resolve_profile(
        self,
        *,
        profile: str | CleaningProfile | None,
        min_age_days: int | None,
        extensions: list[str] | None,
        patterns: list[str] | None,
        recursive: bool | None,
        include_hidden: bool | None,
    ) -> CleaningProfile:
        """
        Resolve e monta o perfil final de limpeza (CleaningProfile).

        A função escolhe um perfil base e, em seguida, aplica sobrescritas opcionais
        passadas pelo usuário (min_age_days, extensions, patterns, recursive,
        include_hidden).

        Regras:
            - Se `profile` for uma string, tenta buscar em `CleaningProfiles.get_by_name()`.
              Se não encontrar, usa `CleaningProfiles.TEMP_FILES` como fallback e registra warning.
            - Se `profile` já for um `CleaningProfile`, usa diretamente.
            - Se `profile` for None, usa `CleaningProfiles.TEMP_FILES`.
            - Se `extensions`/`patterns` forem informados, são normalizados antes de aplicar.
            - Default seguro: se ao final não houver `patterns` nem `extensions`,
              aplica `patterns=["*"]`.

        Returns:
            Um CleaningProfile final, já com defaults e sobrescritas aplicadas.
        """
        if isinstance(profile, str):
            base_profile = CleaningProfiles.get_by_name(profile)
            if base_profile is None:
                logger.warning(
                    "[cleaner] Perfil '%s' não encontrado. Usando 'temp_files'.",
                    profile,
                )
                base_profile = CleaningProfiles.TEMP_FILES
        elif isinstance(profile, CleaningProfile):
            base_profile = profile
        else:
            base_profile = CleaningProfiles.TEMP_FILES

        new_profile = base_profile

        if min_age_days is not None:
            new_profile = replace(new_profile, min_age_days=min_age_days)
        if extensions is not None:
            new_profile = replace(
                new_profile, extensions=_normalize_extensions(extensions)
            )
        if patterns is not None:
            new_profile = replace(new_profile, patterns=_normalize_patterns(patterns))
        if recursive is not None:
            new_profile = replace(new_profile, recursive=recursive)
        if include_hidden is not None:
            new_profile = replace(new_profile, include_hidden=include_hidden)

        if not new_profile.patterns and not new_profile.extensions:
            new_profile = replace(new_profile, patterns=["*"])

        return new_profile

    def _iter_candidate_files(self, base: Path, recursive: bool) -> Iterable[Path]:
        """
        Gera um iterável de candidatos (arquivos/pastas) dentro de um diretório base.

        Se `recursive` for True, percorre recursivamente subdiretórios usando `rglob("*")`.
        Caso contrário, percorre apenas o nível atual com `glob("*")`.

        Args:
            base: Diretório base onde a busca será realizada.
            recursive: Se deve buscar recursivamente.

        Returns:
            Iterável de Paths encontrados a partir de `base`.
        """
        return base.rglob("*") if recursive else base.glob("*")

    def _clean_directory(
        self,
        *,
        base: Path,
        profile: CleaningProfile,
        result: CleaningResult,
        now: datetime,
        max_files: int,
    ) -> None:
        """
        Limpa um diretório específico com base no perfil.

        Args:
            base: Diretório base
            profile: Perfil de limpeza
            result: Objeto de resultado (mutável)
            now: Timestamp atual (para cálculo de idade)
            max_files: Limite de arquivos inspecionados (proteção)
        """
        inspected = 0

        try:
            for item in self._iter_candidate_files(base, profile.recursive):
                if not item.is_file():
                    continue

                inspected += 1
                if inspected > max_files:
                    msg = f"Limite max_files atingido ({max_files}) em {base}. Interrompendo varredura."
                    result.errors.append(msg)
                    logger.warning("[cleaner] %s", msg)
                    break

                if not profile.matches(item, now=now):
                    continue

                try:
                    size = item.stat().st_size
                    item.unlink()
                    result.files_removed += 1
                    result.bytes_freed += size
                    logger.debug("Removido: %s", item)
                except PermissionError:
                    msg = f"Sem permissão: {item}"
                    result.errors.append(msg)
                    logger.warning("[cleaner] %s", msg)
                except OSError as e:
                    msg = f"Erro ao remover {item}: {e}"
                    result.errors.append(msg)
                    logger.warning("[cleaner] %s", msg)

        except Exception as e:
            msg = f"Erro ao processar diretório {base}: {e}"
            result.errors.append(msg)
            logger.error("[cleaner] %s", msg)

    def _remove_empty_dirs(self, base: Path, result: CleaningResult) -> None:
        """
        Remove diretórios vazios recursivamente (do mais profundo para o topo).

        Args:
            base: Diretório base
            result: Resultado acumulado (incrementa dirs_removed)
        """
        try:
            for dir_path in sorted(base.rglob("*"), reverse=True):
                if not dir_path.is_dir():
                    continue
                try:
                    dir_path.rmdir()  # só remove se vazio
                    result.dirs_removed += 1
                    logger.debug("Diretório vazio removido: %s", dir_path)
                except OSError:
                    # não está vazio (ou sem permissão)
                    pass
        except Exception as e:
            logger.warning("Erro ao remover diretórios vazios: %s", e)

    def preview(
        self,
        paths: list[str | Path],
        profile: str | CleaningProfile | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Visualiza o que seria limpo sem remover.

        Args:
            paths: Lista de diretórios
            profile: Perfil de limpeza (nome, objeto ou None)
            **kwargs: Sobrescritas de perfil (min_age_days, extensions, patterns, etc)

        Returns:
            Dict com preview do que seria removido.
        """
        cleaning_profile = self._resolve_profile(
            profile=profile,
            min_age_days=kwargs.get("min_age_days"),
            extensions=kwargs.get("extensions"),
            patterns=kwargs.get("patterns"),
            recursive=kwargs.get("recursive"),
            include_hidden=kwargs.get("include_hidden"),
        )

        now = datetime.now()
        files_to_remove: list[dict[str, Any]] = []
        total_size = 0

        for raw in paths:
            base = safe_path(raw)

            for item in self._iter_candidate_files(base, cleaning_profile.recursive):
                if not item.is_file():
                    continue
                if not cleaning_profile.matches(item, now=now):
                    continue
                try:
                    size = item.stat().st_size
                except OSError:
                    continue

                files_to_remove.append(
                    {
                        "path": str(item),
                        "size": size,
                        "size_formatted": format_size(size),
                    }
                )
                total_size += size

        return {
            "profile": cleaning_profile.name,
            "files_count": len(files_to_remove),
            "total_size": total_size,
            "total_size_formatted": format_size(total_size),
            "files": files_to_remove[:200],
        }


# Exports
__all__ = [
    "CleaningProfile",
    "CleaningProfiles",
    "CleaningResult",
    "CleanerTask",
]
