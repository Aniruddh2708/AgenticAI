/* VibeFinance terminal: no CDN, no API keys and no LLM-derived numeric fields.
   All agent labels, evidence, sources, actions and metrics come from the existing API.
   Values are inserted as text nodes to avoid interpreting retrieved documents as HTML. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const TICKERS = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ITC.NS'];
  const META = {
    momentum: ['M', 'Momentum Analyst', 'RSI · MACD · DMA'],
    volume: ['V', 'Volume Analyst', 'Z-score · price-volume'],
    sentiment: ['S', 'Sentiment Analyst', 'Corpus tone · lexicon'],
    filings: ['F', 'Filings & RAG Scout', 'Ticker-filtered retrieval'],
    risk: ['R', 'Portfolio Risk Guard', 'Limits · HHI · exposure']
  };
  const state = {
    session: null, profiles: [], profile: null, comparison: null, evaluation: null,
    token: '', busy: false, search: '', currentTab: 'overview'
  };
  const num = (value, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
  const pct = (value, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : '—';
  const val = (obj, key, fallback = null) => obj && obj[key] !== undefined && obj[key] !== null ? obj[key] : fallback;
  const shortTicker = (ticker) => String(ticker || '—').replace(/\.NS$/, '');
  function node(tag, className = '', text = null) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== null) result.textContent = String(text);
    return result;
  }
  function wipe(container) { container.replaceChildren(); return container; }
  function appendText(container, tag, className, text) { const item = node(tag, className, text); container.append(item); return item; }
  function clearAlert() { $('alert-region').replaceChildren(); }
  function alertMessage(message, type = 'info') {
    const banner = node('div', `alert ${type}`, message);
    wipe($('alert-region')).append(banner);
  }
  async function request(path, opts = {}, retry = true) {
    const headers = { ...(opts.headers || {}) };
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    let response;
    try { response = await fetch(path, { ...opts, headers, cache: 'no-store' }); }
    catch { throw new Error('Cannot contact VibeFinance API. Start the application with make demo and retry.'); }
    if (response.status === 401 && retry) {
      // Only a temporary in-memory demo token; never localStorage or a URL parameter.
      const entered = window.prompt('This demo uses a protected API. Enter its access token (kept only in this page until refresh):');
      if (entered) { state.token = entered.trim(); return request(path, opts, false); }
      throw new Error('Access token required. Production sign-in remains available in the legacy Streamlit client.');
    }
    if (!response.ok) {
      let reason = `HTTP ${response.status}`;
      try { const json = await response.json(); if (json.detail) reason = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail); }
      catch { /* Keep HTTP status. */ }
      throw new Error(reason);
    }
    if (response.status === 204) return null;
    return response.json();
  }
  function setBusy(busy) {
    state.busy = busy;
    $('run-analysis').disabled = busy;
    $('apply-settings').disabled = busy;
    $('run-analysis').textContent = busy ? '◌ Running…' : '＋ Run Audit';
    $('pipeline-status').textContent = busy ? 'Running five agents…' : (state.session ? 'Pipeline complete' : 'Awaiting analysis');
  }
  function selected() { return { ticker: $('ticker-select').value, user_id: $('user-select').value || 'arjun', sentiment_outage: $('outage-toggle').checked, missing_filing: $('filing-toggle').checked, live: false }; }
  async function loadProfiles() {
    const profiles = await request('/profiles');
    state.profiles = profiles;
    const old = $('user-select').value;
    wipe($('user-select'));
    profiles.forEach((p) => { const opt = node('option', '', p.name); opt.value = p.user_id; $('user-select').append(opt); });
    $('user-select').value = profiles.some(p => p.user_id === old) ? old : profiles.some(p => p.user_id === 'arjun') ? 'arjun' : profiles[0]?.user_id || '';
    updateProfile();
  }
  function updateProfile() {
    state.profile = state.profiles.find((p) => p.user_id === $('user-select').value) || null;
    showProfile();
  }
  async function runAudit() {
    if (state.busy) return;
    clearAlert(); setBusy(true);
    state.comparison = null;
    $('pipeline-status').textContent = 'Running agents in parallel';
    $('pipeline-start').textContent = 'Processing…';
    const input = selected();
    $('target-symbol').textContent = `TARGET: ${shortTicker(input.ticker)}`;
    $('pipeline-goal').textContent = `Evaluate ${shortTicker(input.ticker)} using cited signals & ${state.profile?.risk_tolerance || 'personal'} investor policy`;
    try {
      state.session = await request('/analyze', { method: 'POST', body: JSON.stringify(input) });
      renderAll();
      const warnings = state.session.warnings || [];
      if (warnings.length) alertMessage(`Degraded/important disclosures: ${warnings.join('  •  ')}`, 'info');
    } catch (error) {
      alertMessage(`Audit unavailable: ${error.message}`, 'error');
      $('pipeline-status').textContent = 'Audit failed';
    } finally { setBusy(false); }
  }
  function renderAll() {
    if (!state.session) return;
    renderTicker(); renderPipeline(); renderAgents(); renderFeed(); renderDecision(); renderPrice();
    renderSources(); renderReasoning(); renderMetrics(); showProfile();
  }
  function renderTicker() {
    const s = state.session, r = s.recommendation, m = s.metrics || {};
    $('ticker-action').textContent = r.action;
    $('ticker-action').className = `pill ${r.action.toLowerCase()}`;
    $('ticker-strength').textContent = pct(r.confidence);
    const cites = new Set((r.citations || []).map(c => c.chunk_id));
    $('ticker-citations').textContent = `${cites.size} session sources`;
    $('ticker-coverage').textContent = pct(m.claim_support_coverage);
    $('ticker-mode').textContent = String(s.data_mode || 'unavailable').toUpperCase();
    $('ticker-time').textContent = `${num(m.total_latency_ms, 0)} ms`;
    $('footer-health').textContent = `Target ${shortTicker(r.ticker)} · ${s.persistence?.status === 'saved' ? 'Audit saved' : 'Not saved'}`;
  }
  function renderPipeline() {
    const s = state.session;
    $('pipeline-status').textContent = (s.warnings || []).length ? 'Complete · caveats' : '3 of 3 complete';
    $('pipeline-start').textContent = `${(s.market_rows || []).length} price sessions`;
    const statuses = (s.recommendation.agent_outputs || []).map(a => a.status);
    const stages = [ ['stage-ingest', 'complete'], ['stage-agents', statuses.some(v => v !== 'ok') ? 'degraded' : 'complete'], ['stage-synthesis', 'complete'] ];
    stages.forEach(([id, cls]) => { $(id).className = `stage ${cls}`; });
    $('stage-ingest-text').textContent = `${s.data_mode} · ${s.retrieval_mode} retrieval`;
    $('stage-agents-text').textContent = `${statuses.filter(s => s === 'ok').length} ok · ${statuses.filter(s => s === 'degraded').length} degraded · ${statuses.filter(s => s === 'failed').length} failed`;
    $('stage-synthesis-text').textContent = `${s.recommendation.action} · ${(s.recommendation.conflicts || []).length} conflicts · ${s.persistence?.status || 'unsaved'}`;
  }
  function renderAgents() {
    const rows = wipe($('agents-body'));
    const outputs = state.session.recommendation.agent_outputs || [];
    $('agent-summary').textContent = `${outputs.length} typed outputs · ${pct(state.session.metrics?.claim_support_coverage)} claim support`;
    outputs.forEach((agent) => {
      const [avatar, title, method] = META[agent.dimension] || ['?', agent.dimension, 'Rule engine'];
      const tr = node('tr');
      const name = node('td'); const info = node('div', 'agent-name');
      info.append(node('span', `avatar ${agent.dimension}`, avatar));
      const labels = node('div'); labels.append(node('strong', '', title), node('small', '', agent.dimension.toUpperCase())); info.append(labels); name.append(info); tr.append(name);
      appendText(tr, 'td', 'mono muted', method);
      const status = node('td'); status.append(node('span', `label-chip ${agent.status}`, agent.status.toUpperCase())); tr.append(status);
      appendText(tr, 'td', 'mono accent', `${agent.label} · ${pct(agent.confidence)}`);
      appendText(tr, 'td', 'mono cyan', `${num(agent.latency_ms, 1)} ms`);
      const action = node('td'); const button = node('button', 'text-button', 'Inspect'); button.type = 'button'; button.addEventListener('click', () => { openTab('reasoning'); document.getElementById(`agent-${agent.dimension}`)?.scrollIntoView({ block: 'center' }); }); action.append(button); tr.append(action); rows.append(tr);
    });
  }
  function traceCards(container, steps) {
    wipe(container);
    (steps || []).forEach((trace, i) => {
      const card = node('article', 'trace-card');
      const heading = node('div', 'trace-heading');
      heading.append(node('span', 'trace-index', `STEP ${i + 1}`), node('strong', '', trace.step));
      card.append(heading, node('p', '', trace.detail)); container.append(card);
    });
    if (!steps?.length) appendText(container, 'p', 'empty-state', 'No trace is available.');
  }
  function renderFeed() { traceCards($('trace-feed'), state.session.trace); traceCards($('audit-steps'), state.session.trace); }
  function addNote(parent, text, kind = '') { parent.append(node('div', `note ${kind}`, text)); }
  function renderDecision() {
    const r = state.session.recommendation;
    $('decision-action').textContent = r.action;
    $('decision-action').className = `decision-action ${['REDUCE', 'AVOID'].includes(r.action) ? 'negative' : ['HOLD', 'WATCH'].includes(r.action) ? 'neutral' : ''}`;
    $('decision-confidence').textContent = pct(r.confidence);
    $('confidence-fill').style.width = `${Math.min(100, Math.max(0, (r.confidence || 0) * 100))}%`;
    $('recommendation-basis').textContent = r.decision_basis.replaceAll('_', ' ');
    $('decision-explanation').textContent = `Based on ${r.confidence_kind.replaceAll('_', ' ')}. This is not a probability of price gains or of a correct portfolio action.`;
    wipe($('decision-notes'));
    (r.personalization_notes || []).forEach(note => addNote($('decision-notes'), note));
    wipe($('decision-conflicts'));
    (r.conflicts || []).forEach(conflict => addNote($('decision-conflicts'), `Agent conflict: ${conflict}`, 'warning'));
    if (state.session.persistence?.status !== 'saved') addNote($('decision-notes'), state.session.persistence?.error || 'This session was not saved.', 'warning');
    $('decision-saving').textContent = r.disclaimer;
  }
  function drawChart(rows) {
    const target = wipe($('price-chart'));
    const values = (rows || []).map(r => Number(r.close)).filter(Number.isFinite);
    if (values.length < 2) { appendText(target, 'p', 'empty-state', 'Insufficient price data for a chart.'); return; }
    const w = 710, h = 170, pad = 15, lo = Math.min(...values), hi = Math.max(...values), spread = hi - lo || 1;
    const points = values.map((v, i) => `${pad + i * (w - 2 * pad) / (values.length - 1)},${h - pad - (v - lo) / spread * (h - 2 * pad)}`).join(' ');
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('preserveAspectRatio', 'none'); svg.setAttribute('aria-label', `Closing prices, ${values.length} sessions, min ${num(lo)}, max ${num(hi)}; simulated unless otherwise disclosed`);
    for (let i = 1; i <= 3; i++) {
      const line = document.createElementNS(svgNS, 'line'); line.setAttribute('x1', pad); line.setAttribute('x2', w - pad); line.setAttribute('y1', i * h / 4); line.setAttribute('y2', i * h / 4); line.setAttribute('stroke', '#223746'); line.setAttribute('stroke-dasharray', '4 5'); svg.append(line);
    }
    const polyline = document.createElementNS(svgNS, 'polyline'); polyline.setAttribute('fill', 'none'); polyline.setAttribute('stroke', '#4ade80'); polyline.setAttribute('stroke-width', '2.7'); polyline.setAttribute('vector-effect', 'non-scaling-stroke'); polyline.setAttribute('points', points); svg.append(polyline); target.append(svg);
  }
  function renderPrice() {
    drawChart(state.session.market_rows);
    $('market-source').textContent = `${state.session.data_mode} · ${state.session.market_source?.date || ''}`;
    const profile = state.profile, bars = wipe($('portfolio-bars')), metrics = wipe($('portfolio-metrics'));
    if (!profile) return;
    for (const [ticker, weight] of Object.entries(profile.holdings || {}).sort((a, b) => b[1] - a[1])) {
      const row = node('div'); const label = node('div', 'bar-label'); label.append(node('span', '', shortTicker(ticker)), node('span', '', pct(weight, 0))); row.append(label);
      const track = node('div', 'bar-track'); const fill = node('div', `bar-fill ${weight > profile.max_single_stock_pct ? 'high' : ''}`); fill.style.width = `${Math.max(0, Math.min(100, weight * 100))}%`; track.append(fill); row.append(track); bars.append(row);
    }
    const m = state.session.metrics || {};
    [['Concentration HHI', num(m.hhi_before, 3)], ['What-if HHI', num(m.hhi_after, 3)], ['Stock limit', pct(profile.max_single_stock_pct, 0)]].forEach(([label, value]) => {
      const item = node('span'); item.append(node('span', '', `${label}: `), node('strong', '', value)); metrics.append(item);
    });
  }
  function sourceIdentity(src) { return `${src.doc_title || src.source_id} [${src.date || 'snapshot'} · ${src.source_kind || 'unspecified'}]`; }
  function visibleSources() {
    const sessionSources = state.session?.sources || [];
    const allowed = new Set((state.session?.recommendation?.citations || []).map(c => c.chunk_id));
    const search = state.search.trim().toLowerCase();
    return sessionSources.filter(source => allowed.has(source.chunk_id) && (!search || [source.doc_title, source.excerpt, source.doc_type, source.source_id, source.document_text].some(t => String(t || '').toLowerCase().includes(search))));
  }
  function sourceCard(src) {
    const b = node('button', 'source-card'); b.type = 'button';
    b.append(node('span', 'source-title', sourceIdentity(src)), node('span', 'source-excerpt', src.excerpt || 'Source excerpt unavailable.'), node('span', 'source-id', `${src.source_id} · match ${pct(src.score)}`));
    b.addEventListener('click', () => showSource(src));
    return b;
  }
  function renderSources() {
    const sources = visibleSources(); const list = wipe($('source-list')); const preview = wipe($('overview-sources'));
    sources.forEach((src, index) => { list.append(sourceCard(src)); if (index < 3) preview.append(sourceCard(src)); });
    if (!sources.length) { appendText(list, 'p', 'empty-state', 'No cited sources match this query. Missing documents are not invented.'); appendText(preview, 'p', 'empty-state', 'No cited passages available.'); }
    $('source-count').textContent = `${sources.length} / ${state.session.sources.length} registered source snapshots`;
  }
  function showSource(src) {
    const dialog = $('source-dialog'); $('dialog-title').textContent = sourceIdentity(src);
    const body = wipe($('dialog-body'));
    appendText(body, 'p', 'mono cyan', `Source ID: ${src.source_id}  |  Chunk: ${src.chunk_id}  |  Relevance: ${pct(src.score)}`);
    appendText(body, 'h3', '', `Type: ${src.doc_type || 'unknown'} · source as-of ${src.date || 'not supplied'}`);
    if (src.source_kind === 'authentic') {
      appendText(body, 'p', 'footnote', `Operator-supplied source; identity and rights require review. Published: ${src.published_at}; available: ${src.available_at}. SHA-256: ${src.source_sha256}`);
      if (String(src.source_url).startsWith('https://')) { const link = node('a', '', 'Original source'); link.href = src.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; body.append(link); }
    }
    const passage = src.document_text || src.excerpt || '';
    const block = node('div', 'source-document');
    // Only exact excerpts are highlighted. Never mark text as verified if no match exists.
    const anchor = String(src.excerpt || '').trim();
    const exactSpan = Number.isInteger(src.span_start) && Number.isInteger(src.span_end) && passage.slice(src.span_start, src.span_end) === src.excerpt;
    const idx = exactSpan ? src.span_start : (anchor.length ? passage.indexOf(anchor) : -1);
    if (idx >= 0) { block.append(document.createTextNode(passage.slice(0, idx)), node('mark', 'highlight', passage.slice(idx, idx + anchor.length)), document.createTextNode(passage.slice(idx + anchor.length))); }
    else { block.append(document.createTextNode(passage)); appendText(body, 'p', 'footnote', 'Exact highlight unavailable for this shortened source excerpt. Full retrieved passage shown without a fabricated match.'); }
    body.append(block); dialog.showModal();
  }
  function renderReasoning() {
    const r = state.session.recommendation;
    const chain = wipe($('reasoning-chain'));
    (r.reasoning_chain || []).forEach((reason, i) => { const item = node('div', 'reason-step'); item.append(node('span', 'step-number', String(i + 1).padStart(2, '0')), node('p', '', reason)); chain.append(item); });
    const agents = wipe($('reasoning-agents'));
    (r.agent_outputs || []).forEach(a => {
      const card = node('article', 'agent-card'); card.id = `agent-${a.dimension}`;
      appendText(card, 'h3', '', `${META[a.dimension]?.[1] || a.dimension} · ${a.label}`);
      appendText(card, 'p', 'caption', `STRENGTH ${pct(a.confidence)}  ·  STATUS ${a.status.toUpperCase()}  ·  ${num(a.latency_ms)} ms`);
      if (a.degraded_reason) appendText(card, 'p', 'note warning', a.degraded_reason);
      const ul = node('ul'); (a.evidence || []).forEach(e => appendText(ul, 'li', '', e)); if (!a.evidence?.length) appendText(ul, 'li', 'muted', 'No supported claim available.'); card.append(ul);
      const sources = a.citations || []; if (sources.length) {
        const area = node('div', 'button-row'); sources.forEach(src => {
          const b = node('button', 'text-button', `Source: ${src.source_id}`); b.type = 'button'; b.addEventListener('click', () => showSource(state.session.sources.find(s => s.chunk_id === src.chunk_id) || src)); area.append(b);
        }); card.append(area);
      }
      agents.append(card);
    });
    const specs = wipe($('model-specs'));
    (r.agent_outputs || []).forEach(a => { const card = node('div', 'agent-card'); appendText(card, 'h3', '', META[a.dimension]?.[1] || a.dimension); appendText(card, 'p', 'muted', META[a.dimension]?.[2] || 'Deterministic rules'); appendText(card, 'p', 'caption', `${a.label} • ${pct(a.confidence)} • ${a.status} • ${num(a.latency_ms)} ms`); specs.append(card); });
  }
  function metricCard(key, value, description) { const card = node('div', 'metric-card'); card.append(node('div', 'metric-label', key), node('strong', 'metric-value', value), node('div', 'metric-description', description)); return card; }
  function renderMetrics() {
    const m = state.session.metrics || {}, cards = wipe($('metric-cards'));
    [
      ['TOTAL LATENCY', `${num(m.total_latency_ms, 0)} ms`, 'Measured API pipeline duration'],
      ['PARALLEL AGENT WINDOW', `${num(m.parallel_agents_ms, 0)} ms`, 'Actual concurrent execution'],
      ['EST. SPEEDUP', `${num(m.estimated_parallel_speedup, 2)}×`, 'Sum of agent times / parallel window'],
      ['SUPPORTED CLAIMS', pct(m.claim_support_coverage), `${val(m, 'supported_claim_count', 0)} of ${val(m, 'submitted_claim_count', 0)} submitted`],
      ['DEGRADED AGENTS', String(val(m, 'degraded_agent_count', 0)), 'Evidence gaps explicitly disclosed'],
      ['FAILED AGENTS', String(val(m, 'failed_agent_count', 0)), 'Failures bounded by timeout'],
      ['HHI BEFORE', num(m.hhi_before, 3), 'Portfolio concentration'],
      ['HHI WHAT-IF', num(m.hhi_after, 3), 'Illustration, not a transaction']
    ].forEach(([key, value, desc]) => cards.append(metricCard(key, value, desc)));
    const latencies = m.agent_latency_ms || {}, bars = wipe($('latency-bars'));
    const max = Math.max(1, ...Object.values(latencies).filter(Number.isFinite));
    Object.entries(latencies).forEach(([name, ms]) => {
      const item = node('div', 'latency-row'); const label = node('div', 'bar-label'); label.append(node('span', '', name.toUpperCase()), node('span', '', `${num(ms, 1)} ms`)); item.append(label);
      const track = node('div', 'bar-track'); const fill = node('div', 'bar-fill'); fill.style.width = `${ms / max * 100}%`; track.append(fill); item.append(track); bars.append(item);
    });
  }
  async function loadEvaluation() {
    const results = $('evaluation-results'); results.textContent = 'Loading deterministic synthetic evaluation…';
    try { state.evaluation = await request('/evaluation'); const ev = state.evaluation; wipe(results);
      const summary = node('div', 'evaluation-summary');
      [['Technical hit rate', pct(ev.hit_rate)], ['Random baseline', pct(ev.random_hit_rate)], ['Always-up baseline', pct(ev.buy_hold_hit_rate)], ['Brier score', num(ev.brier_score, 4)], ['Evaluated sample', String(ev.sample_size)], ['30-session horizon', `${ev.horizon_sessions} trading sessions`]].forEach(([k, v]) => summary.append(metricCard(k, v, 'Synthetic holdout evaluation')));
      results.append(summary, node('p', 'note warning', ev.limitations || 'Simulation only. No demonstrated investment advantage.'));
      const head = node('h3', '', 'Probability calibration (not recommendation strength)'); results.append(head);
      renderCalibration(results, ev.calibration || []);
      for (const b of ev.calibration || []) appendText(results, 'p', 'footnote', `${b.bucket}: ${b.count} samples · predicted up ${pct(b.mean_probability_up)} · actual up ${pct(b.realized_up_rate)}`);
    } catch (error) { results.textContent = `Evaluation unavailable: ${error.message}`; }
  }
  async function loadForecastDevelopment() {
    const results = $('forecast-development-results');
    results.textContent = 'Loading historical research…';
    try {
      const report = await request('/evaluation/forecast/development');
      wipe(results);
      if (!report.available) { results.textContent = report.reason; return; }
      results.append(node('p', 'note warning', 'Development results only. No new holdout or predictive advantage established. Portfolio actions use the existing safeguards.'));
      results.append(node('p', 'footnote', `Model ${report.model_id.slice(0, 12)} · as of ${report.as_of} · ${report.age_calendar_days} calendar days old · horizon: 30 observed vendor rows. Not a current market forecast.`));
      const summary = node('div', 'evaluation-summary');
      const dev = report.development;
      [['Development Brier', num(dev.probability_metrics[report.probability_model].brier, 4)],
       ['50% baseline Brier', num(dev.probability_metrics.constant_half.brier, 4)],
       ['Return MAE', pct(dev.return_metrics[report.return_model].mae_return)],
       ['Zero-return MAE', pct(dev.return_metrics.zero.mae_return)],
       ['Shared origin dates', String(dev.shared_origins)],
       ['Learned model admitted', 'No']].forEach(([key, value]) => summary.append(metricCard(key, value, 'Exploratory chronological development')));
      results.append(summary, node('p', 'footnote', `Selected probability: ${report.probability_model}; return: ${report.return_model}. ${report.admission.reason}`));
      for (const [name, interval] of Object.entries(report.prequential_intervals.methods || {})) {
        results.append(node('p', 'footnote', `${name}: marginal coverage ${pct(interval.coverage)}, width ${pct(interval.mean_width)}, interval score ${pct(interval.interval_score)}; simultaneous coverage ${pct(interval.simultaneous_coverage.coverage)} across ${interval.simultaneous_coverage.complete_origins} complete origins. Development estimates only.`));
      }
    } catch (error) { results.textContent = `Research unavailable: ${error.message}`; }
  }
  function renderCalibration(parent, buckets) {
    // A reliability curve for the *separately evaluated direction classifier*.
    // The recommendation confidence is not a success probability.
    const data = buckets.filter(b => Number.isFinite(b.mean_probability_up) && Number.isFinite(b.realized_up_rate));
    if (!data.length) return;
    const NS = 'http://www.w3.org/2000/svg', w = 460, h = 235, margin = 30;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Calibration: actual positive return frequency versus estimated probability from historical synthetic windows');
    svg.style.width = '100%'; svg.style.maxWidth = '460px'; svg.style.background = '#0b1016';
    svg.style.border = '1px solid #243143'; svg.style.borderRadius = '7px';
    const at = (x,y) => [margin + x * (w - 2 * margin), h - margin - y * (h - 2 * margin)];
    const line = (a,b,color,dash = '') => { const shape = document.createElementNS(NS, 'line');
      shape.setAttribute('x1', a[0]); shape.setAttribute('y1', a[1]); shape.setAttribute('x2', b[0]); shape.setAttribute('y2', b[1]);
      shape.setAttribute('stroke', color); shape.setAttribute('stroke-width', '1.5');
      if(dash) shape.setAttribute('stroke-dasharray', dash); svg.append(shape); };
    const text = (x,y,value) => {const t = document.createElementNS(NS, 'text');t.setAttribute('x',x);t.setAttribute('y',y);t.setAttribute('fill','#8293ab');t.setAttribute('font-size','11');t.textContent=value;svg.append(t);};
    for(let i=0;i<=4;i++){const p=i/4;line(at(0,p),at(1,p),'#243143','2 5');text(4,at(0,p)[1]+4,`${Math.round(p*100)}%`);text(at(p,0)[0]-9,h-8,`${Math.round(p*100)}`);}
    line(at(0,0),at(1,1),'#637689','5 5');
    for(let i=1;i<data.length;i++)line(at(data[i-1].mean_probability_up,data[i-1].realized_up_rate),at(data[i].mean_probability_up,data[i].realized_up_rate),'#4ade80');
    data.forEach(b=>{const [cx,cy]=at(b.mean_probability_up,b.realized_up_rate);const circle=document.createElementNS(NS,'circle');circle.setAttribute('cx',cx);circle.setAttribute('cy',cy);circle.setAttribute('r','4');circle.setAttribute('fill','#38bdf8');svg.append(circle);});
    parent.append(svg);
    appendText(parent,'p','footnote','X: fitted P(up), Y: observed up frequency; dashed diagonal = ideal calibration. Values use code-computed backtest samples.');
  }
  async function scanWatchlist() {
    const button = $('scan-watchlist'), target = wipe($('watchlist-results'));
    button.disabled = true; target.append(node('p','empty-state','Analyzing five NSE tickers…'));
    try {
      const data = await request('/watchlist',{method:'POST',body:JSON.stringify({user_id:$('user-select').value,tickers:TICKERS})});
      wipe(target);
      for(const session of data.sessions || []) {
        const rec = session.recommendation, item=node('div','reason-step');
        item.append(node('span','step-number',shortTicker(rec.ticker)),node('p','',`${rec.action} · strength ${pct(rec.confidence)} · basis ${rec.decision_basis.replaceAll('_',' ')}`));
        target.append(item);
      }
      appendText(target,'p','note',`${(data.alerts||[]).length} personalized action flags. These are simulated research signals, not trading instructions.`);
    } catch(error) {target.replaceChildren(node('p','note warning',`Watchlist unavailable: ${error.message}`));}
    finally {button.disabled=false;}
  }
  function showProfile() {
    const p = state.profile; if (!p) return;
    const target = wipe($('profile-detail'));
    appendText(target, 'h3', '', p.name);
    appendText(target, 'p', '', `Risk tolerance: ${p.risk_tolerance}; horizon: ${p.horizon_months} months; single-stock ceiling: ${pct(p.max_single_stock_pct, 0)}.`);
    appendText(target, 'p', 'muted', `Holdings: ${Object.entries(p.holdings).map(([ticker, weight]) => `${shortTicker(ticker)} ${pct(weight, 0)}`).join(' · ')}`);
    appendText(target, 'p', 'muted', `Behavior flags: ${JSON.stringify(p.behavior)}`);
  }
  function editProfile() {
    const p = state.profile, target = $('profile-editor'); if (!p) return;
    if (!target.hidden) { target.hidden = true; return; } target.hidden = false; wipe(target);
    const form = node('form');
    const makeInput = (name, label, value, type = 'number', step = '1') => { const wrapper = node('div', 'field'); const caption = node('label', '', label); caption.htmlFor = `profile-${name}`; const input = node('input'); input.id = `profile-${name}`; input.name = name; input.type = type; input.value = value; if (type === 'number') { input.step = step; input.min = '0'; } wrapper.append(caption, input); form.append(wrapper); return input; };
    makeInput('name', 'Display name', p.name, 'text'); makeInput('horizon_months', 'Investment horizon (months)', p.horizon_months); makeInput('max_single_stock_pct', 'Single stock ceiling (0–1 fraction)', p.max_single_stock_pct, 'number', '0.01');
    makeInput('holdings', 'Holdings JSON (fractions between 0 and 1)', JSON.stringify(p.holdings), 'text');
    const save = node('button', 'primary-button', 'Save profile'); save.type = 'submit'; form.append(save);
    form.addEventListener('submit', async (event) => {
      event.preventDefault(); const fd = new FormData(form);
      try {
        const update = { ...p, name: String(fd.get('name')), horizon_months: Number(fd.get('horizon_months')), max_single_stock_pct: Number(fd.get('max_single_stock_pct')), holdings: JSON.parse(String(fd.get('holdings'))) };
        const saved = await request(`/profiles/${encodeURIComponent(p.user_id)}`, { method: 'PUT', body: JSON.stringify(update) });
        state.profiles = state.profiles.map(x => x.user_id === saved.user_id ? saved : x); state.profile = saved;
        target.hidden = true; showProfile(); alertMessage('Profile updated. Run a new audit to recompute the personalized recommendation.', 'info');
      } catch (error) { alertMessage(`Profile not saved: ${error.message}`, 'error'); }
    }); target.append(form);
  }
  async function saveDecision(action) {
    const s = state.session; if (!s) { alertMessage('Run an audit before recording decisions.'); return; }
    if (s.persistence?.status !== 'saved') { alertMessage('This audit is not persisted; decision cannot be saved.', 'error'); return; }
    try { await request(`/sessions/${encodeURIComponent(s.session_id)}/decision`, { method: 'POST', body: JSON.stringify({ decision: action }) }); $('decision-saving').textContent = `Recorded ${action.toUpperCase()} decision for session ${s.session_id}. No trade was executed.`; }
    catch (error) { alertMessage(`Decision could not be saved: ${error.message}`, 'error'); }
  }
  async function loadHistory() {
    const target = wipe($('history-list'));
    try {
      const sessions = await request(`/history/${encodeURIComponent($('user-select').value)}?limit=10`);
      if (!sessions.length) { appendText(target, 'p', 'muted', 'No saved audits for this user.'); return; }
      sessions.forEach(entry => {
        const id = entry.session_id;
        if (!id) return;
        const b = node('button', 'history-button', `${entry.ticker || entry.recommendation?.ticker || 'Analysis'} · ${entry.action || entry.recommendation?.action || 'Saved audit'} · ${id.slice(0, 9)}`);
        b.addEventListener('click', async () => { try { state.session = await request(`/sessions/${encodeURIComponent(id)}`); renderAll(); openTab('overview'); }
          catch (error) { alertMessage(`Could not load audit: ${error.message}`, 'error'); } }); target.append(b);
      });
    } catch (error) { appendText(target, 'p', 'note warning', `History unavailable: ${error.message}`); }
  }
  async function compareUsers() {
    $('run-compare').disabled = true; const target = wipe($('compare-results')); target.append(node('p', 'empty-state', 'Computing the same market input for all profiles…'));
    try {
      state.comparison = await request('/compare', { method: 'POST', body: JSON.stringify(selected()) }); wipe(target);
      state.comparison.forEach(session => {
        const r = session.recommendation, p = state.profiles.find(p => p.user_id === r.user_id);
        const card = node('article', 'compare-card'); card.append(node('h3', '', p?.name || r.user_id), node('p', 'muted', `${p?.risk_tolerance || 'unknown'} · ${pct(p?.max_single_stock_pct)} max position`), node('div', 'action', r.action), node('p', 'cyan mono', `Evidence strength: ${pct(r.confidence)}`));
        appendText(card, 'p', 'muted', `Basis: ${r.decision_basis.replaceAll('_', ' ')}`);
        (r.personalization_notes || []).forEach(t => addNote(card, t));
        (r.conflicts || []).forEach(t => addNote(card, `Conflict: ${t}`, 'warning'));
        if (session.warnings?.length) addNote(card, `Caveats: ${session.warnings.join('; ')}`, 'warning');
        target.append(card);
      });
      if (!state.comparison.length) target.append(node('p', 'empty-state', 'No profiles returned.'));
    } catch (error) { target.replaceChildren(node('p', 'note warning', `Comparison unavailable: ${error.message}`)); }
    finally { $('run-compare').disabled = false; }
  }
  function openTab(name) {
    if (!$(`view-${name}`)) return;
    state.currentTab = name;
    document.querySelectorAll('[data-tab]').forEach(b => { const active = b.dataset.tab === name; b.classList.toggle('selected', active); if (b.classList.contains('nav-tab')) b.setAttribute('aria-current', active ? 'page' : 'false'); });
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active-view', v.id === `view-${name}`));
    if (name === 'models') loadHistory();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function setSearch(value) { state.search = value || ''; $('global-search').value = state.search; if (state.session) renderSources(); }
  function wireEvents() {
    $('run-analysis').addEventListener('click', runAudit);
    $('toggle-settings').addEventListener('click', () => { const panel = $('settings-panel'); panel.hidden = !panel.hidden; $('toggle-settings').setAttribute('aria-expanded', String(!panel.hidden)); });
    $('apply-settings').addEventListener('click', () => { updateProfile(); $('settings-panel').hidden = true; $('toggle-settings').setAttribute('aria-expanded', 'false'); runAudit(); });
    $('user-select').addEventListener('change', updateProfile);
    document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => openTab(b.dataset.tab)));
    $('global-search').addEventListener('input', e => setSearch(e.target.value));
    $('global-search').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); openTab('sources'); } });
    $('query-form').addEventListener('submit', e => { e.preventDefault(); setSearch($('query-input').value); openTab('sources'); });
    document.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); $('global-search').focus(); } });
    $('close-source').addEventListener('click', () => $('source-dialog').close());
    $('source-dialog').addEventListener('click', e => { if (e.target === $('source-dialog')) $('source-dialog').close(); });
    $('run-compare').addEventListener('click', compareUsers);
    $('load-evaluation').addEventListener('click', loadEvaluation);
    $('load-forecast-development').addEventListener('click', loadForecastDevelopment);
    $('edit-profile').addEventListener('click', editProfile);
    $('load-history').addEventListener('click', loadHistory);
    $('scan-watchlist').addEventListener('click', scanWatchlist);
    document.querySelectorAll('[data-decision]').forEach(b => b.addEventListener('click', () => saveDecision(b.dataset.decision)));
  }
  async function init() {
    wireEvents();
    try {
      await loadProfiles();
      const health = await request('/health');
      $('footer-version').textContent = health.revision ? `Revision ${health.revision.slice(0, 8)}` : 'Local research build';
      if (health.status !== 'ok') alertMessage('Backend reports degraded operation; analysis will disclose limitations.', 'info');
      await runAudit();
    } catch (error) { alertMessage(`Dashboard startup: ${error.message}`, 'error'); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
