"""Testes para o comando CLI `autotarefas organize`."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.organize import organize
from autotarefas.cli.context import CLIContext

# ============================================================
# Helpers
# ============================================================


def _criar_arquivos(base: Path, files: list[str]) -> None:
    """Cria arquivos vazios."""
    for relative in files:
        full = base / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("conteudo", encoding="utf-8")


def _criar_yaml_rules(
    path: Path,
    target_root: Path,
    *,
    action: str = "move",
    on_conflict: str = "skip",
) -> None:
    """Cria YAML basico de regras."""
    content = (
        f"target_root: {target_root}\n"
        f"action: {action}\n"
        f"on_conflict: {on_conflict}\n"
        "rules:\n"
        "  - name: Imagens\n"
        '    patterns: ["*.jpg", "*.png"]\n'
        "    destination: imagens\n"
        "  - name: Documentos\n"
        '    patterns: ["*.pdf", "*.docx"]\n'
        "    destination: docs\n"
    )
    path.write_text(content, encoding="utf-8")


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def cli_ctx() -> CLIContext:
    return CLIContext()


@pytest.fixture
def cli_ctx_yes() -> CLIContext:
    return CLIContext(yes=True)


@pytest.fixture
def cli_ctx_dry_run() -> CLIContext:
    return CLIContext(dry_run=True)


@pytest.fixture
def source_pasta(tmp_path: Path) -> Path:
    """Pasta source com 4 arquivos (3 com regra, 1 sem)."""
    source = tmp_path / "downloads"
    source.mkdir()
    _criar_arquivos(
        source,
        ["foto1.jpg", "foto2.png", "doc.pdf", "sem_regra.xyz"],
    )
    return source


@pytest.fixture
def target_pasta(tmp_path: Path) -> Path:
    """Pasta target (vazia)."""
    target = tmp_path / "organizado"
    target.mkdir()
    return target


@pytest.fixture
def rules_yaml(tmp_path: Path, target_pasta: Path) -> Path:
    """YAML basico de regras."""
    path = tmp_path / "rules.yaml"
    _criar_yaml_rules(path, target_pasta)
    return path


# ============================================================
# Tests: Sucesso (com --yes pra pular confirmacao)
# ============================================================


class TestOrganizeCliSuccess:
    """Cenarios de sucesso (exit 0)."""

    def test_organize_exit_0(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        assert result.exit_code == 0

    def test_arquivos_movidos_de_verdade(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Arquivos batem regra e somem do source."""
        runner = CliRunner()
        runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )

        # foto1.jpg deve ter ido pra target
        assert (target_pasta / "imagens" / "foto1.jpg").exists()
        # E nao deve estar mais no source
        assert not (source_pasta / "foto1.jpg").exists()

    def test_sem_regra_fica_no_source(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Arquivos sem rule continuam no source."""
        runner = CliRunner()
        runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        assert (source_pasta / "sem_regra.xyz").exists()

    def test_output_mostra_estatisticas(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Output contem 'concluida' e numeros."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        assert "concluida" in result.output.lower()
        # 3 movidos
        assert "3" in result.output

    def test_action_copy_mantem_originais(
        self,
        source_pasta: Path,
        target_pasta: Path,
        tmp_path: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Action 'copy' nao remove do source."""
        rules_path = tmp_path / "copy_rules.yaml"
        _criar_yaml_rules(rules_path, target_pasta, action="copy")

        runner = CliRunner()
        runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_path)],
            obj=cli_ctx_yes,
        )

        # Source mantem foto1.jpg
        assert (source_pasta / "foto1.jpg").exists()
        # E destino tambem tem
        assert (target_pasta / "imagens" / "foto1.jpg").exists()


# ============================================================
# Tests: Confirmacao interativa (input=)
# ============================================================


class TestOrganizeCliConfirmation:
    """Confirmacao interativa via click.confirm."""

    def test_threshold_zero_pede_confirmacao_y(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Com --confirm-threshold 0, pede confirmacao. Usuario diz 'y'."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [
                str(source_pasta),
                "--rules",
                str(rules_yaml),
                "--confirm-threshold",
                "0",
            ],
            obj=cli_ctx,
            input="y\n",  # responde "y"
        )
        assert result.exit_code == 0
        # Arquivos foram movidos
        assert (target_pasta / "imagens" / "foto1.jpg").exists()

    def test_threshold_zero_usuario_diz_n(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Usuario diz 'n' -> cancela, exit 0, nada move."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [
                str(source_pasta),
                "--rules",
                str(rules_yaml),
                "--confirm-threshold",
                "0",
            ],
            obj=cli_ctx,
            input="n\n",
        )
        assert result.exit_code == 0
        # Nada moveu
        assert (source_pasta / "foto1.jpg").exists()
        assert not (target_pasta / "imagens").exists()
        # Output indica cancelamento
        assert "cancelada" in result.output.lower()

    def test_usuario_so_aperta_enter_cancela(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Apenas Enter (sem digitar) -> default=False -> cancela."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [
                str(source_pasta),
                "--rules",
                str(rules_yaml),
                "--confirm-threshold",
                "0",
            ],
            obj=cli_ctx,
            input="\n",  # so Enter
        )
        assert result.exit_code == 0
        # Nada moveu (default=False protege)
        assert (source_pasta / "foto1.jpg").exists()

    def test_no_confirm_pula_confirmacao(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """--no-confirm pula confirmacao mesmo acima do threshold."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [
                str(source_pasta),
                "--rules",
                str(rules_yaml),
                "--confirm-threshold",
                "0",
                "--no-confirm",
            ],
            obj=cli_ctx,
            # SEM input — nao deve pedir
        )
        assert result.exit_code == 0
        # Moveu
        assert (target_pasta / "imagens" / "foto1.jpg").exists()

    def test_threshold_alto_nao_pede(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Com threshold alto, nao pede confirmacao."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [
                str(source_pasta),
                "--rules",
                str(rules_yaml),
                "--confirm-threshold",
                "100",
            ],
            obj=cli_ctx,
            # SEM input — source tem 4 arquivos, threshold 100, nao pede
        )
        assert result.exit_code == 0
        # Moveu sem precisar de input
        assert (target_pasta / "imagens" / "foto1.jpg").exists()


# ============================================================
# Tests: Dry-run
# ============================================================


class TestOrganizeCliDryRun:
    """Modo --dry-run global."""

    def test_dry_run_nao_move(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        target_pasta: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        runner = CliRunner()
        runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_dry_run,
        )
        # Nada moveu
        assert (source_pasta / "foto1.jpg").exists()
        assert not (target_pasta / "imagens").exists()

    def test_dry_run_exit_0(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_dry_run,
        )
        assert result.exit_code == 0

    def test_dry_run_mostra_preview(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        """Output contem indicacao de dry-run + preview."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_dry_run,
        )
        assert "DRY-RUN" in result.output
        # Algum arquivo deve aparecer no preview
        assert "foto1.jpg" in result.output


