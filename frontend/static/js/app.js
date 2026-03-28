document.addEventListener('DOMContentLoaded', () => {


    const form = document.getElementById('judge-form');
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const uploadArea = document.getElementById('upload-area');
    const submitBtn = document.getElementById('submit-btn');
    const errorMsg = document.getElementById('error-message');
    const modeRadios = document.getElementsByName('judge_mode');
    const manualAnswerGroup = document.getElementById('manual-answer-group');

    const resultPlaceholder = document.getElementById('result-placeholder');
    const resultContent = document.getElementById('result-content');
    const resScore = document.getElementById('res-score');
    const resTotal = document.getElementById('res-total');
    const resType = document.getElementById('res-type');
    const resJudgment = document.getElementById('res-judgment');
    const resRecognized = document.getElementById('res-recognized');
    const resExplanation = document.getElementById('res-explanation');
    const resStepsContainer = document.getElementById('res-steps-container');
    const resStepsTableBody = document.querySelector('#res-steps-table tbody');
    const uploadText = uploadArea.querySelector('.upload-text');
    const uploadHint = uploadArea.querySelector('.upload-hint');
    const resultSummary = document.querySelector('.result-summary');
    // ============================
// 模式切换条（智能判题 / 答题卡专区）
// ============================
const modeBtns = document.querySelectorAll('.segmented-btn[data-mode]');
const modeSingle = document.getElementById('mode-single');
const modeCards = document.getElementById('mode-cards');

function setMode(mode) {
  modeBtns.forEach((btn) => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });

  if (mode === 'single') {
    modeSingle?.classList.remove('hidden');
    modeCards?.classList.add('hidden');
  } else {
    modeSingle?.classList.add('hidden');
    modeCards?.classList.remove('hidden');
  }
}

modeBtns.forEach((btn) => btn.addEventListener('click', () => setMode(btn.dataset.mode)));
setMode('single');


// ============================
// 答题卡批改模式：提交与渲染
// ============================
const cardsForm = document.getElementById('cards-form');
const paperInput = document.getElementById('paper-input');
const rubricInput = document.getElementById('rubric-input');
const cardsInput = document.getElementById('cards-input');
const cardsErrorMsg = document.getElementById('cards-error-message');
const cardsSubmitBtn = document.getElementById('cards-submit-btn');

const paperHint = document.getElementById('paper-hint');
const rubricHint = document.getElementById('rubric-hint');
const cardsHint = document.getElementById('cards-hint');

const cardsResultPlaceholder = document.getElementById('cards-result-placeholder');
const cardsResultContent = document.getElementById('cards-result-content');
const cardsResultTable = document.getElementById('cards-result-table');

function setHint(el, text) {
  if (!el) return;
  el.textContent = text || '';
}

paperInput?.addEventListener('change', () => {
  const f = paperInput.files?.[0];
  setHint(paperHint, f ? `已选择：${f.name}` : '');
});

rubricInput?.addEventListener('change', () => {
  const f = rubricInput.files?.[0];
  setHint(rubricHint, f ? `已选择：${f.name}` : '');
});

cardsInput?.addEventListener('change', () => {
  const n = cardsInput.files?.length || 0;
  setHint(cardsHint, n ? `已选择 ${n} 份答题卡` : '');
});

function renderCardsTable(data) {
  const thead = cardsResultTable.querySelector('thead');
  const tbody = cardsResultTable.querySelector('tbody');
  thead.innerHTML = '';
  tbody.innerHTML = '';

  const questionCount = Number(data.question_count || 0);
  const rows = Array.isArray(data.rows) ? data.rows : [];

  // 表头：文件名 + 题1..题N + 总分 + 错误
  const trh = document.createElement('tr');
  const headers = ['文件名'];
  for (let i = 1; i <= questionCount; i++) headers.push(`题${i}`);
  headers.push('总分', '错误');
  trh.innerHTML = headers.map(h => `<th>${h}</th>`).join('');
  thead.appendChild(trh);

  rows.forEach((r) => {
    const tr = document.createElement('tr');
    const filename = r.card_filename || '';
    const scores = Array.isArray(r.scores) ? r.scores : [];
    const total = (r.total_score ?? '');
    const err = r.error || '';

    const cells = [];
    cells.push(`<td>${filename}</td>`);
    for (let i = 0; i < questionCount; i++) {
      cells.push(`<td>${scores[i] ?? ''}</td>`);
    }
    cells.push(`<td>${total}</td>`);
    cells.push(`<td>${err}</td>`);

    tr.innerHTML = cells.join('');
    tbody.appendChild(tr);
  });

  cardsResultPlaceholder.classList.add('hidden');
  cardsResultContent.classList.remove('hidden');
}

cardsForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  cardsErrorMsg.classList.add('hidden');

  const paperFile = paperInput.files?.[0];
  const rubricFile = rubricInput.files?.[0];
  const cardFiles = cardsInput.files ? Array.from(cardsInput.files) : [];

  if (!paperFile) {
    cardsErrorMsg.textContent = '请先上传试卷本身';
    cardsErrorMsg.classList.remove('hidden');
    return;
  }
  if (!rubricFile) {
    cardsErrorMsg.textContent = '请先上传评分细则/答案';
    cardsErrorMsg.classList.remove('hidden');
    return;
  }
  if (!cardFiles.length) {
    cardsErrorMsg.textContent = '请先批量上传学生答题卡';
    cardsErrorMsg.classList.remove('hidden');
    return;
  }
  if (cardFiles.length > 100) {
    cardsErrorMsg.textContent = '一次最多上传 100 份答题卡';
    cardsErrorMsg.classList.remove('hidden');
    return;
  }

  const formData = new FormData();
  formData.append('paper', paperFile);
  formData.append('rubric', rubricFile);
  // 多文件：同一个 key append 多次
  cardFiles.forEach((f) => formData.append('cards', f));

  cardsSubmitBtn.disabled = true;
  cardsSubmitBtn.classList.add('loading');

  try {
    const resp = await fetch('/api/grade-cards', {
      method: 'POST',
      body: formData,
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || '请求失败，请检查后端服务');
    }

    const data = await resp.json();
    renderCardsTable(data);
  } catch (err) {
    cardsErrorMsg.textContent = `批改出错: ${err.message || err}`;
    cardsErrorMsg.classList.remove('hidden');
  } finally {
    cardsSubmitBtn.disabled = false;
    cardsSubmitBtn.classList.remove('loading');
  }
});
    function setResultTone(tone) {
        resultSummary.classList.remove('is-excellent', 'is-partial', 'is-empty');
        resultSummary.classList.add(tone);
    }

    function normalizeDisplayText(text) {
        if (!text) return '';
        return text
            .replace(/^[\s\x00-\x1f]+|[\s\x00-\x1f]+$/g, '')
            .replace(/\\\(\s*(?:\\+|_+)?\s*\\\)/g, '(    )')
            .replace(/（\s*(?:\\+|_+)\s*）/g, '（    ）')
            .replace(/\(\s*\\+\s*\)/g, '(    )')
            .replace(/(^|\n)\s*[。.;；,，、•·◦○●▪▫■□◆◇]\s*(?=题目[：:]|学生作答[：:]|综合点评[：:])/g, '$1')
            .replace(/(^|\n)\s*[。.;；,，、•·◦○●▪▫■□◆◇]+\s*(?=\n|$)/g, '$1')
            .replace(/(^|\n)\s*[。.;；,，、•·◦○●▪▫■□◆◇]+\s*(?=学生作答[：:])/g, '$1')
            .replace(/\s+学生作答[：:]/g, '\n\n学生作答：')
            .replace(/\n{3,}/g, '\n\n');
    }

    function renderMath() {
        if (window.renderMathInElement) {
            renderMathInElement(document.getElementById('result-content'), {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '\\[', right: '\\]', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\(', right: '\\)', display: false }
                ],
                throwOnError: false
            });
        }
    }

    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function(loadEvent) {
            imagePreview.src = loadEvent.target.result;
            imagePreview.classList.add('is-visible');
            uploadArea.classList.add('has-file');
            uploadText.textContent = file.name;
            uploadHint.textContent = '已完成选择，可直接提交判题';
        };
        reader.readAsDataURL(file);
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            imageInput.files = e.dataTransfer.files;
            imageInput.dispatchEvent(new Event('change'));
        }
    });

    modeRadios.forEach((radio) => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'manual') {
                manualAnswerGroup.classList.remove('hidden');
            } else {
                manualAnswerGroup.classList.add('hidden');
            }
        });
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorMsg.classList.add('hidden');

        if (!imageInput.files.length) {
            errorMsg.textContent = '请先上传答卷图片';
            errorMsg.classList.remove('hidden');
            return;
        }

        const mode = document.querySelector('input[name="judge_mode"]:checked').value;
        const url = mode === 'manual' ? '/api/judge' : '/api/judge/with-bank';

        const formData = new FormData();
        formData.append('image', imageInput.files[0]);

        if (mode === 'manual') {
            const stdAnswer = document.getElementById('standard-answer').value;
            if (stdAnswer) {
                formData.append('standard_answer', stdAnswer);
            }
        }

        submitBtn.disabled = true;
        submitBtn.classList.add('loading');

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '请求失败，请检查网络或后端服务');
            }

            const data = await response.json();

            resultPlaceholder.classList.add('hidden');
            resultContent.classList.remove('hidden');

            resScore.textContent = data.score ?? '-';
            resTotal.textContent = data.total_score ?? '100';
            resType.textContent = data.question_type || '未知题型';
            resJudgment.textContent = data.judgment || (data.score > 0 ? '得分' : '不得分');

            if (data.score === data.total_score && data.total_score > 0) {
                resJudgment.style.color = 'var(--success)';
                setResultTone('is-excellent');
            } else if (data.score === 0) {
                resJudgment.style.color = 'var(--error)';
                setResultTone('is-empty');
            } else {
                resJudgment.style.color = 'var(--accent)';
                setResultTone('is-partial');
            }

            resRecognized.textContent = normalizeDisplayText(data.recognized_content) || '未识别出内容';
            resExplanation.textContent = normalizeDisplayText(data.explanation) || '无详细点评';

            if (data.steps && data.steps.length > 0) {
                resStepsContainer.classList.remove('hidden');
                resStepsTableBody.innerHTML = '';
                data.steps.forEach((step, idx) => {
                    const tr = document.createElement('tr');
                    const statusClass = step.status === '✓'
                        ? 'status-check'
                        : (step.status === '✗' ? 'status-cross' : '');

                    tr.innerHTML = `
                        <td>步骤 ${idx + 1}</td>
                        <td>${step.score || 0}</td>
                        <td class="${statusClass}">${step.status || '-'}</td>
                        <td>${normalizeDisplayText(step.comment) || '-'}</td>
                    `;
                    resStepsTableBody.appendChild(tr);
                });
            } else {
                resStepsContainer.classList.add('hidden');
            }

            renderMath();
        } catch (error) {
            errorMsg.textContent = `判题出错: ${error.message}`;
            errorMsg.classList.remove('hidden');
            setResultTone('is-empty');
        } finally {
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });
});
