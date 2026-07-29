(function () {
  const flowSelector = document.getElementById("flowSelector");
  const startButton = document.getElementById("startButton");
  const backButton = document.getElementById("backButton");
  const resetAllButton = document.getElementById("resetAllButton");
  const journeyIntro = document.getElementById("journeyIntro");
  const questionCard = document.getElementById("questionCard");
  const resultCard = document.getElementById("resultCard");
  const questionTitle = document.getElementById("questionTitle");
  const questionHelp = document.getElementById("questionHelp");
  const questionOptions = document.getElementById("questionOptions");
  const currentFlowName = document.getElementById("currentFlowName");
  const currentStepCode = document.getElementById("currentStepCode");
  const progressLabel = document.getElementById("progressLabel");
  const historyList = document.getElementById("historyList");
  const leadName = document.getElementById("leadName");
  const leadPhone = document.getElementById("leadPhone");
  const leadNotes = document.getElementById("leadNotes");

  const flowEntries = Object.values(window.FLOW_DEFINITIONS);

  const state = {
    activeFlowId: flowEntries[0].id,
    currentNodeId: null,
    history: [],
    finishedResult: null
  };

  function populateFlowSelector() {
    flowEntries.forEach((flow) => {
      const option = document.createElement("option");
      option.value = flow.id;
      option.textContent = flow.name;
      flowSelector.appendChild(option);
    });
    flowSelector.value = state.activeFlowId;
  }

  function getActiveFlow() {
    return window.FLOW_DEFINITIONS[state.activeFlowId];
  }

  function resetJourney() {
    state.currentNodeId = null;
    state.history = [];
    state.finishedResult = null;
    render();
  }

  function resetAll() {
    leadName.value = "";
    leadPhone.value = "";
    leadNotes.value = "";
    flowSelector.value = flowEntries[0].id;
    state.activeFlowId = flowEntries[0].id;
    resetJourney();
  }

  function startFlow() {
    const flow = getActiveFlow();
    state.currentNodeId = flow.start;
    state.history = [];
    state.finishedResult = null;
    render();
  }

  function answerQuestion(option) {
    const flow = getActiveFlow();
    const node = flow.nodes[state.currentNodeId];

    state.history.push({
      nodeId: node.id,
      nodeCode: node.code,
      question: node.title,
      answer: option.label
    });

    if (option.next) {
      state.currentNodeId = option.next;
      render();
      return;
    }

    if (option.result) {
      state.currentNodeId = null;
      state.finishedResult = flow.results[option.result];
      render();
    }
  }

  function goBack() {
    const flow = getActiveFlow();

    if (!state.history.length) {
      resetJourney();
      return;
    }

    state.finishedResult = null;
    const lastAnswer = state.history.pop();

    if (!state.history.length) {
      state.currentNodeId = lastAnswer.nodeId;
      render();
      return;
    }

    state.currentNodeId = lastAnswer.nodeId;
    render();
  }

  function renderQuestion() {
    const flow = getActiveFlow();
    const node = flow.nodes[state.currentNodeId];

    currentFlowName.textContent = flow.name;
    currentStepCode.textContent = node.code;
    questionTitle.textContent = node.title;
    questionHelp.textContent = node.help || "";
    progressLabel.textContent = `Pergunta ${state.history.length + 1}`;

    questionOptions.innerHTML = "";
    node.options.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "option-button";
      button.innerHTML = `<strong>${option.label}</strong><small>${option.description}</small>`;
      button.addEventListener("click", () => answerQuestion(option));
      questionOptions.appendChild(button);
    });
  }

  function renderHistory() {
    if (!state.history.length) {
      historyList.innerHTML = '<p class="history-placeholder">Nenhuma resposta registrada ainda.</p>';
      return;
    }

    historyList.innerHTML = "";
    state.history.forEach((item, index) => {
      const entry = document.createElement("article");
      entry.className = "history-item";
      entry.innerHTML = `
        <strong>${index + 1}. ${item.nodeCode} - ${item.question}</strong>
        <span>Resposta: ${item.answer}</span>
      `;
      historyList.appendChild(entry);
    });
  }

  function renderResult() {
    if (!state.finishedResult) {
      resultCard.classList.add("hidden");
      return;
    }

    const badgeClass = state.finishedResult.status;
    const leadHeader = leadName.value ? `para ${leadName.value}` : "para este lead";

    resultCard.innerHTML = `
      <div class="result-badge ${badgeClass}">${labelForStatus(state.finishedResult.status)}</div>
      <h3>${state.finishedResult.title}</h3>
      <p>Resultado final da triagem ${leadHeader}.</p>
      <div class="summary-box">
        <strong>Resumo</strong>
        <span>${state.finishedResult.summary}</span>
      </div>
      <div class="summary-box">
        <strong>Próximo passo</strong>
        <span>${state.finishedResult.nextStep}</span>
      </div>
      <div class="summary-box">
        <strong>Contato registrado</strong>
        <span>${leadPhone.value || "Telefone não informado"}.</span>
      </div>
      <button class="primary-button" type="button" id="restartFlowButton">Refazer triagem</button>
    `;

    resultCard.classList.remove("hidden");

    const restartFlowButton = document.getElementById("restartFlowButton");
    restartFlowButton.addEventListener("click", startFlow);
  }

  function labelForStatus(status) {
    if (status === "aprovado") {
      return "Qualificado";
    }

    if (status === "revisao") {
      return "Em revisão";
    }

    return "Desqualificado";
  }

  function render() {
    renderHistory();
    renderResult();

    if (state.finishedResult) {
      journeyIntro.classList.add("hidden");
      questionCard.classList.add("hidden");
      progressLabel.textContent = "Fluxo concluído";
      resultCard.classList.remove("hidden");
      return;
    }

    resultCard.classList.add("hidden");

    if (!state.currentNodeId) {
      journeyIntro.classList.remove("hidden");
      questionCard.classList.add("hidden");
      progressLabel.textContent = "Aguardando início";
      return;
    }

    journeyIntro.classList.add("hidden");
    questionCard.classList.remove("hidden");
    renderQuestion();
  }

  flowSelector.addEventListener("change", (event) => {
    state.activeFlowId = event.target.value;
    resetJourney();
  });

  startButton.addEventListener("click", startFlow);
  backButton.addEventListener("click", goBack);
  resetAllButton.addEventListener("click", resetAll);

  populateFlowSelector();
  render();
})();
