document.addEventListener("DOMContentLoaded", function() {
    const uploadForm = document.getElementById("UploadFile");
    const responseBox = document.querySelector("pre.box");
    const list = document.getElementById("resources-list");
    const syncConfig = document.getElementById("sync-config");
    
    // These will be updated when the HTML is reset
    let locationField = document.getElementById("location-field");
    let saleChannelField = document.getElementById("sale-channel-field");
    let saveAndSyncBtn = document.getElementById("save-and-sync");
    
    let selectedFile = null;

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
            } catch (err) {
                responseBox.textContent = "Error: " + err;
            }
        });
    }

    // Render file list with check buttons (no sync buttons initially)
    function renderFileList(files) {
        if (!Array.isArray(files) || files.length === 0) {
            list.innerHTML = "<li>No files found.</li>";
            return;
        }
        list.innerHTML = files.map(f =>
            `<li>
                <span>${f}</span>
                <div>
                    <button class="check-btn" data-filename="${encodeURIComponent(f)}">Select & Check</button>
                    <button class="del-btn" data-filename="${encodeURIComponent(f)}">Del</button>
                </div>
            </li>`
        ).join("");
        addCheckButtonListeners();
        addDeleteButtonListeners();
    }

    // Check file structure and show configuration if needed
    async function checkFileStructure(filename) {
        try {
            // Reset the sync config panel first
            resetSyncConfig();
            
            const res = await fetch(`/api/v1/check/${filename}`, { method: "GET" });
            const data = await res.json();
            
            if (res.ok) {
                selectedFile = filename;
                
                if (data.ready_to_sync) {
                    // File has all required data, show sync button directly
                    showSyncButton(filename);
                    responseBox.innerHTML = `
                        <div style="color: var(--color-primary);">
                            ✓ File "${filename}" is ready to sync!<br>
                            Found all required columns: ${data.columns.join(", ")}
                        </div>
                    `;
                } else {
                    // File is missing some data, show configuration
                    showMissingFieldsConfig(data);
                    responseBox.innerHTML = `
                        <div style="color: var(--color-highlight);">
                            ⚠ File "${filename}" is missing required data.<br>
                            Please fill in the missing information below.
                        </div>
                    `;
                }
            } else {
                responseBox.textContent = "Check error: " + (data.detail || "Unknown error");
            }
        } catch (err) {
            responseBox.textContent = "Check error: " + err;
        }
    }

    // Reset sync configuration panel
    function resetSyncConfig() {
        // Always reset to original structure first
        syncConfig.innerHTML = `
            <h2>Missing Required Data</h2>
            <p style="color: #bdbdbd; font-size: 1.2rem; margin-bottom: 1em;">
                Please provide the missing information for this file:
            </p>
            <div style="margin-bottom: 1em;">
                <div id="location-field" style="display: none; margin-bottom: 10px;">
                    <label for="location-id">Location ID (ID Sede):</label>
                    <input type="text" id="location-id" placeholder="e.g. 101947474247" style="margin-left: 10px; padding: 8px; width: 200px;">
                </div>
                
                <div id="sale-channel-field" style="display: none; margin-bottom: 10px;">
                    <label for="sale-channel">Sale Channel (Canale di Vendita):</label>
                    <input type="text" id="sale-channel" placeholder="e.g. 176929734983" style="margin-left: 10px; padding: 8px; width: 200px;">
                </div>
                
                <button id="save-and-sync" style="display: none; margin-top: 10px; background: var(--color-primary); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">
                    Save to File & Sync
                </button>
            </div>
        `;
        
        // Re-get references to the elements since we reset the HTML
        updateElementReferences();
        
        // Hide the entire panel
        syncConfig.style.display = "none";
        
        // Make sure all fields are hidden
        if (locationField) locationField.style.display = "none";
        if (saleChannelField) saleChannelField.style.display = "none";
        if (saveAndSyncBtn) saveAndSyncBtn.style.display = "none";
    }

    // Update element references after HTML reset
    function updateElementReferences() {
        // Wait a bit for DOM to update, then get new references
        setTimeout(() => {
            const newLocationField = document.getElementById("location-field");
            const newSaleChannelField = document.getElementById("sale-channel-field");
            const newSaveAndSyncBtn = document.getElementById("save-and-sync");
            
            if (newLocationField) locationField = newLocationField;
            if (newSaleChannelField) saleChannelField = newSaleChannelField;
            if (newSaveAndSyncBtn) saveAndSyncBtn = newSaveAndSyncBtn;
            
            console.log("Updated element references:", {
                locationField: !!locationField,
                saleChannelField: !!saleChannelField,
                saveAndSyncBtn: !!saveAndSyncBtn
            });
        }, 10);
    }

    // Show configuration for missing fields
    function showMissingFieldsConfig(fileData) {
        // Wait for element references to be updated
        setTimeout(() => {
            syncConfig.style.display = "block";
            
            // Update element references in case they were reset
            updateElementReferences();
            
            // Wait a bit more for references to update, then show/hide fields
            setTimeout(() => {
                // Show/hide fields based on what's missing
                if (fileData.missing_fields.includes("location_id")) {
                    if (locationField) locationField.style.display = "block";
                } else {
                    if (locationField) locationField.style.display = "none";
                }
                
                if (fileData.missing_fields.includes("sale_channel")) {
                    if (saleChannelField) saleChannelField.style.display = "block";
                } else {
                    if (saleChannelField) saleChannelField.style.display = "none";
                }
                
                if (saveAndSyncBtn) {
                    saveAndSyncBtn.style.display = "block";
                    saveAndSyncBtn.onclick = () => saveToFileAndSync(selectedFile);
                }
            }, 20);
        }, 10);
    }

    // Show sync button directly if file is ready
    function showSyncButton(filename) {
        syncConfig.innerHTML = `
            <h2>Ready to Sync</h2>
            <button id="direct-sync" style="background: var(--color-primary); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">
                Sync "${filename}"
            </button>
        `;
        syncConfig.style.display = "block";
        
        document.getElementById("direct-sync").onclick = () => syncFile(filename);
    }

    // Save missing data to file and then sync
    async function saveToFileAndSync(filename) {
        // Update element references in case they were reset
        updateElementReferences();
        
        const locationId = document.getElementById("location-id").value.trim();
        const saleChannel = document.getElementById("sale-channel").value.trim();
        
        // Validate required fields
        let missingFields = [];
        if (locationField.style.display !== "none" && !locationId) {
            missingFields.push("Location ID");
        }
        if (saleChannelField.style.display !== "none" && !saleChannel) {
            missingFields.push("Sale Channel");
        }
        
        if (missingFields.length > 0) {
            alert(`Please fill in: ${missingFields.join(", ")}`);
            return;
        }
        
        saveAndSyncBtn.disabled = true;
        saveAndSyncBtn.textContent = "Saving & Syncing...";
        
        try {
            // Update file with missing data
            const formData = new FormData();
            if (locationId) formData.append("location_id", locationId);
            if (saleChannel) formData.append("sale_channel", saleChannel);
            
            const updateRes = await fetch(`/api/v1/update-file/${filename}`, {
                method: "POST",
                body: formData
            });
            
            if (updateRes.ok) {
                // File updated successfully, now sync
                await syncFile(filename);
            } else {
                const updateData = await updateRes.json();
                responseBox.textContent = "Update error: " + (updateData.detail || "Unknown error");
                saveAndSyncBtn.textContent = "Save to File & Sync";
                saveAndSyncBtn.disabled = false;
            }
        } catch (err) {
            responseBox.textContent = "Update error: " + err;
            saveAndSyncBtn.textContent = "Save to File & Sync";
            saveAndSyncBtn.disabled = false;
        }
    }

    // Sync file
    async function syncFile(filename) {
        try {
            const res = await fetch(`/api/v1/sync/${filename}`, { method: "POST" });
            const data = await res.json();
            
            if (res.ok) {
                responseBox.innerHTML = buildSyncTable(data);
                // Hide the sync config and reset state
                resetSyncConfig();
                selectedFile = null;
                loadFiles();
            } else {
                responseBox.textContent = "Sync error: " + (data.detail || "Unknown error");
            }
        } catch (err) {
            responseBox.textContent = "Sync error: " + err;
        }
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

    // Add event listeners to check buttons
    function addCheckButtonListeners() {
        list.querySelectorAll(".check-btn").forEach(btn => {
            btn.addEventListener("click", async function() {
                const filename = decodeURIComponent(this.getAttribute("data-filename"));
                this.disabled = true;
                this.textContent = "Checking...";
                
                await checkFileStructure(filename);
                
                this.textContent = "Select & Check";
                this.disabled = false;
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

    // Delete file handler
    async function deleteFile(button, filename) {
        button.disabled = true;
        button.textContent = "Deleting...";
        try {
            const res = await fetch(`/api/v1/resources/${filename}`, { method: "DELETE" });
            const data = await res.json();
            if (res.ok) {
                button.closest("li").remove();
                // Hide sync config if this was the selected file
                if (selectedFile === decodeURIComponent(filename)) {
                    syncConfig.style.display = "none";
                    selectedFile = null;
                }
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