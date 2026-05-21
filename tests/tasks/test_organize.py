"""Testes para autotarefas.tasks.organize."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.organize import (
    OrganizeTask,
    Rule,
    RuleSet,
    load_rules,
)

# ============================================================
# Helpers
# ============================================================


def _criar_arquivos(base: Path, files: list[str]) -> None:
    """Cria arquivos vazios na pasta (com conteudo placeholder)."""
    for relative in files:
        full = base / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("conteudo", encoding="utf-8")


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def target_pasta(tmp_path: Path) -> Path:
    """Pasta de destino para organizacao."""
    target = tmp_path / "organizado"
    target.mkdir()
    return target


@pytest.fixture
def rules_basicas(target_pasta: Path) -> RuleSet:
    """RuleSet basico com 3 regras."""
    return RuleSet(
        target_root=target_pasta,
        rules=[
            Rule(
                name="Imagens",
                patterns=["*.jpg", "*.png"],
                destination="imagens",
            ),
            Rule(
                name="PDFs",
                patterns=["*.pdf"],
                destination="documentos/pdfs",
            ),
            Rule(
                name="Executaveis",
                patterns=["*.exe"],
                destination="instaladores",
            ),
        ],
    )


@pytest.fixture
def source_com_arquivos(tmp_path: Path) -> Path:
    """Pasta source com varios arquivos."""
    source = tmp_path / "downloads"
    source.mkdir()
    _criar_arquivos(
        source,
        [
            "foto1.jpg",
            "foto2.png",
            "documento.pdf",
            "instalador.exe",
            "sem_regra.xyz",
        ],
    )
    return source


# ============================================================
# Tests: Rule (Pydantic)
# ============================================================


class TestRule:
    """Validacao do modelo Rule."""

    def test_cria_rule_valida(self) -> None:
        rule = Rule(
            name="Test",
            patterns=["*.txt"],
            destination="docs",
        )
        assert rule.name == "Test"
        assert rule.patterns == ["*.txt"]

    def test_rule_sem_name_falha(self) -> None:
        with pytest.raises(PydanticValidationError):
            Rule(patterns=["*.txt"], destination="docs")  # type: ignore[call-arg]

    def test_rule_sem_patterns_falha(self) -> None:
        with pytest.raises(PydanticValidationError):
            Rule(name="X", destination="docs")  # type: ignore[call-arg]

    def test_rule_patterns_vazios_falha(self) -> None:
        """Patterns nao podem ser strings vazias."""
        with pytest.raises(PydanticValidationError):
            Rule(
                name="X",
                patterns=["", "*.jpg"],  # primeiro vazio
                destination="docs",
            )

    def test_rule_extra_field_forbid(self) -> None:
        """Campos desconhecidos sao rejeitados (extra='forbid')."""
        with pytest.raises(PydanticValidationError):
            Rule(
                name="X",
                patterns=["*.jpg"],
                destination="docs",
                campo_inventado="x",  # type: ignore[call-arg]
            )


# ============================================================
# Tests: RuleSet (Pydantic)
# ============================================================


class TestRuleSet:
    """Validacao do modelo RuleSet."""

    def test_cria_ruleset_basico(self, tmp_path: Path) -> None:
        ruleset = RuleSet(
            target_root=tmp_path,
            rules=[Rule(name="X", patterns=["*.txt"], destination="docs")],
        )
        assert ruleset.target_root == tmp_path

    def test_default_on_conflict_skip(self, tmp_path: Path) -> None:
        """Default de on_conflict e 'skip'."""
        ruleset = RuleSet(
            target_root=tmp_path,
            rules=[Rule(name="X", patterns=["*.txt"], destination="docs")],
        )
        assert ruleset.on_conflict == "skip"

    def test_default_action_move(self, tmp_path: Path) -> None:
        """Default de action e 'move'."""
        ruleset = RuleSet(
            target_root=tmp_path,
            rules=[Rule(name="X", patterns=["*.txt"], destination="docs")],
        )
        assert ruleset.action == "move"

    def test_ruleset_sem_rules_falha(self, tmp_path: Path) -> None:
        """RuleSet precisa de pelo menos 1 rule."""
        with pytest.raises(PydanticValidationError):
            RuleSet(target_root=tmp_path, rules=[])

    def test_ruleset_on_conflict_invalido_falha(self, tmp_path: Path) -> None:
        """on_conflict so aceita skip/rename/overwrite."""
        with pytest.raises(PydanticValidationError):
            RuleSet(
                target_root=tmp_path,
                rules=[Rule(name="X", patterns=["*.txt"], destination="docs")],
                on_conflict="invalido",  # type: ignore[arg-type]
            )


# ============================================================
# Tests: load_rules
# ============================================================


class TestLoadRules:
    """Carregamento de RuleSet de YAML."""

    def test_arquivo_inexistente_levanta(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="nao encontrado"):
            load_rules(tmp_path / "nao_existe.yaml")

    def test_yaml_invalido_levanta(self, tmp_path: Path) -> None:
        """YAML malformado: levanta ValidationError."""
        path = tmp_path / "ruim.yaml"
        path.write_text("nao [eh ]} yaml: valido", encoding="utf-8")

        with pytest.raises(ValidationError, match="invalido"):
            load_rules(path)

    def test_yaml_lista_em_vez_de_dict_levanta(self, tmp_path: Path) -> None:
        """YAML deve ser dict no topo."""
        path = tmp_path / "lista.yaml"
        path.write_text("- a\n- b\n", encoding="utf-8")

        with pytest.raises(ValidationError, match="dicionario"):
            load_rules(path)

    def test_estrutura_invalida_levanta(self, tmp_path: Path) -> None:
        """YAML valido mas sem target_root."""
        path = tmp_path / "x.yaml"
        path.write_text(
            "rules:\n" "  - name: X\n" "    patterns: ['*.jpg']\n" "    destination: docs\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="invalida"):
            load_rules(path)

    def test_carrega_ruleset_completo(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.yaml"
        path.write_text(
            f"target_root: {tmp_path / 'out'}\n"
            "on_conflict: rename\n"
            "action: copy\n"
            "rules:\n"
            "  - name: Imagens\n"
            "    patterns: ['*.jpg', '*.png']\n"
            "    destination: imagens/{year}\n",
            encoding="utf-8",
        )

        ruleset = load_rules(path)
        assert ruleset.action == "copy"
        assert ruleset.on_conflict == "rename"
        assert len(ruleset.rules) == 1
        assert ruleset.rules[0].name == "Imagens"


# ============================================================
# Tests: OrganizeTask basico
# ============================================================


class TestOrganizeTaskBasico:
    """Fluxos felizes de organizacao."""

    def test_organize_arquivos_simples(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
    ) -> None:
        task = OrganizeTask(source_dir=source_com_arquivos, rules=rules_basicas)
        result = task.run()

        assert result.is_success
        # 5 arquivos, 4 batem regra, 1 sem regra
        assert result.data["moved_count"] == 4
        assert result.data["unmatched_count"] == 1

    def test_move_arquivos_pro_destino(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
        target_pasta: Path,
    ) -> None:
        """Action 'move' realmente move os arquivos."""
        OrganizeTask(source_dir=source_com_arquivos, rules=rules_basicas).run()

        # Arquivos moveram: nao estao mais no source (exceto sem_regra)
        files_source = [f.name for f in source_com_arquivos.iterdir()]
        assert "foto1.jpg" not in files_source
        assert "documento.pdf" not in files_source
        assert "sem_regra.xyz" in files_source  # ficou (unmatched)

        # Estao no destino
        assert (target_pasta / "imagens" / "foto1.jpg").exists()
        assert (target_pasta / "documentos" / "pdfs" / "documento.pdf").exists()

    def test_copy_action_mantem_original(
        self,
        source_com_arquivos: Path,
        target_pasta: Path,
    ) -> None:
        """Action 'copy' nao remove do source."""
        rules = RuleSet(
            target_root=target_pasta,
            action="copy",
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        OrganizeTask(source_dir=source_com_arquivos, rules=rules).run()

        # Arquivo continua no source
        assert (source_com_arquivos / "foto1.jpg").exists()
        # E foi pro destino
        assert (target_pasta / "img" / "foto1.jpg").exists()

    def test_result_inclui_metadados(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
    ) -> None:
        result = OrganizeTask(source_dir=source_com_arquivos, rules=rules_basicas).run()

        for key in (
            "source_dir",
            "target_root",
            "action",
            "total_files",
            "moved_count",
            "skipped_count",
            "error_count",
            "unmatched_count",
            "operations",
        ):
            assert key in result.data

    def test_rows_affected_igual_moved_count(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
    ) -> None:
        result = OrganizeTask(source_dir=source_com_arquivos, rules=rules_basicas).run()
        assert result.rows_affected == result.data["moved_count"]

    def test_operations_tem_info_por_arquivo(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
    ) -> None:
        """operations[i] tem source, destination, rule_name, action, status."""
        result = OrganizeTask(source_dir=source_com_arquivos, rules=rules_basicas).run()

        ops = result.data["operations"]
        assert len(ops) == 5

        for op in ops:
            assert "source" in op
            assert "destination" in op
            assert "rule_name" in op
            assert "action" in op
            assert "status" in op


# ============================================================
# Tests: Matching de regras
# ============================================================


class TestOrganizeTaskMatching:
    """Testes do match (qual rule pega qual arquivo)."""

    def test_primeira_rule_que_bate_ganha(self, tmp_path: Path, target_pasta: Path) -> None:
        """Quando 2 rules batem, a primeira ganha."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("img")

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(name="A", patterns=["*.jpg"], destination="a"),
                Rule(name="B", patterns=["*.jpg"], destination="b"),  # nunca aplica
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        # foi pra "a", nao "b"
        assert (target_pasta / "a" / "foto.jpg").exists()
        assert not (target_pasta / "b").exists()
        # rule_name na operations confirma
        assert result.data["operations"][0]["rule_name"] == "A"

    def test_arquivos_sem_regra_unmatched(self, tmp_path: Path, target_pasta: Path) -> None:
        """Arquivo sem regra fica como unmatched."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "sem_regra.xyz").write_text("?")

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(name="JPG", patterns=["*.jpg"], destination="img"),
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        assert result.data["unmatched_count"] == 1
        # Arquivo nao moveu
        assert (source / "sem_regra.xyz").exists()

    def test_unmatched_count_correto(self, tmp_path: Path, target_pasta: Path) -> None:
        """Conta corretamente arquivos sem regra."""
        source = tmp_path / "src"
        source.mkdir()
        _criar_arquivos(
            source,
            ["a.xyz", "b.xyz", "c.xyz", "foto.jpg"],
        )

        rules = RuleSet(
            target_root=target_pasta,
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        assert result.data["unmatched_count"] == 3
        assert result.data["moved_count"] == 1

    def test_multiplos_patterns_por_rule(self, tmp_path: Path, target_pasta: Path) -> None:
        """Rule com varios patterns pega todos."""
        source = tmp_path / "src"
        source.mkdir()
        _criar_arquivos(source, ["a.jpg", "b.png", "c.gif"])

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(
                    name="Imagens",
                    patterns=["*.jpg", "*.png", "*.gif"],
                    destination="img",
                ),
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        assert result.data["moved_count"] == 3
        assert result.data["unmatched_count"] == 0


# ============================================================
# Tests: Variaveis no destination
# ============================================================


class TestOrganizeTaskVariaveis:
    """Resolucao de variaveis ({year}, {month:02d}, etc)."""

    def test_year_resolvido_no_destination(self, tmp_path: Path, target_pasta: Path) -> None:
        """{year} vira string do ano."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("img")

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(
                    name="Imagens",
                    patterns=["*.jpg"],
                    destination="imagens/{year}",
                ),
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        # Algum ano deve aparecer no destination
        dest = result.data["operations"][0]["destination"]
        # Pelo menos um dos anos atuais ou recentes
        assert any(str(year) in dest for year in (2024, 2025, 2026))

    def test_month_com_padding(self, tmp_path: Path, target_pasta: Path) -> None:
        """{month:02d} formata com 2 digitos."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("img")

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(
                    name="Imagens",
                    patterns=["*.jpg"],
                    destination="img/{month:02d}",
                ),
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        # destination contem mes com 2 digitos
        dest = result.data["operations"][0]["destination"]
        # Algum padrao "/01/" ate "/12/" deve aparecer
        has_padded_month = any(f"/{m:02d}/" in dest.replace("\\", "/") for m in range(1, 13))
        # Ou no final: "/05" (sem barra final)
        has_padded_month_end = any(
            dest.replace("\\", "/").endswith(f"/{m:02d}") for m in range(1, 13)
        )
        # Ou na sub-pasta sem extensao
        assert has_padded_month or has_padded_month_end

    def test_ext_lowercase(self, tmp_path: Path, target_pasta: Path) -> None:
        """{ext} retorna extensao em lowercase, sem ponto."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.JPG").write_text("img")  # uppercase

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(
                    name="Imagens",
                    patterns=["*.JPG", "*.jpg"],
                    destination="por_ext/{ext}",
                ),
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        dest = result.data["operations"][0]["destination"]
        # "/jpg/" lowercase
        assert "/jpg/" in dest.replace("\\", "/") or dest.replace("\\", "/").endswith(
            "/jpg/foto.JPG"
        )

    def test_variavel_desconhecida_gera_error(self, tmp_path: Path, target_pasta: Path) -> None:
        """{variavel_inexistente} causa erro."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("img")

        rules = RuleSet(
            target_root=target_pasta,
            rules=[
                Rule(
                    name="X",
                    patterns=["*.jpg"],
                    destination="img/{semana}",  # nao existe
                ),
            ],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        # Operacao errou
        assert result.data["error_count"] == 1
        op = result.data["operations"][0]
        assert op["status"] == "error"
        assert "semana" in (op["error"] or "")


# ============================================================
# Tests: Conflict handling
# ============================================================


class TestOrganizeTaskConflito:
    """Comportamento quando destino ja existe."""

    def test_skip_quando_destino_existe(self, tmp_path: Path, target_pasta: Path) -> None:
        """on_conflict=skip: arquivo no source NAO move."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("novo")

        # Cria arquivo ja existente no destino
        dest_dir = target_pasta / "img"
        dest_dir.mkdir()
        (dest_dir / "foto.jpg").write_text("antigo")

        rules = RuleSet(
            target_root=target_pasta,
            on_conflict="skip",
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        assert result.data["skipped_count"] == 1
        # Source nao foi movido
        assert (source / "foto.jpg").exists()
        # Destino mantem conteudo original
        assert (dest_dir / "foto.jpg").read_text() == "antigo"

    def test_rename_gera_arquivo_unico(self, tmp_path: Path, target_pasta: Path) -> None:
        """on_conflict=rename: gera foto_1.jpg, foto_2.jpg, etc."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("novo")

        # Cria arquivo ja existente
        dest_dir = target_pasta / "img"
        dest_dir.mkdir()
        (dest_dir / "foto.jpg").write_text("antigo")

        rules = RuleSet(
            target_root=target_pasta,
            on_conflict="rename",
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        assert result.data["moved_count"] == 1
        # foto_1.jpg foi criado
        assert (dest_dir / "foto_1.jpg").exists()
        # Original mantido
        assert (dest_dir / "foto.jpg").read_text() == "antigo"

    def test_overwrite_sobrescreve(self, tmp_path: Path, target_pasta: Path) -> None:
        """on_conflict=overwrite: substitui."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("novo")

        dest_dir = target_pasta / "img"
        dest_dir.mkdir()
        (dest_dir / "foto.jpg").write_text("antigo")

        rules = RuleSet(
            target_root=target_pasta,
            on_conflict="overwrite",
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        OrganizeTask(source_dir=source, rules=rules).run()

        # Conteudo agora e o novo
        assert (dest_dir / "foto.jpg").read_text() == "novo"

    def test_rename_multiplas_vezes(self, tmp_path: Path, target_pasta: Path) -> None:
        """Com varios conflitos, gera _1, _2, _3..."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "foto.jpg").write_text("novo")

        dest_dir = target_pasta / "img"
        dest_dir.mkdir()
        # Cria foto.jpg e foto_1.jpg ja
        (dest_dir / "foto.jpg").write_text("v0")
        (dest_dir / "foto_1.jpg").write_text("v1")

        rules = RuleSet(
            target_root=target_pasta,
            on_conflict="rename",
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        OrganizeTask(source_dir=source, rules=rules).run()

        # foto_2.jpg deve ter sido criado
        assert (dest_dir / "foto_2.jpg").exists()


# ============================================================
# Tests: Dry-run
# ============================================================


class TestOrganizeTaskDryRun:
    """Modo simulacao."""

    def test_dry_run_nao_move(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
        target_pasta: Path,
    ) -> None:
        """Dry-run nao move/copia nenhum arquivo."""
        OrganizeTask(
            source_dir=source_com_arquivos,
            rules=rules_basicas,
            dry_run=True,
        ).run()

        # Todos arquivos ainda no source
        files = sorted(f.name for f in source_com_arquivos.iterdir())
        assert "foto1.jpg" in files
        assert "documento.pdf" in files

        # Nada criado no destino
        assert list(target_pasta.iterdir()) == []

    def test_dry_run_status_dry_run(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
    ) -> None:
        """Status retornado e DRY_RUN."""
        result = OrganizeTask(
            source_dir=source_com_arquivos,
            rules=rules_basicas,
            dry_run=True,
        ).run()
        assert result.status == TaskStatus.DRY_RUN

    def test_dry_run_inclui_operations(
        self,
        source_com_arquivos: Path,
        rules_basicas: RuleSet,
    ) -> None:
        """Operations sao listadas mesmo em dry-run."""
        result = OrganizeTask(
            source_dir=source_com_arquivos,
            rules=rules_basicas,
            dry_run=True,
        ).run()

        # 5 arquivos -> 5 operations
        assert len(result.data["operations"]) == 5
        # 4 com status="success" (seriam movidos)
        success_count = sum(1 for op in result.data["operations"] if op["status"] == "success")
        assert success_count == 4


# ============================================================
# Tests: Validacao
# ============================================================


class TestOrganizeTaskValidacao:
    """Erros de input."""

    def test_source_inexistente_falha(self, tmp_path: Path, rules_basicas: RuleSet) -> None:
        task = OrganizeTask(
            source_dir=tmp_path / "nao_existe",
            rules=rules_basicas,
        )
        result = task.run()

        assert result.is_failure
        assert "nao encontrado" in (result.error_message or "")

    def test_source_nao_diretorio_falha(self, tmp_path: Path, rules_basicas: RuleSet) -> None:
        """source_dir deve ser diretorio, nao arquivo."""
        arquivo = tmp_path / "x.txt"
        arquivo.write_text("oi", encoding="utf-8")

        task = OrganizeTask(source_dir=arquivo, rules=rules_basicas)
        result = task.run()

        assert result.is_failure
        assert "diretorio" in (result.error_message or "")


# ============================================================
# Tests: Skipped (vazio)
# ============================================================


class TestOrganizeTaskSkipped:
    """SKIPPED quando nao ha arquivos."""

    def test_pasta_vazia_skipped(self, tmp_path: Path, rules_basicas: RuleSet) -> None:
        """Pasta sem arquivos: SKIPPED."""
        vazia = tmp_path / "vazia"
        vazia.mkdir()

        result = OrganizeTask(source_dir=vazia, rules=rules_basicas).run()

        assert result.status == TaskStatus.SKIPPED

    def test_so_subpastas_skipped(self, tmp_path: Path, rules_basicas: RuleSet) -> None:
        """Source so com subpastas (sem arquivos diretos): SKIPPED."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "subpasta").mkdir()

        result = OrganizeTask(source_dir=source, rules=rules_basicas).run()

        assert result.status == TaskStatus.SKIPPED


# ============================================================
# Tests: Recursividade (NAO eh)
# ============================================================


class TestOrganizeTaskRecursividade:
    """Confirma que NAO eh recursivo."""

    def test_nao_recursivo_ignora_subpastas(self, tmp_path: Path, target_pasta: Path) -> None:
        """Arquivos dentro de subpastas NAO sao processados."""
        source = tmp_path / "src"
        source.mkdir()

        # Arquivo direto (deve ser processado)
        (source / "direto.jpg").write_text("img1")

        # Arquivo em subpasta (deve ser ignorado)
        subpasta = source / "subpasta"
        subpasta.mkdir()
        (subpasta / "profundo.jpg").write_text("img2")

        rules = RuleSet(
            target_root=target_pasta,
            rules=[Rule(name="JPG", patterns=["*.jpg"], destination="img")],
        )

        result = OrganizeTask(source_dir=source, rules=rules).run()

        # So 1 arquivo (o direto) foi processado
        assert result.data["total_files"] == 1
        assert result.data["moved_count"] == 1

        # Arquivo profundo continua onde estava
        assert (subpasta / "profundo.jpg").exists()
