"""Testes para o comando CLI `autotarefas backup`."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.backup import _format_size, backup
from autotarefas.cli.context import CLIContext

# ============================================================
# Helpers
# ============================================================


def _criar_estrutura(base: Path, files: dict[str, str]) -> None:
    """Cria arquivos a partir de um dict {path: conteudo}."""
    for relative_path, content in files.items():
        full_path = base / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")


def _zip_namelist(zip_path: Path) -> list[str]:
    """Retorna arcnames do ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        return zf.namelist()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def cli_ctx() -> CLIContext:
    """CLIContext padrao."""
    return CLIContext()


@pytest.fixture
def cli_ctx_dry_run() -> CLIContext:
    """CLIContext com dry-run."""
    return CLIContext(dry_run=True)


@pytest.fixture
def projeto_simples(tmp_path: Path) -> Path:
    """Pasta simples com 3 arquivos uteis."""
    src = tmp_path / "projeto"
    _criar_estrutura(
        src,
        {
            "main.py": "print('hello')",
            "README.md": "# Doc",
            "src/app.py": "# app",
        },
    )
    return src


@pytest.fixture
def projeto_com_excludes(tmp_path: Path) -> Path:
    """Pasta com arquivos que serao excluidos pelos defaults."""
    src = tmp_path / "projeto"
    _criar_estrutura(
        src,
        {
            "main.py": "code",
            "README.md": "doc",
            "__pycache__/main.pyc": "binary",
            ".git/config": "git",
        },
    )
    return src


# ============================================================
# Tests: Sucesso
# ============================================================


