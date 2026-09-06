(() => {
  const escapeHTML = (value) => String(value || '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const token = window.location.hash.slice(1);
  const show = (id) => { const element = document.getElementById(id); if (element) element.hidden = false; };
  const hide = (id) => { const element = document.getElementById(id); if (element) element.hidden = true; };

  async function loadPortal() {
    if (!token || token.length < 32) return showError();
    // O fragmento não viaja ao servidor. Remova-o da barra assim que o JS o ler.
    window.history.replaceState(null, document.title, window.location.pathname);
    try {
      const response = await fetch('/api/portal/resumo', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token}), cache: 'no-store'
      });
      if (!response.ok) throw new Error('unavailable');
      const data = await response.json();
      render(data.portal || {});
    } catch (_) { showError(); }
  }

  function showError() { hide('portal-loading'); show('portal-error'); }
  function render(portal) {
    document.getElementById('portal-client-name').textContent = portal.cliente || 'cliente';
    document.getElementById('portal-benefit').textContent = portal.beneficio || 'Benefício previdenciário';
    document.getElementById('portal-progress').textContent = portal.andamento || 'Caso em acompanhamento';
    document.getElementById('portal-next-step').textContent = portal.proxima_etapa || 'O escritório entrará em contato quando necessário.';
    const documents = Array.isArray(portal.documentos) ? portal.documentos : [];
    const pending = documents.filter((document) => document.situacao === 'pendente').length;
    document.getElementById('portal-doc-count').textContent = pending ? `${pending} pendente${pending === 1 ? '' : 's'}` : 'Tudo certo';
    document.getElementById('portal-documents').innerHTML = documents.length ? documents.map((document) => `<div class="client-portal-document"><span class="portal-document-icon">${document.situacao === 'recebido' ? '✓' : '!'}</span><div><strong>${escapeHTML(document.nome)}</strong><small>${document.obrigatorio ? 'Documento solicitado' : 'Documento complementar'}</small></div><span class="portal-document-status ${document.situacao === 'recebido' ? 'is-received' : ''}">${document.situacao === 'recebido' ? 'Recebido' : 'Pendente'}</span></div>`).join('') : '<p class="client-portal-empty">Nenhum documento solicitado neste momento.</p>';
    hide('portal-loading'); show('portal-content');
  }
  loadPortal();
})();
