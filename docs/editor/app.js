'use strict';
const $ = id => document.getElementById(id);
let locale = TowerI18n.locale(location.search), lastStatus = '', lastError = false, lastProject = '';
const display = value => TowerI18n.text(value, locale);
function project(message) { lastProject = message; $('project').textContent = display(message); }
const fileMode = document.documentElement.dataset.mode === 'file' || new URLSearchParams(location.search).get('mode') === 'file' || !['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname);
let baseline, current, token, selected, monsters = [], names = {}, nameSources = {}, busy = false, store, fileName = 'tower-project.json', exportPending = false;
const clone = value => JSON.parse(JSON.stringify(value));
function status(message, error = false) { lastStatus = message; lastError = error; $('status').textContent = display(message); $('status').className = error ? 'error' : ''; }
async function request(path, options = {}) {
  const response = await fetch(path, {cache: 'no-store', ...options});
  const body = await response.json();
  if (!response.ok) {
    const detail = (body.conflicts || []).map(c => `${c.path}: loaded ${c.expected}, current ${c.current}`).join('\n');
    throw new Error((body.error || `Request failed (${response.status})`) + (detail ? '\n' + detail : ''));
  }
  return body;
}
function changes() {
  if (!current) return [];
  const result = [];
  const add = (path, expected, value) => { if (expected !== value) result.push({path, expected, value}); };
  add('wave_count', baseline.wave_count, current.wave_count);
  current.waves.forEach((wave, wi) => {
    add(`waves/${wi + 1}/group_count`, baseline.waves[wi].group_count, wave.group_count);
    wave.groups.forEach((group, gi) => ['mob_id', 'count'].forEach(field => add(`waves/${wi + 1}/groups/${gi + 1}/${field}`, baseline.waves[wi].groups[gi][field], group[field])));
  });
  return result;
}
function valid() {
  if (!current) return false;
  try { TowerBrowser.validateFloor(current); return true; } catch (_) { return false; }
}
function controls() {
  $('save').disabled = busy || !changes().length || !valid();
  $('floor').disabled = busy || !current;
  $('reload').disabled = busy || !current;
  $('wave-count').disabled = busy || !current;
  $('waves').querySelectorAll('input,select').forEach(el => { el.disabled = busy; });
  $('open').disabled = $('example').disabled = busy;
  $('download').disabled = busy || !store || !!changes().length;
}
function node(tag, text, className) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = display(text); if (className) el.className = className; return el;
}
function number(value, min, max, onChange) {
  const input = node('input'); Object.assign(input, {type:'number', value, min, max, step:1});
  input.addEventListener('input', () => onChange(input.value === '' ? NaN : Number(input.value))); return input;
}
function monsterLabel(mob) { return TowerI18n.monsterLabel(mob, names, locale, nameSources); }
function render() {
  $('heading').textContent = display(`Floor ${current.floor}`);
  $('wave-count').value = current.wave_count;
  $('waves').replaceChildren();
  current.waves.forEach((wave, wi) => {
    const inactive = wi >= current.wave_count;
    if (inactive && !$('show-hidden').checked) return;
    const card = node('article', undefined, `wave${inactive ? ' inactive' : ''}`);
    const head = node('div', undefined, 'wave-head');
    head.append(node('h3', `Wave ${wi + 1}${inactive ? ' · inactive, retained' : ''}`));
    const label = node('label', 'Active groups ');
    label.append(number(wave.group_count, 1, 4, value => { wave.group_count = value; render(); }));
    const total = wave.groups.slice(0, wave.group_count).reduce((n, g) => n + g.count, 0);
    head.append(label, node('span', `Active total ${total} / 8`, total < 1 || total > 8 ? 'invalid' : ''));
    const groups = node('div', undefined, 'groups');
    wave.groups.forEach((group, gi) => {
      const hidden = gi >= wave.group_count;
      if (hidden && !$('show-hidden').checked) return;
      const row = node('div', undefined, 'group');
      row.append(node('span', `Group ${gi + 1}${hidden ? ' · retained' : ''}`, hidden ? 'hidden-label' : ''));
      const mobLabel = node('label', 'Monster');
      if (monsters.length) {
        const select = node('select'); select.setAttribute('aria-label', display(`Wave ${wi + 1} group ${gi + 1} monster`));
        const entries = monsters.slice();
        if (!entries.some(m => m.id === group.mob_id)) entries.unshift({id:group.mob_id});
        for (const mob of entries) {
          const option = node('option', monsterLabel(mob)); option.value = mob.id; select.append(option);
        }
        select.value = group.mob_id;
        select.onchange = () => { group.mob_id = Number(select.value); controls(); };
        mobLabel.append(select);
      } else mobLabel.append(number(group.mob_id, 1, 200000, value => { group.mob_id = value; controls(); }));
      const countLabel = node('label', 'Count');
      countLabel.append(number(group.count, 0, 8, value => {
        group.count = value; const n = wave.groups.slice(0, wave.group_count).reduce((sum, g) => sum + g.count, 0);
        head.lastChild.textContent = display(`Active total ${n} / 8`); head.lastChild.className = n < 1 || n > 8 || !Number.isFinite(n) ? 'invalid' : ''; controls();
      }));
      row.append(mobLabel, countLabel); groups.append(row);
    });
    card.append(head, groups); $('waves').append(card);
  }); controls();
}
async function load(fid) {
  busy = true; controls(); status(`Loading floor ${fid}…`);
  try {
    const floor = fileMode ? store.floor(fid) : (await request(`/api/floors/${fid}`)).floor;
    baseline = clone(floor); current = clone(floor); selected = fid; $('floor').value = fid;
    render(); status(`Floor ${fid} loaded. Inactive values are retained.${fileMode && exportPending ? ' Staged changes still need a download.' : ''}`);
  } catch (error) { status(error.message, true); $('floor').value = selected || ''; }
  finally { busy = false; controls(); }
}
function floorOptions(floors) {
  $('floor').replaceChildren();
  for (const floor of floors) { const option = node('option', `Floor ${floor.floor}`); option.value = floor.floor; $('floor').append(option); }
}
function discardFloor() { return !changes().length || confirm(display('Discard unstaged changes to this floor?')); }
function replaceProject() { return !(changes().length || exportPending) || confirm(display('Replace the browser project and discard changes that have not been downloaded?')); }
async function openText(text, name) {
  // Validate the entire new document before replacing the current browser project.
  const next = TowerBrowser.BrowserStore.fromText(text);
  store = next; fileName = name; exportPending = false; current = baseline = undefined;
  monsters = store.catalog(); const meta = store.metadata(); floorOptions(meta.floors);
  project(`${fileName} · ${meta.floors.length} floors · browser copy`);
  await load(meta.floors[0].floor);
}
$('floor').onchange = () => {
  if (!discardFloor()) { $('floor').value = selected; return; }
  load(Number($('floor').value));
};
$('reload').onclick = () => { if (discardFloor()) load(selected); };
$('wave-count').oninput = () => { current.wave_count = $('wave-count').value === '' ? NaN : Number($('wave-count').value); render(); };
$('show-hidden').onchange = () => { if (current) render(); };
$('save').onclick = async () => {
  const patch = changes(); if (!patch.length || !valid()) return;
  busy = true; controls(); status(fileMode ? 'Staging changed fields in the browser…' : 'Saving changed fields…');
  try {
    const data = fileMode ? store.patch(selected, patch) : await request(`/api/floors/${selected}`, {method:'PATCH', headers:{'Content-Type':'application/json','X-Tower-Token':token}, body:JSON.stringify({changes:patch})});
    baseline = clone(data.floor); current = clone(data.floor); if (fileMode) exportPending = true; render();
    status(fileMode ? `${data.saved_fields} fields staged in this browser. Download JSON to keep the complete project; your original file has not changed.` : `${data.saved_fields} fields saved. Unrelated edits were merged. Game installation remains a separate step.`);
  } catch (error) { status(error.message + '\nYour edits are retained. Review the issue, then reload if needed.', true); }
  finally { busy = false; controls(); }
};
$('open').onclick = () => { if (replaceProject()) $('file-picker').click(); };
$('file-picker').onchange = async () => {
  const file = $('file-picker').files[0]; if (!file) return;
  busy = true; controls();
  try {
    if (file.size > 16000000) throw new Error('Project exceeds 16 MB');
    await openText(await file.text(), file.name);
  } catch (error) { status(`Could not open JSON: ${error.message}. The previous browser project is retained.`, true); }
  finally { $('file-picker').value = ''; busy = false; controls(); }
};
$('example').onclick = async () => {
  if (!replaceProject()) return;
  busy = true; controls(); status('Loading example…');
  try {
    const response = await fetch('./sample-project.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`Example request failed (${response.status})`);
    await openText(await response.text(), 'tower-example.json');
  } catch (error) { status(`Could not load example: ${error.message}`, true); }
  finally { busy = false; controls(); }
};
$('download').onclick = () => {
  if (!store || changes().length) return;
  try {
    const url = URL.createObjectURL(new Blob([store.serialize()], {type:'application/json;charset=utf-8'}));
    const anchor = node('a'); anchor.href = url; anchor.download = TowerI18n.downloadName(fileName, locale);
    document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
    exportPending = false;
    status('Download requested. Confirm that your browser saved the JSON. Your original file has not changed; no game files were written.');
  } catch (error) { status(`Download failed: ${error.message}`, true); }
};
window.addEventListener('beforeunload', event => { if (changes().length || exportPending) { event.preventDefault(); event.returnValue = ''; } });
function translatePage() {
  document.documentElement.lang = locale;
  document.querySelector('nav').setAttribute('aria-label', locale === 'ko' ? '언어' : 'Language');
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = display(el.dataset.i18n); });
  $('lang-en').setAttribute('aria-current', locale === 'en' ? 'page' : 'false');
  $('lang-ko').setAttribute('aria-current', locale === 'ko' ? 'page' : 'false');
  $('mode-badge').textContent = display(fileMode ? 'Browser JSON editor' : 'Authoring JSON editor');
  $('save').textContent = display(fileMode ? 'Stage floor changes' : 'Save changed fields');
  $('mode-help').textContent = display(fileMode ? 'Staging updates only this browser copy. Download JSON to retain your work. Reopen a file to see external edits.' : 'Saving updates the authoring JSON. Game installation remains a separate step.');
  $('mode-footer').textContent = display(fileMode ? 'No uploads, game writes, installation or automatic file overwrites. Downloads contain the complete authoring document.' : 'No automatic installation or restart. Previous JSON versions are retained beside the project in its .backups folder.');
  if (lastProject) project(lastProject);
  if (current) { floorOptions(fileMode ? store.metadata().floors : [...$('floor').options].map(o => ({floor:Number(o.value)}))); $('floor').value = selected; render(); }
  status(lastStatus, lastError);
}
async function loadNames() {
  if (locale !== 'ko') return '';
  const result = await Promise.allSettled([request('./monster-names.ko.json'), request('./monster-names.ko.sources.json')]);
  let warning = '';
  if (result[0].status === 'fulfilled') names = result[0].value;
  else warning += ' Korean names could not be loaded; English names and IDs remain available.';
  if (result[1].status === 'fulfilled') nameSources = result[1].value;
  else { nameSources = {}; warning += ' Korean name provenance could not be loaded; names are marked unverified.'; }
  return warning;
}
// Switch in place: current edits, browser project and pending download are retained.
for (const lang of ['en', 'ko']) $('lang-' + lang).onclick = async event => {
  event.preventDefault(); if (busy) return;
  busy = true; controls(); locale = lang;
  const url = new URL(location.href); url.searchParams.set('lang', lang); history.replaceState(null, '', url);
  const warning = await loadNames(); translatePage(); if (warning) status(lastStatus + warning);
  busy = false; controls();
};
(async () => {
  translatePage();
  const nameWarning = await loadNames();
  if (fileMode) {
    $('file-tools').hidden = false;
    project('Open a project JSON or load the example.');
    status('Ready. Choose Open project JSON or Load example.' + nameWarning); controls(); return;
  }
  try {
    const meta = await request('/api/floors'); token = meta.token;
    project(`${meta.project} · ${meta.floors.length} floors`);
    const catalog = await request('/api/catalog'); monsters = catalog.monsters || [];
    floorOptions(meta.floors); await load(meta.floors[0].floor);
    if (nameWarning) status(lastStatus + nameWarning);
  } catch (error) { status(error.message, true); }
})();
