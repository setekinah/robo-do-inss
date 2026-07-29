# Guia da Versao Python

Esta e a versao recomendada do sistema para uso local.

## Arquivos principais

- `app.py`: interface Streamlit
- `flows_data.py`: regras dos fluxos
- `triage_engine.py`: motor de decisao
- `database.py`: persistencia SQLite
- `requirements.txt`: dependencia principal

## Como rodar

```powershell
py -m streamlit run app.py
```

## O que ela faz

- Cadastro do lead
- Triagem por perguntas
- Resultado com classificacao final
- Salvamento local em `data/triagem.db`
- Lista lateral com atendimentos recentes

## Observacao

Os arquivos HTML e JavaScript continuam na pasta como MVP anterior, mas a operacao principal agora e a interface em Python.
