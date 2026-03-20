/**
 * resume-loader.js
 *
 * Fetches resume.json and populates [data-resume="..."] elements.
 * Falls back silently to hardcoded HTML if resume.json is missing or fails.
 * Only overwrites a section when the JSON has data for it.
 *
 * JSON shape (produced by parse_resume.py + resume_static.json):
 *
 *   name          string
 *   tagline       string
 *   skills        { category: [items] }
 *   certifications [{ label, url }]
 *   education     [{ institution, degree, location, date, gpa, coursework }]
 *   experience    [{ role, company, location, date, bullets[] }]
 *   projects      [{ title, technologies, description, link, linkLabel, bullets[]? }]
 *   patents       [{ title, technologies, number, filed, bullets[], link?, linkLabel? }]
 */

async function loadResume() {
    let data;
    try {
        const res = await fetch("resume.json");
        if (!res.ok) return;       // file not yet generated — keep hardcoded HTML
        data = await res.json();
    } catch {
        return;                    // network / JSON parse error — keep hardcoded HTML
    }

    // ── Helpers ────────────────────────────────────────────────────────────
    const esc = (str = "") =>
        String(str).replace(/[&<>"']/g, c =>
            ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
        );

    // Replace innerHTML only when html is non-null (lets us skip sections with no data)
    const fill = (key, html) => {
        if (html == null) return;
        document.querySelectorAll(`[data-resume="${key}"]`).forEach(el => {
            el.innerHTML = html;
        });
    };

    const setText = (key, text) => {
        if (!text) return;
        document.querySelectorAll(`[data-resume="${key}"]`).forEach(el => {
            el.textContent = text;
        });
    };

    // Renders description string + optional bullets[] into HTML.
    // If bullets exist they are shown as a <ul>; description sits above as <p>.
    const descAndBullets = (description, bullets) => {
        const d = description ? `<p>${esc(description)}</p>` : "";
        const b = Array.isArray(bullets) && bullets.length
            ? `<ul>${bullets.map(b => `<li>${esc(b)}</li>`).join("")}</ul>`
            : "";
        return d + b;
    };

    // ── Name & tagline ─────────────────────────────────────────────────────
    setText("name",    data.name);
    setText("tagline", data.tagline);

    // ── Skills ─────────────────────────────────────────────────────────────
    // Renders one .skill-box per category.
    // Drops the bare "Certificate" key from the PDF (replaced by certifications below).
    if (data.skills && Object.keys(data.skills).length) {
        const boxes = Object.entries(data.skills)
            .filter(([cat]) => cat.toLowerCase() !== "certificate")
            .map(([cat, items]) => `
            <div class="skill-box">
                <h3>${esc(cat)}</h3>
                <ul>
                    ${items.map(item => `<li>${esc(item)}</li>`).join("")}
                </ul>
            </div>`);

        // Certifications box — clickable badge links from resume_static.json
        const certs = data.certifications;
        if (Array.isArray(certs) && certs.length) {
            const certItems = certs.map(cert =>
                cert.url
                    ? `<li><a href="${esc(cert.url)}" target="_blank" rel="noopener noreferrer">${esc(cert.label)}</a></li>`
                    : `<li>${esc(cert.label)}</li>`
            ).join("");
            boxes.push(`
            <div class="skill-box">
                <h3>Certifications</h3>
                <ul>${certItems}</ul>
            </div>`);
        }

        fill("skills", boxes.join(""));
    }

    // ── Education ─────────────────────────────────────────────────────────
    if (Array.isArray(data.education) && data.education.length) {
        const html = data.education.map(edu => {
            const locationDate = [edu.location, edu.date].filter(Boolean).join(" | ");
            return `
            <div class="education-item">
                <div class="education-content">
                    <h3>${esc(edu.institution)}</h3>
                    ${edu.degree     ? `<p><strong>${esc(edu.degree)}</strong></p>`                            : ""}
                    ${locationDate   ? `<p>${esc(locationDate)}</p>`                                           : ""}
                    ${edu.gpa        ? `<p>CGPA: ${esc(edu.gpa)}</p>`                                          : ""}
                    ${edu.coursework ? `<p><strong>Relevant Coursework:</strong> ${esc(edu.coursework)}</p>`   : ""}
                </div>
            </div>`;
        }).join("");
        fill("education", html);
    }

    // ── Experience ────────────────────────────────────────────────────────
    if (Array.isArray(data.experience) && data.experience.length) {
        const html = data.experience.map(job => {
            const title        = (job.role && job.company)
                ? `${esc(job.role)} @ ${esc(job.company)}`
                : esc(job.company || job.role || "");
            const locationDate = [job.location, job.date].filter(Boolean).join(" | ");
            const bullets      = (job.bullets || []).map(b => `<li>${esc(b)}</li>`).join("");
            return `
            <div class="experience-item">
                <h3>${title}</h3>
                ${locationDate ? `<p>${esc(locationDate)}</p>` : ""}
                ${bullets      ? `<ul>${bullets}</ul>`          : ""}
            </div>`;
        }).join("");
        fill("experience", html);
    }

    // ── Projects ──────────────────────────────────────────────────────────
    // projects[] may contain entries from the "Research & Projects" section.
    // Some entries (IEEE papers) use bullets[] instead of a description string —
    // descAndBullets() handles both shapes.
    if (Array.isArray(data.projects) && data.projects.length) {
        const html = data.projects.map(proj => {
            const linkHTML = proj.link
                ? `<p><a href="${esc(proj.link)}" target="_blank">${esc(proj.linkLabel || "View")}</a></p>`
                : "";
            return `
            <div class="project-item">
                <h3>${esc(proj.title)}</h3>
                ${proj.technologies ? `<p><strong>Technologies Used:</strong> ${esc(proj.technologies)}</p>` : ""}
                ${descAndBullets(proj.description, proj.bullets)}
                ${linkHTML}
            </div>`;
        }).join("");
        fill("projects", html);
    }

    // ── Patents ───────────────────────────────────────────────────────────
    if (Array.isArray(data.patents) && data.patents.length) {
        const html = data.patents.map(pat => {
            const bullets  = (pat.bullets || []).map(b => `<li>${esc(b)}</li>`).join("");
            const linkHTML = pat.link
                ? `<p><a href="${esc(pat.link)}" target="_blank">${esc(pat.linkLabel || "View")}</a></p>`
                : "";
            return `
            <div class="patent-item">
                <h3>${esc(pat.title)}</h3>
                ${pat.number ? `<p><strong>Patent Number:</strong> ${esc(pat.number)}</p>` : ""}
                ${pat.filed  ? `<p><strong>Filed on:</strong> ${esc(pat.filed)}</p>`       : ""}
                ${bullets    ? `<ul>${bullets}</ul>`                                        : ""}
                ${linkHTML}
            </div>`;
        }).join("");
        fill("patents", html);
    }
}

document.addEventListener("DOMContentLoaded", loadResume);