# ============================================================
# Tests: Erros de uso (Click rejeita — exit 2)
# ============================================================


class TestOrganizeCliErrors:
    """Click rejeita por argumentos invalidos."""

    def test_source_inexistente_click_rejeita(
        self,
        rules_yaml: Path,
        cli_ctx: CLIContext,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            organize,
            ["/caminho/nao/existe", "--rules", str(rules_yaml)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_source_arquivo_em_vez_de_pasta(
        self,
        tmp_path: Path,
        rules_yaml: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """source_dir deve ser pasta, nao arquivo (file_okay=False)."""
        arquivo = tmp_path / "x.txt"
        arquivo.write_text("oi", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(arquivo), "--rules", str(rules_yaml)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_rules_inexistente_click_rejeita(
        self,
        source_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", "/nao/existe.yaml"],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_rules_yaml_invalido_exit_2(
        self,
        tmp_path: Path,
        source_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """YAML invalido (parse falha) -> exit 2."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("nao [eh ]} yaml: valido", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(bad_yaml)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2


# ============================================================
# Tests: Falhas (exit 1)
# ============================================================


class TestOrganizeCliFailure:
    """Cenarios de falha (exit 1)."""

    def test_error_count_maior_que_zero_exit_1(
        self,
        tmp_path: Path,
        source_pasta: Path,
        target_pasta: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Variavel desconhecida no destination -> error_count>0 -> exit 1."""
        rules_path = tmp_path / "bad_dest.yaml"
        # destination usa {variavel_inexistente}
        rules_path.write_text(
            f"target_root: {target_pasta}\n"
            "rules:\n"
            "  - name: BadRule\n"
            '    patterns: ["*.jpg"]\n'
            "    destination: img/{semana}\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_path)],
            obj=cli_ctx_yes,
        )
        # Pelo menos 1 arquivo (foto1.jpg) dispara error_count
        assert result.exit_code == 1

    def test_estrutura_yaml_invalida_exit_2(
        self,
        tmp_path: Path,
        source_pasta: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """YAML valido mas sem campos obrigatorios -> exit 2."""
        bad_yaml = tmp_path / "missing.yaml"
        # falta target_root
        bad_yaml.write_text(
            "rules:\n" "  - name: X\n" '    patterns: ["*.jpg"]\n' "    destination: docs\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(bad_yaml)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2


# ============================================================
# Tests: Skipped (vazio)
# ============================================================


class TestOrganizeCliSkipped:
    """Cenarios de SKIPPED."""

    def test_pasta_vazia_exit_0(
        self,
        tmp_path: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Pasta vazia -> SKIPPED -> exit 0."""
        vazia = tmp_path / "vazia"
        vazia.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(vazia), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        assert result.exit_code == 0

    def test_pasta_vazia_mostra_aviso(
        self,
        tmp_path: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Output indica que nada foi feito."""
        vazia = tmp_path / "vazia"
        vazia.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(vazia), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        # Alguma palavra-chave de "nada a fazer"
        out = result.output.lower()
        assert "nada" in out or "vazia" in out


# ============================================================
# Tests: Output
# ============================================================


class TestOrganizeCliOutput:
    """Verificacoes do formato do output."""

    def test_mostra_cabecalho_completo(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Cabecalho contem source, target, action, on_conflict."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        out_lower = result.output.lower()
        assert "source" in out_lower
        assert "target" in out_lower
        assert "action" in out_lower

    def test_mostra_nome_da_pasta_source(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        assert source_pasta.name in result.output

    def test_unmatched_aparece_no_output_quando_existe(
        self,
        source_pasta: Path,
        rules_yaml: Path,
        cli_ctx_yes: CLIContext,
    ) -> None:
        """Quando ha arquivo sem regra, output menciona."""
        runner = CliRunner()
        result = runner.invoke(
            organize,
            [str(source_pasta), "--rules", str(rules_yaml)],
            obj=cli_ctx_yes,
        )
        # source_pasta tem sem_regra.xyz (1 unmatched)
        out_lower = result.output.lower()
        assert "regra" in out_lower or "unmatched" in out_lower
