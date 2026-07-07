"""Testes para autotarefas.tasks.send_result."""

from __future__ import annotations

import pytest

from autotarefas.tasks.send_result import (
    ItemEnvio,
    classify_status,
    extract_external_id,
    falhas_por_categoria,
    idempotency_key,
    parse_retry_after,
    total_reenviaveis,
)


class TestClassifyStatus:
    @pytest.mark.parametrize(
        ("status", "categoria", "pode_reenviar"),
        [
            (200, "sucesso", False),
            (201, "sucesso", False),
            (400, "validacao", False),
            (422, "validacao", False),
            (409, "duplicado", False),
            (429, "rate_limit", True),
            (500, "temporario", True),
            (503, "temporario", True),
            (401, "outro", False),
            (404, "outro", False),
        ],
    )
    def test_politica_http(self, status: int, categoria: str, pode_reenviar: bool) -> None:
        assert classify_status(status) == (categoria, pode_reenviar)


class TestExtractExternalId:
    def test_id_direto(self) -> None:
        assert extract_external_id({"id": 42}) == "42"

    def test_id_dentro_de_data(self) -> None:
        # formato do sistema de demonstracao: {"status": "ok", "data": {...}}
        assert extract_external_id({"status": "ok", "data": {"id": 7}}) == "7"

    def test_record_id(self) -> None:
        assert extract_external_id({"record_id": "abc-123"}) == "abc-123"

    def test_sem_id(self) -> None:
        assert extract_external_id({"status": "ok"}) is None

    def test_corpo_nao_dict(self) -> None:
        assert extract_external_id(None) is None
        assert extract_external_id([1, 2]) is None

    def test_id_vazio_ignorado(self) -> None:
        assert extract_external_id({"id": ""}) is None


def _item(categoria: str, *, sucesso: bool, pode_reenviar: bool) -> ItemEnvio:
    return ItemEnvio(
        linha=2,
        status_http=None,
        categoria=categoria,  # type: ignore[arg-type]
        sucesso=sucesso,
        mensagem="",
        id_externo=None,
        idempotency_key="k",
        tentativas=1,
        pode_reenviar=pode_reenviar,
    )


class TestAgregadores:
    def test_falhas_por_categoria_ignora_sucessos(self) -> None:
        items = [
            _item("sucesso", sucesso=True, pode_reenviar=False),
            _item("validacao", sucesso=False, pode_reenviar=False),
            _item("validacao", sucesso=False, pode_reenviar=False),
            _item("duplicado", sucesso=False, pode_reenviar=False),
        ]
        assert falhas_por_categoria(items) == {"validacao": 2, "duplicado": 1}

    def test_total_reenviaveis(self) -> None:
        items = [
            _item("sucesso", sucesso=True, pode_reenviar=False),
            _item("temporario", sucesso=False, pode_reenviar=True),
            _item("rate_limit", sucesso=False, pode_reenviar=True),
            _item("validacao", sucesso=False, pode_reenviar=False),
        ]
        assert total_reenviaveis(items) == 2

    def test_to_dict(self) -> None:
        item = ItemEnvio(
            linha=3,
            status_http=201,
            categoria="sucesso",
            sucesso=True,
            mensagem="criado (id 9)",
            id_externo="9",
            idempotency_key="abc123",
            tentativas=2,
            pode_reenviar=False,
        )
        d = item.to_dict()
        assert d["linha"] == 3
        assert d["status_http"] == 201
        assert d["id_externo"] == "9"
        assert d["idempotency_key"] == "abc123"
        assert d["tentativas"] == 2
        assert d["pode_reenviar"] is False


class TestIdempotencyKey:
    def test_deterministica(self) -> None:
        payload = {"nome": "Ana", "cpf": "529.982.247-25"}
        assert idempotency_key(payload) == idempotency_key(payload)

    def test_ordem_das_chaves_nao_importa(self) -> None:
        a = {"nome": "Ana", "cpf": "1"}
        b = {"cpf": "1", "nome": "Ana"}
        assert idempotency_key(a) == idempotency_key(b)

    def test_payload_diferente_chave_diferente(self) -> None:
        assert idempotency_key({"nome": "Ana"}) != idempotency_key({"nome": "Bia"})

    def test_formato_hex_32(self) -> None:
        key = idempotency_key({"nome": "Ana"})
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


class TestParseRetryAfter:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            ("2", 2.0),
            ("0", 0.0),
            (" 10 ", 10.0),
            (None, None),
            ("", None),
            ("abc", None),
            ("-1", None),
            ("1.5", None),  # forma em segundos e inteira na RFC
        ],
    )
    def test_interpretacao(self, valor: str | None, esperado: float | None) -> None:
        assert parse_retry_after(valor) == esperado
