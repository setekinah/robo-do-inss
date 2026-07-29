window.FLOW_DEFINITIONS = {
  auxilioAcidente: {
    id: "auxilioAcidente",
    name: "Auxílio-Acidente",
    start: "vinculo",
    nodes: {
      vinculo: {
        id: "vinculo",
        code: "AA-01",
        title: "O lead possui vínculo previdenciário ou histórico que indique cobertura do INSS?",
        help: "Primeira triagem do fluxo. Sem vínculo ou sem histórico aproveitável, o caso tende a perder aderência.",
        options: [
          { label: "Sim", description: "Existe vínculo ou contribuição relevante.", next: "acidente" },
          { label: "Não", description: "Não há vínculo aproveitável.", result: "desqualificadoSemVinculo" }
        ]
      },
      acidente: {
        id: "acidente",
        code: "AA-02",
        title: "Houve acidente ou doença ocupacional relacionada à atividade profissional?",
        help: "Se não houve acidente ou se a situação não se conecta ao trabalho/atividade, a estratégia costuma mudar.",
        options: [
          { label: "Sim", description: "Existe acidente ou nexo ocupacional.", next: "sequela" },
          { label: "Não", description: "Não há acidente ou nexo ocupacional claro.", result: "desqualificadoSemAcidente" }
        ]
      },
      sequela: {
        id: "sequela",
        code: "AA-03",
        title: "Ficou uma sequela permanente que reduziu a capacidade para a atividade habitual?",
        help: "Este é o coração do auxílio-acidente. Sem redução permanente da capacidade, o enquadramento enfraquece.",
        options: [
          { label: "Sim", description: "Há sequela consolidada com redução funcional.", next: "afastamento" },
          { label: "Não", description: "Não houve sequela permanente comprovável.", result: "desqualificadoSemSequela" }
        ]
      },
      afastamento: {
        id: "afastamento",
        code: "AA-04",
        title: "Houve afastamento, benefício por incapacidade ou documentação médica relevante?",
        help: "A documentação de afastamento, laudos, exames e histórico do INSS fortalece a validação final.",
        options: [
          { label: "Sim", description: "Há documentos e histórico aproveitáveis.", result: "qualificadoAuxilioAcidente" },
          { label: "Parcial", description: "Existe algo, mas o material ainda está incompleto.", result: "revisaoDocumentalAA" },
          { label: "Não", description: "Ainda não há documentação mínima.", result: "revisaoDocumentalAA" }
        ]
      }
    },
    results: {
      qualificadoAuxilioAcidente: {
        status: "aprovado",
        title: "Lead qualificado para análise de Auxílio-Acidente",
        summary: "Há sinais de vínculo, acidente/doença ocupacional, sequela permanente e base documental inicial.",
        nextStep: "Encaminhar para advogado ou equipe jurídica com checklist documental e agendamento."
      },
      revisaoDocumentalAA: {
        status: "revisao",
        title: "Caso promissor, mas precisa reforço documental",
        summary: "O fluxo indica potencial, porém faltam laudos, CAT, exames, CNIS ou histórico robusto.",
        nextStep: "Solicitar documentos, completar cadastro e reavaliar antes do fechamento."
      },
      desqualificadoSemVinculo: {
        status: "desqualificado",
        title: "Desqualificado por ausência de vínculo previdenciário útil",
        summary: "Sem base previdenciária mínima, o fluxo perde aderência para este benefício.",
        nextStep: "Encerrar com empatia ou redirecionar para outro fluxo."
      },
      desqualificadoSemAcidente: {
        status: "desqualificado",
        title: "Desqualificado por falta de acidente ou nexo ocupacional",
        summary: "O caso não se alinha ao critério central do auxílio-acidente.",
        nextStep: "Avaliar se o lead se enquadra em outro atendimento."
      },
      desqualificadoSemSequela: {
        status: "desqualificado",
        title: "Desqualificado por ausência de sequela permanente",
        summary: "Sem redução permanente da capacidade habitual, o benefício tende a não encaixar.",
        nextStep: "Encerrar ou migrar para outro fluxo se houver aderência."
      }
    }
  },
  aposentadoria: {
    id: "aposentadoria",
    name: "Aposentadoria",
    start: "contribuicao",
    nodes: {
      contribuicao: {
        id: "contribuicao",
        code: "AP-01",
        title: "O lead possui histórico contributivo ou tempo de serviço identificável?",
        help: "Pode vir de carteira, CNIS, atividade rural, serviço público, especial ou outros vínculos.",
        options: [
          { label: "Sim", description: "Existe tempo a apurar ou averbar.", next: "perfil" },
          { label: "Não", description: "Ainda não há base contributiva conhecida.", result: "desqualificadoSemTempo" }
        ]
      },
      perfil: {
        id: "perfil",
        code: "AP-02",
        title: "Qual é o perfil predominante do caso?",
        help: "Escolha o cenário mais forte para orientar o próximo bloco de análise.",
        options: [
          { label: "Comum", description: "Tempo urbano/comum predominante.", next: "idadeTempo" },
          { label: "PCD", description: "Possui possível enquadramento como pessoa com deficiência.", next: "pcd" },
          { label: "Especial", description: "Há exposição especial ou atividade nociva.", next: "especial" }
        ]
      },
      idadeTempo: {
        id: "idadeTempo",
        code: "AP-03",
        title: "A soma atual de idade, tempo e carência já sugere viabilidade de aposentadoria?",
        help: "Esta etapa aproxima a lógica dos pontos, idade mínima e carência do fluxo visual enviado.",
        options: [
          { label: "Sim", description: "Há forte sinal de direito já amadurecido.", next: "documentosApo" },
          { label: "Quase", description: "Está perto, mas depende de acertos ou averbações.", result: "revisaoPlanejamento" },
          { label: "Não", description: "Ainda está distante do requisito mínimo.", result: "desqualificadoSemRequisitos" }
        ]
      },
      pcd: {
        id: "pcd",
        code: "AP-04",
        title: "Existe documentação ou histórico consistente para aposentadoria da PCD?",
        help: "Aqui entram laudos, período da deficiência e documentação médica mínima.",
        options: [
          { label: "Sim", description: "Há base para seguir no fluxo PCD.", next: "documentosApo" },
          { label: "Parcial", description: "Existe indício, mas falta prova consistente.", result: "revisaoPlanejamento" },
          { label: "Não", description: "Sem prova mínima da deficiência no período.", result: "desqualificadoSemRequisitos" }
        ]
      },
      especial: {
        id: "especial",
        code: "AP-05",
        title: "Há PPP, LTCAT ou outra prova de atividade especial?",
        help: "Aposentadoria especial ou conversão de tempo depende fortemente de prova técnica.",
        options: [
          { label: "Sim", description: "Existe documentação técnica relevante.", next: "documentosApo" },
          { label: "Parcial", description: "Alguma prova existe, mas precisa consolidar.", result: "revisaoPlanejamento" },
          { label: "Não", description: "Sem prova técnica suficiente.", result: "desqualificadoSemRequisitos" }
        ]
      },
      documentosApo: {
        id: "documentosApo",
        code: "AP-06",
        title: "O lead consegue apresentar documentos para cálculo e protocolo?",
        help: "CNIS, carteira, PPP, laudos, certidões e outros documentos sustentam a entrada do caso.",
        options: [
          { label: "Sim", description: "Documentação suficiente para avançar.", result: "qualificadoAposentadoria" },
          { label: "Parcial", description: "Documentos incompletos, mas recuperáveis.", result: "revisaoPlanejamento" },
          { label: "Não", description: "Ainda sem material para cálculo sério.", result: "revisaoPlanejamento" }
        ]
      }
    },
    results: {
      qualificadoAposentadoria: {
        status: "aprovado",
        title: "Lead qualificado para análise previdenciária completa",
        summary: "O caso indica possibilidade real de aposentadoria ou planejamento estratégico com base documental.",
        nextStep: "Enviar para cálculo previdenciário, conferência de requisitos e proposta."
      },
      revisaoPlanejamento: {
        status: "revisao",
        title: "Lead em revisão para planejamento e documentação",
        summary: "O caso tem potencial, mas depende de averbações, provas adicionais ou cálculo mais fino.",
        nextStep: "Solicitar documentos, complementar timeline e reavaliar com especialista."
      },
      desqualificadoSemTempo: {
        status: "desqualificado",
        title: "Desqualificado por ausência de histórico contributivo identificável",
        summary: "Sem base mínima de tempo ou contribuição, o fluxo não sustenta análise imediata.",
        nextStep: "Encerrar com orientação inicial ou direcionar para outro benefício."
      },
      desqualificadoSemRequisitos: {
        status: "desqualificado",
        title: "Desqualificado por falta de requisitos atuais",
        summary: "Pelos critérios iniciais, o lead ainda não demonstra encaixe suficiente para este fluxo.",
        nextStep: "Registrar e acompanhar futuramente, se fizer sentido."
      }
    }
  },
  bpcLoas: {
    id: "bpcLoas",
    name: "BPC/LOAS",
    start: "perfilBpc",
    nodes: {
      perfilBpc: {
        id: "perfilBpc",
        code: "BP-01",
        title: "O caso é de idoso 65+ ou de pessoa com deficiência?",
        help: "A primeira divisão do BPC/LOAS separa a via etária da via deficiência.",
        options: [
          { label: "Idoso 65+", description: "Fluxo assistencial etário.", next: "rendaFamiliar" },
          { label: "Pessoa com deficiência", description: "Fluxo assistencial por deficiência.", next: "deficiencia" },
          { label: "Nenhum", description: "Não se encaixa no perfil-base.", result: "desqualificadoPerfilBpc" }
        ]
      },
      deficiencia: {
        id: "deficiencia",
        code: "BP-02",
        title: "Existe impedimento de longo prazo que limite a participação plena na sociedade ou no trabalho?",
        help: "O fluxo visual sugere uma etapa eliminatória forte para deficiência e documentação associada.",
        options: [
          { label: "Sim", description: "Há deficiência de longo prazo.", next: "rendaFamiliar" },
          { label: "Parcial", description: "Há indício, mas a prova ainda é fraca.", result: "revisaoSocioeconomica" },
          { label: "Não", description: "Não há deficiência de longo prazo identificável.", result: "desqualificadoPerfilBpc" }
        ]
      },
      rendaFamiliar: {
        id: "rendaFamiliar",
        code: "BP-03",
        title: "A renda familiar per capita indica hipossuficiência?",
        help: "Aqui entra a validação socioeconômica: renda, composição familiar e despesas relevantes.",
        options: [
          { label: "Sim", description: "A renda sugere enquadramento assistencial.", next: "cadunico" },
          { label: "Limítrofe", description: "Precisa análise social detalhada.", result: "revisaoSocioeconomica" },
          { label: "Não", description: "A renda afasta o enquadramento inicial.", result: "desqualificadoRenda" }
        ]
      },
      cadunico: {
        id: "cadunico",
        code: "BP-04",
        title: "O CadÚnico e a documentação básica estão atualizados?",
        help: "Documento pessoal, comprovantes e CadÚnico atualizado costumam ser etapa-chave do fluxo.",
        options: [
          { label: "Sim", description: "Documentação assistencial pronta.", result: "qualificadoBpc" },
          { label: "Parcial", description: "Faltam atualizações simples.", result: "revisaoSocioeconomica" },
          { label: "Não", description: "Ainda não há base documental suficiente.", result: "revisaoSocioeconomica" }
        ]
      }
    },
    results: {
      qualificadoBpc: {
        status: "aprovado",
        title: "Lead qualificado para protocolo de BPC/LOAS",
        summary: "Há perfil elegível, indício socioeconômico favorável e documentação inicial consistente.",
        nextStep: "Agendar atendimento, conferir documentação final e seguir para protocolo."
      },
      revisaoSocioeconomica: {
        status: "revisao",
        title: "Caso depende de revisão socioeconômica e documental",
        summary: "O benefício pode ser viável, mas precisa de CadÚnico, laudos ou composição familiar mais robusta.",
        nextStep: "Solicitar documentos e refazer a triagem após atualização."
      },
      desqualificadoPerfilBpc: {
        status: "desqualificado",
        title: "Desqualificado por falta de perfil-base do BPC/LOAS",
        summary: "Sem idade mínima ou deficiência de longo prazo, o enquadramento não se sustenta.",
        nextStep: "Redirecionar para outro fluxo compatível, se houver."
      },
      desqualificadoRenda: {
        status: "desqualificado",
        title: "Desqualificado pela renda familiar informada",
        summary: "A triagem inicial não indica hipossuficiência suficiente para este benefício.",
        nextStep: "Encerrar com orientação ou submeter à revisão somente se houver exceções fortes."
      }
    }
  }
};
