document.addEventListener('DOMContentLoaded', () => {
    const addProviderBtn = document.getElementById('add-provider-btn');
    const providerList = document.getElementById('provider-list');

    const modal = document.getElementById('provider-modal');
    const modalBackdrop = document.getElementById('provider-modal-backdrop');
    const modalTitle = document.getElementById('modal-title');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const modalTestBtn = document.getElementById('modal-test-btn');
    const modalSaveBtn = document.getElementById('modal-save-btn');
    const modalError = document.getElementById('modal-error');
    const providerForm = document.getElementById('provider-form');

    const pfName = document.getElementById('pf-name');
    const pfType = document.getElementById('pf-type');
    const pfApiKey = document.getElementById('pf-api-key');
    const pfBaseUrl = document.getElementById('pf-base-url');
    const pfModel = document.getElementById('pf-model');
    const pfBaseUrlHint = document.getElementById('pf-base-url-hint');
    const pfModelHint = document.getElementById('pf-model-hint');

    let providerDefaults = {};
    let editingProviderId = null;

    // ── Provider type defaults ──────────────────────────────────────

    async function loadProviderTypes() {
        try {
            const resp = await fetch('/api/providers/types');
            if (resp.ok) {
                providerDefaults = await resp.json();
            }
        } catch (_) {
            providerDefaults = {
                ark: { base_url: 'https://ark.cn-beijing.volces.com/api/v3', model: 'doubao-seed-2-0-lite-260215' },
                openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
            };
        }
        updatePlaceholders();
    }

    function updatePlaceholders() {
        const type = pfType.value;
        const defaults = providerDefaults[type] || {};
        pfBaseUrl.placeholder = defaults.base_url || '';
        pfModel.placeholder = defaults.model || '';
        pfBaseUrlHint.textContent = defaults.base_url ? `默认: ${defaults.base_url}` : '留空使用默认值';
        pfModelHint.textContent = defaults.model ? `默认: ${defaults.model}` : '留空使用默认值';
    }

    pfType.addEventListener('change', updatePlaceholders);

    // ── Provider list ───────────────────────────────────────────────

    async function loadProviders() {
        try {
            const resp = await fetch('/api/providers');
            if (!resp.ok) throw new Error('获取配置失败');
            const providers = await resp.json();

            if (providers.length === 0) {
                providerList.innerHTML =
                    '<div class="provider-empty state-message">' +
                    '尚未添加 Provider 配置，系统当前使用 .env 环境变量。' +
                    '</div>';
                return;
            }

            providerList.innerHTML = '';
            providers.forEach((p) => {
                const card = document.createElement('div');
                card.className = 'provider-card';
                if (p.is_active) card.classList.add('is-active');

                const typeName = p.provider_type === 'ark' ? '豆包 Ark' : 'OpenAI 兼容';
                const statusClass = p.is_active ? 'active' : '';
                const statusText = p.is_active ? '已启用' : '未启用';
                const toggleText = p.is_active ? '停用' : '启用';
                const toggleClass = p.is_active ? 'btn-outline' : 'btn-accent';

                card.innerHTML =
                    '<div class="provider-card-header">' +
                        '<div class="provider-card-name">' +
                            '<strong>' + escapeHtml(p.name) + '</strong>' +
                            '<span class="badge">' + typeName + '</span>' +
                        '</div>' +
                        '<span class="provider-status ' + statusClass + '">' + statusText + '</span>' +
                    '</div>' +
                    '<div class="provider-card-body">' +
                        '<div class="provider-detail"><span class="provider-detail-label">Base URL</span><span class="provider-detail-value">' + escapeHtml(p.base_url || '-') + '</span></div>' +
                        '<div class="provider-detail"><span class="provider-detail-label">Model</span><span class="provider-detail-value">' + escapeHtml(p.model || '-') + '</span></div>' +
                        '<div class="provider-detail"><span class="provider-detail-label">API Key</span><span class="provider-detail-value">' + escapeHtml(p.api_key_masked || '-') + '</span></div>' +
                    '</div>' +
                    '<div class="provider-card-actions">' +
                        '<button type="button" class="btn btn-outline provider-test-btn" data-id="' + p.id + '"><span class="spinner"></span><span class="btn-text">测试连接</span></button>' +
                        '<button type="button" class="btn btn-outline provider-edit-btn" data-id="' + p.id + '">编辑</button>' +
                        '<button type="button" class="btn ' + toggleClass + ' provider-toggle-btn" data-id="' + p.id + '" data-active="' + p.is_active + '">' + toggleText + '</button>' +
                        '<button type="button" class="btn btn-danger provider-delete-btn" data-id="' + p.id + '">删除</button>' +
                    '</div>';

                card._providerData = p;
                providerList.appendChild(card);
            });

            bindCardButtons();
        } catch (error) {
            providerList.innerHTML =
                '<div class="provider-empty state-message error-message">加载失败: ' + escapeHtml(error.message) + '</div>';
        }
    }

    function bindCardButtons() {
        document.querySelectorAll('.provider-test-btn').forEach((btn) => {
            btn.addEventListener('click', async function () {
                const id = this.getAttribute('data-id');
                this.disabled = true;
                this.classList.add('loading');
                try {
                    const resp = await fetch('/api/providers/' + id + '/test', { method: 'POST' });
                    if (!resp.ok) {
                        const data = await resp.json().catch(() => ({}));
                        throw new Error(data.detail || '测试失败');
                    }
                    alert('连接测试成功!');
                } catch (error) {
                    alert('连接测试失败: ' + error.message);
                } finally {
                    this.disabled = false;
                    this.classList.remove('loading');
                }
            });
        });

        document.querySelectorAll('.provider-edit-btn').forEach((btn) => {
            btn.addEventListener('click', function () {
                const id = Number(this.getAttribute('data-id'));
                const card = this.closest('.provider-card');
                const p = card._providerData;
                openEditModal(p);
            });
        });

        document.querySelectorAll('.provider-toggle-btn').forEach((btn) => {
            btn.addEventListener('click', async function () {
                const id = this.getAttribute('data-id');
                const isActive = this.getAttribute('data-active') === 'true';
                const action = isActive ? 'deactivate' : 'activate';
                try {
                    const resp = await fetch('/api/providers/' + id + '/' + action, { method: 'POST' });
                    if (!resp.ok) {
                        const data = await resp.json().catch(() => ({}));
                        throw new Error(data.detail || '操作失败');
                    }
                    loadProviders();
                } catch (error) {
                    alert('操作失败: ' + error.message);
                }
            });
        });

        document.querySelectorAll('.provider-delete-btn').forEach((btn) => {
            btn.addEventListener('click', async function () {
                const id = this.getAttribute('data-id');
                if (!confirm('确定要删除这个 Provider 配置吗？')) return;
                try {
                    const resp = await fetch('/api/providers/' + id, { method: 'DELETE' });
                    if (!resp.ok) {
                        const data = await resp.json().catch(() => ({}));
                        throw new Error(data.detail || '删除失败');
                    }
                    loadProviders();
                } catch (error) {
                    alert('删除失败: ' + error.message);
                }
            });
        });
    }

    // ── Modal ───────────────────────────────────────────────────────

    function openAddModal() {
        editingProviderId = null;
        modalTitle.textContent = '添加 Provider';
        providerForm.reset();
        pfApiKey.required = true;
        pfApiKey.placeholder = 'sk-...';
        updatePlaceholders();
        modalError.classList.add('hidden');
        showModal();
    }

    function openEditModal(provider) {
        editingProviderId = provider.id;
        modalTitle.textContent = '编辑 Provider';
        pfName.value = provider.name;
        pfType.value = provider.provider_type;
        pfApiKey.value = '';
        pfApiKey.required = false;
        pfApiKey.placeholder = '留空则不修改 (' + provider.api_key_masked + ')';
        pfBaseUrl.value = provider.base_url || '';
        pfModel.value = provider.model || '';
        updatePlaceholders();
        modalError.classList.add('hidden');
        showModal();
    }

    function showModal() {
        modal.classList.remove('hidden');
        modalBackdrop.classList.remove('hidden');
        pfName.focus();
    }

    function closeModal() {
        modal.classList.add('hidden');
        modalBackdrop.classList.add('hidden');
        editingProviderId = null;
    }

    addProviderBtn.addEventListener('click', openAddModal);
    modalCloseBtn.addEventListener('click', closeModal);
    modalCancelBtn.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', closeModal);

    // ── Save ────────────────────────────────────────────────────────

    providerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        modalError.classList.add('hidden');

        const payload = {
            name: pfName.value.trim(),
            provider_type: pfType.value,
            base_url: pfBaseUrl.value.trim(),
            model: pfModel.value.trim(),
        };

        if (!payload.name) {
            modalError.textContent = '请填写名称';
            modalError.classList.remove('hidden');
            return;
        }

        if (editingProviderId === null) {
            // Create
            if (!pfApiKey.value.trim()) {
                modalError.textContent = '请填写 API Key';
                modalError.classList.remove('hidden');
                return;
            }
            payload.api_key = pfApiKey.value.trim();
        } else {
            // Update — only include api_key if user entered one
            if (pfApiKey.value.trim()) {
                payload.api_key = pfApiKey.value.trim();
            }
        }

        modalSaveBtn.disabled = true;
        modalSaveBtn.classList.add('loading');

        try {
            const isEdit = editingProviderId !== null;
            const url = isEdit ? '/api/providers/' + editingProviderId : '/api/providers';
            const method = isEdit ? 'PUT' : 'POST';

            const resp = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data.detail || '保存失败');
            }

            closeModal();
            loadProviders();
        } catch (error) {
            modalError.textContent = error.message;
            modalError.classList.remove('hidden');
        } finally {
            modalSaveBtn.disabled = false;
            modalSaveBtn.classList.remove('loading');
        }
    });

    // ── Test connection (inline from modal) ─────────────────────────

    modalTestBtn.addEventListener('click', async () => {
        modalError.classList.add('hidden');

        const apiKey = pfApiKey.value.trim();

        // For saved providers without a new key, test via saved endpoint
        if (editingProviderId !== null && !apiKey) {
            modalTestBtn.disabled = true;
            modalTestBtn.classList.add('loading');
            try {
                const resp = await fetch('/api/providers/' + editingProviderId + '/test', { method: 'POST' });
                if (!resp.ok) {
                    const data = await resp.json().catch(() => ({}));
                    throw new Error(data.detail || '测试失败');
                }
                alert('连接测试成功!');
            } catch (error) {
                modalError.textContent = '测试失败: ' + error.message;
                modalError.classList.remove('hidden');
            } finally {
                modalTestBtn.disabled = false;
                modalTestBtn.classList.remove('loading');
            }
            return;
        }

        if (!apiKey) {
            modalError.textContent = '请先填写 API Key 再测试';
            modalError.classList.remove('hidden');
            return;
        }

        const payload = {
            provider_type: pfType.value,
            api_key: apiKey,
            base_url: pfBaseUrl.value.trim(),
            model: pfModel.value.trim(),
        };

        modalTestBtn.disabled = true;
        modalTestBtn.classList.add('loading');

        try {
            const resp = await fetch('/api/providers/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data.detail || '测试失败');
            }

            alert('连接测试成功!');
        } catch (error) {
            modalError.textContent = '测试失败: ' + error.message;
            modalError.classList.remove('hidden');
        } finally {
            modalTestBtn.disabled = false;
            modalTestBtn.classList.remove('loading');
        }
    });

    // ── Utils ────────────────────────────────────────────────────────

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Init ────────────────────────────────────────────────────────

    loadProviderTypes();
    loadProviders();
});
