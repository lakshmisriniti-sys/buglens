// The team login page.
const $ = (selector) => document.querySelector(selector);

const form = $("#login-form");
const button = $("#login-button");
const errorBox = $("#login-error");

// Show the demo password hint, if the server is using the public demo password.
fetch("/api/auth/status")
  .then((res) => res.json())
  .then((status) => {
    if (status.logged_in) location.href = "/team";
    if (status.demo_password) {
      $("#demo-password").textContent = status.demo_password;
      $("#demo-hint").hidden = false;
    }
  })
  .catch(() => {});

form.addEventListener("submit", async (event) => {
  event.preventDefault(); // stop the browser's default page reload
  errorBox.hidden = true;
  button.disabled = true;
  button.textContent = "Logging in…";

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: form.elements["password"].value }),
    });
    if (res.ok) {
      location.href = "/team"; // the browser now has the login cookie
      return;
    }
    errorBox.textContent = res.status === 401
      ? "Wrong password. Please try again."
      : "Something went wrong. Please try again.";
  } catch {
    errorBox.textContent = "Couldn't reach the server. Please try again.";
  }
  errorBox.hidden = false;
  form.elements["password"].select();
  button.disabled = false;
  button.textContent = "Log in";
});
