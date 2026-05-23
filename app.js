const categories = ["All", "Frontend", "Backend", "Analytics", "AI", "Security", "Product"];
const themeKey = "baseline-share-theme";

const defaultState = {
  user: null,
  credits: 0,
  favorites: [],
  downloads: [],
  projects: [],
  stats: {
    projects: 0,
    downloads: 0,
    uploads: 0,
    favorites: 0
  },
  theme: localStorage.getItem(themeKey) || "light"
};

let appState = { ...defaultState };
let activeCategory = "All";
let pendingAdToken = null;
let pendingDownloadProject = null;
let countdownTimer = null;

const el = {
  projectGrid: document.querySelector("#projectGrid"),
  filterBar: document.querySelector("#filterBar"),
  searchInput: document.querySelector("#searchInput"),
  creditCount: document.querySelector("#creditCount"),
  statProjects: document.querySelector("#statProjects"),
  statDownloads: document.querySelector("#statDownloads"),
  statUploads: document.querySelector("#statUploads"),
  statFavorites: document.querySelector("#statFavorites"),
  downloadHistory: document.querySelector("#downloadHistory"),
  uploadForm: document.querySelector("#uploadForm"),
  accountPanel: document.querySelector("#accountPanel"),
  loginButton: document.querySelector("#loginButton"),
  themeButton: document.querySelector("#themeButton"),
  authDialog: document.querySelector("#authDialog"),
  authForm: document.querySelector("#authForm"),
  adDialog: document.querySelector("#adDialog"),
  adTitle: document.querySelector("#adTitle"),
  adCopy: document.querySelector("#adCopy"),
  finishAdButton: document.querySelector("#finishAdButton"),
  closeAdButton: document.querySelector("#closeAdButton"),
  toast: document.querySelector("#toast")
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const error = await response.json();
      message = error.error || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.json();
}

async function refresh() {
  const data = await api("/api/bootstrap");
  appState = {
    ...appState,
    user: data.user,
    credits: data.credits,
    projects: data.projects,
    favorites: data.favorites,
    downloads: data.downloads,
    stats: data.stats
  };
  renderAll();
}

async function init() {
  document.documentElement.dataset.theme = appState.theme;
  renderFilters();
  bindEvents();
  renderLoading();
  try {
    await refresh();
  } catch (error) {
    renderBackendError(error);
  }
  if (window.lucide) lucide.createIcons();
}

function bindEvents() {
  document.querySelectorAll("[data-view-link]").forEach(link => {
    link.addEventListener("click", event => {
      event.preventDefault();
      showView(link.dataset.viewLink);
    });
  });

  el.searchInput.addEventListener("input", renderProjects);

  el.loginButton.addEventListener("click", async () => {
    if (!appState.user) {
      el.authDialog.showModal();
      return;
    }
    try {
      await api("/api/auth/logout", { method: "POST", body: "{}" });
      await refresh();
      toast("Logged out.");
    } catch (error) {
      toast(error.message);
    }
  });

  el.authForm.addEventListener("submit", async event => {
    event.preventDefault();
    const data = new FormData(el.authForm);
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name").trim(),
          email: data.get("email").trim()
        })
      });
      el.authDialog.close();
      el.authForm.reset();
      await refresh();
      toast("Account saved to the database.");
    } catch (error) {
      toast(error.message);
    }
  });

  el.themeButton.addEventListener("click", () => {
    appState.theme = appState.theme === "dark" ? "light" : "dark";
    localStorage.setItem(themeKey, appState.theme);
    document.documentElement.dataset.theme = appState.theme;
  });

  el.uploadForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (!requireLogin()) return;

    const data = new FormData(el.uploadForm);
    try {
      const payload = {
        title: data.get("title").trim(),
        category: data.get("category"),
        stack: data.get("stack").trim(),
        description: data.get("description").trim()
      };
      const nextState = await api("/api/projects", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      applyBootstrap(nextState);
      el.uploadForm.reset();
      showView("library");
      toast("Baseline uploaded. Five ad-free download credits added.");
    } catch (error) {
      toast(error.message);
    }
  });

  el.finishAdButton.addEventListener("click", async () => {
    if (!pendingAdToken || !pendingDownloadProject) return;
    try {
      const nextState = await api("/api/downloads/complete-ad", {
        method: "POST",
        body: JSON.stringify({ ad_token: pendingAdToken })
      });
      applyBootstrap(nextState);
      await downloadManifest(pendingDownloadProject);
      toast(`${pendingDownloadProject.title} unlocked.`);
      pendingAdToken = null;
      pendingDownloadProject = null;
      el.adDialog.close();
    } catch (error) {
      toast(error.message);
    }
  });

  el.closeAdButton.addEventListener("click", () => {
    pendingAdToken = null;
    pendingDownloadProject = null;
    clearInterval(countdownTimer);
    el.adDialog.close();
  });
}

