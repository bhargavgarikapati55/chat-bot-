document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const chatHistory = document.getElementById("chat-history");
    const welcomeScreen = document.getElementById("welcome-screen");
    const newChatBtn = document.getElementById("new-chat-btn");

    // Load session and history from localStorage
    let sessionId = localStorage.getItem('chat_session_id') || "session_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('chat_session_id', sessionId);
    
    let chatState = JSON.parse(localStorage.getItem('chat_history') || '[]');

    if (newChatBtn) {
        newChatBtn.addEventListener("click", (e) => {
            e.preventDefault();
            // Reset Session for fresh context
            sessionId = "session_" + Math.random().toString(36).substring(2, 10);
            localStorage.setItem('chat_session_id', sessionId);
            chatState = [];
            localStorage.removeItem('chat_history');
            
            // Clear UI
            chatHistory.innerHTML = "";
            chatHistory.style.display = "none";
            welcomeScreen.style.display = "flex";
            
            // Reset Inputs
            input.value = "";
            input.disabled = false;
            if (sendBtn) {
                sendBtn.disabled = false;
            }
        });
    }

    const appendMessage = (role, text, save = true) => {
        const msgDiv = document.createElement("div");
        msgDiv.style.display = "flex";
        msgDiv.style.gap = "15px";
        msgDiv.style.color = "#ececec";
        msgDiv.style.fontSize = "15px";
        msgDiv.style.lineHeight = "1.6";
        
        const avatar = document.createElement("div");
        avatar.style.width = "30px";
        avatar.style.height = "30px";
        avatar.style.borderRadius = "50%";
        avatar.style.display = "flex";
        avatar.style.alignItems = "center";
        avatar.style.justifyContent = "center";
        avatar.style.flexShrink = "0";
        
        if (role === "user") {
            avatar.style.backgroundColor = "#5436DA";
            avatar.innerHTML = `<i class="fa-solid fa-user" style="font-size: 14px;"></i>`;
        } else {
            avatar.style.backgroundColor = "#10A37F";
            avatar.innerHTML = `<i class="fa-solid fa-robot" style="font-size: 14px; color: white;"></i>`;
        }

        const contentDiv = document.createElement("div");
        contentDiv.style.flexGrow = "1";
        // Convert basic newlines to <br> to respect markdown/line breaks loosely
        contentDiv.innerHTML = text.replace(/\n/g, "<br>");
        
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(contentDiv);
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        if (save) {
            chatState.push({ role, text });
            localStorage.setItem('chat_history', JSON.stringify(chatState));
        }
    };

    // Restore chat history from localStorage on load
    if (chatState.length > 0) {
        welcomeScreen.style.display = "none";
        chatHistory.style.display = "flex";
        chatState.forEach(msg => {
            appendMessage(msg.role, msg.text, false); // false = don't re-save what we just loaded
        });
    }

    const handleSend = async () => {
        const message = input.value.trim();
        if (!message) return;

        // Hide welcome screen and show history container if first message
        if (welcomeScreen.style.display !== "none") {
            welcomeScreen.style.display = "none";
            chatHistory.style.display = "flex";
        }

        appendMessage("user", message);
        input.value = "";
        
        // Disable input while fetching
        input.disabled = true;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

        let currentMessageDiv = null;
        let currentContentDiv = null;

        const startStreamingMessage = () => {
            currentMessageDiv = document.createElement("div");
            currentMessageDiv.style.display = "flex";
            currentMessageDiv.style.gap = "15px";
            currentMessageDiv.style.color = "#ececec";
            currentMessageDiv.style.fontSize = "15px";
            currentMessageDiv.style.lineHeight = "1.6";
            
            const avatar = document.createElement("div");
            avatar.style.width = "30px";
            avatar.style.height = "30px";
            avatar.style.borderRadius = "50%";
            avatar.style.display = "flex";
            avatar.style.alignItems = "center";
            avatar.style.justifyContent = "center";
            avatar.style.flexShrink = "0";
            avatar.style.backgroundColor = "#10A37F";
            avatar.innerHTML = `<i class="fa-solid fa-robot" style="font-size: 14px; color: white;"></i>`;

            currentContentDiv = document.createElement("div");
            currentContentDiv.style.flexGrow = "1";
            // Show a thinking animation while waiting for the actual response
            currentContentDiv.innerHTML = '<span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span>';
            
            currentMessageDiv.appendChild(avatar);
            currentMessageDiv.appendChild(currentContentDiv);
            chatHistory.appendChild(currentMessageDiv);
        };

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: sessionId, message: message })
            });

            if (!response.ok) {
                appendMessage("model", `*Error:* Server returned ${response.status}`);
                return;
            }

            startStreamingMessage();

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let aiText = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunkString = decoder.decode(value, { stream: true });
                const lines = chunkString.split("\n");
                
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const jsonStr = line.replace("data: ", "");
                        try {
                            const parsed = JSON.parse(jsonStr);
                            if (parsed.error) {
                                aiText += `\n\n⚠️ *[Error: ${parsed.error}]*`;
                            } else if (parsed.chunk) {
                                // Filter out system/infrastructure messages from the UI
                                const chunk = parsed.chunk;
                                const isSystemMsg = chunk.includes("[HEARTBEAT]") ||
                                    chunk.includes("*[System:") ||
                                    chunk.includes("*[Agent: Using");
                                
                                if (!isSystemMsg) {
                                    aiText += chunk;
                                }
                            }
                            // Only update DOM if we have visible content
                            if (aiText.trim()) {
                                currentContentDiv.innerHTML = aiText.replace(/\n/g, "<br>");
                                chatHistory.scrollTop = chatHistory.scrollHeight;
                            }
                        } catch (e) {
                            // This is common for partial chunks in SSE, so we just wait for more data
                            console.debug("Partial chunk received, waiting for more...");
                        }
                    }
                }
            }
            
            // Save model response to local storage after stream finishes
            if (aiText.trim()) {
                chatState.push({ role: "model", text: aiText });
                localStorage.setItem('chat_history', JSON.stringify(chatState));
            }
        } catch (error) {
            console.error("Fetch error:", error);
            appendMessage("model", "*Error:* Failed to connect to backend server.");
        } finally {
            input.disabled = false;
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fa-solid fa-paper-plane" style="margin-right: 5px;"></i> Send';
            input.focus();
        }
    };

    sendBtn.addEventListener("click", handleSend);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            handleSend();
        }
    });

    // Interactive mock functionality for sidebar/topbar buttons
    const authModal = document.getElementById("auth-modal");
    const closeModal = document.querySelector(".close-modal");
    const authForm = document.getElementById("auth-form");
    const modalTitle = document.getElementById("modal-title");

    // Close modal handlers
    if (closeModal) {
        closeModal.addEventListener("click", () => authModal.style.display = "none");
    }
    if (authModal) {
        authModal.addEventListener("click", (e) => { 
            if(e.target === authModal) authModal.style.display = "none"; 
        });
    }
    if (authForm) {
        authForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const btn = authForm.querySelector("button");
            const originalText = btn.innerText;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
            setTimeout(() => {
                authModal.style.display = "none";
                btn.innerText = originalText;
                alert("Success! However, since this is a UI Clone, actual persistence is disabled.");
            }, 1000);
        });
    }

    const triggerPrompt = (promptText) => {
        // If chat is ongoing or fresh, inject text and send
        input.value = promptText;
        handleSend();
    };

    const dummyLinks = document.querySelectorAll('.nav-item:not(#new-chat-btn), .btn-sidebar-login, .btn-top-login, .btn-signup');
    dummyLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const featureName = e.currentTarget.innerText.trim();
            const lowerName = featureName.toLowerCase();

            if (lowerName.includes("log in")) {
                modalTitle.innerText = "Welcome back";
                authModal.style.display = "flex";
            } else if (lowerName.includes("sign up")) {
                modalTitle.innerText = "Create your account";
                authModal.style.display = "flex";
            } else if (lowerName.includes("search chats")) {
                input.focus();
                input.placeholder = "Type here to search past conversations...";
                setTimeout(() => input.placeholder = "Ask anything", 5000);
            } else if (lowerName.includes("images")) {
                triggerPrompt("I would like to generate an image. Can you describe a prompt for a beautiful futuristic city?");
            } else if (lowerName.includes("apps")) {
                triggerPrompt("Help me write the code for a simple weather web application.");
            } else if (lowerName.includes("deep research")) {
                triggerPrompt("Perform a deep research analysis on the current progress of Quantum Computing in 2026.");
            } else if (lowerName.includes("health")) {
                triggerPrompt("What are the top 5 scientifically proven habits for maintaining good physical health?");
            } else {
                alert(`${featureName} is currently under development!`);
            }
        });
    });

    console.log("ChatGPT UI Clone configured with Gemini Backend!");
});
