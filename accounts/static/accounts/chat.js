(() => {
  const chat = document.querySelector(".chat-card");
  if (!chat) return;

  const transcript = chat.querySelector(".chat-transcript");
  const input = chat.querySelector("#chat-question");
  const form = chat.querySelector("[data-chat-form]");
  const sendButton = chat.querySelector("[data-chat-send]");
  const feedback = chat.querySelector("[data-chat-feedback]");
  const conversationInput = chat.querySelector("[data-chat-conversation]");
  const statusLabel = chat.querySelector("[data-chat-status-label]");
  const mentorPicker = chat.querySelector("[data-mentor-picker]");
  const mentorForm = chat.querySelector("[data-mentor-form]");
  const mentorSelect = chat.querySelector("#chat-mentor-select");
  const mentorPreview = chat.querySelector("[data-mentor-preview]");
  const forwardConversation = chat.querySelector("[data-forward-conversation]");
  const forwardButton = chat.querySelector("[data-forward-chat]");
  const historyList = chat.querySelector("[data-history-list]");
  const historyEmpty = chat.querySelector("[data-history-empty]");
  const emptyStateTemplate = chat.querySelector("[data-chat-empty-state]");
  const historyKey = `sembon.chat.history.v1.${chat.dataset.userKey}`;
  let historyEntries = [];
  let isSending = false;
  let isForwarded = Boolean(chat.dataset.chatStatus);
  let chatStatus = chat.dataset.chatStatus || "";
  let lastQuestion = "";
  let pollTimer = null;

  const setFeedback = (message, isError = false) => {
    feedback.textContent = message;
    feedback.classList.toggle("chat-feedback-error", isError);
  };

  const updateSendButton = () => {
    sendButton.disabled = isSending || chatStatus === "closed" || !input.value.trim();
    input.disabled = isSending;
    chat.querySelectorAll("button:not([data-chat-send])").forEach((button) => {
      button.disabled = isSending;
    });
  };

  const fadeTranscript = async () => {
    transcript.classList.add("chat-transcript-fading");
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    transcript.classList.remove("chat-transcript-fading");
  };

  const formatTime = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Just now";
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  };

  const createMessage = (
    role,
    text,
    timestamp = new Date().toISOString(),
    { suggestions = [], needsMentor = false, authorName = "" } = {},
  ) => {
    const isUser = role === "user";
    const isMentor = role === "mentor";
    const row = document.createElement("div");
    row.className = `chat-message-row ${
      isUser
        ? "chat-message-own"
        : isMentor
          ? "chat-message-staff"
          : role === "error"
            ? "chat-message-error"
            : "chat-message-bot"
    }`;
    row.dataset.chatRole = role;

    const avatar = document.createElement("span");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = isUser ? "You" : role === "error" ? "!" : isMentor ? "M" : "AI";

    const bubble = document.createElement("div");
    bubble.className = "chat-message-bubble";

    const meta = document.createElement("div");
    meta.className = "chat-message-meta";
    const author = document.createElement("span");
    author.className = "chat-message-author";
    author.textContent =
      authorName || (isUser ? "You" : role === "error" ? "A quick note" : isMentor ? "Mentor" : "Campus assistant");
    meta.append(author);

    const message = document.createElement("div");
    message.className = "chat-message-text";
    message.textContent = text;
    const time = document.createElement("time");
    time.className = "chat-message-time";
    time.dateTime = timestamp;
    time.textContent = formatTime(timestamp);
    bubble.append(meta, message, time);

    if (!isUser && role !== "error") {
      const copyButton = document.createElement("button");
      copyButton.className = "chat-copy";
      copyButton.type = "button";
      copyButton.dataset.copyAnswer = "";
      copyButton.setAttribute("aria-label", "Copy answer");
      copyButton.textContent = "Copy";
      meta.append(copyButton);
    }

    if (!isUser && role !== "error" && (suggestions.length || needsMentor)) {
      const actions = document.createElement("div");
      actions.className = "chat-message-actions";
      suggestions.forEach((suggestion) => {
        const button = document.createElement("button");
        button.className = "chat-followup";
        button.type = "button";
        button.dataset.chatQuestion = suggestion;
        button.textContent = suggestion;
        actions.append(button);
      });
      if (needsMentor && !isForwarded) {
        const contactButton = document.createElement("button");
        contactButton.className = "chat-followup chat-followup-contact";
        contactButton.type = "button";
        contactButton.dataset.openMentorPicker = "";
        contactButton.dataset.chatTopic = lastQuestion;
        contactButton.textContent = "Contact Mentor";
        actions.append(contactButton);
      }
      bubble.append(actions);
    }

    row.append(avatar, bubble);
    return row;
  };

  const scrollToLatest = () => {
    transcript.scrollTop = transcript.scrollHeight;
  };

  const renderHistory = () => {
    historyList.replaceChildren();
    historyEmpty.hidden = historyEntries.length > 0;
    historyEntries.forEach((entry) => {
      const button = document.createElement("button");
      button.className = "chat-history-item";
      button.type = "button";
      button.dataset.historyId = entry.id;

      const question = document.createElement("span");
      question.className = "chat-history-question";
      question.textContent = entry.question;
      const date = document.createElement("span");
      date.className = "chat-history-date";
      date.textContent = formatTime(entry.timestamp);
      button.append(question, date);
      historyList.append(button);
    });
  };

  const saveHistoryEntry = (question, answer, timestamp) => {
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      question,
      answer,
      timestamp,
    };
    historyEntries = [entry, ...historyEntries].slice(0, 50);
    try {
      localStorage.setItem(historyKey, JSON.stringify(historyEntries));
    } catch (error) {
      setFeedback("Your answer is ready, but this browser could not save it to History.", true);
    }
    renderHistory();
  };

  const showEmptyState = async (title, description) => {
    await fadeTranscript();
    transcript.replaceChildren(emptyStateTemplate.content.cloneNode(true));
    const heading = transcript.querySelector(".chat-empty-state h3");
    const message = transcript.querySelector(".chat-empty-state p");
    if (title) heading.textContent = title;
    if (description) message.textContent = description;
  };

  const showConversation = async (question, answer, timestamp) => {
    await fadeTranscript();
    transcript.replaceChildren(
      createMessage("user", question, timestamp),
      createMessage("assistant", answer, timestamp),
    );
    scrollToLatest();
  };

  const showTypingIndicator = () => {
    const indicator = document.createElement("div");
    indicator.className = "chat-typing";
    indicator.dataset.typingIndicator = "";
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-label", "Campus assistant is typing");
    indicator.innerHTML = "<span></span><span></span><span></span>";
    transcript.append(indicator);
    scrollToLatest();
  };

  const setChatStatus = (status) => {
    chatStatus = status || "";
    chat.dataset.chatStatus = chatStatus;
    statusLabel.hidden = !chatStatus;
    statusLabel.textContent = chatStatus
      ? chatStatus.charAt(0).toUpperCase() + chatStatus.slice(1)
      : "";
    updateSendButton();
  };

  const renderThread = (payload) => {
    if (payload.conversation_id) {
      conversationInput.value = payload.conversation_id;
      forwardConversation.value = payload.conversation_id;
      chat.dataset.conversationId = payload.conversation_id;
    }
    if (payload.status) {
      isForwarded = true;
      setChatStatus(payload.status);
    }
    const messageNodes = (payload.messages || []).map((message) =>
      createMessage(message.sender_type, message.body, message.timestamp, {
        authorName: message.sender_name,
      }),
    );
    transcript.replaceChildren(...messageNodes);
    scrollToLatest();
  };

  const requestJson = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "The request could not be completed.");
    }
    return result;
  };

  const updateMentorPreview = () => {
    const selected = mentorSelect.selectedOptions[0];
    if (!selected || !selected.value) {
      mentorPreview.textContent = "";
      return;
    }
    mentorPreview.textContent =
      `${selected.dataset.expertise} · ${selected.dataset.availability}`;
  };

  const openMentorPicker = async (topic = lastQuestion) => {
    setFeedback("");
    try {
      const url = new URL(chat.dataset.mentorsUrl, window.location.origin);
      url.searchParams.set("topic", topic);
      const result = await requestJson(url);
      mentorSelect.replaceChildren();
      result.mentors.forEach((mentor) => {
        const option = document.createElement("option");
        option.value = mentor.id;
        option.textContent = `${mentor.name} · ${mentor.expertise} · ${mentor.availability}`;
        option.dataset.expertise = mentor.expertise;
        option.dataset.availability = mentor.availability;
        option.selected = mentor.id === result.recommended_mentor_id;
        mentorSelect.append(option);
      });
      forwardConversation.value = conversationInput.value;
      mentorPicker.hidden = false;
      updateMentorPreview();
      mentorSelect.focus();
    } catch (error) {
      setFeedback(error.message || "No mentors are available right now. Please try again later.", true);
    }
  };

  const syncStudentThread = async () => {
    if (!isForwarded || !conversationInput.value) return;
    const url = chat.dataset.updatesUrlTemplate.replace(
      /\/0\//,
      `/${conversationInput.value}/`,
    );
    try {
      const result = await requestJson(url);
      renderThread(result);
    } catch (error) {
      setFeedback("Couldn't refresh the mentor chat. Check your connection and try again.", true);
    }
  };

  const startPolling = () => {
    if (pollTimer) window.clearInterval(pollTimer);
    if (!isForwarded || !conversationInput.value) return;
    pollTimer = window.setInterval(syncStudentThread, 4000);
  };

  try {
    const savedHistory = JSON.parse(localStorage.getItem(historyKey) || "[]");
    if (Array.isArray(savedHistory)) {
      historyEntries = savedHistory.filter(
        (entry) =>
          entry &&
          typeof entry.id === "string" &&
          typeof entry.question === "string" &&
          typeof entry.answer === "string" &&
          typeof entry.timestamp === "string",
      ).slice(0, 50);
    }
  } catch (error) {
    setFeedback("Saved History could not be loaded from this browser.", true);
  }
  renderHistory();
  updateSendButton();
  if (isForwarded && conversationInput.value) {
    syncStudentThread();
    startPolling();
  }

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
    updateSendButton();
    if (feedback.textContent) setFeedback("");
  });

  input.addEventListener("keydown", (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.isComposing
    ) {
      event.preventDefault();
      if (!sendButton.disabled) form.requestSubmit();
    }
  });

  mentorSelect.addEventListener("change", updateMentorPreview);

  mentorForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!conversationInput.value) {
      setFeedback("Ask a question before forwarding a chat to a mentor.", true);
      return;
    }
    if (!mentorSelect.value) {
      setFeedback("Choose an available mentor first.", true);
      return;
    }
    forwardConversation.value = conversationInput.value;
    forwardButton.disabled = true;
    setFeedback("");
    try {
      const result = await requestJson(mentorForm.action, {
        method: "POST",
        body: new FormData(mentorForm),
      });
      isForwarded = true;
      mentorPicker.hidden = true;
      renderThread(result);
      setFeedback(result.message || "Your chat was forwarded to the mentor.");
      startPolling();
    } catch (error) {
      setFeedback(error.message || "The chat could not be forwarded. Please try again.", true);
    } finally {
      forwardButton.disabled = false;
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) {
      setFeedback("Type a question before sending.", true);
      updateSendButton();
      return;
    }
    if (question.length > 2000) {
      setFeedback("Keep your question under 2,000 characters.", true);
      return;
    }

    isSending = true;
    lastQuestion = question;
    setFeedback("");
    updateSendButton();
    await fadeTranscript();
    transcript.replaceChildren(createMessage("user", question));
    showTypingIndicator();

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.headers.get("content-type")?.includes("application/json")) {
        throw new Error(
          response.redirected
            ? "Your session may have expired. Refresh the page and sign in again."
            : "The server returned an unexpected response. Please try again.",
        );
      }

      let result;
      try {
        result = await response.json();
      } catch (error) {
        throw new Error("We couldn't read the server's reply. Please try again.");
      }
      if (!response.ok) {
        throw new Error(result.error || "We couldn't send that question. Please try again.");
      }

      transcript.querySelector("[data-typing-indicator]")?.remove();
      const timestamp = result.timestamp || new Date().toISOString();
      input.value = "";
      input.style.height = "auto";
      if (result.conversation_id) {
        conversationInput.value = result.conversation_id;
        forwardConversation.value = result.conversation_id;
        chat.dataset.conversationId = result.conversation_id;
      }
      if (result.forwarded) {
        renderThread(result);
        setFeedback("Your message was sent to your mentor.");
        saveHistoryEntry(
          result.question,
          "Your message was sent to your mentor.",
          timestamp,
        );
        startPolling();
      } else {
        transcript.append(
          createMessage("assistant", result.answer, timestamp, {
            suggestions: result.suggestions || [],
            needsMentor: Boolean(result.needs_mentor),
          }),
        );
        saveHistoryEntry(result.question, result.answer, timestamp);
        scrollToLatest();
      }
    } catch (error) {
      transcript.querySelector("[data-typing-indicator]")?.remove();
      const message =
        error instanceof TypeError
          ? "We couldn't reach the server. Check your connection and try again."
          : error.message;
      transcript.append(createMessage("error", message));
      setFeedback(message, true);
      scrollToLatest();
    } finally {
      isSending = false;
      updateSendButton();
    }
  });

  chat.addEventListener("click", async (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const suggestion = target.closest("[data-chat-question]");
    if (suggestion) {
      input.value = suggestion.dataset.chatQuestion;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
      return;
    }

    const contactButton = target.closest("[data-open-mentor-picker]");
    if (contactButton) {
      await openMentorPicker(contactButton.dataset.chatTopic || lastQuestion);
      return;
    }

    const historyButton = target.closest("[data-history-id]");
    if (historyButton) {
      const entry = historyEntries.find((item) => item.id === historyButton.dataset.historyId);
      if (entry) await showConversation(entry.question, entry.answer, entry.timestamp);
      setFeedback("");
      return;
    }

    if (target.closest("[data-new-chat]")) {
      await showEmptyState("A fresh chat is ready.", "Your saved conversations are still available in History.");
      if (pollTimer) window.clearInterval(pollTimer);
      pollTimer = null;
      conversationInput.value = "";
      forwardConversation.value = "";
      chat.dataset.conversationId = "";
      isForwarded = false;
      setChatStatus("");
      mentorPicker.hidden = true;
      lastQuestion = "";
      input.value = "";
      input.style.height = "auto";
      setFeedback("");
      updateSendButton();
      input.focus();
      return;
    }

    if (target.closest("[data-clear-chat]")) {
      await showEmptyState("Chat cleared.", "Your saved conversations are still available in History.");
      input.value = "";
      input.style.height = "auto";
      setFeedback("");
      updateSendButton();
      input.focus();
      return;
    }

    if (target.closest("[data-close-mentor-picker]")) {
      mentorPicker.hidden = true;
      return;
    }

    if (target.closest("[data-clear-history]")) {
      try {
        localStorage.removeItem(historyKey);
        historyEntries = [];
        renderHistory();
        setFeedback("Saved chat history cleared.");
      } catch (error) {
        setFeedback("This browser could not clear the saved chat history.", true);
      }
      return;
    }

    const copyButton = target.closest("[data-copy-answer]");
    if (copyButton) {
      const message = copyButton.closest(".chat-message-bubble")?.querySelector(".chat-message-text");
      if (!message) return;
      try {
        await navigator.clipboard.writeText(message.textContent);
        setFeedback("Answer copied to clipboard.");
      } catch (error) {
        setFeedback("Could not copy the answer. Select and copy the text instead.", true);
      }
    }
  });

  if (window.matchMedia("(min-width: 768px)").matches) {
    input.focus({ preventScroll: true });
  }
})();
