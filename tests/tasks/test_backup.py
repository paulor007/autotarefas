"""Testes para autotarefas.tasks.backup."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.tasks.backup import (
    MANIFEST_NAME,
    BackupTask,
    is_link,
    rotate_backups,
    same_volume,
    timestamped_name,
    verify_backup,
)

# ============================================================
# Helpers
# ============================================================


def _criar_estrutura(base: Path, files: dict[str, str]) -> None:
    """
    Cria arquivos/pastas a partir de um dict {path: conteudo}.

    Exemplo:
        _criar_estrutura(tmp_path, {
            "src/main.py": "print('oi')",
            "README.md": "# Doc",
            "__pycache__/cache.pyc": "binario",
        })
    """
    for relative_path, content in files.items():
        full_path = base / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")


def _zip_namelist(zip_path: Path) -> list[str]:
    """
    Arcnames dos ARQUIVOS dentro do ZIP.

    Ignora o `MANIFESTO.csv` e as entradas de pasta: todo pacote passou a ter
    os dois, e os testes aqui falam do conteudo copiado.
    """
    with zipfile.ZipFile(zip_path) as zf:
        return [n for n in zf.namelist() if n != MANIFEST_NAME and not n.endswith("/")]


def _zip_todas_as_entradas(zip_path: Path) -> list[str]:
    """Tudo que ha no pacote, inclusive manifesto e pastas."""
    with zipfile.ZipFile(zip_path) as zf:
        return zf.namelist()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def projeto_simples(tmp_path: Path) -> Path:
    """Pasta com estrutura simples (sem nada pra excluir por default)."""
    src = tmp_path / "projeto"
    _criar_estrutura(
        src,
        {
            "main.py": "print('hello')",
            "README.md": "# Projeto",
            "src/app.py": "# app",
        },
    )
    return src


@pytest.fixture
def projeto_com_excludes(tmp_path: Path) -> Path:
    """Pasta com arquivos que devem ser excluidos pelos defaults."""
    src = tmp_path / "projeto"
    _criar_estrutura(
        src,
        {
            "main.py": "code",
            "README.md": "doc",
            "__pycache__/main.cpython-312.pyc": "binary",
            "src/__pycache__/app.cpython-312.pyc": "binary",
            ".git/config": "git config",
            "node_modules/lib/index.js": "code",
            ".mypy_cache/data.json": "{}",
        },
    )
    return src


# ============================================================
# Tests: Backup basico (caminho feliz)
# ============================================================


class TestBackupTaskBasico:
    """Cenarios basicos de sucesso."""

    def test_backup_pasta_simples_sucesso(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Backup de pasta simples retorna SUCCESS."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[projeto_simples], destination=dest)
        result = task.run()

        assert result.is_success
        assert dest.exists()

    def test_backup_inclui_arquivos_esperados(self, tmp_path: Path, projeto_simples: Path) -> None:
        """ZIP contem os 3 arquivos do projeto."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[projeto_simples], destination=dest)
        result = task.run()

        assert result.data["file_count"] == 3

    def test_backup_arquivo_individual(self, tmp_path: Path) -> None:
        """Backup de um arquivo (nao pasta) funciona."""
        # Cria um arquivo solto
        single_file = tmp_path / "documento.txt"
        single_file.write_text("conteudo", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[single_file], destination=dest)
        result = task.run()

        assert result.is_success
        assert result.data["file_count"] == 1

    def test_backup_multiplas_sources(self, tmp_path: Path) -> None:
        """Backup combinando multiplas pastas."""
        # Cria duas pastas
        pasta1 = tmp_path / "p1"
        pasta2 = tmp_path / "p2"
        _criar_estrutura(pasta1, {"a.txt": "1"})
        _criar_estrutura(pasta2, {"b.txt": "2"})

        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[pasta1, pasta2],
            destination=dest,
        )
        result = task.run()

        assert result.is_success
        assert result.data["file_count"] == 2

    def test_result_inclui_metadados(self, tmp_path: Path, projeto_simples: Path) -> None:
        """result.data tem todos os campos esperados."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert "destination" in result.data
        assert "file_count" in result.data
        assert "skipped_count" in result.data
        assert "size_bytes" in result.data
        assert "sha256" in result.data

    def test_rows_affected_igual_file_count(self, tmp_path: Path, projeto_simples: Path) -> None:
        """rows_affected do TaskResult bate com file_count."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert result.rows_affected == result.data["file_count"]

    def test_destination_pasta_pai_criada(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Cria diretorio pai do destination se nao existir."""
        dest = tmp_path / "subpasta" / "outra" / "backup.zip"
        task = BackupTask(sources=[projeto_simples], destination=dest)
        result = task.run()

        assert result.is_success
        assert dest.exists()


# ============================================================
# Tests: Excludes
# ============================================================


class TestBackupTaskExcludes:
    """Testes de exclusao de arquivos."""

    def test_default_excludes_remove_pycache(
        self, tmp_path: Path, projeto_com_excludes: Path
    ) -> None:
        """__pycache__ e excluido por padrao."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[projeto_com_excludes], destination=dest)
        task.run()

        namelist = _zip_namelist(dest)
        assert not any("__pycache__" in name for name in namelist)
        assert not any(name.endswith(".pyc") for name in namelist)

    def test_default_excludes_remove_git(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """.git e excluido por padrao."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert not any(".git" in name for name in namelist)

    def test_default_excludes_remove_node_modules(
        self, tmp_path: Path, projeto_com_excludes: Path
    ) -> None:
        """node_modules e excluido por padrao."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert not any("node_modules" in name for name in namelist)

    def test_apenas_arquivos_uteis_no_zip(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """Apos defaults, sobram apenas main.py e README.md."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        # main.py + README.md = 2 arquivos
        assert result.data["file_count"] == 2

    def test_skipped_count_correto(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """Conta corretamente os arquivos excluidos."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        # 5 excluidos: 2 .pyc + .git/config + node_modules/lib/index.js + .mypy_cache/data.json
        assert result.data["skipped_count"] == 5

    def test_exclude_pattern_customizado(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Pode passar excludes adicionais via construtor."""
        # Cria um .log na pasta
        (projeto_simples / "debug.log").write_text("logs", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            exclude_patterns=["*.log"],
        )
        result = task.run()

        namelist = _zip_namelist(dest)
        assert not any(name.endswith(".log") for name in namelist)
        # Os outros 3 arquivos foram incluidos
        assert result.data["file_count"] == 3

    def test_no_default_excludes(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """include_default_excludes=False mantem __pycache__."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_com_excludes],
            destination=dest,
            include_default_excludes=False,
        )
        result = task.run()

        # Tudo deve ter sido incluido (7 arquivos)
        assert result.data["file_count"] == 7
        assert result.data["skipped_count"] == 0

    def test_excludes_combinados(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """Default + customizados aplicados juntos."""
        # Adiciona um arquivo .tmp
        (projeto_com_excludes / "scratch.tmp").write_text("tmp", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_com_excludes],
            destination=dest,
            exclude_patterns=["*.tmp"],
        )
        result = task.run()

        namelist = _zip_namelist(dest)
        # Nao deve ter .pyc (default) nem .tmp (custom)
        assert not any(name.endswith(".pyc") for name in namelist)
        assert not any(name.endswith(".tmp") for name in namelist)
        # Sobram main.py + README.md
        assert result.data["file_count"] == 2


# ============================================================
# Tests: Validacao de input
# ============================================================


class TestBackupTaskValidacao:
    """Validacao de argumentos."""

    def test_source_inexistente_levanta(self, tmp_path: Path) -> None:
        """Source inexistente -> TaskResult de FAILURE."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[tmp_path / "nao_existe"],
            destination=dest,
        )
        result = task.run()

        # BaseTask captura AutoTarefasError e retorna FAILURE
        assert result.is_failure
        assert "nao encontrado" in (result.error_message or "")

    def test_multiplas_sources_uma_inexistente(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Se UMA source nao existe, a task falha (atomico)."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples, tmp_path / "fake"],
            destination=dest,
        )
        result = task.run()

        assert result.is_failure
        # ZIP nao deve ter sido criado
        assert not dest.exists()


# ============================================================
# Tests: Dry-run
# ============================================================


class TestBackupTaskDryRun:
    """Testes do modo dry-run."""

    def test_dry_run_nao_cria_zip(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Dry-run nao cria arquivo."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        )
        task.run()

        assert not dest.exists()

    def test_dry_run_status_dry_run(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Status retornado e DRY_RUN."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        )
        result = task.run()

        assert result.status == TaskStatus.DRY_RUN

    def test_dry_run_inclui_files_preview(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Dry-run inclui preview dos arquivos no data."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        )
        result = task.run()

        assert "files_preview" in result.data
        assert len(result.data["files_preview"]) > 0

    def test_dry_run_conta_arquivos_corretamente(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        """Dry-run reporta file_count correto."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        ).run()

        # projeto_simples tem 3 arquivos
        assert result.data["file_count"] == 3


# ============================================================
# Tests: SHA-256
# ============================================================


class TestBackupTaskHash:
    """Testes do hash SHA-256."""

    def test_sha256_presente_no_data(self, tmp_path: Path, projeto_simples: Path) -> None:
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert "sha256" in result.data
        assert result.data["sha256"]  # nao vazio

    def test_sha256_tem_64_caracteres_hex(self, tmp_path: Path, projeto_simples: Path) -> None:
        """SHA-256 em hex tem exatamente 64 chars (0-9a-f)."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        sha = result.data["sha256"]
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)


# ============================================================
# Tests: Conteudo do ZIP
# ============================================================


class TestBackupTaskZipContent:
    """Verificacoes da estrutura interna do ZIP."""

    def test_zip_e_arquivo_zip_valido(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Arquivo gerado e um ZIP valido (parseavel)."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        # zipfile consegue abrir sem erro
        with zipfile.ZipFile(dest) as zf:
            assert zf.testzip() is None  # integridade OK

    def test_arcname_inclui_nome_da_pasta_source(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        """Arcname comeca com nome da pasta source (preserva estrutura)."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        namelist = _zip_namelist(dest)
        # Todos os arcnames devem comecar com "projeto/"
        assert all(name.startswith("projeto/") for name in namelist)

    def test_arcname_preserva_subpastas(self, tmp_path: Path, projeto_simples: Path) -> None:
        """src/app.py preserva o sub-path src/."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert any("projeto/src/app.py" in name for name in namelist)

    def test_arquivo_individual_arcname_e_nome(self, tmp_path: Path) -> None:
        """Quando source eh arquivo, arcname e so o nome dele."""
        single_file = tmp_path / "doc.txt"
        single_file.write_text("oi", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        BackupTask(sources=[single_file], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert namelist == ["doc.txt"]


# ============================================================
# Tests: ZIP vazio (SKIPPED)
# ============================================================


class TestBackupTaskVazio:
    """Cenarios em que nao ha arquivos pra fazer backup."""

    def test_pasta_vazia_retorna_skipped(self, tmp_path: Path) -> None:
        """Pasta sem arquivos -> status SKIPPED."""
        pasta_vazia = tmp_path / "vazia"
        pasta_vazia.mkdir()

        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[pasta_vazia], destination=dest).run()

        assert result.status == TaskStatus.SKIPPED
        # ZIP nao deve ter sido criado
        assert not dest.exists()

    def test_tudo_excluido_retorna_skipped(self, tmp_path: Path) -> None:
        """Se TUDO for excluido, retorna SKIPPED."""
        src = tmp_path / "projeto"
        _criar_estrutura(
            src,
            {
                "__pycache__/cache.pyc": "binary",
                ".git/config": "git",
            },
        )

        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[src], destination=dest).run()

        assert result.status == TaskStatus.SKIPPED


# ============================================================
# Tests: Atributos da classe
# ============================================================


class TestBackupTaskAtributos:
    """Testes dos atributos de classe."""

    def test_name(self) -> None:
        assert BackupTask.name == "backup"

    def test_description(self) -> None:
        assert BackupTask.description

    def test_default_excludes_inclui_pycache(self) -> None:
        assert "__pycache__" in BackupTask.DEFAULT_EXCLUDES

    def test_default_excludes_inclui_git(self) -> None:
        assert ".git" in BackupTask.DEFAULT_EXCLUDES

    def test_default_excludes_inclui_node_modules(self) -> None:
        assert "node_modules" in BackupTask.DEFAULT_EXCLUDES

    def test_default_excludes_e_tupla(self) -> None:
        """DEFAULT_EXCLUDES deve ser imutavel (tupla)."""
        assert isinstance(BackupTask.DEFAULT_EXCLUDES, tuple)


# ============================================================
# Testes de seguranca
# ============================================================


class TestBackupTaskSeguranca:
    """Validacoes de seguranca aplicadas em construtor."""

    def test_destination_com_char_proibido_falha(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        """destination com '|' (proibido no Windows) e rejeitado."""
        from autotarefas.core.exceptions import ValidationError

        dest_ruim = tmp_path / "backup|ruim.zip"

        with pytest.raises(ValidationError, match="invalido"):
            BackupTask(
                sources=[projeto_simples],
                destination=dest_ruim,
            )

    def test_destination_com_nul_byte_falha(self, tmp_path: Path, projeto_simples: Path) -> None:
        """destination com NUL byte e rejeitado."""
        from autotarefas.core.exceptions import ValidationError

        # Path com NUL embutido no nome
        dest_ruim = tmp_path / "backup\x00.zip"

        with pytest.raises(ValidationError, match="invalido"):
            BackupTask(
                sources=[projeto_simples],
                destination=dest_ruim,
            )


# ============================================================
# Tests: os defeitos encontrados na auditoria do card
#
# Cada classe abaixo corresponde a um problema COMPROVADO antes da correcao.
# Sao os casos em que um backup falha na vida real — arquivo aberto no Excel,
# duas pastas com o mesmo nome, falha no meio da gravacao — e onde falhar em
# silencio e pior do que nao ter rodado.
# ============================================================


def _travar(caminho: Path) -> Any:
    """Trava um arquivo como o Office faz, e devolve o handle aberto."""
    import msvcrt

    fh = caminho.open("r+b")
    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 100)
    return fh


def _destravar(fh: Any) -> None:
    import msvcrt

    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 100)
    fh.close()


class TestArquivoIlegivelNaoDerrubaOBackup:
    """
    Arquivo travado, sem permissao ou que sumiu nao pode abortar tudo.

    Numa micro empresa em horario comercial, a planilha mais importante e
    justamente a que esta aberta. Antes, um unico arquivo assim derrubava o
    backup inteiro e nenhum pacote era entregue.
    """

    @pytest.fixture
    def escritorio(self, tmp_path: Path) -> Path:
        pasta = tmp_path / "escritorio"
        pasta.mkdir()
        for i in range(3):
            (pasta / f"a{i}_nota.txt").write_text(f"nota {i}", encoding="utf-8")
        (pasta / "m_planilha.xlsx").write_bytes(b"planilha" * 50)
        for i in range(3):
            (pasta / f"z{i}_recibo.txt").write_text(f"recibo {i}", encoding="utf-8")
        return pasta

    def test_backup_conclui_com_ressalva(self, tmp_path: Path, escritorio: Path) -> None:
        dest = tmp_path / "backup.zip"
        fh = _travar(escritorio / "m_planilha.xlsx")
        try:
            result = BackupTask(sources=[escritorio], destination=dest).run()
        finally:
            _destravar(fh)

        assert result.status == TaskStatus.PARTIAL
        assert result.data["file_count"] == 6
        assert result.data["unreadable_count"] == 1
        assert dest.is_file(), "o pacote com os outros 6 arquivos tem de ser entregue"

    def test_o_arquivo_que_faltou_e_nomeado_com_o_motivo(
        self, tmp_path: Path, escritorio: Path
    ) -> None:
        """Ausencia silenciosa e o pior defeito possivel num backup."""
        dest = tmp_path / "backup.zip"
        fh = _travar(escritorio / "m_planilha.xlsx")
        try:
            result = BackupTask(sources=[escritorio], destination=dest).run()
        finally:
            _destravar(fh)

        (ausente,) = result.data["unreadable"]
        assert ausente["arquivo"] == "escritorio/m_planilha.xlsx"
        assert "aberto por outro programa" in ausente["motivo"]

    def test_nao_sobra_entrada_vazia_no_lugar_do_arquivo(
        self, tmp_path: Path, escritorio: Path
    ) -> None:
        """
        Regressao: escrevendo direto no ZIP, o arquivo que falhava na metade
        da leitura deixava uma entrada de 0 byte com o nome certo. Quem
        extraisse pelo Windows recebia um arquivo vazio no lugar da planilha.
        """
        dest = tmp_path / "backup.zip"
        fh = _travar(escritorio / "m_planilha.xlsx")
        try:
            BackupTask(sources=[escritorio], destination=dest).run()
        finally:
            _destravar(fh)

        assert "escritorio/m_planilha.xlsx" not in _zip_todas_as_entradas(dest)

    def test_arquivo_que_some_no_meio_vira_ressalva(self, tmp_path: Path) -> None:
        """Temporarios e logs somem entre a listagem e a gravacao."""
        pasta = tmp_path / "dados"
        pasta.mkdir()
        (pasta / "fica.txt").write_text("fica", encoding="utf-8")
        efemero = pasta / "some.txt"
        efemero.write_text("some", encoding="utf-8")

        task = BackupTask(sources=[pasta], destination=tmp_path / "b.zip")
        arquivos, _, links, pastas = task._collect_files()
        efemero.unlink()
        entradas, ilegiveis = task._build_package(
            arquivos,
            task._resolve_arcnames(arquivos),
            datetime.now(UTC),
            links=links,
            pastas=pastas,
        )

        assert [e.arcname for e in entradas] == ["dados/fica.txt"]
        assert "deixou de existir" in ilegiveis[0].reason

    def test_tudo_ilegivel_e_falha_e_nao_pacote_vazio(self, tmp_path: Path) -> None:
        """Um pacote vazio com cara de backup seria a pior mentira possivel."""
        pasta = tmp_path / "so_travado"
        pasta.mkdir()
        (pasta / "unico.bin").write_bytes(b"x" * 300)
        dest = tmp_path / "backup.zip"

        fh = _travar(pasta / "unico.bin")
        try:
            result = BackupTask(sources=[pasta], destination=dest).run()
        finally:
            _destravar(fh)

        assert result.status == TaskStatus.FAILURE
        assert not dest.exists(), "sem nenhum arquivo lido, nao se entrega pacote"


class TestGravacaoAtomica:
    """O caminho final ou nao existe, ou esta inteiro."""

    def test_nao_sobra_arquivo_parcial_quando_falha(self, tmp_path: Path) -> None:
        pasta = tmp_path / "d"
        pasta.mkdir()
        (pasta / "unico.bin").write_bytes(b"x" * 300)
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[pasta], destination=dest)

        fh = _travar(pasta / "unico.bin")
        try:
            task.run()
        finally:
            _destravar(fh)

        assert not task.partial_path.exists()
        assert not dest.exists()

    def test_backup_dentro_da_pasta_nao_engorda_a_cada_execucao(self, tmp_path: Path) -> None:
        """Guardar o ZIP na propria pasta e comum em rede compartilhada."""
        pasta = tmp_path / "compartilhada"
        pasta.mkdir()
        (pasta / "dado.txt").write_text("dado", encoding="utf-8")
        dest = pasta / "backup.zip"

        BackupTask(sources=[pasta], destination=dest).run()
        segunda = BackupTask(sources=[pasta], destination=dest).run()

        assert segunda.data["file_count"] == 1
        assert _zip_namelist(dest) == ["compartilhada/dado.txt"]


class TestNomesRepetidos:
    """Dois arquivos com o mesmo caminho relativo, vindos de fontes diferentes."""

    @pytest.fixture
    def dois_clientes(self, tmp_path: Path) -> tuple[Path, Path]:
        a = tmp_path / "clienteA" / "docs"
        b = tmp_path / "clienteB" / "docs"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        (a / "contrato.txt").write_text("CLIENTE A", encoding="utf-8")
        (b / "contrato.txt").write_text("CLIENTE B", encoding="utf-8")
        return a, b

    def test_os_dois_arquivos_sobrevivem(
        self, tmp_path: Path, dois_clientes: tuple[Path, Path]
    ) -> None:
        """
        Regressao: o ZIP aceita nomes repetidos sem reclamar, e na extracao um
        sobrescrevia o outro. O resultado dizia "2 arquivos" e entregava 1 —
        o contrato do cliente A sumia em silencio.
        """
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=list(dois_clientes), destination=dest).run()

        assert result.data["file_count"] == 2
        nomes = _zip_namelist(dest)
        assert len(nomes) == len(set(nomes)), "nome repetido dentro do pacote"

        with zipfile.ZipFile(dest) as zf:
            conteudos = {zf.read(n).decode("utf-8") for n in nomes}
        assert conteudos == {"CLIENTE A", "CLIENTE B"}

    def test_a_segunda_fonte_ganha_sufixo_legivel(
        self, tmp_path: Path, dois_clientes: tuple[Path, Path]
    ) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=list(dois_clientes), destination=dest).run()

        assert sorted(_zip_namelist(dest)) == ["docs (2)/contrato.txt", "docs/contrato.txt"]


class TestPastasVazias:
    def test_pasta_sem_arquivos_sobrevive(self, tmp_path: Path) -> None:
        """Ha sistema que nao inicia se a pasta esperada nao existe."""
        pasta = tmp_path / "app"
        (pasta / "logs").mkdir(parents=True)
        (pasta / "config.ini").write_text("[app]", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        BackupTask(sources=[pasta], destination=dest).run()

        assert "app/logs/" in _zip_todas_as_entradas(dest)


class TestManifesto:
    """O manifesto e o que torna o pacote autoverificavel."""

    def test_todo_pacote_tem_manifesto(self, tmp_path: Path, projeto_simples: Path) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        assert MANIFEST_NAME in _zip_todas_as_entradas(dest)

    def test_traz_o_sha256_de_cada_arquivo(self, tmp_path: Path, projeto_simples: Path) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        with zipfile.ZipFile(dest) as zf:
            texto = zf.read(MANIFEST_NAME).decode("utf-8")
            linhas = [
                linha for linha in csv.reader(io.StringIO(texto)) if linha[:1] == ["incluido"]
            ]
            assert linhas, "o manifesto tem de listar os arquivos"
            for linha in linhas:
                arcname, sha = linha[1], linha[4]
                assert sha == hashlib.sha256(zf.read(arcname)).hexdigest()

    def test_nao_expoe_o_caminho_da_maquina(self, tmp_path: Path, projeto_simples: Path) -> None:
        """O pacote costuma sair da maquina; caminho interno nao ajuda ninguem."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        with zipfile.ZipFile(dest) as zf:
            texto = zf.read(MANIFEST_NAME).decode("utf-8")
        assert str(tmp_path) not in texto

    def test_registra_quem_ficou_de_fora(self, tmp_path: Path) -> None:
        pasta = tmp_path / "d"
        pasta.mkdir()
        (pasta / "ok.txt").write_text("ok", encoding="utf-8")
        (pasta / "travado.bin").write_bytes(b"x" * 300)
        dest = tmp_path / "backup.zip"

        fh = _travar(pasta / "travado.bin")
        try:
            BackupTask(sources=[pasta], destination=dest).run()
        finally:
            _destravar(fh)

        with zipfile.ZipFile(dest) as zf:
            texto = zf.read(MANIFEST_NAME).decode("utf-8")
        assert "NAO_LIDO" in texto
        assert "d/travado.bin" in texto


class TestVerificacao:
    """Backup que ninguem confere e fe, nao garantia."""

    def _regravar(self, dest: Path, conteudo: dict[str, bytes]) -> None:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome, dados in conteudo.items():
                zf.writestr(nome, dados)

    def _conteudo(self, dest: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(dest) as zf:
            return {n: zf.read(n) for n in zf.namelist()}

    def test_pacote_intacto_e_aprovado(self, tmp_path: Path, projeto_simples: Path) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        relatorio = verify_backup(dest)

        assert relatorio.ok is True
        assert relatorio.checked > 0
        assert relatorio.corrupted == ()

    def test_conteudo_adulterado_e_detectado(self, tmp_path: Path, projeto_simples: Path) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()
        conteudo = self._conteudo(dest)
        alvo = next(n for n in conteudo if n.endswith(".py"))
        conteudo[alvo] = b"ADULTERADO"
        self._regravar(dest, conteudo)

        relatorio = verify_backup(dest)

        assert relatorio.ok is False
        assert relatorio.corrupted == (alvo,)

    def test_arquivo_removido_do_pacote_e_detectado(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()
        conteudo = self._conteudo(dest)
        removido = next(n for n in conteudo if n.endswith(".py"))
        del conteudo[removido]
        self._regravar(dest, conteudo)

        relatorio = verify_backup(dest)

        assert relatorio.ok is False
        assert relatorio.missing == (removido,)

    def test_lembra_o_que_ficou_de_fora_na_origem(self, tmp_path: Path) -> None:
        """Quem confere precisa saber que esses arquivos nunca estiveram la."""
        pasta = tmp_path / "d"
        pasta.mkdir()
        (pasta / "ok.txt").write_text("ok", encoding="utf-8")
        (pasta / "travado.bin").write_bytes(b"x" * 300)
        dest = tmp_path / "backup.zip"

        fh = _travar(pasta / "travado.bin")
        try:
            BackupTask(sources=[pasta], destination=dest).run()
        finally:
            _destravar(fh)

        relatorio = verify_backup(dest)

        assert relatorio.ok is True, "o pacote esta integro; o que faltou ja era sabido"
        assert relatorio.unreadable_at_origin == ("d/travado.bin",)

    def test_zip_de_outra_ferramenta_diz_que_nao_da_para_conferir(self, tmp_path: Path) -> None:
        alheio = tmp_path / "alheio.zip"
        with zipfile.ZipFile(alheio, "w") as zf:
            zf.writestr("a.txt", "conteudo")

        relatorio = verify_backup(alheio)

        assert relatorio.ok is False
        assert "sem MANIFESTO" in relatorio.problem

    def test_arquivo_que_nem_e_zip(self, tmp_path: Path) -> None:
        falso = tmp_path / "nao_e.zip"
        falso.write_text("isto nao e um zip", encoding="utf-8")

        relatorio = verify_backup(falso)

        assert relatorio.ok is False
        assert relatorio.problem


class TestRetencao:
    """Backup diario sem retencao enche o disco e vira 300 arquivos iguais."""

    def _criar(self, pasta: Path, nome: str) -> Path:
        alvo = pasta / nome
        with zipfile.ZipFile(alvo, "w") as zf:
            zf.writestr("x.txt", "antigo")
        return alvo

    def test_nome_ganha_data_e_hora(self, tmp_path: Path) -> None:
        alvo = timestamped_name(tmp_path / "contabilidade.zip", datetime(2026, 8, 20, 17, 30))

        assert alvo.name == "contabilidade_2026-08-20_1730.zip"

    def test_mantem_os_mais_recentes(self, tmp_path: Path) -> None:
        for dia in (17, 18, 19):
            self._criar(tmp_path, f"dados_2026-08-{dia}_0900.zip")
        novo = self._criar(tmp_path, "dados_2026-08-20_0900.zip")

        removidos = rotate_backups(novo, keep=2)

        assert {p.name for p in removidos} == {
            "dados_2026-08-17_0900.zip",
            "dados_2026-08-18_0900.zip",
        }
        assert novo.exists()

    def test_nunca_apaga_o_recem_criado(self, tmp_path: Path) -> None:
        """Mesmo com pacotes de carimbo mais novo (relogio adiantado)."""
        for hora in ("1800", "1900"):
            self._criar(tmp_path, f"dados_2026-08-20_{hora}.zip")
        novo = self._criar(tmp_path, "dados_2026-08-20_0900.zip")

        rotate_backups(novo, keep=1)

        assert novo.exists()

    def test_nao_toca_em_arquivo_de_outra_base(self, tmp_path: Path) -> None:
        """Apagar arquivo do cliente por engano seria pior que disco cheio."""
        outro = self._criar(tmp_path, "notas_fiscais_2026-08-17_0900.zip")
        sem_data = self._criar(tmp_path, "dados.zip")
        self._criar(tmp_path, "dados_2026-08-17_0900.zip")
        novo = self._criar(tmp_path, "dados_2026-08-20_0900.zip")

        rotate_backups(novo, keep=1)

        assert outro.exists()
        assert sem_data.exists()

    def test_manter_zero_nao_apaga_nada(self, tmp_path: Path) -> None:
        antigo = self._criar(tmp_path, "dados_2026-08-17_0900.zip")
        novo = self._criar(tmp_path, "dados_2026-08-20_0900.zip")

        assert rotate_backups(novo, keep=0) == []
        assert antigo.exists()


# ============================================================
# Tests: Card 02.A — segurança de caminhos e avisos
#
# Os defeitos aqui foram COMPROVADOS com sonda antes da correção: uma
# junção apontando para fora copiava dados de terceiros para dentro do
# pacote, e uma junção apontando para o topo fazia o mesmo arquivo entrar
# sete vezes. Ambos em silêncio, com o relatório dizendo um número que não
# correspondia a nada.
# ============================================================


def _junção(atalho: Path, alvo: Path) -> bool:
    """Cria uma junção do Windows. False quando o SO não permite."""
    if os.name != "nt":
        return False
    resultado = subprocess.run(  # noqa: S603
        ["cmd", "/c", "mklink", "/J", str(atalho), str(alvo)],  # noqa: S607
        capture_output=True,
        check=False,
    )
    return resultado.returncode == 0 and atalho.exists()


@pytest.fixture
def com_junções(tmp_path: Path) -> Path:
    """Origem com um atalho para fora e outro que volta ao topo."""
    origem = tmp_path / "origem"
    (origem / "sub").mkdir(parents=True)
    externo = tmp_path / "externo"
    externo.mkdir()
    (origem / "interno.txt").write_text("dado interno", encoding="utf-8")
    (externo / "segredo.txt").write_text("DADO DE OUTRO SETOR", encoding="utf-8")

    if not _junção(origem / "atalho_externo", externo):
        pytest.skip("o sistema não permitiu criar junção")
    if not _junção(origem / "sub" / "volta_ao_topo", origem):
        pytest.skip("o sistema não permitiu criar junção")
    return origem


class TestAtalhosNaoCopiamDeFora:
    def test_conteudo_de_fora_nao_entra(self, tmp_path: Path, com_junções: Path) -> None:
        """
        Regressão: a junção era percorrida como pasta comum, e o arquivo de
        outro setor entrava no pacote sem ninguém perceber.
        """
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[com_junções], destination=dest).run()

        nomes = _zip_namelist(dest)
        assert nomes == ["origem/interno.txt"]
        assert not any("segredo" in n for n in nomes)

    def test_atalho_e_registrado_com_destino_e_motivo(
        self, tmp_path: Path, com_junções: Path
    ) -> None:
        """Ignorar em silêncio seria tão ruim quanto copiar em silêncio."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[com_junções], destination=dest).run()

        atalhos = {link["atalho"]: link for link in result.data["links"]}
        fora = atalhos["origem/atalho_externo"]
        assert fora["fora_da_origem"] is True
        assert fora["seguido"] is False
        assert "fora da origem" in fora["motivo"]
        assert "externo" in fora["destino"]

    def test_manifesto_registra_os_atalhos(self, tmp_path: Path, com_junções: Path) -> None:
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[com_junções], destination=dest).run()

        with zipfile.ZipFile(dest) as zf:
            texto = zf.read(MANIFEST_NAME).decode("utf-8")
        assert "LINK_IGNORADO" in texto
        assert "origem/atalho_externo" in texto
        assert "# atalhos,2" in texto


class TestAtalhoCircularNaoRepete:
    def test_sem_seguir_links_nao_ha_repeticao(self, tmp_path: Path, com_junções: Path) -> None:
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[com_junções], destination=dest).run()

        assert result.data["file_count"] == 1

    def test_seguindo_links_o_ciclo_ainda_para(self, tmp_path: Path, com_junções: Path) -> None:
        """
        Regressão: `volta_ao_topo` apontava para a própria origem e o mesmo
        arquivo entrava sete vezes, com nomes cada vez mais longos, até o
        limite de caminho do Windows interromper por acaso.
        """
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[com_junções], destination=dest, follow_links=True).run()

        nomes = _zip_namelist(dest)
        assert len(nomes) == len(set(nomes)), "arquivo repetido no pacote"
        assert not any(n.count("volta_ao_topo") > 1 for n in nomes)
        # Com --seguir-links o conteúdo externo entra: foi uma escolha explícita.
        assert "origem/atalho_externo/segredo.txt" in nomes
        assert result.data["file_count"] == 2

    def test_seguir_links_e_registrado_como_seguido(
        self, tmp_path: Path, com_junções: Path
    ) -> None:
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[com_junções], destination=dest, follow_links=True).run()

        assert all(link["seguido"] for link in result.data["links"])
        with zipfile.ZipFile(dest) as zf:
            assert "LINK_SEGUIDO" in zf.read(MANIFEST_NAME).decode("utf-8")


class TestAvisoDeMesmoVolume:
    def test_mesmo_disco_e_apontado(self, tmp_path: Path, projeto_simples: Path) -> None:
        result = BackupTask(sources=[projeto_simples], destination=tmp_path / "backup.zip").run()

        assert result.data["same_volume"] == ["projeto"]

    def test_o_aviso_nao_bloqueia_o_backup(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Travar aqui quebraria o backup agendado, que roda sem ninguém por perto."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert result.status == TaskStatus.SUCCESS
        assert dest.is_file()

    def test_volumes_diferentes_nao_geram_aviso(self, tmp_path: Path) -> None:
        pasta = tmp_path / "d"
        pasta.mkdir()
        (pasta / "a.txt").write_text("a", encoding="utf-8")

        assert same_volume(pasta, tmp_path / "b.zip") is True
        assert same_volume(pasta, Path("//servidor-inexistente/share/b.zip")) is False


class TestDeteccaoDeAtalho:
    def test_pasta_comum_nao_e_atalho(self, tmp_path: Path) -> None:
        pasta = tmp_path / "comum"
        pasta.mkdir()

        assert is_link(pasta) is False

    def test_junção_e_atalho(self, tmp_path: Path) -> None:
        """
        `Path.is_symlink()` devolve False para junção do Windows — era
        exatamente essa a brecha por onde o backup entrava nelas.
        """
        alvo = tmp_path / "alvo"
        alvo.mkdir()
        atalho = tmp_path / "atalho"
        if not _junção(atalho, alvo):
            pytest.skip("o sistema não permitiu criar junção")

        assert is_link(atalho) is True
