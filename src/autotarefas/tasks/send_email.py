"""
Task de envio de emails em massa a partir de uma planilha.

A SendEmailTask le uma planilha de destinatarios e envia um email por
linha, via SMTP (smtplib + email.message, ambos da stdlib). O assunto e
o corpo sao templates: trechos {coluna} sao substituidos pelos valores
da linha (ex: "Ola {nome}" -> "Ola Maria").

Caso de uso tipico: notificar/comunicar uma lista de pessoas
(confirmacoes, avisos, codigos), lendo os dados de uma planilha.

Recursos:
- Templates {coluna} no assunto e no corpo
- Tolerancia a falhas POR LINHA (um email ruim nao para os outros)
- Rate limiting (delay configuravel entre envios)
- Autenticacao opcional (usuario/senha SMTP) e STARTTLS opcional
- Relatorio opcional (CSV/XLSX/JSON) com o resultado de cada linha
- dry-run: nao conecta nem envia; mostra o que enviaria

Oitava subclasse concreta de BaseTask.

NOTA DE SEGURANCA: a senha SMTP transita apenas pela conexao; nunca e
gravada em log, no audit ou no relatorio.
"""

from __future__ import annotations

import smtplib
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.core.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================
# Constantes
# ============================================================

_DEFAULT_SMTP_PORT = 587
_DEFAULT_TIMEOUT_S = 30.0
_PLANILHA_FORMATS = (".csv", ".xlsx", ".xls")
_REPORT_FORMATS = (".csv", ".xlsx", ".xls", ".json")
_PREVIEW_LIMIT = 3

ProgressInfo = dict[str, Any]


# ============================================================
# Configuracao SMTP
# ============================================================


@dataclass
class SmtpConfig:
    """Parametros de conexao com o servidor SMTP."""

    host: str
    port: int = _DEFAULT_SMTP_PORT
    usuario: str | None = None
    senha: str | None = None
    usar_tls: bool = True


# ============================================================
# Task
# ============================================================


