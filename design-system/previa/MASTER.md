# PrevIA — Design System Mestre

**Status:** Source of Truth de UX/UI
**Versão:** 1.0.0 · 2026-09-07
**Escopo:** frontend HTML, CSS e JavaScript vanilla. Este documento define experiência, linguagem visual e componentes; não define regras jurídicas, endpoints, banco ou lógica de estado.

## 1. Objetivo e contexto

PrevIA é um software operacional brasileiro para gestão de casos previdenciários. Combina Legal Case Management, produtividade, workflow documental, evidências, operações previdenciárias, analytics, motor determinístico e portal do cliente.

Não é site institucional, landing page jurídica, CRM comercial genérico, fintech, produto visual de IA ou dashboard futurista. A interface existe para reduzir tempo de decisão e tornar o trabalho verificável.

## 2. Princípios e personalidade

1. **Clareza operacional > decoração.**
2. **Estado confirmado é estado comunicado.** A interface não simula conclusão antes da confirmação real.
3. **Segurança compreensível.** Dados e limitações são explicados em linguagem humana.
4. **Densidade organizada.** A informação é agrupada por tarefa e escaneável, sem transformar cada dado em card.
5. **Automação orienta; profissional decide.** Análise automatizada apresenta evidência, origem e próxima revisão, sem se apresentar como decisão jurídica.

Personalidade: sóbria, precisa, confiável e eficiente. A voz é direta: “2 documentos aguardam validação”, não linguagem promocional ou de “IA mágica”.

## 3. Hierarquia de informação

Toda tela operacional prioriza, nesta ordem:

1. próxima ação;
2. pendência ou impedimento;
3. estado e responsável do caso;
4. documento ou evidência;
5. análise;
6. histórico;
7. ferramentas secundárias.

Cada contexto imediato tem no máximo uma ação primária. Ações destrutivas ou irreversíveis ficam visualmente separadas e usam confirmação proporcional ao impacto.

## 4. Direção visual

- **Categoria:** Legal Operations / Case Management / Productivity.
- **Padrão:** dashboard operacional com Case Management Dashboard e Document Pipeline Dashboard; nunca Product Demo + Features como estrutura da aplicação.
- **Estilo:** Flat Design + Minimalism / Swiss + Accessible & Ethical.
- **Densidade:** 8/10 — dashboard denso, com grade, alinhamento e respiro suficiente para leitura profissional.
- **Motion:** 3/10 — feedback sutil e continuidade, não espetáculo.
- **Variance:** 4/10 — moderno e consistente, sem assimetrias ou experimentação visual por tela.

## 5. Layout, grid e spacing

- Grid: 12 colunas em desktop, 8 em tablet e 4 em mobile. A grade é funcional, não decorativa.
- Conteúdo desktop: largura fluida com máximo de aproximadamente 1440 px; painéis de leitura longa devem limitar a medida do texto.
- Sidebar persistente em desktop; em telas menores, navegação recolhível sem perder localização ou ação principal.
- Escala: `4, 8, 12, 16, 24, 32, 48` px. Usar 16 px como padding interno padrão e 24 px entre blocos de trabalho.
- Listas, filtros e chips devem quebrar linha ou oferecer divulgação operável de excedentes; nunca ocultar valores em uma linha cortada.

### Tokens de espaço e forma

| Token | Valor conceitual | Uso |
| --- | --- | --- |
| `--space-xs` | 4px | ajuste fino, ícone + texto |
| `--space-sm` | 8px | itens relacionados |
| `--space-md` | 12px | grupos compactos |
| `--space-lg` | 16px | padding de componente |
| `--space-xl` | 24px | separação de seções |
| `--space-2xl` | 32px | regiões principais |
| `--radius-sm` | 6px | inputs, badges discretos |
| `--radius-md` | 10px | cards e menus |
| `--radius-lg` | 14px | modal e superfícies grandes |
| `--shadow-sm` | elevação sutil | menu/controle sobre superfície |
| `--shadow-md` | elevação moderada | modal/dropdown; nunca decorativa |

