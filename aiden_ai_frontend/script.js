document.addEventListener('DOMContentLoaded', () => {
    // --- Global Variables ---
    let socket;
    let currentUserData = null;
    let interimAuthToken = null;
    let tempTotpSecret = null;
    let currentManagingOrgId = null;
    let auditLogCurrentPage = 1;
    const auditLogPageLimit = 25;

    const OrgRoles = {
        OWNER: "owner", ADMIN: "admin", MEMBER: "member",
        SALES_REP: "sales_rep", SUPPORT_AGENT: "support_agent"
    };
    const SystemRoles = { ADMIN: "admin", USER: "user" };


    // --- Helper Functions ---
    function handleLogout() {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('userOrgRole');
        localStorage.removeItem('userSystemRole');
        localStorage.removeItem('currentEditingContactId');
        localStorage.removeItem('currentManagingOrgId');
        interimAuthToken = null; currentUserData = null; tempTotpSecret = null;
        alert('You have been logged out.'); window.location.href = 'login.html';
    }

    function displayMessage(element, message, type = 'info', autohideAfterMs = 0) {
        if (element) {
            element.textContent = message;
            element.className = 'message ' + type;
            element.style.display = message ? 'block' : 'none';
            if (autohideAfterMs > 0) setTimeout(() => { if(element) element.style.display = 'none'; }, autohideAfterMs);
        }
    }

    function populateRoleSelect(selectElementId, currentRole = null, excludeOwner = false) {
        const selectElement = document.getElementById(selectElementId);
        if (!selectElement) return;
        selectElement.innerHTML = '';
        for (const roleKey in OrgRoles) {
            const roleValue = OrgRoles[roleKey];
            if (excludeOwner && roleValue === OrgRoles.OWNER) continue;
            const option = document.createElement('option');
            option.value = roleValue;
            option.textContent = roleValue.charAt(0).toUpperCase() + roleValue.slice(1).replace(/_/g, ' ');
            if (currentRole === roleValue) option.selected = true;
            selectElement.appendChild(option);
        }
    }

    async function makeApiRequest(url, method = 'GET', body = null) {
        const token = localStorage.getItem('accessToken');
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const config = { method, headers };
        if (body) config.body = JSON.stringify(body);
        const response = await fetch(url, config);
        if (response.status === 401 && !url.includes('/auth/login')) { handleLogout(); throw new Error('Unauthorized or session expired. Please login again.');}
        let responseData = null;
        if (response.status !== 204) { responseData = await response.json().catch(() => ({ detail: `Request failed, status: ${response.status}` }));}
        if (!response.ok) { throw new Error(responseData?.detail || `HTTP error! status: ${response.status}`);}
        return responseData;
    }

    // --- Global Nav Link Management ---
    function updateUserNavLinks() {
        const accessToken = localStorage.getItem('accessToken');
        const userOrgRole = localStorage.getItem('userOrgRole');
        const userSystemRole = localStorage.getItem('userSystemRole');

        const navLinksConfig = [
            { idPrefix: 'nav-org-management', roles: [OrgRoles.OWNER, OrgRoles.ADMIN], checkRole: userOrgRole },
            { idPrefix: 'nav-admin-audit-logs', roles: [SystemRoles.ADMIN], checkRole: userSystemRole }
        ];

        navLinksConfig.forEach(config => {
            const links = [
                document.getElementById(config.idPrefix), // For index.html
                document.getElementById(config.idPrefix + '-profile'),
                document.getElementById(config.idPrefix + '-contacts'),
                document.getElementById(config.idPrefix + '-inbox'),
                document.getElementById(config.idPrefix + '-org-mgm'), // For org_management page itself
                document.getElementById(config.idPrefix + '-audit') // For admin_audit_logs page itself
            ];
            links.forEach(link => {
                if (link) {
                    if (accessToken && config.roles.includes(config.checkRole)) {
                        link.style.display = 'inline';
                    } else {
                        link.style.display = 'none';
                    }
                }
            });
        });
    }

    // --- Page Load Initializers & Event Listeners ---
    // Index Page (Chat)
    if (document.getElementById('join-conversation-button')) { /* ... existing chat page logic ... */ }

    // Login Page
    const loginFormEl = document.getElementById('login-form');
    if (loginFormEl) { /* ... existing login logic ... */ }

    // Profile Page
    if (window.location.pathname.endsWith('profile.html')) { /* ... existing profile page logic ... */ }

    // Registration page
    const registerFormEl = document.getElementById('register-form');
    if (registerFormEl) { /* ... existing registration logic ... */  }

    // Contacts Page (contacts.html)
    if (document.getElementById('contacts-table')) { /* ... existing contacts logic ... */ }

    // Contact Form Page (contact_form.html)
    if (document.getElementById('contact-form')) { /* ... existing contact form logic ... */ }

    // Inbox Page (inbox.html)
    if (document.getElementById('inbox-emails-table')) { /* ... existing inbox logic ... */ }

    // Organization Management Page (organization_management.html)
    if (document.getElementById('org-management-content')) { /* ... existing org management logic ... */ }

    // --- Admin Audit Logs Page Logic (admin_audit_logs.html) ---
    const adminAuditContent = document.getElementById('admin-audit-content');
    if (adminAuditContent) {
        const logsTableBody = document.querySelector('#audit-logs-table tbody');
        const adminAuditMessages = document.getElementById('admin-audit-messages');
        const filterUserIdInput = document.getElementById('filter-user-id');
        const filterActionInput = document.getElementById('filter-action');
        const filterTargetTypeInput = document.getElementById('filter-target-type');
        const applyFiltersBtn = document.getElementById('apply-filters-btn');
        const resetFiltersBtn = document.getElementById('reset-filters-btn');
        const prevPageBtn = document.getElementById('prev-page-btn');
        const nextPageBtn = document.getElementById('next-page-btn');
        const currentPageDisplay = document.getElementById('current-page-display');
        const logoutBtnAdminAudit = document.getElementById('logout-button-admin-audit');

        if(logoutBtnAdminAudit) logoutBtnAdminAudit.addEventListener('click', handleLogout);

        async function fetchAuditLogs(page = 1) {
            displayMessage(adminAuditMessages, 'Loading audit logs...', 'info', false);
            auditLogCurrentPage = page;
            const params = new URLSearchParams({
                skip: (page - 1) * auditLogPageLimit,
                limit: auditLogPageLimit,
            });
            if (filterUserIdInput.value) params.append('userId', filterUserIdInput.value);
            if (filterActionInput.value) params.append('action', filterActionInput.value);
            if (filterTargetTypeInput.value) params.append('targetType', filterTargetTypeInput.value);

            try {
                const logs = await makeApiRequest(`http://localhost:8000/admin/audit-logs?${params.toString()}`, 'GET');
                renderAuditLogs(logs || []); // Ensure logs is an array
                displayMessage(adminAuditMessages, '', 'info', false); // Clear loading/error
                if (logs.length === 0 && page === 1 && !filterUserIdInput.value && !filterActionInput.value && !filterTargetTypeInput.value) {
                    displayMessage(adminAuditMessages, 'No audit logs found.', 'info');
                }
                if(currentPageDisplay) currentPageDisplay.textContent = `Page: ${auditLogCurrentPage}`;
                if(prevPageBtn) prevPageBtn.disabled = auditLogCurrentPage === 1;
                if(nextPageBtn) nextPageBtn.disabled = logs.length < auditLogPageLimit;
            } catch (error) {
                console.error('Error fetching audit logs:', error);
                displayMessage(adminAuditMessages, error.message, 'error');
                if(logsTableBody) logsTableBody.innerHTML = '<tr><td colspan="6">Could not load audit logs.</td></tr>';
            }
        }

        function renderAuditLogs(logs) {
            if (!logsTableBody) return;
            logsTableBody.innerHTML = '';
            if (logs.length === 0) {
                logsTableBody.innerHTML = '<tr><td colspan="6">No logs match current filters.</td></tr>'; return;
            }
            logs.forEach(log => {
                const row = logsTableBody.insertRow();
                row.insertCell().textContent = new Date(log.timestamp).toLocaleString();
                row.insertCell().textContent = `${log.actor_email || 'N/A'} (${log.user_id || 'System'})`;
                row.insertCell().textContent = log.action;
                row.insertCell().textContent = log.target_type || 'N/A';
                row.insertCell().textContent = log.target_id || 'N/A';
                row.insertCell().textContent = log.details ? JSON.stringify(log.details, null, 2) : 'N/A';
            });
        }

        async function initAdminAuditLogsPage() {
            if (!localStorage.getItem('accessToken')) { window.location.href = 'login.html'; return; }
            const userSystemRole = localStorage.getItem('userSystemRole');
            if (userSystemRole !== SystemRoles.ADMIN) {
                displayMessage(adminAuditMessages, "Access Denied. You must be a System Administrator.", "error");
                if(adminAuditContent) adminAuditContent.style.display = 'none';
                return;
            }
            if(adminAuditContent) adminAuditContent.style.display = 'block';
            fetchAuditLogs(1);
        }

        if(applyFiltersBtn) applyFiltersBtn.addEventListener('click', () => fetchAuditLogs(1));
        if(resetFiltersBtn) {
            resetFiltersBtn.addEventListener('click', () => {
                if(filterUserIdInput) filterUserIdInput.value = '';
                if(filterActionInput) filterActionInput.value = '';
                if(filterTargetTypeInput) filterTargetTypeInput.value = '';
                fetchAuditLogs(1);
            });
        }
        if(prevPageBtn) prevPageBtn.addEventListener('click', () => { if (auditLogCurrentPage > 1) fetchAuditLogs(auditLogCurrentPage - 1); });
        if(nextPageBtn) nextPageBtn.addEventListener('click', () => fetchAuditLogs(auditLogCurrentPage + 1));

        initAdminAuditLogsPage();
    }

    // Call on all pages to set up nav links correctly based on stored role/login state
    updateUserNavLinks();
});
