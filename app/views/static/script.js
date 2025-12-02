document.addEventListener("DOMContentLoaded", function() {
    const uploadForm = document.getElementById("UploadFile");
    const responseBox = document.querySelector("pre.box");
    const list = document.getElementById("resources-list");
    const syncConfig = document.getElementById("sync-config");
    
    // Get selected store from localStorage
    const selectedStore = localStorage.getItem('selectedStore');
    
    // Override fetch to add store header
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const [url, options = {}] = args;
        if (selectedStore) {
            options.headers = {
                ...options.headers,
                'X-Selected-Store': selectedStore
            };
        }
        return originalFetch(url, options);
    };
    
    // Update storeSelected based on localStorage
    if (selectedStore) {
        window.storeSelected = true;
        // Show the file sections
        document.getElementById('files-section').style.display = 'block';
        document.getElementById('upload-section').style.display = 'block';
    }
    
    // Store selector functionality
    const storeBoxes = document.querySelectorAll(".store-box");
    storeBoxes.forEach(box => {
        box.addEventListener("click", function() {
            const storeName = this.dataset.store;
            const storeId = this.dataset.storeId;
            const storeTitle = this.querySelector('h3').textContent;
            
            // Save selected store to localStorage
            localStorage.setItem('selectedStore', storeId);
            localStorage.setItem('selectedStoreName', storeName);
            
            // Reload the page to apply the store selection
            window.location.reload();
        });
    });
    
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
            <h2>Quantity Update Strategy</h2>
            <p style="color: #bdbdbd; font-size: 1rem; margin-bottom: 1em;">
                Choose how inventory quantities should be updated:
            </p>
            <div style="display: flex; gap: 1em; flex-wrap: wrap; margin-bottom: 1.5em;">
                <button class="sync-mode-btn" data-mode="tabula_rasa" style="flex: 1; min-width: 200px; padding: 15px; border: 2px solid #444; background: #2a2a2a; color: white; border-radius: 8px; cursor: pointer; transition: all 0.3s;">
                    <strong>Tabula Rasa</strong>
                    <p style="font-size: 0.85em; margin-top: 5px; color: #bdbdbd;">Set all to 0, then apply file values</p>
                </button>
                
                <button class="sync-mode-btn active" data-mode="adjust" style="flex: 1; min-width: 200px; padding: 15px; border: 2px solid var(--color-primary); background: #2a2a2a; color: white; border-radius: 8px; cursor: pointer; transition: all 0.3s;">
                    <strong>Adjust Quantity</strong>
                    <p style="font-size: 0.85em; margin-top: 5px; color: #bdbdbd;">Add/subtract from existing</p>
                </button>
                
                <button class="sync-mode-btn" data-mode="replace" style="flex: 1; min-width: 200px; padding: 15px; border: 2px solid #444; background: #2a2a2a; color: white; border-radius: 8px; cursor: pointer; transition: all 0.3s;">
                    <strong>Replace Quantity</strong>
                    <p style="font-size: 0.85em; margin-top: 5px; color: #bdbdbd;">Set to exact file values</p>
                </button>
            </div>
            <input type="hidden" id="selected-sync-mode" value="adjust">
            <button id="direct-sync" style="background: var(--color-primary); color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 1rem;">
                Sync "${filename}"
            </button>
        `;
        syncConfig.style.display = "block";
        
        // Add sync mode button listeners
        const syncModeButtons = document.querySelectorAll('.sync-mode-btn');
        const selectedModeInput = document.getElementById('selected-sync-mode');
        
        syncModeButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                syncModeButtons.forEach(b => {
                    b.classList.remove('active');
                    b.style.borderColor = '#444';
                });
                this.classList.add('active');
                this.style.borderColor = 'var(--color-primary)';
                selectedModeInput.value = this.dataset.mode;
            });
        });
        
        document.getElementById("direct-sync").onclick = () => {
            const mode = document.getElementById('selected-sync-mode').value;
            syncFile(filename, mode);
        };
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
                // File updated successfully, now show sync mode selection
                // Re-check the file to show sync UI
                await checkFileStructure(filename);
                saveAndSyncBtn.textContent = "Save to File & Sync";
                saveAndSyncBtn.disabled = false;
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
    async function syncFile(filename, syncMode = 'adjust') {
        try {
            const modeLabels = {
                'adjust': 'Adjusting',
                'replace': 'Replacing',
                'tabula_rasa': 'Resetting & Setting'
            };
            
            // Show loading spinner
            responseBox.innerHTML = `
                <div style="display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px;">
                    <div class="loader"></div>
                    <p style="margin-top: 20px; color: var(--color-primary);">${modeLabels[syncMode]} quantities for "${filename}"...</p>
                    <p style="color: #bdbdbd; font-size: 0.9rem;">This may take a few moments</p>
                </div>
            `;
            
            // Disable sync button if it exists
            const syncBtn = document.getElementById("direct-sync");
            if (syncBtn) {
                syncBtn.disabled = true;
                syncBtn.textContent = "Syncing...";
            }
            
            // Send sync mode as form data
            const formData = new FormData();
            formData.append('sync_mode', syncMode);
            
            const res = await fetch(`/api/v1/sync/${filename}`, { 
                method: "POST",
                body: formData
            });
            const data = await res.json();
            
            if (res.ok) {
                responseBox.innerHTML = buildSyncTable(data);
                // Hide the sync config and reset state
                resetSyncConfig();
                selectedFile = null;
                loadFiles();
            } else {
                responseBox.textContent = "Sync error: " + (data.detail || "Unknown error");
                // Re-enable button on error
                const syncBtn = document.getElementById("direct-sync");
                if (syncBtn) {
                    syncBtn.disabled = false;
                    syncBtn.textContent = `Sync "${filename}"`;
                }
            }
        } catch (err) {
            responseBox.textContent = "Sync error: " + err;
            // Re-enable button on error
            const syncBtn = document.getElementById("direct-sync");
            if (syncBtn) {
                syncBtn.disabled = false;
                syncBtn.textContent = `Sync "${filename}"`;
            }
        }
    }

    function loadingSpinner(show) {
        return `
            <div class="spinner" style="display: flex; justify-content: center; align-items: center; height: 100px;">
                <div class="loader"></div>
            </div>
        `;
    }


    function buildMissingSyncList(data) {
        if (data && Array.isArray(data.missing_rows) && data.missing_rows.length > 0) {
            return `
            <div class="missing-sync">
                <h3>${data.missing_rows.length} SKUs not updated (not found in store):</h3> (${((data.missing_rows.length / (data.total_records || data.missing_rows.length)) * 100).toFixed(2)}% of total items)
                <button class="copy-all-btn" style="display: flex;justify-content: center;align-items: center;" onclick='copyMissingSKUs(${JSON.stringify(data.missing_rows)})'>
                    <svg width="50px" height="50px" viewBox="0 0 1024 1024" class="icon"  version="1.1" xmlns="http://www.w3.org/2000/svg"><path d="M589.3 260.9v30H371.4v-30H268.9v513h117.2v-304l109.7-99.1h202.1V260.9z" fill="#E1F0FF" /><path d="M516.1 371.1l-122.9 99.8v346.8h370.4V371.1z" fill="#E1F0FF" /><path d="M752.7 370.8h21.8v435.8h-21.8z" fill="#446EB1" /><path d="M495.8 370.8h277.3v21.8H495.8z" fill="#446EB1" /><path d="M495.8 370.8h21.8v124.3h-21.8z" fill="#446EB1" /><path d="M397.7 488.7l-15.4-15.4 113.5-102.5 15.4 15.4z" fill="#446EB1" /><path d="M382.3 473.3h135.3v21.8H382.3z" fill="#446EB1" /><path d="M382.3 479.7h21.8v348.6h-21.8zM404.1 806.6h370.4v21.8H404.1z" fill="#446EB1" /><path d="M447.7 545.1h261.5v21.8H447.7zM447.7 610.5h261.5v21.8H447.7zM447.7 675.8h261.5v21.8H447.7z" fill="#6D9EE8" /><path d="M251.6 763h130.7v21.8H251.6z" fill="#446EB1" /><path d="M251.6 240.1h21.8v544.7h-21.8zM687.3 240.1h21.8v130.7h-21.8zM273.4 240.1h108.9v21.8H273.4z" fill="#446EB1" /><path d="M578.4 240.1h130.7v21.8H578.4zM360.5 196.5h21.8v108.9h-21.8zM382.3 283.7h196.1v21.8H382.3zM534.8 196.5h65.4v21.8h-65.4z" fill="#446EB1" /><path d="M360.5 196.5h65.4v21.8h-65.4zM404.1 174.7h152.5v21.8H404.1zM578.4 196.5h21.8v108.9h-21.8z" fill="#446EB1" /></svg>
                    <span> Copy All</span>
                </button>
            </div>
            `;
        }
        return "";
    }

    // Make this function global so it can be called from inline onclick
    window.copyMissingSKUs = function(missing_skus) {
        const skus = missing_skus || [];
        const btn = document.querySelector(".copy-all-btn");
        const originalText = btn.querySelector("span").innerHTML;

        if (skus.length === 0) return;
        const textToCopy = skus.join("\n");
        navigator.clipboard.writeText(textToCopy).then(() => {
            btn.querySelector("span").innerHTML = "Copied!";
            setTimeout(() => {
                btn.querySelector("span").innerHTML = originalText;
            }, 2000);
        }).catch(err => {
            alert("Failed to copy SKUs: " + err);
        });
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
            html += missed
            html += "<pre>" + JSON.stringify(data, null, 2) + "</pre>";
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
        // Don't load files if no store is selected
        if (!window.storeSelected) {
            return;
        }
        
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