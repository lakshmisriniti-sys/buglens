// The public "Report a problem" page.
const $ = (selector) => document.querySelector(selector);

const form = $("#report-form");
const sendButton = $("#send-report");
const errorBox = $("#report-error");

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault(); // stop the browser's default page reload
  errorBox.hidden = true;

  const description = form.elements["description"].value.trim();
  if (description.length < 5) {
    showError("Please describe the problem in a few more words.");
    return;
  }

  sendButton.disabled = true;
  sendButton.textContent = "Sending…";
  try {
    const res = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    });
    if (!res.ok) throw new Error();
    const receipt = await res.json();

    // Swap the form for the thank-you message.
    $("#report-id").textContent = `#${receipt.id}`;
    form.hidden = true;
    $("#thanks").hidden = false;
  } catch {
    showError("Sorry, something went wrong sending your report. Please try again.");
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Send report";
  }
});

$("#report-another").addEventListener("click", () => {
  form.reset();
  $("#thanks").hidden = true;
  form.hidden = false;
  form.elements["description"].focus();
});