## 6. Cor e tokens semânticos

Navy/trust blue estrutura confiança e navegação; superfícies permanecem neutras. Teal é informação eventual, não identidade dominante. Âmbar é controlado para atenção. Nenhum estado depende somente de cor: incluir rótulo e, quando útil, ícone.

| Token | Valor | Papel |
| --- | --- | --- |
| `--color-primary` | `#1E3A8A` | ação primária, navegação ativa |
| `--color-primary-hover` | `#1E40AF` | estado hover/pressed |
| `--color-background` | `#F8FAFC` | canvas de aplicação |
| `--color-surface` | `#FFFFFF` | card, tabela, modal |
| `--color-surface-muted` | `#E9EEF5` | agrupamento secundário |
| `--color-text` | `#0F172A` | texto principal |
| `--color-text-muted` | `#475569` | contexto e ajuda |
| `--color-border` | `#CBD5E1` | divisão e contorno |
| `--color-focus` | `#1E40AF` | anel de foco visível |
| `--color-success` | `#1E7A52` | confirmado/aprovado |
| `--color-warning` | `#B45309` | pendência/revisão |
| `--color-error` | `#DC2626` | impedimento/rejeição |
| `--color-info` | `#2563EB` | informação/processamento |
| `--color-neutral` | `#64748B` | não iniciado/arquivado |
| `--color-accent` | `#B45309` | destaque excepcional; não CTA dominante |

Usar texto branco sobre navy/erro e validar contraste de cada par no contexto real. Não aplicar gradientes “AI”, neon ou dourado como superfície predominante.

## 7. Tipografia

- **Heading:** Lexend, peso 500–700.
- **Body e UI:** Source Sans 3, peso 400–700.
- **Dados técnicos pontuais:** fonte monoespaçada já disponível, apenas para identificadores, logs e comparações técnicas.
- Escala: 12, 14, 16, 20, 24 e 32 px; texto corrido entre 14–16 px com `line-height` unitário de 1.4–1.55.
- Datas, moeda e contagens em tabelas usam números tabulares quando possível.
- Não usar serif decorativa como fonte principal do dashboard.

## 8. Componentes base

### Botões

- Primário: conclui a ação prioritária do contexto, em navy.
- Secundário: alternativa útil, com menor contraste visual.
- Terciário: ferramenta auxiliar; não usar como única via para ação crítica.
- Perigo: texto explícito, cor de erro e separação espacial.
- Durante espera: preservar largura, indicar atividade e impedir repetição. Não trocar o resultado por sucesso antes de confirmação.

### Inputs e formulários

- Todo campo tem rótulo visível; placeholder não substitui rótulo.
- Exibir ajuda, formato e obrigatoriedade próximos ao campo.
- Erro de campo fica associado com `aria-describedby`; em erro múltiplo, usar resumo focável no topo sem remover erros inline.
- Preservar conteúdo digitado após falha de servidor.
- Campos e controles touch têm alvo mínimo de 44 × 44 px quando aplicável.

### Cards, tabelas e listas

- Card representa uma tarefa, decisão ou agrupamento significativo; evitar card dentro de card sem ganho de hierarquia.
- Borda sutil, superfície neutra e sombra apenas quando expressar elevação.
- Tabela para comparação; lista para sequência, atividade e tarefa.
- Colunas críticas: estado, responsável, atualização e próxima ação.
- Em telas pequenas, converter comparação ampla em cards/listas rotuladas ou usar rolagem horizontal contida; nunca quebrar o viewport.

### Badges, chips e status

- Status estáveis: `Pendente`, `Recebido`, `Em validação`, `Aprovado`, `Impedido`, `Concluído`.
- Badge contém texto; cor e ícone são apoio.
- Chips interativos usam elemento nativo `button`, nome acessível, estado selecionado/pressionado e foco visível.
- Alterações assíncronas de contagem usam mensagem contextual única, sem mover foco ou criar múltiplas regiões live concorrentes.

