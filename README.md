# SOFI.IA PREVI

Aplicacao local em Python + Streamlit para operacao previdenciaria com:

- triagem guiada de leads, com perfil previdenciário estruturado para aposentadoria
- CRM jurídico com etapas, conflito de interesse, responsável, tarefas e histórico de interações
- orquestrador interno de eventos com fila, idempotência, auditoria e revisão humana de tarefas críticas
- checklist documental por beneficio
- leitura tecnica local de PDF e imagem
- preview de contratos e configuracoes do escritorio

## Estado atual

O produto ativo pode ser executado de duas formas:

- `api_server.py` serve a interface operacional PrevIA (HTML/JS) em `http://localhost:8501`.
- `app.py` preserva a operação Streamlit local.

A interface PrevIA concentra dashboard, esteira Kanban, base de relacionamento, triagem guiada, documentos/OCR e o monitor de automação.

## Como rodar

No diretorio do projeto:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Os comandos devem ser executados dentro da pasta em que o repositório foi extraído ou clonado. Não há caminho de usuário fixo no projeto.

Ou usar o launcher:

- `iniciar_robo_inss.bat`
- `iniciar_robo_inss_completo.bat` (instala o Streamlit se necessário e abre o navegador)

Os dados operacionais (banco SQLite, configurações e documentos enviados) são armazenados localmente em `%LOCALAPPDATA%\Robo do INSS\data` e não devem ser adicionados ao Git.

## Assinatura digital local (DocuSeal)

Com o contêiner DocuSeal ativo em `http://localhost:3000`, copie a chave
`X-Auth-Token` em **Configurações > API** e, no PowerShell dentro deste
repositório, execute `./configurar_docuseal.ps1`. O script solicita a chave
sem exibi-la e grava a configuração fora do repositório, em
`%LOCALAPPDATA%\Robo do INSS\data\docuseal.json`. Nunca adicione essa chave
ao Git, a um `.env` versionado ou a conversas.

## Inteligência documental e OCR

O `requirements.txt` instala o pipeline documental completo:

- `PyMuPDF` para leitura rápida de PDF nativo, detecção de páginas escaneadas e rasterização seletiva
- `RapidOCR` + `ONNX Runtime` para OCR neural local, portátil e sem envio de documentos à nuvem
- `Pillow` + CLAHE/OpenCV para normalização, contraste, redução de ruído e nova tentativa em imagens difíceis
- `pypdf` como leitor alternativo de PDFs nativos
- `pytesseract` como fallback quando o aplicativo Tesseract está instalado no Windows

O sistema não considera OCR como validação jurídica. Resultados com baixa confiança ou campos críticos ausentes permanecem sujeitos à comparação humana com o original. CPF/CNPJ e NIT/NIS/PIS/PASEP passam por validação de dígitos, e datas civis completas não são classificadas como competências contributivas.

Variáveis opcionais de ambiente:

- `OCR_MAX_FILE_MB` — limite por arquivo, padrão 50 MB
- `OCR_MAX_PAGES` — máximo de páginas escaneadas processadas por PDF, padrão 12
- `OCR_PDF_DPI` — resolução de rasterização, padrão 170 DPI
- `TESSERACT_CMD` — caminho manual para `tesseract.exe`, quando necessário

## Documentacao principal

- Arquitetura do sistema: [docs/ARQUITETURA_DO_SISTEMA.md](docs/ARQUITETURA_DO_SISTEMA.md)
- Catálogo oficial e revisão jurídica: [docs/CATALOGO_OFICIAL_PORTAL_IN.md](docs/CATALOGO_OFICIAL_PORTAL_IN.md)
- Piloto Papermerge: [docs/PILOTO_PAPERMERGE.md](docs/PILOTO_PAPERMERGE.md)
- Piloto dArchiva: [docs/darchiva_pilot.md](docs/darchiva_pilot.md)

## Fluxos atualmente mapeados

1. Auxilio-Acidente
2. Aposentadoria
3. BPC/LOAS
4. Salario-Maternidade
5. Auxilio-Doenca
6. Aposentadoria por Invalidez
7. Pensao por Morte
8. Auxilio-Reclusao
9. Revisao de Beneficio
10. Planejamento Previdenciario
11. Outros Assuntos

## Regras do CRM jurídico

- Registre responsável, próxima ação e data para todo atendimento em andamento.
- Faça a checagem de conflito antes de orientar juridicamente, enviar proposta ou liberar contrato.
- Use o histórico de relacionamento para registrar ligações, WhatsApp, e-mails, reuniões e notas internas.
- Registre a entrega do aviso de privacidade e a base legal predominante do tratamento.
- O contrato permanece bloqueado até a aprovação da triagem, a liberação do conflito e o registro de privacidade/LGPD.
- Casos bloqueados continuam visíveis na esteira de contratos, com o motivo e o atalho para regularização no CRM.
- Eventos repetidos não criam tarefas duplicadas.
- Publicações, movimentações e exigências geram datas operacionais sugeridas; um responsável deve confirmar qualquer prazo jurídico.
- A integração com Astrea foi excluída. Kanban, tarefas, documentos e auditoria pertencem ao CRM próprio.

## Testes

```powershell
py -m unittest discover -s tests -v
```
