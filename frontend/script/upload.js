let selectedFiles = [];

function renderFileList() {
  const list = document.getElementById("file-list");
  list.innerHTML = "";
  selectedFiles.forEach((file, i) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.innerHTML = `
      <i class="fa-solid fa-file-lines text-[#E8551E]"></i>
      <span class="flex-1 truncate">${file.name}</span>
      <span class="text-[#5C5468] text-xs">${(file.size / 1024).toFixed(0)} KB</span>
      <span class="remove-btn" onclick="removeFile(${i})"><i class="fa-solid fa-xmark"></i></span>
    `;
    list.appendChild(pill);
  });
  document.getElementById("upload-btn").disabled = selectedFiles.length === 0;
}

function addFiles(newFiles) {
  const combined = [...selectedFiles, ...newFiles];
  const warning  = document.getElementById("limit-warning");
  if (combined.length > 5) {
    selectedFiles = combined.slice(0, 5);
    warning.classList.remove("hidden");
  } else {
    selectedFiles = combined;
    warning.classList.add("hidden");
  }
  renderFileList();
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  document.getElementById("limit-warning").classList.add("hidden");
  renderFileList();
}

function handleFileSelect(e) { addFiles(Array.from(e.target.files)); }
function handleDragOver(e)   { e.preventDefault(); document.getElementById("drop-zone").classList.add("dragover"); }
function handleDragLeave(e)  { document.getElementById("drop-zone").classList.remove("dragover"); }
function handleDrop(e) {
  e.preventDefault();
  document.getElementById("drop-zone").classList.remove("dragover");
  addFiles(Array.from(e.dataTransfer.files).filter(f => f.name.endsWith(".pdf") || f.name.endsWith(".docx")));
}

async function uploadFiles() {
  const btn     = document.getElementById("upload-btn");
  const results = document.getElementById("results");
  results.innerHTML = "";
  btn.disabled    = true;
  btn.textContent = "Uploading…";

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append("files", f));

  try {
    // calls Netlify proxy — API key is hidden server-side
    const res = await fetch(`https://candidateradar.onrender.com/resume/upload`, {
        method: "POST",
        headers: { "x-api-key": "candidateradar_secret_2026" },
        body  : formData,
    });
    const data = await res.json();

    data.details.forEach(d => {
      const card = document.createElement("div");
      if (d.status === "success") {
        card.className = "result-card result-success";
        card.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>${d.file} — indexed successfully (id: ${d.id})</span>`;
      } else if (d.status === "duplicate") {
        card.className = "result-card result-duplicate";
        card.innerHTML = `<i class="fa-solid fa-clone"></i><span>${d.file} — already in database, skipped</span>`;
      } else {
        card.className = "result-card result-failed";
        card.innerHTML = `<i class="fa-solid fa-circle-xmark"></i><span>${d.file} — failed: ${d.error}</span>`;
      }
      results.appendChild(card);
    });

    selectedFiles = [];
    renderFileList();

  } catch (err) {
    const card = document.createElement("div");
    card.className = "result-card result-failed";
    card.innerHTML = `<i class="fa-solid fa-circle-xmark"></i><span>Network error: ${err.message}</span>`;
    results.appendChild(card);
  }

  btn.textContent = "Upload resumes";
  btn.disabled    = selectedFiles.length === 0;
}