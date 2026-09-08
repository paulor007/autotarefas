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

**O que o manifesto prova — e o que nao prova.** Os SHA-256 gravados dentro
do pacote detectam corrupcao (disco com defeito, transferencia truncada) e
alteracao acidental. Eles NAO comprovam autenticidade: quem tem acesso de
escrita ao arquivo pode trocar o conteudo e recalcular o manifesto, e a
conferencia passaria. Provar que o pacote e o mesmo que o AutoTarefas gerou
exige assinatura com chave mantida FORA dele — e isso ainda nao existe aqui.
Enquanto nao existir, a documentacao e as mensagens nao podem sugerir o
contrario.

O que este modulo NAO faz, de proposito:

- **backup incremental**: restaurar exigiria a corrente inteira (completo +
  todos os incrementais, na ordem). Um elo perdido inutiliza o resto, e quem
  restaura esta sempre sob pressao. Simplicidade aqui e seguranca;
- **senha de ZIP classica (ZipCrypto)**: quebravel em minutos. Oferecer daria
  falsa sensacao de protecao, pior do que nao oferecer;
- **provar autenticidade**: ver o paragrafo acima. Detectamos corrupcao,
  nao adulteracao deliberada;
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
import stat
import sys
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
from autotarefas.tasks import assinatura, cifra
from autotarefas.tasks import catalogo as mod_catalogo

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
    modificado_em_epoch: float = 0.0
    """A mesma data, em segundos. E a forma que o catalogo compara — texto
    ISO nao permite a folga de dois segundos que sistemas de arquivos
    diferentes exigem."""


@dataclass(frozen=True, slots=True)
class LinkFound:
    """
    Um atalho de pasta encontrado na origem: junção, link simbólico ou
    ponto de reanálise.

    Por padrão o conteúdo apontado NAO e copiado. Um atalho para a pasta de
    outro setor, ou para um drive de rede, colocaria dados de fora dentro do
    pacote sem ninguem perceber — e dado de terceiro em backup alheio e
    problema de LGPD, nao so de tamanho de arquivo.
    """

    arcname: str
    """Onde o atalho esta, relativo a origem."""
    target: str
    """Para onde ele aponta."""
    followed: bool
    outside_source: bool
    """O alvo esta FORA da pasta escolhida?"""
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "atalho": self.arcname,
            "destino": self.target,
            "seguido": self.followed,
            "fora_da_origem": self.outside_source,
            "motivo": self.reason,
        }


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


