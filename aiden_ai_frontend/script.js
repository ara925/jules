document.addEventListener('DOMContentLoaded', () => {
    // Chat page elements and functions
    const chatMessagesDiv = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    if (chatMessagesDiv && messageInput && sendButton) {
        function addMessageToChat(text, sender) {
            if (text.trim() === '') {
                return;
            }

            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message');
            messageDiv.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
            messageDiv.textContent = text;

            chatMessagesDiv.appendChild(messageDiv);
            chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight; // Scroll to bottom
        }

        function handleSendMessage() {
            const text = messageInput.value;
            addMessageToChat(text, 'user');
            messageInput.value = ''; // Clear input after sending
            // Future: send text to backend and display bot response
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
            console.log("Login attempt:", email, password);
            // Future: Send data to backend /login endpoint
            alert('Login attempt (check console). Backend integration pending.');
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
            console.log("Registration attempt:", email, password);
            // Future: Send data to backend /users/register endpoint
            alert('Registration attempt (check console). Backend integration pending.');
        });
    }
});
