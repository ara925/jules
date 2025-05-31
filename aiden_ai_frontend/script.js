document.addEventListener('DOMContentLoaded', () => {
    // Global WebSocket variable
    let socket;

    // Chat page elements
    const joinConversationButton = document.getElementById('join-conversation-button');
    const conversationIdInput = document.getElementById('conversation-id-input');
    const chatContainer = document.getElementById('chat-container');
    const currentConversationIdDisplay = document.getElementById('current-conversation-id');
    const chatMessagesDiv = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    // Function to display messages in the chat (adapted)
    function displayChatMessage(messageData) {
        if (!chatMessagesDiv) return;

        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        // Basic differentiation, can be improved if current user ID is available
        // For now, just showing sender email.
        // const currentUserId = localStorage.getItem('userId'); // Assuming userId is stored on login
        // if (messageData.sender_id && currentUserId && messageData.sender_id.toString() === currentUserId) {
        // messageDiv.classList.add('user-message');
        // } else {
        // messageDiv.classList.add('bot-message'); // Generic class for others
        // }

        // Simple display with email and message
        const senderPrefix = messageData.sender_email ? `${messageData.sender_email}: ` : 'System: ';
        messageDiv.textContent = `${senderPrefix}${messageData.message}`;

        // Add a timestamp if available
        if (messageData.timestamp) {
            const timeSpan = document.createElement('span');
            timeSpan.style.fontSize = '0.7em';
            timeSpan.style.marginLeft = '10px';
            timeSpan.style.color = '#888';
            timeSpan.textContent = new Date(messageData.timestamp).toLocaleTimeString();
            messageDiv.appendChild(timeSpan);
        }

        chatMessagesDiv.appendChild(messageDiv);
        chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
    }

    if (joinConversationButton && conversationIdInput && chatContainer && messageInput && sendButton && chatMessagesDiv) {
        // Initially hide chat container elements that require a joined conversation
        // messageInput.disabled = true; // Already hidden by chat-container display:none
        // sendButton.disabled = true;

        joinConversationButton.addEventListener('click', () => {
            const conversationId = conversationIdInput.value.trim();
            const accessToken = localStorage.getItem('accessToken');

            if (!conversationId) {
                alert('Please enter a Conversation ID.');
                return;
            }
            if (!accessToken) {
                alert('You must be logged in to join a conversation.');
                window.location.href = 'login.html';
                return;
            }

            if (socket && socket.readyState !== WebSocket.CLOSED) {
                socket.close(); // Close existing connection before opening a new one
            }

            chatMessagesDiv.innerHTML = ''; // Clear previous messages
            const wsUrl = `ws://localhost:8000/ws/chat/${conversationId}?token=${accessToken}`;
            socket = new WebSocket(wsUrl);

            socket.onopen = (event) => {
                console.log("WebSocket connection opened.");
                displayChatMessage({ message: `Connected to conversation: ${conversationId}` });
                chatContainer.style.display = 'flex';
                currentConversationIdDisplay.textContent = `Conversation: ${conversationId}`;

                // Fetch message history
                fetch(`http://localhost:8000/chat/${conversationId}/messages?limit=50`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${accessToken}`, // accessToken is in scope here
                    },
                })
                .then(response => {
                    if (!response.ok) {
                        // Handle HTTP errors while fetching history, e.g., 401, 403
                        return response.json().then(err => {
                            throw new Error(err.detail || 'Failed to fetch message history');
                        });
                    }
                    return response.json();
                })
                .then(historyMessages => {
                    // Prepend history messages. displayChatMessage appends, so we might need to
                    // insert them in reverse or handle this carefully if order matters strictly with new ones.
                    // For simplicity, we'll just display them. If displayChatMessage appends, they'll appear after "Connected..."
                    // but before any new live messages if they arrive very quickly.
                    // To ensure they are at the top and in order, we can add them one by one.
                    historyMessages.forEach(msgData => {
                        displayChatMessage(msgData); // displayChatMessage should handle the object structure
                    });
                    // Scroll to bottom after loading history
                    if (chatMessagesDiv) chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
                })
                .catch(error => {
                    console.error("Error fetching message history:", error);
                    displayChatMessage({ message: `Error loading history: ${error.message}` });
                });
            };

            socket.onmessage = (event) => {
                try {
                    const messageData = JSON.parse(event.data);
                    console.log("Message from server:", messageData);
                    displayChatMessage(messageData);
                } catch (e) {
                    console.error("Error parsing message data:", e);
                    displayChatMessage({ message: "Received malformed message from server."});
                }
            };

            socket.onclose = (event) => {
                console.log("WebSocket connection closed.", event);
                let reason = "Connection closed.";
                if (event.reason) {
                    reason += ` Reason: ${event.reason} (Code: ${event.code})`;
                }
                displayChatMessage({ message: reason });
                // messageInput.disabled = true;
                // sendButton.disabled = true;
                // chatContainer.style.display = 'none'; // Optionally hide chat on disconnect
            };

            socket.onerror = (error) => {
                console.error("WebSocket error:", error);
                displayChatMessage({ message: "WebSocket error occurred. See console for details."});
                // messageInput.disabled = true;
                // sendButton.disabled = true;
            };
        });

        function handleSendMessage() {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const text = messageInput.value;
                if (text.trim() !== '') {
                    socket.send(text);
                    messageInput.value = ''; // Clear input after sending
                }
            } else {
                alert('Not connected to a conversation. Please join a conversation first.');
            }
        }

        sendButton.addEventListener('click', handleSendMessage);
        messageInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                handleSendMessage();
            }
        });
    }

    // Login page elements and functions
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        const loginEmailInput = document.getElementById('login-email');
        const loginPasswordInput = document.getElementById('login-password');

        loginForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const email = loginEmailInput.value;
            const password = loginPasswordInput.value;
            console.log("Login attempt:", email); // Password removed for security in console

            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);

            fetch('http://localhost:8000/users/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData,
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'Login failed') });
                }
                return response.json();
            })
            .then(data => {
                console.log("Login successful:", data);
                if (data.access_token) {
                    localStorage.setItem('accessToken', data.access_token);
                    // Redirect to chat page or update UI
                    window.location.href = 'index.html';
                } else {
                    alert('Login successful, but no token received.');
                }
            })
            .catch(error => {
                console.error("Login error:", error);
                alert(`Login failed: ${error.message}`);
            });
        });
    }

    // Profile page elements and functions
    const profileInfoDiv = document.getElementById('profile-info');
    const logoutButton = document.getElementById('logout-button');

    if (profileInfoDiv && logoutButton) { // Check if we are on profile.html
        const accessToken = localStorage.getItem('accessToken');

        if (!accessToken) {
            window.location.href = 'login.html'; // Redirect if not logged in
        } else {
            fetch('http://localhost:8000/users/me', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            })
            .then(response => {
                if (response.status === 401) { // Unauthorized or token expired
                    localStorage.removeItem('accessToken');
                    alert('Session expired. Please login again.');
                    window.location.href = 'login.html';
                    return Promise.reject('Unauthorized'); // Stop further processing
                }
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'Failed to fetch profile') });
                }
                return response.json();
            })
            .then(user => {
                profileInfoDiv.innerHTML = `
                    <p><strong>ID:</strong> ${user.id}</p>
                    <p><strong>Email:</strong> ${user.email}</p>
                    <p><strong>Role:</strong> ${user.role}</p>
                    <p><strong>Active:</strong> ${user.is_active ? 'Yes' : 'No'}</p>
                    <p><strong>Email Verified:</strong> ${user.is_email_verified ? 'Yes' : 'No'}</p>
                `;
                console.log("User role:", user.role); // As requested for conceptual check
            })
            .catch(error => {
                if (error !== 'Unauthorized') { // Avoid double alert for 401
                    console.error("Profile fetch error:", error);
                    profileInfoDiv.innerHTML = `<p style="color:red;">Could not load profile: ${error.message}</p>`;
                }
            });
        }

        logoutButton.addEventListener('click', () => {
            localStorage.removeItem('accessToken');
            alert('You have been logged out.');
            window.location.href = 'login.html';
        });
    }

    // Registration page elements and functions
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        const registerEmailInput = document.getElementById('register-email');
        const registerPasswordInput = document.getElementById('register-password');

        registerForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const email = registerEmailInput.value;
            const password = registerPasswordInput.value;
            console.log("Registration attempt:", email); // Password removed for security

            fetch('http://localhost:8000/users/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email: email, password: password }),
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'Registration failed') });
                }
                return response.json();
            })
            .then(data => {
                console.log("Registration successful:", data);
                alert(data.message || 'Registration successful! Please check your email.');
                // Optionally redirect to login page or show a more persistent message
                // window.location.href = 'login.html';
            })
            .catch(error => {
                console.error("Registration error:", error);
                alert(`Registration failed: ${error.message}`);
            });
        });
    }

    // Contact Management Logic
    const contactsTableBody = document.getElementById('contacts-table-body');
    const addContactBtn = document.getElementById('add-contact-btn');
    const contactsMessagesDiv = document.getElementById('contacts-messages');
    const noContactsMessageDiv = document.getElementById('no-contacts-message');

    const contactForm = document.getElementById('contact-form');
    const contactFormTitle = document.getElementById('contact-form-title');
    const contactIdInput = document.getElementById('contact-id');
    const contactFirstNameInput = document.getElementById('contact-first-name');
    const contactLastNameInput = document.getElementById('contact-last-name');
    const contactEmailInput = document.getElementById('contact-email');
    const contactPhoneInput = document.getElementById('contact-phone');
    const contactCompanyInput = document.getElementById('contact-company');
    const contactNotesInput = document.getElementById('contact-notes');
    const saveContactBtn = document.getElementById('save-contact-btn');
    const contactFormMessagesDiv = document.getElementById('contact-form-messages');

    // Logout buttons on new pages
    const logoutButtonContacts = document.getElementById('logout-button-contacts');
    const logoutButtonContactForm = document.getElementById('logout-button-contact-form');

    function handleLogout() {
        localStorage.removeItem('accessToken');
        alert('You have been logged out.');
        window.location.href = 'login.html';
    }

    if (logoutButtonContacts) logoutButtonContacts.addEventListener('click', handleLogout);
    if (logoutButtonContactForm) logoutButtonContactForm.addEventListener('click', handleLogout);


    function displayContactsMessage(message, type = 'info') {
        if (contactsMessagesDiv) {
            contactsMessagesDiv.textContent = message;
            contactsMessagesDiv.className = 'message ' + type;
            contactsMessagesDiv.style.display = 'block';
            setTimeout(() => { contactsMessagesDiv.style.display = 'none'; }, 3000);
        }
    }

    function displayContactFormMessage(message, type = 'info') {
        if (contactFormMessagesDiv) {
            contactFormMessagesDiv.textContent = message;
            contactFormMessagesDiv.className = 'message ' + type;
            contactFormMessagesDiv.style.display = 'block';
        }
    }

    async function fetchContacts() {
        const accessToken = localStorage.getItem('accessToken');
        if (!accessToken) {
            window.location.href = 'login.html';
            return;
        }

        try {
            const response = await fetch('http://localhost:8000/contacts/', {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            });
            if (!response.ok) {
                if (response.status === 401) {
                    localStorage.removeItem('accessToken');
                    window.location.href = 'login.html';
                }
                throw new Error(`Error fetching contacts: ${response.statusText}`);
            }
            const contacts = await response.json();
            renderContacts(contacts);
        } catch (error) {
            console.error("Fetch contacts error:", error);
            displayContactsMessage(error.message || "Could not load contacts.", "error");
        }
    }

    function renderContacts(contacts) {
        if (!contactsTableBody) return;
        contactsTableBody.innerHTML = ''; // Clear existing rows
        if (contacts.length === 0) {
            if (noContactsMessageDiv) noContactsMessageDiv.style.display = 'block';
            if (document.getElementById('contacts-table')) document.getElementById('contacts-table').style.display = 'none';
        } else {
            if (noContactsMessageDiv) noContactsMessageDiv.style.display = 'none';
            if (document.getElementById('contacts-table')) document.getElementById('contacts-table').style.display = 'table';
            contacts.forEach(contact => {
                const row = contactsTableBody.insertRow();
                row.innerHTML = `
                    <td>${contact.first_name} ${contact.last_name || ''}</td>
                    <td>${contact.email}</td>
                    <td>${contact.phone_number || '-'}</td>
                    <td>${contact.company || '-'}</td>
                    <td>
                        <button class="edit-contact-btn action-button-secondary" data-id="${contact.id}">Edit</button>
                        <button class="delete-contact-btn action-button-danger" data-id="${contact.id}">Delete</button>
                    </td>
                `;
            });
            addEventListenersToContactButtons();
        }
    }

    function addEventListenersToContactButtons() {
        document.querySelectorAll('.edit-contact-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const contactId = e.target.dataset.id;
                // Store ID and navigate. Could also pass via query param.
                localStorage.setItem('currentEditingContactId', contactId);
                window.location.href = 'contact_form.html';
            });
        });

        document.querySelectorAll('.delete-contact-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const contactId = e.target.dataset.id;
                if (window.confirm('Are you sure you want to delete this contact?')) {
                    const accessToken = localStorage.getItem('accessToken');
                    try {
                        const response = await fetch(`http://localhost:8000/contacts/${contactId}`, {
                            method: 'DELETE',
                            headers: { 'Authorization': `Bearer ${accessToken}` }
                        });
                        if (!response.ok) {
                             const errData = await response.json();
                            throw new Error(errData.detail || `Error deleting contact: ${response.statusText}`);
                        }
                        // No content on 204, so can't call response.json()
                        displayContactsMessage('Contact deleted successfully.', 'success');
                        fetchContacts(); // Refresh list
                    } catch (error) {
                        console.error("Delete contact error:", error);
                        displayContactsMessage(error.message || "Could not delete contact.", "error");
                    }
                }
            });
        });
    }


    // On contacts.html
    if (window.location.pathname.endsWith('contacts.html')) {
        if (!localStorage.getItem('accessToken')) {
             window.location.href = 'login.html';
        } else {
            fetchContacts();
            if (addContactBtn) {
                addContactBtn.addEventListener('click', () => {
                    localStorage.removeItem('currentEditingContactId'); // Clear any previous edit state
                    window.location.href = 'contact_form.html';
                });
            }
             // Check for messages passed from other pages (e.g., after save)
            const successMessage = localStorage.getItem('contactFormSuccessMessage');
            if (successMessage) {
                displayContactsMessage(successMessage, 'success');
                localStorage.removeItem('contactFormSuccessMessage');
            }
        }
    }

    // On contact_form.html
    if (window.location.pathname.endsWith('contact_form.html')) {
        if (!localStorage.getItem('accessToken')) {
             window.location.href = 'login.html';
        } else {
            const contactIdToEdit = localStorage.getItem('currentEditingContactId');
            if (contactIdToEdit) {
                contactFormTitle.textContent = 'Edit Contact';
                saveContactBtn.textContent = 'Update Contact';
                contactIdInput.value = contactIdToEdit; // Store it in hidden field

                // Fetch contact details to populate form
                (async () => {
                    const accessToken = localStorage.getItem('accessToken');
                    try {
                        const response = await fetch(`http://localhost:8000/contacts/${contactIdToEdit}`, {
                            headers: { 'Authorization': `Bearer ${accessToken}` }
                        });
                        if (!response.ok) {
                            if (response.status === 401) window.location.href = 'login.html';
                            const errData = await response.json();
                            throw new Error(errData.detail || 'Failed to fetch contact details.');
                        }
                        const contact = await response.json();
                        contactFirstNameInput.value = contact.first_name;
                        contactLastNameInput.value = contact.last_name || '';
                        contactEmailInput.value = contact.email;
                        contactPhoneInput.value = contact.phone_number || '';
                        contactCompanyInput.value = contact.company || '';
                        contactNotesInput.value = contact.notes || '';
                    } catch (error) {
                        console.error("Error populating form for edit:", error);
                        displayContactFormMessage(error.message, 'error');
                    }
                })();
            } else {
                contactFormTitle.textContent = 'Add New Contact';
                saveContactBtn.textContent = 'Save Contact';
                contactIdInput.value = ''; // Ensure hidden ID is empty
            }

            contactForm.addEventListener('submit', async (event) => {
                event.preventDefault();
                const contactData = {
                    first_name: contactFirstNameInput.value,
                    last_name: contactLastNameInput.value || null, // Send null if empty
                    email: contactEmailInput.value,
                    phone_number: contactPhoneInput.value || null,
                    company: contactCompanyInput.value || null,
                    notes: contactNotesInput.value || null,
                };

                const accessToken = localStorage.getItem('accessToken');
                const editingId = contactIdInput.value;
                const url = editingId ? `http://localhost:8000/contacts/${editingId}` : 'http://localhost:8000/contacts/';
                const method = editingId ? 'PUT' : 'POST';

                // For PUT, only send fields that are not null or empty if using ContactUpdate schema correctly
                // For simplicity here, sending all. Backend ContactUpdate schema handles optional fields.
                // A more refined approach would filter out unchanged or empty optional fields for PUT.
                let payload = contactData;
                if (method === 'PUT') {
                    // Filter out null values for PUT to work with Pydantic's exclude_unset=True effectively
                    // or ensure backend handles nulls as "do not update this field" if schema is BaseModel
                    payload = Object.fromEntries(Object.entries(contactData).filter(([_, v]) => v !== null && v !== ''));
                }


                try {
                    const response = await fetch(url, {
                        method: method,
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${accessToken}`
                        },
                        body: JSON.stringify(payload)
                    });
                    if (!response.ok) {
                        const errData = await response.json();
                        throw new Error(errData.detail || `Failed to ${editingId ? 'update' : 'create'} contact.`);
                    }
                    const result = await response.json();
                    localStorage.setItem('contactFormSuccessMessage', `Contact ${editingId ? 'updated' : 'saved'} successfully!`);
                    window.location.href = 'contacts.html';
                } catch (error) {
                    console.error("Save/Update contact error:", error);
                    displayContactFormMessage(error.message, 'error');
                }
            });
        }
    }

    // Inbox Page Logic
    const inboxEmailsTable = document.getElementById('inbox-emails-table');
    const logoutButtonInbox = document.getElementById('logout-button-inbox');

    if (logoutButtonInbox) { // Assuming if this button exists, we are on or need its shared logout
        logoutButtonInbox.addEventListener('click', handleLogout);
    }

    async function fetchIngestedEmails(token) {
        const emailsTableBody = document.querySelector('#inbox-emails-table tbody');
        const inboxMessagesDiv = document.getElementById('inbox-messages');

        if (!emailsTableBody || !inboxMessagesDiv) return; // Not on inbox page

        emailsTableBody.innerHTML = ''; // Clear existing rows
        inboxMessagesDiv.textContent = 'Loading emails...';
        inboxMessagesDiv.style.display = 'block';
        inboxMessagesDiv.className = 'message info';


        try {
            const response = await fetch('http://localhost:8000/inbox/emails?limit=100', { // Fetch up to 100 emails
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.status === 401) {
                localStorage.removeItem('accessToken');
                window.location.href = 'login.html';
                return;
            }
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch emails. Status: ' + response.status }));
                throw new Error(errorData.detail || 'Failed to fetch emails.');
            }

            const emails = await response.json();
            if (emails.length === 0) {
                inboxMessagesDiv.textContent = 'No emails ingested yet. If you just triggered ingestion, try refreshing. (Note: IMAP credentials must be configured on the backend for ingestion to work.)';
                inboxMessagesDiv.className = 'message info';
            } else {
                renderIngestedEmails(emails);
                inboxMessagesDiv.style.display = 'none'; // Hide loading message
            }
        } catch (error) {
            console.error('Error fetching ingested emails:', error);
            inboxMessagesDiv.textContent = `Error: ${error.message}`;
            inboxMessagesDiv.className = 'message error';
        }
    }

    function renderIngestedEmails(emails) {
        const emailsTableBody = document.querySelector('#inbox-emails-table tbody');
        if (!emailsTableBody) return;

        emails.forEach(email => {
            const row = emailsTableBody.insertRow();
            row.insertCell().textContent = email.subject || '(No Subject)';
            row.insertCell().textContent = email.sender_address;
            row.insertCell().textContent = new Date(email.received_at).toLocaleString();
            row.insertCell().textContent = email.status;
        });
    }

    if (inboxEmailsTable) { // Check if we are on inbox.html
        const token = localStorage.getItem('accessToken');
        if (!token) {
            window.location.href = 'login.html';
        } else {
            fetchIngestedEmails(token);
        }
    }
});
