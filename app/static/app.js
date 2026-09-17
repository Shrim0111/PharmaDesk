
/* =========================================================
   MedStock Pharmacy
   Frontend application
   ========================================================= */

const API_BASE = "";

let accessToken = localStorage.getItem("medstock_token") || "";
let currentPage = 1;

const pageSize = 8;


/* =========================================================
   DOM helpers
   ========================================================= */

function $(id) {
    return document.getElementById(id);
}


function show(element) {
    if (element) {
        element.classList.remove("hidden");
    }
}


function hide(element) {
    if (element) {
        element.classList.add("hidden");
    }
}


function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* =========================================================
   Toasts
   ========================================================= */

let toastTimer = null;


function showToast(message, type = "success") {
    const toast = $("toast");

    if (!toast) {
        return;
    }

    toast.textContent = message;

    toast.className = "toast";

    if (type === "error") {
        toast.classList.add("error");
    } else {
        toast.classList.add("success");
    }

    show(toast);

    if (toastTimer) {
        clearTimeout(toastTimer);
    }

    toastTimer = setTimeout(() => {
        hide(toast);
    }, 3500);
}


/* =========================================================
   API helper
   ========================================================= */

async function apiRequest(
    path,
    options = {}
) {
    const headers = new Headers(
        options.headers || {}
    );

    if (
        options.body &&
        !(options.body instanceof FormData) &&
        !headers.has("Content-Type")
    ) {
        headers.set(
            "Content-Type",
            "application/json"
        );
    }

    if (accessToken) {
        headers.set(
            "Authorization",
            `Bearer ${accessToken}`
        );
    }

    const response = await fetch(
        `${API_BASE}${path}`,
        {
            ...options,
            headers
        }
    );

    let data = null;

    const contentType =
        response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        data = await response.text();
    }

    if (!response.ok) {
        let message = "Something went wrong.";

        if (data && typeof data === "object") {
            if (Array.isArray(data.detail)) {
                message = data.detail
                    .map(item => {
                        if (
                            item &&
                            typeof item === "object" &&
                            item.msg
                        ) {
                            return item.msg;
                        }

                        return String(item);
                    })
                    .join(", ");
            } else if (data.detail) {
                message = data.detail;
            } else if (data.message) {
                message = data.message;
            }
        } else if (data) {
            message = String(data);
        }

        throw new Error(message);
    }

    return data;
}


/* =========================================================
   Authentication UI
   ========================================================= */

function updateAuthUI() {
    const loggedIn =
        Boolean(accessToken);

    const inventoryLocked =
        $("inventoryLocked");

    const inventoryContent =
        $("inventoryContent");

    const automationLocked =
        $("automationLocked");

    const automationContent =
        $("automationContent");

    const logoutButton =
        $("logoutButton");

    if (loggedIn) {
        hide(inventoryLocked);
        show(inventoryContent);

        hide(automationLocked);
        show(automationContent);

        show(logoutButton);

        loadCurrentUser();
        loadMedicines();
        loadAlerts();
        loadOutbox();
        loadHeroStats();
    } else {
        show(inventoryLocked);
        hide(inventoryContent);

        show(automationLocked);
        hide(automationContent);

        hide(logoutButton);

        $("userEmail").textContent = "";

        clearInventoryTable();
    }
}


async function loadCurrentUser() {
    if (!accessToken) {
        return;
    }

    try {
        const user = await apiRequest(
            "/auth/me"
        );

        $("userEmail").textContent =
            user.email || "";
    } catch (error) {
        console.error(error);

        logout(false);

        showToast(
            "Your session has expired. Please login again.",
            "error"
        );
    }
}


function logout(showMessage = true) {
    accessToken = "";

    localStorage.removeItem(
        "medstock_token"
    );

    updateAuthUI();

    if (showMessage) {
        showToast(
            "Logged out successfully."
        );
    }
}


/* =========================================================
   Registration
   ========================================================= */

