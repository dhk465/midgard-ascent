(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TowerSettingsModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function integer(value, min, max, label) {
    if (!Number.isInteger(value) || value < min || value > max) throw new Error(`${label}: enter an integer from ${min} to ${max}.`);
    return value;
  }
  function keys(object, expected, label) {
    if (!object || typeof object !== 'object' || Array.isArray(object) || Object.keys(object).sort().join('|') !== expected.slice().sort().join('|')) throw new Error(`${label}: invalid JSON fields.`);
  }
  function create(config) {
    if (![1,2,3].includes(config.schema_version) || !Array.isArray(config.settings) || !Array.isArray(config.monsters) || config.monsters.length < 1) throw new Error('Invalid defaults format.');
    const floorStart = integer(config.floor_start === undefined ? 1 : config.floor_start, 1, 191, 'Bank first floor');
    const floorCount = integer(config.floor_count === undefined ? 10 : config.floor_count, 1, 10, 'Bank floor count');
    const floorEnd = floorStart + floorCount - 1;
    if (floorEnd > 200) throw new Error('Settings bank exceeds floor 200.');
    const allowed = new Set(config.monsters.map(m => m.id));
    if (allowed.size !== config.monsters.length || [...allowed].some(id => (!Number.isInteger(id) || id < 1 || id > 46655))) throw new Error('Invalid monster catalog.');
    const codecIds = config.codec_monster_ids || config.monsters.map(m=>m.id).sort((a,b)=>a-b);
    const oldTag=(config.codec_tag || 'g4:t1:').replace(/^g5:/,'g4:');
    const tag=oldTag.replace(/^g4:/,'g5:');
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    if (!/^g5:[a-z0-9]+:$/.test(tag) || tag.length>40 || codecIds.length>256 || new Set(codecIds).size!==codecIds.length || [...allowed].some(id=>!codecIds.includes(id))) throw new Error('Invalid frozen codec dictionary.');
    const defaults = Object.fromEntries(config.settings.map(s => [s.key, s.default]));
    for(let f=floorStart;f<=floorEnd;f++) for(let w=1;w<=20;w++) for(let g=3;g<=4;g++) {
      const prefix=`f${f}_w${w}_g${g}`;
      if (!Object.hasOwn(defaults,`${prefix}_mob_id`)) defaults[`${prefix}_mob_id`]=defaults[`f${f}_w${w}_g1_mob_id`];
      if (!Object.hasOwn(defaults,`${prefix}_count`)) defaults[`${prefix}_count`]=0;
    }
    for(let f=floorStart;f<=floorEnd;f++) for(let w=1;w<=20;w++) if(!Object.hasOwn(defaults,`f${f}_w${w}_groups`)) defaults[`f${f}_w${w}_groups`]=4;
    const expected = [];
    for (let f = floorStart; f <= floorEnd; f++) {
      expected.push(`f${f}_waves`);
      for(let w=1;w<=20;w++) expected.push(`f${f}_w${w}_groups`);
      for (let w = 1; w <= 20; w++) for (let g = 1; g <= 4; g++) expected.push(`f${f}_w${w}_g${g}_mob_id`, `f${f}_w${w}_g${g}_count`);
    }
    function validateRaw(values, acceptRetired = false) {
      keys(values, expected, 'Settings');
      for (let f = floorStart; f <= floorEnd; f++) {
        integer(values[`f${f}_waves`], 1, 20, `Floor ${f} wave count`);
        for (let w = 1; w <= 20; w++) {
          let total = 0;
          const active=integer(values[`f${f}_w${w}_groups`],1,4,`Floor ${f}, wave ${w} active groups`);
          for (let g = 1; g <= 4; g++) {
            const prefix = `f${f}_w${w}_g${g}`;
            if (!Number.isInteger(values[`${prefix}_mob_id`]) || !(allowed.has(values[`${prefix}_mob_id`]) || (acceptRetired && codecIds.includes(values[`${prefix}_mob_id`])))) throw new Error(`Floor ${f}, wave ${w}: select a supported monster.`);
            const count=integer(values[`${prefix}_count`], 0, 8, `Floor ${f}, wave ${w}, group ${g} count`);
            if(g<=active) total+=count;
          }
          integer(total, 1, 8, `Floor ${f}, wave ${w} total count`);
        }
      }
      return { ...values };
    }
    function validate(values) { return validateRaw(values); }
    let migrationNotices=[];
    function migrate(values) {
      validateRaw(values,true);  // Do not repair malformed topology, IDs or counts.
      const out={...values}; migrationNotices=[];
      for(let f=floorStart;f<=floorEnd;f++) for(let w=1;w<=20;w++) {
        const active=out[`f${f}_w${w}_groups`];
        for(let g=1;g<=4;g++) {
          const prefix=`f${f}_w${w}_g${g}`;
          if(!allowed.has(out[`${prefix}_mob_id`])) {
            migrationNotices.push(`Floor ${f}, wave ${w}, group ${g}: retired monster ${out[`${prefix}_mob_id`]} removed.`);
            out[`${prefix}_mob_id`]=defaults[`${prefix}_mob_id`];out[`${prefix}_count`]=0;
          }
        }
        let total=0;for(let g=1;g<=active;g++)total+=out[`f${f}_w${w}_g${g}_count`];
        if(total===0) {
          migrationNotices.push(`Floor ${f}, wave ${w}: empty active roster restored to authored defaults.`);
          out[`f${f}_w${w}_groups`]=defaults[`f${f}_w${w}_groups`];
          for(let g=1;g<=4;g++)for(const field of ['mob_id','count'])out[`f${f}_w${w}_g${g}_${field}`]=defaults[`f${f}_w${w}_g${g}_${field}`];
        }
      }
      return validate(out);
    }
    validate(defaults);
    function exportJSON(values) {
      validate(values);
      return { schema_version: 3, floors: Array.from({ length: floorCount }, (_, i) => {
        const f = floorStart + i;
        return { floor: f, wave_count: values[`f${f}_waves`], waves: Array.from({ length: 20 }, (_, j) => {
          const w = j + 1;
          return { wave: w, group_count: values[`f${f}_w${w}_groups`], groups: [1, 2, 3, 4].map(g => ({ mob_id: values[`f${f}_w${w}_g${g}_mob_id`], count: values[`f${f}_w${w}_g${g}_count`] })) };
        }) };
      }) };
    }
    function importJSON(data) {
      keys(data, ['schema_version', 'floors'], 'JSON');
      if (![1,2,3].includes(data.schema_version) || !Array.isArray(data.floors) || data.floors.length !== floorCount) throw new Error(`JSON version 1, 2 or 3 with floors ${floorStart}–${floorEnd} is required.`);
      const values = { ...defaults };
      data.floors.forEach((floor, i) => {
        keys(floor, ['floor', 'wave_count', 'waves'], 'Floor');
        const f = floorStart + i;
        if (floor.floor !== f || !Array.isArray(floor.waves) || floor.waves.length !== 20) throw new Error('Expected floors in order with 20 stored waves each.');
        values[`f${f}_waves`] = floor.wave_count;
        floor.waves.forEach((wave, j) => {
          keys(wave, data.schema_version===3 ? ['wave','group_count','groups'] : ['wave','groups'], 'Wave');
          const w = j + 1;
          values[`f${f}_w${w}_groups`]=data.schema_version===3 ? wave.group_count : (data.schema_version===1 ? 2 : 4);
          if (wave.wave !== w || !Array.isArray(wave.groups) || wave.groups.length !== (data.schema_version===1 ? 2 : 4)) throw new Error('Expected waves in order with the schema group count.');
          wave.groups.forEach((group, k) => {
            keys(group, ['mob_id', 'count'], 'Monster group');
            values[`f${f}_w${w}_g${k + 1}_mob_id`] = group.mob_id;
            values[`f${f}_w${w}_g${k + 1}_count`] = group.count;
          });
        });
      });
      return migrate(values);
    }
    function toBridge(values) {
      validate(values);
      const out = {};
      for (let f = floorStart; f <= floorEnd; f++) {
        out[`f${f}_waves`] = values[`f${f}_waves`];
        let roster = tag;
        for (let w = 1; w <= 20; w++) {
          roster+=values[`f${f}_w${w}_groups`];
          for (let g = 1; g <= 4; g++) {
          const value=codecIds.indexOf(values[`f${f}_w${w}_g${g}_mob_id`])*16+values[`f${f}_w${w}_g${g}_count`];
          roster += alphabet[Math.floor(value/64)]+alphabet[value%64];
        }
        }
        out[`f${f}_roster`] = roster;
      }
      return out;
    }
    function fromBridge(settings) {
      if (!Array.isArray(settings)) throw new Error('The app did not return a settings list.');
      if (settings.length !== floorCount * 2) throw new Error(`Expected ${floorCount * 2} app settings for floors ${floorStart}–${floorEnd}.`);
      const compact = Object.fromEntries(settings.map(s => [s.key, s.value]));
      keys(compact, Array.from({ length: floorCount }, (_, i) => [`f${floorStart + i}_waves`, `f${floorStart + i}_roster`]).flat(), 'App settings');
      const out = { ...defaults };
      for (let f = floorStart; f <= floorEnd; f++) {
        out[`f${f}_waves`] = compact[`f${f}_waves`];
        const roster = compact[`f${f}_roster`];
        const legacy = typeof roster === 'string' && /^[0-9]{80}$/.test(roster);
        const b3 = typeof roster === 'string' && /^b3:[0-9a-z]{160}$/.test(roster);
        const current = typeof roster === 'string' && roster.startsWith(tag) && roster.length===tag.length+180 && /^(?:[1-4][A-Za-z0-9+/]{8}){20}$/.test(roster.slice(tag.length));
        const g4=typeof roster==='string' && roster.startsWith(oldTag) && roster.length===oldTag.length+160 && /^[A-Za-z0-9+/]+$/.test(roster.slice(oldTag.length));
        if (!legacy && !b3 && !current && !g4) throw new Error(`Floor ${f}: invalid roster encoding.`);
        const legacyIds = config.legacy_monster_ids || [1002,1113,1063,1011,1010,1004,1009,1012,1052,1014];
        for(let w=1;w<=20;w++) out[`f${f}_w${w}_groups`]=current ? Number(roster[tag.length+(w-1)*9]) : (g4 ? 4 : 2);
        for (let w = 1; w <= 20; w++) for (let g = 1; g <= (current||g4?4:2); g++) {
          if(current||g4) {
            const offset=tag.length+(w-1)*(current?9:8)+(current?1:0)+(g-1)*2;
            const value=alphabet.indexOf(roster[offset])*64+alphabet.indexOf(roster[offset+1]);
            out[`f${f}_w${w}_g${g}_mob_id`]=codecIds[Math.floor(value/16)];
            out[`f${f}_w${w}_g${g}_count`]=value%16;
            continue;
          }
          const offset = legacy ? (w - 1) * 4 + (g - 1) * 2 : 3 + ((w - 1) * 2 + g - 1) * 4;
          out[`f${f}_w${w}_g${g}_mob_id`] = legacy ? legacyIds[Number(roster[offset])] : parseInt(roster.slice(offset, offset + 3),36);
          out[`f${f}_w${w}_g${g}_count`] = Number(roster[offset + (legacy ? 1 : 3)]);
        }
      }
      return migrate(out);
    }
    return { floorStart, floorCount, floorEnd, defaults: { ...defaults }, get migrationNotices() { return [...migrationNotices]; }, validate, exportJSON, importJSON, toBridge, fromBridge };
  }
  return { create };
});
