"""
A regra de "protegido".

É a decisão de produto mais delicada da reorganização. Um veredito que erra
para o lado otimista é pior do que nenhum veredito: ele troca a desconfiança
saudável por confiança falsa, e a pessoa descobre no dia em que precisa
restaurar. Por isso os testes aqui insistem no lado feio — política sem pasta,
backup atrasado, máquina revogada, destino no mesmo disco.

`avaliar` é função pura, então cada cenário é um dicionário, sem banco e sem
servidor. Isso permite exercitar combinações que seriam caras de montar de
ponta a ponta e raras de encontrar por acaso.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from apps.api.app.protecao import TOLERANCIA, Nivel, avaliar

AGORA = datetime(2026, 8, 28, 9, 0, 0)

MAQUINA = {
    "id": "d1",
    "nome": "PC da loja",
    "sistema": "Windows 11",
    "versao_agente": "0.1.0",
    "estado": "ativo",
    "impressao": "AAAA",
    "pareado_em": "2026-08-01T10:00:00",
    "ultimo_contato": "2026-08-28T08:00:00",
}

CONFIGURACAO: dict[str, Any] = {
    "origens": ["C:\\Loja\\Dados"],
    "destino": {"tipo": "externo", "caminho": "E:\\Backups"},
    "agendamento": {
        "tipo": "diario",
        "hora": "02:00",
        "dia_da_semana": 0,
        "dia_do_mes": 1,
    },
    "retencao": {"diarias": 7, "semanais": 4, "mensais": 12},
    "retry": {"tentativas": 3, "espera_inicial_min": 5},
    "notificacao": {"quando": "problema", "emails": []},
    "usar_vss": False,
    "cifrar": False,
    "assinar": True,
    "incremental": False,
}


def politica(**mudancas: Any) -> dict[str, Any]:
    configuracao = {**CONFIGURACAO, **mudancas.pop("configuracao", {})}
    return {
        "id": "p1",
        "nome": "Backup da loja",
        "dispositivo_id": "d1",
        "ativa": True,
        "configuracao": configuracao,
        "protege_de_verdade": True,
        "criada_em": "2026-08-01T10:00:00",
        "atualizada_em": "2026-08-01T10:00:00",
        **mudancas,
    }


def execucao(**mudancas: Any) -> dict[str, Any]:
    return {
        "id": "e1",
        "dispositivo_id": "d1",
        "politica_id": "p1",
        "origem": "agendamento",
        "resultado": "sucesso",
        "iniciada_em": "2026-08-28T02:00:00",
        "terminada_em": "2026-08-28T02:04:00",
        "arquivos": 12,
        "bytes_copiados": 4096,
        "ressalva": "",
        "artefatos": [],
        **mudancas,
    }


def julgar(
    politicas: list[dict[str, Any]],
    execucoes: list[dict[str, Any]],
    *,
    dispositivos: list[dict[str, Any]] | None = None,
    agora: datetime = AGORA,
) -> dict[str, Any]:
    return avaliar(
        politicas,
        [MAQUINA] if dispositivos is None else dispositivos,
        execucoes,
        agora,
    )


class TestSemNada:
    def test_sem_politica_nao_e_protegido_nem_em_risco(self) -> None:
        # "Em risco" para quem nunca configurou nada acusaria a pessoa de um
        # problema que ela ainda nao teve chance de criar.
        veredito = julgar([], [])
        assert veredito["nivel"] == Nivel.SEM_CONFIGURACAO.value
        assert veredito["backups"] == []

    def test_politica_desligada_conta_como_nao_configurada(self) -> None:
        veredito = julgar([politica(ativa=False)], [execucao()])
        assert veredito["nivel"] == Nivel.SEM_CONFIGURACAO.value


class TestProtegido:
    def test_tudo_em_ordem(self) -> None:
        veredito = julgar([politica()], [execucao()])
        assert veredito["nivel"] == Nivel.PROTEGIDO.value
        assert veredito["titulo"] == "Protegido"
        assert veredito["backups"][0]["motivos"] == []

    def test_o_resumo_conta_quantos(self) -> None:
        veredito = julgar([politica()], [execucao()])
        assert veredito["resumo"] == "1 backup ativo, todos em dia."


class TestEmRisco:
    def test_nunca_executou(self) -> None:
        # Uma politica recem-criada e uma promessa, nao uma protecao.
        veredito = julgar([politica()], [])
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        assert "nunca concluiu" in veredito["backups"][0]["motivos"][0]

    def test_atrasado_alem_da_tolerancia(self) -> None:
        # Ultimo sucesso anteontem, com backup diario: uma janela inteira
        # passou em branco.
        antigo = execucao(iniciada_em="2026-08-26T02:00:00", terminada_em="2026-08-26T02:04:00")
        veredito = julgar([politica()], [antigo])
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        assert any("não aconteceu" in m for m in veredito["backups"][0]["motivos"])

    def test_dentro_da_tolerancia_continua_protegido(self) -> None:
        # O agendador da maquina ainda executaria esta janela. A tela nao pode
        # gritar antes de ele desistir.
        veredito = julgar(
            [politica()],
            [execucao()],
            agora=datetime(2026, 8, 29, 2, 0, 0) + TOLERANCIA - timedelta(minutes=1),
        )
        assert veredito["nivel"] == Nivel.PROTEGIDO.value

    def test_a_ultima_tentativa_falhou(self) -> None:
        antiga_boa = execucao(
            id="e0", iniciada_em="2026-08-28T02:00:00", terminada_em="2026-08-28T02:04:00"
        )
        recente_ruim = execucao(
            id="e1",
            resultado="falha",
            ressalva="destino inacessivel",
            iniciada_em="2026-08-28T03:00:00",
            terminada_em="2026-08-28T03:00:10",
        )
        veredito = julgar([politica()], [antiga_boa, recente_ruim])
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        assert any("falhou" in m for m in veredito["backups"][0]["motivos"])

    def test_maquina_revogada(self) -> None:
        revogada = {**MAQUINA, "estado": "revogado"}
        veredito = julgar([politica()], [execucao()], dispositivos=[revogada])
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        assert "revogada" in veredito["backups"][0]["motivos"][0]

    def test_maquina_que_nao_existe_mais(self) -> None:
        veredito = julgar([politica()], [execucao()], dispositivos=[])
        assert veredito["nivel"] == Nivel.EM_RISCO.value

    def test_sem_pasta_escolhida_nao_copia_nada(self) -> None:
        veredito = julgar(
            [politica(configuracao={"origens": []})],
            [execucao()],
        )
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        assert any("não copiaria nada" in m for m in veredito["backups"][0]["motivos"])


class TestParcial:
    def test_destino_no_mesmo_computador(self) -> None:
        # O pedido do dono, com todas as letras: "se o destino estiver no mesmo
        # disco/origem, mostre Protecao parcial em vez de Protegido".
        veredito = julgar(
            [politica(configuracao={"destino": {"tipo": "local", "caminho": "C:\\Backups"}})],
            [execucao()],
        )
        assert veredito["nivel"] == Nivel.PARCIAL.value
        assert veredito["titulo"] == "Proteção parcial"
        assert any("mesmo computador" in m for m in veredito["backups"][0]["motivos"])

    def test_sem_agendamento_nao_e_backup_automatico(self) -> None:
        veredito = julgar(
            [
                politica(
                    configuracao={
                        "agendamento": {
                            "tipo": "desligado",
                            "hora": "02:00",
                            "dia_da_semana": 0,
                            "dia_do_mes": 1,
                        }
                    }
                )
            ],
            [execucao()],
        )
        assert veredito["nivel"] == Nivel.PARCIAL.value
        assert any("só acontece quando" in m for m in veredito["backups"][0]["motivos"])

    def test_ultima_execucao_com_ressalva(self) -> None:
        veredito = julgar(
            [politica()],
            [execucao(resultado="com_ressalva", ressalva="2 arquivos em uso")],
        )
        assert veredito["nivel"] == Nivel.PARCIAL.value
        assert "2 arquivos em uso" in " ".join(veredito["backups"][0]["motivos"])


class TestOPiorGanha:
    def test_um_backup_em_risco_derruba_o_veredito_da_empresa(self) -> None:
        # Duas maquinas, uma impecavel e outra sem backup ha dias. A empresa
        # nao esta protegida — e arredondar para o melhor caso seria o erro
        # exato que este veredito existe para evitar.
        outra = {**MAQUINA, "id": "d2", "nome": "PC do escritório"}
        boa = politica()
        ruim = politica(id="p2", nome="Backup do escritório", dispositivo_id="d2")
        veredito = julgar(
            [boa, ruim],
            [execucao()],
            dispositivos=[MAQUINA, outra],
        )
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        assert veredito["resumo"] == "2 backups ativos. 1 precisa de atenção."
        por_nome = {item["nome"]: item for item in veredito["backups"]}
        assert por_nome["Backup da loja"]["nivel"] == Nivel.PROTEGIDO.value
        assert por_nome["Backup do escritório"]["nivel"] == Nivel.EM_RISCO.value

    def test_risco_ganha_de_parcial_no_mesmo_backup(self) -> None:
        veredito = julgar(
            [politica(configuracao={"destino": {"tipo": "local", "caminho": "C:\\Backups"}})],
            [],
        )
        assert veredito["nivel"] == Nivel.EM_RISCO.value
        # E os DOIS motivos aparecem: quem for consertar precisa dos dois.
        assert len(veredito["backups"][0]["motivos"]) == 2


class TestOQueNaoEntraNoVeredito:
    def test_maquina_desligada_nao_e_falha(self) -> None:
        """
        O computador da loja fecha à noite. Isso não é problema.

        Marcar "em risco" por desconexão faria a tela acusar problema toda
        noite — e treinaria o cliente a ignorá-la, que é o pior resultado
        possível para um aviso de backup.
        """
        offline = {**MAQUINA, "ultimo_contato": "2026-08-27T19:00:00"}
        veredito = julgar([politica()], [execucao()], dispositivos=[offline])
        assert veredito["nivel"] == Nivel.PROTEGIDO.value


class TestNaoDivergirDoAgendador:
    def test_a_tolerancia_e_a_mesma_do_agendador(self) -> None:
        """
        A tela e a máquina precisam concordar sobre "atrasado".

        Se a tolerância daqui fosse maior, o Agente desistiria de executar uma
        janela enquanto a tela ainda dissesse que está tudo em dia — e ninguém
        veria o buraco.
        """
        from apps.agente.agente.agendador import TOLERANCIA_ATRASO

        assert TOLERANCIA == TOLERANCIA_ATRASO


class TestAJanelaDaNuvem:
    """
    "Protegido" precisa significar que a copia CHEGOU la.

    `protege_de_verdade` e uma afirmacao sobre a CONFIGURACAO: diz que o
    destino escolhido tira a copia de perto do original. Nao diz que a copia
    chegou. Para disco externo e pasta de rede as duas coisas andam juntas — a
    entrega acontece dentro da execucao, e execucao concluida significa copia
    entregue e conferida.

    Para a nuvem, nao. O agendamento roda offline de proposito, e o envio
    espera haver canal. Existe uma janela — pacote feito, ainda nao subiu — em
    que dizer "Protegido" seria falso. E era exatamente o que a tela dizia:
    desde o instante em que a politica era salva.
    """

    def na_nuvem(self, **mudancas: Any) -> dict[str, Any]:
        return politica(
            configuracao={"destino": {"tipo": "nuvem", "caminho": ""}},
            **mudancas,
        )

    def test_pacote_ainda_nao_enviado_e_protecao_parcial(self) -> None:
        veredito = julgar([self.na_nuvem(nuvem_pendente=True)], [execucao()])

        assert veredito["nivel"] == Nivel.PARCIAL.value
        assert any("ainda não subiu" in m for m in veredito["backups"][0]["motivos"])

    def test_o_motivo_explica_que_o_pacote_existe(self) -> None:
        """
        Nao e falha, e nao pode parecer falha.

        O backup aconteceu, o pacote esta feito e conferido. O que falta e a
        viagem. Um recado que soasse como erro mandaria a pessoa procurar
        defeito onde nao ha.
        """
        veredito = julgar([self.na_nuvem(nuvem_pendente=True)], [execucao()])

        motivo = " ".join(veredito["backups"][0]["motivos"])
        assert "feito e" in motivo
        assert "conexão" in motivo

    def test_depois_do_envio_confirmado_e_protegido(self) -> None:
        veredito = julgar([self.na_nuvem(nuvem_pendente=False)], [execucao()])

        assert veredito["nivel"] == Nivel.PROTEGIDO.value

    def test_sem_a_informacao_nao_inventa_pendencia(self) -> None:
        # Politica sem a chave — o caso de quem chama `avaliar` direto. A
        # ausencia de informacao nao pode virar acusacao.
        veredito = julgar([self.na_nuvem()], [execucao()])

        assert veredito["nivel"] == Nivel.PROTEGIDO.value

    def test_pendencia_de_nuvem_nao_esconde_uma_falha(self) -> None:
        """O pior ganha: falha continua sendo mais grave que espera."""
        veredito = julgar(
            [self.na_nuvem(nuvem_pendente=True)],
            [execucao(resultado="falha", ressalva="disco cheio")],
        )

        assert veredito["nivel"] == Nivel.EM_RISCO.value
