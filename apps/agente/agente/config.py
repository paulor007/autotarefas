"""Configuracao local do Agente: o que fica gravado na maquina do cliente.

Tres regras:

1. **Segredo nao mora aqui.** A chave privada fica no cofre do sistema (ou num
   arquivo proprio, restrito). Este arquivo guarda endereco do servidor,
   identificador do dispositivo e as pastas autorizadas — nada que sirva para
   se passar por alguem.
2. **As pastas autorizadas sao a fronteira do acesso ao disco.** Elas so
   entram aqui por consentimento dado NESTA maquina. Uma tela na nuvem nao
   pode conceder acesso ao disco de ninguem; o servidor pode pedir, o Agente
   e quem autoriza.
3. **Gravacao atomica.** O arquivo e escrito num temporario e renomeado. Um
   corte de energia no meio da gravacao nao pode deixar o Agente com uma
   configuracao pela metade — que, no pior caso, significaria um dispositivo
   sem pastas autorizadas e um backup que silenciosamente copia nada.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

#: Nome do arquivo dentro da pasta de configuracao.
ARQUIVO = "agente.json"

#: Versao do formato. Existe desde o inicio para que uma versao futura saiba
#: ler o que a de hoje escreveu.
VERSAO = 1


@dataclass(frozen=True)
class Configuracao:
    """O que o Agente sabe sobre si mesmo entre uma execucao e outra."""

    #: Endereco do Live ao qual este dispositivo se conecta.
    servidor: str = ""
    #: Identificador que o servidor devolveu no pareamento.
    dispositivo_id: str = ""
    #: Nome exibido na tela de dispositivos.
    nome: str = ""
    #: Pastas que este dispositivo pode ler. Vazio = nada autorizado.
    raizes: tuple[str, ...] = ()
    versao: int = VERSAO
    #: Datas em texto ISO, so para exibicao.
    pareado_em: str = ""

    @property
    def pareado(self) -> bool:
        """Ha pareamento valido? Sem `dispositivo_id`, nao."""
        return bool(self.servidor and self.dispositivo_id)

    def com_raiz(self, caminho: Path) -> Configuracao:
        """
        Devolve uma configuracao com mais uma pasta autorizada.

        Guarda o caminho **resolvido**: sem isso, `..\\..\\Windows` gravado como
        veio autorizaria, na pratica, um lugar diferente do que a pessoa viu na
        hora de consentir.
        """
        resolvido = str(caminho.resolve())
        if resolvido in self.raizes:
            return self
        return replace(self, raizes=(*self.raizes, resolvido))

    def sem_raiz(self, caminho: Path) -> Configuracao:
        """Devolve uma configuracao sem aquela pasta."""
        resolvido = str(caminho.resolve())
        return replace(self, raizes=tuple(r for r in self.raizes if r != resolvido))

    def como_dicionario(self) -> dict[str, object]:
        return {
            "versao": self.versao,
            "servidor": self.servidor,
            "dispositivo_id": self.dispositivo_id,
            "nome": self.nome,
            "raizes": list(self.raizes),
            "pareado_em": self.pareado_em,
        }


@dataclass
class Local:
    """A pasta de configuracao do Agente nesta maquina."""

    pasta: Path
    _cache: Configuracao | None = field(default=None, repr=False)

    @property
    def arquivo(self) -> Path:
        return self.pasta / ARQUIVO

    def carregar(self) -> Configuracao:
        """
        Le a configuracao. Arquivo ausente ou corrompido vira configuracao vazia.

        Corrompido nao derruba o Agente: um JSON quebrado faria o servico nao
        subir, e um servico que nao sobe e um backup que nao acontece. Vazio
        significa "nao pareado", que o Agente sabe tratar.
        """
        if not self.arquivo.is_file():
            return Configuracao()
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return Configuracao()
        if not isinstance(dados, dict):
            return Configuracao()
        return Configuracao(
            servidor=str(dados.get("servidor", "")),
            dispositivo_id=str(dados.get("dispositivo_id", "")),
            nome=str(dados.get("nome", "")),
            raizes=tuple(str(item) for item in dados.get("raizes", []) or []),
            versao=int(dados.get("versao", VERSAO) or VERSAO),
            pareado_em=str(dados.get("pareado_em", "")),
        )

    def gravar(self, configuracao: Configuracao) -> None:
        """Grava de forma atomica: temporario + rename."""
        self.pasta.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".parcial")
        temporario.write_text(
            json.dumps(configuracao.como_dicionario(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporario, self.arquivo)


__all__ = ["ARQUIVO", "VERSAO", "Configuracao", "Local"]