def is_link(path: Path) -> bool:
    """
    O caminho e um atalho — link simbolico, junção ou ponto de reanálise?

    `Path.is_symlink()` sozinho NAO basta no Windows: junção criada com
    `mklink /J` devolve False ali, e era por isso que o backup entrava nela
    como se fosse pasta comum. O atributo de ponto de reanálise pega os dois.
    """
    if path.is_symlink():
        return True
    if sys.platform != "win32":
        # Ponto de reanalise e conceito do Windows: em POSIX o `is_symlink`
        # acima ja respondeu tudo o que havia para responder.
        return False
    try:
        atributos = path.lstat().st_file_attributes
    except OSError:  # caminho sumiu ou ficou inacessivel entre uma chamada e outra
        return False
    return bool(atributos & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _volume(path: Path) -> int | None:
    """Identificador do volume, subindo ate um caminho que exista."""
    alvo = path
    while not alvo.exists() and alvo != alvo.parent:
        alvo = alvo.parent
    try:
        return alvo.stat().st_dev
    except OSError:  # pragma: no cover - caminho invalido
        return None


def same_volume(source: Path, destination: Path) -> bool:
    """
    Origem e destino estao no MESMO disco?

    Nao impede nada — so permite avisar. Backup no mesmo volume nao protege
    contra defeito do disco, e ransomware cifra tudo o que alcança, backup
    inclusive.
    """
    origem, destino = _volume(source), _volume(destination)
    return origem is not None and origem == destino


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
    #:
    #: Eram 16 MB, calibrados para o mundo do envio pelo navegador, onde nada
    #: passa de 10 MB. Com o Agente copiando midia da maquina do cliente, esse
    #: teto virava o pico de memoria por arquivo — medido em 12,8 MB para um
    #: arquivo de 12 MB. Dois megabytes cobrem praticamente todo documento de
    #: escritorio (Word, Excel, PDF) sem tocar o disco, e mantem o pico
    #: pequeno para o resto. O custo e uma gravacao temporaria a mais em
    #: arquivo medio; o ZIP ja esta indo para o disco de qualquer forma.
    _SPOOL_LIMIT: ClassVar[int] = 2 * 1024 * 1024

    def __init__(  # noqa: PLR0913 - opcionais keyword-only, uma decisao cada
        self,
        sources: list[Path],
        destination: Path,
        *,
        exclude_patterns: list[str] | None = None,
        include_default_excludes: bool = True,
        follow_links: bool = False,
        dry_run: bool = False,
        catalogo: mod_catalogo.Catalogo | None = None,
    ) -> None:
        """
        Inicializa BackupTask.

        Args:
            sources: Lista de pastas/arquivos a incluir no backup.
            destination: Caminho do ZIP a criar (cria pasta pai se preciso).
            exclude_patterns: Padroes adicionais de exclusao (fnmatch).
            include_default_excludes: Se True (default), aplica tambem os
                DEFAULT_EXCLUDES.
            follow_links: Se True, entra em junção e link de pasta. Desligado
                por padrao — atalho para fora da origem colocaria dado de
                terceiro no pacote sem ninguem perceber.
            dry_run: Se True, nao cria o ZIP — so lista o que faria.
            catalogo: Quando informado, o backup fica INCREMENTAL: arquivo ja
                copiado e identico nao entra no pacote de novo, e o manifesto
                registra em qual pacote anterior ele esta. Sem catalogo, o
                comportamento e o de sempre — pacote completo.
        """
        super().__init__(dry_run=dry_run)
        self.sources = sources
        self.destination = destination
        self.follow_links = follow_links
        self.catalogo = catalogo
        #: Arquivos que ficaram de fora por ja estarem num pacote anterior.
        self.inalterados: list[mod_catalogo.Anterior] = []

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

    def same_volume_sources(self) -> list[str]:
        """
        Quais fontes estao no MESMO disco do destino.

        So informa; nao bloqueia e nao pede confirmacao — travar aqui
        quebraria backup agendado, que roda sem ninguem por perto.
        """
        return [s.name for s in self.sources if same_volume(s, self.destination)]

    @property
    def partial_path(self) -> Path:
        """Onde o pacote e montado antes de virar o arquivo final."""
        return self.destination.with_name(self.destination.name + PARTIAL_SUFFIX)

    def execute(self) -> TaskResult:
        """Executa o backup."""
        started_at = datetime.now(UTC)

        self._validate_sources()
        files_to_backup, files_excluded, links, pastas = self._collect_files()

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
                    "links": [link.as_dict() for link in links],
                },
            )

        arcnames = self._resolve_arcnames(files_to_backup)
        a_copiar, ja_copiados = self._separar_inalterados(files_to_backup, arcnames)

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
                    "links": [link.as_dict() for link in links],
                    "same_volume": self.same_volume_sources(),
                    "would_create": True,
                },
            )

        self.destination.parent.mkdir(parents=True, exist_ok=True)
        entradas, ilegiveis = self._build_package(
            a_copiar, arcnames, started_at, links=links, pastas=pastas, ja_copiados=ja_copiados
        )

        # Com catalogo, "nenhum arquivo novo" e um desfecho legitimo e comum:
        # a pasta nao mudou desde ontem. O pacote sai com o manifesto e as
        # referencias, e serve para restaurar tanto quanto qualquer outro.
        if not entradas and not ja_copiados:
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
        self._atualizar_catalogo(entradas, started_at)

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
                # Incremental: o que ja estava em pacote anterior e nao foi
                # copiado de novo. Zero quando nao ha catalogo.
                "incremental": self.catalogo is not None,
                "inalterados_count": len(ja_copiados),
                "size_bytes": self.destination.stat().st_size,
                "sha256": sha256,
                "manifest": MANIFEST_NAME,
                "links": [link.as_dict() for link in links],
                "same_volume": self.same_volume_sources(),
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

    def _collect_files(self) -> tuple[list[Path], list[Path], list[LinkFound], list[Path]]:
        """
        Percorre as fontes e separa o que entra, o que sai e o que e atalho.

        A travessia e nossa, e nao `rglob`, por dois motivos comprovados: o
        `rglob` entra em junção como se fosse pasta comum — copiando dados de
        FORA da origem — e, quando a junção aponta para um ancestral, ele
        volta ao mesmo lugar repetidamente, duplicando arquivos ate o limite
        de tamanho de caminho do sistema.

        Returns:
            (incluidos, excluidos por regra, atalhos, pastas visitadas).
        """
        included: list[Path] = []
        skipped: list[Path] = []
        links: list[LinkFound] = []
        pastas: list[Path] = []
        # O proprio pacote nunca entra no pacote: guardar o ZIP dentro da
        # pasta copiada e comum em rede compartilhada, e sem isto cada
        # execucao carregaria a anterior.
        proibidos = {self._resolvido(self.destination), self._resolvido(self.partial_path)}

        for source in self.sources:
            if source.is_file():
                if self._resolvido(source) in proibidos or self._should_exclude(source):
                    skipped.append(source)
                else:
                    included.append(source)
                continue
            self._andar(
                pasta=source,
                raiz=source,
                incluidos=included,
                excluidos=skipped,
                links=links,
                pastas=pastas,
                proibidos=proibidos,
                visitados={self._resolvido(source)},
            )

        return included, skipped, links, pastas

    def _separar_inalterados(
        self, incluidos: list[Path], arcnames: dict[Path, str]
    ) -> tuple[list[Path], list[tuple[str, mod_catalogo.Anterior]]]:
        """
        Separa o que precisa entrar no pacote do que ja esta em outro.

        Sem catalogo, tudo entra: o backup completo continua sendo o padrao, e
        e ele que vale quando alguem nao configurou nada.
        """
        if self.catalogo is None:
            return incluidos, []

        entram: list[Path] = []
        ja_copiados: list[tuple[str, mod_catalogo.Anterior]] = []

        for arquivo in incluidos:
            arcname = arcnames[arquivo]
            try:
                st = arquivo.stat()
            except OSError:
                # Sumiu entre a listagem e agora. Deixa entrar: quem trata
                # arquivo ilegivel e o `_escrever`, que ja sabe virar ressalva.
                entram.append(arquivo)
                continue

            anterior = self.catalogo.anterior(arcname)
            decisao = mod_catalogo.decidir(
                anterior,
                tamanho=st.st_size,
                modificado_em=st.st_mtime,
                calcular_sha=lambda alvo=arquivo: self._sha_do_arquivo(alvo),
            )
            if decisao.entra_no_pacote or anterior is None:
                entram.append(arquivo)
            else:
                ja_copiados.append((arcname, anterior))

        return entram, ja_copiados

    def _atualizar_catalogo(self, entradas: list[BackupEntry], started_at: datetime) -> None:
        """
        Anota, no catalogo, que estes arquivos passaram a morar neste pacote.

        So depois de o pacote existir de verdade: registrar antes deixaria o
        catalogo apontando para um arquivo que a falha impediu de nascer, e o
        proximo backup pularia arquivos que nunca foram copiados.
        """
        if self.catalogo is None:
            return

        nome = self.destination.name
        self.catalogo.registrar_pacote(nome, started_at.isoformat(timespec="seconds"))
        for entrada in entradas:
            self.catalogo.registrar(
                entrada.arcname,
                tamanho=entrada.size_bytes,
                modificado_em=entrada.modificado_em_epoch,
                sha256=entrada.sha256,
                pacote=nome,
            )

    def _sha_do_arquivo(self, arquivo: Path) -> str:
        """SHA-256 de um arquivo, por pedacos."""
        digestor = hashlib.sha256()
        with arquivo.open("rb") as origem:
            while pedaco := origem.read(self._BUFFER_SIZE):
                digestor.update(pedaco)
        return digestor.hexdigest()

    def _andar(  # noqa: PLR0913 - a travessia carrega o estado dela junto
        self,
        *,
        pasta: Path,
        raiz: Path,
        incluidos: list[Path],
        excluidos: list[Path],
        links: list[LinkFound],
        pastas: list[Path],
        proibidos: set[Path],
        visitados: set[Path],
    ) -> None:
        """Uma pasta por vez, sem entrar em atalho e sem repetir caminho."""
        try:
            filhos = sorted(pasta.iterdir())
        except OSError:  # pragma: no cover - pasta sem permissao de listagem
            return

        for filho in filhos:
            if self._should_exclude(filho):
                excluidos.append(filho)
                continue

            if is_link(filho):
                links.append(self._descrever_link(filho, raiz))
                destino = self._resolvido(filho)
                # Mesmo com --seguir-links, um atalho que volta para onde ja
                # estivemos e ignorado: e o que impede a repeticao infinita.
                if self.follow_links and destino not in visitados:
                    self._descer_no_link(
                        filho,
                        raiz=raiz,
                        incluidos=incluidos,
                        excluidos=excluidos,
                        links=links,
                        pastas=pastas,
                        proibidos=proibidos,
                        visitados=visitados | {destino},
                    )
                continue

            if filho.is_dir():
                real = self._resolvido(filho)
                if real in visitados:  # pragma: no cover - so com link
                    continue
                pastas.append(filho)
                self._andar(
                    pasta=filho,
                    raiz=raiz,
                    incluidos=incluidos,
                    excluidos=excluidos,
                    links=links,
                    pastas=pastas,
                    proibidos=proibidos,
                    visitados=visitados | {real},
                )
            elif filho.is_file():
                if self._resolvido(filho) in proibidos:
                    excluidos.append(filho)
                else:
                    incluidos.append(filho)

    def _descer_no_link(  # noqa: PLR0913 - repassa o estado da travessia
        self,
        filho: Path,
        *,
        raiz: Path,
        incluidos: list[Path],
        excluidos: list[Path],
        links: list[LinkFound],
        pastas: list[Path],
        proibidos: set[Path],
        visitados: set[Path],
    ) -> None:
        """Entra no alvo de um atalho — so acontece com `--seguir-links`."""
        if filho.is_dir():
            pastas.append(filho)
            self._andar(
                pasta=filho,
                raiz=raiz,
                incluidos=incluidos,
                excluidos=excluidos,
                links=links,
                pastas=pastas,
                proibidos=proibidos,
                visitados=visitados,
            )
        elif filho.is_file():
            incluidos.append(filho)

    def _descrever_link(self, filho: Path, raiz: Path) -> LinkFound:
        """Registra o atalho: onde esta, para onde vai, e se saiu da origem."""
        destino = self._resolvido(filho)
        try:
            fora = not destino.is_relative_to(self._resolvido(raiz))
        except (OSError, ValueError):  # pragma: no cover - caminho estranho
            fora = True

        if self.follow_links:
            motivo = (
                "atalho SEGUIDO por --seguir-links; o alvo esta FORA da origem"
                if fora
                else "atalho seguido por --seguir-links"
            )
        else:
            motivo = (
                "atalho nao seguido: o alvo esta fora da origem escolhida"
                if fora
                else "atalho nao seguido (use --seguir-links para incluir o conteudo)"
            )

        return LinkFound(
            arcname=self._arcname_de(filho, raiz),
            target=str(destino),
            followed=self.follow_links,
            outside_source=fora,
            reason=motivo,
        )

    def _arcname_de(self, caminho: Path, raiz: Path) -> str:
        """Caminho relativo a origem, no formato do ZIP."""
        try:
            return (Path(raiz.name) / caminho.relative_to(raiz)).as_posix()
        except ValueError:  # pragma: no cover - defesa
            return caminho.name

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

    def _build_package(  # noqa: PLR0913 — cada parametro e uma parte do
        # pacote (conteudo, nomes, data, atalhos, pastas vazias, referencias
        # do incremental). Agrupa-los esconderia o que o pacote carrega.
        self,
        files: list[Path],
        arcnames: dict[Path, str],
        started_at: datetime,
        *,
        links: list[LinkFound],
        pastas: list[Path],
        ja_copiados: list[tuple[str, mod_catalogo.Anterior]] | None = None,
    ) -> tuple[list[BackupEntry], list[UnreadableFile]]:
        """
        Monta o pacote no arquivo temporario.

        Grava sempre em `.parcial`: o caminho final so passa a existir depois
        que o ZIP fecha inteiro. Assim, queda de energia ou disco cheio nao
        deixam um pacote pela metade com cara de completo.

        Com senha configurada, o pacote sai cifrado em AES-256 no padrao
        WinZip — inclusive o manifesto e a assinatura, que sao entradas como
        as outras.
        """
        entradas: list[BackupEntry] = []
        ilegiveis: list[UnreadableFile] = []

        senha = cifra.senha_configurada()
        try:
            with cifra.abrir_para_escrita(self.partial_path, senha) as zf:
                for arquivo in files:
                    arcname = arcnames[arquivo]
                    try:
                        entradas.append(self._escrever(zf, arquivo, arcname))
                    except OSError as exc:
                        # Travado pelo Excel, sem permissao, ou sumiu entre a
                        # listagem e a gravacao. Nada disso pode derrubar o
                        # backup inteiro — vira ressalva.
                        ilegiveis.append(UnreadableFile(arcname, _motivo(exc)))

                self._escrever_pastas_vazias(zf, arcnames, pastas)
                manifesto = self._manifesto(
                    entradas,
                    ilegiveis,
                    started_at,
                    links=links,
                    ja_copiados=ja_copiados or [],
                ).encode("utf-8")
                zf.writestr(MANIFEST_NAME, manifesto)
                self._assinar(zf, manifesto)
        except OSError:
            self._discard_partial()
            raise

        return entradas, ilegiveis

    def _assinar(self, zf: zipfile.ZipFile, manifesto: bytes) -> None:
        """
        Assina o manifesto, quando ha chave configurada.

        Assinar e opcional de proposito: sem chave, o pacote continua util e a
        conferencia diz que a autenticidade nao foi comprovada. Recusar-se a
        fazer backup por falta de chave trocaria um risco por outro pior — o
        de nao ter copia nenhuma.
        """
        chave = assinatura.chave_configurada()
        if chave is None:
            return
        zf.writestr(assinatura.NOME_ASSINATURA, assinatura.assinar(manifesto, chave))

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
        info = cifra.nova_entrada(zf, arcname, _data_do_zip(st.st_mtime))

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
            modificado_em_epoch=st.st_mtime,
        )

    def _escrever_pastas_vazias(
        self, zf: zipfile.ZipFile, arcnames: dict[Path, str], pastas: list[Path]
    ) -> None:
        """
        Preserva pastas que ficaram sem nenhum arquivo.

        Sem isto, a estrutura volta incompleta na restauracao — e ha sistema
        que simplesmente nao inicia se a pasta esperada nao existe.

        A lista de pastas vem da travessia, nao de um `rglob` novo: repetir a
        varredura entraria de novo nas junções que acabamos de evitar.
        """
        com_conteudo = {
            pai for arcname in arcnames.values() for pai in Path(arcname).parents if str(pai) != "."
        }
        raizes = self._nomes_das_fontes()
        for pasta in pastas:
            fonte = next((s for s in self.sources if self._sob(pasta, s)), None)
            if fonte is None:  # pragma: no cover - defesa
                continue
            relativo = Path(raizes[fonte]) / pasta.relative_to(fonte)
            if relativo not in com_conteudo:
                zf.mkdir(relativo.as_posix())

    @staticmethod
    def _sob(caminho: Path, fonte: Path) -> bool:
        """`caminho` esta dentro de `fonte`, pelo caminho literal?"""
        try:
            caminho.relative_to(fonte)
        except ValueError:
            return False
        return True

    def _manifesto(
        self,
        entradas: list[BackupEntry],
        ilegiveis: list[UnreadableFile],
        started_at: datetime,
        *,
        links: list[LinkFound],
        ja_copiados: list[tuple[str, mod_catalogo.Anterior]] | None = None,
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
        writer.writerow(["# inalterados", len(ja_copiados or [])])
        writer.writerow(["# nao_lidos", len(ilegiveis)])
        writer.writerow(["# atalhos", len(links)])
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
        # Linha INALTERADO: o arquivo NAO esta neste pacote, e o `motivo`
        # diz em qual ele esta. E o que torna a restauracao possivel — sem
        # esta referencia, o incremental produziria pacotes que ninguem
        # consegue juntar de volta.
        for arcname, anterior in ja_copiados or []:
            writer.writerow(
                [
                    "INALTERADO",
                    arcname,
                    anterior.tamanho,
                    "",
                    anterior.sha256,
                    f"esta em {anterior.pacote}",
                ]
            )
        for ilegivel in ilegiveis:
            writer.writerow(["NAO_LIDO", ilegivel.arcname, "", "", "", ilegivel.reason])
        # O DESTINO do atalho entra aqui de proposito: e a unica informacao
        # que responde "o que eu deixei de copiar, e de onde?". E o unico
        # caminho absoluto que o manifesto carrega.
        for link in links:
            situacao = "LINK_SEGUIDO" if link.followed else "LINK_IGNORADO"
            writer.writerow([situacao, link.arcname, "", "", link.target, link.reason])
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
    unchanged: tuple[str, ...] = ()
    """Estao num pacote ANTERIOR, nao neste. Backup incremental."""
    chain: tuple[str, ...] = ()
    """Pacotes anteriores que este pacote referencia. Sem eles, a restauracao
    fica incompleta — e isso precisa aparecer, nao ser descoberto na hora."""
    problem: str = ""
    """Preenchido quando o pacote nem pode ser aberto."""
    authenticity: assinatura.Autenticidade = assinatura.Autenticidade.NAO_ASSINADO
    """Integridade e autenticidade sao perguntas diferentes; esta e a segunda."""
    encrypted: bool = False
    """O conteudo do pacote esta cifrado?"""

    @property
    def signed(self) -> bool:
        """O pacote traz assinatura?"""
        return self.authenticity is not assinatura.Autenticidade.NAO_ASSINADO

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
            "assinado": self.signed,
            "autenticidade": self.authenticity.value,
            "limite": assinatura.EXPLICACAO[self.authenticity],
            "incremental": bool(self.unchanged),
            "inalterados": list(self.unchanged),
            "pacotes_anteriores": list(self.chain),
            "cifrado": self.encrypted,
            "limite_cifra": (
                cifra.EXPLICACAO_CIFRADO if self.encrypted else cifra.EXPLICACAO_SEM_CIFRA
            ),
        }


