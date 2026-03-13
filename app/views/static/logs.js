document.addEventListener("DOMContentLoaded", function() {
    const logsSection = document.getElementById("logs-section");
    const logsList = document.getElementById("logs-list");
    const refreshBtn = document.getElementById("refresh-logs");
    const previewSection = document.getElementById("log-preview-section");
    const previewTitle = document.getElementById("log-preview-title");
    const previewContent = document.getElementById("log-preview-content");
    const downloadBtn = document.getElementById("download-log-btn");

    let selectedLog = null;

    const selectedStore = localStorage.getItem("selectedStore");

    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        let [url, options = {}] = args;
        if (typeof url === "string" && url.startsWith("/") && window.ROOT_PATH) {
            url = window.ROOT_PATH + url;
        }
        if (selectedStore) {
            options.headers = {
                ...options.headers,
                "X-Selected-Store": selectedStore,
            };
        }
        return originalFetch(url, options);
    };

    if (selectedStore && logsSection) {
        window.storeSelected = true;
        logsSection.style.display = "block";
    }

    const storeBoxes = document.querySelectorAll(".store-box");
    storeBoxes.forEach((box) => {
        if (selectedStore && box.dataset.storeId === selectedStore) {
            box.classList.add("active");
            const badge = box.querySelector(".active-badge");
            if (badge) {
                badge.style.display = "inline-block";
            }
        }

        box.addEventListener("click", function() {
            const storeName = this.dataset.store;
            const storeId = this.dataset.storeId;

            localStorage.setItem("selectedStore", storeId);
            localStorage.setItem("selectedStoreName", storeName);

            window.location.reload();
        });
    });

    function formatSize(bytes) {
        if (!Number.isFinite(bytes) || bytes < 1024) {
            return `${bytes || 0} B`;
        }
        const kb = bytes / 1024;
        if (kb < 1024) {
            return `${kb.toFixed(1)} KB`;
        }
        return `${(kb / 1024).toFixed(1)} MB`;
    }

    function renderLogs(logs) {
        if (!logsList) {
            return;
        }

        if (!Array.isArray(logs) || logs.length === 0) {
            logsList.innerHTML = "<li>No logs found for this store.</li>";
            return;
        }

        logsList.innerHTML = logs.map((log) => {
            const encodedFilename = encodeURIComponent(log.filename);
            return `
                <li class="log-row">
                    <div class="log-info">
                        <strong>${log.filename}</strong>
                        <small class="log-meta">${(log.type || "file").toUpperCase()} | ${formatSize(log.size_bytes)} | ${log.modified_at}</small>
                    </div>
                    <div class="log-actions">
                        <button class="view-log-btn" data-filename="${encodedFilename}">View</button>
                        <button class="download-log-btn" data-filename="${encodedFilename}">Download</button>
                        <button class="delete-log-btn" data-filename="${encodedFilename}">Delete</button>
                    </div>
                </li>
            `;
        }).join("");

        attachLogActionListeners();
    }

    async function viewLog(filename) {
        if (!previewSection || !previewTitle || !previewContent || !downloadBtn) {
            return;
        }

        selectedLog = filename;
        previewSection.style.display = "block";
        previewTitle.textContent = `Log Preview - ${filename}`;
        previewContent.textContent = "Loading log preview...";
        downloadBtn.style.display = "inline-block";

        try {
            const res = await fetch(`/api/v1/logs/content/${encodeURIComponent(filename)}?lines=400`);
            const text = await res.text();

            if (!res.ok) {
                previewContent.textContent = `Error loading log: ${text || res.statusText}`;
                return;
            }

            previewContent.textContent = text || "(empty file)";
        } catch (err) {
            previewContent.textContent = `Error loading log: ${err}`;
        }
    }

    async function downloadLog(filename) {
        try {
            const res = await fetch(`/api/v1/logs/download/${encodeURIComponent(filename)}`);
            if (!res.ok) {
                const message = await res.text();
                throw new Error(message || `Download failed (${res.status})`);
            }

            const blob = await res.blob();
            const objectUrl = URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();

            URL.revokeObjectURL(objectUrl);
        } catch (err) {
            alert(`Could not download log: ${err}`);
        }
    }

    async function deleteLog(filename) {
        const shouldDelete = confirm(`Delete log file \"${filename}\"?`);
        if (!shouldDelete) {
            return;
        }

        try {
            const res = await fetch(`/api/v1/logs/${encodeURIComponent(filename)}`, {
                method: "DELETE",
            });
            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || `Delete failed (${res.status})`);
            }

            if (selectedLog === filename) {
                selectedLog = null;
                if (previewSection) {
                    previewSection.style.display = "none";
                }
                if (previewContent) {
                    previewContent.textContent = "Select a log file from the list to preview its content.";
                }
            }

            await loadLogs();
        } catch (err) {
            alert(`Could not delete log: ${err}`);
        }
    }

    function attachLogActionListeners() {
        if (!logsList) {
            return;
        }

        logsList.querySelectorAll(".view-log-btn").forEach((btn) => {
            btn.addEventListener("click", async function() {
                const filename = decodeURIComponent(this.getAttribute("data-filename"));
                await viewLog(filename);
            });
        });

        logsList.querySelectorAll(".download-log-btn").forEach((btn) => {
            btn.addEventListener("click", async function() {
                const filename = decodeURIComponent(this.getAttribute("data-filename"));
                await downloadLog(filename);
            });
        });

        logsList.querySelectorAll(".delete-log-btn").forEach((btn) => {
            btn.addEventListener("click", async function() {
                const filename = decodeURIComponent(this.getAttribute("data-filename"));
                await deleteLog(filename);
            });
        });
    }

    async function loadLogs() {
        if (!window.storeSelected || !logsList) {
            return;
        }

        logsList.innerHTML = "<li>Loading logs...</li>";

        try {
            const res = await fetch("/api/v1/logs");
            if (!res.ok) {
                logsList.innerHTML = "<li>Could not load logs for this store.</li>";
                return;
            }

            const logs = await res.json();
            renderLogs(logs);
        } catch (err) {
            logsList.innerHTML = `<li>Error loading logs: ${err}</li>`;
        }
    }

    if (refreshBtn) {
        refreshBtn.addEventListener("click", async function() {
            await loadLogs();
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener("click", async function() {
            if (!selectedLog) {
                return;
            }
            await downloadLog(selectedLog);
        });
    }

    loadLogs();
});
