# CNIS Analyzer v1

O CNIS Analyzer lê exclusivamente o texto extraído de documentos CNIS anexados ao caso. Ele não autentica no Meu INSS, não coleta dados de portais e não tenta contornar bloqueios.

## Fluxo

1. O documento CNIS é enviado pelo usuário e processado localmente pelo pipeline de OCR.
2. O Dossiê Probatório chama `modules.cnis_analyzer.analyze_cnis_documents`.
3. A análise devolve sinais, orientação e evidência (documento, página e trecho) para revisão humana.
4. O advogado registra a decisão no próprio Dossiê.

## Limites deliberados

- PEXT e referências a PPP/LTCAT são sinais de conferência, não conclusões.
- Períodos longos identificados no texto não confirmam vínculo, tempo de contribuição ou carência.
- O módulo não calcula elegibilidade, tempo, melhor benefício ou RMI.
- A referência normativa é o Anexo V da PT 990; sua vigência deve ser conferida no catálogo oficial versionado antes do uso técnico.

## Contrato e falhas

O contrato de entrada é validado com Pydantic. Texto vazio, inválido ou inexistente devolve um resultado seguro (`nao_analisado` ou `documento_ausente`) e nunca uma aprovação implícita.
