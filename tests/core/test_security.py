"""Testes para autotarefas.core.security."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotarefas.core.exceptions import SecurityError
from autotarefas.core.security import hash_string, safe_path, validate_url


class TestSafePath:
    """Testes do safe_path."""

    def test_path_dentro_permitido(self, tmp_path: Path) -> None:
        target = tmp_path / "arquivo.txt"
        result = safe_path(target, [tmp_path])
        assert result == target.resolve()

    def test_subpasta_dentro_permitido(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "arquivo.txt"
        result = safe_path(target, [tmp_path])
        assert result == target.resolve()

    def test_path_fora_levanta(self, tmp_path: Path) -> None:
        """Path fora de allowed_roots levanta SecurityError."""
        # Duas subpastas isoladas dentro de tmp_path (seguro)
        permitida = tmp_path / "permitida"
        fora = tmp_path / "fora"
        permitida.mkdir()
        fora.mkdir()

        target = fora / "arquivo.txt"
        with pytest.raises(SecurityError, match="permitido"):
            safe_path(target, [permitida])

    def test_path_traversal_bloqueado(self, tmp_path: Path) -> None:
        """Tentativa de ../ pra escapar é bloqueada após resolve."""
        sub = tmp_path / "sub"
        sub.mkdir()
        # Tenta usar ../../.. pra escapar
        traversal = sub / ".." / ".." / "outro"
        # Após resolve(), traversal aponta pra fora de sub
        with pytest.raises(SecurityError):
            safe_path(traversal, [sub])

    def test_allowed_roots_vazio_levanta_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="vazio"):
            safe_path(tmp_path, [])

    def test_aceita_path_como_string(self, tmp_path: Path) -> None:
        target = tmp_path / "arquivo.txt"
        result = safe_path(str(target), [tmp_path])
        assert result == target.resolve()

    def test_multiplas_allowed_roots(self, tmp_path: Path) -> None:
        """Path pode estar em qualquer uma das allowed_roots."""
        root1 = tmp_path / "root1"
        root2 = tmp_path / "root2"
        root1.mkdir()
        root2.mkdir()

        target = root2 / "arquivo.txt"
        result = safe_path(target, [root1, root2])
        assert result == target.resolve()


class TestValidateUrl:
    """Testes do validate_url."""

    def test_https_valido(self) -> None:
        url = "https://example.com/page"
        assert validate_url(url) == url

    def test_http_em_dev_ok(self) -> None:
        url = "http://example.com"
        assert validate_url(url, environment="dev") == url

    def test_http_em_prod_levanta(self) -> None:
        with pytest.raises(SecurityError, match="HTTP"):
            validate_url("http://example.com", environment="prod")

    def test_https_em_prod_ok(self) -> None:
        url = "https://example.com"
        assert validate_url(url, environment="prod") == url

    def test_url_vazia_levanta(self) -> None:
        with pytest.raises(SecurityError, match="vazia"):
            validate_url("")

    def test_url_so_espacos_levanta(self) -> None:
        with pytest.raises(SecurityError, match="vazia"):
            validate_url("   ")

    def test_url_com_espacos_extremos_e_strippada(self) -> None:
        """URL com espaços nas pontas é limpa antes de validar."""
        result = validate_url("  https://example.com  ")
        assert result == "https://example.com"

    def test_sem_schema_levanta(self) -> None:
        with pytest.raises(SecurityError):
            validate_url("example.com")

    def test_schema_nao_suportado_levanta(self) -> None:
        with pytest.raises(SecurityError, match="Schema"):
            validate_url("ftp://example.com")

    def test_sem_host_levanta(self) -> None:
        with pytest.raises(SecurityError, match="host"):
            validate_url("https://")


class TestHashString:
    """Testes do hash_string."""

    def test_sha256_consistente(self) -> None:
        h1 = hash_string("teste")
        h2 = hash_string("teste")
        assert h1 == h2

    def test_sha256_tamanho_64_chars(self) -> None:
        h = hash_string("teste")
        assert len(h) == 64  # SHA-256 hex

    def test_strings_diferentes_geram_hashes_diferentes(self) -> None:
        h1 = hash_string("teste1")
        h2 = hash_string("teste2")
        assert h1 != h2

    def test_hmac_consistente(self) -> None:
        h1 = hash_string("teste", secret="chave")
        h2 = hash_string("teste", secret="chave")
        assert h1 == h2

    def test_hmac_tamanho_64_chars(self) -> None:
        h = hash_string("teste", secret="chave")
        assert len(h) == 64

    def test_hmac_diferente_de_sha256(self) -> None:
        h_plain = hash_string("teste")
        h_hmac = hash_string("teste", secret="chave")
        assert h_plain != h_hmac

    def test_secrets_diferentes_geram_hashes_diferentes(self) -> None:
        h1 = hash_string("teste", secret="chave1")
        h2 = hash_string("teste", secret="chave2")
        assert h1 != h2
