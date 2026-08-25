"""AutoTarefas Agente: o programa que roda na maquina do cliente.

Ele existe porque o navegador nao alcanca o disco de ninguem. O Agente le as
pastas que a pessoa autorizou NA PROPRIA MAQUINA, executa o backup com o mesmo
nucleo da CLI, e conversa com o Live por uma conexao de SAIDA — ninguem precisa
abrir porta no roteador da empresa.

O que ele nunca faz: aceitar conexao de entrada, ler pasta que nao foi
autorizada localmente, ou guardar segredo que o servidor tambem tenha.
"""

from .config import Configuracao, Local
from .identidade import Guarda, Identidade, obter_ou_criar, pasta_padrao

__all__ = [
    "Configuracao",
    "Guarda",
    "Identidade",
    "Local",
    "obter_ou_criar",
    "pasta_padrao",
]
