'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let model, config, values, baseline, busy = false;
  function dirty() { return JSON.stringify(values) !== JSON.stringify(baseline); }
  function status(message, error = false) { $('status').textContent = message; $('status').className = error ? 'error' : ''; }
  function migrationSummary() { const notes=model.migrationNotices; return notes.length ? `${notes.length} roster adjustments. ${notes.slice(0,3).join(' ')}${notes.length>3 ? ' See the editor for remaining waves.' : ''} Select Save to persist these changes.` : ''; }
  function changed() { status(dirty() ? 'You have unsaved changes.' : 'Settings match the saved values.'); }
  function render() {
    const f = Number($('floor').value);
    $('wave-count').value = values[`f${f}_waves`];
    $('waves').replaceChildren();
    const active = values[`f${f}_waves`];
    for (let w = 1; w <= (Number.isInteger(active) && active <= 20 ? active : 0); w++) {
      const field = document.createElement('fieldset');
      const legend = document.createElement('legend'); legend.textContent = `Wave ${w}`; field.append(legend);
      const groupLabel=document.createElement('label'); groupLabel.textContent='Active monster groups';
      const groupCount=document.createElement('select'); groupCount.className='group-count';
      for(let n=1;n<=4;n++){const option=document.createElement('option');option.value=n;option.textContent=n;groupCount.append(option);}
      groupCount.value=values[`f${f}_w${w}_groups`];
      groupCount.addEventListener('change',()=>{values[`f${f}_w${w}_groups`]=Number(groupCount.value);render();changed();});
      groupLabel.append(groupCount);field.append(groupLabel);
      for (let g = 1; g <= values[`f${f}_w${w}_groups`]; g++) {
        const prefix = `f${f}_w${w}_g${g}`;
        const row = document.createElement('div'); row.className = 'group';
        const ml = document.createElement('label'); ml.textContent = `Group ${g} monster`;
        const select = document.createElement('select');
        for (const monster of config.monsters) { const option = document.createElement('option'); option.value = monster.id; option.textContent = `${monster.label} (${monster.id}) · Lv ${monster.level} · HP ${monster.hp.toLocaleString("en-US")}`; select.append(option); }
        select.value = values[`${prefix}_mob_id`];
        select.addEventListener('change', () => { values[`${prefix}_mob_id`] = Number(select.value); changed(); }); ml.append(select);
        const cl = document.createElement('label'); cl.textContent = 'Count';
        const count = document.createElement('input'); count.type = 'number'; count.min = '0'; count.max = '8'; count.step = '1'; count.value = values[`${prefix}_count`];
        count.addEventListener('input', () => { values[`${prefix}_count`] = count.value === '' ? NaN : Number(count.value); changed(); }); cl.append(count); row.append(ml, cl); field.append(row);
      }
      $('waves').append(field);
    }
  }
  async function action(fn) {
    if (busy) return;
    busy = true;
    for (const button of document.querySelectorAll('button')) button.disabled = true;
    try { await fn(); } catch (error) { status(error.message || String(error), true); }
    finally { busy = false; for (const button of document.querySelectorAll('button')) button.disabled = false; }
  }
  async function refresh(initial = false) {
    if (!initial && dirty()) throw new Error('Save your changes before reloading.');
    const before = values ? JSON.stringify(values) : null;
    const data = await window.modSettings.get();
    if (values && JSON.stringify(values) !== before) throw new Error('Settings changed during loading. The editor has been preserved.');
    try { values = model.fromBridge(data.settings); }
    catch (error) {
      if (!initial) throw error;
      values = { ...model.defaults }; baseline = null; render();
      status(`Saved settings are invalid. Defaults are ready in the editor but have not been saved. ${error.message}`, true);
      return;
    }
    const migrated=model.migrationNotices.length>0;baseline=migrated ? null : { ...values };render();status(migrated ? migrationSummary() : 'Saved settings loaded.');
  }
  $('floor').addEventListener('change', render);
  $('wave-count').addEventListener('change', () => {
    const n = Number($('wave-count').value);
    values[`f${$('floor').value}_waves`] = $('wave-count').value === '' ? NaN : n;
    if (!Number.isInteger(n) || n < 1 || n > 20) { status('Wave count must be an integer from 1 to 20.', true); return; }
    values[`f${$('floor').value}_waves`] = n; render(); changed();
  });
  for (const button of document.querySelectorAll('[data-preset]')) button.addEventListener('click', () => {
    for (let f = model.floorStart; f <= model.floorEnd; f++) values[`f${f}_waves`] = Number(button.dataset.preset);
    render(); changed();
  });
  $('save').addEventListener('click', () => action(async () => {
    const snapshot = model.validate(values);
    await window.modSettings.set(model.toBridge(snapshot)); baseline = snapshot;
    status(dirty() ? 'Saved. Changes made during saving are still unsaved.' : 'JSON settings saved. Apply to the server separately.');
  }));
  $('apply').addEventListener('click', () => action(async () => {
    if (dirty()) throw new Error('Save the current settings first.');
    model.validate(values);
    if (!window.confirm('Restart the server to apply the saved tower settings?')) return;
    status('Applying to server…'); await window.modSettings.apply(); status('Server apply request completed.');
  }));
  $('refresh').addEventListener('click', () => action(() => refresh()));
  $('reset').addEventListener('click', () => { values = { ...model.defaults }; render(); changed(); });
  $('export').addEventListener('click', () => action(async () => {
    const blob = new Blob([JSON.stringify(model.exportJSON(values), null, 2) + '\n'], { type: 'application/json' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = model.floorStart === 1 && model.floorEnd === 10 ? 'tower-wave-settings.json' : `tower-wave-settings-${model.floorStart}-${model.floorEnd}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status('Current editor settings exported as JSON.');
  }));
  $('import').addEventListener('change', () => action(async () => {
    const file = $('import').files[0]; $('import').value = '';
    if (!file) return;
    if (file.size > 256 * 1024) throw new Error('JSON files must be 256 KB or smaller.');
    const before = JSON.stringify(values);
    const text = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('Unable to read the file.')); reader.readAsText(file); });
    const imported = model.importJSON(JSON.parse(text));
    if (JSON.stringify(values) !== before) throw new Error('Settings changed while reading the file. Import cancelled.');
    values = imported; render(); status('JSON imported into the editor. '+(migrationSummary() || 'Select Save to persist it.'));
  }));
  window.addEventListener('beforeunload', event => { if (values && dirty()) { event.preventDefault(); event.returnValue = ''; } });
  action(async () => {
    if (!window.modSettings) throw new Error('Open this page from the Ragnarok Offline mod settings window.');
    const response = await fetch('defaults.json'); if (!response.ok) throw new Error('Unable to load defaults.');
    config = await response.json(); model = TowerSettingsModel.create(config);
    $('bank-heading').textContent = `Tower settings: Floors ${model.floorStart}–${model.floorEnd}`;
    document.title = `Tower settings: Floors ${model.floorStart}–${model.floorEnd}`;
    $('bulk-label').textContent = `Wave count for all ${model.floorCount} floors in this bank:`;
    if (config.client_profile) $('catalog-profile').textContent = `Verified local Renewal asset profile: ${config.client_profile.packetver}. ${config.monsters.length} selectable records; source levels ${Math.min(...config.monsters.map(m=>m.level))}–${Math.max(...config.monsters.map(m=>m.level))}. The 20221005 historical client has not been verified.`;
    for (const row of config.excluded || []) { const item=document.createElement('li'); item.textContent=`${row.label} (${row.id}): ${row.reason}`; $('excluded-list').append(item); }
    $('catalog-exclusions').hidden = !(config.excluded || []).length;
    for (let f = model.floorStart; f <= model.floorEnd; f++) { const option = document.createElement('option'); option.value = f; option.textContent = `Floor ${f}`; $('floor').append(option); }
    await refresh(true); $('editor').hidden = false;
  });
})();
