/* InterviewAI - Centralized API Service */
const API_BASE_URL = window.location.origin.includes("http") ? "" : "http://localhost:8000";

class API {
  static getToken() {
    return localStorage.getItem("interviewai_token");
  }

  static setToken(token) {
    localStorage.setItem("interviewai_token", token);
  }

  static removeToken() {
    localStorage.removeItem("interviewai_token");
    localStorage.removeItem("interviewai_user");
  }

  static getUser() {
    const u = localStorage.getItem("interviewai_user");
    return u ? JSON.parse(u) : null;
  }

  static setUser(user) {
    localStorage.setItem("interviewai_user", JSON.stringify(user));
  }

  static async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = API.getToken();

    const headers = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    };

    try {
      const response = await fetch(url, { ...options, headers });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401 && !endpoint.includes("/auth/")) {
          API.removeToken();
          window.location.href = "login.html";
        }
        throw new Error(data.detail || data.message || "An unexpected error occurred");
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  static get(endpoint) {
    return API.request(endpoint, { method: "GET" });
  }

  static post(endpoint, body) {
    return API.request(endpoint, { method: "POST", body: JSON.stringify(body) });
  }

  static async postFormData(endpoint, formData) {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = API.getToken();
    const headers = {
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };

    try {
      const response = await fetch(url, { method: "POST", body: formData, headers });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401 && !endpoint.includes("/auth/")) {
          API.removeToken();
          window.location.href = "login.html";
        }
        throw new Error(data.detail || data.message || "An unexpected error occurred");
      }
      return data;
    } catch (err) {
      console.error(`API FormData Error on ${endpoint}:`, err);
      throw err;
    }
  }

  static put(endpoint, body) {
    return API.request(endpoint, { method: "PUT", body: JSON.stringify(body) });
  }

  // Coding Interview API Endpoints
  static startCodingInterview(data) {
    return API.post("/api/coding/start", data);
  }

  static getCodingInterview(id) {
    return API.get(`/api/coding/${id}`);
  }

  static runCodingTests(data) {
    return API.post("/api/coding/run-tests", data);
  }

  static submitCodingSolution(data) {
    return API.post("/api/coding/submit", data);
  }

  static getCodingResults(id) {
    return API.get(`/api/coding/${id}/results`);
  }
}


// Toast Helper
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Auth Guard Helper
function requireAuth() {
  if (!API.getToken()) {
    window.location.href = "login.html";
  }
}
