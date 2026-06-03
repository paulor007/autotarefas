"""
Testes da SendEmailTask.

ESTRATEGIA:
- Troca smtplib.SMTP por um fake que captura os emails enviados e
  permite simular falhas (conexao, TLS, login, destinatario recusado).
- Planilhas reais em tmp_path.

Cobertura:
- Validacao do construtor
- Envio (sucesso, planilha vazia, coluna ausente)
- Template ({coluna} no assunto/corpo; coluna faltante -> "")
- Parcial / falha total
- Conexao (falha em connect/tls/login; starttls/login condicionais)
- dry-run (nao conecta; preview)
- Relatorio
- Progresso / HTML
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.send_email import SendEmailTask, SmtpConfig

if TYPE_CHECKING:
    from pathlib import Path


# ============================================================
# Helpers
# ============================================================


def criar_csv(path: Path, linhas: list[dict[str, str]]) -> None:
    pd.DataFrame(linhas).to_csv(path, index=False)


def linhas_ok(n: int) -> list[dict[str, str]]:
    return [
        {"nome": f"Pessoa {i}", "email": f"p{i}@destino.local", "codigo": f"C{i}"}
        for i in range(1, n + 1)
    ]


def smtp_local() -> SmtpConfig:
    return SmtpConfig(host="localhost", port=8025, usar_tls=False)


# ============================================================
# Fixture: fake smtplib.SMTP
# ============================================================


@pytest.fixture
def mock_smtp(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Troca smtplib.SMTP por um fake. Inspecione/configure via state:
      state["sent"]            -> lista de EmailMessage enviados
      state["login"]           -> (usuario, senha) ou None
      state["starttls"]        -> bool
      state["connected"]       -> bool (SMTP foi instanciado?)
      state["fail_on"]         -> None | "connect" | "tls" | "login"
      state["fail_recipient"]  -> destinatario que falha no send_message
    """
    state: dict[str, Any] = {
        "sent": [],
        "login": None,
        "starttls": False,
        "connected": False,
        "quit": False,
        "fail_on": None,
        "fail_recipient": None,
    }

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
            if state["fail_on"] == "connect":
                msg = "connect failed"
                raise OSError(msg)
            state["connected"] = True
            state["host"] = host
            state["port"] = port

        def starttls(self) -> None:
            if state["fail_on"] == "tls":
                msg = "tls failed"
                raise smtplib.SMTPException(msg)
            state["starttls"] = True

        def login(self, user: str, password: str) -> None:
            if state["fail_on"] == "login":
                raise smtplib.SMTPAuthenticationError(535, b"auth failed")
            state["login"] = (user, password)

        def send_message(self, msg: EmailMessage) -> None:
            to = msg["To"]
            if state["fail_recipient"] is not None and to == state["fail_recipient"]:
                raise smtplib.SMTPRecipientsRefused({to: (550, b"refused")})
            state["sent"].append(msg)

        def quit(self) -> None:
            state["quit"] = True

        def close(self) -> None:
            pass

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return state


# ============================================================
# Construtor
# ============================================================


