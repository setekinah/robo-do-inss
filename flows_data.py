"""Definicoes dos fluxos de triagem do SOFI.IA PREVI."""

FLOW_DEFINITIONS = {
    "auxilioAcidente": {
        "id": "auxilioAcidente",
        "name": "Auxilio-Acidente",
        "start": "vinculo",
        "nodes": {
            "vinculo": {
                "id": "vinculo",
                "code": "AA-01",
                "title": "O lead possui vinculo previdenciario ou historico que indique cobertura do INSS?",
                "help": (
                    "Sem vinculo ou sem historico aproveitavel, o caso tende a perder aderencia "
                    "para o fluxo de auxilio-acidente."
                ),
                "options": [
                    {
                        "label": "Sim",
                        "description": "Existe vinculo, contribuicao ou historico aproveitavel.",
                        "next": "acidente",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha base previdenciaria minima.",
                        "result": "desqualificadoSemVinculo",
                    },
                ],
            },
            "acidente": {
                "id": "acidente",
                "code": "AA-02",
                "title": "Houve acidente ou doenca ocupacional relacionada a atividade profissional?",
                "help": "Sem acidente ou nexo ocupacional claro, a estrategia juridica costuma mudar.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Existe acidente ou nexo ocupacional.",
                        "next": "sequela",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha acidente ou nexo ocupacional claro.",
                        "result": "desqualificadoSemAcidente",
                    },
                ],
            },
            "sequela": {
                "id": "sequela",
                "code": "AA-03",
                "title": "Ficou uma sequela permanente que reduziu a capacidade para a atividade habitual?",
                "help": "Este e o nucleo do auxilio-acidente.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha indicio de sequela consolidada com reducao funcional.",
                        "next": "afastamento",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao houve sequela permanente comprovavel.",
                        "result": "desqualificadoSemSequela",
                    },
                ],
            },
            "afastamento": {
                "id": "afastamento",
                "code": "AA-04",
                "title": "Houve afastamento, beneficio por incapacidade ou documentacao medica relevante?",
                "help": (
                    "Laudos, CAT, exames, CNIS e historico do INSS fortalecem a validacao final."
                ),
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha documentos e historico aproveitaveis.",
                        "result": "qualificadoAuxilioAcidente",
                    },
                    {
                        "label": "Parcial",
                        "description": "Existe algo, mas o material ainda esta incompleto.",
                        "result": "revisaoDocumentalAA",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha documentacao minima.",
                        "result": "revisaoDocumentalAA",
                    },
                ],
            },
        },
        "results": {
            "qualificadoAuxilioAcidente": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de Auxilio-Acidente",
                "summary": (
                    "Ha sinais de vinculo, acidente ou doenca ocupacional, sequela permanente "
                    "e base documental inicial."
                ),
                "next_step": (
                    "Encaminhar para equipe juridica com checklist documental e agendamento."
                ),
            },
            "revisaoDocumentalAA": {
                "status": "revisao",
                "title": "Caso promissor, mas precisa reforco documental",
                "summary": "O fluxo indica potencial, porem faltam laudos, CAT, exames ou historico robusto.",
                "next_step": "Solicitar documentos e reavaliar antes do fechamento.",
            },
            "desqualificadoSemVinculo": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de vinculo previdenciario util",
                "summary": "Sem base previdenciaria minima, o fluxo perde aderencia para este beneficio.",
                "next_step": "Encerrar com empatia ou redirecionar para outro fluxo.",
            },
            "desqualificadoSemAcidente": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de acidente ou nexo ocupacional",
                "summary": "O caso nao se alinha ao criterio central do auxilio-acidente.",
                "next_step": "Avaliar se o lead se enquadra em outro atendimento.",
            },
            "desqualificadoSemSequela": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de sequela permanente",
                "summary": "Sem reducao permanente da capacidade habitual, o beneficio tende a nao encaixar.",
                "next_step": "Encerrar ou migrar para outro fluxo se houver aderencia.",
            },
        },
    },
    "aposentadoria": {
        "id": "aposentadoria",
        "name": "Aposentadoria",
        "start": "contribuicao",
        "nodes": {
            "contribuicao": {
                "id": "contribuicao",
                "code": "AP-01",
                "title": "O lead possui historico contributivo ou tempo de servico identificavel?",
                "help": (
                    "Pode vir de carteira, CNIS, atividade rural, servico publico, atividade especial "
                    "ou outros vinculos."
                ),
                "options": [
                    {
                        "label": "Sim",
                        "description": "Existe tempo a apurar ou averbar.",
                        "next": "perfil",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha base contributiva conhecida.",
                        "result": "desqualificadoSemTempo",
                    },
                ],
            },
            "perfil": {
                "id": "perfil",
                "code": "AP-02",
                "title": "Qual e o perfil predominante do caso?",
                "help": "Escolha o cenario mais forte para orientar o bloco seguinte.",
                "options": [
                    {
                        "label": "Comum",
                        "description": "Tempo urbano ou comum predominante.",
                        "next": "idadeTempo",
                    },
                    {
                        "label": "PCD",
                        "description": "Possui possivel enquadramento como pessoa com deficiencia.",
                        "next": "pcd",
                    },
                    {
                        "label": "Especial",
                        "description": "Ha exposicao especial ou atividade nociva.",
                        "next": "especial",
                    },
                ],
            },
            "idadeTempo": {
                "id": "idadeTempo",
                "code": "AP-03",
                "title": "A soma atual de idade, tempo e carencia ja sugere viabilidade de aposentadoria?",
                "help": "Etapa inicial de pontos, idade minima e carencia.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha forte sinal de direito amadurecido.",
                        "next": "documentosApo",
                    },
                    {
                        "label": "Quase",
                        "description": "Depende de acertos ou averbacoes.",
                        "result": "revisaoPlanejamento",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda esta distante do requisito minimo.",
                        "result": "desqualificadoSemRequisitos",
                    },
                ],
            },
            "pcd": {
                "id": "pcd",
                "code": "AP-04",
                "title": "Existe documentacao ou historico consistente para aposentadoria da PCD?",
                "help": "Entram aqui laudos, periodo da deficiencia e documentacao medica minima.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha base para seguir no fluxo PCD.",
                        "next": "documentosApo",
                    },
                    {
                        "label": "Parcial",
                        "description": "Existe indicio, mas falta prova consistente.",
                        "result": "revisaoPlanejamento",
                    },
                    {
                        "label": "Nao",
                        "description": "Sem prova minima da deficiencia no periodo.",
                        "result": "desqualificadoSemRequisitos",
                    },
                ],
            },
            "especial": {
                "id": "especial",
                "code": "AP-05",
                "title": "Ha PPP, LTCAT ou outra prova de atividade especial?",
                "help": "Aposentadoria especial ou conversao de tempo depende fortemente de prova tecnica.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Existe documentacao tecnica relevante.",
                        "next": "documentosApo",
                    },
                    {
                        "label": "Parcial",
                        "description": "Alguma prova existe, mas precisa consolidar.",
                        "result": "revisaoPlanejamento",
                    },
                    {
                        "label": "Nao",
                        "description": "Sem prova tecnica suficiente.",
                        "result": "desqualificadoSemRequisitos",
                    },
                ],
            },
            "documentosApo": {
                "id": "documentosApo",
                "code": "AP-06",
                "title": "O lead consegue apresentar documentos para calculo e protocolo?",
                "help": "CNIS, carteira, PPP, laudos e certidoes sustentam a entrada do caso.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Documentacao suficiente para avancar.",
                        "result": "qualificadoAposentadoria",
                    },
                    {
                        "label": "Parcial",
                        "description": "Documentos incompletos, mas recuperaveis.",
                        "result": "revisaoPlanejamento",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda sem material para calculo serio.",
                        "result": "revisaoPlanejamento",
                    },
                ],
            },
        },
        "results": {
            "qualificadoAposentadoria": {
                "status": "aprovado",
                "title": "Lead qualificado para analise previdenciaria completa",
                "summary": (
                    "O caso indica possibilidade real de aposentadoria ou planejamento estrategico "
                    "com base documental."
                ),
                "next_step": "Enviar para calculo previdenciario, conferencia de requisitos e proposta.",
            },
            "revisaoPlanejamento": {
                "status": "revisao",
                "title": "Lead em revisao para planejamento e documentacao",
                "summary": (
                    "O caso tem potencial, mas depende de averbacoes, provas adicionais ou calculo mais fino."
                ),
                "next_step": "Solicitar documentos, complementar timeline e reavaliar com especialista.",
            },
            "desqualificadoSemTempo": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de historico contributivo identificavel",
                "summary": "Sem base minima de tempo ou contribuicao, o fluxo nao sustenta analise imediata.",
                "next_step": "Encerrar com orientacao inicial ou direcionar para outro beneficio.",
            },
            "desqualificadoSemRequisitos": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de requisitos atuais",
                "summary": "Pelos criterios iniciais, o lead ainda nao demonstra encaixe suficiente.",
                "next_step": "Registrar e acompanhar futuramente, se fizer sentido.",
            },
        },
    },
    "bpcLoas": {
        "id": "bpcLoas",
        "name": "BPC/LOAS",
        "start": "perfilBpc",
        "nodes": {
            "perfilBpc": {
                "id": "perfilBpc",
                "code": "BP-01",
                "title": "O caso e de idoso com 65+ ou de pessoa com deficiencia?",
                "help": "A primeira divisao do BPC/LOAS separa a via etaria da via deficiencia.",
                "options": [
                    {"label": "Idoso 65+", "description": "Fluxo assistencial etario.", "next": "rendaFamiliar"},
                    {
                        "label": "Pessoa com deficiencia",
                        "description": "Fluxo assistencial por deficiencia.",
                        "next": "deficiencia",
                    },
                    {
                        "label": "Nenhum",
                        "description": "Nao se encaixa no perfil-base.",
                        "result": "desqualificadoPerfilBpc",
                    },
                ],
            },
            "deficiencia": {
                "id": "deficiencia",
                "code": "BP-02",
                "title": (
                    "Existe impedimento de longo prazo que limite a participacao plena na sociedade "
                    "ou no trabalho?"
                ),
                "help": "Etapa eliminatoria forte para BPC por deficiencia.",
                "options": [
                    {"label": "Sim", "description": "Ha deficiencia de longo prazo.", "next": "rendaFamiliar"},
                    {
                        "label": "Parcial",
                        "description": "Ha indicio, mas a prova ainda e fraca.",
                        "result": "revisaoSocioeconomica",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha deficiencia de longo prazo identificavel.",
                        "result": "desqualificadoPerfilBpc",
                    },
                ],
            },
            "rendaFamiliar": {
                "id": "rendaFamiliar",
                "code": "BP-03",
                "title": "A renda familiar per capita indica hipossuficiencia?",
                "help": "Validacao socioeconomica: renda, composicao familiar e despesas relevantes.",
                "options": [
                    {"label": "Sim", "description": "A renda sugere enquadramento assistencial.", "next": "cadunico"},
                    {
                        "label": "Limitrofe",
                        "description": "Precisa de analise social detalhada.",
                        "result": "revisaoSocioeconomica",
                    },
                    {
                        "label": "Nao",
                        "description": "A renda afasta o enquadramento inicial.",
                        "result": "desqualificadoRenda",
                    },
                ],
            },
            "cadunico": {
                "id": "cadunico",
                "code": "BP-04",
                "title": "O CadUnico e a documentacao basica estao atualizados?",
                "help": "Documento pessoal, comprovantes e CadUnico atualizado costumam ser etapa-chave.",
                "options": [
                    {"label": "Sim", "description": "Documentacao assistencial pronta.", "result": "qualificadoBpc"},
                    {
                        "label": "Parcial",
                        "description": "Faltam atualizacoes simples.",
                        "result": "revisaoSocioeconomica",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha base documental suficiente.",
                        "result": "revisaoSocioeconomica",
                    },
                ],
            },
        },
        "results": {
            "qualificadoBpc": {
                "status": "aprovado",
                "title": "Lead qualificado para protocolo de BPC/LOAS",
                "summary": (
                    "Ha perfil elegivel, indicio socioeconomico favoravel e documentacao inicial consistente."
                ),
                "next_step": "Agendar atendimento, conferir documentacao final e seguir para protocolo.",
            },
            "revisaoSocioeconomica": {
                "status": "revisao",
                "title": "Caso depende de revisao socioeconomica e documental",
                "summary": (
                    "O beneficio pode ser viavel, mas precisa de CadUnico, laudos ou composicao familiar "
                    "mais robusta."
                ),
                "next_step": "Solicitar documentos e refazer a triagem apos atualizacao.",
            },
            "desqualificadoPerfilBpc": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de perfil-base do BPC/LOAS",
                "summary": "Sem idade minima ou deficiencia de longo prazo, o enquadramento nao se sustenta.",
                "next_step": "Redirecionar para outro fluxo compativel, se houver.",
            },
            "desqualificadoRenda": {
                "status": "desqualificado",
                "title": "Desqualificado pela renda familiar informada",
                "summary": "A triagem inicial nao indica hipossuficiencia suficiente para este beneficio.",
                "next_step": "Encerrar com orientacao ou submeter a revisao apenas se houver excecoes fortes.",
            },
        },
    },
    "salarioMaternidade": {
        "id": "salarioMaternidade",
        "name": "Salario-Maternidade",
        "start": "eventoGerador",
        "nodes": {
            "eventoGerador": {
                "id": "eventoGerador",
                "code": "SM-01",
                "title": "O caso envolve parto, adocao, guarda judicial para fins de adocao ou aborto nao criminoso?",
                "help": "Esta e a porta de entrada do salario-maternidade na triagem inicial.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Existe evento gerador compativel com o beneficio.",
                        "next": "qualidadeSegurada",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha evento gerador valido para este fluxo.",
                        "result": "desqualificadoSemEvento",
                    },
                ],
            },
            "qualidadeSegurada": {
                "id": "qualidadeSegurada",
                "code": "SM-02",
                "title": "Qual e a categoria predominante da segurada neste caso?",
                "help": "Escolha a categoria principal para seguir com a triagem especifica.",
                "options": [
                    {
                        "label": "CLT / empregada",
                        "description": "Empregada urbana, rural ou domestica com vinculo formal.",
                        "next": "cltVinculo",
                    },
                    {
                        "label": "MEI",
                        "description": "Microempreendedora individual.",
                        "next": "meiContribuicao",
                    },
                    {
                        "label": "Autonoma / Facultativa",
                        "description": "Contribuinte individual ou segurada facultativa.",
                        "next": "autonomaCarencia",
                    },
                    {
                        "label": "Segurada especial rural",
                        "description": "Trabalhadora rural em regime de economia familiar ou equiparada.",
                        "next": "ruralAtividade",
                    },
                    {
                        "label": "Desempregada",
                        "description": "Sem vinculo atual, possivelmente em periodo de graca.",
                        "next": "desempregadaPeriodoGraca",
                    },
                    {
                        "label": "Nao identificado",
                        "description": "Ainda nao foi possivel identificar a categoria.",
                        "result": "desqualificadoSemQualidade",
                    },
                ],
            },
            "cltVinculo": {
                "id": "cltVinculo",
                "code": "SM-03",
                "title": "Ha vinculo de emprego ativo ou afastamento coberto na data do fato gerador?",
                "help": "Para CLT, o foco inicial e confirmar o vinculo e a condicao de segurada.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha vinculo formal ou situacao equivalente coberta.",
                        "next": "cltDocumentos",
                    },
                    {
                        "label": "Parcial",
                        "description": "Precisa revisar carteira, eSocial, afastamento ou datas.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha vinculo coberto identificado para a data.",
                        "result": "desqualificadoSemQualidade",
                    },
                ],
            },
            "cltDocumentos": {
                "id": "cltDocumentos",
                "code": "SM-04",
                "title": "Os documentos basicos do evento e do vinculo estao disponiveis?",
                "help": "Ex.: certidao, atestado, carteira, holerite, dados do empregador ou CNIS.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha base documental suficiente para seguir.",
                        "result": "qualificadoSalarioMaternidade",
                    },
                    {
                        "label": "Parcial",
                        "description": "Faltam documentos simples de complementar.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha base documental minima.",
                        "result": "revisaoDocumentalSM",
                    },
                ],
            },
            "meiContribuicao": {
                "id": "meiContribuicao",
                "code": "SM-05",
                "title": "O MEI possui contribuicoes e regularidade suficientes para a analise inicial?",
                "help": "Aqui vale olhar DAS pagos, CNIS e eventual complemento de contribuicao.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha base contributiva minima e categoria confirmada.",
                        "next": "meiDocumentos",
                    },
                    {
                        "label": "Parcial",
                        "description": "Precisa revisar pagamentos ou qualidade de segurada.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha regularidade minima identificada.",
                        "result": "desqualificadoCarencia",
                    },
                ],
            },
            "meiDocumentos": {
                "id": "meiDocumentos",
                "code": "SM-06",
                "title": "Os documentos do evento e das contribuicoes estao disponiveis?",
                "help": "Ex.: certidao, CNIS, DAS, comprovantes e dados cadastrais.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Documentacao suficiente para seguir com o pedido.",
                        "result": "qualificadoSalarioMaternidade",
                    },
                    {
                        "label": "Parcial",
                        "description": "Ha potencial, mas faltam comprovantes.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha prova minima do caso.",
                        "result": "revisaoDocumentalSM",
                    },
                ],
            },
            "autonomaCarencia": {
                "id": "autonomaCarencia",
                "code": "SM-07",
                "title": "A autonoma ou facultativa aparenta cumprir a carencia e a qualidade de segurada?",
                "help": "Considere as contribuicoes recentes, o CNIS e a data do fato gerador.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha contribuicoes suficientes e segurada identificada.",
                        "next": "autonomaDocumentos",
                    },
                    {
                        "label": "Parcial",
                        "description": "Precisa revisar contribuicoes, lacunas ou datas.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha indicio suficiente de carencia ou qualidade.",
                        "result": "desqualificadoCarencia",
                    },
                ],
            },
            "autonomaDocumentos": {
                "id": "autonomaDocumentos",
                "code": "SM-08",
                "title": "Ha documentos do evento e das contribuicoes para protocolo?",
                "help": "Ex.: certidao, atestado, GPS, CNIS e comprovantes de recolhimento.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Documentacao consistente para seguir.",
                        "result": "qualificadoSalarioMaternidade",
                    },
                    {
                        "label": "Parcial",
                        "description": "Faltam guias ou comprovantes importantes.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha base documental minima.",
                        "result": "revisaoDocumentalSM",
                    },
                ],
            },
            "ruralAtividade": {
                "id": "ruralAtividade",
                "code": "SM-09",
                "title": "Ha prova da atividade rural no periodo exigido?",
                "help": "Busque inicio de prova material e coerencia com a narrativa do caso.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha indicios consistentes de atividade rural.",
                        "next": "ruralDocumentos",
                    },
                    {
                        "label": "Parcial",
                        "description": "Existe alguma prova, mas ainda fraca ou incompleta.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha prova suficiente da atividade rural.",
                        "result": "desqualificadoSemQualidade",
                    },
                ],
            },
            "ruralDocumentos": {
                "id": "ruralDocumentos",
                "code": "SM-10",
                "title": "Os documentos do evento e da atividade rural estao organizados?",
                "help": "Ex.: certidao, declaracoes, notas, cadastro rural, documentos familiares e afins.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha conjunto documental razoavel para seguir.",
                        "result": "qualificadoSalarioMaternidade",
                    },
                    {
                        "label": "Parcial",
                        "description": "Precisa reforcar a prova material.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha base documental minima.",
                        "result": "revisaoDocumentalSM",
                    },
                ],
            },
            "desempregadaPeriodoGraca": {
                "id": "desempregadaPeriodoGraca",
                "code": "SM-11",
                "title": "A desempregada aparenta estar no periodo de graca ou manter qualidade de segurada?",
                "help": "Revise data da ultima contribuicao, ultima demissao e possiveis prorrogacoes.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha indicio razoavel de manutencao da qualidade de segurada.",
                        "next": "desempregadaContribuicoes",
                    },
                    {
                        "label": "Parcial",
                        "description": "Precisa revisar CNIS, desligamento e datas com cuidado.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Nao ha indicio suficiente de periodo de graca aplicavel.",
                        "result": "desqualificadoSemQualidade",
                    },
                ],
            },
            "desempregadaContribuicoes": {
                "id": "desempregadaContribuicoes",
                "code": "SM-12",
                "title": "As contribuicoes anteriores e os documentos do evento estao disponiveis?",
                "help": "Ex.: CNIS, rescisao, carteira, certidao ou atestado conforme o caso.",
                "options": [
                    {
                        "label": "Sim",
                        "description": "Ha base documental para seguir com a analise.",
                        "result": "qualificadoSalarioMaternidade",
                    },
                    {
                        "label": "Parcial",
                        "description": "Ha potencial, mas faltam documentos para fechar a tese.",
                        "result": "revisaoDocumentalSM",
                    },
                    {
                        "label": "Nao",
                        "description": "Ainda nao ha documentos suficientes.",
                        "result": "revisaoDocumentalSM",
                    },
                ],
            },
        },
        "results": {
            "qualificadoSalarioMaternidade": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de Salario-Maternidade",
                "summary": (
                    "Ha evento gerador compativel, indicios de qualidade de segurada e base documental "
                    "inicial para prosseguir."
                ),
                "next_step": "Encaminhar para conferencia documental, calculo e protocolo do pedido.",
            },
            "revisaoDocumentalSM": {
                "status": "revisao",
                "title": "Caso com potencial, mas dependente de revisao documental",
                "summary": (
                    "O fluxo indica viabilidade, porem ainda e preciso confirmar categoria, carencia "
                    "ou documentos do evento gerador."
                ),
                "next_step": "Solicitar documentos faltantes e refazer a validacao antes do fechamento.",
            },
            "desqualificadoSemEvento": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de evento gerador compativel",
                "summary": "Nao foi identificado parto, adocao, guarda judicial ou outra hipotese valida.",
                "next_step": "Encerrar com orientacao ou verificar se o caso se encaixa em outro fluxo.",
            },
            "desqualificadoSemQualidade": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de qualidade de segurada identificavel",
                "summary": "Sem vinculo, categoria ou base contributiva minima, o beneficio perde aderencia.",
                "next_step": "Encerrar ou revisar apenas se surgirem novos documentos.",
            },
            "desqualificadoCarencia": {
                "status": "desqualificado",
                "title": "Desqualificado por carencia aparentemente insuficiente",
                "summary": "Na triagem inicial, os recolhimentos ou requisitos minimos nao parecem atendidos.",
                "next_step": "Reavaliar somente se houver documentos que alterem a analise.",
            },
        },
    },
    "auxilioDoenca": {
        "id": "auxilioDoenca",
        "name": "Auxilio-Doenca",
        "start": "incapacidadeTemporaria",
        "nodes": {
            "incapacidadeTemporaria": {
                "id": "incapacidadeTemporaria",
                "code": "AD-01",
                "title": "Ha incapacidade temporaria para o trabalho ou atividade habitual?",
                "help": "Este fluxo cobre beneficio por incapacidade temporaria.",
                "options": [
                    {"label": "Sim", "description": "Ha indicio de incapacidade temporaria.", "next": "qualidadeSeguradaAD"},
                    {"label": "Nao", "description": "Nao ha incapacidade temporaria identificavel.", "result": "desqualificadoSemIncapacidadeAD"},
                ],
            },
            "qualidadeSeguradaAD": {
                "id": "qualidadeSeguradaAD",
                "code": "AD-02",
                "title": "A pessoa aparenta manter qualidade de segurada e carencia quando exigivel?",
                "help": "Considere CNIS, vinculo, recolhimentos e periodo de graca.",
                "options": [
                    {"label": "Sim", "description": "Ha base previdenciaria minima.", "next": "documentosAD"},
                    {"label": "Parcial", "description": "Precisa revisar contribuicoes ou datas.", "result": "revisaoDocumentalAD"},
                    {"label": "Nao", "description": "Nao ha base minima identificada.", "result": "desqualificadoSemQualidadeAD"},
                ],
            },
            "documentosAD": {
                "id": "documentosAD",
                "code": "AD-03",
                "title": "Ha laudos, atestados e documentos medicos suficientes para analise inicial?",
                "help": "Atestados, exames, relatorios e historico de afastamento ajudam a sustentar o caso.",
                "options": [
                    {"label": "Sim", "description": "Documentacao inicial suficiente.", "result": "qualificadoAuxilioDoenca"},
                    {"label": "Parcial", "description": "Faltam documentos medicos relevantes.", "result": "revisaoDocumentalAD"},
                    {"label": "Nao", "description": "Ainda nao ha base documental minima.", "result": "revisaoDocumentalAD"},
                ],
            },
        },
        "results": {
            "qualificadoAuxilioDoenca": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de Auxilio-Doenca",
                "summary": "Ha incapacidade temporaria, base previdenciaria inicial e documentos medicos aproveitaveis.",
                "next_step": "Encaminhar para conferencia documental e preparacao do pedido.",
            },
            "revisaoDocumentalAD": {
                "status": "revisao",
                "title": "Caso depende de revisao medica e documental",
                "summary": "O caso pode ser viavel, mas precisa reforco em laudos, atestados ou base contributiva.",
                "next_step": "Solicitar documentos e refazer a triagem.",
            },
            "desqualificadoSemIncapacidadeAD": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de incapacidade temporaria identificavel",
                "summary": "A triagem inicial nao mostrou incapacidade temporaria compativel.",
                "next_step": "Encerrar ou revisar outro fluxo compativel.",
            },
            "desqualificadoSemQualidadeAD": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de qualidade de segurado ou carencia",
                "summary": "Nao houve base previdenciaria minima na analise inicial.",
                "next_step": "Encerrar ou revisar somente com novos documentos.",
            },
        },
    },
    "aposentadoriaInvalidez": {
        "id": "aposentadoriaInvalidez",
        "name": "Aposentadoria por Invalidez",
        "start": "incapacidadePermanente",
        "nodes": {
            "incapacidadePermanente": {
                "id": "incapacidadePermanente",
                "code": "AI-01",
                "title": "Ha indicio de incapacidade total e permanente para o trabalho?",
                "help": "Fluxo voltado ao beneficio por incapacidade permanente.",
                "options": [
                    {"label": "Sim", "description": "Ha indicio de incapacidade total e permanente.", "next": "qualidadeSeguradaAI"},
                    {"label": "Parcial", "description": "Ha incapacidade, mas ainda sem permanencia clara.", "result": "revisaoDocumentalAI"},
                    {"label": "Nao", "description": "Nao ha incapacidade permanente identificavel.", "result": "desqualificadoSemIncapacidadeAI"},
                ],
            },
            "qualidadeSeguradaAI": {
                "id": "qualidadeSeguradaAI",
                "code": "AI-02",
                "title": "A pessoa aparenta manter qualidade de segurada e carencia quando exigivel?",
                "help": "Considere vinculos, contribuicoes e periodo de graca.",
                "options": [
                    {"label": "Sim", "description": "Ha base previdenciaria minima.", "next": "documentosAI"},
                    {"label": "Parcial", "description": "Precisa revisar historico contributivo.", "result": "revisaoDocumentalAI"},
                    {"label": "Nao", "description": "Nao ha base previdenciaria minima.", "result": "desqualificadoSemQualidadeAI"},
                ],
            },
            "documentosAI": {
                "id": "documentosAI",
                "code": "AI-03",
                "title": "Ha laudos robustos, exames e historico medico suficientes para o caso?",
                "help": "Quanto mais robusta a prova medica, melhor a chance de enquadramento.",
                "options": [
                    {"label": "Sim", "description": "Ha base documental forte.", "result": "qualificadoAposentadoriaInvalidez"},
                    {"label": "Parcial", "description": "Faltam laudos ou relatorios essenciais.", "result": "revisaoDocumentalAI"},
                    {"label": "Nao", "description": "Ainda nao ha prova medica minima.", "result": "revisaoDocumentalAI"},
                ],
            },
        },
        "results": {
            "qualificadoAposentadoriaInvalidez": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de incapacidade permanente",
                "summary": "Ha indicio de incapacidade total e permanente com base contributiva e medica inicial.",
                "next_step": "Encaminhar para analise juridica e pericial.",
            },
            "revisaoDocumentalAI": {
                "status": "revisao",
                "title": "Caso depende de consolidacao medica e documental",
                "summary": "Existe potencial, mas a permanencia da incapacidade ou a base previdenciaria ainda exigem revisao.",
                "next_step": "Solicitar laudos, exames e historico previdenciario.",
            },
            "desqualificadoSemIncapacidadeAI": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de incapacidade permanente identificavel",
                "summary": "A triagem inicial nao mostrou quadro compativel com incapacidade permanente.",
                "next_step": "Revisar outro fluxo, se houver aderencia.",
            },
            "desqualificadoSemQualidadeAI": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de qualidade de segurado ou carencia",
                "summary": "Nao houve base previdenciaria minima na analise inicial.",
                "next_step": "Encerrar ou revisar com novos documentos.",
            },
        },
    },
    "pensaoMorte": {
        "id": "pensaoMorte",
        "name": "Pensao por Morte",
        "start": "obito",
        "nodes": {
            "obito": {
                "id": "obito",
                "code": "PM-01",
                "title": "Ha obito comprovado do segurado ou instituidor?",
                "help": "Fluxo inicial para pensao por morte.",
                "options": [
                    {"label": "Sim", "description": "Ha certidao ou prova do obito.", "next": "dependencia"},
                    {"label": "Nao", "description": "Nao ha obito comprovado.", "result": "desqualificadoSemObitoPM"},
                ],
            },
            "dependencia": {
                "id": "dependencia",
                "code": "PM-02",
                "title": "Ha dependencia economica presumida ou comprovavel do requerente?",
                "help": "Considere conjuge, companheiro, filho, menor tutelado e demais dependentes.",
                "options": [
                    {"label": "Sim", "description": "Ha dependencia presumida ou comprovavel.", "next": "qualidadeInstituidor"},
                    {"label": "Parcial", "description": "Dependencia existe, mas precisa de prova.", "result": "revisaoDocumentalPM"},
                    {"label": "Nao", "description": "Nao ha dependencia identificavel.", "result": "desqualificadoSemDependenciaPM"},
                ],
            },
            "qualidadeInstituidor": {
                "id": "qualidadeInstituidor",
                "code": "PM-03",
                "title": "O falecido aparenta ter qualidade de segurado ou direito adquirido relacionado ao beneficio?",
                "help": "Considere contribuicoes, vinculos e situacoes de manutencao da qualidade.",
                "options": [
                    {"label": "Sim", "description": "Ha base previdenciaria do instituidor.", "result": "qualificadoPensaoMorte"},
                    {"label": "Parcial", "description": "Precisa revisar CNIS, vinculos ou periodo de graca.", "result": "revisaoDocumentalPM"},
                    {"label": "Nao", "description": "Nao ha base minima do instituidor.", "result": "desqualificadoSemQualidadePM"},
                ],
            },
        },
        "results": {
            "qualificadoPensaoMorte": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de Pensao por Morte",
                "summary": "Ha obito, dependencia e base previdenciaria inicial do instituidor.",
                "next_step": "Encaminhar para checklist documental e protocolo.",
            },
            "revisaoDocumentalPM": {
                "status": "revisao",
                "title": "Caso depende de revisao de dependencia e qualidade do instituidor",
                "summary": "O caso pode ser viavel, mas exige documentos complementares.",
                "next_step": "Solicitar certidoes, uniao estavel, CNIS e demais provas.",
            },
            "desqualificadoSemObitoPM": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de obito comprovado",
                "summary": "Sem prova do obito, o fluxo nao se sustenta.",
                "next_step": "Encerrar ou aguardar documentacao minima.",
            },
            "desqualificadoSemDependenciaPM": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de dependencia identificavel",
                "summary": "Nao foi identificada dependencia economica presumida ou comprovavel.",
                "next_step": "Encerrar ou revisar somente com novas provas.",
            },
            "desqualificadoSemQualidadePM": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de qualidade de segurado do instituidor",
                "summary": "Nao houve base previdenciaria minima do falecido na triagem inicial.",
                "next_step": "Encerrar ou revisar com novos documentos.",
            },
        },
    },
    "auxilioReclusao": {
        "id": "auxilioReclusao",
        "name": "Auxilio-Reclusao",
        "start": "prisao",
        "nodes": {
            "prisao": {
                "id": "prisao",
                "code": "AR-01",
                "title": "Ha prisao em regime compativel com a analise do beneficio?",
                "help": "Fluxo inicial do auxilio-reclusao.",
                "options": [
                    {"label": "Sim", "description": "Ha encarceramento compativel com o fluxo.", "next": "dependentesAR"},
                    {"label": "Nao", "description": "Nao ha situacao de prisao compativel identificada.", "result": "desqualificadoSemPrisaoAR"},
                ],
            },
            "dependentesAR": {
                "id": "dependentesAR",
                "code": "AR-02",
                "title": "Ha dependentes com legitimidade para requerer o beneficio?",
                "help": "Considere dependentes previdenciarios do segurado recolhido.",
                "options": [
                    {"label": "Sim", "description": "Ha dependentes identificados.", "next": "qualidadeSeguradoAR"},
                    {"label": "Parcial", "description": "Dependencia precisa de prova complementar.", "result": "revisaoDocumentalAR"},
                    {"label": "Nao", "description": "Nao ha dependentes identificaveis.", "result": "desqualificadoSemDependentesAR"},
                ],
            },
            "qualidadeSeguradoAR": {
                "id": "qualidadeSeguradoAR",
                "code": "AR-03",
                "title": "O segurado recolhido aparenta manter qualidade de segurado e preencher os requisitos economicos aplicaveis?",
                "help": "Considere CNIS, vinculo, contribuicoes e enquadramento legal vigente.",
                "options": [
                    {"label": "Sim", "description": "Ha base inicial para o beneficio.", "result": "qualificadoAuxilioReclusao"},
                    {"label": "Parcial", "description": "Precisa revisar base contributiva e documentos.", "result": "revisaoDocumentalAR"},
                    {"label": "Nao", "description": "Nao ha base minima para o beneficio.", "result": "desqualificadoSemQualidadeAR"},
                ],
            },
        },
        "results": {
            "qualificadoAuxilioReclusao": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de Auxilio-Reclusao",
                "summary": "Ha prisao compativel, dependentes e base previdenciaria inicial.",
                "next_step": "Encaminhar para conferencia documental e protocolo.",
            },
            "revisaoDocumentalAR": {
                "status": "revisao",
                "title": "Caso depende de revisao documental do auxilio-reclusao",
                "summary": "O fluxo indica potencial, mas faltam provas sobre dependencia, prisao ou qualidade de segurado.",
                "next_step": "Solicitar documentos e reavaliar.",
            },
            "desqualificadoSemPrisaoAR": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de prisao compativel",
                "summary": "Nao foi identificada situacao de prisao apta ao fluxo inicial.",
                "next_step": "Encerrar ou revisar se houver novos dados.",
            },
            "desqualificadoSemDependentesAR": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de dependentes legitimados",
                "summary": "Nao ha dependentes identificados para requerer o beneficio.",
                "next_step": "Encerrar ou revisar somente com novas provas.",
            },
            "desqualificadoSemQualidadeAR": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de qualidade de segurado ou requisitos aplicaveis",
                "summary": "Nao houve base minima previdenciaria na triagem inicial.",
                "next_step": "Encerrar ou revisar com novos documentos.",
            },
        },
    },
    "revisaoBeneficio": {
        "id": "revisaoBeneficio",
        "name": "Revisao de Beneficio",
        "start": "beneficioAtivo",
        "nodes": {
            "beneficioAtivo": {
                "id": "beneficioAtivo",
                "code": "RB-01",
                "title": "Ja existe beneficio concedido ou indeferido a ser revisado?",
                "help": "Fluxo para revisar concessao, valor, tempo ou indeferimento com estrategia especifica.",
                "options": [
                    {"label": "Sim", "description": "Ha ato ou beneficio a revisar.", "next": "motivoRevisao"},
                    {"label": "Nao", "description": "Nao ha beneficio ou ato identificavel para revisao.", "result": "desqualificadoSemObjetoRB"},
                ],
            },
            "motivoRevisao": {
                "id": "motivoRevisao",
                "code": "RB-02",
                "title": "Ha um motivo concreto de revisao identificado?",
                "help": "Ex.: erro de calculo, tempo nao computado, atividade especial, documentos novos ou revisao do indeferimento.",
                "options": [
                    {"label": "Sim", "description": "Ha tese inicial de revisao.", "next": "documentosRB"},
                    {"label": "Parcial", "description": "Existe suspeita, mas sem tese bem fechada.", "result": "revisaoDocumentalRB"},
                    {"label": "Nao", "description": "Nao ha motivo concreto identificado.", "result": "desqualificadoSemTeseRB"},
                ],
            },
            "documentosRB": {
                "id": "documentosRB",
                "code": "RB-03",
                "title": "Ha carta de concessao, processo, memoria de calculo ou documentos para revisar o caso?",
                "help": "Esses documentos sao chave para validar uma revisao com seguranca.",
                "options": [
                    {"label": "Sim", "description": "Ha documentos suficientes para analise inicial.", "result": "qualificadoRevisaoBeneficio"},
                    {"label": "Parcial", "description": "Faltam documentos importantes.", "result": "revisaoDocumentalRB"},
                    {"label": "Nao", "description": "Nao ha base documental minima.", "result": "revisaoDocumentalRB"},
                ],
            },
        },
        "results": {
            "qualificadoRevisaoBeneficio": {
                "status": "aprovado",
                "title": "Lead qualificado para analise de revisao de beneficio",
                "summary": "Ha objeto de revisao, tese inicial e documentos relevantes para conferencia.",
                "next_step": "Encaminhar para auditoria previdenciaria e calculo revisional.",
            },
            "revisaoDocumentalRB": {
                "status": "revisao",
                "title": "Caso depende de documentos para revisao previdenciaria",
                "summary": "Ha potencial de revisao, mas os documentos ainda estao incompletos.",
                "next_step": "Solicitar processo, carta, memoria e documentos faltantes.",
            },
            "desqualificadoSemObjetoRB": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de beneficio ou ato a revisar",
                "summary": "Nao foi identificado objeto concreto de revisao.",
                "next_step": "Encerrar ou redirecionar para outro fluxo.",
            },
            "desqualificadoSemTeseRB": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de tese inicial de revisao",
                "summary": "Nao foi identificado motivo concreto para revisar o beneficio na triagem inicial.",
                "next_step": "Encerrar ou revisar somente com novos elementos.",
            },
        },
    },
    "planejamentoPrevidenciario": {
        "id": "planejamentoPrevidenciario",
        "name": "Planejamento Previdenciario",
        "start": "historicoContributivoPP",
        "nodes": {
            "historicoContributivoPP": {
                "id": "historicoContributivoPP",
                "code": "PP-01",
                "title": "O lead possui historico contributivo ou documental suficiente para planejamento?",
                "help": "Fluxo para quem quer organizar estrategia futura ou validar melhor beneficio.",
                "options": [
                    {"label": "Sim", "description": "Ha CNIS, carteiras ou historico aproveitavel.", "next": "objetivoPP"},
                    {"label": "Parcial", "description": "Ha alguma base, mas ainda incompleta.", "result": "revisaoDocumentalPP"},
                    {"label": "Nao", "description": "Nao ha base minima para planejamento serio.", "result": "desqualificadoSemBasePP"},
                ],
            },
            "objetivoPP": {
                "id": "objetivoPP",
                "code": "PP-02",
                "title": "O objetivo do planejamento esta minimamente claro?",
                "help": "Ex.: melhor aposentadoria, organizacao de contribuicoes, averbacoes ou estrategia PCD/especial.",
                "options": [
                    {"label": "Sim", "description": "Ha objetivo definido.", "next": "documentosPP"},
                    {"label": "Parcial", "description": "Ha duvida, mas o caso ainda e aproveitavel.", "result": "revisaoDocumentalPP"},
                    {"label": "Nao", "description": "Nao ha objetivo minimamente claro.", "result": "desqualificadoSemObjetivoPP"},
                ],
            },
            "documentosPP": {
                "id": "documentosPP",
                "code": "PP-03",
                "title": "O lead consegue apresentar documentos para calculo e estrategia?",
                "help": "Quanto melhor a base documental, mais confiavel o planejamento.",
                "options": [
                    {"label": "Sim", "description": "Ha documentos suficientes para iniciar.", "result": "qualificadoPlanejamento"},
                    {"label": "Parcial", "description": "Faltam documentos, mas o caso e viavel.", "result": "revisaoDocumentalPP"},
                    {"label": "Nao", "description": "Ainda nao ha base documental minima.", "result": "revisaoDocumentalPP"},
                ],
            },
        },
        "results": {
            "qualificadoPlanejamento": {
                "status": "aprovado",
                "title": "Lead qualificado para planejamento previdenciario",
                "summary": "Ha base contributiva, objetivo minimamente claro e documentos iniciais para estrategia.",
                "next_step": "Encaminhar para calculo e construcao do planejamento.",
            },
            "revisaoDocumentalPP": {
                "status": "revisao",
                "title": "Caso depende de consolidacao documental para planejamento",
                "summary": "O lead tem potencial, mas ainda faltam documentos ou definicao do objetivo.",
                "next_step": "Solicitar CNIS, carteira e demais documentos relevantes.",
            },
            "desqualificadoSemBasePP": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de base contributiva minima",
                "summary": "Nao ha material suficiente para planejamento previdenciario inicial.",
                "next_step": "Encerrar ou orientar sobre coleta de documentos.",
            },
            "desqualificadoSemObjetivoPP": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de objetivo minimamente definido",
                "summary": "Sem objetivo claro, o planejamento nao ganha forma suficiente para a triagem.",
                "next_step": "Encerrar ou orientar retorno com objetivo definido.",
            },
        },
    },
    "outrosAssuntos": {
        "id": "outrosAssuntos",
        "name": "Outros Assuntos",
        "start": "temaIdentificado",
        "nodes": {
            "temaIdentificado": {
                "id": "temaIdentificado",
                "code": "OA-01",
                "title": "O lead conseguiu explicar minimamente qual assunto deseja tratar?",
                "help": "Fluxo guarda-chuva para nao perder leads fora dos roteiros principais.",
                "options": [
                    {"label": "Sim", "description": "Ha assunto identificavel.", "next": "aderenciaJuridica"},
                    {"label": "Parcial", "description": "O assunto ainda esta confuso.", "result": "revisaoOutrosAssuntos"},
                    {"label": "Nao", "description": "Nao foi possivel identificar o tema.", "result": "desqualificadoSemTemaOA"},
                ],
            },
            "aderenciaJuridica": {
                "id": "aderenciaJuridica",
                "code": "OA-02",
                "title": "O tema aparenta ter aderencia previdenciaria ou juridica para atendimento?",
                "help": "Serve para separar curiosidade geral de oportunidade real de analise.",
                "options": [
                    {"label": "Sim", "description": "Ha aderencia para atendimento humano.", "result": "qualificadoOutrosAssuntos"},
                    {"label": "Parcial", "description": "Pode haver aderencia, mas precisa de triagem humana.", "result": "revisaoOutrosAssuntos"},
                    {"label": "Nao", "description": "Nao ha aderencia suficiente ao escopo.", "result": "desqualificadoSemAderenciaOA"},
                ],
            },
        },
        "results": {
            "qualificadoOutrosAssuntos": {
                "status": "aprovado",
                "title": "Lead qualificado para triagem humana em outros assuntos",
                "summary": "O tema foi identificado e aparenta ter aderencia para atendimento especializado.",
                "next_step": "Encaminhar para avaliacao humana e definicao do fluxo correto.",
            },
            "revisaoOutrosAssuntos": {
                "status": "revisao",
                "title": "Caso precisa de esclarecimento adicional",
                "summary": "O lead trouxe um tema potencial, mas ainda confuso ou incompleto.",
                "next_step": "Solicitar mais contexto e direcionar para triagem humana.",
            },
            "desqualificadoSemTemaOA": {
                "status": "desqualificado",
                "title": "Desqualificado por ausencia de tema identificavel",
                "summary": "Nao foi possivel entender o assunto do lead na triagem inicial.",
                "next_step": "Encerrar com empatia e orientar retorno com mais detalhes.",
            },
            "desqualificadoSemAderenciaOA": {
                "status": "desqualificado",
                "title": "Desqualificado por falta de aderencia ao escopo",
                "summary": "O tema informado nao aparenta ter encaixe previdenciario ou juridico no escopo atual.",
                "next_step": "Encerrar ou orientar para outro canal, se aplicavel.",
            },
        },
    },
}
