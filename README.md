# SOFI.IA PREVI

Aplicacao local em Python + Streamlit para operacao previdenciaria com:

- triagem guiada de leads, com perfil previdenciário estruturado para aposentadoria
- CRM jurídico com etapas, conflito de interesse, responsável, tarefas e histórico de interações
- orquestrador interno de eventos com fila, idempotência, auditoria e revisão humana de tarefas críticas
- checklist documental por beneficio
- leitura tecnica local de PDF e imagem
- preview de contratos e configuracoes do escritorio

## Estado atual

O produto ativo do repositorio e o Streamlit em `app.py`.

Arquivos como `index.html`, `app.js`, `flows.js` e `styles.css` pertencem a um prototipo legado e nao sao a interface principal atual.

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

## Dependencias opcionais da fase documental

Para leitura documental local mais completa, o ambiente pode exigir:

- `pypdf`
- `pillow`
- `pytesseract`
- instalacao do `tesseract.exe` no Windows

## Documentacao principal

- Arquitetura do sistema: [docs/ARQUITETURA_DO_SISTEMA.md](docs/ARQUITETURA_DO_SISTEMA.md)

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
