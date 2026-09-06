/**
 * PrevIA - Core Engine & Interactive UI
 * Módulo JavaScript ES2024 Modular com OCR & Leitura Documental Totalmente Operacional
 */

class AudioSynth {
  constructor() {
    this.ctx = null;
    this.enabled = false;
  }

  init() {
    if (!this.ctx) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
  }

  playTone(freq, type, duration, gainVal = 0.05) {
    if (!this.enabled) return;
    this.init();
    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {}
  }

  click() { this.playTone(800, 'sine', 0.04, 0.03); }
  tabSwitch() { this.playTone(600, 'triangle', 0.08, 0.04); }
  success() {
    this.playTone(523.25, 'sine', 0.1, 0.05);
    setTimeout(() => this.playTone(659.25, 'sine', 0.1, 0.05), 80);
    setTimeout(() => this.playTone(783.99, 'sine', 0.15, 0.05), 160);
  }
  scan() {
    this.playTone(1200, 'sawtooth', 0.05, 0.02);
    setTimeout(() => this.playTone(1500, 'sawtooth', 0.05, 0.02), 50);
  }

  toggle() {
    this.enabled = !this.enabled;
    if (this.enabled) this.success();
    return this.enabled;
  }
}

const audio = new AudioSynth();

// Valores provenientes de documentos, API ou formulários nunca entram em
// innerHTML sem codificação. Prefira textContent sempre que possível.
const escapeHTML = (value) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

class NeuralCanvas {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.particles = [];
    this.numParticles = 45;
    this.resize();
    this.init();
    this.animate();

    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  init() {
    this.particles = [];
    for (let i = 0; i < this.numParticles; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        radius: Math.random() * 2 + 1
      });
    }
  }

  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    for (let i = 0; i < this.particles.length; i++) {
      let p = this.particles[i];
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0 || p.x > this.canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > this.canvas.height) p.vy *= -1;

      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = 'rgba(0, 242, 254, 0.4)';
      this.ctx.fill();

      for (let j = i + 1; j < this.particles.length; j++) {
        let p2 = this.particles[j];
        let dx = p.x - p2.x;
        let dy = p.y - p2.y;
        let dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 120) {
          this.ctx.beginPath();
          this.ctx.moveTo(p.x, p.y);
          this.ctx.lineTo(p2.x, p2.y);
          this.ctx.strokeStyle = `rgba(0, 242, 254, ${1 - dist / 120})`;
          this.ctx.lineWidth = 0.5;
          this.ctx.stroke();
        }
      }
    }
    requestAnimationFrame(() => this.animate());
  }
}

class AppEngine {
  constructor() {
    this.currentTab = 'dashboard';
    this.atendimentos = [];
    this.currentLead = null;
    this.currentRetirementDossier = null;
    this.smartPending = { items: [], summary: {} };
    this.stats = null;
    this.dashboardFilters = { stage: '', benefit: '' };
    this.filteredDashboardStats = null;
    this.onboardingStep = 2;
    this.activeKanbanStage = 'all';
    this.triageState = { flowId: null, currentNode: null, history: [], selectedResult: null };
    this.ocrUploadSequence = 0;
    this.currentOCRReport = null;
    this.newLeadDestination = 'lead';

    this.initEvents();
    this.initCatalogControls();
    this.initOCRDropzone();
    this.checkAuthStatus();
    this.loadData();
    this.renderOperationalStatus();
    window.addEventListener('online', () => this.renderOperationalStatus());
    window.addEventListener('offline', () => this.renderOperationalStatus());
    this.runSilentCatalogCheck();
  }

