/* The host owns state and submission. Generated surfaces supply data, never code. */
'use strict';
(() => {
  const types = new Set(['Stack', 'Card', 'Heading', 'Text', 'Stat', 'Badge', 'ProgressBar', 'Table', 'Select', 'TextField', 'Button', 'Slider', 'Divider', 'Spacer', 'Image', 'KeyValue', 'Form']);
  const asText = value => value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const mediaPath = value => typeof value === 'string' && /^\/media\/[a-zA-Z0-9_./-]+$/.test(value) && !value.includes('..') ? value : null;
  function validateSurface(surface) {
    if (!surface || !Array.isArray(surface.components) || !surface.components.length || surface.components.length > 120) throw new Error('The DM’s interface could not be displayed. You can still reply below.');
    const nodes = new Map();
    for (const c of surface.components) {
      if (!c || typeof c.id !== 'string' || nodes.has(c.id) || !c.props || typeof c.props !== 'object' || (c.children && !Array.isArray(c.children))) throw new Error('Invalid generated interface. Use the message box to continue.');
      nodes.set(c.id, c);
    }
    const root = nodes.has('root') ? 'root' : surface.components[0].id;
    const active = new Set(), seen = new Set();
    function visit(id, depth) {
      if (!nodes.has(id) || active.has(id) || depth > 30) throw new Error('Invalid generated interface structure. Use the message box to continue.');
      if (seen.has(id)) return;
      active.add(id);
      for (const child of nodes.get(id).children || []) visit(child, depth + 1);
      active.delete(id); seen.add(id);
    }
    // Check disconnected nodes too, so hidden cycles are never accepted.
    for (const id of nodes.keys()) visit(id, 0);
    return {nodes, root};
  }
  function actionText(action, values, label) {
    if (!action || !['act', 'confirm_character'].includes(action.intent)) throw new Error('This generated action is not supported. Describe your choice below.');
    const keys = Array.isArray(action.payloadKeys) ? action.payloadKeys : [];
    if (keys.some(key => typeof key !== 'string' || !Object.hasOwn(values, key))) throw new Error('This choice is missing information. Tell your DM what you choose below.');
    return keys.length === 1 ? asText(values[keys[0]]) : keys.length ? keys.map(key => `${key}: ${asText(values[key])}`).join('; ') : asText(label);
  }
  // Pure contract helpers are exposed only to Node's test harness.
  if (typeof module !== 'undefined' && module.exports) { module.exports = {validateSurface, actionText, mediaPath}; return; }
  const $ = id => document.getElementById(id);
  const el = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = asText(text); return node; };
  let status = null, campaign = null, busy = false, surfaceSignature = '', pollTimer = null, pollCount = 0, retryOperation = null, currentMusic = '', musicRequested = false;
  let campaignEpoch = 0;
  const savedKey = 'ai-dungeon-master.live-campaign';
  function savedCampaign(value) { try { if (value !== undefined) localStorage.setItem(savedKey, value); return localStorage.getItem(savedKey); } catch { return null; } }
  function notice(message, retry = null) { $('notice-text').textContent = message; $('notice').hidden = !message; $('retry').hidden = !retry; retryOperation = retry; }
  async function api(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);
    let response;
    try { response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? {} : {'Content-Type': 'application/json', 'X-Game-Token': status?.write_token || ''}, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal}); }
    catch { const error = new Error('The connection was interrupted. Retry to safely check the same request.'); error.transport = true; throw error; }
    finally { clearTimeout(timeout); }
    let result; try { result = await response.json(); } catch { throw new Error('The server returned an unreadable response. Refresh to reconnect.'); }
    if (!response.ok) { const error = new Error(asText(result.error?.message || result.error || result.message || `Server error ${response.status}`)); error.code = response.status; throw error; }
    return result;
  }
  function setBusy(value) {
    busy = value;
    $('send').disabled = value || !campaign;
    $('start').disabled = value || !status?.configured;
    $('new-campaign').disabled = value || !status?.configured;
    $('confirm-character').disabled = value;
    $('campaign-select').disabled = value;
    $('turn-status').textContent = value ? 'Your DM is thinking…' : '';
    $('composer').setAttribute('aria-busy', String(value));
    for (const button of $('generated-surface').querySelectorAll('button')) button.disabled = value;
  }
  function renderSurface(surface) {
    const signature = JSON.stringify(surface || null);
    if (signature === surfaceSignature) return;
    surfaceSignature = signature;
    const host = $('generated-surface');
    host.replaceChildren();
    if (!surface) return;
    try {
      const {nodes, root} = validateSurface(surface);
      const values = Object.assign(Object.create(null), surface.dataModel || {});
      function render(id, depth = 0) {
        if (depth > 30) throw new Error('The generated interface is too deeply nested.');
        const c = nodes.get(id), p = c.props || {}, type = c.type;
        if (!types.has(type)) return el('p', 'surface-unsupported', `A ${asText(type)} view is unavailable here. You can describe your action below.`);
        let n;
        switch (type) {
          case 'Stack': n = el('div', `surface-stack${p.direction === 'row' ? ' surface-row' : ''}`); break;
          case 'Card': n = el('section', 'surface-card'); break;
          case 'Form': n = el('div', 'surface-form'); break;
          case 'Heading': n = el(`h${Math.min(6, Math.max(2, Number(p.level) || 2))}`, 'surface-heading', p.text); break;
          case 'Text': n = el('p', 'surface-text', p.text); break;
          case 'Badge': n = el('span', 'surface-badge', p.text); break;
          case 'Stat': n = el('div', 'surface-stat'); n.append(el('small', '', p.label), el('strong', '', `${asText(p.value)}${p.unit ? ` ${asText(p.unit)}` : ''}`)); break;
          case 'KeyValue': n = el('div', 'surface-keyvalue'); n.append(el('span', 'key-label', p.label), el('span', '', p.value)); break;
          case 'Divider': n = el('hr', 'surface-divider'); break;
          case 'Spacer': n = el('div', 'surface-spacer'); n.setAttribute('aria-hidden', 'true'); break;
          case 'Image': { const src = mediaPath(p.src); n = src ? el('img', 'surface-image') : el('p', 'muted', 'Illustration unavailable'); if (src) { n.src = src; n.alt = asText(p.alt || 'Generated illustration'); n.loading = 'lazy'; } break; }
          case 'Button': n = el('button', '', p.label || 'Continue'); n.type = 'button'; n.disabled = busy; n.addEventListener('click', () => { try { if (!host.reportValidity?.()) { const invalid = host.querySelector(':invalid'); if (invalid) { invalid.reportValidity(); return; } } const text = actionText(p.action, values, p.label); if (p.action.intent === 'confirm_character') { notice('Review your character sheet, then use “Begin adventure with this character” below.'); return; } submitAction(text); } catch (error) { notice(error.message); } }); break;
          case 'TextField': case 'Select': case 'Slider': {
            n = el('label', 'surface-control'); n.append(el('span', 'key-label', p.label || p.bind));
            let input;
            if (type === 'Select') { input = el('select'); for (const option of Array.isArray(p.options) ? p.options : []) { const object = option && typeof option === 'object'; const entry = el('option', '', object ? option.label ?? option.value : option); entry.value = asText(object ? option.value : option); input.append(entry); } }
            else if (type === 'Slider') { input = el('input'); input.type = 'range'; input.min = String(Number.isFinite(p.min) ? p.min : 0); input.max = String(Number.isFinite(p.max) ? p.max : 100); input.step = String(Number.isFinite(p.step) && p.step > 0 ? p.step : 1); }
            else { input = el(p.multiline ? 'textarea' : 'input'); input.placeholder = asText(p.placeholder); input.required = Boolean(p.required); input.maxLength = 4000; }
            input.value = asText(values[p.bind]);
            if (typeof p.bind === 'string' && Object.hasOwn(values, p.bind)) { values[p.bind] = type === 'Slider' ? Number(input.value) : input.value; input.addEventListener('input', () => { values[p.bind] = type === 'Slider' ? Number(input.value) : input.value; }); }
            else input.disabled = true;
            n.append(input); break;
          }
          case 'ProgressBar': { n = el('label', 'surface-control', p.label || 'Progress'); const progress = el('progress', 'surface-progress'); progress.max = Math.max(1, Number(p.max) || 100); progress.value = Math.max(0, Number(p.value) || 0); n.append(progress); break; }
          case 'Table': { n = el('div', 'surface-table-wrap'); const table = el('table', 'surface-table'); const columns = Array.isArray(p.columns) ? p.columns : []; const head = el('tr'); columns.forEach(column => head.append(el('th', '', typeof column === 'object' ? column.label ?? column.key : column))); const thead = el('thead'); thead.append(head); table.append(thead); const body = el('tbody'); for (const row of Array.isArray(p.rows) ? p.rows.slice(0, 100) : []) { const tr = el('tr'); const cells = Array.isArray(row) ? row : columns.map(column => row?.[typeof column === 'object' ? column.key : column]); cells.forEach(cell => tr.append(el('td', '', cell))); body.append(tr); } table.append(body); n.append(table); break; }
        }
        for (const child of c.children || []) n.append(render(child, depth + 1));
        return n;
      }
      host.append(render(root));
    } catch (error) { host.append(el('p', 'muted', error.message)); }
  }
  function renderCharacter(character) {
    const host = $('character-sheet');
    host.replaceChildren(); $('hero-name').textContent = character?.name || 'An unwritten name';
    if (!character) { host.append(el('p', 'muted', 'Your character will take shape here as you and your DM create them together.')); return; }
    host.append(el('p', 'muted', [character.species, character.class, character.level != null ? `Level ${character.level}` : null].filter(Boolean).join(' · ')));
    const stats = el('div', 'sheet-grid');
    for (const [label, value] of [['HP', character.hp != null ? `${character.hp}/${character.max_hp ?? character.hp}` : null], ['AC', character.ac], ['Level', character.level]]) if (value != null) { const item = el('div', 'surface-stat'); item.append(el('small', '', label), el('strong', '', value)); stats.append(item); }
    host.append(stats);
    for (const key of ['background', 'abilities', 'modifiers', 'skills', 'equipment', 'features', 'spells', 'resources', 'rule_sources']) { const value = character[key]; if (value == null) continue; const details = el('details', 'sheet-section'); details.append(el('summary', '', key.replaceAll('_', ' '))); const lines = Array.isArray(value) ? value.map(asText) : typeof value === 'object' ? Object.entries(value).map(([label, item]) => `${label}: ${asText(item)}`) : [asText(value)]; lines.forEach(line => details.append(el('p', 'muted', line))); host.append(details); }
  }
  function renderMedia(media = {}) {
    const image = media.image, path = mediaPath(image?.url);
    if (image?.status === 'ready' && path) { if ($('scene-art').getAttribute('src') !== path) $('scene-art').src = path; $('scene-art').alt = asText(campaign?.presentation?.title || 'Your generated adventure scene'); $('scene-art').hidden = false; $('art-empty').hidden = true; }
    else { $('scene-art').hidden = true; $('art-empty').hidden = false; $('art-status').textContent = image?.status === 'pending' ? 'Your scene is being illustrated…' : image?.status === 'error' ? 'Scene illustration unavailable. Your adventure can continue.' : 'A world waiting to be imagined'; }
    const music = media.music, musicPath = music?.status === 'ready' ? mediaPath(music.url) : null;
    $('audio-toggle').disabled = !musicPath;
    $('audio-toggle').title = music?.status === 'pending' ? 'Your soundtrack is being composed' : music?.status === 'error' ? 'Soundtrack generation unavailable' : 'Play or pause generated music';
    if (musicPath && musicPath !== currentMusic) { currentMusic = musicPath; $('soundtrack').src = musicPath; if (musicRequested) playMusic(); }
    else if (!musicPath && currentMusic) { $('soundtrack').pause(); $('soundtrack').removeAttribute('src'); currentMusic = ''; }
    $('audio-toggle').textContent = !$('soundtrack').paused && musicPath ? 'Pause music' : 'Play music';
  }
  function render(state) {
    campaign = state;
    savedCampaign(state.id);
    $('welcome').hidden = true; $('dm-turn').hidden = false; $('composer').hidden = false;
    $('scene-title').textContent = state.presentation?.title || (state.stage === 'adventure' ? 'Your adventure unfolds' : 'Discover your character');
    $('stage-label').textContent = state.stage === 'adventure' ? 'THE ADVENTURE' : 'CHARACTER CREATION · D&D 2024';
    $('narration').textContent = state.presentation?.narration || (state.presentation?.status === 'pending' ? 'Your Dungeon Master is preparing your next moment…' : 'Tell your Dungeon Master about the character you would like to play.');
    $('campaign-state').textContent = `Saved · Revision ${state.revision} · ${state.stage === 'adventure' ? 'Adventure' : 'Character creation'}`;
    $('confirm-character').hidden = !state.character || state.stage === 'adventure';
    renderSurface(state.presentation?.surface);
    renderCharacter(state.character);
    const journal = $('journal'); journal.replaceChildren();
    for (const entry of (state.journal || []).slice(-8).reverse()) { const block = el('article', 'journal-entry'); block.append(el('p', 'journal-action', entry.action)); if (entry.outcome) block.append(el('p', 'muted', entry.outcome)); journal.append(block); }
    if (!journal.childNodes.length) journal.append(el('p', 'muted', 'Your decisions and their consequences will be recorded here.'));
    renderMedia(state.media);
    if (state.presentation?.status === 'error') notice('Your DM could not generate this turn. Your campaign is saved; send a message to try again.');
    updateCampaignList(); setBusy(busy);
  }
  function updateCampaignList() {
    const selector = $('campaign-select'); const ids = new Set(); selector.replaceChildren(el('option', '', 'Choose a saved campaign…')); selector.firstChild.value = '';
    for (const item of [...(campaign ? [campaign] : []), ...(status?.campaigns || [])]) { if (!item.id || ids.has(item.id)) continue; ids.add(item.id); const option = el('option', '', item.title || item.presentation?.title || item.character?.name || `Chronicle ${item.id.slice(0, 8)}`); option.value = item.id; selector.append(option); }
    selector.value = campaign?.id || '';
  }
  function pending(state) { return state.presentation?.status === 'pending' || Object.values(state.media || {}).some(item => item?.status === 'pending'); }
  function schedulePoll() {
    clearTimeout(pollTimer);
    if (!campaign || !pending(campaign)) { pollCount = 0; return; }
    if (pollCount >= 80) { notice('Generation is taking longer than expected. Your campaign is saved.', () => loadCampaign(campaign.id)); return; }
    const id = campaign.id, epoch = campaignEpoch;
    pollTimer = setTimeout(async () => { try { const state = await api(`/api/campaigns/${encodeURIComponent(id)}`); if (epoch !== campaignEpoch) return; render(state); pollCount++; schedulePoll(); } catch (error) { if (epoch === campaignEpoch) notice(error.message, () => loadCampaign(id)); } }, Math.min(2000 + pollCount * 300, 7000));
  }
  async function loadCampaign(id) {
    campaignEpoch++; const epoch = campaignEpoch; clearTimeout(pollTimer); setBusy(true); notice(''); surfaceSignature = ''; pollCount = 0;
    try { const state = await api(`/api/campaigns/${encodeURIComponent(id)}`); if (epoch === campaignEpoch) { render(state); schedulePoll(); } }
    catch (error) { notice(error.message, () => loadCampaign(id)); }
    finally { if (epoch === campaignEpoch) setBusy(false); }
  }
  async function createCampaign(requestId = crypto.randomUUID()) {
    if (busy) return;
    campaignEpoch++; clearTimeout(pollTimer); setBusy(true); notice(''); surfaceSignature = ''; pollCount = 0;
    try { const state = await api('/api/campaigns', {profile: {edition: '2024'}, request_id: requestId}); render(state); schedulePoll(); }
    catch (error) { notice(error.message, error.transport ? () => createCampaign(requestId) : null); }
    finally { setBusy(false); }
  }
  async function submitAction(text, intent = 'act', original = null) {
    if (busy || !campaign || (!text.trim() && intent !== 'confirm_character')) return;
    const body = original || {revision: campaign.revision, request_id: crypto.randomUUID(), action: text, intent};
    const id = campaign.id; clearTimeout(pollTimer); setBusy(true); notice('');
    try { const state = await api(`/api/campaigns/${encodeURIComponent(id)}/actions`, body); render(state); $('action').value = ''; pollCount = 0; schedulePoll(); }
    catch (error) {
      if (error.code === 409) { try { render(await api(`/api/campaigns/${encodeURIComponent(id)}`)); notice('This campaign changed in another window. Review the latest turn, then resend your decision.', () => submitAction(text, intent)); } catch (refreshError) { notice(refreshError.message, () => loadCampaign(id)); } }
      else notice(error.message, error.transport ? () => submitAction(text, intent, body) : null);
    } finally { setBusy(false); }
  }
  async function playMusic() { try { await $('soundtrack').play(); $('audio-toggle').textContent = 'Pause music'; } catch { musicRequested = false; $('audio-toggle').textContent = 'Play music'; notice('Music could not play. Select Play music to try again.'); } }
  $('start').addEventListener('click', () => createCampaign());
  $('new-campaign').addEventListener('click', () => createCampaign());
  $('campaign-select').addEventListener('change', event => { if (event.target.value) loadCampaign(event.target.value); });
  $('composer').addEventListener('submit', event => { event.preventDefault(); submitAction($('action').value); });
  $('confirm-character').addEventListener('click', () => submitAction('Begin adventure with this character', 'confirm_character'));
  $('retry').addEventListener('click', () => { const retry = retryOperation; notice(''); if (retry) retry(); });
  $('help-toggle').addEventListener('click', () => { $('help').hidden = !$('help').hidden; $('help-toggle').setAttribute('aria-expanded', String(!$('help').hidden)); });
  $('audio-toggle').addEventListener('click', () => { if ($('soundtrack').paused) { musicRequested = true; playMusic(); } else { musicRequested = false; $('soundtrack').pause(); $('audio-toggle').textContent = 'Play music'; } });
  $('scene-art').addEventListener('error', () => { $('scene-art').hidden = true; $('art-empty').hidden = false; $('art-status').textContent = 'Illustration could not load. Your adventure can continue.'; });
  $('soundtrack').addEventListener('error', () => { $('audio-toggle').textContent = 'Music unavailable'; $('audio-toggle').disabled = true; });
  async function connect() {
    setBusy(true);
    try { status = await api('/api/status'); $('provider-status').textContent = status.configured ? '● Live AI DM' : '○ AI provider not configured'; $('provider-status').classList.toggle('live', Boolean(status.configured)); updateCampaignList(); if (!status.configured) notice('Live generation needs a configured cloud provider on the server. No story generation is being simulated.'); const saved = savedCampaign(); if (saved) await loadCampaign(saved); }
    catch (error) { $('provider-status').textContent = '○ Connection unavailable'; notice(error.message, connect); }
    finally { setBusy(false); }
  }
  connect();
})();