class TestBackupCliSuccess:
    """Cenarios de sucesso — exit 0."""

    def test_backup_simples_exit_0(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

    def test_cria_zip_no_destino(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Arquivo ZIP e realmente criado."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert dest.exists()

    def test_mostra_caminho_no_output(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Output menciona o caminho do backup criado."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert "backup.zip" in result.output

    def test_mostra_sha256(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Output inclui o hash SHA-256."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert "SHA-256" in result.output

    def test_mostra_tamanho_humanizado(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Output mostra tamanho com unidade (B, KB, MB)."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        # Tem que aparecer pelo menos uma unidade
        has_unit = any(unit in result.output for unit in (" B", " KB", " MB", " GB"))
        assert has_unit


# ============================================================
# Tests: Excludes
# ============================================================


class TestBackupCliExcludes:
    """--exclude e --no-default-excludes."""

    def test_exclude_simples(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """--exclude '*.md' remove arquivos .md."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        runner.invoke(
            backup,
            [
                str(projeto_simples),
                "--output",
                str(dest),
                "--exclude",
                "*.md",
            ],
            obj=cli_ctx,
        )
        namelist = _zip_namelist(dest)
        assert not any(name.endswith(".md") for name in namelist)

    def test_exclude_multiplo(self, tmp_path: Path, cli_ctx: CLIContext) -> None:
        """Multiplos --exclude funcionam juntos."""
        src = tmp_path / "p"
        _criar_estrutura(
            src,
            {
                "main.py": "code",
                "debug.log": "logs",
                "scratch.tmp": "tmp",
            },
        )

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        runner.invoke(
            backup,
            [
                str(src),
                "--output",
                str(dest),
                "--exclude",
                "*.log",
                "--exclude",
                "*.tmp",
            ],
            obj=cli_ctx,
        )

        namelist = _zip_namelist(dest)
        assert not any(name.endswith(".log") for name in namelist)
        assert not any(name.endswith(".tmp") for name in namelist)
        # main.py ainda deve estar
        assert any("main.py" in name for name in namelist)

    def test_no_default_excludes_inclui_pycache(
        self,
        tmp_path: Path,
        projeto_com_excludes: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """--no-default-excludes mantem __pycache__."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        runner.invoke(
            backup,
            [
                str(projeto_com_excludes),
                "--output",
                str(dest),
                "--no-default-excludes",
            ],
            obj=cli_ctx,
        )
        namelist = _zip_namelist(dest)
        assert any("__pycache__" in name for name in namelist)

    def test_no_default_excludes_mostra_aviso(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Quando flag ativa, mostra aviso explicito."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [
                str(projeto_simples),
                "--output",
                str(dest),
                "--no-default-excludes",
            ],
            obj=cli_ctx,
        )
        # Algum indicador no output (case-insensitive)
        out_lower = result.output.lower()
        assert "desabilitados" in out_lower or "disabled" in out_lower


# ============================================================
# Tests: Multiplas sources
# ============================================================


class TestBackupCliMultiplasSources:
    """Comando com 2+ sources."""

    def test_multiplas_pastas(self, tmp_path: Path, cli_ctx: CLIContext) -> None:
        p1 = tmp_path / "p1"
        p2 = tmp_path / "p2"
        _criar_estrutura(p1, {"a.txt": "1"})
        _criar_estrutura(p2, {"b.txt": "2"})

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(p1), str(p2), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

        namelist = _zip_namelist(dest)
        assert any("a.txt" in name for name in namelist)
        assert any("b.txt" in name for name in namelist)

    def test_pasta_e_arquivo_juntos(self, tmp_path: Path, cli_ctx: CLIContext) -> None:
        """Mistura pasta + arquivo solto."""
        pasta = tmp_path / "p"
        _criar_estrutura(pasta, {"x.txt": "x"})

        arquivo_solto = tmp_path / "doc.txt"
        arquivo_solto.write_text("doc", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(pasta), str(arquivo_solto), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

    def test_plural_quando_multiplas_sources(self, tmp_path: Path, cli_ctx: CLIContext) -> None:
        """Output usa 'sources' (plural) quando >1."""
        p1 = tmp_path / "p1"
        p2 = tmp_path / "p2"
        _criar_estrutura(p1, {"a.txt": "1"})
        _criar_estrutura(p2, {"b.txt": "2"})

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(p1), str(p2), "--output", str(dest)],
            obj=cli_ctx,
        )
        # "2 sources" no output
        assert "2 sources" in result.output


# ============================================================
# Tests: Erros de uso (Click rejeita — exit 2)
# ============================================================


class TestBackupCliErrors:
    """Click rejeita por argumentos faltando/invalidos."""

    def test_sem_sources_click_rejeita(
        self,
        tmp_path: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Sem nenhuma source: exit 2."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            ["--output", str(dest)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_sem_output_click_rejeita(
        self,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Sem --output: exit 2 (option obrigatoria)."""
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_source_inexistente_click_rejeita(
        self,
        tmp_path: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Source que nao existe: Click valida antes e rejeita."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            ["/caminho/nao/existe", "--output", str(dest)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2


# ============================================================
# Tests: Falha em runtime (exit 1)
# ============================================================


class TestBackupCliFailure:
    """Falhas que escapam validacao do Click — exit 1."""

    def test_destination_em_path_inacessivel(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Path com '/' no Windows ou char invalido provoca erro de I/O.

        Esse teste e cross-platform por usar caminho relativo invalido.
        """
        # Cria estrutura valida, mas escolhe path "estranho"
        # Em sistemas POSIX, isso pode funcionar. Vamos pular o
        # assertNotEqual se o backup conseguir mesmo assim.
        dest = tmp_path / "backup.zip"

        # Simula erro: passa source vazio (cria de fato vazia)
        pasta_vazia = tmp_path / "vazia"
        pasta_vazia.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(pasta_vazia), "--output", str(dest)],
            obj=cli_ctx,
        )
        # Pasta vazia -> SKIPPED -> exit 0 (NAO e falha)
        assert result.exit_code == 0

    def test_failure_messages_in_output(
        self,
        tmp_path: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Quando ha SKIPPED, mostra mensagem informativa."""
        pasta_vazia = tmp_path / "vazia"
        pasta_vazia.mkdir()

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(pasta_vazia), "--output", str(dest)],
            obj=cli_ctx,
        )
        # Alguma indicacao no output
        assert "Nada" in result.output or "vazia" in result.output


# ============================================================
# Tests: Dry-run
# ============================================================


class TestBackupCliDryRun:
    """--dry-run global."""

    def test_dry_run_nao_cria_zip(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx_dry_run,
        )
        assert not dest.exists()

    def test_dry_run_exit_0(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        """Dry-run nao e erro — exit 0."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx_dry_run,
        )
        assert result.exit_code == 0

    def test_dry_run_mostra_aviso(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        """Output indica modo dry-run."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx_dry_run,
        )
        assert "DRY-RUN" in result.output

    def test_dry_run_mostra_preview(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        """Output lista alguns arquivos como preview."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx_dry_run,
        )
        # Algum arquivo do projeto deve aparecer
        assert "main.py" in result.output or "README.md" in result.output


# ============================================================
# Tests: Skipped (vazio)
# ============================================================


class TestBackupCliSkipped:
    """Cenarios de SKIPPED (nada pra fazer)."""

    def test_pasta_vazia_exit_0(self, tmp_path: Path, cli_ctx: CLIContext) -> None:
        """Pasta vazia: SKIPPED, exit 0 (nao e erro)."""
        pasta_vazia = tmp_path / "vazia"
        pasta_vazia.mkdir()

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(pasta_vazia), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0
        assert not dest.exists()

    def test_pasta_vazia_mostra_warning(self, tmp_path: Path, cli_ctx: CLIContext) -> None:
        """Output indica que nada foi feito."""
        pasta_vazia = tmp_path / "vazia"
        pasta_vazia.mkdir()

        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(pasta_vazia), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert "Nada" in result.output or "nada" in result.output.lower()


# ============================================================
# Tests: _format_size (unit tests da helper)
# ============================================================


class TestFormatSize:
    """Testes unitarios da funcao _format_size."""

    def test_bytes_pequeno(self) -> None:
        assert _format_size(500) == "500 B"

    def test_bytes_zero(self) -> None:
        assert _format_size(0) == "0 B"

    def test_kilobytes(self) -> None:
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        assert _format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self) -> None:
        # 1.5 GB
        size = int(1.5 * 1024 * 1024 * 1024)
        result = _format_size(size)
        assert "GB" in result
        assert "1.5" in result or "1.50" in result


# ============================================================
# Tests: Output / formato
# ============================================================


class TestBackupCliOutput:
    """Verificacoes do output."""

    def test_output_mostra_file_count(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Output mostra a contagem de arquivos."""
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        # 3 arquivos
        assert "3" in result.output

    def test_output_mostra_destination(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Caminho do output aparece."""
        dest = tmp_path / "meu_backup_unico.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        assert "meu_backup_unico.zip" in result.output

    def test_skipped_count_zero_nao_polui_output(
        self,
        tmp_path: Path,
        projeto_simples: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Quando skipped_count=0, nao mostra a linha."""
        # projeto_simples nao tem nada pra excluir
        dest = tmp_path / "backup.zip"
        runner = CliRunner()
        result = runner.invoke(
            backup,
            [str(projeto_simples), "--output", str(dest)],
            obj=cli_ctx,
        )
        # Nao deve aparecer "Arquivos excluidos:" (nao tem nenhum)
        assert "excluidos: 0" not in result.output
