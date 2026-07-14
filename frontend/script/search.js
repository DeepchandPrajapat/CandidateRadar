const API_BASE = "https://candidateradar.onrender.com";

function setQuery(q) {
  document.getElementById("search-input").value = q;
  runSearch();
}

function showState(state) {
  ["loading", "empty", "error"].forEach(s => {
    document.getElementById(`state-${s}`).classList.add("hidden");
  });
  if (state) document.getElementById(`state-${state}`).classList.remove("hidden");
}


function escapeHtml(str) {
  if (!str) return "";
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function buildResumeLink(resumeUrl) {
  if (!resumeUrl) {
    return `<span class="font-mono text-xs text-[#5C5468]">No resume on file</span>`;
  }
  return `
    <a href="${resumeUrl}" target="_blank" rel="noopener noreferrer"
       class="font-mono text-xs text-[#E8551E] hover:underline inline-flex items-center gap-1.5">
      <i class="fa-solid fa-file-lines"></i> View original resume
    </a>
  `;
}

function buildCard(candidate, index) {
  const rank = candidate.rank || index + 1;
  const name = escapeHtml(candidate.name) || `Candidate ${candidate.id}`;
  const why = escapeHtml(candidate.why);
  const fit = escapeHtml(candidate.fit);
  const concerns = escapeHtml(candidate.concerns);
  const experience = escapeHtml(candidate.experience);

  const card = document.createElement("div");
  card.className = "candidate-card animate-in";
  card.style.animationDelay = `${index * 0.1}s`;

  card.innerHTML = `
    <div class="flex items-center gap-4 mb-4">
      <div class="rank-badge ${rank === 1 ? "rank-1" : ""}">0${rank}</div>
      <div class="flex-1">
        <h3 class="font-serif font-medium text-xl">${name}</h3>
      ${experience ? `<span class="font-mono text-xs text-[#5C5468]">${experience}</span>` : ""}
      </div>
    </div>

    <div class="reasoning">
      ${why ? `<strong>Why this rank:</strong> ${why}<br><br>` : ""}
      ${fit ? `<strong>Fit:</strong> ${fit}<br><br>` : ""}
      ${concerns ? `<strong>Concerns:</strong> ${concerns}` : ""}
    </div>

    <div class="mt-4">
      ${buildResumeLink(candidate.resume_url)}
    </div>
  `;

  return card;
}

async function runSearch() {
  const query = document.getElementById("search-input").value.trim();
  if (!query) return;

  const results = document.getElementById("results");
  results.innerHTML = "";
  showState("loading");

  try {
    const res = await fetch(`${API_BASE}/search/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_n: 3 }),
    });

    if (!res.ok) {
      throw new Error(`Server responded with ${res.status}`);
    }

    const data = await res.json();
    showState(null);

    if (!data.results || data.results.length === 0) {
      showState("empty");
      return;
    }

    data.results.forEach((candidate, index) => {
      results.appendChild(buildCard(candidate, index));
    });

  } catch (err) {
    showState("error");
    document.getElementById("error-msg").textContent = `Error: ${err.message}`;
  }
}