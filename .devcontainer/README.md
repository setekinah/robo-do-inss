# PrevIA no GitHub Codespaces

Abra o repositório no GitHub e escolha **Code → Codespaces → Create codespace**.

O Codespace instala as dependências automaticamente pelo `requirements.txt`. A
porta `8000` aparece como **PrevIA** e deve permanecer **Private** no painel
**PORTS**. Codespaces é apenas ambiente de desenvolvimento e testes, não
produção.

Os dados locais de teste (banco, credenciais locais e configurações) ficam em
`/workspaces/.previa-data`, fora da pasta Git do projeto. Apagar o Codespace
pode apagar esse ambiente local.

Para iniciar a aplicação:

```bash
python api_server.py
```

Para executar os testes:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Segredos do Fil One

Fil One continua externo. Configure os valores apenas em **GitHub Codespaces
Secrets**, sem criar ou versionar um `.env`. Os nomes esperados são:

- `FILONE_ENDPOINT`
- `FILONE_REGION`
- `FILONE_ACCESS_KEY`
- `FILONE_SECRET_KEY`
- `FILONE_BUCKET`
- `FILONE_MAX_DOCUMENT_MB`

Nunca inclua valores desses segredos em commits, arquivos do repositório ou
logs.