### Kanban

Kanban comunica estágio real do caso. Cartão apresenta cliente/caso, benefício, impedimento prioritário, próxima ação, responsável e última atualização. Triagem é exclusiva para triagem não concluída; casos convertidos com requisitos documentais permanecem em `documentos`.

### Checklist documental e upload

Checklist é a superfície operacional principal do dossiê. Cada documento apresenta nome, finalidade, status, quantidade de versões, origem/data, ação principal e motivo de bloqueio quando houver. Ações são contextuais: `Enviar documento`, `Visualizar`, `Adicionar versão` ou `Validar`.

Upload informa formato, tamanho, progresso/espera e resultado confirmado. Em falha, preserva estado anterior e explica como recuperar. Matriz de Provas é análise secundária e não substitui checklist acionável.

### Modais, tooltips e navegação

- Modal é foco temporário, não navegação primária; tem título, propósito, saída clara por teclado e retorno de foco ao acionador.
- Tooltips complementam, nunca são a única explicação para requisito, estado ou ação.
- Navegação global organiza módulos; navegação local organiza o caso. Indicador de localização atual é obrigatório.
- Não esconder ação essencial em hover e não misturar sidebar, tabs e navegação inferior no mesmo nível hierárquico.

## 9. Estados de interface e feedback

- **Vazio:** explica o que não existe e a primeira ação disponível.
- **Loading:** skeleton para estrutura conhecida; progresso/estado acessível para operação demorada. Evitar spinner piscando para resposta quase instantânea.
- **Erro:** mensagem humana, causa compreensível e caminho de recuperação. Nunca exibir stack, JSON, `Failed to fetch` ou erro de parse.
- **Disabled:** usar atributo semântico, contraste suficiente e motivo próximo ou em tooltip; não parecer apenas “botão quebrado”.
- **Sucesso:** confirmar somente após persistência/resultado real e manter o usuário no contexto da ação.

## 10. Acessibilidade, foco e teclado

- Meta mínima: WCAG 2.2 AA; aplicar requisitos web relevantes de WCAG 2.2 quando possível.
- Contraste: 4.5:1 para texto normal; 3:1 para controles e texto grande.
- Focus ring de 2–4 px visível em todo controle, inclusive em modal; nunca remover outline sem alternativa.
- Ordem de tabulação acompanha ordem visual; todas as ações podem ser concluídas por teclado.
- Cabeçalho, rodapé fixo e overlay não podem obscurecer foco; usar compensação de rolagem quando necessário.
- Ícones decorativos usam `aria-hidden="true"`; ícones significativos sem texto recebem alternativa textual. Controle por ícone recebe nome acessível e estado exposto.
- Suportar zoom de 200%, reflow, fontes maiores e espaçamento do usuário sem corte em largura/altura fixa.
- `prefers-reduced-motion` reduz movimento não essencial sem esconder o estado final.

## 11. Responsividade e motion

- Breakpoints de validação: 375, 768, 1024 e 1440 px; testar também orientação paisagem quando relevante.
- Desktop otimiza operações densas; tablet reorganiza grade; mobile mantém ação, estado e rótulo antes de conteúdo secundário.
- Sem rolagem horizontal global. Conteúdo longo usa `overflow-wrap` e filhos flex/grid podem encolher.
- Motion: 120–200 ms, opacidade/transformação apenas quando orientarem continuidade. Sem animação contínua decorativa, reveal de conteúdo crítico ou dependência de evento de animação para estado funcional.

## 12. Iconografia

O projeto mantém Font Awesome nesta fase; não introduzir biblioteca nova. Usar família, peso e tamanho consistentes por nível visual. O resultado do domínio icons confirmou o ícone `warning` como símbolo de status de atenção, em estilo outline; seu significado depende do contexto e deve possuir texto alternativo quando não houver rótulo visível.

