document.addEventListener('DOMContentLoaded', () => {
    let currentParsedQuestions = [];
    let currentSourceFile = "";
    
    // UI Elements
    const docInput = document.getElementById('doc-input');
    const uploadDocBtn = document.getElementById('upload-doc-btn');
    const previewContainer = document.getElementById('preview-container');
    const previewTableBody = document.querySelector('#preview-table tbody');
    const previewCount = document.getElementById('preview-count');
    const confirmImportBtn = document.getElementById('confirm-import-btn');

    const toggleManualBtn = document.getElementById('toggle-manual-btn');
    const manualAddForm = document.getElementById('manual-add-form');
    const cancelManualBtn = document.getElementById('cancel-manual-btn');
    const addQForm = document.getElementById('add-q-form');
    const saveManualBtn = document.getElementById('save-manual-btn');

    const searchKeyword = document.getElementById('search-keyword');
    const filterType = document.getElementById('filter-type');
    const searchBtn = document.getElementById('search-btn');
    
    const bankTableBody = document.querySelector('#bank-table tbody');
    const loadMoreBtn = document.getElementById('load-more-btn');

    let currentOffset = 0;
    const LIMIT = 50;

    // Helper: Truncate text
    const truncate = (str, len = 40) => {
        if (!str) return '';
        return str.length > len ? str.substring(0, len) + '...' : str;
    };

    // Render Math
    function renderMath() {
        if (window.renderMathInElement) {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "\\[", right: "\\]", display: true},
                    {left: "$", right: "$", display: false},
                    {left: "\\(", right: "\\)", display: false}
                ],
                throwOnError: false
            });
        }
    }

    // --- Document Upload & Parsing ---
    uploadDocBtn.addEventListener('click', async () => {
        if (!docInput.files.length) {
            alert('请先选择要上传的文档');
            return;
        }

        const formData = new FormData();
        formData.append('file', docInput.files[0]);

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
            currentSourceFile = data.filename || docInput.files[0].name;

            previewTableBody.innerHTML = '';
            currentParsedQuestions.forEach(q => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><span class="badge">${q.question_type}</span></td>
                    <td title="${q.content}">${truncate(q.content, 30)}</td>
                    <td title="${q.standard_answer}">${truncate(q.standard_answer, 30)}</td>
                `;
                previewTableBody.appendChild(tr);
            });

            previewCount.textContent = `解析到 ${currentParsedQuestions.length} 道题目`;
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
                    source_file: currentSourceFile
                })
            });

            if (!response.ok) throw new Error('导入失败');
            const data = await response.json();
            
            alert(`成功导入 ${data.imported || currentParsedQuestions.length} 道题目`);
            previewContainer.classList.add('hidden');
            docInput.value = '';
            
            // Reload list
            loadQuestions(true);

        } catch (error) {
            alert(`错误: ${error.message}`);
        } finally {
            confirmImportBtn.disabled = false;
            confirmImportBtn.classList.remove('loading');
        }
    });

    // --- Manual Add ---
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

    // --- Question List ---
    async function loadQuestions(reset = false) {
        if (reset) {
            currentOffset = 0;
            bankTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">加载中...</td></tr>';
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
                bankTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">暂无题目数据</td></tr>';
                loadMoreBtn.classList.add('hidden');
                return;
            }

            questions.forEach((q, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${currentOffset + idx + 1}</td>
                    <td><span class="badge">${q.question_type}</span></td>
                    <td title="${q.content}">${truncate(q.content, 35)}</td>
                    <td title="${q.standard_answer}">${truncate(q.standard_answer, 35)}</td>
                    <td><small style="color:var(--text-secondary)">${q.source_file || '-'}</small></td>
                    <td>
                        <button class="btn btn-danger delete-btn" style="padding: 4px 8px; font-size: 0.8rem;" data-id="${q.id}">删除</button>
                    </td>
                `;
                bankTableBody.appendChild(tr);
            });

            // Bind delete events
            document.querySelectorAll('.delete-btn').forEach(btn => {
                btn.onclick = async function() {
                    if (!confirm('确定要删除这道题吗？')) return;
                    const id = this.getAttribute('data-id');
                    try {
                        const delRes = await fetch(`/api/questions/${id}`, { method: 'DELETE' });
                        if (delRes.ok) {
                            loadQuestions(true);
                        } else {
                            throw new Error('删除失败');
                        }
                    } catch (e) {
                        alert(`错误: ${e.message}`);
                    }
                };
            });

            if (questions.length === LIMIT) {
                loadMoreBtn.classList.remove('hidden');
            } else {
                loadMoreBtn.classList.add('hidden');
            }
            
            renderMath();

        } catch (error) {
            bankTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--error);">错误: ${error.message}</td></tr>`;
        }
    }

    searchBtn.addEventListener('click', () => loadQuestions(true));
    loadMoreBtn.addEventListener('click', () => {
        currentOffset += LIMIT;
        loadQuestions();
    });

    // Initial load
    loadQuestions(true);
});