document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('judge-form');
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const uploadArea = document.getElementById('upload-area');
    const submitBtn = document.getElementById('submit-btn');
    const errorMsg = document.getElementById('error-message');
    const modeRadios = document.getElementsByName('judge_mode');
    const manualAnswerGroup = document.getElementById('manual-answer-group');

    // UI Elements for result
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

    // Image preview
    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                uploadArea.style.padding = '20px';
            }
            reader.readAsDataURL(file);
        }
    });

    // Drag and drop
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

    // Toggle manual answer textarea
    modeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'manual') {
                manualAnswerGroup.classList.remove('hidden');
            } else {
                manualAnswerGroup.classList.add('hidden');
            }
        });
    });

    function renderMath() {
        if (window.renderMathInElement) {
            renderMathInElement(document.getElementById('result-content'), {
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

    // Form submission
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
            
            // Render results
            resultPlaceholder.classList.add('hidden');
            resultContent.classList.remove('hidden');

            resScore.textContent = data.score ?? '-';
            resTotal.textContent = data.total_score ?? '100';
            resType.textContent = data.question_type || '未知题型';
            resJudgment.textContent = data.judgment || (data.score > 0 ? '得分' : '不得分');
            
            // Set colors based on judgment
            if (data.score === data.total_score && data.total_score > 0) {
                resJudgment.style.color = 'var(--success)';
            } else if (data.score === 0) {
                resJudgment.style.color = 'var(--error)';
            } else {
                resJudgment.style.color = 'var(--accent)';
            }

            resRecognized.textContent = data.recognized_content || '未识别出内容';
            resExplanation.textContent = data.explanation || '无详细点评';

            // Steps
            if (data.steps && data.steps.length > 0) {
                resStepsContainer.classList.remove('hidden');
                resStepsTableBody.innerHTML = '';
                data.steps.forEach((step, idx) => {
                    const tr = document.createElement('tr');
                    const statusClass = step.status === '✓' ? 'status-check' : (step.status === '✗' ? 'status-cross' : '');
                    tr.innerHTML = `
                        <td>步骤 ${idx + 1}</td>
                        <td>${step.score || 0}</td>
                        <td class="${statusClass}">${step.status || '-'}</td>
                        <td>${step.comment || '-'}</td>
                    `;
                    resStepsTableBody.appendChild(tr);
                });
            } else {
                resStepsContainer.classList.add('hidden');
            }

            // Render math formulas
            renderMath();

        } catch (error) {
            errorMsg.textContent = `判题出错: ${error.message}`;
            errorMsg.classList.remove('hidden');
        } finally {
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });
});