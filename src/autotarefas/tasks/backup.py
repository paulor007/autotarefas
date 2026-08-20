"""
Task de backup: compacta arquivos/pastas em ZIP verificavel.

Um backup nao e um ZIP. E uma promessa que precisa ser COBRAVEL no dia em que
o original ja nao existe. Nesse dia a pessoa faz duas perguntas — "o que tem
aqui dentro?" e "posso confiar que esta inteiro?" — e o pacote precisa
responder as duas sozinho, sem a ferramenta e sem os arquivos originais.

Dai saem as regras que este modulo segue, em ordem de importancia:

1. **Nunca perder dado em silencio.** Perder e ruim; perder sem avisar e
   fatal, porque destroi a confianca em todos os outros backups.
2. **Nunca entregar pacote incompleto com cara de completo.** Por isso a
   gravacao e atomica: o caminho final ou nao existe, ou esta inteiro.
3. **O que NAO foi salvo aparece tanto quanto o que foi.** Arquivo travado
   pelo Excel, sem permissao ou que sumiu no meio nao derruba o backup — vira
   ressalva registrada no resultado e dentro do proprio pacote.

O que este modulo NAO faz, de proposito:

- **backup incremental**: restaurar exigiria a corrente inteira (completo +
  todos os incrementais, na ordem). Um elo perdido inutiliza o resto, e quem
  restaura esta sempre sob pressao. Simplicidade aqui e seguranca;
- **senha de ZIP classica (ZipCrypto)**: quebravel em minutos. Oferecer daria
  falsa sensacao de protecao, pior do que nao oferecer;
- **copiar arquivo aberto**: nenhuma copia comum le um `.xlsx` aberto no
  Excel. Isso exige instantaneo de volume (VSS) e privilegio de
  administrador — fica para um card proprio. Aqui, o arquivo aberto vira
  ressalva explicita, com o motivo.

Uso:
    task = BackupTask(
        sources=[Path("D:/contabilidade")],
        destination=Path("D:/backups/contabilidade.zip"),
        exclude_patterns=["*.log"],
    )
    result = task.run()
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import io
import os
import re
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from autotarefas.core import BaseTask, TaskResult, TaskStatus, ValidationError
from autotarefas.core.exceptions import SecurityError
from autotarefas.core.security import validate_filename

#: Nome do manifesto dentro do pacote.
MANIFEST_NAME = "MANIFESTO.csv"

#: Sufixo do arquivo em construcao. So vira o nome final quando termina.
PARTIAL_SUFFIX = ".parcial"

#: O ZIP nao representa datas anteriores a 1980.
_ZIP_MIN_YEAR = 1980

#: Nome com data: `contabilidade_2026-08-20_1730.zip`.
_CARIMBO = "%Y-%m-%d_%H%M"
_PADRAO_CARIMBO = r"\d{4}-\d{2}-\d{2}_\d{4}"


@dataclass(frozen=True, slots=True)
class BackupEntry:
    """Um arquivo que ENTROU no pacote, com o que prova a integridade dele."""

    arcname: str
    """Caminho dentro do ZIP."""
    size_bytes: int
    sha256: str
    modified_at: str
    """Data de modificacao do original, em ISO."""


@dataclass(frozen=True, slots=True)
class UnreadableFile:
    """
    Um arquivo que NAO entrou, e por que.

    Existe para que a ausencia seja tao visivel quanto a presenca. Sem isto,
    a pessoa acha que tem o arquivo — e so descobre que nao tem no pior dia
    possivel.
    """

    arcname: str
    reason: str


def timestamped_name(destination: Path, momento: datetime | None = None) -> Path:
    """
    Insere a data no nome: `backup.zip` -> `backup_2026-08-20_1730.zip`.

    Backup diario com nome fixo sobrescreve o de ontem — e quando alguem
    percebe que os dados de ontem eram os bons, ja foi.
    """
    # O carimbo usa a hora LOCAL de proposito: e o relogio que a pessoa ve.
    agora = momento or datetime.now()
    return destination.with_name(
        f"{destination.stem}_{agora.strftime(_CARIMBO)}{destination.suffix}"
    )


def rotate_backups(destination: Path, keep: int) -> list[Path]:
    """
    Apaga os backups datados mais antigos, mantendo os `keep` mais novos.

    So considera arquivos irmaos com o MESMO nome base e um carimbo de data
    valido — `contabilidade_2026-08-20_1730.zip` conta, `contabilidade.zip`
    e `notas_fiscais_2026-08-20_1730.zip` nao. A regra e estreita de
    proposito: apagar arquivo do cliente por engano seria pior do que deixar
    disco encher.

    Args:
        destination: o backup recem-criado (nunca e apagado).
        keep: quantos manter, contando com o recem-criado. `0` desliga.

    Returns:
        Os arquivos removidos.
    """
    if keep <= 0:
        return []

    base = re.sub(f"_{_PADRAO_CARIMBO}$", "", destination.stem)
    padrao = re.compile(f"^{re.escape(base)}_{_PADRAO_CARIMBO}{re.escape(destination.suffix)}$")

    irmaos = sorted(
        (p for p in destination.parent.iterdir() if p.is_file() and padrao.match(p.name)),
        reverse=True,  # o carimbo ordena igual à data
    )

    # Preservados: os `keep` mais recentes E o recem-criado, sempre. As duas
    # regras coincidem no caso normal; separam-se quando o relogio da maquina
    # anda para tras ou ha pacote com carimbo no futuro. Nesse caso e melhor
    # sobrar um arquivo do que apagar o backup que a pessoa acabou de pedir,
    # ou apagar um mais novo que ele.
    preservados = set(irmaos[:keep]) | {destination}

    removidos: list[Path] = []
    for antigo in irmaos:
        if antigo in preservados:
            continue
        try:
            antigo.unlink()
            removidos.append(antigo)
        except OSError:  # pragma: no cover - arquivo em uso
            continue
    return removidos


class BackupTask(BaseTask):
    """
    Compacta uma ou mais fontes (pastas/arquivos) em um ZIP verificavel.

    Alem dos arquivos, grava um `MANIFESTO.csv` com o SHA-256 de CADA um e a
    lista do que nao pode ser lido. E o manifesto que torna o pacote
    autoverificavel: no dia em que ele e necessario, o original nao existe
    mais, entao conferir contra a origem e impossivel.
    """

    name = "backup"
    description = "Compacta arquivos/pastas em ZIP verificavel, com manifesto"

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
        # Bloqueio do Office: e lixo temporario, nunca conteudo.
        "~$*",
    )

    #: Buffer de leitura. 64 KB rende mais que 8 KB em disco de verdade.
    _BUFFER_SIZE: ClassVar[int] = 64 * 1024

    #: Ate este tamanho, o arquivo e lido na memoria antes de entrar no
    #: pacote; acima disso, vai para um temporario em disco. Ver `_escrever`.
    _SPOOL_LIMIT: ClassVar[int] = 16 * 1024 * 1024

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
            include_default_excludes: Se True (default), aplica tambem os
                DEFAULT_EXCLUDES.
            dry_run: Se True, nao cria o ZIP — so lista o que faria.
        """
        super().__init__(dry_run=dry_run)
        self.sources = sources
        self.destination = destination

        # SEGURANCA: valida que o nome do arquivo de destino e seguro
        try:
            validate_filename(destination.name)
        except SecurityError as e:
            raise ValidationError(
                f"Nome de arquivo de destino invalido: {e}",
                field="destination",
                value=str(destination),
            ) from e

        excludes = list(exclude_patterns or [])
        if include_default_excludes:
            excludes.extend(self.DEFAULT_EXCLUDES)
        self.exclude_patterns: tuple[str, ...] = tuple(excludes)

    @property
    def partial_path(self) -> Path:
        """Onde o pacote e montado antes de virar o arquivo final."""
        return self.destination.with_name(self.destination.name + PARTIAL_SUFFIX)

    def execute(self) -> TaskResult:
        """Executa o backup."""
        started_at = datetime.now(UTC)

        self._validate_sources()
        files_to_backup, files_excluded = self._collect_files()

        if not files_to_backup:
            return self._make_result(
                status=TaskStatus.SKIPPED,
                started_at=started_at,
                error_message=(f"Nenhum arquivo para fazer backup (skipped={len(files_excluded)})"),
                data={
                    "sources": [s.name for s in self.sources],
                    "destination": str(self.destination),
                    "file_count": 0,
                    "skipped_count": len(files_excluded),
                },
            )

        arcnames = self._resolve_arcnames(files_to_backup)

        if self.dry_run:
            return self._make_result(
                status=TaskStatus.DRY_RUN,
                started_at=started_at,
                rows_affected=len(files_to_backup),
                data={
                    "sources": [s.name for s in self.sources],
                    "destination": str(self.destination),
                    "file_count": len(files_to_backup),
                    "skipped_count": len(files_excluded),
                    "files_preview": [str(f) for f in files_to_backup[:20]],
                    "would_create": True,
                },
            )

        self.destination.parent.mkdir(parents=True, exist_ok=True)
        entradas, ilegiveis = self._build_package(files_to_backup, arcnames, started_at)

        if not entradas:
            # Tudo falhou: isso e falha, nao ressalva. Um pacote vazio com
            # cara de backup seria a pior mentira possivel.
            self._discard_partial()
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                rows_failed=len(ilegiveis),
                error_message=(
                    f"Nenhum dos {len(ilegiveis)} arquivo(s) pode ser lido; o backup nao foi criado"
                ),
                data={
                    "sources": [s.name for s in self.sources],
                    "destination": str(self.destination),
                    "file_count": 0,
                    "unreadable_count": len(ilegiveis),
                    "unreadable": [{"arquivo": u.arcname, "motivo": u.reason} for u in ilegiveis],
                },
            )

        # So agora o arquivo final passa a existir — inteiro, ou nunca.
        os.replace(self.partial_path, self.destination)
        sha256 = self._calculate_sha256(self.destination)

        return self._make_result(
            status=TaskStatus.PARTIAL if ilegiveis else TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=len(entradas),
            rows_failed=len(ilegiveis),
            error_message=(
                f"{len(ilegiveis)} arquivo(s) nao puderam ser lidos e ficaram de fora"
                if ilegiveis
                else None
            ),
            data={
                "sources": [s.name for s in self.sources],
                "destination": str(self.destination),
                "file_count": len(entradas),
                "skipped_count": len(files_excluded),
                "unreadable_count": len(ilegiveis),
                "unreadable": [{"arquivo": u.arcname, "motivo": u.reason} for u in ilegiveis],
                "size_bytes": self.destination.stat().st_size,
                "sha256": sha256,
                "manifest": MANIFEST_NAME,
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
            Tupla (incluidos, excluidos por regra).
        """
        included: list[Path] = []
        skipped: list[Path] = []
        # O proprio pacote nunca entra no pacote: guardar o ZIP dentro da
        # pasta copiada e comum em rede compartilhada, e sem isto cada
        # execucao carregaria a anterior.
        proibidos = {self._resolvido(self.destination), self._resolvido(self.partial_path)}

        for source in self.sources:
            candidatos = [source] if source.is_file() else sorted(source.rglob("*"))
            for path in candidatos:
                if not path.is_file():
                    continue
                if self._resolvido(path) in proibidos or self._should_exclude(path):
                    skipped.append(path)
                else:
                    included.append(path)

        return included, skipped

    @staticmethod
    def _resolvido(path: Path) -> Path:
        """Caminho absoluto para comparacao, mesmo que o arquivo nao exista."""
        try:
            return path.resolve()
        except OSError:  # pragma: no cover - caminho invalido no SO
            return path.absolute()

    def _should_exclude(self, path: Path) -> bool:
        """
        Verifica se o path deve ser excluido por algum padrao.

        Aplica fnmatch em CADA parte do path. Assim, padrao "__pycache__"
        bate em qualquer __pycache__ na arvore. E "*.log" bate em qualquer
        .log.
        """
        return any(
            fnmatch.fnmatch(part, pattern)
            for part in path.parts
            for pattern in self.exclude_patterns
        )

    # ========================================================
    # Nomes dentro do pacote (sem colisao)
    # ========================================================

    def _resolve_arcnames(self, files: list[Path]) -> dict[Path, str]:
        """
        Decide o nome de cada arquivo DENTRO do pacote, sem colisao.

        Duas fontes diferentes podem ter o mesmo caminho relativo — por
        exemplo `clienteA/docs/contrato.txt` e `clienteB/docs/contrato.txt`.
        O ZIP aceita nomes repetidos sem reclamar, e na extracao um
        sobrescreve o outro: o backup diz "2 arquivos" e entrega 1.

        Aqui isso nao acontece. A fonte entra como pasta raiz; fontes de
        mesmo nome ganham sufixo; e qualquer colisao restante vira
        `contrato (2).txt`. Nome feio e irrelevante perto de um contrato
        perdido em silencio.
        """
        raizes = self._nomes_das_fontes()
        usados: set[str] = set()
        arcnames: dict[Path, str] = {}

        for arquivo in files:
            arcnames[arquivo] = self._unico(self._arcname_bruto(arquivo, raizes), usados)
        return arcnames

    def _nomes_das_fontes(self) -> dict[Path, str]:
        """Nome de pasta raiz de cada fonte, desambiguado entre elas."""
        raizes: dict[Path, str] = {}
        usados: set[str] = set()
        for source in self.sources:
            base = source.name or "raiz"
            raizes[source] = self._unico(base, usados)
        return raizes

    @staticmethod
    def _unico(nome: str, usados: set[str]) -> str:
        """`nome`, ou `nome (2)`, `nome (3)`... se ja estiver em uso."""
        if nome not in usados:
            usados.add(nome)
            return nome

        caminho = Path(nome)
        raiz, sufixo = str(caminho.with_suffix("")), caminho.suffix
        contador = 2
        while f"{raiz} ({contador}){sufixo}" in usados:
            contador += 1
        candidato = f"{raiz} ({contador}){sufixo}"
        usados.add(candidato)
        return candidato

    def _arcname_bruto(self, file_path: Path, raizes: dict[Path, str]) -> str:
        """Caminho dentro do ZIP, antes de resolver colisoes."""
        for source in self.sources:
            if source.is_file():
                if file_path == source:
                    return file_path.name
                continue
            try:
                relativo = file_path.relative_to(source)
            except ValueError:
                continue
            return (Path(raizes[source]) / relativo).as_posix()
        return file_path.name  # pragma: no cover - defesa

    # ========================================================
    # Montagem do pacote
    # ========================================================

    def _build_package(
        self, files: list[Path], arcnames: dict[Path, str], started_at: datetime
    ) -> tuple[list[BackupEntry], list[UnreadableFile]]:
        """
        Monta o pacote no arquivo temporario.

        Grava sempre em `.parcial`: o caminho final so passa a existir depois
        que o ZIP fecha inteiro. Assim, queda de energia ou disco cheio nao
        deixam um pacote pela metade com cara de completo.
        """
        entradas: list[BackupEntry] = []
        ilegiveis: list[UnreadableFile] = []

        try:
            with zipfile.ZipFile(
                self.partial_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zf:
                for arquivo in files:
                    arcname = arcnames[arquivo]
                    try:
                        entradas.append(self._escrever(zf, arquivo, arcname))
                    except OSError as exc:
                        # Travado pelo Excel, sem permissao, ou sumiu entre a
                        # listagem e a gravacao. Nada disso pode derrubar o
                        # backup inteiro — vira ressalva.
                        ilegiveis.append(UnreadableFile(arcname, _motivo(exc)))

                self._escrever_pastas_vazias(zf, arcnames)
                zf.writestr(MANIFEST_NAME, self._manifesto(entradas, ilegiveis, started_at))
        except OSError:
            self._discard_partial()
            raise

        return entradas, ilegiveis

    def _escrever(self, zf: zipfile.ZipFile, arquivo: Path, arcname: str) -> BackupEntry:
        """
        Grava um arquivo no pacote e devolve a entrada do manifesto.

        O arquivo e lido INTEIRO antes de a entrada existir no ZIP. Parece um
        detalhe, e nao e: escrevendo direto para dentro do pacote, um arquivo
        que falha na metade da leitura — travado pelo Excel, por exemplo —
        deixa uma entrada de 0 byte com o nome certo. Quem extraisse pelo
        Windows receberia um arquivo vazio no lugar da planilha, em silencio.
        Assim, ou a leitura termina e a entrada nasce completa, ou a entrada
        nunca existe e o arquivo vira ressalva.

        O intermediario e um `SpooledTemporaryFile`: fica na memoria ate
        `_SPOOL_LIMIT` (o caso de quase todo documento de escritorio) e so
        toca o disco em arquivo grande.
        """
        st = arquivo.stat()
        info = zipfile.ZipInfo(arcname, date_time=_data_do_zip(st.st_mtime))
        info.compress_type = zipfile.ZIP_DEFLATED

        h = hashlib.sha256()
        with tempfile.SpooledTemporaryFile(max_size=self._SPOOL_LIMIT) as buffer:
            with arquivo.open("rb") as origem:
                while chunk := origem.read(self._BUFFER_SIZE):
                    h.update(chunk)
                    buffer.write(chunk)
            buffer.seek(0)
            with zf.open(info, "w") as destino:
                shutil.copyfileobj(buffer, destino, self._BUFFER_SIZE)

        return BackupEntry(
            arcname=arcname,
            size_bytes=st.st_size,
            sha256=h.hexdigest(),
            modified_at=datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(timespec="seconds"),
        )

    def _escrever_pastas_vazias(self, zf: zipfile.ZipFile, arcnames: dict[Path, str]) -> None:
        """
        Preserva pastas que ficaram sem nenhum arquivo.

        Sem isto, a estrutura volta incompleta na restauracao — e ha sistema
        que simplesmente nao inicia se a pasta esperada nao existe.
        """
        com_conteudo = {
            pai for arcname in arcnames.values() for pai in Path(arcname).parents if str(pai) != "."
        }
        raizes = self._nomes_das_fontes()
        for source in self.sources:
            if source.is_file():
                continue
            for pasta in source.rglob("*"):
                if not pasta.is_dir() or self._should_exclude(pasta):
                    continue
                relativo = Path(raizes[source]) / pasta.relative_to(source)
                if relativo not in com_conteudo:
                    zf.mkdir(relativo.as_posix())

    def _manifesto(
        self,
        entradas: list[BackupEntry],
        ilegiveis: list[UnreadableFile],
        started_at: datetime,
    ) -> str:
        """
        Monta o `MANIFESTO.csv` que vai DENTRO do pacote.

        CSV de proposito: abre no Excel do proprio cliente, sem depender da
        nossa ferramenta para ser lido. Um manifesto que so a ferramenta le
        nao serve para o dia em que a ferramenta nao esta a mao.

        Guarda o NOME das fontes, nunca o caminho completo: o pacote costuma
        sair da maquina, e o caminho interno nao ajuda quem restaura.
        """
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["# backup", "autotarefas"])
        writer.writerow(["# gerado_em", started_at.isoformat(timespec="seconds")])
        writer.writerow(["# fontes", " | ".join(s.name for s in self.sources)])
        writer.writerow(["# arquivos", len(entradas)])
        writer.writerow(["# nao_lidos", len(ilegiveis)])
        writer.writerow([])
        writer.writerow(["situacao", "arquivo", "bytes", "modificado_em", "sha256", "motivo"])
        for entrada in entradas:
            writer.writerow(
                [
                    "incluido",
                    entrada.arcname,
                    entrada.size_bytes,
                    entrada.modified_at,
                    entrada.sha256,
                    "",
                ]
            )
        for ilegivel in ilegiveis:
            writer.writerow(["NAO_LIDO", ilegivel.arcname, "", "", "", ilegivel.reason])
        return buffer.getvalue()

    def _discard_partial(self) -> None:
        """Remove o pacote incompleto. Melhor nada do que meia verdade."""
        self.partial_path.unlink(missing_ok=True)

    # ========================================================
    # Hash SHA-256
    # ========================================================

    def _calculate_sha256(self, path: Path) -> str:
        """SHA-256 do arquivo, lido em blocos (funciona com pacote grande)."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(self._BUFFER_SIZE):
                h.update(chunk)
        return h.hexdigest()


def _motivo(exc: OSError) -> str:
    """Traduz a falha do sistema para o que a pessoa precisa decidir."""
    if isinstance(exc, FileNotFoundError):
        return "o arquivo deixou de existir durante o backup"
    if isinstance(exc, PermissionError):
        return "sem permissao de leitura, ou aberto por outro programa (Excel, Word)"
    return f"nao foi possivel ler ({exc.strerror or type(exc).__name__})"


def _data_do_zip(mtime: float) -> tuple[int, int, int, int, int, int]:
    """Data de modificacao no formato do ZIP, que nao representa antes de 1980."""
    t = time.localtime(mtime)
    if t.tm_year < _ZIP_MIN_YEAR:
        return (_ZIP_MIN_YEAR, 1, 1, 0, 0, 0)
    return (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)


# ============================================================
# Verificacao de um pacote existente
# ============================================================


@dataclass(frozen=True, slots=True)
class VerifyReport:
    """O que a conferencia encontrou."""

    path: Path
    ok: bool
    checked: int
    corrupted: tuple[str, ...] = ()
    """Arquivos cujo conteudo nao bate com o manifesto."""
    missing: tuple[str, ...] = ()
    """Estavam no manifesto e sumiram do pacote."""
    unexpected: tuple[str, ...] = ()
    """Estao no pacote e nao constam do manifesto."""
    unreadable_at_origin: tuple[str, ...] = ()
    """Ficaram de fora quando o backup foi feito (ja era sabido)."""
    problem: str = ""
    """Preenchido quando o pacote nem pode ser aberto."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "arquivo": self.path.name,
            "integro": self.ok,
            "conferidos": self.checked,
            "corrompidos": list(self.corrupted),
            "faltando": list(self.missing),
            "nao_declarados": list(self.unexpected),
            "nao_lidos_na_origem": list(self.unreadable_at_origin),
            "problema": self.problem,
        }


#: Colunas minimas de uma linha util do manifesto (situacao + arquivo).
_COLUNAS_MINIMAS = 2

#: Posicao do sha256 na linha do manifesto.
_COLUNA_SHA = 4


def _ler_manifesto(zf: zipfile.ZipFile) -> tuple[dict[str, str], list[str]]:
    """(sha256 por arquivo, lista do que nao foi lido na origem)."""
    esperado: dict[str, str] = {}
    nao_lidos: list[str] = []
    texto = zf.read(MANIFEST_NAME).decode("utf-8")
    for linha in csv.reader(io.StringIO(texto)):
        if (
            len(linha) < _COLUNAS_MINIMAS
            or linha[0] in {"situacao", ""}
            or linha[0].startswith("#")
        ):
            continue
        if linha[0] == "incluido":
            esperado[linha[1]] = linha[_COLUNA_SHA]
        elif linha[0] == "NAO_LIDO":
            nao_lidos.append(linha[1])
    return esperado, nao_lidos


def verify_backup(path: Path, *, buffer_size: int = 64 * 1024) -> VerifyReport:
    """
    Confere um pacote gerado pelo `BackupTask`, sem precisar dos originais.

    Tres perguntas, nesta ordem:

    1. o ZIP abre e todas as entradas passam no CRC?
    2. cada arquivo tem o mesmo SHA-256 que o manifesto declarou?
    3. o que o manifesto diz que existe realmente esta la — e vice-versa?

    Um backup que ninguem confere e fe, nao garantia. Com isto, da para
    conferir de tempos em tempos, ANTES do dia em que ele e necessario.
    """
    if not path.is_file():
        return VerifyReport(path=path, ok=False, checked=0, problem="arquivo nao encontrado")

    try:
        with zipfile.ZipFile(path) as zf:
            if zf.testzip() is not None:
                return VerifyReport(
                    path=path, ok=False, checked=0, problem="o pacote esta corrompido (CRC)"
                )
            if MANIFEST_NAME not in zf.namelist():
                return VerifyReport(
                    path=path,
                    ok=False,
                    checked=0,
                    problem=(
                        f"pacote sem {MANIFEST_NAME}: nao da para conferir o conteudo "
                        "(foi gerado por outra ferramenta ou por uma versao antiga)"
                    ),
                )

            esperado, nao_lidos = _ler_manifesto(zf)
            presentes = {
                nome for nome in zf.namelist() if nome != MANIFEST_NAME and not nome.endswith("/")
            }

            corrompidos = [
                arcname
                for arcname, sha in esperado.items()
                if arcname in presentes and _sha_da_entrada(zf, arcname, buffer_size) != sha
            ]
            faltando = sorted(set(esperado) - presentes)
            inesperados = sorted(presentes - set(esperado))
    except (zipfile.BadZipFile, OSError) as exc:
        return VerifyReport(
            path=path, ok=False, checked=0, problem=f"nao foi possivel abrir: {exc}"
        )

    return VerifyReport(
        path=path,
        ok=not (corrompidos or faltando or inesperados),
        checked=len(esperado),
        corrupted=tuple(corrompidos),
        missing=tuple(faltando),
        unexpected=tuple(inesperados),
        unreadable_at_origin=tuple(nao_lidos),
    )


def _sha_da_entrada(zf: zipfile.ZipFile, arcname: str, buffer_size: int) -> str:
    h = hashlib.sha256()
    with zf.open(arcname) as entrada:
        while chunk := entrada.read(buffer_size):
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "MANIFEST_NAME",
    "PARTIAL_SUFFIX",
    "BackupEntry",
    "BackupTask",
    "UnreadableFile",
    "VerifyReport",
    "rotate_backups",
    "timestamped_name",
    "verify_backup",
]
