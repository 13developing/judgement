document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('judge-form');
    const imageInput = document.getElementById('image-input');
    const uploadArea = document.getElementById('upload-area');
    const submitBtn = document.getElementById('submit-btn');
    const errorMsg = document.getElementById('error-message');
    const modeRadios = document.getElementsByName('judge_mode');
    const manualAnswerGroup = document.getElementById('manual-answer-group');
    const pagesPerSheetInput = document.getElementById('pages-per-sheet');
    const pagesPerSheetLabel = document.getElementById('pages-per-sheet-label');
    const sheetPreviewGrid = document.getElementById('sheet-preview-grid');
    const sheetPreviewEmpty = document.getElementById('sheet-preview-empty');
    const scoreTableBody = document.getElementById('score-table-body');
    const sheetModal = document.getElementById('sheet-modal');
    const sheetModalBackdrop = document.getElementById('sheet-modal-backdrop');
    const sheetModalClose = document.getElementById('sheet-modal-close');
    const sheetModalTitle = document.getElementById('sheet-modal-title');
    const sheetModalMeta = document.getElementById('sheet-modal-meta');
    const sheetModalBody = document.getElementById('sheet-modal-body');
    const detailModal = document.getElementById('detail-modal');
    const detailModalBackdrop = document.getElementById('detail-modal-backdrop');
    const detailModalClose = document.getElementById('detail-modal-close');
    const detailModalTitle = document.getElementById('detail-modal-title');
    const detailModalMeta = document.getElementById('detail-modal-meta');
    const detailStudentNameInput = document.getElementById('detail-student-name');
    const detailSubjectInput = document.getElementById('detail-subject');
    const detailSaveBtn = document.getElementById('detail-save-btn');

    const resultPlaceholder = document.getElementById('result-placeholder');
    const resultContent = document.getElementById('result-content');
    const resScore = document.getElementById('res-score');
    const resTotal = document.getElementById('res-total');
    const resType = document.getElementById('res-type');
    const resJudgment = document.getElementById('res-judgment');
    const resSubject = document.getElementById('res-subject');
    const resRecognized = document.getElementById('res-recognized');
    const resExplanation = document.getElementById('res-explanation');
    const resStepsContainer = document.getElementById('res-steps-container');
    const resStepsTableBody = document.querySelector('#res-steps-table tbody');
    const uploadText = uploadArea.querySelector('.upload-text');
    const uploadHint = uploadArea.querySelector('.upload-hint');
    const resultSummary = document.querySelector('.detail-summary');
    let groupedSheets = [];
    let examSheets = [];
    let activeSheetId = null;

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

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

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
        trh.innerHTML = headers.map(h => `<th>${escapeHtml(h)}</th>`).join('');
        thead.appendChild(trh);

        rows.forEach((r) => {
            const tr = document.createElement('tr');
            const filename = r.card_filename || '';
            const scores = Array.isArray(r.scores) ? r.scores : [];
            const total = (r.total_score ?? '');
            const err = r.error || '';

            const cells = [];
            cells.push(`<td>${escapeHtml(String(filename))}</td>`);
            for (let i = 0; i < questionCount; i++) {
                cells.push(`<td>${escapeHtml(String(scores[i] ?? ''))}</td>`);
            }
            cells.push(`<td>${escapeHtml(String(total))}</td>`);
            cells.push(`<td>${escapeHtml(String(err))}</td>`);

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

    function formatCreatedAt(value) {
        if (!value) {
            return '-';
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }

        const datePart = date.toLocaleDateString('zh-CN');
        const timePart = date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
        return `${datePart}<br>${timePart}`;
    }

    function renderMath() {
        if (window.renderMathInElement) {
            renderMathInElement(detailModal, {
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

    function getPagesPerSheet() {
        const value = Number.parseInt(pagesPerSheetInput.value, 10);
        return Number.isFinite(value) && value > 0 ? value : 1;
    }

    function groupFiles(files) {
        const pagesPerSheet = getPagesPerSheet();
        const groups = [];
        for (let i = 0; i < files.length; i += pagesPerSheet) {
            groups.push(files.slice(i, i + pagesPerSheet));
        }
        return groups;
    }

    function renderGroupedSheets() {
        const files = Array.from(imageInput.files || []);
        groupedSheets = groupFiles(files);
        pagesPerSheetLabel.textContent = String(getPagesPerSheet());

        if (!files.length) {
            uploadArea.classList.remove('has-file');
            uploadText.textContent = '点击或拖拽上传答题图片';
            uploadHint.textContent = '支持多选图片，按拍摄顺序连续分组';
            sheetPreviewEmpty.classList.remove('hidden');
            sheetPreviewGrid.classList.add('hidden');
            sheetPreviewGrid.innerHTML = '';
            return;
        }

        uploadArea.classList.add('has-file');
        uploadText.textContent = `已选择 ${files.length} 张图片`;
        uploadHint.textContent = `已自动分成 ${groupedSheets.length} 份答卷，可点击卡片查看`;

        sheetPreviewEmpty.classList.add('hidden');
        sheetPreviewGrid.classList.remove('hidden');
        sheetPreviewGrid.innerHTML = '';

        groupedSheets.forEach((group, index) => {
            const card = document.createElement('button');
            card.type = 'button';
            card.className = 'sheet-card';
            card.innerHTML = `
                <span class="sheet-card-title">第 ${index + 1} 份答卷</span>
                <span class="sheet-card-meta">${group.length} 张图片</span>
                <span class="sheet-card-files">${group.map((file) => file.name).join(' / ')}</span>
            `;
            card.addEventListener('click', () => {
                openSheetModal({
                    title: `第 ${index + 1} 份答卷`,
                    meta: `按上传顺序展示，共 ${group.length} 页`,
                    images: group.map((file) => ({ url: URL.createObjectURL(file), name: file.name })),
                });
            });
            sheetPreviewGrid.appendChild(card);
        });
    }

    imageInput.addEventListener('change', renderGroupedSheets);
    pagesPerSheetInput.addEventListener('input', renderGroupedSheets);

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

    function openSheetModal({ title, meta, images }) {
        sheetModalTitle.textContent = title;
        sheetModalMeta.textContent = meta;
        sheetModalBody.innerHTML = '';

        images.forEach((image, index) => {
            const block = document.createElement('div');
            block.className = 'sheet-modal-page';
            block.innerHTML = `
                <div class="sheet-modal-page-header">第 ${index + 1} 页${image.name ? ` · ${image.name}` : ''}</div>
                <img src="${image.url}" alt="${title} 第 ${index + 1} 页" class="sheet-modal-image">
            `;
            sheetModalBody.appendChild(block);
        });

        sheetModal.classList.remove('hidden');
        sheetModalBackdrop.classList.remove('hidden');
    }

    function closeSheetModal() {
        sheetModal.classList.add('hidden');
        sheetModalBackdrop.classList.add('hidden');
    }

    function openDetailModal(data) {
        activeSheetId = data.id ?? null;
        detailModalTitle.textContent = `${data.student_name || '未识别学生'} 的成绩详情`;
        detailModalMeta.textContent = `${data.subject || '未识别科目'} · ${data.page_count || 0} 页答卷`;
        detailStudentNameInput.value = data.student_name || '';
        detailSubjectInput.value = data.subject || '';
        updateResultPanel(data);
        detailModal.classList.remove('hidden');
        detailModalBackdrop.classList.remove('hidden');
    }

    function closeDetailModal() {
        activeSheetId = null;
        detailModal.classList.add('hidden');
        detailModalBackdrop.classList.add('hidden');
    }

    function replaceExamSheet(updatedSheet) {
        examSheets = examSheets.map((sheet) => sheet.id === updatedSheet.id ? updatedSheet : sheet);
        renderScoreTable();
    }

    sheetModalClose.addEventListener('click', closeSheetModal);
    sheetModalBackdrop.addEventListener('click', closeSheetModal);
    detailModalClose.addEventListener('click', closeDetailModal);
    detailModalBackdrop.addEventListener('click', closeDetailModal);

    modeRadios.forEach((radio) => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'manual') {
                manualAnswerGroup.classList.remove('hidden');
            } else {
                manualAnswerGroup.classList.add('hidden');
            }
        });
    });

    function updateResultPanel(data) {
        resultPlaceholder.classList.add('hidden');
        resultContent.classList.remove('hidden');

        resScore.textContent = data.score ?? '-';
        resTotal.textContent = data.total_score ?? '100';
        resType.textContent = data.student_name || '未识别学生';
        resSubject.textContent = `科目：${data.subject || '未识别'}`;
        resJudgment.textContent = data.judgment || 'partial';

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

        if (data.page_summaries && data.page_summaries.length > 0) {
            resStepsContainer.classList.remove('hidden');
            resStepsTableBody.innerHTML = '';
            data.page_summaries.forEach((summary, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>第 ${idx + 1} 页</td>
                    <td>${normalizeDisplayText(summary) || '-'}</td>
                `;
                resStepsTableBody.appendChild(tr);
            });
        } else {
            resStepsContainer.classList.add('hidden');
        }

        renderMath();
    }

    async function deleteExamSheet(sheet) {
        const confirmed = window.confirm(`确定删除 ${sheet.student_name || '该学生'} 的成绩记录吗？`);
        if (!confirmed) {
            return;
        }

        const response = await fetch(`/api/judge/exam-sheets/${sheet.id}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || '删除成绩记录失败');
        }

        examSheets = examSheets.filter((item) => item.id !== sheet.id);
        renderScoreTable();
        closeDetailModal();
    }

    async function saveSheetMetadata() {
        if (!activeSheetId) {
            return;
        }

        const studentName = detailStudentNameInput.value.trim();
        const subject = detailSubjectInput.value.trim();
        if (!studentName || !subject) {
            throw new Error('姓名和科目都不能为空');
        }

        detailSaveBtn.disabled = true;
        try {
            const response = await fetch(`/api/judge/exam-sheets/${activeSheetId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    student_name: studentName,
                    subject,
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '保存失败');
            }

            const updatedSheet = await response.json();
            replaceExamSheet(updatedSheet);
            openDetailModal(updatedSheet);
        } finally {
            detailSaveBtn.disabled = false;
        }
    }

    function renderScoreTable() {
        scoreTableBody.innerHTML = '';
        if (!examSheets.length) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="7" class="table-state-cell">暂无成绩记录</td>';
            scoreTableBody.appendChild(tr);
            return;
        }

        examSheets.forEach((sheet) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="cell-name">${sheet.student_name || '未识别'}</td>
                <td class="cell-subject">${sheet.subject || '未识别'}</td>
                <td class="cell-score">${sheet.score ?? '-'} / ${sheet.total_score ?? '-'}</td>
                <td class="cell-time">${formatCreatedAt(sheet.created_at)}</td>
                <td class="cell-action"><button type="button" class="btn btn-outline table-link-btn">查看答卷</button></td>
                <td class="cell-action"><button type="button" class="btn btn-outline table-link-btn">查看详情</button></td>
                <td class="cell-action"><button type="button" class="btn btn-danger table-link-btn">删除</button></td>
            `;
            const buttons = tr.querySelectorAll('button');
            buttons[0].addEventListener('click', (event) => {
                event.stopPropagation();
                openSheetModal({
                    title: `${sheet.student_name || '未识别学生'} 的答卷`,
                    meta: `${sheet.subject || '未识别科目'} · ${sheet.page_count || 0} 页`,
                    images: (sheet.image_urls || []).map((url, index) => ({
                        url,
                        name: `第 ${index + 1} 页`,
                    })),
                });
            });
            buttons[1].addEventListener('click', (event) => {
                event.stopPropagation();
                openDetailModal(sheet);
            });
            buttons[2].addEventListener('click', async (event) => {
                event.stopPropagation();
                try {
                    await deleteExamSheet(sheet);
                } catch (error) {
                    errorMsg.textContent = `删除出错: ${error.message}`;
                    errorMsg.classList.remove('hidden');
                }
            });
            scoreTableBody.appendChild(tr);
        });
    }

    detailSaveBtn.addEventListener('click', async () => {
        try {
            await saveSheetMetadata();
        } catch (error) {
            errorMsg.textContent = `保存出错: ${error.message}`;
            errorMsg.classList.remove('hidden');
        }
    });

    async function loadExamSheets() {
        const response = await fetch('/api/judge/exam-sheets');
        if (!response.ok) {
            throw new Error('加载成绩列表失败');
        }
        examSheets = await response.json();
        resultPlaceholder.classList.toggle('hidden', examSheets.length > 0);
        resultContent.classList.toggle('hidden', examSheets.length === 0);
        renderScoreTable();
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorMsg.classList.add('hidden');

        if (!imageInput.files.length) {
            errorMsg.textContent = '请先上传答卷图片';
            errorMsg.classList.remove('hidden');
            return;
        }

        if (!groupedSheets.length) {
            errorMsg.textContent = '未生成有效答卷分组，请检查页数设置';
            errorMsg.classList.remove('hidden');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.classList.add('loading');

        try {
            const stdAnswer = document.getElementById('standard-answer').value;
            const createdSheets = [];

            for (const group of groupedSheets) {
                const formData = new FormData();
                group.forEach((file) => formData.append('images', file));
                if (stdAnswer) {
                    formData.append('standard_answer', stdAnswer);
                }

                const response = await fetch('/api/judge/exam-sheet', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.detail || '请求失败，请检查网络或后端服务');
                }

                createdSheets.push(await response.json());
            }

            await loadExamSheets();
            if (createdSheets.length) {
                openDetailModal(createdSheets[0]);
            }
        } catch (error) {
            errorMsg.textContent = `判题出错: ${error.message}`;
            errorMsg.classList.remove('hidden');
            setResultTone('is-empty');
        } finally {
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });

    loadExamSheets().catch(() => {
        renderScoreTable();
    });
});
