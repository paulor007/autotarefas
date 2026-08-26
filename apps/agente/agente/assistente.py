"""A instalacao vista como decisoes, sem janela nenhuma.

O cliente do AutoTarefas nao abre terminal. Ele da um duplo clique, responde
duas perguntas e vai embora. Este modulo e o que acontece por baixo desse duplo
clique — e ele existe separado da janela por um motivo pratico: janela nao se
testa bem, decisao se testa.

Os quatro passos, na ordem em que a pessoa os vive:

1. **parear** — a maquina se registra na organizacao com o codigo temporario;
2. **conferir a impressao** — a pessoa compara o que apareceu aqui com o que
   aparece no Live. E o unico momento em que ela precisa olhar duas telas, e
   nao da para evitar: e o que impede um servidor comprometido de se passar
   pela maquina dela;
3. **autorizar a pasta** — escolhida no seletor do Windows, gravada AQUI. A
   regra nao muda por ser bonita agora: nenhuma tela na nuvem concede acesso ao
   disco de ninguem;
4. **deixar rodando** — registra no Agendador e sobe o servico na hora, para a
   maquina aparecer conectada antes de a pessoa fechar a janela.

Cada passo devolve um `Passo`, com `ok` e uma frase que uma pessoa entende.
Nenhum deles levanta excecao para cima: um instalador que mostra `Traceback` ja
falhou, mesmo que o erro fosse informativo.
"""

from __future__ import annotations

import subprocess  # nosec B404 — sobe o proprio servico, com argumentos fixos
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import identidade as ident
from . import instalacao, pareamento, raizes
from .config import Local


@dataclass(frozen=True)
class Passo:
    """O que aconteceu num passo, do jeito que a janela vai mostrar."""

    ok: bool
    mensagem: str
    #: Detalhe secundario: a impressao digital, o caminho autorizado, o modo do
    #: servico. Vazio quando nao ha o que acrescentar.
    detalhe: str = ""

    def como_dicionario(self) -> dict[str, object]:
        return {"ok": self.ok, "mensagem": self.mensagem, "detalhe": self.detalhe}


