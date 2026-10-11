/* Registration & Login Form Logic */
document.addEventListener("DOMContentLoaded", () => {
  const registerForm = document.getElementById("register-form");
  const loginForm = document.getElementById("login-form");

  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = registerForm.querySelector("button[type='submit']");
      const errEl = document.getElementById("auth-error");
      if (errEl) errEl.textContent = "";

      const name = document.getElementById("name").value.trim();
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const confirmPassword = document.getElementById("confirm-password") ? document.getElementById("confirm-password").value : "";

      if (confirmPassword && password !== confirmPassword) {
        if (errEl) errEl.textContent = "Passwords do not match.";
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner"></span> Creating Account...`;

      try {
        const res = await API.post("/api/auth/register", {
          name,
          email,
          password,
          confirm_password: confirmPassword
        });
        API.setToken(res.access_token);
        API.setUser(res.user);
        showToast("Account created successfully! Redirecting...", "success");
        setTimeout(() => {
          window.location.href = "dashboard.html";
        }, 1000);
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = "Create Account";
        if (errEl) errEl.textContent = err.message;
        showToast(err.message, "error");
      }
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = loginForm.querySelector("button[type='submit']");
      const errEl = document.getElementById("auth-error");
      if (errEl) errEl.textContent = "";

      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;

      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner"></span> Logging In...`;

      try {
        const res = await API.post("/api/auth/login", { email, password });
        API.setToken(res.access_token);
        API.setUser(res.user);
        showToast("Logged in successfully! Redirecting...", "success");
        setTimeout(() => {
          window.location.href = "dashboard.html";
        }, 1000);
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = "Log In";
        if (errEl) errEl.textContent = err.message;
        showToast(err.message, "error");
      }
    });
  }
});