async function handleRegister(event) {
    event.preventDefault();

    const email =
        $("registerEmail").value.trim();

    const password =
        $("registerPassword").value;

    if (!email || !password) {
        showToast(
            "Please enter email and password.",
            "error"
        );

        return;
    }

    try {
        await apiRequest(
            "/auth/register",
            {
                method: "POST",
                body: JSON.stringify({
                    email,
                    password
                })
            }
        );

        showToast(
            "Account created. You can now login."
        );

        $("registerForm").reset();

        $("loginEmail").value = email;

        $("loginPassword").focus();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Login
   ========================================================= */

async function handleLogin(event) {
    event.preventDefault();

    const email =
        $("loginEmail").value.trim();

    const password =
        $("loginPassword").value;

    if (!email || !password) {
        showToast(
            "Please enter email and password.",
            "error"
        );

        return;
    }

    try {
        const formData =
            new URLSearchParams();

        formData.append(
            "username",
            email
        );

        formData.append(
            "password",
            password
        );

        const response =
            await fetch(
                "/auth/login",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/x-www-form-urlencoded"
                    },
                    body: formData
                }
            );

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Invalid email or password."
            );
        }

        accessToken =
            data.access_token;

        localStorage.setItem(
            "medstock_token",
            accessToken
        );

        showToast(
            "Login successful."
        );

        $("loginForm").reset();

        updateAuthUI();

        scrollToSection("inventory");

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Medicine inventory
   ========================================================= */

async function loadMedicines() {
    if (!accessToken) {
        return;
    }

    const search =
        $("searchInput")?.value.trim() || "";

    const sortBy =
        $("sortBy")?.value || "name";

    const sortOrder =
        $("sortOrder")?.value || "asc";

    const params =
        new URLSearchParams();

    if (search) {
        params.set(
            "search",
            search
        );
    }

    params.set(
        "page",
        String(currentPage)
    );

    params.set(
        "page_size",
        String(pageSize)
    );

    params.set(
        "sort_by",
        sortBy
    );

    params.set(
        "sort_order",
        sortOrder
    );

    try {
        const data =
            await apiRequest(
                `/medicines?${params.toString()}`
            );

        renderMedicines(data);

    } catch (error) {
        if (
            error.message.includes(
                "credentials"
            )
        ) {
            logout(false);
        }

        showToast(
            error.message,
            "error"
        );
    }
}


function renderMedicines(data) {
    const tbody =
        $("medicineTableBody");

    const emptyState =
        $("emptyInventory");

    if (!tbody) {
        return;
    }

    tbody.innerHTML = "";

    const items =
        data.items || [];

    if (items.length === 0) {
        show(emptyState);
    } else {
        hide(emptyState);
    }

    items.forEach(medicine => {
        const row =
            document.createElement("tr");

        const stock =
            Number(
                medicine.sellable_stock || 0
            );

        const threshold =
            Number(
                medicine.reorder_threshold || 0
            );

        let stockClass =
            "stock-good";

        if (stock === 0) {
            stockClass = "stock-empty";
        } else if (
            stock < threshold
        ) {
            stockClass = "stock-low";
        }

        const expiry =
            medicine.nearest_expiry
                ? formatDate(
                    medicine.nearest_expiry
                )
                : "—";

        row.innerHTML = `
            <td>
                <div class="medicine-name">
                    ${escapeHtml(medicine.name)}
                </div>
            </td>

            <td>
                <span class="sku-text">
                    ${escapeHtml(medicine.sku)}
                </span>
            </td>

            <td>
                <span class="stock-value ${stockClass}">
                    ${stock}
                </span>
            </td>

            <td>
                <span class="expiry-text">
                    ${escapeHtml(expiry)}
                </span>
            </td>

            <td>
                ${threshold}
            </td>

            <td>
                <button
                    type="button"
                    class="button button-small button-outline"
                    onclick="viewStock(${medicine.id})"
                >
                    Stock
                </button>
            </td>
        `;

        tbody.appendChild(row);
    });

    const totalPages =
        Number(data.total_pages || 0);

    $("pageInfo").textContent =
        totalPages > 0
            ? `Page ${data.page} of ${totalPages}`
            : "Page 0 of 0";

    $("previousPageButton").disabled =
        currentPage <= 1;

    $("nextPageButton").disabled =
        totalPages === 0 ||
        currentPage >= totalPages;
}


function clearInventoryTable() {
    const tbody =
        $("medicineTableBody");

    if (tbody) {
        tbody.innerHTML = "";
    }

    hide($("emptyInventory"));

    $("pageInfo").textContent =
        "Page 1";
}


