'use strict';
(function (root) {
  const hangul = /\p{Script=Hangul}/gu;
  const english = value => String(value ?? '').replace(hangul, '').replace(/\s+/g, ' ').trim();
  const phrases = {
    'Loading editor…':'편집기 불러오는 중…', 'Authoring JSON editor':'제작용 JSON 편집기',
    'Open project JSON':'프로젝트 JSON 열기', 'Load example':'예제 불러오기', 'Download JSON':'JSON 다운로드',
    'Files stay in your browser. Stage floor changes, then download the complete project. Keep your original file as a backup.':'파일은 브라우저 안에만 보관됩니다. 층 변경 사항을 반영한 뒤 전체 프로젝트를 다운로드하세요. 원본 파일은 백업으로 보관하세요.',
    'Floor to edit':'편집할 층', 'All 20 waves and four groups per wave are retained, including inactive values.':'비활성 값을 포함해 20개 웨이브와 웨이브별 4개 그룹을 모두 유지합니다.',
    'Saving updates the authoring JSON. Game installation remains a separate step.':'저장하면 제작용 JSON이 갱신됩니다. 게임 설치는 별도로 진행합니다.',
    'Reload selected floor':'선택한 층 다시 불러오기', 'Select a floor':'층 선택', 'Save changed fields':'변경한 항목 저장',
    'Active waves':'활성 웨이브', 'Each wave needs 1–8 active monsters. Inactive values are preserved and validated.':'각 웨이브에는 활성 몬스터가 1–8마리 필요합니다. 비활성 값도 보존하고 검사합니다.',
    'Edit inactive waves and groups':'비활성 웨이브와 그룹 편집',
    'No automatic installation or restart. Previous JSON versions are retained beside the project in its .backups folder.':'자동 설치나 재시작은 하지 않습니다. 이전 JSON은 프로젝트 옆 .backups 폴더에 보관됩니다.',
    'Active groups ':'활성 그룹 ', 'Monster':'몬스터', 'Count':'수량',
    'Discard unstaged changes to this floor?':'이 층의 아직 반영하지 않은 변경 사항을 버릴까요?',
    'Replace the browser project and discard changes that have not been downloaded?':'브라우저 프로젝트를 교체하고 다운로드하지 않은 변경 사항을 버릴까요?',
    'Staging changed fields in the browser…':'브라우저에 변경 사항 반영 중…', 'Saving changed fields…':'변경 사항 저장 중…',
    'Your edits are retained. Review the issue, then reload if needed.':'편집 내용은 유지됩니다. 문제를 확인한 뒤 필요하면 다시 불러오세요.',
    'Project exceeds 16 MB':'프로젝트가 16 MB를 초과합니다', 'Loading example…':'예제 불러오는 중…',
    'Download requested. Confirm that your browser saved the JSON. Your original file has not changed; no game files were written.':'다운로드를 요청했습니다. 브라우저가 JSON을 저장했는지 확인하세요. 원본 파일과 게임 파일은 변경되지 않았습니다.',
    ' Korean names could not be loaded; English names and IDs remain available.':' 한국어 이름을 불러오지 못했습니다. 영어 이름과 ID는 사용할 수 있습니다.',
    ' Korean name provenance could not be loaded; names are marked unverified.':' 한국어 이름 출처를 불러오지 못했습니다. 이름에 인벤 미확인 표시를 붙입니다.',
    'Browser JSON editor':'브라우저 JSON 편집기', 'Stage floor changes':'층 변경 사항 반영',
    'Staging updates only this browser copy. Download JSON to retain your work. Reopen a file to see external edits.':'반영은 현재 브라우저 사본에만 적용됩니다. 작업을 보관하려면 JSON을 다운로드하세요. 외부 변경은 파일을 다시 열어 확인하세요.',
    'No uploads, game writes, installation or automatic file overwrites. Downloads contain the complete authoring document.':'업로드, 게임 파일 변경, 설치, 자동 덮어쓰기는 하지 않습니다. 다운로드에는 전체 제작 문서가 포함됩니다.',
    'Open a project JSON or load the example.':'프로젝트 JSON을 열거나 예제를 불러오세요.',
    'Ready. Choose Open project JSON or Load example.':'준비되었습니다. 프로젝트 JSON 열기 또는 예제 불러오기를 선택하세요.',
    ' Staged changes still need a download.':' 반영한 변경 사항은 다운로드해야 보관됩니다.',
    'Project must be an object':'프로젝트는 객체여야 합니다', 'Expected schema_version 3 wave_preset with floors':'floors가 있는 schema_version 3 wave_preset이 필요합니다',
    'Invalid floor':'올바르지 않은 층', 'Every floor must retain 20 waves':'모든 층은 웨이브 20개를 유지해야 합니다',
    'Wave identifiers must be ordered 1–20':'웨이브 번호는 1–20 순서여야 합니다', 'Every wave must retain four groups':'모든 웨이브는 그룹 4개를 유지해야 합니다',
    'Invalid group':'올바르지 않은 그룹', 'Expected 1–200 stored floors':'저장된 층은 1–200개여야 합니다', 'Duplicate floor identifier':'층 번호가 중복됩니다',
    'Monster catalog must be an array':'몬스터 목록은 배열이어야 합니다', 'Invalid catalog monster':'목록의 몬스터가 올바르지 않습니다',
    'Duplicate catalog monster ID':'목록의 몬스터 ID가 중복됩니다', 'Unsupported field path':'지원하지 않는 항목 경로입니다', 'Floor not found':'층을 찾을 수 없습니다',
    'Expected 1–181 field changes':'변경 항목은 1–181개여야 합니다', 'Each change requires path, expected and value':'각 변경에는 path, expected, value가 필요합니다',
    'Duplicate field path':'항목 경로가 중복됩니다', 'Expected and value must be integers':'expected와 value는 정수여야 합니다',
    'Select a monster from the project catalog':'프로젝트 목록에서 몬스터를 선택하세요',
    'Another edit changed these fields. Reload before retrying.':'다른 편집이 이 항목을 변경했습니다. 다시 불러온 뒤 재시도하세요.',
    'Project changed outside this editor; reload and retry.':'편집기 밖에서 프로젝트가 변경되었습니다. 다시 불러온 뒤 재시도하세요.'
  };
  const patterns = [
    [/^Floor (\d+)$/, '$1층'], [/^Wave (\d+)( · inactive, retained)?$/, '웨이브 $1$2'],
    [/^Group (\d+)( · retained)?$/, '그룹 $1$2'], [/ · inactive, retained/g, ' · 비활성, 보존됨'], [/ · retained/g, ' · 보존됨'],
    [/^Active total (.+) \/ 8$/, '활성 합계 $1 / 8'], [/^Loading floor (\d+)…$/, '$1층 불러오는 중…'],
    [/Floor (\d+) loaded\. Inactive values are retained\./g, '$1층을 불러왔습니다. 비활성 값은 유지됩니다.'],
    [/^Wave (\d+) group (\d+) monster$/, '웨이브 $1 그룹 $2 몬스터'],
    [/(\d+) fields staged in this browser\. Download JSON to keep the complete project; your original file has not changed\./g, '브라우저에 $1개 항목을 반영했습니다. 전체 프로젝트를 보관하려면 JSON을 다운로드하세요. 원본 파일은 변경되지 않았습니다.'],
    [/(\d+) fields saved\. Unrelated edits were merged\. Game installation remains a separate step\./g, '$1개 항목을 저장했습니다. 다른 변경 사항은 병합했습니다. 게임 설치는 별도로 진행합니다.'],
    [/ · (\d+) floors · browser copy/g, ' · $1개 층 · 브라우저 사본'], [/ · (\d+) floors/g, ' · $1개 층'],
    [/Could not open JSON: /g, 'JSON을 열지 못했습니다: '], [/\. The previous browser project is retained\./g, '. 이전 브라우저 프로젝트는 유지됩니다.'],
    [/Could not load example: /g, '예제를 불러오지 못했습니다: '], [/Example request failed/g, '예제 요청 실패'], [/Request failed/g, '요청 실패'],
    [/Download failed: /g, '다운로드 실패: '], [/: loaded (.+), current (.+)/g, ': 불러온 값 $1, 현재 값 $2'],
    [/Field conflict: (.+)\. Reload before retrying\./g, '항목 충돌: $1. 다시 불러온 뒤 재시도하세요.'],
    [/: integer (.+) required/g, ': $1 범위의 정수가 필요합니다'], [/Wave (\d+) active total/g, '웨이브 $1 활성 합계'],
    [/Wave count/g, '웨이브 수'], [/Group count/g, '그룹 수'], [/Catalog monster ID/g, '목록 몬스터 ID'], [/Monster ID/g, '몬스터 ID'], [/^Count:/g, '수량:'], [/^Floor:/g, '층:'],
    [/Monster (.+) must be text/g, '몬스터 $1은 문자열이어야 합니다'], [/Invalid project JSON:/g, '올바르지 않은 프로젝트 JSON:']
  ];
  function text(value, locale) {
    value = String(value ?? '');
    if (locale !== 'ko') return value.replace(hangul, '');
    if (Object.hasOwn(phrases, value)) return phrases[value];
    // Compose statuses while preserving schema paths, IDs and diagnostic details.
    for (const [source, translated] of Object.entries(phrases).sort((a, b) => b[0].length - a[0].length)) value = value.replaceAll(source, translated);
    for (const [pattern, translated] of patterns) value = value.replace(pattern, translated);
    return value;
  }
  function monsterLabel(mob, names, locale, sources = {}) {
    const label = mob.id === 1077 ? 'Poison Spore' : [mob.label, mob.aegis_name, mob.aegis].map(english).find(Boolean) || 'Outside project catalog';
    const unverified = sources.monsters?.[String(mob.id)]?.status !== 'verified_inven_detail_id';
    return locale === 'ko' ? `${names[String(mob.id)] || '한국어 이름 없음'}${unverified ? ' [인벤 미확인]' : ''} · ${label} · ID ${mob.id}` : `${label} · ID ${english(mob.id)}`;
  }
  const downloadName = (name, locale) => ((locale === 'ko' ? String(name) : english(name)).replace(/\.json$/i, '') || 'tower-project') + '-edited.json';
  const api = {english, text, monsterLabel, downloadName, phrases, locale: search => new URLSearchParams(search).get('lang') === 'ko' ? 'ko' : 'en'};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.TowerI18n = api;
})(typeof window !== 'undefined' ? window : globalThis);
