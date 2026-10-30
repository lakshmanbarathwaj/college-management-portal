(() => {
  const dashboard = document.querySelector("[data-mentor-dashboard]");
  const thread = dashboard?.querySelector("[data-mentor-thread]");
  if (!dashboard || !thread) return;

  const statusLabel = dashboard.querySelector("[data-mentor-status]");
  const feedback = dashboard.querySelector("[data-mentor-feedback]");
  const replyForm = dashboard.querySelector("[data-mentor-reply-form]");
  const closeForm = dashboard.querySelector("[data-mentor-close-form]");
  let busy = false;

  const setFeedback = (message, isError = false) => {
    feedback.textContent = message;
    feedback.classList.toggle("chat-feedback-error", isError);
  };

  const setStatus = (status) => {
    statusLabel.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    const closed = status === "closed";
    replyForm.querySelector("textarea").disabled = closed;
    replyForm.querySelector("button[type=submit]").disabled = closed;
    closeForm.querySelector("button[type=submit]").disabled = closed;
  };

  const addMessage = (message) => {
    const row = document.createElement("article");
    row.className = `mentor-thread-message ${
      message.sender_type === "mentor"
        ? "mentor-thread-own"
        : message.sender_type === "assistant"
          ? "mentor-thread-assistant"
          : "mentor-thread-student"
    }`;
    row.dataset.messageId = message.id;

    const meta = document.createElement("div");
    meta.className = "mentor-thread-meta";
    const sender = document.createElement("strong");
    sender.textContent = message.sender_name;
    const time = document.createElement("time");
    time.dateTime = message.timestamp;
    const parsedTime = new Date(message.timestamp);
    time.textContent = Number.isNaN(parsedTime.getTime())
      ? ""
      : new Intl.DateTimeFormat(undefined, {
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
        }).format(parsedTime);
    meta.append(sender, time);

    const text = document.createElement("div");
    text.className = "mentor-thread-text";
    text.textContent = message.body;
    row.append(meta, text);
    return row;
  };

  const renderMessages = (messages) => {
    thread.replaceChildren(...messages.map(addMessage));
    thread.scrollTop = thread.scrollHeight;
  };

  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The request could not be completed.");
    return result;
  };

  const refresh = async () => {
    if (busy) return;
    try {
      const result = await request(dashboard.dataset.updatesUrl);
      renderMessages(result.messages);
      setStatus(result.status);
      const selected = dashboard.querySelector(".mentor-chat-list-item.is-selected .mentor-unread-badge");
      selected?.remove();
    } catch (error) {
      setFeedback("Couldn't refresh this chat. Check your connection and try again.", true);
    }
  };

  const submitForm = async (event, form, isClose = false) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    setFeedback("");
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const result = await request(form.action, {
        method: "POST",
        body: new FormData(form),
      });
      renderMessages(result.messages);
      setStatus(result.status);
      setFeedback(result.message);
      if (!isClose) form.querySelector("textarea").value = "";
    } catch (error) {
      setFeedback(error.message || "Your reply could not be sent. Please try again.", true);
    } finally {
      busy = false;
      if (statusLabel.textContent.toLowerCase() !== "closed") button.disabled = false;
    }
  };

  replyForm.addEventListener("submit", (event) => submitForm(event, replyForm));
  closeForm.addEventListener("submit", (event) => submitForm(event, closeForm, true));

  refresh();
  window.setInterval(refresh, 4000);
})();