class SendEmailTask(BaseTask):
    """Envia emails em massa a partir de uma planilha de destinatarios."""

    name = "send_email"
    description = "Envia emails em massa a partir de uma planilha"

    def __init__(  # noqa: PLR0913 - task de config com parametros keyword-only
        self,
        planilha_path: Path,
        smtp: SmtpConfig,
        remetente: str,
        assunto: str,
        corpo: str,
        *,
        coluna_email: str = "email",
        is_html: bool = False,
        delay_s: float = 0.0,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        report_path: Path | None = None,
        on_progress: Callable[[ProgressInfo], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            planilha_path: Planilha CSV/XLSX com os destinatarios.
            smtp: Configuracao de conexao SMTP.
            remetente: Endereco "From".
            assunto: Template do assunto (aceita {coluna}).
            corpo: Template do corpo (aceita {coluna}).
            coluna_email: Nome da coluna que contem o email do destinatario.
            is_html: Se True, envia o corpo como HTML.
            delay_s: Pausa em segundos entre envios (rate limit).
            timeout_s: Timeout da conexao SMTP.
            report_path: Se informado, salva relatorio por linha.
            on_progress: Callback chamado a cada email.
            dry_run: Se True, nao conecta nem envia; so conta/preview.
        """
        super().__init__(dry_run=dry_run)

        suffix = planilha_path.suffix.lower()
        if suffix not in _PLANILHA_FORMATS:
            msg = (
                f"Formato de planilha nao suportado: '{suffix}'. "
                f"Use: {', '.join(_PLANILHA_FORMATS)}"
            )
            raise ValidationError(msg)

        if not smtp.host or not smtp.host.strip():
            msg = "smtp.host nao pode ser vazio"
            raise ValidationError(msg)

        if not remetente or not remetente.strip():
            msg = "remetente nao pode ser vazio"
            raise ValidationError(msg)

        if not assunto or not assunto.strip():
            msg = "assunto nao pode ser vazio"
            raise ValidationError(msg)

        if report_path is not None:
            rep_suffix = report_path.suffix.lower()
            if rep_suffix not in _REPORT_FORMATS:
                msg = (
                    f"Formato de relatorio nao suportado: '{rep_suffix}'. "
                    f"Use: {', '.join(_REPORT_FORMATS)}"
                )
                raise ValidationError(msg)

        if delay_s < 0:
            msg = "delay_s nao pode ser negativo"
            raise ValidationError(msg)

        self.planilha_path = planilha_path
        self.smtp = smtp
        self.remetente = remetente
        self.assunto = assunto
        self.corpo = corpo
        self.coluna_email = coluna_email
        self.is_html = is_html
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.report_path = report_path
        self.on_progress = on_progress

    # --------------------------------------------------------
    # Planilha
    # --------------------------------------------------------

    def _read_planilha(self) -> pd.DataFrame:
        """Le a planilha como strings, normalizando vazios."""
        suffix = self.planilha_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(self.planilha_path, dtype=str)
        else:  # .xlsx / .xls
            df = pd.read_excel(self.planilha_path, dtype=str)
        return df.fillna("")

    # --------------------------------------------------------
    # Template / email
    # --------------------------------------------------------

    def _render(self, template: str, row: dict[str, Any]) -> str:
        """Substitui {coluna} pelos valores da linha (faltantes -> '')."""
        safe: defaultdict[str, str] = defaultdict(str)
        for k, v in row.items():
            safe[str(k)] = str(v)
        try:
            return template.format_map(safe)
        except (IndexError, ValueError):
            # template malformado (ex: chave entre chaves solta) -> literal
            return template

    def _montar_email(self, destinatario: str, row: dict[str, Any]) -> EmailMessage:
        """Monta o EmailMessage de uma linha."""
        msg = EmailMessage()
        msg["From"] = self.remetente
        msg["To"] = destinatario
        msg["Subject"] = self._render(self.assunto, row)
        corpo = self._render(self.corpo, row)
        if self.is_html:
            msg.set_content(corpo, subtype="html")
        else:
            msg.set_content(corpo)
        return msg

    def _enviar_um(
        self,
        server: smtplib.SMTP,
        destinatario: str,
        row: dict[str, Any],
    ) -> tuple[bool, str]:
        """Envia um email. Retorna (sucesso, mensagem)."""
        if not destinatario:
            return False, "destinatario vazio"
        try:
            msg = self._montar_email(destinatario, row)
            server.send_message(msg)
        except smtplib.SMTPException as exc:
            return False, f"{type(exc).__name__}: {exc}"
        except OSError as exc:
            return False, f"erro de conexao: {exc}"
        return True, "enviado"

    # --------------------------------------------------------
    # Progresso / relatorio
    # --------------------------------------------------------

    def _notify(
        self,
        linha: int,
        total: int,
        destinatario: str,
        *,
        sucesso: bool,
        mensagem: str,
    ) -> None:
        """Chama o callback de progresso (se houver), sem propagar erro."""
        if self.on_progress is None:
            return
        info: ProgressInfo = {
            "linha": linha,
            "total": total,
            "para": destinatario,
            "sucesso": sucesso,
            "mensagem": mensagem,
        }
        try:
            self.on_progress(info)
        except Exception:  # noqa: BLE001 - callback do usuario nao quebra a task
            logger.warning("Callback de progresso levantou excecao (ignorado)")

    def _salvar_relatorio(
        self,
        resultados: list[dict[str, Any]],
        path: Path,
    ) -> None:
        """Salva o relatorio por linha no formato indicado pela extensao."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(resultados)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df.to_csv(path, index=False)
        elif suffix in (".xlsx", ".xls"):
            df.to_excel(path, index=False)
        else:  # .json
            df.to_json(path, orient="records", indent=2, force_ascii=False)

    # --------------------------------------------------------
    # Conexao
    # --------------------------------------------------------

    def _conectar(self) -> smtplib.SMTP:
        """Abre a conexao SMTP, aplica STARTTLS e login (se houver)."""
        server = smtplib.SMTP(self.smtp.host, self.smtp.port, timeout=self.timeout_s)
        try:
            if self.smtp.usar_tls:
                server.starttls()
            if self.smtp.usuario is not None:
                server.login(self.smtp.usuario, self.smtp.senha or "")
        except (OSError, smtplib.SMTPException):
            server.close()
            raise
        return server

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    def execute(self) -> TaskResult:  # noqa: PLR0912, PLR0915
        """Executa o envio dos emails."""
        started_at = datetime.now(UTC)

        # Ler planilha
        try:
            df = self._read_planilha()
        except (OSError, ValueError) as exc:
            logger.error(f"Falha ao ler a planilha: {exc}")
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Erro ao ler a planilha: {exc}",
            )

        # Coluna de email precisa existir
        if self.coluna_email not in df.columns:
            msg = (
                f"Coluna de email '{self.coluna_email}' nao encontrada. "
                f"Colunas: {', '.join(str(c) for c in df.columns)}"
            )
            logger.error(msg)
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=msg,
            )

        total = len(df)
        rows = df.to_dict("records")
        logger.info(f"Preparando {total} emails via {self.smtp.host}:{self.smtp.port}")

        # Planilha vazia: nao e erro
        if total == 0:
            logger.warning("Planilha sem destinatarios")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                rows_affected=0,
                data={
                    "total": 0,
                    "enviados": 0,
                    "falhas": 0,
                    "smtp_host": self.smtp.host,
                    "warning": "Planilha sem destinatarios",
                },
            )

        # Dry-run: nao conecta, monta preview
        if self.dry_run:
            preview: list[dict[str, str]] = []
            for row in rows[:_PREVIEW_LIMIT]:
                payload = {str(k): v for k, v in row.items()}
                destino = str(payload.get(self.coluna_email, "")).strip()
                preview.append(
                    {
                        "para": destino,
                        "assunto": self._render(self.assunto, payload),
                    }
                )
            logger.info(f"[dry-run] Enviaria {total} emails")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                data={
                    "dry_run": True,
                    "would_send": total,
                    "smtp_host": self.smtp.host,
                    "preview": preview,
                },
            )

        # Conexao (erro aqui = falha geral, nenhum email saiu)
        try:
            server = self._conectar()
        except (OSError, smtplib.SMTPException) as exc:
            logger.error(f"Falha ao conectar/autenticar no SMTP: {exc}")
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Falha ao conectar/autenticar no SMTP: {exc}",
            )

        # Envio (tolerancia por linha)
        resultados: list[dict[str, Any]] = []
        enviados = 0
        falhas = 0
        try:
            for idx, row in enumerate(rows, start=1):
                payload = {str(k): v for k, v in row.items()}
                destinatario = str(payload.get(self.coluna_email, "")).strip()
                sucesso, mensagem = self._enviar_um(server, destinatario, payload)

                registro = dict(payload)
                registro["_resultado"] = "ok" if sucesso else "erro"
                registro["_mensagem"] = mensagem
                resultados.append(registro)

                if sucesso:
                    enviados += 1
                else:
                    falhas += 1

                self._notify(
                    idx,
                    total,
                    destinatario,
                    sucesso=sucesso,
                    mensagem=mensagem,
                )

                if self.delay_s > 0 and idx < total:
                    time.sleep(self.delay_s)
        finally:
            try:
                server.quit()
            except smtplib.SMTPException:
                server.close()

        # Relatorio
        report_saved: str | None = None
        if self.report_path is not None:
            try:
                self._salvar_relatorio(resultados, self.report_path)
                report_saved = str(self.report_path)
            except (OSError, ValueError) as exc:
                logger.warning(f"Falha ao salvar relatorio: {exc}")

        # Status agregado
        if falhas == 0:
            status = TaskStatus.SUCCESS
        elif enviados == 0:
            status = TaskStatus.FAILURE
        else:
            status = TaskStatus.PARTIAL

        logger.info(f"Envio concluido: {enviados} enviados, {falhas} falhas")
        return self._make_result(
            status=status,
            started_at=started_at,
            rows_affected=enviados,
            rows_failed=falhas,
            data={
                "total": total,
                "enviados": enviados,
                "falhas": falhas,
                "smtp_host": self.smtp.host,
                "remetente": self.remetente,
                "report_path": report_saved,
            },
        )


__all__ = ["SendEmailTask", "SmtpConfig"]
