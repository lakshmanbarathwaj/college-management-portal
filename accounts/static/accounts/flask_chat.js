(() => {
  const form = document.querySelector("[data-question-form]");
  const questionInput = document.querySelector("#question");
  const answerContainer = document.querySelector("[data-answer]");
  const submitButton = document.querySelector("[data-submit]");
  if (!form || !questionInput || !answerContainer || !submitButton) return;

  const showMessage = (message, isError = false) => {
    const paragraph = document.createElement("p");
    paragraph.className = isError ? "text-danger mb-0" : "mb-0";
    paragraph.textContent = message;
    answerContainer.replaceChildren(paragraph);
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitButton.disabled = true;
    showMessage("Finding an answer...");
    try {
      const response = await fetch("/api/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: questionInput.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The question could not be answered.");
      showMessage(result.answer);
    } catch (error) {
      showMessage(error.message || "The answer service is unavailable. Try again.", true);
    } finally {
      submitButton.disabled = false;
    }
  });

  document.querySelectorAll("[data-suggestion]").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.suggestion;
      form.requestSubmit();
    });
  });
})();
