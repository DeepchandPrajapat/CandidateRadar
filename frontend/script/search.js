
  const API_BASE = "https://candidateradar.onrender.com;

  function setQuery(q) {
    document.getElementById("search-input").value = q;
    runSearch();
  }

  function showState(state) {
    ["loading","empty","error"].forEach(s => {
      document.getElementById(`state-${s}`).classList.add("hidden");
    });
    if (state) document.getElementById(`state-${state}`).classList.remove("hidden");
  }

  function parseRankingText(rankingText, candidates) {
    // split Gemini's ranking text by candidate separators
    const blocks = rankingText.split("---").map(b => b.trim()).filter(Boolean);
    return blocks;
  }

  async function runSearch() {
    const query = document.getElementById("search-input").value.trim();
    if (!query) return;

    const results = document.getElementById("results");
    results.innerHTML = "";
    showState("loading");

    try {
      const res  = await fetch(`${API_BASE}/search/`, {
        method : "POST",
        headers: { "Content-Type": "application/json" },
        body   : JSON.stringify({ query, top_n: 3 }),
      });
      const data = await res.json();

      showState(null);

      if (!data.results || data.results.length === 0) {
        showState("empty");
        return;
      }

      // parse Gemini ranking text into per-candidate blocks
      const rankingBlocks = parseRankingText(data.ranking, data.results);

      data.results.forEach((id, index) => {
        const block = rankingBlocks[index] || "";
        const rank  = index + 1;

        // extract name from first line of block
        const firstLine = block.split("\n")[0] || "";
        const name      = firstLine.replace(/Rank #\d+\s*[—-]\s*/i, "").trim() || `Candidate ${id}`;

        // everything after first line is reasoning
        const reasoning = block.split("\n").slice(1).join("\n").trim();

        const card = document.createElement("div");
        card.className = "candidate-card animate-in";
        card.style.animationDelay = `${index * 0.1}s`;
        card.innerHTML = `
          <div class="flex items-center gap-4 mb-4">
            <div class="rank-badge ${rank === 1 ? 'rank-1' : ''}">0${rank}</div>
            <div class="flex-1">
              <h3 class="font-serif font-medium text-xl">${name}</h3>
              <span class="font-mono text-xs text-[#5C5468]">Candidate ID: ${id}</span>
            </div>
          </div>
          ${reasoning ? `<div class="reasoning">${reasoning}</div>` : ""}
        `;
        results.appendChild(card);
      });

    } catch (err) {
      showState("error");
      document.getElementById("error-msg").textContent = `Error: ${err.message}`;
    }
  }
