"""
Task de backup: compacta arquivos/pastas em ZIP com integridade verificada.

Segunda subclasse real de BaseTask (depois de ValidateTask).

Features:
- Compactacao ZIP (deflate)
- Multiplas fontes (pastas e/ou arquivos individuais)
- Excludes via fnmatch (.gitignore-like)
- Excludes padrao razoaveis (__pycache__, .git, node_modules, etc)
- Hash SHA-256 do ZIP final (auditoria)
- Dry-run (lista o que faria sem criar nada)
- Audit trail automatico (herda BaseTask)

Uso:
    from pathlib import Path
    from autotarefas.tasks.backup import BackupTask

    task = BackupTask(
        sources=[Path("D:/projeto")],
        destination=Path("D:/backups/projeto.zip"),
        exclude_patterns=["*.log", "tmp/*"],
    )
    result = task.run()

    if result.is_success:
        print(f"Backup OK! {result.data['file_count']} arquivos, "
              f"{result.data['size_bytes']} bytes, "
              f"hash={result.data['sha256']}")
"""

from __future__ import annotations

import fnmatch
import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from autotarefas.core import BaseTask, TaskResult, TaskStatus, ValidationError


class BackupTask(BaseTask):
    """
    Compacta uma ou mais fontes (pastas/arquivos) em um ZIP.

    Calcula SHA-256 do ZIP gerado pra garantir integridade — armazenado
    no audit trail. Em caso de corrupcao posterior, da pra detectar.

    Excludes padrao incluem cache/build dirs comuns. Pode desabilitar
    com `include_default_excludes=False`.
    """

    name = "backup"
    description = "Compacta arquivos/pastas em ZIP com hash SHA-256"

    #: Padroes que sao excluidos por padrao (cache, VCS, IDEs).
    DEFAULT_EXCLUDES: ClassVar[tuple[str, ...]] = (
        # Python
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        # Virtual envs
        ".venv",
        "venv",
        "env",
        # VCS
        ".git",
        ".svn",
        ".hg",
        # Node
        "node_modules",
        # OS
        ".DS_Store",
        "Thumbs.db",
        # IDE
        ".idea",
        ".vscode",
    )

    #: Buffer pra leitura do arquivo ao calcular hash (8 KB).
    _HASH_BUFFER_SIZE: ClassVar[int] = 8192

    def __init__(
        self,
        sources: list[Path],
        destination: Path,
        *,
        exclude_patterns: list[str] | None = None,
        include_default_excludes: bool = True,
        dry_run: bool = False,
    ) -> None:
        """
        Inicializa BackupTask.

        Args:
            sources: Lista de pastas/arquivos a incluir no backup.
            destination: Caminho do ZIP a criar (cria pasta pai se preciso).
            exclude_patterns: Padroes adicionais de exclusao (fnmatch).
                Ex: ["*.log", "tmp/*", "build"].
            include_default_excludes: Se True (default), aplica tambem os
                DEFAULT_EXCLUDES.
            dry_run: Se True, nao cria o ZIP — so lista o que faria.
        """
        super().__init__(dry_run=dry_run)
        self.sources = sources
        self.destination = destination

        # Combina excludes do usuario com defaults (se habilitado)
        excludes = list(exclude_patterns or [])
        if include_default_excludes:
            excludes.extend(self.DEFAULT_EXCLUDES)

        # Tupla pra imutabilidade
        self.exclude_patterns: tuple[str, ...] = tuple(excludes)

    def execute(self) -> TaskResult:
        """Executa o backup."""
        started_at = datetime.now(UTC)

        # 1. Valida que todas as sources existem
        self._validate_sources()

        # 2. Coleta arquivos a incluir (aplicando excludes)
        files_to_backup, files_skipped = self._collect_files()

        if not files_to_backup:
            return self._make_result(
                status=TaskStatus.SKIPPED,
                started_at=started_at,
                error_message=(
                    "Nenhum arquivo para fazer backup " f"(skipped={len(files_skipped)})"
                ),
                data={
                    "sources": [str(s) for s in self.sources],
                    "destination": str(self.destination),
                    "file_count": 0,
                    "skipped_count": len(files_skipped),
                },
            )

        # 3. Se dry-run, retorna sem criar o ZIP
        if self.dry_run:
            return self._make_result(
                status=TaskStatus.DRY_RUN,
                started_at=started_at,
                rows_affected=len(files_to_backup),
                data={
                    "sources": [str(s) for s in self.sources],
                    "destination": str(self.destination),
                    "file_count": len(files_to_backup),
                    "skipped_count": len(files_skipped),
                    # Lista os primeiros 20 — evita poluir audit
                    "files_preview": [str(f) for f in files_to_backup[:20]],
                    "would_create": True,
                },
            )

        # 4. Cria o ZIP
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        size_bytes = self._create_zip(files_to_backup)

        # 5. Calcula SHA-256 do resultado
        sha256 = self._calculate_sha256(self.destination)

        # 6. Retorna sucesso
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=len(files_to_backup),
            data={
                "sources": [str(s) for s in self.sources],
                "destination": str(self.destination),
                "file_count": len(files_to_backup),
                "skipped_count": len(files_skipped),
                "size_bytes": size_bytes,
                "sha256": sha256,
            },
        )

    # ========================================================
    # Validacao
    # ========================================================

    def _validate_sources(self) -> None:
        """Garante que todas as sources existem."""
        for src in self.sources:
            if not src.exists():
                raise ValidationError(
                    f"Source nao encontrado: {src}",
                    field="sources",
                    value=str(src),
                )

    # ========================================================
    # Coleta de arquivos (com excludes)
    # ========================================================

    def _collect_files(self) -> tuple[list[Path], list[Path]]:
        """
        Coleta arquivos a incluir, aplicando os padroes de exclusao.

        Returns:
            Tupla (incluidos, excluidos).
        """
        included: list[Path] = []
        skipped: list[Path] = []

        for source in self.sources:
            if source.is_file():
                # Arquivo individual
                if self._should_exclude(source):
                    skipped.append(source)
                else:
                    included.append(source)
            else:
                # Diretorio — walk recursivo
                for path in source.rglob("*"):
                    if path.is_file():
                        if self._should_exclude(path):
                            skipped.append(path)
                        else:
                            included.append(path)

        return included, skipped

    def _should_exclude(self, path: Path) -> bool:
        """
        Verifica se o path deve ser excluido por algum padrao.

        Aplica fnmatch em CADA parte do path. Assim, padrao "__pycache__"
        bate em qualquer __pycache__ na arvore. E "*.log" bate em qualquer
        .log.

        Args:
            path: Caminho a verificar.

        Returns:
            True se algum padrao bate (path deve ser excluido).
        """
        for part in path.parts:
            for pattern in self.exclude_patterns:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    # ========================================================
    # Criacao do ZIP
    # ========================================================

    def _create_zip(self, files: list[Path]) -> int:
        """
        Cria o arquivo ZIP com os arquivos especificados.

        Usa ZIP_DEFLATED (algoritmo deflate) — bom equilibrio entre
        velocidade e compressao. Cada arquivo recebe um arcname
        relativo, preservando a estrutura.

        Args:
            files: Lista de arquivos a incluir.

        Returns:
            Tamanho final do ZIP em bytes.
        """
        with zipfile.ZipFile(
            self.destination,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,  # padrao do deflate
        ) as zf:
            for file_path in files:
                arcname = self._make_arcname(file_path)
                zf.write(file_path, arcname=arcname)

        return self.destination.stat().st_size

    def _make_arcname(self, file_path: Path) -> str:
        """
        Calcula o nome do arquivo dentro do ZIP (arcname).

        Lógica:
        - Se source eh arquivo: arcname = nome do arquivo
        - Se source eh pasta: arcname = caminho relativo desde a pasta

        Multiplas sources com mesmo nome podem colidir — usuario que se
        preocupa com isso.
        """
        for source in self.sources:
            try:
                if source.is_file():
                    # Source eh arquivo: arcname e so o nome
                    if file_path == source:
                        return file_path.name
                else:
                    # Source eh pasta: arcname relativo
                    relative = file_path.relative_to(source)
                    # Inclui o nome da pasta source no caminho final
                    return str(Path(source.name) / relative)
            except ValueError:
                # file_path nao e relativo a essa source — tenta proxima
                continue

        # Fallback: so o nome do arquivo
        return file_path.name

    # ========================================================
    # Hash SHA-256
    # ========================================================

    def _calculate_sha256(self, path: Path) -> str:
        """
        Calcula SHA-256 do arquivo, lendo em chunks (memoria-friendly).

        Le em buffers de 8 KB pra suportar arquivos grandes sem carregar
        tudo na RAM.

        Args:
            path: Caminho do arquivo.

        Returns:
            Hash SHA-256 em hexadecimal (64 chars).
        """
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(self._HASH_BUFFER_SIZE):
                h.update(chunk)
        return h.hexdigest()


__all__ = ["BackupTask"]