#: Colunas minimas de uma linha util do manifesto (situacao + arquivo).
_COLUNAS_MINIMAS = 2

#: Posicao do sha256 na linha do manifesto.
_COLUNA_SHA = 4

#: Posicao do motivo. Em linha INALTERADO, e onde o pacote anterior e
#: nomeado — a referencia que torna a restauracao possivel.
_COLUNA_MOTIVO = 5


def _ler_manifesto(
    zf: zipfile.ZipFile,
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """
    (sha256 por arquivo, nao lidos na origem, inalterados -> pacote onde estao).

    `INALTERADO` e o que o backup incremental grava: o arquivo NAO esta neste
    pacote, e a linha diz em qual ele esta. Tratar essas linhas como
    "declarado e ausente" faria todo pacote incremental parecer defeituoso.
    """
    esperado: dict[str, str] = {}
    nao_lidos: list[str] = []
    inalterados: dict[str, str] = {}
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
        elif linha[0] == "INALTERADO":
            inalterados[linha[1]] = linha[_COLUNA_MOTIVO] if len(linha) > _COLUNA_MOTIVO else ""
    return esperado, nao_lidos, inalterados


def _impedimento_de_conferir(zf: zipfile.ZipFile, senha: bytes | None) -> str:
    """
    Motivo para nem comecar a conferir. Vazio quando da para seguir.

    Os tres casos sao diferentes para quem le, e por isso nao viram uma
    mensagem so: "informe a senha" pede uma acao, "corrompido" pede outra, e
    "sem manifesto" diz que este pacote nem veio daqui.
    """
    if cifra.esta_cifrado(zf) and senha is None:
        return f"pacote cifrado: informe a senha em {cifra.VAR_SENHA} para conferir o conteudo"
    if zf.testzip() is not None:
        return "o pacote esta corrompido (CRC)"
    if MANIFEST_NAME not in zf.namelist():
        return (
            f"pacote sem {MANIFEST_NAME}: nao da para conferir o conteudo "
            "(foi gerado por outra ferramenta ou por uma versao antiga)"
        )
    return ""


def verify_backup(path: Path, *, buffer_size: int = 64 * 1024) -> VerifyReport:
    """
    Confere um pacote gerado pelo `BackupTask`, sem precisar dos originais.

    Tres perguntas, nesta ordem:

    1. o ZIP abre e todas as entradas passam no CRC?
    2. cada arquivo tem o mesmo SHA-256 que o manifesto declarou?
    3. o que o manifesto diz que existe realmente esta la — e vice-versa?

    Um backup que ninguem confere e fe, nao garantia. Com isto, da para
    conferir de tempos em tempos, ANTES do dia em que ele e necessario.

    E uma quarta, quando o pacote foi assinado: a assinatura do manifesto
    confere com a chave externa? Sem assinatura, o limite antigo continua
    valendo por inteiro — quem alterar um arquivo e recalcular o manifesto
    passa despercebido, porque a chave da conferencia viaja dentro do proprio
    pacote. Com assinatura, esse caminho fecha: recalcular o manifesto nao
    produz uma assinatura valida para quem nao tem a chave.

    O desfecho da assinatura vem em `authenticity`, e a frase que o acompanha
    em `as_dict()["limite"]` — sempre junto do resultado, para que nenhum
    "integro" apareca sozinho prometendo mais do que provou.
    """
    if not path.is_file():
        return VerifyReport(path=path, ok=False, checked=0, problem="arquivo nao encontrado")

    try:
        senha = cifra.senha_configurada()
        with cifra.abrir_para_leitura(path, senha) as zf:
            impedimento = _impedimento_de_conferir(zf, senha)
            if impedimento:
                return VerifyReport(path=path, ok=False, checked=0, problem=impedimento)

            esperado, nao_lidos, inalterados = _ler_manifesto(zf)
            # O manifesto e a assinatura sao metadados do proprio pacote: nao
            # constam do manifesto, e listar os dois como "nao declarados"
            # faria todo pacote assinado parecer defeituoso.
            metadados = {MANIFEST_NAME, assinatura.NOME_ASSINATURA}
            presentes = {
                nome for nome in zf.namelist() if nome not in metadados and not nome.endswith("/")
            }

            corrompidos = [
                arcname
                for arcname, sha in esperado.items()
                if arcname in presentes and _sha_da_entrada(zf, arcname, buffer_size) != sha
            ]
            faltando = sorted(set(esperado) - presentes)
            inesperados = sorted(presentes - set(esperado))
            autenticidade = _conferir_assinatura(zf)
            cifrado = cifra.esta_cifrado(zf)
    except RuntimeError as exc:
        # `RuntimeError` e o que o zipfile levanta para senha errada. Traduzir
        # aqui evita que a pessoa receba "Bad password for file" no lugar de
        # uma frase que diz o que fazer.
        return VerifyReport(
            path=path,
            ok=False,
            checked=0,
            problem=f"nao foi possivel abrir o pacote cifrado (senha incorreta?): {exc}",
        )
    except cifra.SenhaFraca as exc:
        return VerifyReport(path=path, ok=False, checked=0, problem=str(exc))
    except cifra.ERROS_DE_PACOTE as exc:
        return VerifyReport(
            path=path, ok=False, checked=0, problem=f"nao foi possivel abrir: {exc}"
        )

    # Assinatura que nao confere derruba o pacote, mesmo com todos os hashes
    # batendo: hash conferindo com manifesto recalculado e exatamente o cenario
    # da adulteracao intencional. Ja `SEM_CHAVE` nao derruba nada — significa
    # que a autenticidade nao pode ser avaliada aqui, e nao que ha problema.
    suspeito = autenticidade in {
        assinatura.Autenticidade.ADULTERADO,
        assinatura.Autenticidade.OUTRA_CHAVE,
    }

    return VerifyReport(
        path=path,
        ok=not (corrompidos or faltando or inesperados or suspeito),
        checked=len(esperado),
        corrupted=tuple(corrompidos),
        missing=tuple(faltando),
        unexpected=tuple(inesperados),
        unreadable_at_origin=tuple(nao_lidos),
        authenticity=autenticidade,
        encrypted=cifrado,
        unchanged=tuple(sorted(inalterados)),
        chain=tuple(sorted(_pacotes_referenciados(inalterados))),
    )


def _pacotes_referenciados(inalterados: dict[str, str]) -> set[str]:
    """
    Quais pacotes anteriores este manifesto cita.

    O motivo da linha tem a forma "esta em <pacote>". Extrair o nome permite
    dizer a quem restaura EXATAMENTE quais arquivos ele precisa ter em maos.
    """
    pacotes: set[str] = set()
    for motivo in inalterados.values():
        _, separador, nome = motivo.partition("esta em ")
        if separador and nome.strip():
            pacotes.add(nome.strip())
    return pacotes


def _conferir_assinatura(zf: zipfile.ZipFile) -> assinatura.Autenticidade:
    """Confere a assinatura do manifesto, se o pacote tiver uma."""
    if assinatura.NOME_ASSINATURA not in zf.namelist():
        return assinatura.Autenticidade.NAO_ASSINADO
    try:
        chave = assinatura.chave_configurada()
    except assinatura.ChaveInvalida:
        # Chave configurada mas ilegivel e o mesmo que nao ter chave: da para
        # conferir integridade, nao autenticidade.
        chave = None
    return assinatura.conferir(
        zf.read(assinatura.NOME_ASSINATURA).decode("utf-8"),
        zf.read(MANIFEST_NAME),
        chave,
    )


def _sha_da_entrada(zf: zipfile.ZipFile, arcname: str, buffer_size: int) -> str:
    h = hashlib.sha256()
    with zf.open(arcname) as entrada:
        while chunk := entrada.read(buffer_size):
            h.update(chunk)
    return h.hexdigest()


def corrente_de(pacote: Path) -> list[Path]:
    """
    Pacotes de que este depende, do mais proximo para o mais distante.

    Um pacote incremental nao se sustenta sozinho: o manifesto dele cita, para
    cada arquivo inalterado, em qual pacote anterior o conteudo esta. Quem for
    restaurar precisa da corrente inteira — e quem for **apagar** precisa saber
    que ela existe.

    So entram os que ainda estao no disco, ao lado do pacote. Um citado que
    sumiu nao vira excecao: a restauracao relata o que faltou, o que e mais util
    do que recusar tudo por causa de um arquivo antigo.
    """
    pasta = pacote.parent
    encontrados: list[Path] = []
    vistos = {pacote.name}
    fila = [pacote]

    while fila:
        atual = fila.pop(0)
        try:
            relatorio = verify_backup(atual)
        except (OSError, ValueError, zipfile.BadZipFile):
            # Pacote ilegivel no meio da corrente. Nao e motivo para desistir:
            # o que der para recuperar continua valendo.
            continue
        for nome in relatorio.chain:
            if nome in vistos:
                continue
            vistos.add(nome)
            anterior = pasta / nome
            if anterior.is_file():
                encontrados.append(anterior)
                fila.append(anterior)

    return encontrados


__all__ = [
    "MANIFEST_NAME",
    "PARTIAL_SUFFIX",
    "BackupEntry",
    "BackupTask",
    "UnreadableFile",
    "VerifyReport",
    "corrente_de",
    "rotate_backups",
    "timestamped_name",
    "verify_backup",
]
