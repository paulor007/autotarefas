"""Aviso de backup: quem soube, e quando.

Duas coisas diferentes moram aqui, e confundi-las seria caro:

1. **O registro do aviso**, que sempre acontece e fica no banco. É ele que
   permite responder "vocês foram avisados?" com evidência, meses depois.
2. **A entrega por e-mail**, que só acontece quando há SMTP configurado no
   cofre da organização. Sem SMTP, o aviso existe — na tela e no histórico — e
   o registro diz que o e-mail **não** foi enviado, com o motivo.

A separação é o que evita a mentira mais fácil desta parte do produto: marcar
"notificado" quando nada saiu da máquina. Um cliente que confia num e-mail que
nunca chegou fica sem backup e sem saber.

Regra do que avisar, vinda da política: `nunca`, `problema` (falha ou
ressalva — é o padrão) ou `sempre`. Aviso que sempre chega vira ruído, e ruído
é filtrado para uma pasta que ninguém abre.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from sqlalchemy.orm import Session

from autotarefas.tasks.politica import QuandoNotificar

from . import cofre
from .db import repositorio as repo
from .db.models import Execucao, Politica, ResultadoExecucao

#: Nomes dos segredos de SMTP no cofre da organização. Fixos, pelo mesmo
#: motivo dos de nuvem: a tela grava com estes nomes e o envio lê com estes.
SEGREDOS_SMTP = ("smtp.servidor", "smtp.porta", "smtp.usuario", "smtp.senha", "smtp.remetente")

#: Sem estes, não há como enviar.
OBRIGATORIOS_SMTP = ("smtp.servidor", "smtp.remetente")

#: Tempo máximo esperando o servidor de e-mail. Um SMTP lento não pode segurar
#: a resposta de um backup que já terminou.
TIMEOUT_S = 20.0


@dataclass(frozen=True)
class Aviso:
    """O que foi (ou não foi) enviado."""

    enviado: bool
    destinatarios: tuple[str, ...]
    motivo: str = ""

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "enviado": self.enviado,
            "destinatarios": list(self.destinatarios),
            "motivo": self.motivo,
        }


def deve_avisar(quando: QuandoNotificar, resultado: ResultadoExecucao) -> bool:
    """
    Esta execução merece aviso?

    `problema` inclui a ressalva de propósito: backup que copiou quase tudo é
    exatamente o caso em que alguém precisa olhar — e o único que passaria
    despercebido se só falha avisasse.
    """
    if quando is QuandoNotificar.NUNCA:
        return False
    if quando is QuandoNotificar.SEMPRE:
        return True
    return resultado in {ResultadoExecucao.FALHA, ResultadoExecucao.COM_RESSALVA}


def _credencial_smtp(sessao: Session, contexto: repo.Contexto) -> dict[str, str] | None:
    """Configuração de e-mail da organização, ou `None` quando não há."""
    faltando = [nome for nome in OBRIGATORIOS_SMTP if not cofre.existe(sessao, contexto, nome=nome)]
    if faltando:
        return None

    valores: dict[str, str] = {}
    for nome in SEGREDOS_SMTP:
        if cofre.existe(sessao, contexto, nome=nome):
            valores[nome.removeprefix("smtp.")] = cofre.revelar(sessao, contexto, nome=nome)
    return valores


def _mensagem(remetente: str, destinatarios: list[str], assunto: str, corpo: str) -> EmailMessage:
    email = EmailMessage()
    email["From"] = remetente
    email["To"] = ", ".join(destinatarios)
    email["Subject"] = assunto
    email.set_content(corpo)
    return email


def texto_do_aviso(
    *, dispositivo: str, politica: str, resultado: ResultadoExecucao, ressalva: str
) -> tuple[str, str]:
    """
    (assunto, corpo) do aviso.

    O assunto diz o desfecho antes de a pessoa abrir: quem recebe dez e-mails
    por dia decide pelo assunto se vai olhar agora ou depois — e "depois" é
    quando o backup não existe.
    """
    rotulos = {
        ResultadoExecucao.SUCESSO: "concluído",
        ResultadoExecucao.COM_RESSALVA: "concluído COM RESSALVAS",
        ResultadoExecucao.FALHA: "FALHOU",
        ResultadoExecucao.CANCELADA: "cancelado",
        ResultadoExecucao.EM_ANDAMENTO: "em andamento",
    }
    desfecho = rotulos.get(resultado, resultado.value)
    assunto = f"[AutoTarefas] Backup {desfecho} — {dispositivo}"

    linhas = [
        f"Dispositivo: {dispositivo}",
        f"Política: {politica or '(execução manual)'}",
        f"Resultado: {desfecho}",
    ]
    if ressalva:
        linhas.append(f"Observação: {ressalva}")
    if resultado is ResultadoExecucao.COM_RESSALVA:
        linhas.append(
            "\nO pacote foi criado e é utilizável. O que ficou de fora está "
            "listado no manifesto, dentro do próprio pacote."
        )
    if resultado is ResultadoExecucao.FALHA:
        linhas.append("\nNenhum pacote foi criado nesta execução.")
    return assunto, "\n".join(linhas)


def enviar(
    sessao: Session,
    contexto: repo.Contexto,
    *,
    destinatarios: list[str],
    assunto: str,
    corpo: str,
) -> Aviso:
    """
    Tenta entregar o aviso. Nunca levanta.

    Falha de e-mail não pode derrubar o registro do backup: o pacote existe, e
    perder o histórico por causa de um servidor SMTP fora do ar seria trocar
    um problema pequeno por um grande.
    """
    if not destinatarios:
        return Aviso(enviado=False, destinatarios=(), motivo="nenhum destinatario configurado")

    try:
        credencial = _credencial_smtp(sessao, contexto)
    except cofre.CofreTrancado as erro:
        return Aviso(enviado=False, destinatarios=tuple(destinatarios), motivo=str(erro))

    if credencial is None:
        return Aviso(
            enviado=False,
            destinatarios=tuple(destinatarios),
            motivo=(
                "envio de e-mail nao configurado nesta organizacao "
                "(guarde smtp.servidor e smtp.remetente no cofre)"
            ),
        )

    email = _mensagem(credencial["remetente"], destinatarios, assunto, corpo)
    porta = int(credencial.get("porta") or 587)

    try:
        with smtplib.SMTP(credencial["servidor"], porta, timeout=TIMEOUT_S) as servidor:
            servidor.ehlo()
            # STARTTLS quando o servidor oferece. Sem isto, usuário e senha
            # viajariam em texto claro pela rede do cliente.
            if servidor.has_extn("starttls"):
                servidor.starttls()
                servidor.ehlo()
            if credencial.get("usuario"):
                servidor.login(credencial["usuario"], credencial.get("senha", ""))
            servidor.send_message(email)
    except (OSError, smtplib.SMTPException) as erro:
        return Aviso(
            enviado=False,
            destinatarios=tuple(destinatarios),
            motivo=f"{type(erro).__name__}: {erro}",
        )

    return Aviso(enviado=True, destinatarios=tuple(destinatarios))


def registrar_aviso(
    sessao: Session,
    contexto: repo.Contexto,
    *,
    aviso: Aviso,
    dispositivo_id: str | None,
    alvo: str,
) -> None:
    """
    Grava na trilha o que aconteceu com o aviso — enviado ou não.

    É este registro que permite responder "vocês foram avisados?" com
    evidência. Marcar "notificado" sem ele seria uma afirmação sem lastro.
    """
    repo.registrar(
        sessao,
        contexto,
        acao="notificacao.enviada" if aviso.enviado else "notificacao.nao_enviada",
        alvo=alvo,
        detalhe=(", ".join(aviso.destinatarios) if aviso.enviado else aviso.motivo),
        dispositivo_id=dispositivo_id,
    )


def _politica_da_execucao(
    sessao: Session, contexto: repo.Contexto, execucao: Execucao
) -> Politica | None:
    """
    A politica que produziu esta execucao, e nao "alguma" politica da maquina.

    Com duas politicas na mesma maquina — uma diaria e uma mensal, por exemplo —
    pegar a primeira ativa mandaria o aviso com o nome errado, e quem recebesse
    procuraria o problema no lugar errado.
    """
    if execucao.politica_id:
        alvo = sessao.execute(
            repo.escopo(Politica, contexto).where(Politica.id == execucao.politica_id)
        ).scalar_one_or_none()
        if alvo is not None:
            return alvo

    # Execucao avulsa (pedida pela tela sem politica citada): cai na politica
    # ativa da maquina, que e de onde vem a lista de destinatarios.
    return (
        sessao.execute(
            repo.escopo(Politica, contexto)
            .where(Politica.dispositivo_id == execucao.dispositivo_id)
            .where(Politica.ativa.is_(True))
        )
        .scalars()
        .first()
    )


def avisar_execucao(
    sessao: Session,
    contexto: repo.Contexto,
    *,
    execucao: Execucao,
    dispositivo: str,
) -> dict[str, Any]:
    """
    Avisa quem a politica pediu, e registra o que aconteceu com o aviso.

    Vale para os DOIS caminhos: a execucao pedida pela tela e a que o Agente
    fez sozinho, de madrugada. A segunda e justamente a que mais precisa de
    aviso — ninguem estava olhando —, e deixa-la de fora faria a notificacao
    funcionar so quando nao era necessaria.

    Sem politica com destinatarios, nao ha a quem avisar. Isso e dito, e nao
    silenciado: "nao avisei porque nao ha destinatario" e informacao.
    """
    from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica

    registro = _politica_da_execucao(sessao, contexto, execucao)
    if registro is None:
        return {"enviado": False, "motivo": "nenhuma politica com destinatarios"}

    configuracao = ConfiguracaoDePolitica.de_json(registro.configuracao)
    if not deve_avisar(configuracao.notificacao.quando, execucao.resultado):
        return {"enviado": False, "motivo": "a politica nao pede aviso neste desfecho"}

    assunto, corpo = texto_do_aviso(
        dispositivo=dispositivo,
        politica=registro.nome,
        resultado=execucao.resultado,
        ressalva=execucao.ressalva,
    )
    aviso = enviar(
        sessao,
        contexto,
        destinatarios=list(configuracao.notificacao.emails),
        assunto=assunto,
        corpo=corpo,
    )
    registrar_aviso(
        sessao,
        contexto,
        aviso=aviso,
        dispositivo_id=execucao.dispositivo_id,
        alvo=registro.nome,
    )
    return aviso.como_dicionario()


__all__ = [
    "OBRIGATORIOS_SMTP",
    "SEGREDOS_SMTP",
    "Aviso",
    "deve_avisar",
    "enviar",
    "registrar_aviso",
    "texto_do_aviso",
]
