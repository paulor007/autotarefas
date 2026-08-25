"""Restauração: tirar os arquivos de volta do pacote.

É o único momento em que o backup prova que serviu para alguma coisa. Tudo o
que veio antes — manifesto, assinatura, cifra, retenção — existe para que este
passo funcione no pior dia possível, quando o original já não existe.

Quatro regras, e nenhuma é opcional:

1. **Conferir antes de escrever.** Pacote corrompido é recusado inteiro, e não
   restaurado "até onde deu". Restauração parcial silenciosa é pior do que
   nenhuma: a pessoa acha que recuperou tudo.
2. **Nunca sair da pasta de destino.** Um pacote pode conter `..\\..\\Windows`
   ou `C:\\Windows\\System32`. O ZIP é um formato de arquivo, não um contrato
   de confiança — e um pacote pode ter vindo de qualquer lugar.
3. **Nunca sobrescrever sem permissão.** Restaurar por cima do que existe é
   uma decisão de quem está ali, não do programa. O padrão preserva.
4. **Conferir depois de escrever.** O SHA-256 do arquivo restaurado é
   comparado com o do manifesto. Um disco com defeito escreve bytes errados
   sem reclamar.

Pacote **incremental** não se sustenta sozinho: os arquivos marcados como
`INALTERADO` estão em pacotes anteriores. A restauração segue essa corrente
quando os pacotes estão à mão, e **diz o que falta** quando não estão — em vez
de restaurar pela metade e chamar de sucesso.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from autotarefas.tasks import assinatura as mod_assinatura
from autotarefas.tasks import cifra as mod_cifra
from autotarefas.tasks.backup import MANIFEST_NAME, verify_backup

#: Buffer de leitura e escrita. O mesmo motivo do backup: arquivo grande não
#: pode passar pela memória.
BUFFER = 1024 * 1024

#: Nomes que nunca são restaurados: são metadados do pacote, não conteúdo.
METADADOS = frozenset({MANIFEST_NAME, mod_assinatura.NOME_ASSINATURA})


class RestauracaoRecusada(Exception):
    """Não dá para restaurar, e a mensagem diz por quê."""


@dataclass
class Relatorio:
    """O que a restauração fez, e o que não fez."""

    destino: Path
    restaurados: list[str] = field(default_factory=list)
    ja_existiam: list[str] = field(default_factory=list)
    """Preservados porque `sobrescrever` estava desligado."""
    recusados: list[str] = field(default_factory=list)
    """Caminhos que tentavam sair da pasta de destino."""
    faltando: list[str] = field(default_factory=list)
    """Estão em pacotes anteriores que não foram informados."""
    corrompidos: list[str] = field(default_factory=list)
    """O conteúdo restaurado não bateu com o manifesto."""

    @property
    def completa(self) -> bool:
        """
        A restauração entregou tudo o que o pacote prometia?

        `ja_existiam` não conta como falha: preservar foi a escolha de quem
        pediu. `faltando` e `corrompidos` contam, e por isso aparecem.
        """
        return not (self.faltando or self.corrompidos or self.recusados)

    def as_dict(self) -> dict[str, object]:
        return {
            "destino": self.destino.name,
            "restaurados": len(self.restaurados),
            "ja_existiam": self.ja_existiam,
            "recusados": self.recusados,
            "faltando": self.faltando,
            "corrompidos": self.corrompidos,
            "completa": self.completa,
        }


@dataclass(frozen=True)
class Declarado:
    """O que o manifesto diz sobre um arquivo."""

    arcname: str
    sha256: str
    #: Vazio quando o arquivo está NESTE pacote; senão, o nome do anterior.
    pacote_anterior: str = ""


def _ler_declaracoes(zf: zipfile.ZipFile) -> list[Declarado]:
    """Lê do manifesto o que este pacote promete entregar."""
    texto = zf.read(MANIFEST_NAME).decode("utf-8")
    declarados: list[Declarado] = []
    for linha in csv.reader(io.StringIO(texto)):
        if len(linha) < 2 or linha[0] in {"situacao", ""} or linha[0].startswith("#"):  # noqa: PLR2004
            continue
        if linha[0] == "incluido":
            declarados.append(Declarado(arcname=linha[1], sha256=linha[4]))
        elif linha[0] == "INALTERADO":
            motivo = linha[5] if len(linha) > 5 else ""  # noqa: PLR2004
            _, _, nome = motivo.partition("esta em ")
            declarados.append(
                Declarado(arcname=linha[1], sha256=linha[4], pacote_anterior=nome.strip())
            )
    return declarados


def caminho_seguro(destino: Path, arcname: str) -> Path | None:
    """
    Onde este arquivo pode ser escrito — ou `None` se ele tenta escapar.

    O ZIP é um formato de arquivo, não um contrato de confiança: um pacote
    pode ter vindo de qualquer lugar e conter `..\\..\\Windows\\System32` ou um
    caminho absoluto. Resolver e comparar com a pasta de destino é a única
    defesa que não depende de o nome "parecer" seguro.
    """
    normalizado = arcname.replace("\\", "/")
    bruto = PurePosixPath(normalizado)
    # `PurePosixPath` nao enxerga `C:` como disco — para ele e so um nome de
    # pasta. Sem a checagem no estilo Windows, `C:/Windows/System32/...`
    # passaria pela primeira barreira.
    janela = PureWindowsPath(normalizado)
    if (
        bruto.is_absolute()
        or bruto.drive
        or janela.is_absolute()
        or janela.drive
        or any(parte == ".." for parte in bruto.parts)
        or any(parte.endswith(":") for parte in bruto.parts)
    ):
        return None

    alvo = (destino / Path(*bruto.parts)).resolve()
    raiz = destino.resolve()
    if alvo != raiz and raiz not in alvo.parents:
        return None
    return alvo


def _extrair(zf: zipfile.ZipFile, arcname: str, alvo: Path) -> str:
    """
    Escreve o arquivo e devolve o SHA-256 do que foi escrito de verdade.

    O hash é calculado sobre o que SAIU da leitura, não sobre o que se
    esperava: é assim que um disco com defeito, que aceita a escrita e guarda
    outra coisa, é pego.
    """
    alvo.parent.mkdir(parents=True, exist_ok=True)
    parcial = alvo.with_suffix(alvo.suffix + ".parcial")
    digestor = hashlib.sha256()

    try:
        with zf.open(arcname) as origem, parcial.open("wb") as saida:
            while pedaco := origem.read(BUFFER):
                digestor.update(pedaco)
                saida.write(pedaco)
        os.replace(parcial, alvo)
    except OSError:
        parcial.unlink(missing_ok=True)
        raise

    return digestor.hexdigest()


def _conferir_pacote(caminho: Path) -> None:
    """Recusa o pacote inteiro quando ele não confere."""
    relatorio = verify_backup(caminho)
    if relatorio.problem:
        msg = f"{caminho.name}: {relatorio.problem}"
        raise RestauracaoRecusada(msg)
    if not relatorio.ok:
        detalhes = []
        if relatorio.corrupted:
            detalhes.append(f"{len(relatorio.corrupted)} arquivo(s) com conteudo diferente")
        if relatorio.authenticity in {
            mod_assinatura.Autenticidade.ADULTERADO,
            mod_assinatura.Autenticidade.OUTRA_CHAVE,
        }:
            detalhes.append(mod_assinatura.EXPLICACAO[relatorio.authenticity])
        msg = (
            f"{caminho.name} nao confere e nao sera restaurado: "
            f"{'; '.join(detalhes) or 'conteudo diferente do manifesto'}"
        )
        raise RestauracaoRecusada(msg)


def restaurar(
    pacote: Path,
    destino: Path,
    *,
    anteriores: list[Path] | None = None,
    apenas: list[str] | None = None,
    sobrescrever: bool = False,
) -> Relatorio:
    """
    Restaura o conteúdo do pacote na pasta de destino.

    `anteriores` são os pacotes que a corrente do incremental exige. O que não
    for encontrado neles entra em `faltando` — restaurar pela metade e chamar
    de sucesso seria a pior forma de falhar aqui.

    `apenas` restaura um subconjunto (restauração de amostra, que é como se
    testa um backup sem mexer no que está em produção).
    """
    if not pacote.is_file():
        msg = f"pacote nao encontrado: {pacote.name}"
        raise RestauracaoRecusada(msg)

    _conferir_pacote(pacote)
    for anterior in anteriores or []:
        _conferir_pacote(anterior)

    destino.mkdir(parents=True, exist_ok=True)
    relatorio = Relatorio(destino=destino)
    senha = mod_cifra.senha_configurada()
    filtro = set(apenas) if apenas else None

    with mod_cifra.abrir_para_leitura(pacote, senha) as zf:
        declaracoes = [
            item
            for item in _ler_declaracoes(zf)
            if item.arcname not in METADADOS and (filtro is None or item.arcname in filtro)
        ]
        _restaurar_deste_pacote(zf, declaracoes, destino, relatorio, sobrescrever=sobrescrever)

    pendentes = [item for item in declaracoes if item.pacote_anterior]
    if pendentes:
        _restaurar_da_corrente(
            pendentes, anteriores or [], destino, relatorio, sobrescrever=sobrescrever, senha=senha
        )

    return relatorio


def _restaurar_deste_pacote(
    zf: zipfile.ZipFile,
    declaracoes: list[Declarado],
    destino: Path,
    relatorio: Relatorio,
    *,
    sobrescrever: bool,
) -> None:
    presentes = set(zf.namelist())
    for item in declaracoes:
        if item.pacote_anterior or item.arcname not in presentes:
            continue
        _restaurar_um(zf, item, destino, relatorio, sobrescrever=sobrescrever)


def _restaurar_da_corrente(  # noqa: PLR0913 — cada parametro e uma parte
    # da decisao de restaurar: o que falta, onde procurar, para onde vai,
    # o que ja aconteceu, se pode sobrescrever e a senha do pacote.
    pendentes: list[Declarado],
    anteriores: list[Path],
    destino: Path,
    relatorio: Relatorio,
    *,
    sobrescrever: bool,
    senha: bytes | None,
) -> None:
    """
    Busca nos pacotes anteriores o que o incremental deixou lá.

    Um arquivo que não estiver em nenhum deles é registrado em `faltando`, com
    o nome do pacote que o manifesto aponta — para a pessoa saber exatamente
    qual arquivo procurar.
    """
    por_nome = {caminho.name: caminho for caminho in anteriores}
    for item in pendentes:
        origem = por_nome.get(item.pacote_anterior)
        if origem is None:
            relatorio.faltando.append(f"{item.arcname} (esta em {item.pacote_anterior})")
            continue
        with mod_cifra.abrir_para_leitura(origem, senha) as anterior_zf:
            if item.arcname not in set(anterior_zf.namelist()):
                relatorio.faltando.append(f"{item.arcname} (esta em {item.pacote_anterior})")
                continue
            _restaurar_um(anterior_zf, item, destino, relatorio, sobrescrever=sobrescrever)


def _restaurar_um(
    zf: zipfile.ZipFile,
    item: Declarado,
    destino: Path,
    relatorio: Relatorio,
    *,
    sobrescrever: bool,
) -> None:
    alvo = caminho_seguro(destino, item.arcname)
    if alvo is None:
        # Caminho que tenta sair da pasta. Recusado e REGISTRADO: um pacote
        # com caminho malicioso é informação sobre a origem dele, não um
        # detalhe para engolir em silêncio.
        relatorio.recusados.append(item.arcname)
        return

    if alvo.exists() and not sobrescrever:
        relatorio.ja_existiam.append(item.arcname)
        return

    escrito = _extrair(zf, item.arcname, alvo)
    if item.sha256 and escrito != item.sha256:
        # Um disco com defeito aceita a escrita e guarda outra coisa. Sem esta
        # conferência, a pessoa acharia que recuperou o arquivo.
        relatorio.corrompidos.append(item.arcname)
        alvo.unlink(missing_ok=True)
        return

    relatorio.restaurados.append(item.arcname)


def listar_conteudo(pacote: Path) -> list[dict[str, str]]:
    """
    O que há dentro do pacote, para a tela mostrar antes de restaurar.

    Escolher o que restaurar sem ver a lista seria escolher às cegas — e
    restauração às cegas costuma sobrescrever o que não devia.
    """
    if not pacote.is_file():
        msg = f"pacote nao encontrado: {pacote.name}"
        raise RestauracaoRecusada(msg)

    senha = mod_cifra.senha_configurada()
    with mod_cifra.abrir_para_leitura(pacote, senha) as zf:
        if MANIFEST_NAME not in zf.namelist():
            msg = f"{pacote.name} nao tem manifesto: nao da para listar com seguranca"
            raise RestauracaoRecusada(msg)
        declaracoes = _ler_declaracoes(zf)

    return [
        {
            "arquivo": item.arcname,
            "onde": item.pacote_anterior or pacote.name,
            "neste_pacote": "sim" if not item.pacote_anterior else "nao",
        }
        for item in declaracoes
        if item.arcname not in METADADOS
    ]


__all__ = [
    "BUFFER",
    "METADADOS",
    "Declarado",
    "Relatorio",
    "RestauracaoRecusada",
    "caminho_seguro",
    "listar_conteudo",
    "restaurar",
]
