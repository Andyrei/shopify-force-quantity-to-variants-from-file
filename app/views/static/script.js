document.addEventListener("DOMContentLoaded", function() {
    const uploadForm = document.getElementById("UploadFile");
    const responseBox = document.querySelector("pre.box");
    const list = document.getElementById("resources-list");

    // Handle file upload
    function handleUploadForm() {
        if (!uploadForm) return;
        uploadForm.addEventListener("submit", async function(e) {
            e.preventDefault();
            responseBox.textContent = "Uploading...";
            try {
                const res = await fetch(uploadForm.action, {
                    method: "POST",
                    body: new FormData(uploadForm),
                });
                const result = await res.json();
                console.log(result);
                
                responseBox.textContent = res.ok
                    ? JSON.stringify(result, null, 2)
                    : `Response error: ${res.status} - ${result.detail}`;

                loadFiles()
                syncFile(this, result.filename)
            } catch (err) {
                responseBox.textContent = "Error: " + err;
            }
        });
    }

    // Render file list with sync buttons
    function renderFileList(files) {
        if (!Array.isArray(files) || files.length === 0) {
            list.innerHTML = "<li>No files found.</li>";
            return;
        }
        list.innerHTML = files.map(f =>
            `<li>
                <span>${f}</span>
                <div>
                    <button class="sync-btn" data-filename="${encodeURIComponent(f)}">Sync</button>
                    <button class="del-btn" data-filename="${encodeURIComponent(f)}">Del</button>
                </div>
            </li>`
        ).join("");
        addSyncButtonListeners();
        addDeleteButtonListeners();
    }

    function buildMissingSyncList(data) {
        if (data && Array.isArray(data.missing_sync) && data.missing_sync.length > 0) {
            return `
            <div class="missing-sync">
                <h3>SKUs not updated (not found in store):</h3>
                <ul>
                    ${data.missing_sync.map(sku => `<li>${sku}</li>`).join("")}
                </ul>
            </div>
            `;
        }
        return "";
    }

    function buildSyncTable(data) {
        let html = ""
        const missed = buildMissingSyncList(data); // Add missing SKUs section first

        if (
            !data ||
            !data.data ||
            !data.data.inventoryAdjustQuantities ||
            !data.data.inventoryAdjustQuantities.inventoryAdjustmentGroup ||
            !Array.isArray(data.data.inventoryAdjustQuantities.inventoryAdjustmentGroup.changes)
        ) {
            html += "<pre>" + JSON.stringify(data, null, 2) + "</pre>";
            html += missed
            return html;
        }
        const changes = data.data.inventoryAdjustQuantities.inventoryAdjustmentGroup.changes;
        html += `<table class="sync-table">
            <caption>Inventory Adjustments</caption>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Product handle</th>
                    <th>Variant</th>
                    <th>Location</th>
                    <th>Quantity</th>
                    <th>Delta (+ / -)</th>
                </tr>
            </thead>
            <tbody>
        `;
        let rowNum = 1;
        changes.forEach(change => {
            const variant = change.item.variant;
            const product = variant.product;
            const variantName = variant.displayName || "-";
            const productName = product && product.handle ? product.handle.replace(/-/g, " ") : "-";
            const locations = change.item.inventoryLevels.nodes;
            locations.forEach(loc => {
                const locationName = loc.location.name;
                const quantityObj = loc.quantities.find(q => q.name === "available");
                const quantity = quantityObj ? quantityObj.quantity : "-";
                let delta = '-';
                if(change.location.id === loc.location.id ){
                    delta = change.delta
                }
                html += `<tr>
                    <td>${rowNum++}</td>
                    <td>${productName}</td>
                    <td>${variantName}</td>
                    <td>${locationName}</td>
                    <td>${quantity}</td>
                    <td>${delta}</td>
                </tr>`;
            });
        });
        html += "</tbody></table>";
        html += missed;
        return html;
    }

    // Add event listeners to sync buttons
    function addSyncButtonListeners() {
        list.querySelectorAll(".sync-btn").forEach(btn => {
            btn.addEventListener("click", async function() {
                const filename = this.getAttribute("data-filename");
                await syncFile(this, filename);
            });
        });
    }

    // Add event listeners to delete buttons
    function addDeleteButtonListeners() {
        list.querySelectorAll(".del-btn").forEach(btn => {
            btn.addEventListener("click", async function() {
                const filename = this.getAttribute("data-filename");
                if (confirm(`Delete file "${decodeURIComponent(filename)}"?`)) {
                    await deleteFile(this, filename);
                }
            });
        });
    }

    // Sync file handler
    async function syncFile(button, filename) {
        button.disabled = true;
        button.textContent = "Syncing...";
        try {
            const res = await fetch(`/api/v1/sync/${filename}`, { method: "POST" });
            const data = await res.json();
            if (res.ok) {
                button.textContent = "Synced!";
            } else {
                button.textContent = "Failed";
                if (responseBox) {
                    responseBox.textContent = "Sync error: " + err;
                }
            }

            // Show sync result in the <pre> box
            if (responseBox) {
                responseBox.innerHTML = buildSyncTable(data)
            }

        } catch (err) {
            button.textContent = "Error";
            if (responseBox) {
                responseBox.textContent = "Sync error: " + err;
            }
        }
        setTimeout(() => {
            button.textContent = "Sync";
            button.disabled = false;
        }, 2000);
    }

    // Delete file handler
    async function deleteFile(button, filename) {
        button.disabled = true;
        button.textContent = "Deleting...";
        try {
            const res = await fetch(`/api/v1/resources/${filename}`, { method: "DELETE" });
            const data = await res.json();
            if (res.ok) {
                button.closest("li").remove();
            } else {
                button.textContent = "Failed";
                alert(data.detail || "Delete failed");
                button.disabled = false;
                button.textContent = "Del";
            }
        } catch (err) {
            button.textContent = "Error";
            alert("Delete error: " + err);
            button.disabled = false;
            button.textContent = "Del";
        }

        loadFiles()
    }

    // Fetch and display files
    async function loadFiles() {
        try {
            const res = await fetch("/api/v1/resources");
            if (res.ok) {
                const files = await res.json();
                renderFileList(files);
            } else {
                list.innerHTML = "<li>Could not load files.</li>";
            }
        } catch {
            list.innerHTML = "<li>Error loading files.</li>";
        }
    }

    // Initialize
    handleUploadForm();
    loadFiles();
});