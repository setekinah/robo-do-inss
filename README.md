# SOFI.IA PREVI

Aplicacao local em Python + Streamlit para operacao previdenciaria com:

- triagem guiada de leads
- CRM operacional
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

Se voce usa o Python instalado em:

`C:\Users\bruno\AppData\Local\Python\pythoncore-3.14-64\python.exe`

tambem pode rodar:

```powershell
& "C:\Users\bruno\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pip install -r "C:\Users\bruno\OneDrive\Desktop\Robo do INSS\requirements.txt"
& "C:\Users\bruno\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run "C:\Users\bruno\OneDrive\Desktop\Robo do INSS\app.py"
```

Ou usar o launcher:

- `iniciar_robo_inss.bat`
- `iniciar_robo_inss_completo.bat`

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