function applyBootstrap(data) {
  appState = {
    ...appState,
    user: data.user,
    credits: data.credits,
    projects: data.projects,
    favorites: data.favorites,
    downloads: data.downloads,
    stats: data.stats
  };
  renderAll();
}

function showView(viewName) {
  document.querySelectorAll(".view").forEach(view => view.classList.remove("active"));
  document.querySelector(`#${viewName}View`).classList.add("active");
  document.querySelectorAll("[data-view-link]").forEach(link => {
    link.classList.toggle("active", link.dataset.viewLink === viewName);
  });
  renderAll();
}

function renderAll() {
  renderProjects();
  renderStats();
  renderHistory();
  renderAccount();
  renderLogin();
  if (window.lucide) lucide.createIcons();
}

function renderLoading() {
  el.projectGrid.innerHTML = `<div class="history-item"><strong>Loading baselines...</strong><span>Connecting to the local database.</span></div>`;
}

function renderBackendError(error) {
  el.projectGrid.innerHTML = `
    <div class="history-item">
      <strong>Backend is not reachable.</strong>
      <span>${escapeHtml(error.message)}. Start the Baseline Share server and reload.</span>
    </div>
  `;
}

function renderFilters() {
  el.filterBar.innerHTML = categories.map(category => (
    `<button class="filter-button ${category === activeCategory ? "active" : ""}" data-category="${category}">${category}</button>`
  )).join("");

  el.filterBar.querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.category;
      renderFilters();
      renderProjects();
    });
  });
}

function renderProjects() {
  const term = el.searchInput.value.trim().toLowerCase();
  const projects = appState.projects.filter(project => {
    const categoryMatch = activeCategory === "All" || project.category === activeCategory;
    const text = `${project.title} ${project.description} ${project.stack.join(" ")} ${project.category}`.toLowerCase();
    return categoryMatch && (!term || text.includes(term));
  });

  if (!projects.length) {
    el.projectGrid.innerHTML = `<div class="history-item"><strong>No baselines found.</strong><span>Try another search or upload one.</span></div>`;
    return;
  }

  el.projectGrid.innerHTML = projects.map(project => {
    const favorite = appState.favorites.includes(project.id);
    return `
      <article class="project-card">
        <div class="project-thumb" style="--thumb:${project.color}">
          <code>${project.file}</code>
        </div>
        <h3>${escapeHtml(project.title)}</h3>
        <p>${escapeHtml(project.description)}</p>
        <div class="project-meta">
          <span>${escapeHtml(project.category)}</span>
          ${project.stack.map(item => `<span>${escapeHtml(item)}</span>`).join("")}
          <span>${project.downloads} downloads</span>
        </div>
        <div class="card-actions">
          <button class="primary-button" data-download="${project.id}"><i data-lucide="download"></i> Download</button>
          <button class="outline-button favorite-button ${favorite ? "active" : ""}" data-favorite="${project.id}" title="Favorite" aria-label="Favorite ${escapeHtml(project.title)}"><i data-lucide="star"></i></button>
        </div>
      </article>
    `;
  }).join("");

  el.projectGrid.querySelectorAll("[data-download]").forEach(button => {
    button.addEventListener("click", () => startDownload(button.dataset.download));
  });

  el.projectGrid.querySelectorAll("[data-favorite]").forEach(button => {
    button.addEventListener("click", () => toggleFavorite(button.dataset.favorite));
  });

  if (window.lucide) lucide.createIcons();
}

function renderStats() {
  el.creditCount.textContent = appState.credits;
  el.statProjects.textContent = appState.stats.projects;
  el.statDownloads.textContent = appState.stats.downloads;
  el.statUploads.textContent = appState.stats.uploads;
  el.statFavorites.textContent = appState.stats.favorites;
}

