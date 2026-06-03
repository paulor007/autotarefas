r"""
Servidor SMTP de debug local — alvo de teste para a EmailTask.

Recebe emails (NAO envia para a internet), mostra cada um no console e
salva como .eml em ./emails_recebidos/, para inspecao.

USO:
    pip install -e ".[demo]"
    python -m tools.smtp_debug          # escuta em localhost:8025

Em outro terminal, aponte a EmailTask para localhost:8025 (sem TLS,
sem login) e os emails aparecem aqui.

Ctrl+C para parar.

Destino deste arquivo:
    tools/smtp_debug.py
"""

from __future__ import annotations

import time
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import Any, cast

from aiosmtpd.controller import Controller

HOST = "localhost"
PORT = 8025
SAVE_DIR = Path("emails_recebidos")
_BODY_PREVIEW = 800


class DebugHandler:
    """Mostra no console e salva cada email recebido."""

    def __init__(self, save_dir: Path) -> None:
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.count = 0

    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
        """Processa uma mensagem recebida pelo servidor SMTP."""
        # server/session fazem parte da assinatura do aiosmtpd (nao usados)
        del server, session

        content = envelope.content
        if isinstance(content, str):
            content = content.encode("utf-8", errors="replace")

        msg = cast(
            EmailMessage,
            BytesParser(policy=cast(Any, policy.default)).parsebytes(content),
        )

        assunto = msg.get("Subject", "(sem assunto)")
        de = msg.get("From", envelope.mail_from or "?")
        para = ", ".join(envelope.rcpt_tos)

        self.count += 1
        print("=" * 60)
        print(f"Email #{self.count}")
        print(f"De:      {de}")
        print(f"Para:    {para}")
        print(f"Assunto: {assunto}")

        corpo = msg.get_body(preferencelist=("plain", "html"))
        if corpo is not None:
            texto = corpo.get_content()
            print("-" * 60)
            print(texto.strip()[:_BODY_PREVIEW])
        print("=" * 60)
        print("")

        nome = f"email_{self.count:03d}.eml"
        (self.save_dir / nome).write_bytes(content)

        return "250 Message accepted for delivery"


def main() -> None:
    """Sobe o servidor e mantem o processo vivo ate Ctrl+C."""
    handler = DebugHandler(SAVE_DIR)
    controller = Controller(handler, hostname=HOST, port=PORT)
    controller.start()

    print(f"Servidor SMTP de debug ouvindo em {HOST}:{PORT}")
    print(f"Emails salvos em ./{SAVE_DIR}/")
    print("Aponte a EmailTask para este host (sem TLS, sem login).")
    print("Ctrl+C para parar.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nParando o servidor...")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
