# Catálogo oficial Portal IN

## Objetivo

O PrevIA mantém uma base versionada de indicadores CNIS e de referências administrativas para transformar a leitura documental em diagnóstico operacional: indicador encontrado, risco, documentos de apoio e providência sugerida.

O catálogo **não** substitui análise jurídica nem ativa alterações normativas de forma automática.

## Fontes

O registro de fontes é uma lista controlada no código (`official_catalog.py`) e aponta somente para documentos públicos do [Portal IN](https://portalin.inss.gov.br/anexos), incluindo Anexo V da PT 990 (indicadores CNIS), normas de transição, regras de atividade especial, dependentes e proteção social.

Em cada verificação, o sistema baixa apenas as URLs autorizadas, limita o tamanho da resposta, guarda o hash SHA-256 e registra data, resultado e versão do arquivo em armazenamento local. Documentos e banco operacional permanecem em `%LOCALAPPDATA%\Robo do INSS\data`, fora do Git.

## Fluxo de governança

1. No menu **Robô & Automação**, use **Verificar fontes oficiais**.
2. Havendo material novo, compare a versão, o hash e o texto com a fonte original.
3. Importe a planilha de indicadores CNIS quando aplicável. A importação cria uma versão com status `aguarda_revisao`.
4. Um responsável jurídico registra a nota de revisão e somente então ativa a versão.
5. O motor de OCR e o plano de ação passam a usar exclusivamente a versão ativa.

Uma versão pendente nunca altera diagnóstico, cálculo, elegibilidade, checklist ou minuta. A ativação é auditada e exige uma justificativa de revisão.

## Segurança e limites

- A coleta não usa URLs enviadas pelo navegador; apenas a allowlist do Portal IN é consultada.
- Não são enviados CNIS, CPF, documentos ou credenciais a serviços externos durante o monitoramento.
- O catálogo produz orientação e cenários; a conclusão previdenciária continua sujeita à validação humana e ao documento original.
- Indicadores pendentes podem alimentar um cenário conservador e um cenário potencial, mas não devem ser computados automaticamente como tempo confirmado.

## Endpoints locais

Todos exigem sessão autenticada:

- `GET /api/catalogo-cnis/status`
- `GET /api/catalogo-cnis/versoes`
- `POST /api/catalogo-cnis/monitorar`
- `POST /api/catalogo-cnis/importar-planilha`
- `POST /api/catalogo-cnis/versoes/{id}/ativar`

## Validação de desenvolvimento

```powershell
py -m py_compile api_server.py database.py official_catalog.py cnis_knowledge.py
py -m unittest tests.test_document_intelligence tests.test_auth_security -v
node --check app.js
```
