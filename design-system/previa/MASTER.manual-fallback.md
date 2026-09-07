# PrevIA — Design System Mestre

Status: fundação visual e de UX para o frontend HTML, CSS e JavaScript vanilla.
Escopo: governança; não altera componentes, fluxos ou regras de negócio.

## 1. Princípios de UX

1. **Clareza operacional antes de decoração.** A próxima decisão, pendência e ação têm precedência visual.
2. **Estado verificável.** A tela só comunica conclusão após confirmação real; carregamento, bloqueio e erro são explícitos.
3. **Segurança compreensível.** Dados sensíveis, acesso privado e limitações técnicas devem ser explicados em linguagem humana.
4. **Densidade com respiro.** Informação jurídica é abundante; agrupamento, hierarquia e escaneabilidade substituem cartões decorativos.
5. **Análise não é decisão jurídica.** Resultados automatizados indicam evidência, origem, confiança e próxima revisão humana.

## 2. Personalidade do produto

PrevIA é uma bancada operacional previdenciária: sóbria, precisa, acolhedora sem ser informal e eficiente sem aparência futurista. A voz é direta e orientada a ação: “2 documentos precisam de validação”, não “IA encontrou algo incrível”.

## 3. Dials de direção

- Design variance: **4/10** — moderno, previsível e sem experimentação visual por tela.
- Motion intensity: **3/10** — transições curtas apenas para continuidade, feedback e foco.
- Visual density: **8/10** — alta densidade organizada para jornada profissional de desktop, com adaptação progressiva em telas menores.

## 4. Hierarquia visual

Ordem obrigatória em telas operacionais:

1. próxima ação e impedimento;
2. estado e responsável do caso;
3. checklist e evidências;
4. análise e indicadores;
5. histórico e contexto;
6. ferramentas secundárias.

Use uma ação primária por contexto. Ações destrutivas, irreversíveis ou que alterem estado devem ser separadas visualmente e pedir confirmação quando necessário.

## 5. Layout e espaçamento

- Layout principal: barra lateral persistente em desktop, área de conteúdo com largura fluida e leitura máxima aproximada de 1440 px.
- Grade: 12 colunas em desktop, 8 em tablet, 4 em mobile; evitar cards estreitos que quebrem nomes, CPF mascarado e status.
- Escala de espaçamento: 4, 8, 12, 16, 24, 32, 48 px. Use 16 px como respiro interno padrão de cards e 24 px entre blocos de trabalho.
- Agrupar por tarefa, não apenas por tipo de dado. Um checklist deve conter sua ação, estado e histórico de versões no mesmo contexto.

## 6. Tokens de cor semânticos

Os tokens são referência para futuras CSS variables; não são instrução para alteração imediata do CSS.

| Papel | Token sugerido | Uso |
| --- | --- | --- |
| Fundo de aplicação | `--surface-canvas: #F6F8FB` | área de trabalho clara e leitura longa |
| Superfície | `--surface-raised: #FFFFFF` | cards, modais e tabelas |
| Texto principal | `--text-primary: #14213D` | títulos e conteúdo crítico |
| Texto secundário | `--text-secondary: #52627A` | contexto e ajuda |
| Borda | `--border-subtle: #D8E0EA` | agrupamento sem ruído |
| Confiança/primário | `--action-primary: #164E8C` | ação principal e navegação ativa |
| Informação | `--state-info: #2563A6` | processamento e contexto |
| Sucesso | `--state-success: #1E7A52` | confirmado/aprovado |
| Atenção | `--state-warning: #A85E00` | pendência e revisão |
| Erro | `--state-danger: #B4233C` | impedimento e rejeição |
| Neutro | `--state-neutral: #667085` | não iniciado/arquivado |
| Acento controlado | `--accent-amber: #B7791F` | sinalização pontual, nunca como cor dominante |

Estados devem combinar cor, rótulo textual e ícone/símbolo. Nunca depender apenas de cor.

## 7. Tipografia

- Fonte primária: uma sans-serif de interface legível (Inter é adequada ao stack atual).
- Fonte de títulos: a mesma família com peso 600–700; evitar serifas decorativas como padrão de aplicação.
- Fonte monoespaçada: apenas para identificadores técnicos, JSON e chaves de auditoria.
- Escala base: 12, 14, 16, 20, 24, 32 px; corpo padrão 14–16 px, linha entre 1.4 e 1.55.
- Números financeiros e datas devem usar alinhamento tabular quando a fonte oferecer esse recurso.

## 8. Cards e superfícies

Cards são contêineres de tarefa, não molduras para toda informação. Cada card tem título, contexto breve, estado e ação quando aplicável. Use borda sutil, raio moderado (8–12 px) e sombra discreta; sem vidro excessivo, brilho neon ou gradiente decorativo.

## 9. Formulários

- Rótulo sempre visível; placeholder é exemplo, não rótulo.
- Exibir obrigatoriedade, formato e ajuda próxima ao campo.
- Validar no momento adequado e preservar a entrada em caso de erro de servidor.
- Erros ficam associados ao campo quando específicos; falhas da operação ficam no contexto do formulário.
- Alvos interativos: mínimo de 40 × 40 px; 44 × 44 px é preferível em touch.

## 10. Botões

- Primário: conclui a ação principal do contexto; máximo um por seção imediata.
- Secundário: ação útil sem competir com a primária.
- Terciário/ícone: ferramentas auxiliares, sempre com rótulo acessível e tooltip quando necessário.
- Perigo: texto explícito (“Excluir versão”), não apenas ícone ou vermelho.
- Loading: conservar largura, desabilitar repetição e explicar a ação em curso.

