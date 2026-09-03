# Relatório de validação — triagens simuladas

Data: 16/08/2026
Escopo: motor local PrevIA, sem consulta a links, serviços ou bases externas.

## Critério usado

Cada resultado abaixo é **elegibilidade na triagem interna**, isto é, o caso alcançou o status `aprovado` na árvore local a partir das informações simuladas. Não significa concessão, direito líquido e certo, cálculo de RMI ou dispensa de revisão jurídica.

Foram executadas 11 validações: pré-filtro de aposentadoria com evidência CNIS simulada, árvore completa de aposentadoria e os outros nove fluxos publicamente disponíveis. O robô possui 10 benefícios ativos; a décima primeira validação cobre a porta de entrada documental da aposentadoria.

## Resultado das simulações

| # | Cliente fictício | Jornada | Informações/evidências usadas pelo motor | Caminho de decisão | Resultado local |
|---:|---|---|---|---|---|
| 1 | Carlos Simulado | Pré-filtro de aposentadoria | CNIS simulado classificado como CNIS; nascimento 01/01/1958; 18 anos estimados de contribuição; primeira filiação antes da EC 103; sem indicadores simulados | O CNIS substituiu a idade e o tempo manuais; atingiu a referência de entrada | `triagem_tecnica`: pode iniciar análise técnica, sem reconhecimento de direito |
| 2 | Carlos Simulado | Aposentadoria | Histórico contributivo, perfil comum, viabilidade inicial, regra de transição, CNIS sem divergências declaradas e documentos disponíveis | AP-01 Sim → AP-02 Comum → AP-03 Sim → AP-06 Regra de transição → AP-07 Sem divergências → AP-08 Nenhum → AP-09 Planejamento → AP-10 Sim | `aprovado`: análise/planejamento previdenciário |
| 3 | Ana Acidente | Auxílio-Acidente | Cobertura previdenciária, acidente/doença ocupacional, sequela permanente e afastamento/documentação | AA-01 Sim → AA-02 Sim → AA-03 Sim → AA-04 Sim | `aprovado`: encaminhar para dossiê e equipe jurídica |
| 4 | Beatriz BPC | BPC/LOAS | Idosa 65+, baixa renda declarada e documentação socioeconômica disponível | BP-01 Idoso 65+ → BP-03 Sim → BP-04 Sim | `aprovado`: validação socioeconômica e documental |
| 5 | Camila Mãe | Salário-Maternidade | Evento gerador, vínculo CLT, qualidade de segurada e documentação | SM-01 Sim → SM-02 CLT/empregada → SM-03 Sim → SM-04 Sim | `aprovado`: conferir evento, categoria e documentos |
| 6 | Daniel Afastado | Auxílio-Doença | Incapacidade alegada, qualidade de segurado e prova médica inicial | AD-01 Sim → AD-02 Sim → AD-03 Sim | `aprovado`: preparar dossiê médico e qualidade de segurado |
| 7 | Elisa Permanente | Aposentadoria por Invalidez | Incapacidade permanente, qualidade de segurada e documentação médica | AI-01 Sim → AI-02 Sim → AI-03 Sim | `aprovado`: submeter à análise médico-previdenciária |
| 8 | Fernanda Dependente | Pensão por Morte | Óbito, dependência e qualidade do instituidor declarados | PM-01 Sim → PM-02 Sim → PM-03 Sim | `aprovado`: conferir certidão, dependência e CNIS do instituidor |
| 9 | Gustavo Dependente | Auxílio-Reclusão | Prisão, dependência e qualidade de segurado declaradas | AR-01 Sim → AR-02 Sim → AR-03 Sim | `aprovado`: conferir certidão carcerária e requisitos do instituidor |
| 10 | Helena Revisão | Revisão de Benefício | Benefício existente, tese inicial e documentos de cálculo | RB-01 Sim → RB-02 Sim → RB-03 Sim | `aprovado`: revisar carta, processo e memória de cálculo |
| 11 | Igor Planejamento | Planejamento Previdenciário | Base contributiva, objetivo definido e documentos disponíveis | PP-01 Sim → PP-02 Sim → PP-03 Sim | `aprovado`: produzir cenários e estratégia documental |

## Como o resultado foi obtido

1. O teste criou estados temporários pelo `triage_engine.create_state`; nenhum atendimento, lead, documento ou evento foi gravado no banco.
2. Cada resposta foi aplicada pelo próprio `triage_engine.answer_current_question`. O resultado veio de `flows_data.py`, a mesma árvore consumida pela interface.
3. Para aposentadoria, o `retirement_prefilter.evaluate_retirement_prefilter` recebeu uma evidência CNIS simulada. Quando a evidência é CNIS, idade e tempo de contribuição extraídos substituem os valores manuais; esse comportamento foi validado por teste automatizado.
4. O checklist de cada caso veio de `document_rules.get_flow_document_strategy`, não de regra inventada no relatório.
5. A suite percorreu ainda **todas as respostas declaradas de cada árvore**, validando que toda opção alcança resultado válido e que não há rotas mortas.

## Dossiê mínimo que o sistema exige após a triagem

| Jornada | Documentos específicos obrigatórios além dos documentos comuns |
|---|---|
| Auxílio-Acidente | CAT/prova do acidente; laudo de evolução da sequela |
| Aposentadoria | CNIS e CTPS já fazem parte do núcleo comum obrigatório |
| BPC/LOAS | CadÚnico; extratos de renda e despesas |
| Salário-Maternidade | Certidão/guarda/adoção; prova da categoria |
| Auxílio-Doença | Atestados atuais; laudos, exames ou relatórios |
| Aposentadoria por Invalidez | Laudo com incapacidade permanente |
| Pensão por Morte | Certidão de óbito; prova de dependência; documentos previdenciários do instituidor |
| Auxílio-Reclusão | Certidão carcerária; prova de dependência |
| Revisão de Benefício | Carta de concessão/decisão; processo administrativo e memória de cálculo |
| Planejamento Previdenciário | Documentos complementares de períodos, contribuições e objetivo |

Documentos comuns obrigatórios: identificação com foto, CPF, comprovante de residência, CNIS e CTPS.

## Limites e achados

- Uma resposta “Sim” na triagem é uma declaração de entrada. Ela precisa ser confrontada com OCR, documentos e revisão humana antes de qualquer protocolo ou promessa ao cliente.
- O CNIS pode fornecer idade, períodos, competências e indicadores quando esses elementos forem realmente extraídos; se o OCR não estruturar o dado, o sistema deve manter o caso em revisão, não completar valores por suposição.
- BPC, incapacidade, pensão, reclusão, revisão e salário-maternidade ainda dependem de documentos específicos. O motor atual valida aderência inicial e checklist; não substitui perícia, análise socioeconômica, qualidade de segurado ou cálculo previdenciário.
- Não há 11º benefício público ativo hoje. O módulo “Outros Assuntos” foi removido por estar fora do escopo; por isso a 11ª execução foi o pré-filtro documental de aposentadoria.

## Verificação automatizada

- `tests/test_simulated_triage_journeys.py`: 11 simulações internas aprovadas conforme os cenários acima.
- `tests/test_full_triage_coverage.py`: todas as alternativas das 10 árvores ativas chegam a resultado válido e têm estratégia documental.
- Suite completa: 38 testes aprovados.