class TestConstrutor:
    def test_planilha_extensao_invalida(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            SendEmailTask(
                planilha_path=tmp_path / "c.txt",
                smtp=smtp_local(),
                remetente="a@x.com",
                assunto="S",
                corpo="B",
            )

    def test_host_vazio(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendEmailTask(
                planilha_path=csv,
                smtp=SmtpConfig(host=""),
                remetente="a@x.com",
                assunto="S",
                corpo="B",
            )

    def test_remetente_vazio(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendEmailTask(
                planilha_path=csv,
                smtp=smtp_local(),
                remetente="",
                assunto="S",
                corpo="B",
            )

    def test_assunto_vazio(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendEmailTask(
                planilha_path=csv,
                smtp=smtp_local(),
                remetente="a@x.com",
                assunto="",
                corpo="B",
            )

    def test_report_extensao_invalida(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendEmailTask(
                planilha_path=csv,
                smtp=smtp_local(),
                remetente="a@x.com",
                assunto="S",
                corpo="B",
                report_path=tmp_path / "r.txt",
            )

    def test_delay_negativo(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendEmailTask(
                planilha_path=csv,
                smtp=smtp_local(),
                remetente="a@x.com",
                assunto="S",
                corpo="B",
                delay_s=-1.0,
            )


# ============================================================
# Envio
# ============================================================


class TestEnvio:
    def test_todas_sucesso(self, mock_smtp: dict[str, Any], tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(3))
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3
        assert len(mock_smtp["sent"]) == 3

    def test_planilha_vazia(self, mock_smtp: dict[str, Any], tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        csv.write_text("nome,email\n", encoding="utf-8")
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0
        assert mock_smtp["connected"] is False  # nem conectou

    def test_coluna_email_ausente(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, [{"nome": "Ana", "contato": "ana@x.com"}])
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.FAILURE


# ============================================================
# Template
# ============================================================


class TestTemplate:
    def test_substitui_no_assunto_e_corpo(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, [{"nome": "Maria", "email": "m@x.com", "codigo": "Z9"}])
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola {nome}!",
            corpo="Seu codigo: {codigo}",
        ).run()
        msg = mock_smtp["sent"][0]
        assert msg["Subject"] == "Ola Maria!"
        assert "Z9" in msg.get_content()

    def test_coluna_faltante_vira_vazio(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, [{"nome": "Ana", "email": "a@x.com"}])
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Oi {nome} {inexistente}",
            corpo="B",
        ).run()
        assert mock_smtp["sent"][0]["Subject"] == "Oi Ana "


# ============================================================
# Parcial / falha
# ============================================================


class TestParcialFalha:
    def test_destinatario_recusado_parcial(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_smtp["fail_recipient"] = "p2@destino.local"
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(3))
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.PARTIAL
        assert result.rows_affected == 2
        assert result.rows_failed == 1

    def test_email_vazio_falha_da_linha(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(
            csv,
            [
                {"nome": "Ana", "email": "a@x.com"},
                {"nome": "Sem", "email": ""},
            ],
        )
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.PARTIAL
        assert result.rows_affected == 1
        assert result.rows_failed == 1
        assert len(mock_smtp["sent"]) == 1  # so o valido foi enviado


# ============================================================
# Conexao
# ============================================================


class TestConexao:
    def test_falha_connect(self, mock_smtp: dict[str, Any], tmp_path: Path) -> None:
        mock_smtp["fail_on"] = "connect"
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.FAILURE
        assert result.error_message is not None

    def test_falha_login(self, mock_smtp: dict[str, Any], tmp_path: Path) -> None:
        mock_smtp["fail_on"] = "login"
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))
        result = SendEmailTask(
            planilha_path=csv,
            smtp=SmtpConfig(host="x", usuario="u", senha="p", usar_tls=False),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.status == TaskStatus.FAILURE

    def test_starttls_quando_tls(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendEmailTask(
            planilha_path=csv,
            smtp=SmtpConfig(host="x", usar_tls=True),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert mock_smtp["starttls"] is True

    def test_sem_starttls_quando_no_tls(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert mock_smtp["starttls"] is False

    def test_login_quando_usuario(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendEmailTask(
            planilha_path=csv,
            smtp=SmtpConfig(host="x", usuario="u@x", senha="p", usar_tls=False),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert mock_smtp["login"] == ("u@x", "p")

    def test_sem_login_quando_sem_usuario(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert mock_smtp["login"] is None


# ============================================================
# Dry-run
# ============================================================


class TestDryRun:
    def test_nao_conecta(self, mock_smtp: dict[str, Any], tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(5))
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola {nome}",
            corpo="Oi",
            dry_run=True,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["would_send"] == 5
        assert mock_smtp["connected"] is False
        assert mock_smtp["sent"] == []

    def test_preview_renderizado(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, [{"nome": "Ana", "email": "a@x.com"}])
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola {nome}!",
            corpo="Oi",
            dry_run=True,
        ).run()
        preview = result.data["preview"]
        assert preview[0]["assunto"] == "Ola Ana!"
        assert preview[0]["para"] == "a@x.com"


# ============================================================
# Relatorio
# ============================================================


class TestRelatorio:
    def test_salva_relatorio(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))
        report = tmp_path / "rel.csv"
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
            report_path=report,
        ).run()
        assert report.exists()
        df = pd.read_csv(report)
        assert "_resultado" in df.columns
        assert "_mensagem" in df.columns
        assert len(df) == 2

    def test_sem_relatorio(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))
        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
        ).run()
        assert result.data["report_path"] is None


# ============================================================
# Progresso / HTML
# ============================================================


class TestProgressoHtml:
    def test_callback_por_linha(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(3))
        chamadas: list[dict[str, Any]] = []
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
            on_progress=chamadas.append,
        ).run()
        assert len(chamadas) == 3
        assert chamadas[0]["para"] == "p1@destino.local"

    def test_callback_com_erro_nao_quebra(
        self,
        mock_smtp: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))

        def ruim(_info: dict[str, Any]) -> None:
            msg = "falhou"
            raise RuntimeError(msg)

        result = SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="Oi",
            on_progress=ruim,
        ).run()
        assert result.status == TaskStatus.SUCCESS

    def test_corpo_html(self, mock_smtp: dict[str, Any], tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, [{"nome": "Ana", "email": "a@x.com"}])
        SendEmailTask(
            planilha_path=csv,
            smtp=smtp_local(),
            remetente="robo@local",
            assunto="Ola",
            corpo="<b>Oi {nome}</b>",
            is_html=True,
        ).run()
        assert mock_smtp["sent"][0].get_content_type() == "text/html"
