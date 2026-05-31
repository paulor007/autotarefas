"""
Testes do Storage do servidor demo.

Cobertura:
- create(): IDs auto-incrementados, retorna registro completo
- find_by_id, find_by_cpf: encontram ou retornam None
- list_all: ordem e conteudo
- clear: zera storage
- Persistencia: dados sobrevivem entre instancias
- Concorrencia: lock funciona
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from tools.demo_server.storage import Storage

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    """Storage isolado em pasta temporaria."""
    return Storage(data_dir=tmp_path / "data")


# ============================================================
# Testes de inicializacao
# ============================================================


class TestInit:
    """Inicializacao do Storage."""

    def test_cria_pasta_data_se_nao_existir(self, tmp_path: Path) -> None:
        """A pasta data/ eh criada automaticamente."""
        data_dir = tmp_path / "nao_existe"
        assert not data_dir.exists()
        Storage(data_dir=data_dir)
        assert data_dir.exists()

    def test_cria_arquivo_json_vazio(self, storage: Storage) -> None:
        """O cadastros.json eh criado com lista vazia."""
        assert storage.list_all() == []

    def test_usa_data_dir_default_se_omitido(self) -> None:
        """Sem data_dir, usa pasta padrao do modulo."""
        # Nao queremos poluir a pasta real - apenas verifica que nao crasha
        s = Storage()
        assert s.list_all() is not None


# ============================================================
# Testes de create
# ============================================================


class TestCreate:
    """Criacao de registros."""

    def test_create_retorna_registro_com_id(self, storage: Storage) -> None:
        """create() retorna o registro com id, created_at, etc."""
        data = {
            "nome": "Ana Silva",
            "email": "ana@exemplo.com",
            "cpf": "123.456.789-09",
            "telefone": "(11) 98765-4321",
        }
        record = storage.create(data)

        assert record["id"] == 1
        assert record["nome"] == "Ana Silva"
        assert record["email"] == "ana@exemplo.com"
        assert record["cpf"] == "123.456.789-09"
        assert record["telefone"] == "(11) 98765-4321"
        assert "created_at" in record

    def test_create_telefone_opcional(self, storage: Storage) -> None:
        """Cadastro sem telefone usa string vazia."""
        record = storage.create(
            {
                "nome": "Bruno",
                "email": "b@x.com",
                "cpf": "111.222.333-44",
            }
        )
        assert record["telefone"] == ""

    def test_create_ids_sequenciais(self, storage: Storage) -> None:
        """IDs sao 1, 2, 3, ... auto-incrementados."""
        for i in range(1, 6):
            record = storage.create(
                {
                    "nome": f"Pessoa {i}",
                    "email": f"p{i}@x.com",
                    "cpf": f"00{i}.000.000-0{i}",
                }
            )
            assert record["id"] == i

    def test_create_persiste_em_arquivo(
        self,
        storage: Storage,
        tmp_path: Path,
    ) -> None:
        """Dados sao escritos no JSON imediatamente."""
        storage.create({"nome": "X", "email": "x@x.com", "cpf": "1"})
        json_file = tmp_path / "data" / "cadastros.json"
        assert json_file.exists()
        records = json.loads(json_file.read_text(encoding="utf-8"))
        assert len(records) == 1
        assert records[0]["nome"] == "X"


# ============================================================
# Testes de find
# ============================================================


class TestFind:
    """Busca por id e cpf."""

    def test_find_by_id_encontra(self, storage: Storage) -> None:
        record = storage.create({"nome": "Ana", "email": "a@x.com", "cpf": "1"})
        found = storage.find_by_id(record["id"])
        assert found is not None
        assert found["nome"] == "Ana"

    def test_find_by_id_nao_encontra(self, storage: Storage) -> None:
        assert storage.find_by_id(999) is None

    def test_find_by_cpf_encontra(self, storage: Storage) -> None:
        storage.create({"nome": "X", "email": "x@x.com", "cpf": "111.222.333-44"})
        found = storage.find_by_cpf("111.222.333-44")
        assert found is not None
        assert found["nome"] == "X"

    def test_find_by_cpf_nao_encontra(self, storage: Storage) -> None:
        assert storage.find_by_cpf("999.999.999-99") is None

    def test_find_by_cpf_case_sensitive(self, storage: Storage) -> None:
        """CPF e busca exata (nao normaliza)."""
        storage.create({"nome": "X", "email": "x@x.com", "cpf": "111.222.333-44"})
        # CPF sem pontos nao encontra
        assert storage.find_by_cpf("11122233344") is None


# ============================================================
# Testes de list_all e clear
# ============================================================


class TestListAndClear:
    """list_all e clear."""

    def test_list_all_vazio(self, storage: Storage) -> None:
        assert storage.list_all() == []

    def test_list_all_retorna_todos(self, storage: Storage) -> None:
        for i in range(3):
            storage.create(
                {
                    "nome": f"P{i}",
                    "email": f"p{i}@x.com",
                    "cpf": f"{i:03d}.000.000-00",
                }
            )
        records = storage.list_all()
        assert len(records) == 3

    def test_clear_remove_todos(self, storage: Storage) -> None:
        storage.create({"nome": "X", "email": "x@x.com", "cpf": "1"})
        storage.create({"nome": "Y", "email": "y@x.com", "cpf": "2"})
        assert len(storage.list_all()) == 2

        storage.clear()
        assert storage.list_all() == []

    def test_clear_reseta_ids(self, storage: Storage) -> None:
        """Apos clear, IDs reiniciam em 1."""
        storage.create({"nome": "X", "email": "x@x.com", "cpf": "1"})
        storage.create({"nome": "Y", "email": "y@x.com", "cpf": "2"})
        storage.clear()
        new_record = storage.create({"nome": "Z", "email": "z@x.com", "cpf": "3"})
        assert new_record["id"] == 1


# ============================================================
# Testes de persistencia
# ============================================================


class TestPersistence:
    """Dados sobrevivem entre instancias do Storage."""

    def test_segunda_instancia_le_dados_existentes(
        self,
        tmp_path: Path,
    ) -> None:
        """Cria storage, escreve, cria nova instancia, le."""
        data_dir = tmp_path / "data"

        s1 = Storage(data_dir=data_dir)
        s1.create({"nome": "Ana", "email": "a@x.com", "cpf": "1"})

        s2 = Storage(data_dir=data_dir)
        records = s2.list_all()
        assert len(records) == 1
        assert records[0]["nome"] == "Ana"

    def test_arquivo_json_invalido_retorna_lista_vazia(
        self,
        tmp_path: Path,
    ) -> None:
        """Se cadastros.json estiver corrompido, list_all retorna []."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "cadastros.json").write_text("{{ invalido !!!", encoding="utf-8")

        s = Storage(data_dir=data_dir)
        # Nao crasha; retorna vazio
        assert s.list_all() == []


# ============================================================
# Testes de concorrencia
# ============================================================


class TestConcurrency:
    """Locks garantem que writes paralelos nao corrompem dados."""

    def test_creates_paralelos_geram_ids_unicos(
        self,
        storage: Storage,
    ) -> None:
        """50 threads criando ao mesmo tempo - todos os IDs sao unicos."""
        results: list[int] = []
        errors: list[Exception] = []

        def create_one(i: int) -> None:
            try:
                rec = storage.create(
                    {
                        "nome": f"P{i}",
                        "email": f"p{i}@x.com",
                        "cpf": f"{i:09d}",
                    }
                )
                results.append(rec["id"])
            except Exception as exc:  # pragma: no cover  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 50
        assert len(set(results)) == 50  # todos unicos
        assert sorted(results) == list(range(1, 51))
