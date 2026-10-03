'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const i18n = require('./i18n.js');
const {BrowserStore} = require('./browser-store.js');
const hangul = /\p{Script=Hangul}/u;
const sample = JSON.parse(fs.readFileSync(path.join(__dirname, 'sample-project.json'), 'utf8'));
for (const [en, ko] of Object.entries(i18n.phrases)) {
  assert(!hangul.test(i18n.text(en, 'en')));
  assert.equal(i18n.text(en, 'ko'), ko);
}
assert.match(i18n.monsterLabel({id:2398, label:'Little Poring'}, {2398:'풋내기 포링'}, 'ko', {monsters:{2398:{status:'unresolved_inven_retained_navigation_fallback'}}}), /인벤 미확인/);
assert.equal(i18n.downloadName('한국어.json', 'en'), 'tower-project-edited.json');
assert.equal(i18n.downloadName('한국어.json', 'ko'), '한국어-edited.json');
assert(!hangul.test(i18n.text('ﾡﾢﾣ한글', 'en')));
assert.equal(i18n.locale('?lang=ko'), 'ko'); assert.equal(i18n.locale('?lang=KO'), 'en');
assert.equal(i18n.monsterLabel({id:1002, label:'포링', aegis:'PORING'}, {1002:'포링'}, 'en'), 'PORING · ID 1002');
assert.equal(i18n.monsterLabel({id:999, label:'한글', aegis_name:'한국어'}, {}, 'en'), 'Outside project catalog · ID 999');
assert.equal(i18n.monsterLabel({id:1002, label:'Poring'}, {1002:'포링'}, 'ko', {monsters:{1002:{status:'verified_inven_detail_id'}}}), '포링 · Poring · ID 1002');
assert(!hangul.test(i18n.text('한국어.json · 20 floors\n오류: hidden schema path waves/1/count', 'en')));
assert.equal(i18n.text('Wave 3 group 2 monster', 'ko'), '웨이브 3 그룹 2 몬스터');
assert.match(i18n.text('Wave count: integer 1–20 required', 'ko'), /웨이브 수:.*정수/);
const store = new BrowserStore(sample), before = store.serialize();
for (const lang of ['en','ko','en']) store.catalog().forEach(m => i18n.monsterLabel(m, {}, lang));
assert.equal(store.serialize(), before);
store.patch(1, [{path:'waves/20/groups/4/count', expected:sample.wave_preset.floors[0].waves[19].groups[3].count, value:7}]);
const edited = store.serialize(); i18n.text('Floor 1', 'ko'); assert.equal(store.serialize(), edited);
assert.equal(JSON.parse(edited).wave_preset.floors[0].waves[19].groups[3].count, 7);

// Exercise real app rendering and in-place switches with an isolated DOM/API model.
class Element {
  constructor(tag='div') { this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this.value='';this.checked=false;this.events={}; }
  append(...els) { this.children.push(...els); }
  replaceChildren(...els) { this.children=els;this.textContent=''; }
  setAttribute(key,value) { this[key]=value; }
  addEventListener(key,fn) { this.events[key]=fn; }
  querySelectorAll() { return this.children.flatMap(e => [e,...e.querySelectorAll()]).filter(e => ['input','select'].includes(e.tagName)); }
  get lastChild() { return this.children.at(-1); }
  get options() { return this.children; }
}
(async () => {
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');assert(!hangul.test(html));
  const els={}; for (const m of html.matchAll(/id="([^"]+)"/g)) els[m[1]]=new Element(m[1]==='floor'?'select':'div');
  const staticNodes=[...html.matchAll(/data-i18n="([^"]+)"/g)].map(m => {const e=new Element();e.dataset.i18n=m[1];return e;});
  const requests=[], doc={documentElement:{dataset:{mode:'file'},lang:'en'},getElementById:id=>els[id],createElement:tag=>new Element(tag),querySelectorAll:()=>staticNodes,querySelector:()=>new Element('nav')};
  const url=new URL('https://example.test/editor/'), context={document:doc,location:url,history:{replaceState(){}},URL,URLSearchParams,TextEncoder,console,confirm:()=>true,setTimeout,window:{addEventListener(){}},TowerBrowser:require('./browser-store.js'),TowerI18n:i18n};
  context.fetch=async resource=>{requests.push(resource);return {ok:true,text:async()=>JSON.stringify(sample),json:async()=>({'1002':'포링'})};};
  vm.createContext(context); vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8'),context);
  await new Promise(resolve=>setImmediate(resolve));
  assert(!requests.some(p=>p.includes('monster-names.ko')), 'English must not fetch Korean mapping/provenance');
  sample.monsters[0].label='악의적인 한국어'; sample.monsters[0].aegis='PORING';
  await vm.runInContext('openText(JSON.stringify('+JSON.stringify(sample)+'), "한국어파일.json")',context);
  function rendered() {const collect=e=>e.textContent+' '+(e['aria-label']||'')+' '+e.children.map(collect).join(' ');return [...Object.values(els),...staticNodes].map(collect).join(' ');}
  assert(!hangul.test(rendered()), 'English rendered text must contain no Hangul');
  vm.runInContext('current.waves[19].groups[3].count = 6; exportPending = true;',context);
  const pending=vm.runInContext('JSON.stringify({current,baseline,project:store.serialize(),exportPending})',context);
  await els['lang-ko'].onclick({preventDefault(){}});
  assert(requests.includes('./monster-names.ko.json'));assert.equal(doc.documentElement.lang,'ko');assert(hangul.test(rendered()));
  assert.equal(vm.runInContext('JSON.stringify({current,baseline,project:store.serialize(),exportPending})',context),pending,'Switch must preserve unstaged/staged state');
  await els['lang-en'].onclick({preventDefault(){}});
  assert(!hangul.test(rendered()), 'Returning to English clears Korean visible copy');
  assert.equal(vm.runInContext('JSON.stringify({current,baseline,project:store.serialize(),exportPending})',context),pending);
  console.log('PASS English no-Hangul, conditional mapping, Korean UI, validation, rendering, switch/edit/export invariance');
})().catch(error=>{console.error(error);process.exitCode=1;});
