"""
Módulo de organização automática de arquivos.

O QUE ESTE MÓDULO FAZ:
======================
Organiza arquivos em pastas por tipo (extensão), útil para:
- Limpar pasta de Downloads
- Separar fotos, documentos, vídeos, etc
- Manter diretórios organizados automaticamente

EXEMPLO DE USO:
===============
    from autotarefas.tasks.organizer import OrganizerTask

    task = OrganizerTask()
    result = task.run(
        source="~/Downloads",
        profile="default",
    )

    # Resultado:
    # Downloads/
    # ├── Imagens/     (jpg, png, gif, webp...)
    # ├── Documentos/  (pdf, doc, xlsx, txt...)
    # ├── Videos/      (mp4, avi, mkv...)
    # ├── Audio/       (mp3, wav, flac...)
    # ├── Arquivos/    (zip, rar, 7z...)
    # └── Outros/      (extensões não mapeadas)

CLASSES:
========
- OrganizeProfile: Perfis de organização (enum)
- ConflictStrategy: O que fazer com arquivos duplicados (enum)
- FileCategory: Categorias de arquivos
- OrganizerTask: Task principal de organização
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.logger import logger

# =============================================================================
# ENUMS
# =============================================================================


class OrganizeProfile(Enum):
    """
    Perfis de organização de arquivos.

    Cada perfil define como os arquivos serão organizados:
    - DEFAULT: Organiza por tipo (Imagens, Documentos, Videos, etc)
    - BY_DATE: Organiza por data de modificação (2024/01, 2024/02, etc)
    - BY_EXTENSION: Organiza por extensão (pdf/, jpg/, docx/, etc)
    - CUSTOM: Usa mapeamento personalizado

    Exemplo:
        profile = OrganizeProfile.DEFAULT
        # Arquivos .jpg vão para pasta "Imagens"
        # Arquivos .pdf vão para pasta "Documentos"
    """

    DEFAULT = "default"
    BY_DATE = "by_date"
    BY_EXTENSION = "by_extension"
    CUSTOM = "custom"

    def __str__(self) -> str:
        return self.value


class ConflictStrategy(Enum):
    """
    Estratégia para lidar com arquivos duplicados.

    Quando um arquivo com mesmo nome já existe no destino:
    - SKIP: Pula o arquivo (não move)
    - OVERWRITE: Sobrescreve o arquivo existente
    - RENAME: Renomeia adicionando número (foto.jpg → foto_1.jpg)
    - ASK: Pergunta ao usuário (modo interativo)

    Exemplo:
        strategy = ConflictStrategy.RENAME
        # arquivo.pdf existe → cria arquivo_1.pdf
        # arquivo_1.pdf existe → cria arquivo_2.pdf
    """

    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"
    ASK = "ask"

    def __str__(self) -> str:
        return self.value


class FileCategory(Enum):
    """
    Categorias de arquivos para organização.

    Cada categoria representa uma pasta de destino:
    - IMAGES: Fotos e imagens
    - DOCUMENTS: Documentos de texto, PDFs, planilhas
    - VIDEOS: Arquivos de vídeo
    - AUDIO: Músicas e áudio
    - ARCHIVES: Arquivos compactados
    - CODE: Código fonte e scripts
    - EXECUTABLES: Programas executáveis
    - FONTS: Arquivos de fonte
    - EBOOKS: Livros digitais
    - OTHERS: Extensões não mapeadas
    """

    IMAGES = "Imagens"
    DOCUMENTS = "Documentos"
    VIDEOS = "Videos"
    AUDIO = "Audio"
    ARCHIVES = "Arquivos"
    CODE = "Codigo"
    EXECUTABLES = "Executaveis"
    FONTS = "Fontes"
    EBOOKS = "Ebooks"
    DATA = "Dados"
    OTHERS = "Outros"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# MAPEAMENTO PADRÃO DE EXTENSÕES
# =============================================================================


DEFAULT_EXTENSION_MAP: dict[str, FileCategory] = {
    # Imagens
    ".jpg": FileCategory.IMAGES,
    ".jpeg": FileCategory.IMAGES,
    ".png": FileCategory.IMAGES,
    ".gif": FileCategory.IMAGES,
    ".bmp": FileCategory.IMAGES,
    ".svg": FileCategory.IMAGES,
    ".webp": FileCategory.IMAGES,
    ".ico": FileCategory.IMAGES,
    ".tiff": FileCategory.IMAGES,
    ".tif": FileCategory.IMAGES,
    ".heic": FileCategory.IMAGES,
    ".heif": FileCategory.IMAGES,
    ".raw": FileCategory.IMAGES,
    ".psd": FileCategory.IMAGES,
    ".ai": FileCategory.IMAGES,
    # Documentos
    ".pdf": FileCategory.DOCUMENTS,
    ".doc": FileCategory.DOCUMENTS,
    ".docx": FileCategory.DOCUMENTS,
    ".xls": FileCategory.DOCUMENTS,
    ".xlsx": FileCategory.DOCUMENTS,
    ".ppt": FileCategory.DOCUMENTS,
    ".pptx": FileCategory.DOCUMENTS,
    ".odt": FileCategory.DOCUMENTS,
    ".ods": FileCategory.DOCUMENTS,
    ".odp": FileCategory.DOCUMENTS,
    ".txt": FileCategory.DOCUMENTS,
    ".rtf": FileCategory.DOCUMENTS,
    ".md": FileCategory.DOCUMENTS,
    ".tex": FileCategory.DOCUMENTS,
    # Vídeos
    ".mp4": FileCategory.VIDEOS,
    ".avi": FileCategory.VIDEOS,
    ".mkv": FileCategory.VIDEOS,
    ".mov": FileCategory.VIDEOS,
    ".wmv": FileCategory.VIDEOS,
    ".flv": FileCategory.VIDEOS,
    ".webm": FileCategory.VIDEOS,
    ".m4v": FileCategory.VIDEOS,
    ".mpeg": FileCategory.VIDEOS,
    ".mpg": FileCategory.VIDEOS,
    ".3gp": FileCategory.VIDEOS,
    # Áudio
    ".mp3": FileCategory.AUDIO,
    ".wav": FileCategory.AUDIO,
    ".flac": FileCategory.AUDIO,
    ".aac": FileCategory.AUDIO,
    ".ogg": FileCategory.AUDIO,
    ".wma": FileCategory.AUDIO,
    ".m4a": FileCategory.AUDIO,
    ".opus": FileCategory.AUDIO,
    ".aiff": FileCategory.AUDIO,
    # Arquivos compactados
    ".zip": FileCategory.ARCHIVES,
    ".rar": FileCategory.ARCHIVES,
    ".7z": FileCategory.ARCHIVES,
    ".tar": FileCategory.ARCHIVES,
    ".gz": FileCategory.ARCHIVES,
    ".bz2": FileCategory.ARCHIVES,
    ".xz": FileCategory.ARCHIVES,
    ".iso": FileCategory.ARCHIVES,
    ".dmg": FileCategory.ARCHIVES,
    # Código
    ".py": FileCategory.CODE,
    ".js": FileCategory.CODE,
    ".ts": FileCategory.CODE,
    ".html": FileCategory.CODE,
    ".css": FileCategory.CODE,
    ".java": FileCategory.CODE,
    ".c": FileCategory.CODE,
    ".cpp": FileCategory.CODE,
    ".h": FileCategory.CODE,
    ".cs": FileCategory.CODE,
    ".php": FileCategory.CODE,
    ".rb": FileCategory.CODE,
    ".go": FileCategory.CODE,
    ".rs": FileCategory.CODE,
    ".swift": FileCategory.CODE,
    ".kt": FileCategory.CODE,
    ".sql": FileCategory.CODE,
    ".sh": FileCategory.CODE,
    ".bat": FileCategory.CODE,
    ".ps1": FileCategory.CODE,
    # Executáveis
    ".exe": FileCategory.EXECUTABLES,
    ".msi": FileCategory.EXECUTABLES,
    ".app": FileCategory.EXECUTABLES,
    ".deb": FileCategory.EXECUTABLES,
    ".rpm": FileCategory.EXECUTABLES,
    ".apk": FileCategory.EXECUTABLES,
    # Fontes
    ".ttf": FileCategory.FONTS,
    ".otf": FileCategory.FONTS,
    ".woff": FileCategory.FONTS,
    ".woff2": FileCategory.FONTS,
    ".eot": FileCategory.FONTS,
    # E-books
    ".epub": FileCategory.EBOOKS,
    ".mobi": FileCategory.EBOOKS,
    ".azw": FileCategory.EBOOKS,
    ".azw3": FileCategory.EBOOKS,
    ".fb2": FileCategory.EBOOKS,
    # Dados
    ".json": FileCategory.DATA,
    ".xml": FileCategory.DATA,
    ".yaml": FileCategory.DATA,
    ".yml": FileCategory.DATA,
    ".csv": FileCategory.DATA,
    ".tsv": FileCategory.DATA,
    ".sqlite": FileCategory.DATA,
    ".db": FileCategory.DATA,
}


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class OrganizeResult:
    """
    Resultado detalhado da organização.

    Attributes:
        files_moved: Número de arquivos movidos
        files_skipped: Número de arquivos pulados
        files_renamed: Número de arquivos renomeados (conflito)
        bytes_organized: Total de bytes organizados
        categories_used: Categorias utilizadas
        errors: Lista de erros ocorridos
    """

    files_moved: int = 0
    files_skipped: int = 0
    files_renamed: int = 0
    files_failed: int = 0
    bytes_organized: int = 0
    categories_used: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return {
            "files_moved": self.files_moved,
            "files_skipped": self.files_skipped,
            "files_renamed": self.files_renamed,
            "files_failed": self.files_failed,
            "bytes_organized": self.bytes_organized,
            "categories_used": self.categories_used,
            "errors": self.errors,
        }


@dataclass
class FileMove:
    """
    Representa uma operação de mover arquivo.

    Attributes:
        source: Caminho original do arquivo
        destination: Caminho de destino
        category: Categoria do arquivo
        size: Tamanho em bytes
        success: Se a operação foi bem sucedida
        error: Mensagem de erro (se houver)
    """

    source: Path
    destination: Path
    category: FileCategory
    size: int = 0
    success: bool = False
    renamed: bool = False
    error: str | None = None


# =============================================================================
# ORGANIZER TASK
# =============================================================================


class OrganizerTask(BaseTask):
    """
    Task para organizar arquivos em pastas por tipo.

    Organiza arquivos de um diretório fonte em subpastas baseadas
    no tipo de arquivo (extensão).

    Exemplo:
        task = OrganizerTask()
        result = task.run(
            source="~/Downloads",
            profile="default",
            conflict_strategy="rename",
        )
    """

    @property
    def name(self) -> str:
        return "organizer"

    @property
    def description(self) -> str:
        return "Organiza arquivos em pastas por tipo"

    def validate(self, **kwargs: Any) -> tuple[bool, str]:
        """
        Valida parâmetros da organização.

        Args:
            source: Diretório a organizar
            profile: Perfil de organização

        Returns:
            Tupla (válido, mensagem)
        """
        source = kwargs.get("source")

        if not source:
            return False, "Parâmetro 'source' é obrigatório"

        source_path = Path(source).expanduser().resolve()

        if not source_path.exists():
            return False, f"Diretório não existe: {source_path}"

        if not source_path.is_dir():
            return False, f"Caminho não é um diretório: {source_path}"

        # Verificar se não é diretório do sistema
        dangerous_paths = [
            Path.home(),
            Path("/"),
            Path("C:\\"),
            Path("C:\\Windows"),
            Path("C:\\Program Files"),
            Path("/usr"),
            Path("/etc"),
            Path("/var"),
        ]

        for dangerous in dangerous_paths:
            if source_path == dangerous:
                return (
                    False,
                    f"Não é permitido organizar diretório do sistema: {source_path}",
                )

        return True, "Validação OK"

    def execute(self, **kwargs: Any) -> TaskResult:
        """
        Executa a organização de arquivos.

        Args:
            source: Diretório a organizar
            dest: Diretório de destino (default: mesmo que source)
            profile: Perfil de organização (default, by_date, by_extension)
            conflict_strategy: Estratégia para conflitos (skip, overwrite, rename)
            recursive: Incluir subdiretórios
            include_hidden: Incluir arquivos ocultos
            dry_run: Simular sem mover
            custom_map: Mapeamento customizado de extensões

        Returns:
            TaskResult com estatísticas da organização
        """
        source = Path(kwargs.get("source", ".")).expanduser().resolve()
        dest = kwargs.get("dest")
        dest_path = Path(dest).expanduser().resolve() if dest else source

        profile_str = kwargs.get("profile", "default")
        profile = (
            OrganizeProfile(profile_str)
            if isinstance(profile_str, str)
            else profile_str
        )

        conflict_str = kwargs.get("conflict_strategy", "rename")
        conflict = (
            ConflictStrategy(conflict_str)
            if isinstance(conflict_str, str)
            else conflict_str
        )

        recursive = kwargs.get("recursive", False)
        include_hidden = kwargs.get("include_hidden", False)
        dry_run = kwargs.get("dry_run", False)
        custom_map = kwargs.get("custom_map", {})

        logger.info(f"Organizando: {source}")
        logger.info(f"Perfil: {profile}, Conflito: {conflict}")

        if dry_run:
            logger.info("[DRY-RUN] Simulando organização")

        # Resultado
        result = OrganizeResult()

        # Obter mapeamento de extensões
        extension_map = self._get_extension_map(profile, custom_map)

        # Listar arquivos
        files = self._list_files(source, recursive, include_hidden)

        if not files:
            return TaskResult(
                status=TaskStatus.SUCCESS,
                message="Nenhum arquivo para organizar",
                data=result.to_dict(),
            )

        # Processar cada arquivo
        for file_path in files:
            move = self._process_file(
                file_path=file_path,
                dest_base=dest_path,
                profile=profile,
                extension_map=extension_map,
                conflict=conflict,
                dry_run=dry_run,
            )

            # Atualizar estatísticas
            if move.success:
                result.files_moved += 1
                result.bytes_organized += move.size

                category_name = move.category.value
                result.categories_used[category_name] = (
                    result.categories_used.get(category_name, 0) + 1
                )

                if move.renamed:
                    result.files_renamed += 1
            elif move.error and "pulado" in move.error.lower():
                result.files_skipped += 1
            else:
                result.files_failed += 1
                if move.error:
                    result.errors.append(f"{move.source.name}: {move.error}")

        # Mensagem final
        if dry_run:
            message = (
                f"[DRY-RUN] {result.files_moved} arquivos seriam organizados "
                f"em {len(result.categories_used)} categorias"
            )
        else:
            message = (
                f"Organização concluída: {result.files_moved} arquivos movidos "
                f"({self._format_bytes(result.bytes_organized)})"
            )

            if result.files_skipped:
                message += f", {result.files_skipped} pulados"

            if result.files_renamed:
                message += f", {result.files_renamed} renomeados"

        return TaskResult(
            status=TaskStatus.SUCCESS,
            message=message,
            data=result.to_dict(),
        )

    def _get_extension_map(
        self,
        profile: OrganizeProfile,
        custom_map: dict[str, str],
    ) -> dict[str, FileCategory]:
        """Retorna mapeamento de extensões baseado no perfil."""
        if profile == OrganizeProfile.CUSTOM and custom_map:
            # Converter strings para FileCategory
            result = {}
            for ext, category in custom_map.items():
                ext_lower = ext.lower() if not ext.startswith(".") else ext.lower()
                if not ext_lower.startswith("."):
                    ext_lower = f".{ext_lower}"

                if isinstance(category, str):
                    try:
                        result[ext_lower] = FileCategory(category)
                    except ValueError:
                        # Categoria customizada não existe, usar OTHERS
                        result[ext_lower] = FileCategory.OTHERS
                else:
                    result[ext_lower] = category
            return result

        return DEFAULT_EXTENSION_MAP.copy()

    def _list_files(
        self,
        source: Path,
        recursive: bool,
        include_hidden: bool,
    ) -> list[Path]:
        """Lista arquivos a serem organizados."""
        files = []

        pattern = "**/*" if recursive else "*"

        for path in source.glob(pattern):
            # Ignorar diretórios
            if path.is_dir():
                continue

            # Ignorar arquivos ocultos
            if not include_hidden and path.name.startswith("."):
                continue

            # Ignorar arquivos em pastas de categoria já existentes
            if self._is_in_category_folder(path, source):
                continue

            files.append(path)

        return files

    def _is_in_category_folder(self, path: Path, source: Path) -> bool:
        """Verifica se arquivo já está em pasta de categoria."""
        category_names = {cat.value for cat in FileCategory}

        # Verificar se algum pai é uma pasta de categoria
        try:
            relative = path.relative_to(source)
            parts = relative.parts

            if len(parts) > 1 and parts[0] in category_names:
                return True
        except ValueError:
            pass

        return False

    def _process_file(
        self,
        file_path: Path,
        dest_base: Path,
        profile: OrganizeProfile,
        extension_map: dict[str, FileCategory],
        conflict: ConflictStrategy,
        dry_run: bool,
    ) -> FileMove:
        """Processa um arquivo individual."""
        # Determinar categoria
        category = self._get_category(file_path, extension_map)

        # Determinar destino
        if profile == OrganizeProfile.BY_DATE:
            dest_folder = self._get_date_folder(file_path, dest_base)
        elif profile == OrganizeProfile.BY_EXTENSION:
            ext = file_path.suffix.lower().lstrip(".")
            dest_folder = dest_base / (ext if ext else "sem_extensao")
        else:
            dest_folder = dest_base / category.value

        dest_path = dest_folder / file_path.name

        # Criar objeto de movimento
        move = FileMove(
            source=file_path,
            destination=dest_path,
            category=category,
            size=file_path.stat().st_size if file_path.exists() else 0,
        )

        # Verificar conflito
        if dest_path.exists():
            if conflict == ConflictStrategy.SKIP:
                move.error = "Arquivo já existe, pulado"
                return move

            elif conflict == ConflictStrategy.RENAME:
                dest_path = self._get_unique_name(dest_path)
                move.destination = dest_path
                move.renamed = True

            elif conflict == ConflictStrategy.OVERWRITE:
                pass  # Vai sobrescrever

        # Executar movimento
        if dry_run:
            logger.debug(f"[DRY-RUN] {file_path.name} → {dest_path}")
            move.success = True
        else:
            try:
                dest_folder.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(dest_path))
                logger.debug(f"Movido: {file_path.name} → {dest_path}")
                move.success = True
            except Exception as e:
                move.error = str(e)
                logger.error(f"Erro ao mover {file_path.name}: {e}")

        return move

    def _get_category(
        self,
        file_path: Path,
        extension_map: dict[str, FileCategory],
    ) -> FileCategory:
        """Determina a categoria de um arquivo."""
        ext = file_path.suffix.lower()

        if ext in extension_map:
            return extension_map[ext]

        return FileCategory.OTHERS

    def _get_date_folder(self, file_path: Path, dest_base: Path) -> Path:
        """Retorna pasta baseada na data de modificação."""
        try:
            mtime = file_path.stat().st_mtime
            dt = datetime.fromtimestamp(mtime)
            return dest_base / str(dt.year) / f"{dt.month:02d}"
        except Exception:
            return dest_base / "sem_data"

    def _get_unique_name(self, path: Path) -> Path:
        """Gera nome único adicionando número."""
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name

            if not new_path.exists():
                return new_path

            counter += 1

            # Segurança: limitar tentativas
            if counter > 1000:
                raise RuntimeError(f"Não foi possível gerar nome único para {path}")

    def _format_bytes(self, size: int | float) -> str:
        """Formata bytes para exibição."""
        size_float = float(size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size_float < 1024:
                return f"{size_float:.1f} {unit}"
            size_float /= 1024
        return f"{size_float:.1f} TB"


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================


def organize_directory(
    source: str | Path,
    dest: str | Path | None = None,
    profile: str | OrganizeProfile = "default",
    conflict_strategy: str | ConflictStrategy = "rename",
    recursive: bool = False,
    dry_run: bool = False,
) -> TaskResult:
    """
    Função de conveniência para organizar diretório.

    Args:
        source: Diretório a organizar
        dest: Diretório de destino (default: mesmo que source)
        profile: Perfil de organização
        conflict_strategy: Estratégia para conflitos
        recursive: Incluir subdiretórios
        dry_run: Simular sem mover

    Returns:
        TaskResult com estatísticas

    Exemplo:
        result = organize_directory("~/Downloads")
        print(f"Arquivos organizados: {result.data['files_moved']}")
    """
    task = OrganizerTask()
    return task.run(
        source=source,
        dest=dest,
        profile=profile,
        conflict_strategy=conflict_strategy,
        recursive=recursive,
        dry_run=dry_run,
    )


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    # Enums
    "OrganizeProfile",
    "ConflictStrategy",
    "FileCategory",
    # Classes
    "OrganizerTask",
    "OrganizeResult",
    "FileMove",
    # Constantes
    "DEFAULT_EXTENSION_MAP",
    # Funções
    "organize_directory",
]
