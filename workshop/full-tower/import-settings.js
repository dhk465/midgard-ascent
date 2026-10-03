'use strict';
// Import an exported native settings bank into a local JSON project, never live state.
const fs = require('node:fs');
const path = require('node:path');
const model = require('../chapter-one/settings/model.js');
function migrate(project, defaults, exported) {
  const bank = model.create(defaults);
  const values = bank.importJSON(exported);
  if (bank.migrationNotices.length) throw new Error('Retired monsters require explicit review: ' + bank.migrationNotices.join('; '));
  const preset = bank.exportJSON(values);
  const result = JSON.parse(JSON.stringify(project));
  const target = result.wave_preset || result;
  for (const floor of preset.floors) {
    const current = target.floors.find(f => f.floor === floor.floor);
    if (!current) throw new Error(`Project does not contain floor ${floor.floor}`);
    current.wave_count = floor.wave_count;
    for (let w = 0; w < 20; w++) {
      current.waves[w].group_count = floor.waves[w].group_count;
      const supplied = exported.floors.find(f => f.floor === floor.floor).waves[w].groups.length;
      for (let g = 0; g < supplied; g++) Object.assign(current.waves[w].groups[g], floor.waves[w].groups[g]);
    }
  }
  return result;
}
module.exports = { migrate };
if (require.main === module) {
  const [projectPath, defaultsPath, exportedPath, outputPath] = process.argv.slice(2);
  if (!outputPath) throw new Error('Usage: node import-settings.js PROJECT DEFAULTS EXPORTED_JSON NEW_OUTPUT');
  const output = path.resolve(outputPath);
  const root = path.resolve(__dirname, '../..');
  if (!['build', 'local'].some(folder => {
    const relative = path.relative(path.join(root, folder), output);
    return relative && !relative.startsWith('..') && !path.isAbsolute(relative);
  })) throw new Error('Output must be nested inside repository build/ or local/');
  const read = p => JSON.parse(fs.readFileSync(p, 'utf8').replace(/^\uFEFF/, ''));
  const result = migrate(read(projectPath), read(defaultsPath), read(exportedPath));
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
  console.log(output);
}
