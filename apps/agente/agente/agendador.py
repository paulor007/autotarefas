"""Agendador local: o backup acontece com o navegador fechado.

Esta é a diferença entre "o cliente pode mandar fazer backup" e "o cliente tem
backup". O agendamento **não** vive no servidor esperando a hora: ele vive
aqui, na máquina, gravado em disco. Consequências que valem o desenho:

- **navegador fechado** não muda nada;
- **servidor fora do ar** não muda nada — a política já está aqui;
- **máquina reiniciada** não perde o horário — a política é lida do disco na
  partida, e o que passou enquanto ela estava desligada é tratado como
  atrasado, não como perdido.

Retry com espera crescente. Falha transitória é a regra num escritório: disco
externo desconectado, rede que cai, arquivo travado por um minuto. Desistir na
primeira tentativa faria o backup depender de sorte; insistir de minuto em
minuto num disco que não está conectado só enche o log e gasta a bateria.

O agendador **não decide o que copiar**: ele dispara a política, e a política
passa pela mesma guarda de pastas autorizadas de sempre.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from autotarefas.tasks.politica import Politica, proxima_execucao

from .config import Local

#: Nome do arquivo com as políticas, na pasta de configuração do Agente.
ARQUIVO = "politicas.json"

#: De quanto em quanto tempo o laço acorda para conferir o relógio. Um minuto
#: é fino o bastante para um agendamento em HH:MM e barato o bastante para um
#: serviço que fica meses no ar.
PASSO_S = 60.0

#: Atraso máximo que ainda vale executar. Máquina desligada por uma semana não
#: deve disparar sete backups ao ligar: um só, o mais recente, e segue o
#: horário normal. Disparar todos encheria o disco e demoraria horas.
TOLERANCIA_ATRASO = timedelta(hours=12)


@dataclass
class PoliticaLocal:
    """Uma política guardada nesta máquina, com o que já aconteceu com ela."""

    id: str
    nome: str
    politica: Politica
    #: Quando ela deve disparar. Recalculado a cada execução.
    proxima: datetime | None = None
    ultima_execucao: str = ""
    ultimo_resultado: str = ""
    ultima_ressalva: str = ""
    #: Em que tentativa está, quando houve falha. Zero = nada pendente.
    tentativa: int = 0

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "politica": json.loads(self.politica.como_json()),
            "proxima": self.proxima.isoformat() if self.proxima else "",
            "ultima_execucao": self.ultima_execucao,
            "ultimo_resultado": self.ultimo_resultado,
            "ultima_ressalva": self.ultima_ressalva,
            "tentativa": self.tentativa,
        }

    @classmethod
    def de_dicionario(cls, dados: dict[str, Any]) -> PoliticaLocal:
        bruta = dados.get("proxima") or ""
        return cls(
            id=str(dados.get("id", "")),
            nome=str(dados.get("nome", "")),
            politica=Politica.model_validate(dados.get("politica") or {}),
            proxima=datetime.fromisoformat(bruta) if bruta else None,
            ultima_execucao=str(dados.get("ultima_execucao", "")),
            ultimo_resultado=str(dados.get("ultimo_resultado", "")),
            ultima_ressalva=str(dados.get("ultima_ressalva", "")),
            tentativa=int(dados.get("tentativa", 0) or 0),
        )


@dataclass
class Agendador:
    """
    Guarda as políticas em disco e dispara na hora.

    O relógio e a espera são injetáveis porque um teste que espera de verdade
    por um agendamento diário demoraria um dia. O que se testa aqui é a
    DECISÃO — o que dispara, quando, e o que acontece quando falha.
    """

    local: Local
    executar: Callable[[PoliticaLocal], Awaitable[dict[str, Any]]]
    relogio: Callable[[], datetime] = datetime.now
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep
    politicas: list[PoliticaLocal] = field(default_factory=list)

    @property
    def arquivo(self) -> Path:
        return self.local.pasta / ARQUIVO

    # --------------------------------------------------------
    # Persistência
    # --------------------------------------------------------

    def carregar(self) -> list[PoliticaLocal]:
        """
        Lê as políticas do disco.

        Arquivo ausente ou corrompido vira lista vazia, e não exceção: um JSON
        quebrado não pode impedir o serviço de subir. O que se perde é o
        agendamento — e isso aparece na tela como "nenhuma política", que é
        verdade e é acionável.
        """
        if not self.arquivo.is_file():
            self.politicas = []
            return self.politicas
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            self.politicas = [PoliticaLocal.de_dicionario(item) for item in dados]
        except (OSError, ValueError, TypeError):
            self.politicas = []
        return self.politicas

    def gravar(self) -> None:
        """Grava de forma atômica: temporário + rename."""
        self.local.pasta.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".parcial")
        temporario.write_text(
            json.dumps(
                [item.como_dicionario() for item in self.politicas],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporario, self.arquivo)

    def substituir(self, politicas: list[PoliticaLocal]) -> None:
        """
        Troca todas as políticas pelas que o servidor mandou.

        O horário de cada uma é recalculado a partir de agora — mas a política
        que **já existia e não mudou** mantém o próximo disparo. Sem isso, uma
        sincronização a cada reconexão empurraria o backup para sempre: a
        máquina reconecta às 01:59, o próximo vira amanhã, e nunca são 02:00.
        """
        anteriores = {item.id: item for item in self.politicas}
        agora = self.relogio()

        novas: list[PoliticaLocal] = []
        for item in politicas:
            anterior = anteriores.get(item.id)
            if anterior is not None and anterior.politica == item.politica:
                item.proxima = anterior.proxima
                item.ultima_execucao = anterior.ultima_execucao
                item.ultimo_resultado = anterior.ultimo_resultado
                item.ultima_ressalva = anterior.ultima_ressalva
                item.tentativa = anterior.tentativa
            else:
                item.proxima = proxima_execucao(item.politica.agendamento, agora)
            novas.append(item)

        self.politicas = novas
        self.gravar()

    # --------------------------------------------------------
    # Decisão
    # --------------------------------------------------------

    def devidas(self, agora: datetime | None = None) -> list[PoliticaLocal]:
        """
        Políticas que já deveriam ter disparado.

        Atraso maior que a tolerância é **descartado**, não acumulado: máquina
        desligada por uma semana não pode disparar sete backups ao ligar.
        """
        instante = agora or self.relogio()
        prontas: list[PoliticaLocal] = []
        for item in self.politicas:
            if item.proxima is None or item.proxima > instante:
                continue
            if instante - item.proxima > TOLERANCIA_ATRASO:
                # Perdeu a janela. Reagenda para a próxima e segue a vida —
                # com registro, para a tela poder dizer o que aconteceu.
                item.ultimo_resultado = "perdida"
                item.ultima_ressalva = f"a maquina estava desligada as {item.proxima:%d/%m %H:%M}"
                item.proxima = proxima_execucao(item.politica.agendamento, instante)
                continue
            prontas.append(item)
        return prontas

    async def disparar(self, item: PoliticaLocal) -> dict[str, Any]:
        """
        Executa uma política, com retry e espera crescente.

        A espera acontece **entre** as tentativas, dentro deste método: sair e
        voltar pelo laço faria a política concorrer com o horário normal e, no
        pior caso, disparar duas vezes.
        """
        regra = item.politica.retry
        ultimo_erro = ""

        for numero in range(1, regra.tentativas + 1):
            item.tentativa = numero
            espera = regra.espera_da_tentativa(numero)
            if espera:
                await self.dormir(espera.total_seconds())

            try:
                resultado = await self.executar(item)
            except Exception as erro:  # noqa: BLE001 — o laço não pode morrer
                ultimo_erro = f"{type(erro).__name__}: {erro}"
                continue

            if resultado.get("ok", True):
                item.tentativa = 0
                item.ultima_execucao = self.relogio().isoformat(timespec="seconds")
                item.ultimo_resultado = (
                    "com_ressalva" if resultado.get("com_ressalva") else "sucesso"
                )
                item.ultima_ressalva = str(resultado.get("ressalva", ""))
                return resultado
            ultimo_erro = str(resultado.get("erro", "sem detalhe"))

        item.tentativa = 0
        item.ultima_execucao = self.relogio().isoformat(timespec="seconds")
        item.ultimo_resultado = "falha"
        item.ultima_ressalva = ultimo_erro
        return {"ok": False, "erro": ultimo_erro, "tentativas": regra.tentativas}

    async def rodada(self) -> list[dict[str, Any]]:
        """
        Uma passada: dispara o que está devido e reagenda.

        Reagendar **depois** de executar, e a partir do fim da execução, evita
        o laço em que um backup de duas horas encontra o próprio horário já
        vencido ao terminar.
        """
        resultados: list[dict[str, Any]] = []
        prontas = self.devidas()

        for item in prontas:
            resultado = await self.disparar(item)
            item.proxima = proxima_execucao(item.politica.agendamento, self.relogio())
            resultados.append({"politica": item.id, **resultado})

        if prontas or self.politicas:
            self.gravar()
        return resultados

    async def rodar(self, *, passadas: int | None = None) -> None:
        """
        Laço do serviço. `passadas` existe para a suíte; em produção é infinito.

        Parar por conta própria significaria parar de fazer backup em silêncio,
        que é o pior desfecho possível deste produto.
        """
        self.carregar()
        contador = 0
        while passadas is None or contador < passadas:
            with contextlib.suppress(Exception):
                await self.rodada()
            contador += 1
            if passadas is None or contador < passadas:
                await self.dormir(PASSO_S)


__all__ = [
    "ARQUIVO",
    "PASSO_S",
    "TOLERANCIA_ATRASO",
    "Agendador",
    "PoliticaLocal",
]
