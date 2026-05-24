"""
Storage simples em JSON pro servidor demo.

Persistencia local sem dependencia de banco. Concorrencia
simples (locked write) pra suportar requests paralelos.

NAO usar em producao.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ============================================================
# Storage
# ============================================================


class Storage:
    """
    Storage em JSON com lock pra concorrencia.

    Arquivo eh criado no primeiro write. Reset com clear().
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """
        Args:
            data_dir: Pasta onde fica cadastros.json.
                Default: tools/demo_server/data/
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"

        self._data_dir = data_dir
        self._file = data_dir / "cadastros.json"
        self._lock = threading.Lock()

        # Garante diretorio
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Inicializa arquivo se nao existir
        if not self._file.exists():
            self._write_all([])

    # --------------------------------------------------------
    # Operacoes basicas
    # --------------------------------------------------------

    def list_all(self) -> list[dict[str, Any]]:
        """Retorna todos os cadastros (mais recente primeiro)."""
        return self._read_all()

    def find_by_id(self, record_id: int) -> dict[str, Any] | None:
        """Busca cadastro pelo ID. Retorna None se nao encontrar."""
        for record in self._read_all():
            if record["id"] == record_id:
                return record
        return None

    def find_by_cpf(self, cpf: str) -> dict[str, Any] | None:
        """Busca cadastro pelo CPF. Retorna None se nao encontrar."""
        for record in self._read_all():
            if record["cpf"] == cpf:
                return record
        return None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Cria novo cadastro. ID e auto-incrementado.

        Returns:
            Registro criado (com id e created_at preenchidos).
        """
        with self._lock:
            records = self._read_all()
            next_id = max([r["id"] for r in records], default=0) + 1

            record = {
                "id": next_id,
                "nome": data["nome"],
                "email": data["email"],
                "cpf": data["cpf"],
                "telefone": data.get("telefone", ""),
                "created_at": datetime.now(UTC).isoformat(),
            }

            records.append(record)
            self._write_all(records)

        return record

    def clear(self) -> None:
        """Apaga todos os cadastros."""
        with self._lock:
            self._write_all([])

    # --------------------------------------------------------
    # I/O
    # --------------------------------------------------------

    def _read_all(self) -> list[dict[str, Any]]:
        """Le todos os registros do arquivo."""
        try:
            text = self._file.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, list):
                return []
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_all(self, records: list[dict[str, Any]]) -> None:
        """Escreve lista completa no arquivo."""
        self._file.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
