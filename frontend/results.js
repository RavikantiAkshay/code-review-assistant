const severityFilter = document.getElementById("severityFilter");
const fileFilter = document.getElementById("fileFilter");
const categoryFilter = document.getElementById("categoryFilter");
const tableBody = document.getElementById("resultsTable");

const issues = [
  {
    file: "test.js",
    line: 10,
    category: "correctness",
    severity: "high",
    message: "Hooks must be called at the top level",
    rule: {
      id: "RH-01",
      link: "https://react.dev/reference/rules/rules-of-hooks"
    },
    source: "llm",
    impact: 4.5
  },
  {
    file: "test.js",
    line: 2,
    category: "readability",
    severity: "low",
    message: "Missing semicolon",
    rule: null,
    source: "static",
    impact: 0.7
  }
];

const files = [...new Set(issues.map(i => i.file))];
files.forEach(f => {
  const opt = document.createElement("option");
  opt.value = f;
  opt.textContent = f;
  fileFilter.appendChild(opt);
});

function renderTable(data) {
  tableBody.innerHTML = "";

  data.forEach(issue => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${issue.impact}</td>
      <td>${issue.severity}</td>
      <td>${issue.file}</td>
      <td>${issue.line}</td>
      <td>${issue.category}</td>
      <td>
        <details>
          <summary>${issue.message}</summary>
          ${issue.rule ? `
            <div>
              Rule: <a href="${issue.rule.link}" target="_blank">
                ${issue.rule.id}
              </a>
            </div>` : ""}
          <div>Source: ${issue.source}</div>
        </details>
      </td>
    `;

    tableBody.appendChild(row);
  });
}

function applyFilters() {
  let filtered = [...issues];

  if (severityFilter.value) {
    filtered = filtered.filter(i => i.severity === severityFilter.value);
  }

  if (fileFilter.value) {
    filtered = filtered.filter(i => i.file === fileFilter.value);
  }

  if (categoryFilter.value) {
    filtered = filtered.filter(i => i.category === categoryFilter.value);
  }

  renderTable(filtered);
}

severityFilter.addEventListener("change", applyFilters);
fileFilter.addEventListener("change", applyFilters);
categoryFilter.addEventListener("change", applyFilters);

renderTable(issues);