## 11. Badges, chips e status

Use status curtos e estáveis: `Pendente`, `Recebido`, `Em validação`, `Aprovado`, `Impedido`, `Concluído`. Badges exibem texto e, quando útil, ícone. Chips são filtros/removíveis, não substitutos de navegação nem rótulos de estado crítico.

## 12. Tabelas e listas

- Preferir tabela para comparação de múltiplos registros; usar lista para sequência, histórico ou tarefas.
- Cabeçalhos fixos em tabelas longas quando tecnicamente viável.
- Colunas críticas: estado, responsável, última atualização e próxima ação.
- Permitir quebra de linhas para nomes/documentos; não truncar informação jurídica sem acesso ao conteúdo completo.

## 13. Kanban

Kanban representa estágio real, não um atalho visual. Cada cartão exibe: cliente/caso, benefício, impedimento prioritário, próxima ação, responsável e atualização. O estágio `triagem` é exclusivamente para triagem não concluída; casos convertidos com documentos pendentes devem aparecer em `documentos`.

## 14. Modais

Modal é para foco temporário, não página principal escondida. Deve ter título, propósito, fechamento por teclado, foco inicial previsível, retorno de foco ao acionador e rolagem interna segura. Em fluxos documentais complexos, preferir página/aba de caso a modal profundo.

## 15. Checklist documental

É a superfície operacional principal do dossiê. Cada item deve reunir:

- nome e finalidade;
- status textual;
- versões recebidas;
- ação principal apropriada (`Enviar documento`, `Visualizar`, `Adicionar versão`, `Validar`);
- origem e data quando disponíveis;
- motivo de bloqueio ou pré-requisito.

A Matriz de Provas é analítica e secundária, preferencialmente recolhível. Não pode substituir o checklist acionável.

## 16. Estados vazios, loading, erro e disabled

- **Vazio:** explique o estado e a primeira ação possível; não use apenas ilustração.
- **Loading:** skeleton para estrutura conhecida; texto de progresso quando a operação for demorada.
- **Erro:** descreva impacto, próxima tentativa e preserve dados já preenchidos. Nunca exibir stack, JSON, `Failed to fetch` ou erro de parse.
- **Disabled:** manter contraste suficiente e apresentar motivo adjacente/tooltip; exemplo: “Auditoria disponível após receber CNIS e CTPS”.

## 17. Navegação

Navegação global orienta módulos; navegação local orienta o caso. A página Dashboard não deve acumular ações de criação sem contexto: `Novo lead`, `Novo atendimento` e `Adicionar à base` pertencem a um ponto de criação claro. Indicar localização atual, preservar filtros de contexto e não esconder ações essenciais exclusivamente em hover.

## 18. Acessibilidade

- Meta: WCAG 2.1 AA como mínimo operacional.
- Contraste mínimo 4.5:1 para texto comum e 3:1 para textos grandes/controles.
- Focus ring visível, consistente e não removido.
- Navegação integral por teclado, ordem de tabulação lógica e skip link quando aplicável.
- Ícones decorativos com `aria-hidden`; controles por ícone recebem nome acessível.
- Mensagens dinâmicas usam região de anúncio apropriada quando forem implementadas.
- Suportar zoom de 200%, fontes maiores e reflow sem perda de ações.

## 19. Motion

Transições de 120–200 ms, propriedades de opacidade/transformação apenas quando ajudam orientação. Nunca usar animação contínua como decoração. Respeitar `prefers-reduced-motion`, removendo transições não essenciais e mantendo feedback textual.

## 20. Responsividade

Prioridade desktop para operação intensa; tablet reorganiza grades e mantém ações visíveis; mobile transforma tabelas em cartões/listas com rótulos, sem esconder status ou ação principal. Sidebar pode recolher, mas a localização atual e a ação de criação devem permanecer acessíveis.

## 21. Iconografia

Usar Font Awesome já presente ou ícones equivalentes do mesmo estilo: traço simples, sem emojis para ações. Ícones apoiam texto, não o substituem em ações críticas. Evitar a mistura de estilos filled, outline, caracteres geométricos e emojis no mesmo contexto.

## 22. Anti-patterns

- neon, roxo “IA”, gradientes chamativos e glassmorphism extensivo;
- dashboard de marketing, métricas sem ação ou gráficos puramente decorativos;
- cards dentro de cards sem ganho de hierarquia;
- múltiplos botões primários concorrentes;
- badges sem texto, erro técnico ou sucesso antes da confirmação;
- truncamento de nomes/documentos sem visualização alternativa;
- usar dourado como cor dominante;
- esconder requisitos de documento em matriz ou modal inacessível.

## 23. Checklist de entrega visual

Antes de cada tela/alteração de componente, confirmar:

- [ ] A próxima ação está clara em menos de cinco segundos?
- [ ] Estado, impedimento e responsável são distinguíveis sem depender só de cor?
- [ ] O conteúdo continua utilizável por teclado, zoom e tela menor?
- [ ] O erro é humano, acionável e não expõe detalhes técnicos?
- [ ] A densidade ajuda a comparação, em vez de criar cartões decorativos?
- [ ] Há somente uma ação primária por contexto?
- [ ] O componente respeita tokens semânticos e motion reduzido?
- [ ] A mudança não introduz dependência, framework ou padrão incompatível com HTML/CSS/JS vanilla?
