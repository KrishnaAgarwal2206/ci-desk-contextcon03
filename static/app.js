const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
async function post(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body || {}) });
  let j = {}; try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(j.detail || j.error || r.statusText);
  return j;
}
// persona tabs (remember choice per viewer)
function showPersona(p) {
  $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.p === p));
  $$('.persona').forEach(d => d.hidden = d.dataset.p !== p);
  try { localStorage.setItem('persona', p); } catch (e) {}
}
$$('.tab').forEach(t => t.onclick = () => showPersona(t.dataset.p));
try { const p = localStorage.getItem('persona'); if (p && $(`.tab[data-p="${p}"]`)) showPersona(p); } catch (e) {}

// poll while running
const st = $('#status');
if (st && st.dataset.status === 'running') {
  setTimeout(async function poll() {
    const j = await (await fetch(`/api/requests/${st.dataset.rid}/status`)).json();
    st.textContent = j.status + ' · ' + j.steps.join(' → ');
    if (j.status === 'running') setTimeout(poll, 1500); else location.reload();
  }, 1500);
}
const reviewer = () => ($('#reviewer') && $('#reviewer').value.trim()) || '';
const fbGo = $('#fb-go');
if (fbGo) fbGo.onclick = async () => {
  const m = $('#fb-msg'); m.textContent = ' Interpreting…';
  try { const j = await post('/api/feedback', { persona_id: $('#fb-persona').value, text: $('#fb').value });
    m.textContent = ` Proposal #${j.id}: ${j.state} (${j.parser})`; setTimeout(() => location.reload(), 600);
  } catch (e) { m.textContent = ' ' + e.message; }
};
$$('.approve').forEach(b => b.onclick = async () => {
  const name = reviewer() || prompt('Reviewer name (required for approval):');
  if (!name) return;
  const hi = b.dataset.risk === 'high' ? confirm('High-risk proposal. Confirm activation?') : false;
  try { const j = await post(`/api/proposals/${b.dataset.id}/approve`, { reviewer: name, confirm_high_risk: hi });
    alert(`Activated ${j.persona_id} policy v${j.version}. Other persona unchanged.`); location.reload();
  } catch (e) { alert(e.message); }
});
$$('.reject').forEach(b => b.onclick = async () => {
  try { await post(`/api/proposals/${b.dataset.id}/reject`, { reviewer: reviewer() || 'reviewer' }); location.reload(); } catch (e) { alert(e.message); }
});
$$('.rollback').forEach(b => b.onclick = async () => {
  const name = reviewer() || prompt('Reviewer name:'); if (!name) return;
  try { await post(`/api/personas/${b.dataset.p}/rollback`, { to_version: +b.dataset.v, reviewer: name }); location.reload(); } catch (e) { alert(e.message); }
});
const rec = $('#reconcile');
if (rec) rec.onclick = async () => {
  $('#w-msg').textContent = 'Reconciling…';
  try { const j = await post(`/api/watches/${rec.dataset.id}/reconcile`); $('#w-msg').textContent = JSON.stringify(j); setTimeout(() => location.reload(), 1200); }
  catch (e) { $('#w-msg').textContent = e.message; }
};
const wt = $('#wtest');
if (wt) wt.onclick = async () => {
  try { await post(`/api/watches/${wt.dataset.id}/test`); $('#w-msg').textContent = 'Test sent (free, metadata.test=true). Refresh to see the envelope.'; }
  catch (e) { $('#w-msg').textContent = e.message; }
};
$$('.choose').forEach(b => b.onclick = async () => {
  b.textContent = 'resolving + fetching evidence…'; b.disabled = true;
  try { await post(`/api/entities/${b.dataset.e}/choose`, { crustdata_company_id: +b.dataset.c }); location.reload(); }
  catch (e) { alert(e.message); b.disabled = false; b.textContent = 'use this'; }
});