function renderHistory() {
  if (!appState.downloads.length) {
    el.downloadHistory.innerHTML = `<div class="history-item"><strong>No downloads yet.</strong><span>Downloaded baselines will appear here.</span></div>`;
    return;
  }

  el.downloadHistory.innerHTML = appState.downloads.map(item => `
    <article class="history-item">
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <p>${escapeHtml(item.method)}</p>
      </div>
      <time>${new Date(item.time).toLocaleString()}</time>
    </article>
  `).join("");
}

function renderAccount() {
  if (!appState.user) {
    el.accountPanel.innerHTML = `
      <p>You are browsing as a guest. Log in to save favorites, uploads, credits, and download history in the database.</p>
      <button class="primary-button" id="accountLoginButton"><i data-lucide="log-in"></i> Log in</button>
    `;
    document.querySelector("#accountLoginButton").addEventListener("click", () => el.authDialog.showModal());
    return;
  }

  const favoriteTitles = appState.projects
    .filter(project => appState.favorites.includes(project.id))
    .map(project => project.title)
    .join(", ") || "No favorites yet";

  el.accountPanel.innerHTML = `
    <div class="account-row"><span>Name</span><strong>${escapeHtml(appState.user.name)}</strong></div>
    <div class="account-row"><span>Email</span><strong>${escapeHtml(appState.user.email)}</strong></div>
    <div class="account-row"><span>Ad-free credits</span><strong>${appState.credits}</strong></div>
    <div class="account-row"><span>Favorites</span><strong>${escapeHtml(favoriteTitles)}</strong></div>
    <button class="outline-button" id="refreshAccountButton"><i data-lucide="refresh-cw"></i> Refresh database state</button>
  `;

  document.querySelector("#refreshAccountButton").addEventListener("click", async () => {
    try {
      await refresh();
      toast("Database state refreshed.");
    } catch (error) {
      toast(error.message);
    }
  });
}

function renderLogin() {
  el.loginButton.innerHTML = appState.user
    ? `<i data-lucide="log-out"></i><span>Log out</span>`
    : `<i data-lucide="log-in"></i><span>Log in</span>`;
}

function requireLogin() {
  if (appState.user) return true;
  el.authDialog.showModal();
  toast("Log in to save downloads and uploads.");
  return false;
}

async function startDownload(projectId) {
  if (!requireLogin()) return;
  const project = appState.projects.find(item => item.id === projectId);
  if (!project) return;

  try {
    const response = await api("/api/downloads/start", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId })
    });

    if (response.requiresAd) {
      pendingAdToken = response.adToken;
      pendingDownloadProject = response.project;
      openAd(response.project, response.seconds);
      return;
    }

    applyBootstrap(response);
    await downloadManifest(project);
    toast(`${project.title} unlocked.`);
  } catch (error) {
    toast(error.message);
  }
}

function openAd(project, seconds = 5) {
  let count = seconds;
  clearInterval(countdownTimer);
  el.adTitle.textContent = `Unlock ${project.title}`;
  el.adCopy.textContent = "This sponsor view funds creators while keeping baseline projects free to access.";
  el.finishAdButton.disabled = true;
  el.finishAdButton.innerHTML = `Continue in <span id="adCountdown">${count}</span>s`;
  el.adDialog.showModal();

  countdownTimer = setInterval(() => {
    count -= 1;
    const countdown = document.querySelector("#adCountdown");
    if (countdown) countdown.textContent = count;
    if (count <= 0) {
      clearInterval(countdownTimer);
      el.finishAdButton.disabled = false;
      el.finishAdButton.textContent = "Download project";
    }
  }, 1000);
}

async function downloadManifest(project) {
  const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}/manifest`, {
    credentials: "same-origin"
  });
  if (!response.ok) throw new Error("Download file was not available.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const fileName = project.file.replace(".zip", "-manifest.txt");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

async function toggleFavorite(projectId) {
  if (!requireLogin()) return;
  try {
    const nextState = await api("/api/favorites/toggle", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId })
    });
    applyBootstrap(nextState);
  } catch (error) {
    toast(error.message);
  }
}

function toast(message) {
  el.toast.textContent = message;
  el.toast.classList.add("show");
  setTimeout(() => el.toast.classList.remove("show"), 2200);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

init();