Não usar emojis estruturais, glifos geométricos improvisados ou mistura arbitrária de filled/outline. Ícones apoiam texto; não substituem rótulo em ação crítica.

## 13. Anti-patterns

- Product Demo/hero/CTA como estrutura da aplicação;
- site institucional, fintech, CRM genérico ou narrativa de startup de IA;
- neon, roxo “AI”, cyberpunk, gradiente decorativo e glassmorphism dominante;
- métricas ou gráficos sem decisão acionável;
- vários botões primários concorrentes;
- sucesso visual antes de confirmação; erros técnicos ou silenciosos;
- badge sem texto, chip cortado ou ação apenas em hover;
- card aninhado sem propósito, texto truncado sem revelação e tabelas que rompem viewport;
- foco invisível, modal sem rota de saída ou gesto/drag como único caminho.

## 14. Checklist pré-entrega

- [ ] A próxima ação está identificável em até cinco segundos?
- [ ] Pendência, estado, responsável e evidência são distinguíveis sem depender somente de cor?
- [ ] Há uma única ação primária no contexto?
- [ ] Formulários mantêm rótulo, ajuda, erro inline e recuperação?
- [ ] Carregamento, erro, disabled e sucesso têm feedback claro e acessível?
- [ ] Teclado, foco, modal, zoom de 200% e reflow foram validados?
- [ ] Viewports 375, 768, 1024 e 1440 foram verificados sem rolagem horizontal global?
- [ ] Animações respeitam reduced motion e não carregam significado sozinhas?
- [ ] Ícones têm semântica e consistência adequadas?
- [ ] A implementação continua compatível com HTML/CSS/JS vanilla, sem dependência nova?

## 15. Proveniência das decisões

| Domínio | Query | Resultado verificado | Decisão no PrevIA |
| --- | --- | --- | --- |
| product | `legal case management productivity dashboard` | Legal Services: Case Management Dashboard; Productivity Tool; Analytics Dashboard | Legal Operations + produtividade + Case Management; analytics é secundário à operação |
| product | `productivity tool workflow dashboard` | Document Workflow: Document Pipeline Dashboard e trust navy | Checklist/documentos como fluxo operacional; não landing |
| style | `professional operational dashboard accessible minimal flat` | Minimalism & Swiss: grade, alto contraste, grid, baixo custo e foco acessível | Flat Design + Minimalism/Swiss; Accessible & Ethical vem das categorias Legal/Document Workflow |
| color | `legal services` | navy `#1E3A8A`, branco, âmbar `#B45309`, superfícies neutras | navy/trust blue estrutural e âmbar controlado |
| color | `productivity tool` | teal foi primário; Invoice & Billing apresentou navy profissional | teal fica apenas como informação eventual; tokens semânticos independentes |
| typography | `professional software dashboard readable dense` | Corporate Trust: Lexend + Source Sans 3, acessível e legível | Lexend para títulos e Source Sans 3 para corpo/UI |
| typography | `legal professional modern readable` | Legal Professional sugeriu serif + sans; Modern Professional sugeriu sans + sans | sem serif principal, pois legibilidade de software prevalece |
| ux | `keyboard focus visible`; `error validation feedback`; `badge chip status accessible`; `responsive reflow zoom`; `loading feedback disabled state` | foco visível, erro recuperável e anunciado, chips operáveis, reflow sem corte, loading/disabled explícitos | regras de foco, formulário, status, reflow e feedback deste Master |
| icons | `status action navigation document`, retry `caution` | primeira consulta sem match; retry retornou `warning`, outline, semântica contextual | manter Font Awesome e aplicar semântica contextual; sem nova biblioteca |
| web | `accessibility focus modal navigation`; `responsive dashboard interaction` | resultados eram majoritariamente iOS/Android/React Native | somente princípios universais aplicáveis foram considerados; nenhuma regra nativa/Tailwind foi adotada |
