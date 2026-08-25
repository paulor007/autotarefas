# AutoTarefas Agente

O programa que roda **na máquina do cliente**. Existe porque o navegador não
alcança o disco de ninguém: proteger uma pasta local, com horário e destino
externo, exige um processo instalado ali.

## Princípios

| Regra | Por quê |
| --- | --- |
| Conexão **de saída** (WSS) | Ninguém precisa abrir porta no roteador da empresa, e não há serviço escutando na rede interna |
| Par de chaves **Ed25519** | O servidor guarda só a parte pública. Um vazamento do banco não permite se passar por nenhum dispositivo |
| Pastas autorizadas **na própria máquina** | Uma tela na nuvem não concede acesso ao disco de ninguém. O servidor pede; o Agente autoriza |
| Segredo **fora da configuração** | A chave privada fica no cofre do Windows; o `agente.json` guarda só endereço, id e pastas |

## Estado

Em construção — trilha G do Card 02. Ver
[docs/cards/02-roadmap-execucao.md](../../docs/cards/02-roadmap-execucao.md).
