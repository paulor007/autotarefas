"""Política de backup: o que copiar, para onde, quando e por quanto tempo guardar.

Uma política é o que transforma "fiz um backup" em "tenho backup". Ela vive em
dois lugares e precisa significar a mesma coisa nos dois: o servidor guarda e
valida; o **Agente executa**, inclusive com o navegador fechado e sem rede. Por
isso o formato mora aqui, no núcleo compartilhado, e não de um lado só — duas
definições paralelas divergem no primeiro campo novo.

Três decisões que valem registrar:

1. **O horário é local da máquina.** Backup "às 2h" quer dizer 2h no relógio de
   quem trabalha ali. Guardar em UTC e converter na hora de rodar erraria duas
   vezes por ano, no horário de verão, exatamente na madrugada.
2. **Retenção é GFS (avô-pai-filho), não "guardar N".** Guardar os 30 últimos
   diários protege contra o erro de ontem; não protege contra o erro que
   ninguém viu há três meses. Diárias, semanais e mensais cobrem os dois.
3. **Nada de valor implícito perigoso.** Retenção zero apagaria tudo; janela de
   retry infinita seguraria a máquina o dia inteiro. Os limites são validados
   na gravação, e não na hora de executar — de madrugada não há quem corrija.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time, timedelta

from pydantic import BaseModel, Field, field_validator, model_validator


class TipoDeAgendamento(enum.StrEnum):
    """Com que frequência a política dispara sozinha."""

    DESLIGADO = "desligado"
    """Só executa quando alguém manda."""

    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSAL = "mensal"


class TipoDeDestino(enum.StrEnum):
    """Para onde a cópia vai, além da própria máquina."""

    NENHUM = "nenhum"
    """Fica só na máquina. Útil para começar; não é backup de verdade."""

    LOCAL = "local"
    EXTERNO = "externo"
    REDE = "rede"
    NUVEM = "nuvem"


class QuandoNotificar(enum.StrEnum):
    """Quando avisar as pessoas."""

    NUNCA = "nunca"
    PROBLEMA = "problema"
    """Falha ou ressalva. É o padrão: aviso que sempre chega vira ruído."""
    SEMPRE = "sempre"


class Agendamento(BaseModel):
    """Quando a política dispara."""

    tipo: TipoDeAgendamento = TipoDeAgendamento.DESLIGADO
    #: `HH:MM` no relógio da máquina que executa.
    hora: str = "02:00"
    #: 0 = segunda-feira. Só vale para `semanal`.
    dia_da_semana: int = Field(default=0, ge=0, le=6)
    #: Só vale para `mensal`. 29, 30 e 31 caem para o último dia do mês.
    dia_do_mes: int = Field(default=1, ge=1, le=31)

    @field_validator("hora")
    @classmethod
    def _hora_valida(cls, valor: str) -> str:
        try:
            hora, minuto = valor.split(":")
            time(int(hora), int(minuto))
        except (ValueError, TypeError) as erro:
            msg = f"horario invalido: {valor!r}. Use HH:MM, como 02:00."
            raise ValueError(msg) from erro
        return valor

    @property
    def momento(self) -> time:
        hora, minuto = self.hora.split(":")
        return time(int(hora), int(minuto))


class Retencao(BaseModel):
    """
    Quantos pacotes guardar, no esquema avô-pai-filho.

    Zero em todos os campos seria "apagar tudo depois de copiar", que é pior do
    que não ter retenção nenhuma — por isso é recusado.
    """

    diarias: int = Field(default=7, ge=0, le=365)
    semanais: int = Field(default=4, ge=0, le=104)
    mensais: int = Field(default=12, ge=0, le=120)

    @model_validator(mode="after")
    def _pelo_menos_um(self) -> Retencao:
        if self.diarias == 0 and self.semanais == 0 and self.mensais == 0:
            msg = (
                "retencao zerada apagaria todos os pacotes logo depois de "
                "criá-los. Guarde ao menos uma cópia diária, semanal ou mensal."
            )
            raise ValueError(msg)
        return self


class Retry(BaseModel):
    """
    Como insistir quando a execução falha.

    Falha transitória é a regra, não a exceção: disco externo desconectado,
    rede que cai, arquivo travado por um minuto. Desistir na primeira faria o
    backup depender de sorte.
    """

    tentativas: int = Field(default=3, ge=1, le=10)
    espera_inicial_min: int = Field(default=5, ge=1, le=120)
    fator: float = Field(default=2.0, ge=1.0, le=5.0)

    def espera_da_tentativa(self, numero: int) -> timedelta:
        """
        Quanto esperar antes da tentativa `numero` (a primeira é 1).

        Crescente: insistir de minuto em minuto num disco que não está
        conectado só enche o log e gasta a bateria do notebook.
        """
        if numero <= 1:
            return timedelta(0)
        minutos = self.espera_inicial_min * (self.fator ** (numero - 2))
        return timedelta(minutes=min(minutos, 24 * 60))


class Notificacao(BaseModel):
    """Quem avisar, e quando."""

    quando: QuandoNotificar = QuandoNotificar.PROBLEMA
    emails: list[str] = Field(default_factory=list)

    @field_validator("emails")
    @classmethod
    def _emails_plausiveis(cls, valores: list[str]) -> list[str]:
        for item in valores:
            if "@" not in item or item.startswith("@") or item.endswith("@"):
                msg = f"endereco de e-mail invalido: {item!r}"
                raise ValueError(msg)
        return valores


class Destino(BaseModel):
    """Para onde copiar o pacote depois de pronto."""

    tipo: TipoDeDestino = TipoDeDestino.NENHUM
    #: Caminho na máquina do cliente. Vazio para `nenhum` e para `nuvem`
    #: (a nuvem vem da credencial guardada no cofre da organização).
    caminho: str = ""

    @model_validator(mode="after")
    def _caminho_quando_precisa(self) -> Destino:
        precisa = {TipoDeDestino.LOCAL, TipoDeDestino.EXTERNO, TipoDeDestino.REDE}
        if self.tipo in precisa and not self.caminho.strip():
            msg = f"destino '{self.tipo.value}' precisa de um caminho"
            raise ValueError(msg)
        return self


class Politica(BaseModel):
    """
    A configuração completa de uma política de backup.

    Validada na gravação, e não na hora de executar: de madrugada não há quem
    corrija um campo errado, e a execução que falha por configuração inválida
    é indistinguível, no log, da que falha por disco cheio.
    """

    #: Vazio = todas as pastas autorizadas na máquina. É o padrão útil: quem
    #: autorizou uma pasta quer que ela seja copiada.
    origens: list[str] = Field(default_factory=list)
    destino: Destino = Field(default_factory=Destino)
    agendamento: Agendamento = Field(default_factory=Agendamento)
    retencao: Retencao = Field(default_factory=Retencao)
    retry: Retry = Field(default_factory=Retry)
    notificacao: Notificacao = Field(default_factory=Notificacao)
    #: Instantâneo de volume, para copiar arquivo aberto. Exige o Agente como
    #: serviço do sistema; sem isso ele recusa em vez de copiar sem o arquivo.
    usar_vss: bool = False
    #: Cifrar o pacote com a senha guardada no cofre da organização.
    cifrar: bool = False
    #: Assinar o manifesto com a chave do cofre. Ligado por padrão: é o que
    #: separa "não se estragou" de "ninguém mexeu".
    assinar: bool = True
    #: Copiar só o que mudou desde o pacote anterior, usando um catálogo local.
    #: Desligado por padrão de propósito: o pacote completo se sustenta
    #: sozinho, e o incremental exige a corrente de pacotes anteriores para
    #: restaurar. Quem liga precisa saber disso — e a tela diz.
    incremental: bool = False

    @property
    def protege_de_verdade(self) -> bool:
        """
        Esta política tira a cópia de perto do original?

        Pacote no mesmo computador não protege contra o disco morrer nem
        contra ransomware. A tela usa isto para dizer a verdade em vez de
        mostrar um "configurado" que não significa nada.
        """
        return self.destino.tipo in {
            TipoDeDestino.EXTERNO,
            TipoDeDestino.REDE,
            TipoDeDestino.NUVEM,
        }

    def como_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def de_json(cls, bruto: str) -> Politica:
        """Lê a política gravada. Texto vazio vira a política padrão."""
        if not bruto.strip():
            return cls()
        return cls.model_validate_json(bruto)


# ============================================================
# Quando é a próxima execução
# ============================================================


def _ultimo_dia_do_mes(referencia: date) -> int:
    proximo = referencia.replace(day=28) + timedelta(days=4)
    return (proximo.replace(day=1) - timedelta(days=1)).day


def proxima_execucao(agendamento: Agendamento, depois_de: datetime) -> datetime | None:
    """
    Quando esta política dispara pela próxima vez, no relógio da máquina.

    `None` quando o agendamento está desligado. O cálculo é sempre "o próximo
    instante ESTRITAMENTE depois" do informado: sem isso, uma execução que
    termina às 02:00:00 em ponto agendaria a seguinte para o mesmo segundo, e o
    backup rodaria em laço.
    """
    if agendamento.tipo is TipoDeAgendamento.DESLIGADO:
        return None

    alvo = agendamento.momento

    if agendamento.tipo is TipoDeAgendamento.DIARIO:
        candidato = datetime.combine(depois_de.date(), alvo, tzinfo=depois_de.tzinfo)
        if candidato <= depois_de:
            candidato += timedelta(days=1)
        return candidato

    if agendamento.tipo is TipoDeAgendamento.SEMANAL:
        dias = (agendamento.dia_da_semana - depois_de.weekday()) % 7
        candidato = datetime.combine(
            depois_de.date() + timedelta(days=dias), alvo, tzinfo=depois_de.tzinfo
        )
        if candidato <= depois_de:
            candidato += timedelta(days=7)
        return candidato

    # Mensal. Mês que não tem o dia escolhido cai para o último: quem marcou
    # dia 31 quer "fim do mês", e pular fevereiro seria perder a cópia mensal
    # justamente no mês mais curto.
    referencia = depois_de.date().replace(day=1)
    for _ in range(3):
        dia = min(agendamento.dia_do_mes, _ultimo_dia_do_mes(referencia))
        candidato = datetime.combine(referencia.replace(day=dia), alvo, tzinfo=depois_de.tzinfo)
        if candidato > depois_de:
            return candidato
        referencia = (referencia + timedelta(days=32)).replace(day=1)
    return None


__all__ = [
    "Agendamento",
    "Destino",
    "Notificacao",
    "Politica",
    "QuandoNotificar",
    "Retencao",
    "Retry",
    "TipoDeAgendamento",
    "TipoDeDestino",
    "proxima_execucao",
]