function changePage(direction) {
    const newPage =
        currentPage + direction;

    if (newPage < 1) {
        return;
    }

    currentPage = newPage;

    loadMedicines();
}


/* =========================================================
   Medicine creation
   ========================================================= */

async function handleMedicineCreate(event) {
    event.preventDefault();

    const name =
        $("medicineName").value.trim();

    const sku =
        $("medicineSku").value.trim();

    const reorderThreshold =
        Number(
            $("reorderThreshold").value
        );

    if (!name || !sku) {
        showToast(
            "Medicine name and SKU are required.",
            "error"
        );

        return;
    }

    try {
        const medicine =
            await apiRequest(
                "/medicines",
                {
                    method: "POST",
                    body: JSON.stringify({
                        name,
                        sku,
                        reorder_threshold:
                            reorderThreshold
                    })
                }
            );

        showToast(
            `Medicine ${medicine.name} created.`
        );

        $("medicineForm").reset();

        $("reorderThreshold").value =
            "10";

        currentPage = 1;

        await loadMedicines();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Batch creation
   ========================================================= */

async function handleBatchCreate(event) {
    event.preventDefault();

    const medicineId =
        Number(
            $("batchMedicineId").value
        );

    const batchNo =
        $("batchNumber").value.trim();

    const quantity =
        Number(
            $("batchQuantity").value
        );

    const expiryDate =
        $("batchExpiry").value;

    if (
        !medicineId ||
        !batchNo ||
        !quantity ||
        !expiryDate
    ) {
        showToast(
            "Please complete all batch fields.",
            "error"
        );

        return;
    }

    try {
        await apiRequest(
            "/batches",
            {
                method: "POST",
                body: JSON.stringify({
                    medicine_id: medicineId,
                    batch_no: batchNo,
                    quantity,
                    expiry_date: expiryDate
                })
            }
        );

        showToast(
            "Batch added successfully."
        );

        $("batchForm").reset();

        currentPage = 1;

        await loadMedicines();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Stock
   ========================================================= */

async function viewStock(medicineId) {
    try {
        const data =
            await apiRequest(
                `/medicines/${medicineId}/stock`
            );

        const batchLines =
            (data.batches || [])
                .map(batch => {
                    return (
                        `${batch.batch_no}: ` +
                        `${batch.quantity} units, ` +
                        `expires ${formatDate(batch.expiry_date)}`
                    );
                })
                .join("\n");

        const message =
            `${data.medicine_name} (${data.sku})\n\n` +
            `Sellable stock: ${data.sellable_stock}\n` +
            `Reorder threshold: ${data.reorder_threshold}\n\n` +
            `Sellable batches:\n` +
            `${batchLines || "None"}`;

        window.alert(message);

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Dispensing
   ========================================================= */

async function handleDispense(event) {
    event.preventDefault();

    const medicineId =
        Number(
            $("dispenseMedicineId").value
        );

    const quantity =
        Number(
            $("dispenseQuantity").value
        );

    if (
        !medicineId ||
        !quantity ||
        quantity <= 0
    ) {
        showToast(
            "Enter a valid medicine ID and quantity.",
            "error"
        );

        return;
    }

    try {
        const result =
            await apiRequest(
                `/medicines/${medicineId}/dispense`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        quantity
                    })
                }
            );

        const details =
            (result.fefo_deductions || [])
                .map(item => {
                    return (
                        `${item.batch_no}: ` +
                        `${item.quantity_dispensed} units`
                    );
                })
                .join(", ");

        showToast(
            `Dispensed ${result.dispensed} units using FEFO.`
        );

        $("dispenseForm").reset();

        if (details) {
            showClockResult(
                $("clockResult"),
                `FEFO batches used: ${details}`
            );
        }

        await loadMedicines();
        await loadHeroStats();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Daily clock
   ========================================================= */

async function runClock() {
    const button =
        $("clockButton");

    if (button) {
        button.disabled = true;
        button.textContent =
            "Running...";
    }

    try {
        const result =
            await apiRequest(
                "/clock",
                {
                    method: "POST"
                }
            );

        const message =
            `Clock completed on ${formatDate(result.run_date)}. ` +
            `Expired quarantined: ${result.expired_quarantined}. ` +
            `Expiry alerts created: ${result.expiry_alerts_created}. ` +
            `Reorder alerts created: ${result.reorder_alerts_created}.`;

        showClockResult(
            $("clockResult"),
            message
        );

        showToast(
            "Daily pharmacy clock completed."
        );

        await loadAlerts();
        await loadOutbox();
        await loadMedicines();
        await loadHeroStats();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent =
                "Run Clock";
        }
    }
}


function showClockResult(
    element,
    message
) {
    if (!element) {
        return;
    }

    element.textContent =
        message;

    show(element);
}


/* =========================================================
   Expiry alerts
   ========================================================= */

async function loadAlerts() {
    if (!accessToken) {
        return;
    }

    try {
        const alerts =
            await apiRequest(
                "/alerts"
            );

        renderAlerts(alerts);

        $("heroAlertCount").textContent =
            alerts.length;

    } catch (error) {
        console.error(
            "Unable to load alerts:",
            error
        );
    }
}


function renderAlerts(alerts) {
    const container =
        $("alertsList");

    if (!container) {
        return;
    }

    if (
        !alerts ||
        alerts.length === 0
    ) {
        container.innerHTML = `
            <p class="muted">
                No open expiry alerts.
            </p>
        `;

        return;
    }

    container.innerHTML =
        alerts
            .map(alert => {
                return `
                    <div class="alert-item">

                        <strong>
                            ${escapeHtml(
                                alert.medicine_name
                            )}
                            — ${escapeHtml(
                                alert.batch_no
                            )}
                        </strong>

                        <p>
                            Expires:
                            ${escapeHtml(
                                formatDate(
                                    alert.expiry_date
                                )
                            )}
                        </p>

                        <p>
                            ${escapeHtml(
                                alert.message
                            )}
                        </p>

                    </div>
                `;
            })
            .join("");
}


/* =========================================================
   Notification outbox
   ========================================================= */

async function loadOutbox() {
    if (!accessToken) {
        return;
    }

    try {
        const messages =
            await apiRequest(
                "/outbox"
            );

        renderOutbox(messages);

    } catch (error) {
        console.error(
            "Unable to load outbox:",
            error
        );
    }
}


function renderOutbox(messages) {
    const container =
        $("outboxList");

    if (!container) {
        return;
    }

    if (
        !messages ||
        messages.length === 0
    ) {
        container.innerHTML = `
            <p class="muted">
                No notification messages.
            </p>
        `;

        return;
    }

    container.innerHTML =
        messages
            .map(message => {
                const delivered =
                    message.status ===
                    "delivered";

                return `
                    <div class="outbox-item">

                        <strong>
                            ${escapeHtml(
                                message.subject
                            )}
                        </strong>

                        <p>
                            ${escapeHtml(
                                message.message
                            )}
                        </p>

                        <p>
                            Status:
                            ${escapeHtml(
                                message.status
                            )}
                        </p>

                        ${
                            delivered
                                ? ""
                                : `
                                    <button
                                        type="button"
                                        class="button button-small button-outline"
                                        onclick="deliverOutbox(${message.id})"
                                    >
                                        Mark Delivered
                                    </button>
                                `
                        }

                    </div>
                `;
            })
            .join("");
}


async function deliverOutbox(messageId) {
    try {
        await apiRequest(
            `/outbox/${messageId}/deliver`,
            {
                method: "POST"
            }
        );

        showToast(
            "Notification marked as delivered."
        );

        await loadOutbox();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   CSV Import
   ========================================================= */

async function handleImport(event) {
    event.preventDefault();

    const fileInput =
        $("importFile");

    const file =
        fileInput.files[0];

    if (!file) {
        showToast(
            "Please select a CSV file.",
            "error"
        );

        return;
    }

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );

    try {
        const result =
            await apiRequest(
                "/import/batches",
                {
                    method: "POST",
                    body: formData
                }
            );

        const message =
            `Import completed. ` +
            `Imported: ${result.imported}. ` +
            `Deduped: ${result.deduped}. ` +
            `Rejected: ${result.rejected}.`;

        showClockResult(
            $("importResult"),
            message
        );

        showToast(
            "CSV import completed."
        );

        $("importForm").reset();

        currentPage = 1;

        await loadMedicines();
        await loadHeroStats();

    } catch (error) {
        showToast(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   Hero statistics
   ========================================================= */

async function loadHeroStats() {
    if (!accessToken) {
        return;
    }

    try {
        const summary =
            await apiRequest(
                "/debug/summary"
            );

        $("heroMedicineCount").textContent =
            summary.medicines ?? "0";

        $("heroBatchCount").textContent =
            summary.batches ?? "0";

        $("heroAlertCount").textContent =
            summary.expiry_alerts ?? "0";

    } catch (error) {
        console.error(
            "Unable to load hero statistics:",
            error
        );
    }
}


/* =========================================================
   Date helpers
   ========================================================= */

function formatDate(value) {
    if (!value) {
        return "—";
    }

    const parts =
        String(value).split("-");

    if (parts.length === 3) {
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }

    return String(value);
}


/* =========================================================
   Navigation
   ========================================================= */

function scrollToSection(id) {
    const element =
        document.getElementById(id);

    if (!element) {
        return;
    }

    element.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


/* =========================================================
   Event listeners
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        const registerForm =
            $("registerForm");

        if (registerForm) {
            registerForm.addEventListener(
                "submit",
                handleRegister
            );
        }


        const loginForm =
            $("loginForm");

        if (loginForm) {
            loginForm.addEventListener(
                "submit",
                handleLogin
            );
        }


        const logoutButton =
            $("logoutButton");

        if (logoutButton) {
            logoutButton.addEventListener(
                "click",
                () => logout(true)
            );
        }


        const medicineForm =
            $("medicineForm");

        if (medicineForm) {
            medicineForm.addEventListener(
                "submit",
                handleMedicineCreate
            );
        }


        const batchForm =
            $("batchForm");

        if (batchForm) {
            batchForm.addEventListener(
                "submit",
                handleBatchCreate
            );
        }


        const dispenseForm =
            $("dispenseForm");

        if (dispenseForm) {
            dispenseForm.addEventListener(
                "submit",
                handleDispense
            );
        }


        const importForm =
            $("importForm");

        if (importForm) {
            importForm.addEventListener(
                "submit",
                handleImport
            );
        }


        const searchInput =
            $("searchInput");

        if (searchInput) {
            let searchTimer = null;

            searchInput.addEventListener(
                "input",
                () => {
                    clearTimeout(
                        searchTimer
                    );

                    searchTimer =
                        setTimeout(
                            () => {
                                currentPage = 1;
                                loadMedicines();
                            },
                            350
                        );
                }
            );
        }


        const sortBy =
            $("sortBy");

        if (sortBy) {
            sortBy.addEventListener(
                "change",
                () => {
                    currentPage = 1;
                    loadMedicines();
                }
            );
        }


        const sortOrder =
            $("sortOrder");

        if (sortOrder) {
            sortOrder.addEventListener(
                "change",
                () => {
                    currentPage = 1;
                    loadMedicines();
                }
            );
        }


        const previousButton =
            $("previousPageButton");

        if (previousButton) {
            previousButton.addEventListener(
                "click",
                () => changePage(-1)
            );
        }


        const nextButton =
            $("nextPageButton");

        if (nextButton) {
            nextButton.addEventListener(
                "click",
                () => changePage(1)
            );
        }


        const refreshMedicinesButton =
            $("refreshMedicinesButton");

        if (refreshMedicinesButton) {
            refreshMedicinesButton.addEventListener(
                "click",
                () => loadMedicines()
            );
        }


        const clockButton =
            $("clockButton");

        if (clockButton) {
            clockButton.addEventListener(
                "click",
                runClock
            );
        }


        const refreshAlertsButton =
            $("refreshAlertsButton");

        if (refreshAlertsButton) {
            refreshAlertsButton.addEventListener(
                "click",
                loadAlerts
            );
        }


        const refreshOutboxButton =
            $("refreshOutboxButton");

        if (refreshOutboxButton) {
            refreshOutboxButton.addEventListener(
                "click",
                loadOutbox
            );
        }


        updateAuthUI();
    }
);

