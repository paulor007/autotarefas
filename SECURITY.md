# 🔒 Política de Segurança

## Versões Suportadas

Atualmente, as seguintes versões do AutoTarefas recebem atualizações de segurança:

| Versão | Suportada          |
| ------ | ------------------ |
| 0.1.x  | ✅ Sim             |
| < 0.1  | ❌ Não             |

## Reportando uma Vulnerabilidade

A segurança do AutoTarefas é levada a sério. Se você descobrir uma vulnerabilidade de segurança, agradecemos sua ajuda em divulgá-la de forma responsável.

### Como Reportar

**⚠️ NÃO reporte vulnerabilidades de segurança através de issues públicas do GitHub.**

Em vez disso, por favor:

1. **Envie um email** para: paulo.lavarini@gmail.com
2. **Inclua as seguintes informações:**
   - Tipo de vulnerabilidade (ex: injeção de código, escalação de privilégios, etc.)
   - Caminhos completos dos arquivos fonte relacionados
   - Localização do código afetado (branch/commit/URL)
   - Configuração especial necessária para reproduzir
   - Passos detalhados para reproduzir o problema
   - Prova de conceito ou código de exploit (se possível)
   - Impacto potencial da vulnerabilidade

### O Que Esperar

- **Confirmação:** Você receberá uma confirmação de recebimento em até 48 horas
- **Avaliação:** Avaliaremos a vulnerabilidade e determinaremos sua gravidade em até 7 dias
- **Atualizações:** Manteremos você informado sobre o progresso da correção
- **Correção:** Vulnerabilidades críticas serão corrigidas o mais rápido possível
- **Créditos:** Você receberá crédito pela descoberta (se desejar) quando a correção for publicada

### Escopo

#### Dentro do Escopo

- Vulnerabilidades no código do AutoTarefas
- Problemas de configuração que levem a falhas de segurança
- Dependências com vulnerabilidades conhecidas
- Exposição não intencional de dados sensíveis

#### Fora do Escopo

- Ataques de engenharia social
- Ataques físicos
- Vulnerabilidades em serviços de terceiros não controlados por nós
- Problemas já conhecidos e documentados

## Boas Práticas de Segurança

### Para Usuários

1. **Proteja suas credenciais:**
   - Nunca commite o arquivo `.env` com senhas reais
   - Use senhas de app para serviços de email
   - Mantenha suas credenciais SMTP seguras

2. **Cuidado com permissões:**
   - Não execute o AutoTarefas como root/administrador desnecessariamente
   - Use o mínimo de permissões necessárias

3. **Mantenha atualizado:**
   - Atualize para a versão mais recente regularmente
   - Verifique o CHANGELOG para correções de segurança

4. **Backup seguro:**
   - Proteja seus backups com permissões adequadas
   - Considere criptografar backups sensíveis

### Para Desenvolvedores

1. **Validação de entrada:**
   - Sempre valide caminhos de arquivos
   - Sanitize nomes de arquivos
   - Verifique permissões antes de operações

2. **Secrets:**
   - Use variáveis de ambiente para credenciais
   - Nunca logue senhas ou tokens
   - Mascare informações sensíveis na saída

3. **Dependências:**
   - Mantenha dependências atualizadas
   - Verifique vulnerabilidades conhecidas
   - Use `pip-audit` ou ferramentas similares

## Histórico de Segurança

### Vulnerabilidades Corrigidas

| Data | Versão | Descrição | Gravidade |
|------|--------|-----------|-----------|
| - | - | Nenhuma vulnerabilidade reportada até o momento | - |

---

## Agradecimentos

Agradecemos a todos os pesquisadores de segurança que ajudam a manter o AutoTarefas seguro.

## Contato

Para questões de segurança: paulo.lavarini@gmail.com

Para questões gerais: Use as [GitHub Discussions](https://github.com/paulor007/autotarefas/discussions)
