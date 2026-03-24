document.addEventListener('DOMContentLoaded', () => {
    let currentParsedQuestions = [];
    let currentSourceFile = '';
    let currentParsedBundles = [];

    const docInput = document.getElementById('doc-input');
    const uploadDocBtn = document.getElementById('upload-doc-btn');
    const previewContainer = document.getElementById('preview-container');
    const previewTableBody = document.querySelector('#preview-table tbody');
    const previewCount = document.getElementById('preview-count');
    const confirmImportBtn = document.getElementById('confirm-import-btn');
    const docUploadArea = document.getElementById('doc-upload-area');
    const docUploadText = docUploadArea.querySelector('.upload-text');
    const docUploadHint = docUploadArea.querySelector('.upload-hint');

    const toggleManualBtn = document.getElementById('toggle-manual-btn');
    const manualAddForm = document.getElementById('manual-add-form');
    const cancelManualBtn = document.getElementById('cancel-manual-btn');
    const addQForm = document.getElementById('add-q-form');
    const saveManualBtn = document.getElementById('save-manual-btn');

    const searchKeyword = document.getElementById('search-keyword');
    const filterType = document.getElementById('filter-type');
    const searchBtn = document.getElementById('search-btn');
    const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
    const selectAllCheckbox = document.getElementById('select-all-questions');

    const bankTableBody = document.querySelector('#bank-table tbody');
    const loadMoreBtn = document.getElementById('load-more-btn');
    const mathPreviewPopover = document.getElementById('math-preview-popover');
    const mathPreviewBackdrop = document.getElementById('math-preview-backdrop');
    const mathPreviewTitle = document.getElementById('math-preview-title');
    const mathPreviewContent = document.getElementById('math-preview-content');
    const mathPreviewClose = document.getElementById('math-preview-close');

    let currentOffset = 0;
    const LIMIT = 50;
    const selectedQuestionIds = new Set();
    let hoverPreviewTimer = null;
    let isPreviewPinned = false;

    const truncate = (str, len = 40) => {
        if (!str) return '';
        return str.length > len ? str.substring(0, len) + '...' : str;
    };

    const hasMathMarkup = (str) => /(\$\$[\s\S]*?\$\$|\$[^$]+\$|\\\(|\\\)|\\\[|\\\])/.test(str || '');

    const looksLikeBareLatex = (str) => {
        if (!str) return false;
        return /(\\[a-zA-Z]+|\^|_|\{.+\}|\b(?:sin|cos|tan|ln|log|lim|int|sum|pi|theta)\b)/.test(str);
    };

    const prepareMathContent = (str) => {
        if (!str) return '-';
        if (hasMathMarkup(str)) return str;
        if (looksLikeBareLatex(str)) return `$${str}$`;
        return str;
    };

    const formatCellContent = (str, len = 40) => {
        if (!str) return '-';
        const prepared = prepareMathContent(str);
        return hasMathMarkup(prepared) ? prepared : truncate(prepared, len);
    };

    function renderMath() {
        if (window.renderMathInElement) {
            renderMathInElement(document.body, {
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

    function renderMathFor(element) {
        if (window.renderMathInElement) {
            renderMathInElement(element, {
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

    function schedulePreviewHide() {
        if (isPreviewPinned) return;
        clearTimeout(hoverPreviewTimer);
        hoverPreviewTimer = setTimeout(() => {
            mathPreviewPopover.classList.add('hidden');
            mathPreviewPopover.classList.remove('is-pinned');
            mathPreviewBackdrop.classList.add('hidden');
            mathPreviewPopover.setAttribute('aria-hidden', 'true');
        }, 120);
    }

    function hidePreview() {
        clearTimeout(hoverPreviewTimer);
        isPreviewPinned = false;
        mathPreviewPopover.classList.add('hidden');
        mathPreviewPopover.classList.remove('is-pinned');
        mathPreviewBackdrop.classList.add('hidden');
        mathPreviewPopover.setAttribute('aria-hidden', 'true');
    }

    function showPreview(title, content, anchor, pinned = false) {
        clearTimeout(hoverPreviewTimer);
        isPreviewPinned = pinned;
        mathPreviewTitle.textContent = title;
        mathPreviewContent.textContent = prepareMathContent(content || '-');
        mathPreviewPopover.classList.remove('hidden');
        mathPreviewPopover.setAttribute('aria-hidden', 'false');
        mathPreviewPopover.classList.toggle('is-pinned', pinned);
        mathPreviewBackdrop.classList.toggle('hidden', !pinned);

        if (!pinned && anchor) {
            const rect = anchor.getBoundingClientRect();
            const width = 560;
            const maxLeft = Math.max(16, window.innerWidth - width - 16);
            const left = Math.min(Math.max(16, rect.left), maxLeft);
            const top = Math.min(rect.bottom + 12, window.innerHeight - 280);
            mathPreviewPopover.style.left = `${left}px`;
            mathPreviewPopover.style.top = `${Math.max(16, top)}px`;
        } else {
            mathPreviewPopover.style.left = '';
            mathPreviewPopover.style.top = '';
        }

        renderMathFor(mathPreviewContent);
    }

    function createMathPreviewCell(content, previewTitle, truncateLength) {
        const td = document.createElement('td');
        const wrapper = document.createElement('div');
        const preview = document.createElement('div');
        const actions = document.createElement('div');
        const button = document.createElement('button');

        wrapper.className = 'math-preview-trigger';
        preview.className = 'math-cell math-cell-collapsed';
        actions.className = 'math-preview-actions';
        button.className = 'math-cell-more';
        button.type = 'button';
        button.textContent = '展开';

        preview.textContent = formatCellContent(content, truncateLength);
        actions.appendChild(button);
        wrapper.appendChild(preview);
        wrapper.appendChild(actions);
        td.appendChild(wrapper);

        wrapper.addEventListener('mouseenter', () => showPreview(previewTitle, content || '-', wrapper, false));
        wrapper.addEventListener('mouseleave', schedulePreviewHide);
        wrapper.addEventListener('focusin', () => showPreview(previewTitle, content || '-', wrapper, false));
        wrapper.addEventListener('focusout', schedulePreviewHide);
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            showPreview(previewTitle, content || '-', wrapper, true);
        });

        return td;
    }

    function updateBulkDeleteState() {
        const hasSelection = selectedQuestionIds.size > 0;
        bulkDeleteBtn.classList.toggle('hidden', !hasSelection);
        bulkDeleteBtn.textContent = hasSelection ? `批量删除 (${selectedQuestionIds.size})` : '批量删除';

        const rowCheckboxes = Array.from(document.querySelectorAll('.question-select-checkbox'));
        const checkedCount = rowCheckboxes.filter((checkbox) => checkbox.checked).length;
        selectAllCheckbox.checked = rowCheckboxes.length > 0 && checkedCount === rowCheckboxes.length;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < rowCheckboxes.length;
    }

    async function deleteQuestions(ids) {
        const uniqueIds = [...new Set(ids.map(Number).filter(Boolean))];
        if (uniqueIds.length === 0) return;

        try {
            const response = await fetch('/api/questions/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: uniqueIds })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || '删除失败');
            }

            selectedQuestionIds.clear();
            loadQuestions(true);
        } catch (error) {
            alert(`错误: ${error.message}`);
        }
    }

    function formatSelectedFiles(files, emptyLabel) {
        if (!files.length) return emptyLabel;
        if (files.length === 1) return files[0].name;
        return `${files[0].name} 等 ${files.length} 份文件`;
    }

    docInput.addEventListener('change', () => {
        docUploadArea.classList.toggle('has-file', docInput.files.length > 0);
        docUploadText.textContent = formatSelectedFiles(docInput.files, '批量上传试卷 / 答案 PDF');
        docUploadHint.textContent = docInput.files.length
            ? '文件已选择，系统会自动识别试卷与答案并按名称匹配'
            : '一键多选导入，系统会按文件名自动匹配，例如 `L-A.pdf` 对应 `L-A答案.pdf`';
    });

    mathPreviewPopover.addEventListener('mouseenter', () => clearTimeout(hoverPreviewTimer));
    mathPreviewPopover.addEventListener('mouseleave', schedulePreviewHide);
    mathPreviewBackdrop.addEventListener('click', hidePreview);
    mathPreviewClose.addEventListener('click', hidePreview);

    uploadDocBtn.addEventListener('click', async () => {
        if (!docInput.files.length) {
            alert('请先选择要导入的 PDF / Word 文档');
            return;
        }

        const formData = new FormData();
        Array.from(docInput.files).forEach((file) => formData.append('files', file));

        uploadDocBtn.disabled = true;
        uploadDocBtn.classList.add('loading');

        try {
            const response = await fetch('/api/upload/document', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('文档解析失败');
            const data = await response.json();

            currentParsedQuestions = data.questions || [];
            currentParsedBundles = data.bundles || [];
            currentSourceFile = data.filename || '批量导入';

            previewTableBody.innerHTML = '';
            currentParsedQuestions.forEach((q) => {
                const tr = document.createElement('tr');
                const typeCell = document.createElement('td');
                typeCell.innerHTML = `<span class="badge">${q.question_type}</span>`;
                tr.appendChild(typeCell);
                tr.appendChild(createMathPreviewCell(q.content, '题面预览', 30));
                tr.appendChild(createMathPreviewCell(q.standard_answer, '标准答案预览', 30));
                previewTableBody.appendChild(tr);
            });

            previewCount.textContent = `${data.filename}，共解析到 ${currentParsedQuestions.length} 道题目`;
            previewContainer.classList.remove('hidden');
            renderMath();
        } catch (error) {
            alert(`错误: ${error.message}`);
        } finally {
            uploadDocBtn.disabled = false;
            uploadDocBtn.classList.remove('loading');
        }
    });

    confirmImportBtn.addEventListener('click', async () => {
        if (currentParsedQuestions.length === 0) return;

        confirmImportBtn.disabled = true;
        confirmImportBtn.classList.add('loading');

        try {
            const response = await fetch('/api/upload/document/confirm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    questions: currentParsedQuestions,
                    source_file: currentSourceFile,
                    bundles: currentParsedBundles
                })
            });

            if (!response.ok) throw new Error('导入失败');
            const data = await response.json();

            alert(`成功导入 ${data.imported || currentParsedQuestions.length} 道题目`);
            previewContainer.classList.add('hidden');
            currentParsedBundles = [];
            docInput.value = '';
            docUploadArea.classList.remove('has-file');
            docUploadText.textContent = '批量上传试卷 / 答案 PDF';
            docUploadHint.textContent = '一键多选导入，系统会按文件名自动匹配，例如 `L-A.pdf` 对应 `L-A答案.pdf`';
            loadQuestions(true);
        } catch (error) {
            alert(`错误: ${error.message}`);
        } finally {
            confirmImportBtn.disabled = false;
            confirmImportBtn.classList.remove('loading');
        }
    });

    toggleManualBtn.addEventListener('click', () => manualAddForm.classList.toggle('hidden'));
    cancelManualBtn.addEventListener('click', () => manualAddForm.classList.add('hidden'));

    addQForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        saveManualBtn.disabled = true;
        saveManualBtn.classList.add('loading');

        const payload = {
            question_type: document.getElementById('add-q-type').value,
            content: document.getElementById('add-q-content').value,
            standard_answer: document.getElementById('add-q-answer').value,
            source_file: '手动添加'
        };

        try {
            const response = await fetch('/api/questions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('保存失败');

            alert('添加成功');
            addQForm.reset();
            manualAddForm.classList.add('hidden');
            loadQuestions(true);
        } catch (error) {
            alert(`错误: ${error.message}`);
        } finally {
            saveManualBtn.disabled = false;
            saveManualBtn.classList.remove('loading');
        }
    });

    async function loadQuestions(reset = false) {
        if (reset) {
            currentOffset = 0;
            selectedQuestionIds.clear();
            bankTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center;">加载中...</td></tr>';
            updateBulkDeleteState();
        }

        const kw = searchKeyword.value;
        const qt = filterType.value;

        try {
            const url = new URL(window.location.origin + '/api/questions');
            if (kw) url.searchParams.append('keyword', kw);
            if (qt) url.searchParams.append('question_type', qt);
            url.searchParams.append('offset', currentOffset);
            url.searchParams.append('limit', LIMIT);

            const response = await fetch(url);
            if (!response.ok) throw new Error('获取题库失败');

            const questions = await response.json();

            if (reset) bankTableBody.innerHTML = '';

            if (questions.length === 0 && reset) {
                bankTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">暂无题目数据</td></tr>';
                loadMoreBtn.classList.add('hidden');
                updateBulkDeleteState();
                return;
            }

            questions.forEach((q, idx) => {
                const tr = document.createElement('tr');
                const isChecked = selectedQuestionIds.has(q.id);

                const checkboxCell = document.createElement('td');
                checkboxCell.className = 'checkbox-col';
                checkboxCell.innerHTML = `<input type="checkbox" class="question-select-checkbox" data-id="${q.id}" ${isChecked ? 'checked' : ''} aria-label="选择题目 ${currentOffset + idx + 1}">`;

                const indexCell = document.createElement('td');
                indexCell.textContent = currentOffset + idx + 1;

                const typeCell = document.createElement('td');
                typeCell.innerHTML = `<span class="badge">${q.question_type}</span>`;

                const sourceCell = document.createElement('td');
                sourceCell.innerHTML = `<small style="color:var(--text-secondary)">${q.source_file || '-'}</small>`;

                const actionCell = document.createElement('td');
                actionCell.innerHTML = `<button class="btn btn-danger delete-btn" style="padding: 4px 8px; font-size: 0.8rem;" data-id="${q.id}">删除</button>`;

                tr.appendChild(checkboxCell);
                tr.appendChild(indexCell);
                tr.appendChild(typeCell);
                tr.appendChild(createMathPreviewCell(q.content, '题面预览', 35));
                tr.appendChild(createMathPreviewCell(q.standard_answer, '标准答案预览', 35));
                tr.appendChild(sourceCell);
                tr.appendChild(actionCell);
                bankTableBody.appendChild(tr);
            });

            document.querySelectorAll('.delete-btn').forEach((btn) => {
                btn.onclick = async function() {
                    if (!confirm('确定要删除这道题吗？')) return;
                    const id = this.getAttribute('data-id');
                    selectedQuestionIds.delete(Number(id));
                    await deleteQuestions([id]);
                };
            });

            document.querySelectorAll('.question-select-checkbox').forEach((checkbox) => {
                checkbox.onchange = function() {
                    const id = Number(this.getAttribute('data-id'));
                    if (this.checked) {
                        selectedQuestionIds.add(id);
                    } else {
                        selectedQuestionIds.delete(id);
                    }
                    updateBulkDeleteState();
                };
            });

            updateBulkDeleteState();

            if (questions.length === LIMIT) {
                loadMoreBtn.classList.remove('hidden');
            } else {
                loadMoreBtn.classList.add('hidden');
            }

            renderMath();
        } catch (error) {
            bankTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--error);">错误: ${error.message}</td></tr>`;
            updateBulkDeleteState();
        }
    }

    searchBtn.addEventListener('click', () => loadQuestions(true));

    selectAllCheckbox.addEventListener('change', () => {
        const checked = selectAllCheckbox.checked;
        document.querySelectorAll('.question-select-checkbox').forEach((checkbox) => {
            checkbox.checked = checked;
            const id = Number(checkbox.getAttribute('data-id'));
            if (checked) {
                selectedQuestionIds.add(id);
            } else {
                selectedQuestionIds.delete(id);
            }
        });
        updateBulkDeleteState();
    });

    bulkDeleteBtn.addEventListener('click', async () => {
        const ids = [...selectedQuestionIds];
        if (ids.length === 0) return;
        if (!confirm(`确定要批量删除已选中的 ${ids.length} 道题吗？`)) return;
        await deleteQuestions(ids);
    });

    loadMoreBtn.addEventListener('click', () => {
        currentOffset += LIMIT;
        loadQuestions();
    });

    loadQuestions(true);
});
