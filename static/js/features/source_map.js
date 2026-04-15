(function () {
    async function fetchJson(url) {
        const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
        return await res.json();
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // normalizeDomain 已不再使用（当前数据直接来自后端聚合）

    function sizeToStyle(count, maxCount) {
        // 更强烈的视觉权重：使用幂次缩放拉大极差
        // count=max 时 ratio=1；count 很小时会显著变小
        const max = Math.max(1, maxCount || 1);
        const ratio = Math.max(0, Math.min(1, count / max));
        const gamma = 0.55; // <1: 强化高频差异
        const scaled = Math.pow(ratio, gamma);
        const fontSize = 12 + Math.round(scaled * 34); // 12..46
        const opacity = 0.55 + scaled * 0.45;
        return { fontSize, opacity, scaled };
    }

    function pickRotation(idx, scaled) {
        // 少量竖排（约 15%），并且更偏向低权重词，避免大词旋转影响阅读
        if (scaled >= 0.72) return 0;
        return (idx % 7 === 0) ? -90 : 0;
    }

    function formatCountLabel(count) {
        return `${count}封`;
    }

    function showCloudTooltip(text, x, y) {
        let tip = document.getElementById('wordCloudTooltip');
        if (!tip) {
            tip = document.createElement('div');
            tip.id = 'wordCloudTooltip';
            tip.className = 'wc-tooltip';
            document.body.appendChild(tip);
        }
        tip.textContent = text;
        tip.style.left = (x + 12) + 'px';
        tip.style.top = (y + 12) + 'px';
        tip.classList.add('show');
    }

    function hideCloudTooltip() {
        const tip = document.getElementById('wordCloudTooltip');
        if (tip) tip.classList.remove('show');
    }

    function renderWordCloud(container, items) {
        if (!container) return;
        if (!items || items.length === 0) {
            container.innerHTML = `<div style="color:var(--text-muted);">暂无数据（需要先拉取/缓存邮件）。</div>`;
            return;
        }
        const maxCount = Math.max(...items.map(i => i.count || 0), 1);
        const palette = ['#F59E0B', '#22C55E', '#60A5FA', '#A78BFA', '#F87171', '#34D399', '#FB7185'];
        container.innerHTML = items.map((it, idx) => {
            const s = sizeToStyle(it.count, maxCount);
            const color = palette[idx % palette.length];
            const tooltip = `${it.domain}: ${formatCountLabel(it.count)}`;
            const rot = pickRotation(idx, s.scaled);
            const label = escapeHtml(String(it.domain || ''));
            const countLabel = escapeHtml(formatCountLabel(it.count));
            // title 作为兜底，Tooltip 由 JS 控制
            return `
              <span class="word-cloud-item" 
                    title="${escapeHtml(tooltip)}"
                    data-tooltip="${escapeHtml(tooltip)}"
                    style="font-size:${s.fontSize}px;opacity:${s.opacity};color:${color};transform:rotate(${rot}deg);">
                <span class="wc-word">${label}</span>
                <span class="wc-count">${countLabel}</span>
              </span>`;
        }).join('');

        // 交互 Tooltip
        container.querySelectorAll('.word-cloud-item').forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const text = el.getAttribute('data-tooltip') || '';
                showCloudTooltip(text, e.clientX, e.clientY);
            });
            el.addEventListener('mouseleave', () => hideCloudTooltip());
        });
    }

    function renderTopDomains(listEl, items) {
        if (!listEl) return;
        if (!items || items.length === 0) {
            listEl.innerHTML = `<li style="color:var(--text-muted);padding:1rem;">暂无数据</li>`;
            return;
        }
        listEl.innerHTML = items.slice(0, 12).map(it => {
            return `<li><span>${escapeHtml(it.domain)}</span><span class="badge badge-gray">${it.count}</span></li>`;
        }).join('');
    }

    function renderGraph(container, data) {
        if (!container) return;
        const accounts = data?.accounts || [];
        const edges = data?.edges || [];
        const domains = data?.domains || [];

        if (accounts.length === 0) {
            container.innerHTML = `<div style="color:var(--text-muted);">暂无数据</div>`;
            return;
        }

        // Minimal graph layout: left accounts, right domains
        const accountHtml = accounts.map(a => `<div class="sm-node sm-node-account">${escapeHtml(a)}</div>`).join('');
        const domainHtml = domains.map(d => `<div class="sm-node sm-node-domain" title="${escapeHtml(d.domain)} (${d.count})">${escapeHtml(d.domain)}<span class="sm-node-badge">${d.count}</span></div>`).join('');

        const edgeHtml = edges.map(e => {
            return `<div class="sm-edge"><span class="sm-edge-left">${escapeHtml(e.account)}</span><span class="sm-edge-mid">→</span><span class="sm-edge-right">${escapeHtml(e.domain)}</span><span class="sm-edge-count">${e.count}</span></div>`;
        }).join('');

        container.innerHTML = `
            <div class="sm-graph">
                <div class="sm-graph-col">
                    <div class="sm-graph-col-title">账号</div>
                    ${accountHtml}
                </div>
                <div class="sm-graph-col sm-graph-col-edges">
                    <div class="sm-graph-col-title">关联（Top 连接）</div>
                    <div class="sm-edges">${edgeHtml || `<div style="color:var(--text-muted);">暂无连接</div>`}</div>
                </div>
                <div class="sm-graph-col">
                    <div class="sm-graph-col-title">域名</div>
                    ${domainHtml}
                </div>
            </div>
        `;
    }

    async function loadAccountsIntoSelect(selectEl) {
        if (!selectEl) return;
        // 从 /api/accounts 拉所有账号（后端已有接口）
        const data = await fetchJson('/api/accounts');
        const accounts = (data && data.success && data.accounts) ? data.accounts : [];
        const options = [`<option value="">全部账号</option>`].concat(accounts.map(a => {
            const email = a.email || '';
            return `<option value="${escapeHtml(email)}">${escapeHtml(email)}</option>`;
        }));
        selectEl.innerHTML = options.join('');
    }

    window.initSourceMapPage = async function initSourceMapPage() {
        const accountSelect = document.getElementById('sourceMapAccountSelect');
        const windowSelect = document.getElementById('sourceMapWindowSelect');
        if (accountSelect && !accountSelect.dataset.loaded) {
            accountSelect.dataset.loaded = '1';
            try { await loadAccountsIntoSelect(accountSelect); } catch (e) { /* ignore */ }
        }
        if (windowSelect && !windowSelect.value) windowSelect.value = '30d';
    };

    window.loadSourceMap = async function loadSourceMap() {
        const accountSelect = document.getElementById('sourceMapAccountSelect');
        const windowSelect = document.getElementById('sourceMapWindowSelect');
        const wordCloudEl = document.getElementById('sourceMapWordCloud');
        const topDomainsEl = document.getElementById('sourceMapTopDomains');
        const graphEl = document.getElementById('sourceMapGraph');

        if (wordCloudEl) wordCloudEl.innerHTML = `<div class="loading-overlay" style="position:relative;"><span class="spinner"></span> 加载中…</div>`;
        if (topDomainsEl) topDomainsEl.innerHTML = `<li style="padding:1rem;color:var(--text-muted);">加载中…</li>`;
        if (graphEl) graphEl.innerHTML = `<div style="padding:1rem;color:var(--text-muted);">加载中…</div>`;

        const email = accountSelect ? accountSelect.value : '';
        const windowKey = windowSelect ? windowSelect.value : '30d';

        const qs = new URLSearchParams();
        if (email) qs.set('email', email);
        if (windowKey) qs.set('window', windowKey);

        const data = await fetchJson('/api/analytics/source-domains?' + qs.toString());
        if (!data || !data.success) {
            const msg = (data && data.error && data.error.message) ? data.error.message : '加载失败';
            if (wordCloudEl) wordCloudEl.innerHTML = `<div style="color:var(--text-muted);">${escapeHtml(msg)}</div>`;
            if (topDomainsEl) topDomainsEl.innerHTML = `<li style="padding:1rem;color:var(--text-muted);">${escapeHtml(msg)}</li>`;
            if (graphEl) graphEl.innerHTML = `<div style="padding:1rem;color:var(--text-muted);">${escapeHtml(msg)}</div>`;
            return;
        }

        renderWordCloud(wordCloudEl, data.word_cloud || []);
        renderTopDomains(topDomainsEl, data.top_domains || []);
        renderGraph(graphEl, data.graph || {});
    };
})();
