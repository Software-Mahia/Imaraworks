// auth.js - shared by every role page (employee.html, manager.html, finance.html, admin.html)
// Include it once with <script src="{% static 'frontend/auth.js' %}"></script>, before each
// page's own <script> block, then call AUTH.apiFetch(...) instead of fetch(...) everywhere.

const AUTH = (() => {
  const ACCESS_KEY = "imaraworks_access";
  const REFRESH_KEY = "imaraworks_refresh";

  // NOTE on localStorage: simplest option for a project this size, but tokens stored here are
  // readable by any JS that runs on the page. That is why every page must escape data before
  // putting it into innerHTML (see esc() in manager.html and finance.html): one XSS hole
  // becomes token theft. The safer alternative, an httpOnly cookie set by the server, is more
  // setup than this timeline allows. List it under "known limitations" in the documentation.

  function getAccess() { return localStorage.getItem(ACCESS_KEY); }
  function getRefresh() { return localStorage.getItem(REFRESH_KEY); }

  function setTokens(access, refresh) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  }

  function clearTokens() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  async function login(username, password) {
    const res = await fetch("/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error("Login failed - check the username and password.");
    const data = await res.json();
    setTokens(data.access, data.refresh);
    return data;
  }

  function logout() {
    clearTokens();
    window.location.href = "/login/";  // route of LoginView in frontend/urls.py
  }

  async function doRefresh() {
    const refresh = getRefresh();
    if (!refresh) throw new Error("No refresh token on file - need to log in again.");
    const res = await fetch("/api/auth/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) {
      clearTokens();
      throw new Error("Session expired - please log in again.");
    }
    const data = await res.json();
    // If the backend ever turns on ROTATE_REFRESH_TOKENS, it returns a new refresh token too,
    // and setTokens stores it. Without rotation, data.refresh is undefined and is ignored.
    setTokens(data.access, data.refresh);
    return data.access;
  }

  // Only one refresh runs at a time. If several requests get a 401 together, they all wait on
  // the same in-flight promise instead of each calling /api/auth/refresh/.
  let refreshInFlight = null;
  function refreshAccessToken() {
    if (!refreshInFlight) {
      refreshInFlight = doRefresh().finally(() => { refreshInFlight = null; });
    }
    return refreshInFlight;
  }

  function buildHeaders(options, token) {
    const headers = { ...(options.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`; // no token, no header (never "Bearer null")
    // JSON bodies are sent as strings, so default the Content-Type and callers can't forget it.
    if (typeof options.body === "string" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    return headers;
  }

  // The one function every page should call instead of fetch() directly.
  // Attaches the access token; if the server answers 401, refreshes once and retries the
  // same request. If the refresh fails, clears the session and sends the user to login.
  async function apiFetch(url, options = {}) {
    let res = await fetch(url, { ...options, headers: buildHeaders(options, getAccess()) });

    if (res.status === 401) {
      try {
        const newAccess = await refreshAccessToken();
        res = await fetch(url, { ...options, headers: buildHeaders(options, newAccess) });
        if (res.status === 401) logout(); // the fresh token was rejected too: end the session
      } catch (err) {
        logout();
        throw err;
      }
    }
    return res;
  }

  async function getCurrentUser() {
    const res = await apiFetch("/api/auth/me/");
    if (!res.ok) throw new Error("Could not load the current user.");
    return res.json(); // { username, first_name, last_name, role }
  }

  return {
    login,
    logout,
    apiFetch,
    getCurrentUser,
    isLoggedIn: () => !!getAccess(),
  };
})();