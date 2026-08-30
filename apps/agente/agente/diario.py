"""Diário de execuções: o que aconteceu na máquina, mesmo sem ninguém olhando.

O agendador roda com o navegador fechado — e, muitas vezes, com a internet
caída. Se a única memória de um backup fosse a resposta enviada ao servidor, o
backup de madrugada que rodou durante uma queda de rede simplesmente **não teria
acontecido** do ponto de vista do Live. O cliente veria um histórico vazio para
uma noite em que o backup foi feito.

Por isso o registro é gravado **aqui**, em disco, no momento em que a execução
termina, e só depois enviado. O envio é uma consequência; o registro é o fato.

Formato: uma linha JSON por execução, acrescentada ao fim do arquivo. Escolhido
porque acrescentar uma linha é a operação mais difícil de corromper: uma queda
de energia no meio da gravação estraga no máximo a última linha, e as anteriores
continuam legíveis. Um JSON único teria que ser reescrito inteiro a cada
execução, e a queda levaria tudo.

Linha ilegível é **pulada**, não fatal. O diário existe para não perder
histórico; deixá-lo derrubar o serviço inverteria o propósito.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

#: Nome do arquivo, na pasta de configuração do Agente.
ARQUIVO = "execucoes.jsonl"

#: Quantas execuções manter. Um Agente que fica anos no ar acumularia um
#: arquivo sem fim; o Live é quem guarda o histórico longo. O que fica aqui é
#: o suficiente para atravessar uma queda de rede prolongada.
LIMITE = 500

#: Quantas mandar de uma vez ao reconectar. Uma máquina que passou uma semana
#: sem rede não pode despejar centenas de registros numa mensagem só.
LOTE = 50


@dataclass(frozen=True)
class Execucao:
    """Uma rodada de backup, do jeito que o Live precisa vê-la."""

    politica_id: str
    politica_nome: str
    iniciada_em: str
    terminada_em: str
    resultado: str
    arquivos: int = 0
    bytes_copiados: int = 0
    ressalva: str = ""
    origem: str = "agendamento"
    #: Ficha do pacote produzido, quando houve um. Nunca o conteúdo: o ZIP
    #: fica na máquina do cliente.
    artefato: dict[str, Any] | None = None
    #: A política pede destino na nuvem e este pacote ainda não subiu.
    #:
    #: O agendamento roda offline; o envio precisa de rede. A janela entre uma
    #: coisa e outra é verdade, e o servidor precisa sabê-la para pedir o envio
    #: assim que houver canal — em vez de o painel dizer "Protegido" para uma
    #: cópia que ainda está só aqui.
    nuvem_pendente: bool = False

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "politica_id": self.politica_id,
            "politica_nome": self.politica_nome,
            "iniciada_em": self.iniciada_em,
            "terminada_em": self.terminada_em,
            "resultado": self.resultado,
            "arquivos": self.arquivos,
            "bytes_copiados": self.bytes_copiados,
            "ressalva": self.ressalva,
            "origem": self.origem,
            "artefato": self.artefato,
            "nuvem_pendente": self.nuvem_pendente,
        }


@dataclass
class Diario:
    """O arquivo de execuções desta máquina."""

    pasta: Path

    @property
    def arquivo(self) -> Path:
        return self.pasta / ARQUIVO

    def registrar(self, execucao: Execucao) -> str:
        """
        Grava a execução e devolve o identificador dela.

        O identificador é gerado aqui, na máquina, e viaja com o registro. É
        ele que permite ao servidor reconhecer um reenvio — o Agente que manda
        de novo depois de uma queda no meio do envio não pode virar duas linhas
        no histórico.
        """
        identificador = uuid.uuid4().hex
        linha = json.dumps(
            {"id": identificador, "enviada": False, **execucao.como_dicionario()},
            ensure_ascii=False,
        )
        self.pasta.mkdir(parents=True, exist_ok=True)
        with self.arquivo.open("a", encoding="utf-8") as saida:
            saida.write(linha + "\n")
        self._podar()
        return identificador

    def todas(self) -> list[dict[str, Any]]:
        """Tudo que dá para ler. Linha quebrada é pulada, não derruba nada."""
        if not self.arquivo.is_file():
            return []
        registros: list[dict[str, Any]] = []
        try:
            bruto = self.arquivo.read_text(encoding="utf-8")
        except OSError:
            return []
        for linha in bruto.splitlines():
            if not linha.strip():
                continue
            try:
                item = json.loads(linha)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("id"):
                registros.append(item)
        return registros

    def pendentes(self, limite: int = LOTE) -> list[dict[str, Any]]:
        """As que o servidor ainda não confirmou, das mais antigas para as novas."""
        return [item for item in self.todas() if not item.get("enviada")][:limite]

    def confirmar(self, identificadores: list[str]) -> int:
        """
        Marca como entregues as que o servidor confirmou.

        Só o que ele **confirmou**: marcar no envio faria um registro sumir
        para sempre se a conexão caísse entre o envio e a gravação do outro
        lado — e o histórico ficaria com um buraco que ninguém consegue
        explicar depois.
        """
        alvos = set(identificadores)
        if not alvos:
            return 0
        registros = self.todas()
        marcadas = 0
        for item in registros:
            if item["id"] in alvos and not item.get("enviada"):
                item["enviada"] = True
                marcadas += 1
        if marcadas:
            self._regravar(registros)
        return marcadas

    def _podar(self) -> None:
        """
        Descarta o excesso, começando pelas mais antigas **já entregues**.

        O que ainda não foi entregue nunca é descartado por idade: seria perder
        justamente o histórico que a queda de rede segurou — e o Live ficaria
        com um buraco na noite em que o backup mais importava.
        """
        registros = self.todas()
        sobrando = len(registros) - LIMITE
        if sobrando <= 0:
            return

        mantidos: list[dict[str, Any]] = []
        for item in registros:
            if sobrando > 0 and item.get("enviada"):
                sobrando -= 1
                continue
            mantidos.append(item)
        self._regravar(mantidos)

    def _regravar(self, registros: list[dict[str, Any]]) -> None:
        """Reescreve o arquivo inteiro, de forma atômica."""
        self.pasta.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".parcial")
        temporario.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in registros),
            encoding="utf-8",
        )
        os.replace(temporario, self.arquivo)


def agora_iso() -> str:
    """Instante local, em segundos. O Live mostra a hora da máquina do cliente."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


__all__ = ["ARQUIVO", "LIMITE", "LOTE", "Diario", "Execucao", "agora_iso"]