  initEvents() {
    const sidebarTagline = document.querySelector('.brand-text .tagline');
    if (sidebarTagline) sidebarTagline.textContent = 'SOF.IA';
    const relationshipNav = document.querySelector('.nav-item[data-tab="relationship"] span');
    if (relationshipNav) relationshipNav.textContent = 'Novos Clientes à Base';
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => this.switchTab(item.dataset.tab));
    });
    document.querySelectorAll('[data-finance-tab]').forEach((button) => {
      button.addEventListener('click', () => this.switchFinanceTab(button.dataset.financeTab));
    });

    const btnAudio = document.getElementById('btn-audio-toggle');
    if (btnAudio) {
      const icon = document.getElementById('audio-toggle-icon');
      btnAudio.setAttribute('aria-pressed', 'false');
      btnAudio.title = 'Ativar efeitos sonoros';
      if (icon) icon.innerHTML = '<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="m16 9 5 6m0-6-5 6"/>';
      btnAudio.addEventListener('click', () => {
        const enabled = audio.toggle();
        btnAudio.style.color = enabled ? 'var(--primary)' : 'var(--text-muted)';
        btnAudio.setAttribute('aria-pressed', String(enabled));
        btnAudio.title = enabled ? 'Desativar efeitos sonoros' : 'Ativar efeitos sonoros';
        if (icon) icon.innerHTML = enabled
          ? '<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15 9a4 4 0 0 1 0 6m2-9a8 8 0 0 1 0 12"/>'
          : '<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="m16 9 5 6m0-6-5 6"/>';
      });
    }

    document.getElementById('btn-logout')?.addEventListener('click', () => this.logout());
    document.getElementById('btn-notifications')?.addEventListener('click', () => this.toggleNotifications());

    const btnNovo = document.getElementById('btn-novo-atendimento');
    if (btnNovo) {
      btnNovo.addEventListener('click', () => this.startNewAttendance());
    }

    const btnNovoLead = document.getElementById('btn-novo-lead');
    if (btnNovoLead) {
      btnNovoLead.addEventListener('click', () => this.openNewLead('lead'));
    }

    document.getElementById('auth-form')?.addEventListener('submit', (event) => event.preventDefault());
    document.getElementById('new-lead-form')?.addEventListener('submit', (event) => {
      event.preventDefault();
      this.createNewLead();
    });
    document.getElementById('btn-start-retirement-triage')?.addEventListener('click', () => this.startRetirementTriage());
    document.getElementById('btn-upload-retirement-cnis')?.addEventListener('click', () => document.getElementById('triage-retirement-cnis-file')?.click());
    document.getElementById('triage-retirement-cnis-file')?.addEventListener('change', (event) => this.uploadRetirementCNIS(event.target.files?.[0]));
    document.getElementById('btn-triage-back')?.addEventListener('click', () => this.goBackTriage());
    document.getElementById('btn-salvar-triage-lead')?.addEventListener('click', () => this.saveTriageLead());
    document.addEventListener('click', (event) => this.handleAction(event));

    const searchInput = document.getElementById('global-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterKanban(e.target.value));
    }
    document.getElementById('dashboard-stage-filter')?.addEventListener('change', (event) => {
      this.dashboardFilters.stage = event.target.value;
      this.applyDashboardFilters();
    });
    document.getElementById('dashboard-benefit-filter')?.addEventListener('change', (event) => {
      this.dashboardFilters.benefit = event.target.value;
      this.applyDashboardFilters();
    });
    document.getElementById('btn-dashboard-clear')?.addEventListener('click', () => {
      this.dashboardFilters = { stage: '', benefit: '' };
      document.getElementById('dashboard-stage-filter').value = '';
      document.getElementById('dashboard-benefit-filter').value = '';
      this.applyDashboardFilters();
    });
    document.getElementById('btn-refresh-smart-pending')?.addEventListener('click', () => this.loadSmartPending());
    document.getElementById('btn-ocr-reset')?.addEventListener('click', () => this.resetOCRAnalysis());
  }

  toggleNotifications() {
    const panel = document.getElementById('notifications-popover');
    const button = document.getElementById('btn-notifications');
    if (!panel || !button) return;
    const isOpen = panel.matches(':popover-open') || !panel.hidden;
    if (isOpen) {
      if (typeof panel.hidePopover === 'function' && panel.matches(':popover-open')) panel.hidePopover();
      panel.hidden = true;
    } else {
      panel.hidden = false;
      if (typeof panel.showPopover === 'function') panel.showPopover();
    }
    button.setAttribute('aria-expanded', String(!isOpen));
    audio.click();
  }

  renderOperationalStatus() {
    const network = document.getElementById('status-network');
    const dot = document.getElementById('status-network-dot');
    if (!network || !dot) return;
    const online = navigator.onLine;
    network.textContent = online ? 'Conexão local disponível' : 'Sem conexão neste navegador';
    dot.classList.toggle('status-dot--ok', online);
    dot.classList.toggle('status-dot--alert', !online);
  }

  switchFinanceTab(tab) {
    const views = {
      geral: ['VISÃO GERAL', 'O escritório em números', 'Receita, carteira, margem e recebimentos em uma leitura operacional.', ['R$ 4.122.000', 'R$ 2.213.580', 'R$ 817.810', 'R$ 324.270']],
      receita: ['RECEITA', 'De onde vem o dinheiro', 'Faturamento realizado, meios de pagamento e origem dos contratos.', ['R$ 301.942', 'R$ 184.468', 'R$ 852.209', '1.753']],
      inadimplencia: ['INADIMPLÊNCIA', 'Recebimentos sob atenção', 'Acompanhe parcelas em aberto e priorize ações de recuperação.', ['68 clientes', 'R$ 324.270', '12,3%', 'R$ 74.527']],
      carteira: ['CARTEIRA', 'Contratos e clientes', 'Contratos ativos, valor contratado e ticket médio por unidade.', ['473 contratos', 'R$ 4.122.000', 'R$ 8.250', 'R$ 1.800.000']],
      custos: ['BENEFÍCIOS E CUSTOS', 'Onde o escritório gera resultado', 'Resultado e participação por tipo de benefício previdenciário.', ['Aposentadoria', 'R$ 381.248', '17,2%', '4 benefícios']],
      equipe: ['EQUIPE', 'Produção por responsável', 'Carteira e receita por responsável, com leitura de risco.', ['4 sócios', 'R$ 637.602', 'R$ 561.521', 'R$ 491.760']],
    };
    const view = views[tab] || views.geral;
    document.querySelectorAll('[data-finance-tab]').forEach((button) => button.classList.toggle('active', button.dataset.financeTab === tab));
    document.getElementById('finance-kicker').textContent = view[0];
    document.getElementById('finance-title').textContent = view[1];
    document.getElementById('finance-description').textContent = view[2];
    view[3].forEach((value, index) => { const element = document.getElementById(`finance-kpi-${index + 1}`); if (element) element.textContent = value; });
    const chartTitle = document.getElementById('finance-chart-title');
    if (chartTitle) chartTitle.textContent = tab === 'inadimplencia' ? 'Evolução de valores em aberto' : tab === 'equipe' ? 'Receita por responsável' : 'Receita, custo e resultado';
    audio.click();
  }

  handleAction(event) {
    const control = event.target.closest('[data-action]');
    if (!control) return;
    const { action, step, dialog, modaltab, stagefilter, destination, mode } = control.dataset;
    event.preventDefault();
    if (action === 'show-login') this.showLoginMode();
    else if (action === 'onboarding-step') this.nextOnboardingStep(Number(step));
    else if (action === 'register') this.submitRegistration();
    else if (action === 'login') this.submitLogin();
    else if (action === 'close-dialog') document.getElementById(dialog)?.close();
    else if (action === 'modal-tab') this.switchModalTab(modaltab);
    else if (action === 'add-activity') this.addActivity();
    else if (action === 'print') window.print();
    else if (action === 'print-cnis-report') this.printCNISReviewReport();
    else if (action === 'send-signature') this.sendContractForSignature();
    else if (action === 'new-lead') this.openNewLead(destination || 'lead');
    else if (action === 'kanban-filter') this.filterKanbanStage(stagefilter);
    else if (action === 'choose-ocr-file') {
      event.stopPropagation();
      document.getElementById('ocr-file-input')?.click();
    } else if (action === 'ocr-mode') this.toggleOCRViewMode(mode);
    else if (action === 'convert-cnis-lead') this.convertCNISToLead();
    else if (action === 'quickstart-case') this.startNewAttendance();
    else if (action === 'quickstart-document') { this.switchTab('ocr'); window.setTimeout(() => document.getElementById('ocr-file-input')?.click(), 0); }
    else if (action === 'quickstart-review') { this.switchTab('ocr'); window.setTimeout(() => document.getElementById('ocr-results-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0); }
    else if (action === 'confirm-retirement-prefilter') this.confirmRetirementPrefilter();
    else if (action === 'save-retirement-prefilter') this.saveRetirementPrefilterLead(control.dataset.route);
    else if (action === 'logout') this.logout();
  }

  initCatalogControls() {
    const monitorButton = document.getElementById('btn-monitorar-fontes');
    const importButton = document.getElementById('btn-importar-catalogo');
    const input = document.getElementById('catalog-workbook-input');
    if (monitorButton) monitorButton.addEventListener('click', () => this.monitorOfficialSources());
    if (importButton && input) importButton.addEventListener('click', () => input.click());
    if (input) input.addEventListener('change', () => this.importCatalogWorkbook(input.files?.[0]));
  }

  // --- INTELIGÊNCIA DOCUMENTAL & OCR 100% OPERACIONAL ---
  initOCRDropzone() {
    const dropzone = document.getElementById('ocr-dropzone');
    const fileInput = document.getElementById('ocr-file-input');

    if (!dropzone || !fileInput) return;

    // Clique na zona de drop ativa o seletor de arquivos
    dropzone.addEventListener('click', () => {
      fileInput.click();
    });

    // Seletor de Arquivos do Computador
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleOCRFileUpload(e.target.files[0]);
      }
    });

    // Suporte a Drag & Drop Nativo
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag-over');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag-over');
      }, false);
    });

    dropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        this.handleOCRFileUpload(dt.files[0]);
      }
    }, false);
  }

  async handleOCRFileUpload(file) {
    if (!file) return;
    return this.processOCRUpload(file);

    audio.scan();

    const statusBox = document.getElementById('ocr-status-box');
    const statusText = document.getElementById('ocr-status-text');
    const tree = document.getElementById('ocr-extracted-tree');
    const title = document.getElementById('ocr-dropzone-title');
    const sub = document.getElementById('ocr-dropzone-sub');

    const fileSizeKB = (file.size / 1024).toFixed(1);
    title.textContent = `📄 ${file.name}`;
    sub.textContent = `Tamanho: ${fileSizeKB} KB | Tipo: ${file.type || 'Documento Previdenciário'}`;

    statusBox.style.display = 'block';
    statusText.textContent = `Lendo "${file.name}" com OCR local ONNX...`;
    tree.textContent = `// Processando "${file.name}" (${fileSizeKB} KB)...\n// Extraindo campos de contribuição, carência e dados cadastrais do INSS...`;

    // Chamada à API de análise documental
    try {
      const res = await fetch('/api/documentos/analisar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_name: file.name, file_size: file.size })
      });
      const data = await res.json();

      setTimeout(() => {
        audio.success();
        statusBox.style.display = 'none';

        const resultData = {
          "arquivo_processado": {
            "nome_original": file.name,
            "tamanho_kb": parseFloat(fileSizeKB),
            "tipo_mime": file.type || "application/pdf",
            "data_envio": new Date().toISOString()
          },
          "classificacao_ia": {
            "tipo_documento": file.name.toLowerCase().includes('cnis') ? "CNIS - Extrato Previdenciário" : (file.name.toLowerCase().includes('laudo') ? "Laudo Médico Pericial" : "Documentação de Identificação / Vínculo"),
            "confianca_ocr": "98.7%",
            "motor_ocr": "RapidOCR + ONNX Engine local"
          },
          "dados_extraidos": data.extracted_data || {
            "nome_beneficiario": "MARIA DAS DORES SILVA",
            "cpf": "384.912.847-19",
            "nit_pis": "128.94827.12-4",
            "data_nascimento": "1968-04-12",
            "status_cadastral": "Regular no CADAUD"
          },
          "analise_previdenciaria": {
            "vinculos_detectados": 5,
            "tempo_contribuicao_total": "32 anos, 2 meses e 15 dias",
            "carencia_cumprida": "386 contribuições (Carência mínima ok)",
            "diagnostico": "Apto para Aposentadoria por Idade Urbana (Art. 48/8213)"
          }
        };

        tree.textContent = JSON.stringify(resultData, null, 2);
      }, 1000);
    } catch (e) {
      setTimeout(() => {
        audio.success();
        statusBox.style.display = 'none';
        tree.textContent = JSON.stringify({
          "arquivo_processado": file.name,
          "tamanho_kb": fileSizeKB,
          "status": "Extração Concluída",
          "dados_cadastrais": {
            "nome": "CLIENTE PROCESSADO LOCALMENTE",
            "status_documento": "Válido e Legível"
          }
        }, null, 2);
      }, 1000);
    }
  }

  async processOCRUpload(file) {
    const allowedExtensions = /\.(pdf|png|jpe?g|tiff?|webp|bmp)$/i;
    if (!allowedExtensions.test(file.name)) {
      this.showOCRError('Formato não suportado. Envie PDF, PNG, JPG, TIFF, WEBP ou BMP.');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      this.showOCRError('Arquivo excede o limite de 50 MB para o OCR local.');
      return;
    }

    const requestVersion = ++this.ocrUploadSequence;
    const statusBox = document.getElementById('ocr-status-box');
    const statusText = document.getElementById('ocr-status-text');
    const tree = document.getElementById('ocr-extracted-tree');
    const title = document.getElementById('ocr-dropzone-title');
    const sub = document.getElementById('ocr-dropzone-sub');
    const fileSizeKB = (file.size / 1024).toFixed(1);
    const resetButton = document.getElementById('btn-ocr-reset');
    const resetFeedback = document.getElementById('ocr-reset-feedback');
    title.textContent = `Arquivo selecionado: ${file.name}`;
    sub.textContent = `Tamanho: ${fileSizeKB} KB | Processamento local em andamento`;
    statusBox.style.display = 'block';
    statusBox.style.borderColor = 'var(--glass-border-glow)';
    statusText.style.color = 'var(--primary)';
    statusText.textContent = `Lendo ${file.name} com OCR local...`;
    tree.textContent = 'Processando documento localmente...';
    if (resetButton) resetButton.style.display = 'inline-flex';
    if (resetFeedback) resetFeedback.style.display = 'none';
    audio.scan();

    try {
      const formData = new FormData();
      formData.append('file', file, file.name);
      formData.append('document_code', 'AUTO');
      const response = await fetch('/api/documentos/analisar', { method: 'POST', body: formData });
      const data = await response.json();
      if (requestVersion !== this.ocrUploadSequence) return;
      if (!response.ok || !data.success) {
        throw new Error(data.error || data.technical_notes || 'O documento não pôde ser lido.');
      }
      statusBox.style.display = 'none';
      tree.textContent = JSON.stringify(data, null, 2);
      this.renderCNISDashboard(data);
      audio.success();
    } catch (error) {
      if (requestVersion !== this.ocrUploadSequence) return;
      statusBox.style.display = 'none';
      this.showOCRError(error.message || 'Falha ao analisar o documento.');
    }
  }

  resetOCRAnalysis() {
    // Invalida uma requisição ainda em curso para que ela não restaure, depois
    // do descarte, os dados de um arquivo que o usuário decidiu trocar.
    this.ocrUploadSequence += 1;
    const input = document.getElementById('ocr-file-input');
    const title = document.getElementById('ocr-dropzone-title');
    const sub = document.getElementById('ocr-dropzone-sub');
    const statusBox = document.getElementById('ocr-status-box');
    const resetButton = document.getElementById('btn-ocr-reset');
    const resetFeedback = document.getElementById('ocr-reset-feedback');
    const results = document.getElementById('ocr-results-content');
    const empty = document.getElementById('ocr-empty-state');
    const reportTitle = document.getElementById('ocr-report-title');
    const tree = document.getElementById('ocr-extracted-tree');
    const meta = document.getElementById('ocr-doc-meta');

    if (input) input.value = '';
    if (title) title.textContent = 'Arraste o documento aqui ou clique para selecionar';
    if (sub) sub.textContent = 'Suporta PDF nativo, PNG ou JPG (Processamento 100% Local)';
    if (statusBox) statusBox.style.display = 'none';
    if (results) results.style.display = 'none';
    if (empty) empty.style.display = 'block';
    if (reportTitle) reportTitle.textContent = 'Central de Inteligência Documental';
    if (tree) tree.textContent = '// A análise estruturada do próximo documento aparecerá aqui.';
    if (meta) meta.style.display = 'none';
    if (resetButton) resetButton.style.display = 'none';
    if (resetFeedback) {
      resetFeedback.textContent = 'Análise descartada. Selecione o documento correto para iniciar uma nova leitura local.';
      resetFeedback.style.display = 'block';
    }
    this.toggleOCRViewMode('visual');
    input?.focus();
  }

  convertCNISToLead() {
    const report = this.currentOCRReport;
    if (!report || report.classification?.code !== 'CNIS') {
      alert('Analise um CNIS válido antes de criar o lead.');
      return;
    }
    this.openNewLead('lead');
    const segurado = report.segurado || {};
    const name = document.getElementById('new-lead-name');
    const flow = document.getElementById('new-lead-flow');
    const note = document.getElementById('new-lead-note');
    if (name) name.value = segurado.nome || '';
    if (flow) flow.value = 'aposentadoria';
    if (note) note.value = `CNIS analisado localmente: ${report.metricas?.alertas_contagem || 0} indicador(es) para revisão. Vincule e confira o documento original antes de qualquer conclusão.`;
    document.getElementById('new-lead-modal-title').textContent = 'Criar lead a partir do CNIS';
    document.getElementById('new-lead-modal-subtitle').textContent = 'Confirme o contato e inclua este caso na esteira para revisão documental.';
    document.getElementById('new-lead-submit-label').textContent = 'Criar lead na esteira';
    document.getElementById('new-lead-phone')?.focus();
  }

  showOCRError(message) {
    const statusBox = document.getElementById('ocr-status-box');
    const statusText = document.getElementById('ocr-status-text');
    if (!statusBox || !statusText) return;
    statusBox.style.display = 'block';
    statusBox.style.borderColor = 'rgba(244,63,94,.55)';
    statusText.style.color = 'var(--accent-rose)';
    statusText.textContent = message;
  }

  renderCNISDashboard(data) {
    const setText = (id, value) => {
      const element = document.getElementById(id);
      if (element) element.textContent = value || 'Não apurado';
    };
    const segurado = data.segurado || {};
    const metricas = data.metricas || {};
    const vinculos = Array.isArray(data.vinculos) ? data.vinculos : [];
    const classification = data.classification || { code: 'CNIS', label: 'CNIS - Extrato Previdenciario' };
    const documentFields = Array.isArray(data.document_fields) ? data.document_fields : [];
    const isCNIS = classification.code === 'CNIS';
    this.currentOCRReport = data;
    const catalogNotice = document.getElementById('cnis-catalog-notice');
    const activeCatalog = data.cnis_catalog?.active;
    if (catalogNotice) {
      if (isCNIS && activeCatalog) {
        catalogNotice.style.display = 'block';
        catalogNotice.textContent = `Indicadores comparados com o catálogo revisado: ${activeCatalog.source_name} (${activeCatalog.total_indicators} indicadores).`;
      } else if (isCNIS) {
        catalogNotice.style.display = 'block';
        catalogNotice.textContent = 'Nenhum catálogo oficial ativo: indicadores encontrados exigem conferência manual.';
      } else {
        catalogNotice.style.display = 'none';
      }
    }
    setText('ocr-report-title', isCNIS ? 'Relatório de Inteligência CNIS' : `Documento identificado: ${classification.label}`);
    document.getElementById('ocr-empty-state').style.display = 'none';
    document.getElementById('ocr-results-content').style.display = 'block';
    setText('cnis-nome', segurado.nome);
    setText('cnis-cpf', segurado.cpf);
    setText('cnis-nit', segurado.nit_pis);
    setText('cnis-nasc', segurado.data_nascimento);
    setText('cnis-diag-title', metricas.diagnostico_principal);
    setText('cnis-tempo-total', metricas.tempo_contribuicao_total);
    if (metricas.tempo_nota) setText('cnis-tempo-dias', metricas.tempo_nota);
    setText('cnis-tempo-dias', metricas.tempo_contribuicao_dias ? `${metricas.tempo_contribuicao_dias} dias apurados` : 'Cálculo pendente de revisão');
    setText('cnis-carencia-val', metricas.carencia_cumprida);
    const carenciaNota = document.getElementById('cnis-carencia-val')?.nextElementSibling;
    if (carenciaNota) {
      carenciaNota.textContent = metricas.carencia_nota || 'Revisao humana necessaria';
      carenciaNota.style.color = 'var(--text-muted)';
    }
    setText('cnis-rmi-val', metricas.rmi_estimada);
    const rmiNota = document.getElementById('cnis-rmi-val')?.nextElementSibling;
    if (rmiNota) rmiNota.textContent = metricas.rmi_nota || 'Calculo tecnico pendente';
    const alertCount = Number(metricas.alertas_contagem || 0);
    setText('cnis-alertas-val', `${alertCount} ${alertCount === 1 ? 'indicador para revisão' : 'indicadores para revisão'}`);
    const alertasNota = document.getElementById('cnis-alertas-val')?.nextElementSibling;
    if (alertasNota) {
      alertasNota.textContent = metricas.alertas_nota || 'Revisao humana necessaria';
      alertasNota.style.color = 'var(--text-muted)';
    }
    setText('cnis-vinculos-count', `${vinculos.length} vínculos extraídos`);
    const timeline = document.getElementById('cnis-timeline-container');
    const timelineTitle = timeline?.parentElement?.querySelector('h4');
    document.querySelectorAll('.cnis-kpi-card').forEach((card) => {
      card.style.display = isCNIS ? '' : 'none';
    });
    timeline.replaceChildren();
    if (!isCNIS) {
      if (timelineTitle) timelineTitle.textContent = `Dados extraidos - ${classification.label}`;
      setText('cnis-vinculos-count', `${documentFields.filter((field) => field.status === 'extraido').length} campo(s) identificados`);
      documentFields.forEach((field) => {
        const item = document.createElement('div');
        item.className = 'cnis-vinculo-card regular';
        item.textContent = `${field.label}: ${field.value}`;
        timeline.appendChild(item);
      });
      if (!documentFields.length) {
        timeline.textContent = 'Nenhum campo estruturado foi extraido. Selecione o Codigo JSON e revise o documento original.';
      }
      return;
    }
    if (timelineTitle) timelineTitle.textContent = 'Vínculos contributivos identificados';
    if (!vinculos.length) {
      timeline.textContent = 'Nenhum vínculo estruturado foi extraído automaticamente. Consulte o Código JSON e revise o documento original.';
      return;
    }
    vinculos.forEach((vinculo) => {
      const item = document.createElement('div');
      item.className = `cnis-vinculo-card ${vinculo.status || 'regular'}`;
      item.textContent = `${vinculo.empregador || 'Vínculo não identificado'} · ${vinculo.data_inicio || '—'} a ${vinculo.data_fim || '—'}`;
      timeline.appendChild(item);
    });
  }

  printCNISReviewReport() {
    const data = this.currentOCRReport;
    if (!data || (data.classification?.code && data.classification.code !== 'CNIS')) {
      alert('Analise um extrato CNIS antes de gerar o relatório de revisão.');
      return;
    }
    const safe = (value) => escapeHTML(String(value || 'Não apurado'));
    const segurado = data.segurado || {};
    const metricas = data.metricas || {};
    const indicadores = metricas.alertas_nota || 'Nenhum indicador estruturado foi identificado.';
    const vinculos = Array.isArray(data.vinculos) ? data.vinculos : [];
    const rows = vinculos.length
      ? vinculos.map((item) => `<tr><td>${safe(item.empregador)}</td><td>${safe(item.tipo_filiacao)}</td><td>${safe(item.data_inicio)} a ${safe(item.data_fim)}</td><td>${safe((item.indicadores || []).join(', ') || 'Sem indicador no bloco')}</td></tr>`).join('')
      : '<tr><td colspan="4">Nenhum vínculo foi estruturado automaticamente. Confira o extrato original.</td></tr>';
    const generatedAt = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long', timeStyle: 'short' }).format(new Date());
    const reportWindow = window.open('', '_blank');
    if (!reportWindow) {
      alert('O navegador bloqueou a nova janela. Libere pop-ups para gerar o relatório.');
      return;
    }
    reportWindow.opener = null;
    reportWindow.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório de revisão CNIS</title><style>
      @page { size: A4; margin: 15mm; } * { box-sizing:border-box; } body { color:#172033; font:11pt/1.45 Arial,sans-serif; margin:0; } h1,h2 { margin:0; } .brand { border-bottom:3px solid #0bbad1; padding-bottom:12px; display:flex; justify-content:space-between; gap:18px; } .brand h1 { font-size:21pt; } .brand p,.muted { color:#5d6a7c; margin:4px 0 0; } .label { color:#087d90; font-size:8pt; font-weight:700; letter-spacing:.08em; text-transform:uppercase; } .notice { background:#fff7df; border-left:4px solid #d89400; margin:16px 0; padding:11px 13px; } .identity,.metrics { display:grid; gap:10px; } .identity { grid-template-columns:repeat(3,1fr); margin:14px 0; } .metrics { grid-template-columns:repeat(2,1fr); } .card { border:1px solid #dce3ea; border-radius:7px; padding:10px; } .card strong { display:block; font-size:13pt; margin-top:3px; } section { margin-top:18px; } h2 { font-size:14pt; border-bottom:1px solid #dce3ea; padding-bottom:5px; margin-bottom:9px; } table { width:100%; border-collapse:collapse; font-size:9.5pt; } th { background:#eef7f8; text-align:left; } th,td { border:1px solid #dce3ea; padding:7px; vertical-align:top; } ul { margin:7px 0; padding-left:20px; } footer { border-top:1px solid #dce3ea; color:#5d6a7c; font-size:8.5pt; margin-top:20px; padding-top:8px; } @media print { .no-print { display:none; } }
      </style></head><body><header class="brand"><div><div class="label">PrevIA · uso interno do escritório</div><h1>Relatório de revisão documental - CNIS</h1><p>Leitura estruturada para conferência profissional; não conclui direito, carência, RMI ou elegibilidade.</p></div><div class="muted">Emitido em<br><strong>${safe(generatedAt)}</strong></div></header>
      <div class="notice"><strong>Decisão necessária:</strong> há ${safe(metricas.alertas_contagem || 0)} indicador(es) documental(is) para revisão. Antes de qualquer protocolo, confronte este resumo com o CNIS original e as provas complementares.</div>
      <section><h2>Identificação extraída</h2><div class="identity"><div class="card"><span class="label">Segurado</span><strong>${safe(segurado.nome)}</strong></div><div class="card"><span class="label">CPF</span><strong>${safe(segurado.cpf)}</strong></div><div class="card"><span class="label">NIT/PIS · nascimento</span><strong>${safe(segurado.nit_pis)} · ${safe(segurado.data_nascimento)}</strong></div></div></section>
      <section><h2>Resumo da leitura</h2><div class="metrics"><div class="card"><span class="label">Tempo identificado</span><strong>${safe(metricas.tempo_contribuicao_total)}</strong><span class="muted">${safe(metricas.tempo_nota)}</span></div><div class="card"><span class="label">Competências localizadas</span><strong>${safe(metricas.carencia_cumprida)}</strong><span class="muted">${safe(metricas.carencia_nota)}</span></div><div class="card"><span class="label">RMI</span><strong>${safe(metricas.rmi_estimada)}</strong><span class="muted">${safe(metricas.rmi_nota)}</span></div><div class="card"><span class="label">Indicadores para revisão</span><strong>${safe(metricas.alertas_contagem || 0)}</strong><span class="muted">${safe(indicadores)}</span></div></div></section>
      <section><h2>Vínculos contributivos extraídos (${vinculos.length})</h2><table><thead><tr><th>Fonte / empregador</th><th>Filiação</th><th>Período</th><th>Indicadores no bloco</th></tr></thead><tbody>${rows}</tbody></table></section>
      <section><h2>Próximas providências recomendadas</h2><ul><li>Conferir os indicadores no documento original e no catálogo normativo oficialmente revisado.</li><li>Confrontar períodos e remunerações com CTPS, GPS, PPP e demais provas disponíveis.</li><li>Registrar a conclusão e o responsável técnico no dossiê antes de qualquer requerimento.</li></ul></section><footer>Relatório gerado a partir de extração local. Os dados devem ser revisados por profissional habilitado; este documento não é requerimento ao INSS nem parecer conclusivo.</footer><script>window.onload=()=>window.print();</script></body></html>`);
    reportWindow.document.close();
  }

  toggleOCRViewMode(mode) {
    document.getElementById('ocr-visual-dashboard').style.display = mode === 'visual' ? 'block' : 'none';
    document.getElementById('ocr-extracted-tree').style.display = mode === 'json' ? 'block' : 'none';
    document.getElementById('btn-ocr-mode-visual').classList.toggle('active', mode === 'visual');
    document.getElementById('btn-ocr-mode-json').classList.toggle('active', mode === 'json');
  }

  async checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status');
      const data = await res.json();
      if (data.configured) {
        this.showLoginMode();
      }
      if (data.office_name) {
        document.getElementById('sidebar-office-name').textContent = data.office_name;
        document.getElementById('user-display-name').textContent = data.office_name;
        document.getElementById('user-display-oab').textContent = `OAB: ${data.oab || '524387'}`;
        document.getElementById('user-avatar-initials').textContent = data.office_name.substring(0, 4).toUpperCase();
      }
    } catch (e) {}
  }

  nextOnboardingStep(step) {
    audio.click();
    this.onboardingStep = step;

    document.getElementById('step-content-1').style.display = step === 1 ? 'block' : 'none';
    document.getElementById('step-content-2').style.display = step === 2 ? 'block' : 'none';
    document.getElementById('step-content-login').style.display = 'none';

    document.getElementById('step-indicator').style.display = 'flex';
    document.getElementById('login-subtitle').textContent = 'Crie sua conta e comece em minutos';

    const node1 = document.getElementById('node-1');
    const node2 = document.getElementById('node-2');
    const line1 = document.getElementById('line-1');

    if (step === 1) {
      node1.className = 'step-node active';
      node1.innerHTML = '1';
      node2.className = 'step-node';
      line1.className = 'step-line';
    } else if (step === 2) {
      node1.className = 'step-node completed';
      node1.innerHTML = '<i class="fa-solid fa-check"></i>';
      node2.className = 'step-node active';
      node2.innerHTML = '2';
      line1.className = 'step-line active';
    }
  }

  showLoginMode() {
    audio.click();
    document.getElementById('step-content-1').style.display = 'none';
    document.getElementById('step-content-2').style.display = 'none';
    document.getElementById('step-content-login').style.display = 'block';

    document.getElementById('step-indicator').style.display = 'none';
    document.getElementById('login-subtitle').textContent = 'Acesse sua conta no PrevIA';

    const toggle = document.getElementById('login-toggle-container');
    toggle.replaceChildren('Não tem conta? ');
    const link = document.createElement('a');
    link.href = '#';
    link.dataset.action = 'onboarding-step';
    link.dataset.step = '2';
    link.textContent = 'Criar em minutos';
    toggle.appendChild(link);
  }

  async logout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } finally {
      window.location.reload();
    }
  }

  async submitRegistration() {
    audio.success();
    const officeName = document.getElementById('office-name').value || 'MADE';
    const officeOab = document.getElementById('office-oab').value || '524387';
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          office_name: officeName,
          oab: officeOab
        })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível criar a conta.');
    } catch (e) {
      alert(e.message || 'Não foi possível criar a conta.');
      return;
    }

    document.getElementById('sidebar-office-name').textContent = officeName;
    document.getElementById('user-display-name').textContent = officeName;
    document.getElementById('user-display-oab').textContent = `OAB: ${officeOab}`;
    document.getElementById('user-avatar-initials').textContent = officeName.substring(0, 4).toUpperCase();

    const overlay = document.getElementById('login-overlay');
    overlay.style.opacity = '0';
    setTimeout(() => overlay.style.display = 'none', 300);
  }

  async submitLogin() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível entrar.');
    } catch (e) {
      alert(e.message || 'Não foi possível entrar.');
      return;
    }
    audio.success();
    const overlay = document.getElementById('login-overlay');
    overlay.style.opacity = '0';
    setTimeout(() => overlay.style.display = 'none', 300);
  }

  switchTab(tabId) {
    if (this.currentTab === tabId) return;

    audio.tabSwitch();

    const updateDOM = () => {
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      const activeNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
      if (activeNav) activeNav.classList.add('active');

      document.querySelectorAll('.tab-view').forEach(view => view.style.display = 'none');
      const targetView = document.getElementById(`view-${tabId}`);
      if (targetView) targetView.style.display = 'block';

      this.currentTab = tabId;
      if (tabId === 'triage') this.renderTriageFlows();
      if (tabId === 'kanban') this.renderKanban();
      if (tabId === 'relationship') this.renderRelationshipBase();
      if (tabId === 'orchestrator') {
        this.loadEvents();
      }
    };

    if (document.startViewTransition) {
      document.startViewTransition(() => updateDOM());
    } else {
      updateDOM();
    }
  }

  async loadData() {
    try {
      const resStats = await fetch('/api/stats');
      this.stats = await resStats.json();
      this.renderDashboardStats();

      const resAtt = await fetch('/api/atendimentos');
      this.atendimentos = await resAtt.json();
      this.populateDashboardBenefitFilter();
      this.applyDashboardFilters();
      this.renderKanban();
      await this.loadSmartPending();
    } catch (e) {
      this.renderMockData();
    }
  }

  renderMockData() {
    this.stats = {
      total_atendimentos: 12,
      total_estimated_value: 148500.0,
      events_pending: 3,
      docs_pending: 4,
      stages: {
        triagem: { count: 3, value: 36000 },
        qualificacao: { count: 2, value: 24000 },
        conflito: { count: 2, value: 18500 },
        proposta: { count: 2, value: 32000 },
        documentos: { count: 2, value: 28000 },
        concluido: { count: 1, value: 10000 },
        perdido: { count: 0, value: 0 }
      }
    };
    this.renderDashboardStats();
  }

  async loadSmartPending() {
    const button = document.getElementById('btn-refresh-smart-pending');
    if (button) { button.disabled = true; button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Atualizando'; }
    try {
      const response = await fetch('/api/pendencias-inteligentes');
      if (!response.ok) throw new Error('A fila não pôde ser carregada.');
      this.smartPending = await response.json();
      this.renderSmartPending();
    } catch (error) {
      const list = document.getElementById('smart-pending-list');
      if (list) list.innerHTML = '<p style="color:var(--text-muted);">Não foi possível carregar a fila de pendências agora.</p>';
    } finally {
      if (button) { button.disabled = false; button.innerHTML = '<i class="fa-solid fa-rotate"></i> Atualizar fila'; }
    }
  }

  renderSmartPending() {
    const list = document.getElementById('smart-pending-list');
    const summary = document.getElementById('smart-pending-summary');
    const notice = document.getElementById('smart-pending-notice');
    if (!list || !summary || !notice) return;
    const data = this.smartPending || { items: [], summary: {} };
    const totals = data.summary || {};
    notice.textContent = data.notice || 'A fila prioriza atividade operacional e não confirma prazo jurídico automaticamente.';
    summary.innerHTML = [
      ['Total', totals.total || 0, 'var(--primary)'],
      ['Críticas', totals.criticas || 0, 'var(--accent-rose)'],
      ['Alta prioridade', totals.alta_prioridade || 0, 'var(--accent-gold)'],
      ['Aguardam revisão', totals.em_revisao || 0, 'var(--accent-cyan)'],
    ].map(([label, value, color]) => `<span style="border:1px solid var(--glass-border); border-radius:999px; padding:.28rem .6rem; font-size:.78rem;"><strong style="color:${color};">${value}</strong> ${label}</span>`).join('');

    if (!(data.items || []).length) {
      list.innerHTML = '<p style="color:var(--accent-emerald); margin:0;"><i class="fa-solid fa-circle-check"></i> Nenhuma pendência operacional priorizada no momento.</p>';
      return;
    }
    list.innerHTML = '';
    data.items.forEach((item) => {
      const card = document.createElement('article');
      card.className = 'smart-pending-card';
      const reasons = (item.reasons || []).map((reason) => `<li>${this.describePendingReason(reason)}</li>`).join('');
      const due = item.due_at ? ` · ação operacional: ${escapeHTML(String(item.due_at))}` : '';
      card.innerHTML = `<div><strong>${escapeHTML(item.lead_name)}</strong> <span class="smart-pending-meta">${escapeHTML(item.flow_name)} · ${escapeHTML(item.assigned_to)}${due}</span><ul>${reasons}</ul></div><button type="button" class="dashboard-action dashboard-action--quiet" aria-label="Abrir caso de ${escapeHTML(item.lead_name)}">Abrir caso</button>`;
      card.querySelector('button').addEventListener('click', async () => {
        await this.openLeadModal(Number(item.attendance_id));
        const documentRelated = (item.reasons || []).some((reason) => reason.code.includes('dossie') || reason.code === 'proxima_acao');
        if (documentRelated) this.switchModalTab('docs');
      });
      list.appendChild(card);
    });
  }

  describePendingReason(reason) {
    const code = String(reason?.code || '').toLowerCase();
    const label = escapeHTML(reason?.label || 'Atenção necessária');
    const detail = escapeHTML(reason?.detail || 'Revise o caso e defina a próxima providência.');
    if (code.includes('dossie') || code.includes('document')) return `<strong>${label}.</strong> Solicite ou confira os documentos necessários antes de avançar. <span>${detail}</span>`;
    if (code.includes('proxima_acao') || code.includes('revis')) return `<strong>${label}.</strong> O caso precisa de uma decisão do responsável. <span>${detail}</span>`;
    return `<strong>${label}.</strong> <span>${detail}</span>`;
  }

  populateDashboardBenefitFilter() {
    const select = document.getElementById('dashboard-benefit-filter');
    if (!select) return;

    const selectedBenefit = this.dashboardFilters.benefit;
    const benefits = [...new Set(this.atendimentos.map((item) => item.flow_name).filter(Boolean))].sort();
    select.replaceChildren(new Option('Todos os benefícios', ''));
    benefits.forEach((benefit) => select.add(new Option(benefit, benefit)));
    select.value = selectedBenefit;
  }

  applyDashboardFilters() {
    if (!this.stats) return;

    const { stage, benefit } = this.dashboardFilters;
    const filteredRows = this.atendimentos.filter((item) =>
      (!stage || (item.crm_stage || 'triagem') === stage) &&
      (!benefit || item.flow_name === benefit)
    );
    const stages = Object.fromEntries(
      Object.keys(this.stats.stages || {}).map((key) => [key, { count: 0, value: 0 }])
    );

    filteredRows.forEach((item) => {
      const key = item.crm_stage || 'triagem';
      if (!stages[key]) stages[key] = { count: 0, value: 0 };
      stages[key].count += 1;
      stages[key].value += Number(item.estimated_total_value || 0);
    });

    this.filteredDashboardStats = {
      ...this.stats,
      total_atendimentos: filteredRows.length,
      total_estimated_value: filteredRows.reduce(
        (total, item) => total + Number(item.estimated_total_value || 0), 0
      ),
      stages,
    };

    const summary = document.getElementById('dashboard-filter-summary');
    if (summary) summary.textContent = `${filteredRows.length} caso(s) na visão atual`;
    this.renderDashboardStats();
  }

  renderDashboardStats() {
    if (!this.stats) return;
    const stats = this.filteredDashboardStats || this.stats;

    document.getElementById('stat-total').textContent = stats.total_atendimentos || 0;
    document.getElementById('stat-value').textContent = (stats.total_estimated_value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    document.getElementById('stat-docs').textContent = stats.docs_pending || 0;
    document.getElementById('stat-events').textContent = stats.events_pending || 0;

    this.renderMetricsChart();
  }

  renderMetricsChart() {
    const canvas = document.getElementById('metrics-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const width = canvas.parentElement.clientWidth;
    const height = canvas.parentElement.clientHeight;
    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    const stats = this.filteredDashboardStats || this.stats || { stages: {} };
    const stages = ['Triagem', 'Qualificação', 'Conflito', 'Proposta', 'Documentos', 'Concluído'];
    const stageKeys = ['triagem', 'qualificacao', 'conflito', 'proposta', 'documentos', 'concluido'];
    const values = stageKeys.map((key) => Number(stats.stages?.[key]?.value || 0) / 1000);
    const maxVal = Math.max(1, ...values);

    const barWidth = (width - 100) / stages.length;

    stages.forEach((label, i) => {
      const val = values[i];
      const h = (val / maxVal) * (height - 80);
      const x = 50 + i * barWidth;
      const y = height - 40 - h;

      const grad = ctx.createLinearGradient(0, y, 0, height - 40);
      grad.addColorStop(0, '#2563eb');
      grad.addColorStop(1, '#00f2fe');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x + 10, y, barWidth - 20, h, [6, 6, 0, 0]);
      ctx.fill();

      ctx.fillStyle = '#f8fafc';
      ctx.font = '11px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`R$ ${val}k`, x + barWidth / 2, y - 8);

      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px Inter, sans-serif';
      ctx.fillText(label, x + barWidth / 2, height - 15);
    });
  }

  filterKanbanStage(stage) {
    audio.click();
    this.activeKanbanStage = stage;

    document.querySelectorAll('.kanban-pill').forEach(btn => btn.classList.remove('active'));
    const activePill = document.querySelector(`.kanban-pill[data-stagefilter="${stage}"]`);
    if (activePill) activePill.classList.add('active');

    const board = document.getElementById('kanban-board');
    if (stage === 'all') {
      board.classList.remove('focused-mode');
      document.querySelectorAll('.kanban-column').forEach(col => col.style.display = 'flex');
    } else {
      board.classList.add('focused-mode');
      document.querySelectorAll('.kanban-column').forEach(col => {
        col.style.display = col.dataset.stage === stage ? 'flex' : 'none';
      });
    }
  }

  renderKanban() {
    const stages = ['triagem', 'qualificacao', 'conflito', 'proposta', 'documentos', 'concluido'];

    stages.forEach(stage => {
      const container = document.getElementById(`cards-${stage}`);
      const countEl = document.getElementById(`count-${stage}`);
      if (!container) return;

      const filtered = this.atendimentos.filter(a => (a.crm_stage || 'triagem') === stage);
      countEl.textContent = filtered.length;

      container.innerHTML = '';
      filtered.forEach(lead => {
        const card = document.createElement('div');
        card.className = 'lead-card';
        card.dataset.id = lead.id;

        const val = (lead.estimated_total_value || 12500).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

        card.innerHTML = `
          <span class="card-tag tag-aposentadoria">${escapeHTML(lead.flow_name || 'Aposentadoria')}</span>
          <button class="card-title card-title-button" type="button">${escapeHTML(lead.lead_name)}</button>
          <div class="card-sub"><i class="fa-solid fa-phone"></i> ${escapeHTML(lead.lead_phone || '(11) 98765-4321')}</div>
          <div class="card-value">${val}</div>
          <div class="card-actions">
            <button class="btn-secondary lead-details-button" type="button" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;">
              <i class="fa-solid fa-folder-open"></i> Abrir Detalhes
            </button>
            <button class="icon-btn lead-advance-button" type="button" style="width: 28px; height: 28px; font-size: 0.75rem;" title="Avançar Etapa">
              <i class="fa-solid fa-chevron-right"></i>
            </button>
          </div>
        `;

        const stopCardInteraction = (event) => {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
        };
        const openDetails = (event) => {
          stopCardInteraction(event);
          this.openLeadModal(lead.id);
        };
        card.querySelector('.card-title-button').addEventListener('pointerdown', stopCardInteraction);
        card.querySelector('.lead-details-button').addEventListener('pointerdown', stopCardInteraction);
        card.querySelector('.card-title-button').addEventListener('click', openDetails);
        card.querySelector('.lead-details-button').addEventListener('click', openDetails);
        card.querySelector('.lead-advance-button').addEventListener('click', (event) => {
          stopCardInteraction(event);
          this.advanceStage(lead.id, stage);
        });
        container.appendChild(card);
      });
    });
  }

  async advanceStage(leadId, currentStage) {
    audio.click();
    const stageOrder = ['triagem', 'qualificacao', 'conflito', 'proposta', 'documentos', 'concluido'];
    const idx = stageOrder.indexOf(currentStage);
    if (idx < stageOrder.length - 1) {
      const nextStage = stageOrder[idx + 1];
      if (!window.confirm(`Mover este lead para ${nextStage}?`)) return;
      
      try {
        const response = await fetch(`/api/atendimentos/${leadId}/stage`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage: nextStage })
        });
        if (!response.ok) throw new Error('Não foi possível atualizar a etapa do lead.');
        const item = this.atendimentos.find(a => a.id === leadId);
        if (item) item.crm_stage = nextStage;
        this.renderKanban();
      } catch (error) {
        console.error('Erro ao avançar etapa:', error);
      }
    }
  }

  // --- MODAL DE DETALHES DO LEAD ---
  async openLeadModal(leadId) {
    audio.click();
    this.currentDocumentAudit = null;
    this.currentRetirementDossier = null;
    try {
      const res = await fetch(`/api/atendimentos/${leadId}`);
      if (!res.ok) throw new Error('Não foi possível carregar os detalhes do lead.');
      this.currentLead = await res.json();
    } catch (e) {
      this.currentLead = this.atendimentos.find(a => a.id === leadId) || {
        id: leadId,
        lead_name: "Cliente Exemplo",
        flow_name: "Aposentadoria Programada",
        activities: [],
        documents: []
      };
    }

    document.getElementById('modal-lead-name').textContent = this.currentLead.lead_name || 'Lead previdenciário';
    document.getElementById('modal-flow-name').textContent = this.currentLead.flow_name || 'Em triagem';

    this.renderModalHistory();
    this.renderModalDocs();
    this.renderModalStrategy();
    this.loadModalContract();

    const modal = document.getElementById('lead-modal');
    if (!modal.open) modal.showModal();
  }

  switchModalTab(tabName) {
    audio.tabSwitch();
    document.querySelectorAll('.modal-tab').forEach(b => b.classList.remove('active'));
    document.querySelector(`.modal-tab[data-modaltab="${tabName}"]`).classList.add('active');

    document.querySelectorAll('.modal-panel').forEach(p => p.style.display = 'none');
    document.getElementById(`modaltab-${tabName}`).style.display = 'block';
  }

  renderModalHistory() {
    const list = document.getElementById('modal-activities-list');
    if (!list) return;

    const activities = this.currentLead.activities || [
      { activity_type: 'nota', body: 'Atendimento inicial de triagem concluído.', created_at: 'Hoje' }
    ];

    list.innerHTML = '';
    activities.forEach(act => {
      const item = document.createElement('div');
      item.style.padding = '0.7rem';
      item.style.background = 'rgba(255,255,255,0.03)';
      item.style.borderRadius = 'var(--radius-sm)';
      item.style.border = '1px solid var(--glass-border)';

      item.innerHTML = `
        <div style="font-size: 0.8rem; color: var(--primary); font-weight: 600;">${escapeHTML(String(act.activity_type || '').toUpperCase())}</div>
        <div style="font-size: 0.9rem; margin-top: 0.2rem;">${escapeHTML(act.body)}</div>
      `;
      list.appendChild(item);
    });
  }

  renderModalStrategy() {
    const container = document.getElementById('modal-strategy-content');
    if (!container || !this.currentLead) return;

    const lead = this.currentLead;
    const docs = Array.isArray(lead.documents) ? lead.documents : [];
    const requiredDocs = docs.filter(doc => Number(doc.required ?? 1) === 1);
    const validatedDocs = requiredDocs.filter(doc => ['aprovado', 'validado'].includes(doc.status)).length;
    const receivedDocs = requiredDocs.filter(doc => ['recebido', 'aprovado', 'validado'].includes(doc.status)).length;
    const profile = lead.triage_profile || {};
    const answers = Array.isArray(profile.answers) ? profile.answers.length : (lead.history || []).length;
    const stageLabels = {
      triagem: 'Triagem', qualificacao: 'Qualificação', conflito: 'Conflito / LGPD',
      proposta: 'Proposta', documentos: 'Documentos', concluido: 'Concluído', relacionamento: 'Relacionamento'
    };
    const stage = stageLabels[lead.crm_stage] || 'Em análise';
    const isDisqualified = lead.status === 'desqualificado';
    const statusLabel = isDisqualified ? 'Sem elegibilidade atual' : (lead.status === 'revisao' ? 'Revisão documental' : 'Potencial identificado');
    const statusClass = isDisqualified ? 'strategy-risk' : (lead.status === 'revisao' ? 'strategy-warning' : 'strategy-good');
    const focus = lead.document_strategy?.analysis_focus || 'Consolidar evidências antes da análise jurídica.';
    const pending = Math.max(0, requiredDocs.length - receivedDocs);

    container.innerHTML = `
      <div class="strategy-hero ${statusClass}">
        <div><span>DIAGNÓSTICO OPERACIONAL</span><h3>${escapeHTML(statusLabel)}</h3><p>${escapeHTML(lead.result_title || 'Triagem inicial ainda não concluída.')}</p></div>
        <div class="strategy-stage"><small>ETAPA ATUAL</small><strong>${escapeHTML(stage)}</strong></div>
      </div>
      <div class="strategy-metrics">
        <div><span>BENEFÍCIO EM FOCO</span><strong>${escapeHTML(lead.flow_name || 'Não definido')}</strong></div>
        <div><span>TRIAGEM REGISTRADA</span><strong>${answers} respostas</strong></div>
        <div><span>EVIDÊNCIAS RECEBIDAS</span><strong>${receivedDocs}/${requiredDocs.length || 0}</strong></div>
        <div><span>VALIDADAS</span><strong>${validatedDocs}/${requiredDocs.length || 0}</strong></div>
      </div>
      <div class="strategy-grid">
        <section><h4><i class="fa-solid fa-bullseye"></i> Estratégia recomendada</h4><p>${escapeHTML(lead.next_step || 'Definir a próxima ação jurídica.')}</p><p class="strategy-muted">${escapeHTML(focus)}</p></section>
        <section><h4><i class="fa-solid fa-folder-open"></i> Pendências documentais</h4><p>${pending ? `${pending} documento(s) obrigatório(s) ainda precisam ser recebidos.` : 'Nenhuma pendência obrigatória de recebimento.'}</p><button class="btn-secondary strategy-docs-button" type="button">Ver checklist</button></section>
      </div>`;
    container.querySelector('.strategy-docs-button').addEventListener('click', () => this.switchModalTab('docs'));
  }

  async addActivity() {
    if (!this.currentLead) return;
    audio.click();

    const type = document.getElementById('new-activity-type').value;
    const body = document.getElementById('new-activity-body').value;

    if (!body) return;

    if (!this.currentLead.activities) this.currentLead.activities = [];
    this.currentLead.activities.unshift({ activity_type: type, body: body });
    this.renderModalHistory();

    document.getElementById('new-activity-body').value = '';

    try {
      await fetch(`/api/atendimentos/${this.currentLead.id}/atividades`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activity_type: type, body: body })
      });
    } catch (e) {}
  }

  renderModalDocs() {
    const list = document.getElementById('modal-docs-list');
    if (!list) return;

    const docs = this.currentLead.documents || [
      { id: 1, document_name: 'Documento de Identidade com Foto', status: 'aprovado' },
      { id: 2, document_name: 'CPF', status: 'aprovado' },
      { id: 3, document_name: 'CNIS - Extrato Previdenciário', status: 'recebido' },
      { id: 4, document_name: 'Carteira de Trabalho (CTPS)', status: 'pendente' }
    ];

    const completed = docs.filter(d => d.status === 'aprovado').length;
    document.getElementById('modal-docs-progress').textContent = `${completed} de ${docs.length} Aprovados`;

    const auditButton = document.getElementById('modal-docs-audit-button');
    if (auditButton) auditButton.onclick = () => this.runDocumentAudit();
    const portalButton = document.getElementById('modal-client-portal-button');
    if (portalButton) portalButton.onclick = () => this.generateClientPortalLink(portalButton);
    const dossierButton = document.getElementById('modal-retirement-dossier-button');
    if (dossierButton) {
      const isRetirement = this.currentLead?.flow_id === 'aposentadoria';
      dossierButton.hidden = !isRetirement;
      dossierButton.onclick = () => this.runRetirementDossier();
    }
    this.renderDocumentAuditResult();
    this.renderRetirementDossier();

    list.innerHTML = '';
    docs.forEach(doc => {
      const card = document.createElement('div');
      card.className = 'doc-item-card';
      const safeStatus = ['pendente', 'recebido', 'aprovado', 'rejeitado', 'validado', 'ilegivel', 'inconsistente'].includes(doc.status)
        ? doc.status
        : 'pendente';
      const auditNote = doc.extraction_status
        ? `Leitura: ${doc.extraction_status}${doc.extraction_confidence != null ? ` · confiança ${Math.round(Number(doc.extraction_confidence) * 100)}%` : ''}`
        : 'Ainda não enviado para leitura.';

      card.innerHTML = `
        <div>
          <strong style="font-size: 0.9rem;">${escapeHTML(doc.document_name)}</strong>
          <small class="doc-audit-note">${escapeHTML(auditNote)}</small>
        </div>
        <div style="display: flex; align-items: center; gap: 0.8rem;">
          <span class="doc-status-badge doc-status-${safeStatus}">${escapeHTML(safeStatus)}</span>
          <button class="icon-btn doc-upload-button" style="width: 30px; height: 30px; font-size: 0.8rem;" title="Enviar e ler documento">
            <i class="fa-solid fa-file-arrow-up"></i>
          </button>
          <button class="icon-btn doc-status-toggle" style="width: 30px; height: 30px; font-size: 0.8rem;" title="Alternar Status">
            <i class="fa-solid fa-rotate"></i>
          </button>
        </div>
      `;
      card.querySelector('.doc-status-toggle').addEventListener('click', () => this.toggleDocStatus(Number(doc.id), safeStatus));
      const fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = '.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp';
      fileInput.hidden = true;
      fileInput.addEventListener('change', () => {
        const file = fileInput.files?.[0];
        if (file) this.uploadCaseDocument(file, doc);
      });
      card.querySelector('.doc-upload-button').addEventListener('click', () => fileInput.click());
      card.appendChild(fileInput);
      list.appendChild(card);
    });
  }

  async generateClientPortalLink(button) {
    if (!this.currentLead?.id) return;
    const originalLabel = button.innerHTML;
    button.disabled = true;
    button.textContent = 'Gerando acesso…';
    try {
      const response = await fetch(`/api/atendimentos/${this.currentLead.id}/portal-acesso`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ttl_days: 7})
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.access_token) throw new Error(data.error || 'Não foi possível gerar o acesso.');
      const link = `${window.location.origin}/portal.html#${data.access_token}`;
      await navigator.clipboard.writeText(link);
      button.textContent = 'Link copiado · válido por 7 dias';
      this.showToast?.('Link seguro do cliente copiado. Ele não inclui dados do caso.', 'success');
    } catch (error) {
      button.textContent = 'Não foi possível copiar';
      this.showToast?.(error.message || 'Não foi possível gerar o link do cliente.', 'error');
    } finally {
      window.setTimeout(() => { button.disabled = false; button.innerHTML = originalLabel; }, 3500);
    }
  }

  renderDocumentAuditResult() {
    const container = document.getElementById('modal-docs-audit-result');
    if (!container) return;
    const audit = this.currentDocumentAudit;
    if (!audit) { container.hidden = true; container.innerHTML = ''; return; }
    const summary = audit.resumo || {};
    const review = Number(summary.divergentes || 0) + Number(summary.nao_localizados || 0);
    container.hidden = false;
    container.innerHTML = `
      <strong><i class="fa-solid fa-shield-halved"></i> Auditoria CNIS × CTPS</strong>
      <span>${escapeHTML(audit.conclusao || 'Auditoria documental concluída.')}</span>
      <small>${Number(summary.confirmados || 0)} confirmado(s) · ${review} para revisão · não calcula elegibilidade.</small>`;
  }

  renderRetirementDossier() {
    const container = document.getElementById('modal-retirement-dossier-result');
    if (!container) return;
    const dossier = this.currentRetirementDossier;
    if (!dossier) { container.hidden = true; container.innerHTML = ''; return; }

    const summary = dossier.resumo || {};
    const decision = dossier.decisao_humana || {};
    const cnisAnalysis = dossier.analise_cnis || {};
    const scenarioCatalog = dossier.cenarios_preparatorios || {};
    const scenarios = (scenarioCatalog.cenarios || []).map((scenario) => {
      const missing = (scenario.dados_ou_provas_pendentes || []).join(', ') || 'nenhuma pendência básica identificada';
      return `<li><strong>${escapeHTML(scenario.titulo || '')}</strong> — ${escapeHTML(scenario.status || '')}<br><small>Pendente: ${escapeHTML(missing)}</small></li>`;
    }).join('') || '<li>Gere o dossiê para preparar os cenários.</li>';
    const cnisFindings = (cnisAnalysis.findings || []).map((finding) => {
      const evidence = (finding.evidence || [])[0] || {};
      const page = evidence.page ? ` · página ${evidence.page}` : '';
      const excerpt = evidence.excerpt ? `<small>${escapeHTML(evidence.excerpt)}</small>` : '';
      return `<li><strong>${escapeHTML(finding.code || 'Sinal CNIS')}</strong> — ${escapeHTML(finding.message || '')}${page}<br><small>${escapeHTML(finding.guidance || '')}</small>${excerpt}</li>`;
    }).join('') || '<li>Nenhum sinal automático localizado. Confira o CNIS original antes de concluir.</li>';
    const hypotheses = (dossier.hipoteses || []).map((hypothesis) => {
      const pending = (hypothesis.pendencias || []).map(escapeHTML).join(' · ') || 'Nenhuma pendência documental crítica localizada.';
      const evidence = (hypothesis.requisitos || []).filter((item) => item.status === 'evidenciado').length;
      return `<details style="margin-top:.65rem;"><summary><strong>${escapeHTML(hypothesis.titulo)}</strong> — ${escapeHTML(hypothesis.status)}</summary><p style="margin:.45rem 0;">${escapeHTML(hypothesis.conclusao)}</p><small>${evidence} requisito(s) com evidência · Pendências: ${pending}</small></details>`;
    }).join('');

    container.hidden = false;
    container.innerHTML = `
      <strong><i class="fa-solid fa-scale-balanced"></i> Dossiê probatório de aposentadoria</strong>
      <span>${escapeHTML(dossier.conclusao || '')}</span>
      <small>${Number(summary.evidencias || 0)} evidência(s) mapeada(s) · ${Number(summary.pendencias || 0)} pendência(s) · revisão humana obrigatória.</small>
      <details class="cnis-analysis-result" style="margin-top:.7rem;" open>
        <summary><strong><i class="fa-solid fa-magnifying-glass-chart"></i> Leitura técnica preliminar do CNIS</strong> — ${escapeHTML(cnisAnalysis.status || 'não analisado')}</summary>
        <p style="margin:.45rem 0;">${escapeHTML(cnisAnalysis.conclusion || 'Gere o dossiê após anexar o CNIS.')}</p>
        <ul style="margin:.35rem 0 .5rem; padding-left:1.1rem;">${cnisFindings}</ul>
        <small>Referência: ${escapeHTML(cnisAnalysis.source?.titulo || 'catálogo oficial')} · não calcula tempo, carência, RMI ou elegibilidade.</small>
      </details>
      <details class="retirement-scenarios-result" style="margin-top:.7rem;">
        <summary><strong><i class="fa-solid fa-list-check"></i> Cenários para futura simulação</strong></summary>
        <p style="margin:.45rem 0;">${escapeHTML(scenarioCatalog.conclusao || 'Ainda não há cenários preparados.')}</p>
        <ul style="margin:.35rem 0 .5rem; padding-left:1.1rem;">${scenarios}</ul>
        <small>Este quadro não calcula RMI, pontos, pedágios, tempo ou elegibilidade.</small>
      </details>
      <div style="margin-top:.7rem;">${hypotheses}</div>
      <button type="button" id="retirement-dossier-pdf" class="btn-secondary" style="margin-top:.8rem;"><i class="fa-solid fa-file-pdf"></i> Baixar rascunho PDF para revisão</button>
      <div style="display:grid; gap:.45rem; margin-top:.85rem; border-top:1px solid var(--glass-border); padding-top:.75rem;">
        <label style="font-size:.78rem;">Decisão do responsável <select id="retirement-dossier-decision"><option value="em_revisao">Em revisão</option><option value="prosseguir_analise">Prosseguir para análise técnica</option><option value="solicitar_provas">Solicitar provas complementares</option><option value="arquivar_hipotese">Arquivar hipótese</option></select></label>
        <input id="retirement-dossier-responsible" placeholder="Responsável pela decisão" value="${escapeHTML(decision.responsavel || '')}">
        <textarea id="retirement-dossier-note" rows="2" placeholder="Fundamente a decisão e a próxima providência">${escapeHTML(decision.nota || '')}</textarea>
        <button type="button" id="retirement-dossier-save" class="btn-secondary" style="justify-self:start;">Registrar decisão humana</button>
      </div>`;
    const decisionSelect = document.getElementById('retirement-dossier-decision');
    if (decisionSelect) decisionSelect.value = decision.status || 'em_revisao';
    document.getElementById('retirement-dossier-save')?.addEventListener('click', () => this.saveRetirementDossierDecision());
    document.getElementById('retirement-dossier-pdf')?.addEventListener('click', () => {
      if (this.currentLead?.id) window.open(`/api/atendimentos/${this.currentLead.id}/kit-requerimento.pdf`, '_blank', 'noopener');
    });
  }

  async runRetirementDossier() {
    if (!this.currentLead?.id) return;
    const button = document.getElementById('modal-retirement-dossier-button');
    if (button) { button.disabled = true; button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Montando'; }
    try {
      const response = await fetch(`/api/atendimentos/${this.currentLead.id}/dossie-probatorio`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'gerar' })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível montar o dossiê probatório.');
      this.currentRetirementDossier = data.dossie;
      this.renderRetirementDossier();
    } catch (error) {
      alert(error.message || 'Não foi possível montar o dossiê probatório.');
    } finally {
      if (button) { button.disabled = false; button.innerHTML = '<i class="fa-solid fa-scale-balanced"></i> Dossiê probatório'; }
    }
  }

  async saveRetirementDossierDecision() {
    if (!this.currentLead?.id) return;
    const status = document.getElementById('retirement-dossier-decision')?.value;
    const responsavel = document.getElementById('retirement-dossier-responsible')?.value;
    const nota = document.getElementById('retirement-dossier-note')?.value;
    try {
      const response = await fetch(`/api/atendimentos/${this.currentLead.id}/dossie-probatorio`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'registrar_decisao', status, responsavel, nota })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível registrar a decisão.');
      this.currentRetirementDossier = data.dossie;
      this.renderRetirementDossier();
    } catch (error) {
      alert(error.message || 'Não foi possível registrar a decisão.');
    }
  }

  async runDocumentAudit() {
    if (!this.currentLead?.id) return;
    const button = document.getElementById('modal-docs-audit-button');
    if (button) { button.disabled = true; button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Auditando'; }
    try {
      const response = await fetch(`/api/atendimentos/${this.currentLead.id}/auditoria-documental`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível gerar a auditoria documental.');
      this.currentDocumentAudit = data.audit;
      this.renderDocumentAuditResult();
    } catch (error) {
      alert(error.message || 'Não foi possível gerar a auditoria documental.');
    } finally {
      if (button) { button.disabled = false; button.innerHTML = '<i class="fa-solid fa-code-compare"></i> Auditar CNIS × CTPS'; }
    }
  }

  async uploadCaseDocument(file, doc) {
    if (!this.currentLead?.id || !doc?.id) return;
    const allowedExtensions = /\.(pdf|png|jpe?g|tiff?|webp|bmp)$/i;
    if (!allowedExtensions.test(file.name)) {
      alert('Envie PDF, PNG, JPG, TIFF, WEBP ou BMP.');
      return;
    }
    const originalStatus = doc.status;
    doc.status = 'recebido';
    this.renderModalDocs();
    try {
      const formData = new FormData();
      formData.append('file', file, file.name);
      formData.append('document_code', doc.document_code || 'AUTO');
      formData.append('attendance_id', String(this.currentLead.id));
      formData.append('document_id', String(doc.id));
      const response = await fetch('/api/documentos/analisar', { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || data.technical_notes || 'Falha na leitura documental.');
      doc.status = data.dossier_document?.status || 'recebido';
      doc.extraction_status = data.extraction_status;
      doc.extraction_confidence = data.extraction_confidence;
      doc.technical_notes = data.technical_notes;
      this.currentDocumentAudit = null;
      this.currentRetirementDossier = null;
      this.renderModalDocs();
      this.renderCNISDashboard(data);
      this.switchTab('ocr');
      alert(`Documento incluído no dossiê. Leitura: ${data.extraction_status}.`);
    } catch (error) {
      doc.status = originalStatus;
      this.renderModalDocs();
      alert(error.message || 'Não foi possível anexar o documento ao dossiê.');
    }
  }

  async toggleDocStatus(docId, currentStatus) {
    audio.click();
    const order = ['pendente', 'recebido', 'aprovado', 'rejeitado'];
    const idx = order.indexOf(currentStatus);
    const nextStatus = order[(idx + 1) % order.length];

    if (this.currentLead && this.currentLead.documents) {
      const d = this.currentLead.documents.find(doc => doc.id === docId);
      if (d) d.status = nextStatus;
      this.renderModalDocs();
    }

    try {
      await fetch(`/api/documentos/${docId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus })
      });
    } catch (e) {}
  }

  async loadModalContract() {
    if (!this.currentLead) return;

    try {
      const res = await fetch(`/api/atendimentos/${this.currentLead.id}/contrato`);
      const data = await res.json();
      document.getElementById('modal-contract-text').textContent = data.contract_text;
      const input = document.getElementById('modal-signature-email');
      if (input) input.value = this.currentLead?.lead_email || '';
    } catch (e) {
      document.getElementById('modal-contract-text').textContent = `
CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS PREVIDENCIÁRIOS

CONTRATADA: MADE Advocacia (OAB: 524387)
CONTRATANTE: ${this.currentLead.lead_name}

OBJETO: Prestação de serviços advocatícios para o benefício de ${this.currentLead.flow_name}.
HONORÁRIOS: 30% sobre o proveito econômico obtido.
`;
    }
  }

  async sendContractForSignature() {
    if (!this.currentLead) return;
    const email = document.getElementById('modal-signature-email')?.value.trim();
    const feedback = document.getElementById('modal-signature-feedback');
    if (!email) { if (feedback) feedback.textContent = 'Informe o e-mail do contratante.'; return; }
    if (!window.confirm(`Enviar a solicitação de assinatura para ${email}?`)) return;
    try {
      const response = await fetch(`/api/atendimentos/${this.currentLead.id}/assinatura`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({client_email:email})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível enviar para assinatura.');
      if (feedback) { feedback.style.color='var(--accent-emerald)'; feedback.textContent=data.message; }
    } catch (error) { if (feedback) { feedback.style.color='var(--accent-rose)'; feedback.textContent=error.message; } }
  }

  filterKanban(term) {
    const query = term.toLowerCase();
    document.querySelectorAll('.lead-card').forEach(card => {
      const text = card.textContent.toLowerCase();
      card.style.display = text.includes(query) ? 'block' : 'none';
    });
  }

  // --- TRIAGEM GUIADA ---
  async renderTriageFlows() {
    const container = document.getElementById('triage-flow-buttons');
    const error = document.getElementById('triage-flow-error');
    if (!container) return;

    try {
      const res = await fetch('/api/triagem/fluxos');
      if (!res.ok) throw new Error('Não foi possível carregar os benefícios disponíveis.');
      const fluxos = await res.json();
      if (!Array.isArray(fluxos) || !fluxos.length) throw new Error('Nenhum benefício foi disponibilizado para triagem.');

      container.replaceChildren();
      if (error) error.textContent = '';
      fluxos.forEach(f => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn-option';
        btn.innerHTML = `<strong>${escapeHTML(f.name)}</strong><span>${Number(f.total_nodes) || 0} perguntas estruturadas</span>`;
        btn.addEventListener('click', () => this.selectTriageBenefit(f.id));
        container.appendChild(btn);
      });
    } catch (e) {
      if (error) error.textContent = e.message || 'Falha ao carregar os benefícios.';
    }
  }

  selectTriageBenefit(flowId) {
    audio.click();
    const leadName = document.getElementById('triage-lead-name').value.trim();
    const leadPhone = document.getElementById('triage-lead-phone').value.trim();
    const error = document.getElementById('triage-lead-error');
    if (!leadName || !leadPhone) {
      error.textContent = 'Informe nome e WhatsApp antes de iniciar a triagem.';
      return;
    }
    error.textContent = '';
    const retirementFilter = document.getElementById('triage-aposentadoria-filter');
    if (flowId === 'aposentadoria') {
      retirementFilter.style.display = 'block';
      document.getElementById('triage-retirement-result').style.display = 'none';
      document.getElementById('triage-retirement-error').textContent = '';
      this.triageState = { flowId, leadName, leadPhone, prequalification: null, currentNode: null, history: [], selectedResult: null };
      retirementFilter.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    retirementFilter.style.display = 'none';
    this.startTriageFlow(flowId, leadName, leadPhone, null);
  }

  async startRetirementTriage() {
    const sex = document.getElementById('triage-retirement-sex').value;
    const age = Number(document.getElementById('triage-retirement-age').value);
    const contributionYears = Number(document.getElementById('triage-retirement-contribution').value);
    const hasCNIS = document.getElementById('triage-retirement-cnis').value;
    const affiliation = document.getElementById('triage-retirement-affiliation').value;
    const error = document.getElementById('triage-retirement-error');
    const resultContainer = document.getElementById('triage-retirement-result');
    if (!sex || !hasCNIS || !affiliation || !Number.isFinite(age) || age < 14 || age > 100 || !Number.isFinite(contributionYears) || contributionYears < 0 || contributionYears > 70) {
      error.textContent = 'Informe sexo, idade, tempo de contribuição, CNIS e primeira filiação antes de avaliar.';
      return;
    }
    error.textContent = '';
    resultContainer.style.display = 'none';
    const button = document.getElementById('btn-start-retirement-triage');
    if (button) { button.disabled = true; button.textContent = 'Avaliando pré-filtro...'; }
    try {
      const response = await fetch('/api/triagem/aposentadoria/pre-filtro', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sex, age, contribution_years: contributionYears, has_cnis: hasCNIS, affiliation, cnis_evidence: this.triageState?.cnisEvidence || null })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível avaliar o pré-filtro.');
      this.triageState = {
        ...this.triageState, flowId: 'aposentadoria', prequalification: data.prequalification,
        prefilter: data, currentNode: null, history: [], selectedResult: null,
      };
      this.renderRetirementPrefilter(data);
    } catch (err) {
      error.textContent = err.message || 'Falha ao avaliar o pré-filtro.';
    } finally {
      if (button) { button.disabled = false; button.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Avaliar pré-filtro'; }
    }
  }

  async uploadRetirementCNIS(file) {
    const status = document.getElementById('triage-retirement-cnis-status');
    const input = document.getElementById('triage-retirement-cnis-file');
    if (!file) return;
    if (!/\.pdf$|\.(png|jpe?g|tiff?|webp|bmp)$/i.test(file.name)) {
      status.textContent = 'Use um PDF ou imagem do CNIS.';
      status.className = 'triage-evidence-status error';
      return;
    }
    status.textContent = `Lendo ${file.name} localmente…`;
    status.className = 'triage-evidence-status loading';
    try {
      const body = new FormData();
      body.append('file', file, file.name);
      body.append('document_code', 'CNIS');
      const response = await fetch('/api/documentos/analisar', { method: 'POST', body });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || data.technical_notes || 'Não foi possível extrair dados do CNIS.');
      if (data.document_code !== 'CNIS') throw new Error(`O arquivo foi identificado como ${data.classification?.label || 'outro documento'}, não como CNIS.`);

      const segurado = data.segurado || {};
      const metricas = data.metricas || {};
      const ageInput = document.getElementById('triage-retirement-age');
      const contributionInput = document.getElementById('triage-retirement-contribution');
      const hasCNISInput = document.getElementById('triage-retirement-cnis');
      const days = Number(metricas.tempo_contribuicao_dias);
      const birth = String(segurado.data_nascimento || '');
      const birthParts = birth.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
      if (birthParts) {
        const today = new Date();
        const year = Number(birthParts[3]); const month = Number(birthParts[2]) - 1; const day = Number(birthParts[1]);
        const age = today.getFullYear() - year - ((today.getMonth() < month || (today.getMonth() === month && today.getDate() < day)) ? 1 : 0);
        ageInput.value = String(age);
      }
      if (Number.isFinite(days) && days > 0) contributionInput.value = (days / 365).toFixed(1);
      hasCNISInput.value = 'sim';
      this.triageState = {
        ...this.triageState,
        cnisEvidence: {
          document_code: data.document_code, file_name: data.file_name,
          extraction_confidence: data.extraction_confidence, segurado, metricas,
          indicator_matches: Array.isArray(data.indicator_matches) ? data.indicator_matches : []
        }
      };
      const timeMessage = Number.isFinite(days) && days > 0 ? `tempo estimado preenchido (${(days / 365).toFixed(1)} anos)` : 'tempo não pôde ser estruturado; informe-o e revise o CNIS';
      status.textContent = `CNIS lido: ${segurado.nome || 'segurado não identificado'}; ${timeMessage}; ${this.triageState.cnisEvidence.indicator_matches.length} indicador(es) encontrado(s).`;
      status.className = 'triage-evidence-status success';
    } catch (error) {
      this.triageState = { ...this.triageState, cnisEvidence: null };
      status.textContent = error.message || 'Falha ao ler o CNIS.';
      status.className = 'triage-evidence-status error';
    } finally {
      if (input) input.value = '';
    }
  }

  renderRetirementPrefilter(data) {
    const container = document.getElementById('triage-retirement-result');
    const requirements = data.requirements || {};
    const evidence = data.evidence || {};
    const ageText = requirements.idade_minima_referencia ? `Idade de referência: ${requirements.idade_minima_referencia} anos` : 'Idade de referência será confirmada no CNIS';
    const contributionText = requirements.tempo_minimo_referencia ? `Tempo de referência: ${requirements.tempo_minimo_referencia} anos` : 'Tempo de referência depende da primeira filiação';
    const gaps = [];
    if (requirements.faltam_anos_idade) gaps.push(`faltam ${requirements.faltam_anos_idade} ano(s) de idade`);
    if (requirements.faltam_anos_contribuicao) gaps.push(`faltam ${requirements.faltam_anos_contribuicao} ano(s) de contribuição`);
    const routeLabel = data.route === 'triagem'
      ? 'Iniciar triagem técnica de aposentadoria'
      : data.route === 'documentos' ? 'Salvar e abrir dossiê para validar CNIS' : 'Salvar na Base de Relacionamento';
    const action = data.route === 'triagem' ? 'confirm-retirement-prefilter' : 'save-retirement-prefilter';
    const icon = data.route === 'triagem' ? 'fa-arrow-right' : data.route === 'documentos' ? 'fa-folder-open' : 'fa-heart-circle-plus';
    container.innerHTML = `
      <span class="triage-step-label">RESULTADO DO PRÉ-FILTRO</span>
      <h3>${escapeHTML(data.title)}</h3>
      <p>${escapeHTML(data.summary)}</p>
      <div class="triage-prefilter-metrics"><span>${escapeHTML(ageText)}</span><span>${escapeHTML(contributionText)}</span>${evidence.used ? `<span class="evidence">Dados cruzados: ${escapeHTML(evidence.source || 'CNIS')}</span>` : '<span class="manual">Dados manuais — CNIS ainda não foi usado</span>' }${Number(evidence.alerts) ? `<span class="warning">${Number(evidence.alerts)} indicador(es) do CNIS exigem revisão</span>` : ''}${gaps.map(item => `<span class="warning">${escapeHTML(item)}</span>`).join('')}</div>
      <p class="triage-prefilter-disclaimer">${escapeHTML(data.disclaimer)}</p>
      <button class="btn-primary" type="button" data-action="${action}" data-route="${escapeHTML(data.route)}"><i class="fa-solid ${icon}"></i> ${routeLabel}</button>`;
    container.style.display = 'block';
    container.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  confirmRetirementPrefilter() {
    const state = this.triageState;
    if (state?.prefilter?.route !== 'triagem') return;
    this.startTriageFlow('aposentadoria', state.leadName, state.leadPhone, state.prequalification);
  }

  saveRetirementPrefilterLead(route) {
    const prefilter = this.triageState?.prefilter;
    if (!prefilter || !['documentos', 'planejamento'].includes(route)) return;
    const isPlanning = route === 'planejamento';
    this.renderTriageResult({
      title: prefilter.title,
      summary: prefilter.summary,
      next_step: isPlanning
        ? 'Acompanhar o cliente e revisar o CNIS antes de uma nova simulação.'
        : 'Anexar e analisar o CNIS para iniciar a triagem técnica de aposentadoria.',
      status: isPlanning ? 'desqualificado' : 'pendente_documental'
    });
  }

  async startTriageFlow(flowId, leadName, leadPhone, prequalification = null) {
    this.triageState = { flowId, leadName, leadPhone, prequalification, currentNode: null, history: [], selectedResult: null };

    document.getElementById('triage-selector').style.display = 'none';
    document.getElementById('triage-quiz').style.display = 'block';
    document.getElementById('triage-result').style.display = 'none';
    this.sendTriageStep(null, null);
  }

  async sendTriageStep(nodeId, answerLabel, preview = false) {
    try {
      const res = await fetch('/api/triagem/executar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          flow_id: this.triageState.flowId,
          node_id: nodeId,
          answer_label: answerLabel,
          preview,
          history: this.triageState.history
        })
      });
      if (!res.ok) throw new Error('Não foi possível carregar a próxima pergunta.');
      const data = await res.json();
      this.triageState.history = data.history || this.triageState.history;

      if (data.is_finished) {
        audio.success();
        this.renderTriageResult(data.result);
      } else {
        this.renderTriageQuestion(data.current_node);
      }
    } catch (e) {
      const container = document.getElementById('triage-options-container');
      if (container) {
        container.textContent = e.message || 'Falha na triagem. Tente novamente.';
        container.className = 'triage-error';
      }
    }
  }

  renderTriageQuestion(node) {
    document.getElementById('triage-node-code').textContent = node.code || 'INSS-01';
    document.getElementById('triage-question-title').textContent = node.title;
    document.getElementById('triage-question-help').textContent = node.help || '';

    const optsContainer = document.getElementById('triage-options-container');
    optsContainer.innerHTML = '';

    node.options.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'btn-option';
      btn.innerHTML = `<strong>${escapeHTML(opt.label)}</strong><span>${escapeHTML(opt.description)}</span>`;
      btn.addEventListener('click', () => {
        audio.click();
        this.sendTriageStep(node.id, opt.label);
      });
      optsContainer.appendChild(btn);
    });
  }

  goBackTriage() {
    if (!this.triageState.history.length) {
      document.getElementById('triage-quiz').style.display = 'none';
      document.getElementById('triage-selector').style.display = 'block';
      return;
    }
    const previous = this.triageState.history.pop();
    this.sendTriageStep(previous.node_id, null, true);
  }

  renderTriageResult(result) {
    document.getElementById('triage-quiz').style.display = 'none';
    document.getElementById('triage-result').style.display = 'block';

    document.getElementById('triage-result-title').textContent = result.title;
    document.getElementById('triage-result-summary').textContent = result.summary;
    document.getElementById('triage-result-next-step').textContent = result.next_step;

    this.triageState.selectedResult = result;

    const btnSave = document.getElementById('btn-salvar-triage-lead');
    btnSave.innerHTML = result.status === 'desqualificado'
      ? '<i class="fa-solid fa-heart-circle-plus"></i> Salvar na Base de Relacionamento'
      : '<i class="fa-solid fa-folder-open"></i> Salvar e abrir dossiê documental';
  }

  async saveTriageLead() {
    if (this.triageSaving || !this.triageState?.selectedResult) return;
    this.triageSaving = true;
    audio.success();
    const result = this.triageState.selectedResult;
    const saveButton = document.getElementById('btn-salvar-triage-lead');
    if (saveButton) { saveButton.disabled = true; saveButton.textContent = 'Salvando dossiê...'; }

    const newLead = {
      lead_name: this.triageState.leadName,
      lead_phone: this.triageState.leadPhone,
      lead_source: 'triagem_guiada',
      flow_id: this.triageState.flowId,
      result_title: result.title,
      summary: result.summary,
      next_step: result.next_step,
      status: result.status || 'aprovado',
      crm_stage: result.status === 'desqualificado' ? 'relacionamento' : 'triagem',
      relationship_status: result.status === 'desqualificado' ? 'aguardando_revisao' : 'nao_aplicavel',
      relationship_next_review_at: result.status === 'desqualificado'
        ? new Date(Date.now() + 180 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
        : null,
      history: this.triageState.history,
      triage_profile: {
        flow_id: this.triageState.flowId,
        prequalification: this.triageState.prequalification,
        answers: this.triageState.history,
        result: { title: result.title, status: result.status }
      },
      estimated_monthly_value: 3840.0,
      estimated_total_value: 46080.0
    };

    try {
      const res = await fetch('/api/atendimentos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newLead)
      });
      const data = await res.json();
      if (!res.ok || !data.success || !data.id) throw new Error(data.error || 'Não foi possível criar o dossiê do cliente.');
      newLead.id = data.id;
    } catch (error) {
      alert(error.message || 'Não foi possível salvar a triagem.');
      this.triageSaving = false;
      if (saveButton) { saveButton.disabled = false; this.renderTriageResult(result); }
      return;
    }

    this.atendimentos.unshift(newLead);
    if (result.status === 'desqualificado') {
      this.switchTab('relationship');
      this.triageSaving = false;
      return;
    }
    try {
      // Abre o dossiê primeiro: transições visuais do Kanban não podem impedir
      // o acesso imediato aos documentos recém-criados.
      await this.openLeadModal(newLead.id);
      this.switchModalTab('docs');
      this.switchTab('kanban');
    } catch (error) {
      this.switchTab('kanban');
      alert('Lead salvo. Abra os detalhes no Kanban para acessar o dossiê documental.');
    } finally {
      this.triageSaving = false;
      if (saveButton) { saveButton.disabled = false; this.renderTriageResult(result); }
    }
  }

  async renderRelationshipBase() {
    const container = document.getElementById('relationship-list');
    if (!container) return;
    container.innerHTML = '<p class="relationship-empty">Carregando base de relacionamento...</p>';
    try {
      const response = await fetch('/api/relacionamento');
      if (!response.ok) throw new Error('Falha ao carregar a base de relacionamento.');
      const leads = await response.json();
      document.getElementById('relationship-count').textContent = leads.length;
      container.innerHTML = '';
      if (!leads.length) {
        container.innerHTML = '<p class="relationship-empty">Nenhum lead em acompanhamento. Leads desqualificados com potencial futuro aparecerão aqui.</p>';
        return;
      }
      leads.forEach((lead) => {
        const card = document.createElement('article');
        card.className = 'relationship-card';
        const reviewDate = lead.relationship_next_review_at
          ? new Date(`${lead.relationship_next_review_at}T00:00:00`).toLocaleDateString('pt-BR')
          : 'Sem revisão agendada';
        card.innerHTML = `
          <div><span class="relationship-badge">Acompanhamento</span><h3>${escapeHTML(lead.lead_name)}</h3><p>${escapeHTML(lead.lead_phone || 'Telefone não informado')} · ${escapeHTML(lead.flow_name || 'Triagem previdenciária')}</p></div>
          <div class="relationship-reason"><strong>Motivo atual:</strong> ${escapeHTML(lead.result_title || 'Sem elegibilidade atual')}<br><span>${escapeHTML(lead.next_step || lead.summary || '')}</span></div>
          <div><strong>Revisar em:</strong> ${reviewDate}<br><span class="relationship-consent">${lead.remarketing_opt_in ? 'Contato autorizado' : 'Sem consentimento de remarketing'}</span></div>
          <div class="relationship-actions"><button class="btn-secondary relationship-detail" type="button">Detalhes</button><button class="btn-primary relationship-reactivate" type="button">Reabrir triagem</button></div>`;
        card.querySelector('.relationship-detail').addEventListener('click', () => this.openLeadModal(lead.id));
        card.querySelector('.relationship-reactivate').addEventListener('click', () => this.reactivateLead(lead.id));
        container.appendChild(card);
      });
    } catch (error) {
      container.textContent = error.message || 'Falha ao carregar a base de relacionamento.';
      container.className = 'triage-error';
    }
  }

  async reactivateLead(leadId) {
    try {
      const response = await fetch(`/api/atendimentos/${leadId}/reativar`, { method: 'POST' });
      if (!response.ok) throw new Error('Não foi possível reabrir o lead.');
      await this.loadData();
      this.switchTab('kanban');
    } catch (error) {
      alert(error.message || 'Falha ao reabrir o lead.');
    }
  }

  startNewAttendance() {
    audio.click();
    this.triageState = { flowId: null, currentNode: null, history: [], selectedResult: null };
    document.getElementById('triage-selector').style.display = 'block';
    document.getElementById('triage-quiz').style.display = 'none';
    document.getElementById('triage-result').style.display = 'none';
    document.getElementById('triage-aposentadoria-filter').style.display = 'none';
    document.getElementById('triage-retirement-result').style.display = 'none';
    document.getElementById('triage-lead-error').textContent = '';
    document.getElementById('triage-retirement-error').textContent = '';
    this.switchTab('triage');
    window.setTimeout(() => document.getElementById('triage-lead-name')?.focus(), 0);
  }

  openNewLead(destination = 'lead') {
    this.newLeadDestination = destination;
    document.getElementById('new-lead-form').reset();
    const isRelationship = destination === 'relationship';
    document.getElementById('new-lead-modal-title').textContent = isRelationship ? 'Adicionar à base' : 'Novo lead';
    document.getElementById('new-lead-modal-subtitle').textContent = isRelationship
      ? 'Cadastre o contato para acompanhamento futuro, sem iniciar a triagem agora.'
      : 'Cadastre e inicie a qualificação previdenciária.';
    document.getElementById('new-lead-submit-label').textContent = isRelationship ? 'Salvar contato' : 'Criar lead';
    document.getElementById('new-lead-modal').showModal();
  }

  async createNewLead() {
    const name = document.getElementById('new-lead-name').value.trim();
    const phone = document.getElementById('new-lead-phone').value.trim();
    const flowId = document.getElementById('new-lead-flow').value;
    const note = document.getElementById('new-lead-note').value.trim();
    const remarketingOptIn = document.getElementById('new-lead-remarketing-consent').checked;
    const feedback = document.getElementById('new-lead-feedback');
    const isRelationship = this.newLeadDestination === 'relationship';
    if (!name || !phone) {
      feedback.textContent = 'Informe nome e WhatsApp para criar o lead.';
      return;
    }
    try {
      const response = await fetch('/api/atendimentos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_name: name,
          lead_phone: phone,
          flow_id: flowId,
          result_title: isRelationship ? 'Contato aguardando oportunidade ou reavaliação' : 'Novo lead aguardando triagem',
          summary: isRelationship ? 'Cadastro direto na Base de Relacionamento.' : 'Lead cadastrado manualmente.',
          next_step: isRelationship ? 'Revisar o contato e definir a melhor jornada quando houver oportunidade.' : 'Iniciar triagem guiada.',
          notes: note,
          status: 'revisao',
          crm_stage: isRelationship ? 'relacionamento' : 'triagem',
          relationship_status: isRelationship ? 'aguardando_revisao' : 'nao_aplicavel',
          relationship_next_review_at: isRelationship ? new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10) : null,
          lead_source: isRelationship ? 'cadastro_relacionamento' : 'cadastro_manual',
          remarketing_opt_in: remarketingOptIn
        })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error('Não foi possível salvar o lead.');
      document.getElementById('new-lead-modal').close();
      await this.loadData();
      this.switchTab(isRelationship ? 'relationship' : 'kanban');
    } catch (error) {
      feedback.textContent = error.message || 'Falha ao salvar o lead.';
    }
  }

  async loadEvents() {
    const tbody = document.getElementById('orchestrator-events-body');
    if (!tbody) return;

    try {
      const res = await fetch('/api/eventos/fila');
      const events = await res.json();

      if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="padding: 1.5rem; text-align: center; color: var(--text-muted);">Nenhum evento em fila no momento.</td></tr>';
        return;
      }

      tbody.innerHTML = '';
      events.forEach(ev => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--glass-border)';
        tr.innerHTML = `
          <td style="padding: 0.8rem; font-family: var(--font-code); color: var(--primary);">#${ev.id}</td>
          <td style="padding: 0.8rem; font-weight: 600;">${escapeHTML(ev.event_type)}</td>
          <td style="padding: 0.8rem;">${escapeHTML(ev.source)}</td>
          <td style="padding: 0.8rem;"><span style="color: var(--accent-gold);">${escapeHTML(String(ev.priority || '').toUpperCase())}</span></td>
          <td style="padding: 0.8rem;"><span style="color: var(--accent-emerald);">${escapeHTML(String(ev.status || '').toUpperCase())}</span></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {}
  }

  setCatalogMessage(message = '', isError = false) {
    const target = document.getElementById('catalog-status-message');
    if (!target) return;
    target.textContent = message;
    target.style.color = isError ? 'var(--accent-rose)' : 'var(--accent-emerald)';
  }

  async loadOfficialCatalog() {
    const summary = document.getElementById('catalog-active-summary');
    const sourcesContainer = document.getElementById('official-sources-list');
    const versionsContainer = document.getElementById('catalog-versions-list');
    if (!summary || !sourcesContainer || !versionsContainer) return;
    try {
      const [statusResponse, versionsResponse] = await Promise.all([
        fetch('/api/catalogo-cnis/status'), fetch('/api/catalogo-cnis/versoes')
      ]);
      const statusData = await statusResponse.json();
      const versionsData = await versionsResponse.json();
      if (!statusResponse.ok || !versionsResponse.ok) throw new Error('Não foi possível carregar o catálogo oficial.');
      const active = statusData.catalog?.active;
      summary.textContent = active
        ? `Versão ativa #${active.id}: ${active.total_indicators} indicadores, revisada por ${active.reviewed_by || 'responsável do escritório'}.`
        : 'Nenhuma versão está ativa. O OCR permanece conservador e não aplica indicadores automaticamente.';
      sourcesContainer.replaceChildren();
      (statusData.sources || []).forEach((source) => {
        const card = document.createElement('article');
        card.className = 'official-source-card';
        const title = document.createElement('strong');
        title.className = 'official-source-title';
        title.textContent = source.title;
        const scope = document.createElement('p');
        scope.className = 'official-source-scope';
        scope.textContent = source.scope;
        const detail = document.createElement('p');
        detail.className = 'official-source-detail';
        detail.textContent = source.source_hash
          ? `Hash ${source.source_hash.slice(0, 12)}… · última captura ${new Date(source.captured_at).toLocaleString('pt-BR')}`
          : 'Fonte ainda não verificada.';
        const link = document.createElement('a');
        link.href = source.source_url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Abrir fonte oficial';
        link.className = 'official-source-link';
        card.append(title, scope, detail, link);
        sourcesContainer.appendChild(card);
      });
      versionsContainer.replaceChildren();
      const versions = versionsData.versions || [];
      if (!versions.length) versionsContainer.textContent = 'Nenhuma versão importada.';
      versions.forEach((version) => {
        const row = document.createElement('div');
        row.className = 'doc-item-card';
        const label = document.createElement('div');
        const strong = document.createElement('strong');
        strong.textContent = `#${version.id} · ${version.source_name}`;
        const description = document.createElement('div');
        description.style.color = 'var(--text-muted)';
        description.style.fontSize = '.78rem';
        description.textContent = `${version.imported_definitions} indicadores · ${version.status}`;
        label.append(strong, description);
        row.appendChild(label);
        if (version.status === 'aguarda_revisao' && Number(version.imported_definitions) > 0) {
          const activate = document.createElement('button');
          activate.type = 'button';
          activate.className = 'btn-primary';
          activate.textContent = 'Revisar e ativar';
          activate.addEventListener('click', () => this.activateCatalogVersion(version.id));
          row.appendChild(activate);
        }
        versionsContainer.appendChild(row);
      });
    } catch (error) {
      this.setCatalogMessage(error.message || 'Falha ao carregar o catálogo oficial.', true);
    }
  }

  async runSilentCatalogCheck() {
    // Governança interna: a consulta não gera alerta visual e jamais ativa
    // regras. Alterações continuam dependentes de revisão jurídica registrada.
    const storageKey = 'previa_catalog_last_silent_check';
    const previous = Number(sessionStorage.getItem(storageKey) || 0);
    if (Date.now() - previous < 12 * 60 * 60 * 1000) return;
    try {
      const response = await fetch('/api/catalogo-cnis/monitorar', { method: 'POST' });
      if (response.ok) sessionStorage.setItem(storageKey, String(Date.now()));
    } catch (_) {
      // Falhas de rede não interrompem a operação do CRM.
    }
  }

  async monitorOfficialSources() {
    const button = document.getElementById('btn-monitorar-fontes');
    if (button) button.disabled = true;
    this.setCatalogMessage('Consultando e preservando as fontes oficiais do Portal IN…');
    try {
      const response = await fetch('/api/catalogo-cnis/monitorar', { method: 'POST' });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível verificar as fontes.');
      const changed = (data.outcomes || []).filter((item) => item.change_detected).length;
      const failures = (data.outcomes || []).filter((item) => item.success === false).length;
      this.setCatalogMessage(failures ? `${failures} fonte(s) não puderam ser verificadas.` : changed ? `${changed} fonte(s) alterada(s): aguardam revisão jurídica.` : 'Fontes oficiais verificadas; nenhuma mudança foi ativada automaticamente.', failures > 0);
      await this.loadOfficialCatalog();
    } catch (error) {
      this.setCatalogMessage(error.message || 'Falha ao verificar as fontes.', true);
    } finally {
      if (button) button.disabled = false;
    }
  }

  async importCatalogWorkbook(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      this.setCatalogMessage('Envie a planilha de indicadores no formato XLSX.', true);
      return;
    }
    this.setCatalogMessage(`Importando ${file.name}; a versão ficará pendente de revisão jurídica…`);
    try {
      const body = new FormData();
      body.append('file', file, file.name);
      const response = await fetch('/api/catalogo-cnis/importar-planilha', { method: 'POST', body });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível importar a planilha.');
      this.setCatalogMessage(`Versão #${data.version.id} importada com ${data.version.total_indicators} indicadores. Revise antes de ativar.`);
      await this.loadOfficialCatalog();
    } catch (error) {
      this.setCatalogMessage(error.message || 'Falha ao importar a planilha.', true);
    } finally {
      const input = document.getElementById('catalog-workbook-input');
      if (input) input.value = '';
    }
  }

  async activateCatalogVersion(versionId) {
    const note = window.prompt('Registre a revisão jurídica antes de ativar esta versão:');
    if (note === null) return;
    if (!note.trim()) {
      this.setCatalogMessage('A ativação exige uma anotação de revisão jurídica.', true);
      return;
    }
    try {
      const response = await fetch(`/api/catalogo-cnis/versoes/${versionId}/ativar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível ativar a versão.');
      this.setCatalogMessage(`Versão #${versionId} ativada com revisão jurídica registrada.`);
      await this.loadOfficialCatalog();
    } catch (error) {
      this.setCatalogMessage(error.message || 'Falha ao ativar a versão.', true);
    }
  }
}

let app;
window.addEventListener('DOMContentLoaded', () => {
  new NeuralCanvas('bg-canvas');
  app = new AppEngine();
});

window.addEventListener('DOMContentLoaded', () => {
  const stageFilter = document.getElementById('dashboard-stage-filter');
  const filterBar = stageFilter?.closest('.glass-panel');
  if (filterBar) filterBar.classList.add('dashboard-filter-bar');
});

window.addEventListener('DOMContentLoaded', () => {
  // Destaca no painel o que pede decisão operacional, sem alterar os dados.
  document.querySelectorAll('.metric-card').forEach((card) => {
    const label = (card.textContent || '').toLowerCase();
    if (label.includes('documentos pendentes')) card.classList.add('metric-action-required');
    if (label.includes('tarefas de automação')) card.classList.add('metric-priority');
  });
});
