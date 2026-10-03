'use strict';
(function (root) {
  const clone = value => JSON.parse(JSON.stringify(value));
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  function integer(value, low, high, label) {
    if (!Number.isInteger(value) || value < low || value > high) throw new Error(`${label}: integer ${low}–${high} required`);
  }
  function preset(document) {
    if (!object(document)) throw new Error('Project must be an object');
    const value = Object.hasOwn(document, 'wave_preset') ? document.wave_preset : document;
    if (!object(value) || value.schema_version !== 3 || !Array.isArray(value.floors)) throw new Error('Expected schema_version 3 wave_preset with floors');
    return value;
  }
  function validateFloor(floor) {
    if (!object(floor)) throw new Error('Invalid floor');
    integer(floor.floor, 1, 200, 'Floor'); integer(floor.wave_count, 1, 20, 'Wave count');
    if (!Array.isArray(floor.waves) || floor.waves.length !== 20) throw new Error('Every floor must retain 20 waves');
    floor.waves.forEach((wave, i) => {
      if (!object(wave) || wave.wave !== i + 1) throw new Error('Wave identifiers must be ordered 1–20');
      integer(wave.group_count, 1, 4, 'Group count');
      if (!Array.isArray(wave.groups) || wave.groups.length !== 4) throw new Error('Every wave must retain four groups');
      wave.groups.forEach(group => {
        if (!object(group)) throw new Error('Invalid group');
        integer(group.mob_id, 1, 200000, 'Monster ID'); integer(group.count, 0, 8, 'Count');
      });
      integer(wave.groups.slice(0, wave.group_count).reduce((n, g) => n + g.count, 0), 1, 8, `Wave ${i + 1} active total`);
    });
    return floor;
  }
  function validateProject(document) {
    const floors = preset(document).floors;
    if (floors.length < 1 || floors.length > 200) throw new Error('Expected 1–200 stored floors');
    const seen = new Set();
    floors.forEach(floor => {
      validateFloor(floor);
      if (seen.has(floor.floor)) throw new Error('Duplicate floor identifier'); seen.add(floor.floor);
    });
    if (Object.hasOwn(document, 'monsters')) {
      if (!Array.isArray(document.monsters)) throw new Error('Monster catalog must be an array');
      const ids = new Set();
      document.monsters.forEach(mob => {
        if (!object(mob)) throw new Error('Invalid catalog monster');
        integer(mob.id, 1, 200000, 'Catalog monster ID');
        if (ids.has(mob.id)) throw new Error('Duplicate catalog monster ID'); ids.add(mob.id);
        for (const key of ['label', 'label_ko', 'aegis_name', 'aegis']) {
          if (Object.hasOwn(mob, key) && typeof mob[key] !== 'string') throw new Error(`Monster ${key} must be text`);
        }
      });
    }
    return document;
  }
  function target(floor, path) {
    const match = typeof path === 'string' && /^(?:wave_count|waves\/([1-9]|1[0-9]|20)\/(?:group_count|groups\/([1-4])\/(?:mob_id|count)))$/.exec(path);
    if (!match) throw new Error('Unsupported field path');
    const parts = path.split('/');
    if (parts.length === 1) return [floor, parts[0]];
    const wave = floor.waves[Number(parts[1]) - 1];
    return parts.length === 3 ? [wave, parts[2]] : [wave.groups[Number(parts[3]) - 1], parts[4]];
  }
  class BrowserStore {
    constructor(document) { validateProject(document); this.document = clone(document); }
    static fromText(text) {
      if (new TextEncoder().encode(text).length > 16000000) throw new Error('Project exceeds 16 MB');
      return new BrowserStore(JSON.parse(text.replace(/^\uFEFF/, '')));
    }
    metadata() { return {floors: preset(this.document).floors.map(f => ({floor: f.floor, wave_count: f.wave_count}))}; }
    catalog() { return clone(this.document.monsters || []); }
    floor(fid) {
      const floor = preset(this.document).floors.find(f => f.floor === fid);
      if (!floor) throw new Error('Floor not found'); return clone(floor);
    }
    patch(fid, changes) {
      if (!Array.isArray(changes) || changes.length < 1 || changes.length > 181) throw new Error('Expected 1–181 field changes');
      const next = clone(this.document), floor = preset(next).floors.find(f => f.floor === fid);
      if (!floor) throw new Error('Floor not found');
      const seen = new Set(), catalog = next.monsters || [];
      changes.forEach(change => {
        if (!object(change) || Object.keys(change).sort().join(',') !== 'expected,path,value') throw new Error('Each change requires path, expected and value');
        const [container, key] = target(floor, change.path);
        if (seen.has(change.path)) throw new Error('Duplicate field path'); seen.add(change.path);
        if (!Number.isInteger(change.expected) || !Number.isInteger(change.value)) throw new Error('Expected and value must be integers');
        if (container[key] !== change.expected) throw new Error(`Field conflict: ${change.path}. Reload before retrying.`);
        if (key === 'mob_id' && catalog.length && !catalog.some(m => m.id === change.value)) throw new Error('Select a monster from the project catalog');
        container[key] = change.value;
      });
      validateProject(next); this.document = next;
      return {floor: clone(floor), saved_fields: changes.length};
    }
    serialize() { validateProject(this.document); return JSON.stringify(this.document, null, 2) + '\n'; }
  }
  const api = {BrowserStore, validateProject, validateFloor, preset};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TowerBrowser = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
