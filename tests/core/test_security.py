"""Testes para autotarefas.core.security."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotarefas.core.exceptions import SecurityError
from autotarefas.core.security import (
    hash_string,
    is_within_directory,
    mask_sensitive_in_dict,
    safe_extension,
    safe_path,
    validate_filename,
    validate_url,
)


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


class TestValidateFilename:
    """Testes do validate_filename — 7 camadas defensivas."""

    # ---- Camada 1: Vazio ----

    def test_nome_valido_passa(self) -> None:
        assert validate_filename("relatorio.pdf") == "relatorio.pdf"

    def test_nome_vazio_falha(self) -> None:
        with pytest.raises(SecurityError, match="vazio"):
            validate_filename("")

    def test_nome_so_whitespace_falha(self) -> None:
        with pytest.raises(SecurityError, match="vazio"):
            validate_filename("   ")

    # ---- Camada 2: Tamanho ----

    def test_nome_muito_longo_falha(self) -> None:
        """Nome >255 chars e rejeitado."""
        nome_longo = "a" * 256
        with pytest.raises(SecurityError, match="muito longo"):
            validate_filename(nome_longo)

    def test_nome_no_limite_passa(self) -> None:
        """255 chars passa (limite inclusivo)."""
        nome = "a" * 255
        assert validate_filename(nome) == nome

    # ---- Camada 3: Path separators ----

    def test_separator_unix_falha(self) -> None:
        with pytest.raises(SecurityError, match="path separator"):
            validate_filename("pasta/arquivo.txt")

    def test_separator_windows_falha(self) -> None:
        with pytest.raises(SecurityError, match="path separator"):
            validate_filename("pasta\\arquivo.txt")

    # ---- Camada 4: Path traversal (. e ..) ----

    def test_dot_falha(self) -> None:
        with pytest.raises(SecurityError, match="navegacao"):
            validate_filename(".")

    def test_dot_dot_falha(self) -> None:
        with pytest.raises(SecurityError, match="navegacao"):
            validate_filename("..")

    # ---- Camada 5: Chars de controle ----

    def test_nul_byte_falha(self) -> None:
        with pytest.raises(SecurityError, match="char de controle"):
            validate_filename("arquivo\x00.txt")

    def test_tab_falha(self) -> None:
        """Tab (0x09) e char de controle."""
        with pytest.raises(SecurityError, match="char de controle"):
            validate_filename("arquivo\t.txt")

    def test_newline_falha(self) -> None:
        """Newline (0x0a) e char de controle."""
        with pytest.raises(SecurityError, match="char de controle"):
            validate_filename("arquivo\n.txt")

    # ---- Camada 6: Chars proibidos do Windows ----

    def test_pipe_falha(self) -> None:
        with pytest.raises(SecurityError, match="proibido"):
            validate_filename("arquivo|.txt")

    def test_aspas_falha(self) -> None:
        with pytest.raises(SecurityError, match="proibido"):
            validate_filename('arquivo".txt')

    def test_asterisco_falha(self) -> None:
        with pytest.raises(SecurityError, match="proibido"):
            validate_filename("arquivo*.txt")

    # ---- Camada 7: Nomes reservados do Windows ----

    def test_nome_reservado_con_falha(self) -> None:
        with pytest.raises(SecurityError, match="reservado"):
            validate_filename("CON")

    def test_nome_reservado_lpt1_falha(self) -> None:
        with pytest.raises(SecurityError, match="reservado"):
            validate_filename("LPT1")

    def test_nome_reservado_case_insensitive_falha(self) -> None:
        """'con' (lowercase) e tao reservado quanto 'CON'."""
        with pytest.raises(SecurityError, match="reservado"):
            validate_filename("con")

    def test_nome_reservado_com_extensao_falha(self) -> None:
        """'CON.txt' tambem e reservado (extensao nao salva)."""
        with pytest.raises(SecurityError, match="reservado"):
            validate_filename("CON.txt")

    # ---- Casos OK ----

    def test_unicode_pt_passa(self) -> None:
        """Acentos sao permitidos."""
        assert validate_filename("relatório.pdf") == "relatório.pdf"

    def test_underscore_passa(self) -> None:
        assert validate_filename("meu_arquivo.txt") == "meu_arquivo.txt"

    def test_numero_passa(self) -> None:
        assert validate_filename("dados_2026.csv") == "dados_2026.csv"


class TestSafeExtension:
    """Testes do safe_extension."""

    def test_extensao_permitida_passa(self) -> None:
        assert safe_extension("doc.pdf", [".pdf"]) == ".pdf"

    def test_case_insensitive_input_uppercase(self) -> None:
        """Extensao no nome em UPPERCASE casa com whitelist lowercase."""
        assert safe_extension("doc.PDF", [".pdf"]) == ".pdf"

    def test_case_insensitive_allowed_uppercase(self) -> None:
        """Whitelist UPPERCASE casa com extensao lowercase."""
        assert safe_extension("doc.pdf", [".PDF"]) == ".pdf"

    def test_multiplas_extensoes_permitidas(self) -> None:
        """Whitelist com varias extensoes."""
        assert safe_extension("doc.txt", [".pdf", ".txt", ".md"]) == ".txt"

    def test_extensao_nao_permitida_falha(self) -> None:
        with pytest.raises(SecurityError, match="nao permitida"):
            safe_extension("doc.exe", [".pdf"])

    def test_arquivo_sem_extensao_falha(self) -> None:
        with pytest.raises(SecurityError, match="sem extensao"):
            safe_extension("Makefile", [".pdf"])

    def test_trick_dupla_extensao_bloqueado(self) -> None:
        """'doc.pdf.exe' tem extensao final .exe — bloqueado."""
        with pytest.raises(SecurityError, match="nao permitida"):
            safe_extension("doc.pdf.exe", [".pdf"])

    def test_allowed_extensions_vazio_levanta_value_error(self) -> None:
        """Whitelist vazia e erro de programador (ValueError, nao Security)."""
        with pytest.raises(ValueError, match="nao pode ser vazio"):
            safe_extension("doc.pdf", [])


class TestIsWithinDirectory:
    """Testes do is_within_directory."""

    def test_child_diretamente_em_parent_true(self, tmp_path: Path) -> None:
        """Arquivo direto na pasta: True."""
        child = tmp_path / "arquivo.txt"
        assert is_within_directory(child, tmp_path) is True

    def test_child_em_subpasta_true(self, tmp_path: Path) -> None:
        """Arquivo em subpasta: True (recursivo)."""
        child = tmp_path / "sub" / "arquivo.txt"
        assert is_within_directory(child, tmp_path) is True

    def test_child_em_subpasta_profunda_true(self, tmp_path: Path) -> None:
        """Profundidade arbitraria: True."""
        child = tmp_path / "a" / "b" / "c" / "d" / "arquivo.txt"
        assert is_within_directory(child, tmp_path) is True

    def test_path_iguais_true(self, tmp_path: Path) -> None:
        """Path identico ao parent: True (esta dentro de si mesmo)."""
        assert is_within_directory(tmp_path, tmp_path) is True

    def test_child_fora_de_parent_false(self, tmp_path: Path) -> None:
        """Path completamente diferente: False."""
        # Cria pasta sibling fora do tmp_path
        outside = tmp_path.parent / "outra_pasta"
        assert is_within_directory(outside, tmp_path) is False

    def test_path_traversal_resolvido_false(self, tmp_path: Path) -> None:
        """tmp_path/../outro nao esta em tmp_path apos resolve."""
        # tmp_path/.. e o parent — fora de tmp_path
        outside = tmp_path / ".." / "fora"
        assert is_within_directory(outside, tmp_path) is False


class TestMaskSensitiveInDict:
    """Testes do mask_sensitive_in_dict."""

    def test_mascara_password(self) -> None:
        data = {"user": "ana", "password": "x123"}  # pragma: allowlist secret
        result = mask_sensitive_in_dict(data)
        assert result["password"] == "***"
        assert result["user"] == "ana"

    def test_mascara_senha_pt(self) -> None:
        data = {"usuario": "ana", "senha": "x123"}
        result = mask_sensitive_in_dict(data)
        assert result["senha"] == "***"

    def test_mascara_token(self) -> None:
        data = {"endpoint": "/api", "senha": "xyz"}
        result = mask_sensitive_in_dict(data)
        assert result["senha"] == "***"

    def test_mascara_cpf(self) -> None:
        data = {"nome": "Ana", "cpf": "111.222.333-44"}
        result = mask_sensitive_in_dict(data)
        assert result["cpf"] == "***"

    def test_mascara_case_insensitive(self) -> None:
        """'PASSWORD' (uppercase) tambem e mascarado."""
        data = {"PASSWORD": "x"}
        result = mask_sensitive_in_dict(data)
        assert result["PASSWORD"] == "***"

    def test_substring_match(self) -> None:
        """'user_password' contem 'password' — mascarado."""
        data = {"user_password": "x", "user_name": "ana"}
        result = mask_sensitive_in_dict(data)
        assert result["user_password"] == "***"
        assert result["user_name"] == "ana"  # nao tem keyword sensitivel

    def test_recursao_em_subdicts(self) -> None:
        """Sub-dicts sao processados recursivamente."""
        data = {
            "user": "ana",
            "credentials": {
                "username": "ana",
                "password": "x",
            },
        }
        result = mask_sensitive_in_dict(data)
        assert result["credentials"]["password"] == "***"
        assert result["credentials"]["username"] == "ana"

    def test_nao_modifica_original(self) -> None:
        """Dict original NAO e alterado (retorna nova copia)."""
        original = {"senha": "x123"}
        mask_sensitive_in_dict(original)
        # Original intacto
        assert original["senha"] == "x123"

    def test_dict_vazio_retorna_dict_vazio(self) -> None:
        assert mask_sensitive_in_dict({}) == {}

    def test_sem_keys_sensiveis_retorna_copia_igual(self) -> None:
        """Sem keys sensitivas: copia com mesmos valores."""
        data = {"nome": "Ana", "idade": 30, "ativo": True}
        result = mask_sensitive_in_dict(data)
        assert result == data
        # Mas e copia (id diferente)
        assert result is not data

    def test_valor_nao_dict_nao_modificado(self) -> None:
        """Tipos primitivos passam intactos."""
        data = {"a": 42, "b": "string", "c": [1, 2, 3], "d": None}
        result = mask_sensitive_in_dict(data)
        assert result == data
