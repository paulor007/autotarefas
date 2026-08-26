"""A janela do instalador: quatro telas, nenhum terminal.

Fina de proposito. Tudo que decide alguma coisa mora em `assistente.py`, que se
testa sem display; aqui so ficam os widgets e a ordem em que aparecem. Quando
uma janela concentra decisao, ela vira a parte do produto que ninguem consegue
verificar.

Usa `tkinter` porque ele vem junto com o Python — e o Python vem junto com o
executavel. Uma biblioteca grafica de fora somaria dezenas de megabytes ao
download para desenhar quatro telas com um botao cada.

O que a janela **nao** faz, e e proposital:

- nao pede elevacao;
- nao instala Python;
- nao pergunta o endereco do servidor quando o carimbo ja traz (e ele quase
  sempre traz: o download veio do Live de quem pediu);
- nao esconde o que deu errado atras de "ocorreu um erro".
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any

from . import carimbo, identidade
from .assistente import Assistente, Passo
from .config import Local

TITULO = "AutoTarefas — proteger este computador"
LARGURA = 560
ALTURA = 380


class Janela:
    """
    As quatro telas, na ordem em que a pessoa as vive.

    Cada passo demorado roda numa thread e devolve o resultado por uma fila: o
    `tkinter` congela se alguem trabalhar dentro do laco de eventos, e uma
    janela congelada durante o pareamento parece um programa travado.
    """

    def __init__(self, assistente: Assistente) -> None:
        self.assistente = assistente
        self.raiz = tk.Tk()
        self.raiz.title(TITULO)
        self.raiz.geometry(f"{LARGURA}x{ALTURA}")
        self.raiz.resizable(width=False, height=False)

        self.recados: queue.Queue[tuple[str, Passo]] = queue.Queue()
        self.corpo = ttk.Frame(self.raiz, padding=24)
        self.corpo.pack(fill="both", expand=True)

        self.raiz.after(100, self._drenar)

    # --------------------------------------------------------
    # Telas
    # --------------------------------------------------------

    def _limpar(self) -> None:
        for filho in self.corpo.winfo_children():
            filho.destroy()

    def _titulo(self, texto: str) -> None:
        ttk.Label(self.corpo, text=texto, font=("Segoe UI", 15, "bold")).pack(anchor="w")

    def _paragrafo(self, texto: str, *, cor: str = "") -> None:
        rotulo = ttk.Label(self.corpo, text=texto, wraplength=LARGURA - 60, justify="left")
        if cor:
            rotulo.configure(foreground=cor)
        rotulo.pack(anchor="w", pady=(8, 0))

    def _botao(self, texto: str, acao: Any, *, principal: bool = True) -> ttk.Button:
        estilo = "Accent.TButton" if principal else "TButton"
        botao = ttk.Button(self.corpo, text=texto, command=acao, style=estilo)
        botao.pack(anchor="w", pady=(20, 0))
        return botao

    def tela_apresentacao(self) -> None:
        """Primeira tela: o que vai acontecer, antes de acontecer."""
        self._limpar()
        self._titulo("Proteger este computador")
        self._paragrafo(
            "Vou registrar esta máquina na sua organização e escolher com você "
            "a pasta que será copiada. Depois disso o backup passa a acontecer "
            "no horário, sozinho — mesmo com o navegador fechado."
        )
        self._paragrafo(f"Servidor: {self.assistente.servidor or '(não informado)'}")

        if self.assistente.ja_pareado():
            self._paragrafo(
                "Este computador já está registrado. Instalar de novo criaria um "
                "segundo dispositivo para a mesma máquina.",
                cor="#b45309",
            )
            self._botao("Continuar mesmo assim", self._parear, principal=False)
            return

        if not self.assistente.servidor or not self.assistente.codigo:
            self._campos_manuais()
            return

        self._botao("Começar", self._parear)

    def _campos_manuais(self) -> None:
        """
        Só aparece quando o executável veio sem carimbo.

        É o caso de quem compilou por conta própria. O download feito pelo Live
        já traz endereço e código, e a pessoa não digita nada.
        """
        self._paragrafo("Este instalador veio sem os dados do seu Live. Informe-os:")

        servidor = tk.StringVar(value=self.assistente.servidor)
        codigo = tk.StringVar(value=self.assistente.codigo)
        for rotulo, variavel in (("Endereço do Live", servidor), ("Código de pareamento", codigo)):
            ttk.Label(self.corpo, text=rotulo).pack(anchor="w", pady=(10, 2))
            ttk.Entry(self.corpo, textvariable=variavel, width=52).pack(anchor="w")

        def começar() -> None:
            self.assistente.servidor = servidor.get().strip()
            self.assistente.codigo = codigo.get().strip()
            self._parear()

        self._botao("Começar", começar)

    def tela_pasta(self) -> None:
        """Segunda tela: a impressão para conferir, e a pasta a proteger."""
        self._limpar()
        self._titulo("Escolha a pasta a proteger")
        self._paragrafo(
            "Confira se esta impressão digital é a mesma que aparece no Live. "
            "É o que garante que esta máquina é esta máquina."
        )
        ttk.Label(self.corpo, text=self.assistente.impressao, font=("Consolas", 12, "bold")).pack(
            anchor="w", pady=(6, 0)
        )
        self._paragrafo(
            "A autorização é dada aqui, neste computador. Nenhuma tela na nuvem "
            "concede acesso ao seu disco."
        )

        aviso = ttk.Label(self.corpo, text="", wraplength=LARGURA - 60, justify="left")
        aviso.pack(anchor="w", pady=(10, 0))

        def escolher() -> None:
            escolhida = filedialog.askdirectory(title="Qual pasta você quer proteger?")
            if not escolhida:
                return
            passo = self.assistente.autorizar(Path(escolhida))
            aviso.configure(
                text=f"{passo.mensagem} {passo.detalhe}".strip(),
                foreground="#15803d" if passo.ok else "#b91c1c",
            )
            if passo.ok:
                self._botao("Concluir", self._instalar)

        self._botao("Procurar…", escolher)

    def tela_trabalhando(self, texto: str) -> None:
        self._limpar()
        self._titulo(texto)
        self._paragrafo("Isso leva alguns segundos.")
        barra = ttk.Progressbar(self.corpo, mode="indeterminate", length=LARGURA - 60)
        barra.pack(anchor="w", pady=(20, 0))
        barra.start(12)

    def tela_final(self, passo: Passo) -> None:
        """
        Última tela: o que ficou pronto, e o que **não** ficou.

        A frase vem do assistente, que sabe o que de fato aconteceu. Terminar
        sempre com "tudo certo" faria a primeira madrugada sem backup pegar a
        pessoa de surpresa.
        """
        self._limpar()
        self._titulo(passo.mensagem)
        self._paragrafo(passo.detalhe, cor="" if passo.ok else "#b45309")
        if passo.ok:
            self._paragrafo("Você pode fechar esta janela. O resto acontece pelo Live.")
        self._botao("Fechar", self.raiz.destroy)

    def tela_recusa(self, passo: Passo) -> None:
        self._limpar()
        self._titulo("Não deu para continuar")
        self._paragrafo(passo.mensagem, cor="#b91c1c")
        if passo.detalhe:
            self._paragrafo(passo.detalhe)
        self._botao("Tentar de novo", self.tela_apresentacao, principal=False)

    # --------------------------------------------------------
    # Trabalho fora do laço de eventos
    # --------------------------------------------------------

    def _em_thread(self, nome: str, tarefa: Any, titulo: str) -> None:
        self.tela_trabalhando(titulo)
        threading.Thread(target=lambda: self.recados.put((nome, tarefa())), daemon=True).start()

    def _parear(self) -> None:
        self._em_thread("pareou", self.assistente.parear, "Registrando esta máquina…")

    def _instalar(self) -> None:
        def trabalho() -> Passo:
            servico = self.assistente.instalar_servico()
            self.assistente.iniciar_agora()
            return servico

        self._em_thread("instalou", trabalho, "Deixando o Agente pronto…")

    def _drenar(self) -> None:
        """Traz o resultado da thread para o laço de eventos, que é quem desenha."""
        try:
            while True:
                nome, passo = self.recados.get_nowait()
                if nome == "pareou":
                    self.tela_pasta() if passo.ok else self.tela_recusa(passo)
                elif nome == "instalou":
                    self.tela_final(self.assistente.resumo())
        except queue.Empty:
            pass
        self.raiz.after(100, self._drenar)

    def abrir(self) -> None:
        self.tela_apresentacao()
        self.raiz.mainloop()


def montar(pasta_de_configuracao: Path | None = None) -> Janela:
    """
    Monta o assistente com o que o carimbo trouxe.

    O nome da máquina sai do próprio computador: é o que a pessoa reconhece na
    lista de dispositivos, e pedir para digitar seria mais um campo para errar.
    """
    import os

    dados = carimbo.do_processo()
    pasta = pasta_de_configuracao or identidade.pasta_padrao()

    return Janela(
        Assistente(
            local=Local(pasta=pasta),
            guarda=identidade.Guarda(pasta),
            servidor=dados.get("servidor", ""),
            codigo=dados.get("codigo", ""),
            nome_da_maquina=os.environ.get("COMPUTERNAME", "") or "Computador",
        )
    )


__all__ = ["Janela", "montar"]
