/* InterviewAI - Centralized API Service */
const API_BASE_URL = window.location.origin.includes("http") ? "" : "http://localhost:8000";

class API {
  static getToken() {
    return localStorage.getItem("interviewai_token") || localStorage.getItem("token");
  }

  static setToken(token) {
    if (token) {
      localStorage.setItem("interviewai_token", token);
      localStorage.setItem("token", token);
    }
  }

  static removeToken() {
    localStorage.removeItem("interviewai_token");
    localStorage.removeItem("token");
    localStorage.removeItem("interviewai_user");
    localStorage.removeItem("user");
  }

  static getUser() {
    const u = localStorage.getItem("interviewai_user") || localStorage.getItem("user");
    try {
      return u ? JSON.parse(u) : null;
    } catch (_) {
      return null;
    }
  }

  static setUser(user) {
    if (user) {
      const uStr = typeof user === "string" ? user : JSON.stringify(user);
      localStorage.setItem("interviewai_user", uStr);
      localStorage.setItem("user", uStr);
    }
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

  static patch(endpoint, body) {
    return API.request(endpoint, { method: "PATCH", body: JSON.stringify(body) });
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

  // Intelligence & Memory API Endpoints
  static getMemorySummary() {
    return API.get("/api/intelligence/memory-summary");
  }

  static getSessionComparison(interviewId) {
    return API.get(`/api/intelligence/session-comparison/${interviewId}`);
  }

  static getAnalyticsDashboard(params = {}) {
    const qs = new URLSearchParams();
    if (params.date_from) qs.set("date_from", params.date_from);
    if (params.date_to) qs.set("date_to", params.date_to);
    if (params.session_a_id) qs.set("session_a_id", params.session_a_id);
    if (params.session_b_id) qs.set("session_b_id", params.session_b_id);
    const qsStr = qs.toString();
    return API.get(`/api/intelligence/analytics-dashboard${qsStr ? "?" + qsStr : ""}`);
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