@dataclass
class Assistente:
    """
    A instalacao inteira, passo a passo.

    Guarda o que ja aconteceu para a janela poder perguntar — e para o resumo
    final dizer a verdade sobre o que ficou de fora.
    """

    local: Local
    guarda: ident.Guarda
    servidor: str = ""
    codigo: str = ""
    nome_da_maquina: str = ""

    impressao: str = ""
    pastas: list[str] = field(default_factory=list)
    sobe_sozinho: bool = False
    rodando: bool = False

    # --------------------------------------------------------
    # 1. Parear
    # --------------------------------------------------------

    def ja_pareado(self) -> bool:
        """
        Esta maquina ja pertence a uma organizacao?

        Perguntado antes de tudo: reinstalar por cima de um pareamento existente
        criaria um segundo dispositivo para a mesma maquina, e o historico da
        empresa passaria a ter duas linhas para um computador so.
        """
        return self.local.carregar().pareado

    def parear(self) -> Passo:
        """Registra esta maquina na organizacao, com o codigo temporario."""
        if not self.servidor:
            return Passo(False, "Falta o endereco do Live.")
        if not self.codigo:
            return Passo(False, "Falta o codigo de pareamento. Ele aparece no Live.")

        try:
            resultado = pareamento.parear(
                servidor=self.servidor,
                codigo=self.codigo,
                guarda=self.guarda,
                local=self.local,
                nome=self.nome_da_maquina,
            )
        except pareamento.PareamentoFalhou as erro:
            return Passo(False, _em_portugues(str(erro)))

        self.impressao = resultado.impressao
        return Passo(
            True,
            f"{resultado.nome} foi registrado.",
            f"Impressao digital: {resultado.impressao}",
        )

    # --------------------------------------------------------
    # 2. Autorizar a pasta
    # --------------------------------------------------------

    def autorizar(self, pasta: Path) -> Passo:
        """
        Libera uma pasta para o Agente ler. So aqui, nesta maquina.

        Passa pela mesma guarda do comando de linha: pasta de sistema, raiz de
        volume e caminho que nao resolve continuam recusados. O seletor bonito
        nao afrouxa nada — ele so poupa a pessoa de digitar.
        """
        try:
            configuracao = raizes.autorizar(self.local, pasta)
        except raizes.AutorizacaoRecusada as erro:
            return Passo(False, str(erro))

        self.pastas = list(configuracao.raizes)
        return Passo(
            True,
            f"{pasta.name} sera protegida.",
            f"{len(self.pastas)} pasta(s) autorizada(s) nesta maquina.",
        )

    # --------------------------------------------------------
    # 3. Deixar rodando
    # --------------------------------------------------------

    def instalar_servico(self) -> Passo:
        """
        Registra o Agente para subir junto com o Windows.

        Falhar aqui **nao** invalida a instalacao: o pareamento e a pasta
        continuam valendo, e o backup ainda pode ser disparado pelo Live. O que
        se perde e o horario — e isso e dito, em vez de virar um "instalado" que
        nao instalou o que importa.
        """
        try:
            resultado = instalacao.instalar(
                comando=_comando_do_servico(self.local.pasta),
                pasta_de_configuracao=self.local.pasta,
            )
        except instalacao.InstalacaoRecusada as erro:
            return Passo(
                False,
                "Nao consegui deixar o Agente ligado sozinho.",
                f"{erro} O backup agendado nao vai acontecer ate isso ser resolvido.",
            )

        self.sobe_sozinho = True
        return Passo(True, "O Agente vai subir junto com o Windows.", resultado.detalhe)

    def iniciar_agora(self) -> Passo:
        """
        Sobe o servico neste instante, sem esperar o proximo login.

        Sem isto, a maquina so apareceria conectada no Live depois de a pessoa
        reiniciar — e ela fecharia o instalador achando que algo deu errado.
        """
        try:
            subprocess.Popen(  # noqa: S603  # nosec B603 — argumentos montados aqui
                _argumentos_do_servico(self.local.pasta),
                creationflags=_SEM_JANELA,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as erro:
            return Passo(
                False,
                "Nao consegui iniciar o Agente agora.",
                f"{erro} Ele vai subir no proximo login.",
            )

        self.rodando = True
        return Passo(True, "O Agente esta no ar.", "A maquina ja aparece no Live.")

    # --------------------------------------------------------
    # Resumo
    # --------------------------------------------------------

    def resumo(self) -> Passo:
        """
        O que ficou pronto, e o que nao ficou.

        A frase muda conforme o que **de fato** aconteceu. Um instalador que
        termina sempre com "tudo certo" nao informa nada, e a primeira madrugada
        sem backup pega a pessoa de surpresa.
        """
        if not self.pastas:
            return Passo(
                False,
                "Falta escolher a pasta a proteger.",
                "Sem pasta autorizada, este computador nao copia nada.",
            )
        if not self.sobe_sozinho:
            return Passo(
                False,
                "Instalado, mas sem horario.",
                "O backup so vai acontecer quando alguem mandar pelo Live.",
            )
        return Passo(
            True,
            "Pronto. Este computador esta protegido.",
            f"{len(self.pastas)} pasta(s) · backup no horario, mesmo com o navegador fechado.",
        )


#: `CREATE_NO_WINDOW`, para o servico nao piscar um console preto na cara da
#: pessoa. Fora do Windows o valor nao existe, e zero significa "sem sinalizador".
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _argumentos_do_servico(configuracao: Path) -> list[str]:
    """
    Como subir o servico a partir de onde este processo esta rodando.

    Congelado (o `.exe` do cliente), o proprio executavel sabe rodar em modo
    servico. Rodando do codigo, e o Python atual com o modulo — que e o caminho
    de quem desenvolve.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--servico", "--pasta-de-configuracao", str(configuracao)]
    return [
        sys.executable,
        "-m",
        "apps.agente.agente",
        "servico",
        "--pasta-de-configuracao",
        str(configuracao),
    ]


def _comando_do_servico(configuracao: Path) -> str:
    """A mesma coisa, na forma de uma linha para o Agendador de Tarefas."""
    argumentos = _argumentos_do_servico(configuracao)
    return " ".join(f'"{parte}"' if " " in parte else parte for parte in argumentos)


def _em_portugues(erro: str) -> str:
    """
    Traduz a recusa do servidor para algo que diga o que fazer.

    "403" nao ajuda ninguem. "O codigo venceu, gere outro no Live" ajuda — e a
    diferenca entre as duas frases e a diferenca entre resolver sozinho e ligar
    para o suporte.
    """
    baixo = erro.lower()
    if "codigo" in baixo and ("venc" in baixo or "expir" in baixo):
        return "Este codigo ja venceu. Gere outro no Live e tente de novo."
    if "codigo" in baixo and ("usado" in baixo or "invalid" in baixo):
        return "Este codigo nao vale mais. Gere outro no Live e tente de novo."
    if "conex" in baixo or "connect" in baixo or "resolve" in baixo:
        return "Nao consegui falar com o Live. Confira o endereco e a internet."
    return erro


__all__ = ["Assistente", "Passo"]
