# Piloto local: Papermerge + PrevIA

## Objetivo

Validar o Papermerge como repositório documental local e independente do PrevIA. O CRM, a triagem guiada e as regras dos 11 benefícios continuam no PrevIA. Este piloto avalia apenas arquivo, OCR, busca, versionamento e auditoria dos documentos.

## Isolamento e privacidade

- Papermerge: `http://localhost:8081`.
- PrevIA: permanece em `http://localhost:8000`.
- O serviço é ligado apenas em `127.0.0.1`: não fica público na rede.
- Os arquivos e banco ficam em volumes Docker locais próprios (`previa_papermerge_pilot_media` e `previa_papermerge_pilot_db`).
- Não enviar documentos reais ou dados de saúde para o piloto. Usar amostra anonimizada e aprovada pelo escritório.

## Arquitetura adotada

O Papermerge será o arquivo documental e índice de busca; não tomará decisões de elegibilidade. Ele preserva versões, executa OCR e permite pesquisa por conteúdo, título e tags. O PrevIA seguirá responsável pela leitura previdenciária, validação de campos e regras de cada benefício.

O worker do piloto é construído localmente a partir da imagem oficial com o idioma `por` do Tesseract. A imagem oficial só inclui inglês e alemão; essa extensão é necessária para que o OCR de documentos brasileiros seja minimamente válido.

### Taxonomia inicial do escritório

Na homologação, criar os seguintes **tipos documentais**: CNIS, CTPS, PPP/LTCAT, CAT, Laudo Médico, CadÚnico, Certidão, Carta de Concessão, Processo Administrativo, Documento de Identificação, Comprovante de Renda e Documento de Auxílio-Reclusão.

Para cada tipo, usar campos de metadados compatíveis com o arquivo, como `benefício`, `cliente_id_PrevIA`, `competência`, `número do benefício`, `CPF mascarado`, `NIT mascarado`, `data do documento`, `validado por` e `status de conferência`. Um documento recebe apenas um tipo no Papermerge; quando for relevante a mais de um benefício, usar tags, por exemplo `aposentadoria`, `bpc-loas`, `revisão` e `pendência`.

## Início

1. Instale e abra o Docker Desktop, aguardando o status **Running**.
2. Entre em `docker/papermerge-pilot`.
3. Execute `./start-pilot.ps1`.
4. Na primeira execução, preencha `docker/papermerge-pilot/.env` com uma chave e senha locais fortes.
5. Execute `./start-pilot.ps1` de novo e acesse `http://localhost:8081`.

Para acompanhar a inicialização: `docker compose --env-file .env logs -f`.

## Roteiro de homologação

Monte uma amostra anonimizada com 30 a 50 documentos, cobrindo ao menos CNIS, CTPS, PPP/LTCAT, CAT, laudos médicos, CadÚnico, certidões, cartas de concessão e documentos de auxílio-reclusão. Registre, por documento:

| Critério | Como validar |
| --- | --- |
| Leitura | OCR recupera texto suficiente para pesquisa? |
| Busca | CPF mascarado, NIT mascarado, nome e empresa retornam o documento correto? |
| Estrutura | Tipo documental, tags e campos identificam benefício e cliente? |
| Evidência | Operador consegue conferir página/original antes de usar um campo? |
| Operação | Upload, nova versão e recuperação funcionam sem perda? |
| Segurança | Usuário, permissões e trilha de auditoria atendem à política interna? |

Nenhum CPF, NIT, data crítica, diagnóstico médico ou direito previdenciário pode ser aceito automaticamente. A aprovação humana e a comparação com o original continuam obrigatórias.

## Integração futura, somente após homologação

O Papermerge disponibiliza API REST documentada por OpenAPI na própria instância e usa token por usuário. A integração segura será unidirecional no início: o PrevIA envia uma cópia aprovada do documento e recebe o identificador, o status de OCR e a referência interna. Não haverá token no navegador, nem consulta direta do navegador ao Papermerge.

## Critério de decisão

Só integrar ao PrevIA por API após o piloto demonstrar busca confiável, preservação de versão/original, permissões adequadas e rotina de backup. A primeira integração deverá ser somente de referência: o PrevIA armazena o identificador e o link interno do documento, sem duplicar o arquivo nem transformar o Papermerge em motor das regras previdenciárias.
