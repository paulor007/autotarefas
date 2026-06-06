"""Testes para autotarefas.core.logger."""

from __future__ import annotations

from autotarefas.core.logger import mask_sensitive


class TestMaskSensitiveCpfCnpj:
    """Testes de mascaramento de CPF e CNPJ."""

    def test_mascara_cpf_simples(self) -> None:
        result = mask_sensitive("CPF do cliente: 123.456.789-00")
        assert "123.456.789-00" not in result
        assert "***.***.***-XX" in result

    def test_mascara_cnpj(self) -> None:
        result = mask_sensitive("CNPJ: 12.345.678/0001-90")
        assert "12.345.678/0001-90" not in result
        assert "**.***.***/****-**" in result

    def test_mascara_multiplos_cpfs(self) -> None:
        result = mask_sensitive("CPFs: 111.222.333-44 e 999.888.777-66")
        assert "111.222.333-44" not in result
        assert "999.888.777-66" not in result
        # Deve ter 2 instâncias do mascarado
        assert result.count("***.***.***-XX") == 2


class TestMaskSensitivePassword:
    """Testes de mascaramento de senhas."""

    def test_mascara_password_em_ingles(self) -> None:
        result = mask_sensitive("password=segredo123")
        assert "segredo123" not in result
        assert "password=***" in result

    def test_mascara_pwd(self) -> None:
        result = mask_sensitive("pwd=hunter2")
        assert "hunter2" not in result
        assert "pwd=***" in result

    def test_mascara_senha_em_portugues(self) -> None:
        result = mask_sensitive("senha=minhasenha")
        assert "minhasenha" not in result
        assert "senha=***" in result

    def test_mascara_password_case_insensitive(self) -> None:
        result = mask_sensitive("PASSWORD=ABC")
        assert "ABC" not in result

    def test_mascara_password_com_dois_pontos(self) -> None:
        result = mask_sensitive("password: meusegredo")
        assert "meusegredo" not in result


class TestMaskSensitiveTokens:
    """Testes de mascaramento de tokens."""

    def test_mascara_token(self) -> None:
        result = mask_sensitive("token=ghp_xyz123abc")
        assert "ghp_xyz123abc" not in result
        assert "token=***" in result

    def test_mascara_api_key_underscore(self) -> None:
        result = mask_sensitive("api_key=sk-abc123def456")
        assert "sk-abc123def456" not in result

    def test_mascara_api_key_hifen(self) -> None:
        result = mask_sensitive("api-key=valor123")
        assert "valor123" not in result

    def test_mascara_bearer_token(self) -> None:
        result = mask_sensitive("Authorization: Bearer eyJhbGc.xyz.abc")
        assert "eyJhbGc.xyz.abc" not in result
        assert "Bearer ***" in result


class TestMaskSensitiveEmail:
    """Testes de mascaramento de email."""

    def test_mascara_email_padrao(self) -> None:
        result = mask_sensitive("Email: paulo@gmail.com")
        assert "paulo@gmail.com" not in result
        assert "p***@gmail.com" in result

    def test_mascara_email_no_meio_da_frase(self) -> None:
        result = mask_sensitive("Login do user joao.silva@empresa.com.br falhou")
        assert "joao.silva@empresa.com.br" not in result
        assert "@empresa.com.br" in result

    def test_mascara_multiplos_emails(self) -> None:
        result = mask_sensitive("De: a@x.com Para: b@y.com")
        assert "a@x.com" not in result
        assert "b@y.com" not in result


class TestMaskSensitiveSeguro:
    """Testes que strings sem dados sensíveis não são modificadas."""

    def test_nao_modifica_string_simples(self) -> None:
        original = "Hello World"
        assert mask_sensitive(original) == original

    def test_nao_modifica_numero_aleatorio(self) -> None:
        # 12345 não é CPF nem CNPJ
        original = "Total de itens: 12345"
        assert mask_sensitive(original) == original

    def test_nao_modifica_palavra_que_contem_password(self) -> None:
        # 'password' sozinha sem '=' ou ':' não é mascarada
        original = "Mude sua password regularmente"
        assert "Mude sua password regularmente" in mask_sensitive(original)


class TestMaskSensitiveCombinado:
    """Testes com múltiplos tipos sensíveis na mesma string."""

    def test_mascara_cpf_email_e_token(self) -> None:
        result = mask_sensitive(
            "Cliente CPF 123.456.789-00, email paulo@gmail.com, token=abc123xyz"
        )
        assert "123.456.789-00" not in result
        assert "paulo@gmail.com" not in result
        assert "abc123xyz" not in result
        # Mas mantém estrutura
        assert "***.***.***-XX" in result
        assert "@gmail.com" in result
        assert "token=***" in result


class TestLogger:
    """Testes do logger configurado."""

    def test_logger_importavel(self) -> None:
        """Logger pode ser importado."""
        from autotarefas.core.logger import logger

        assert logger is not None

    def test_logger_funciona(self) -> None:
        """Logger consegue logar sem erro."""
        from autotarefas.core.logger import logger

        # Não deve lançar exceção
        logger.info("Teste de log INFO")
        logger.warning("Teste de log WARNING")
        logger.error("Teste de log ERROR")
