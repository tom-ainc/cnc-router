// confirm.js: the To confirm tab, part of the page framework (core.js loads it first, always).
// Needs no data of its own: from systems.json it lists every requirement the user has not confirmed (implied by
// what the thing is for, or a limit the agent chose) grouped by topic, every assumption not yet confirmed, and the
// confirmed assumptions. The user marks each one confirmed or writes the change, and copies one reply to paste back
// into the chat; the agent records it with confirm() and by rewriting what changed. Marks are kept in this browser.
// Clicking a requirement shows it in 3D as the requirements tab does; an assumption lights the parts of the
// requirements it feeds. The block diagram's focus filters both.
(function () {
  const comp = { id: "confirm", tab: "To confirm", pane: "p-conf", after: "p-req" };
  Page.component(comp);
  Page.style(`
.cf-it { padding: 8px 14px; border-bottom: 1px solid var(--line); display: grid; grid-template-columns: 38px 1fr auto; gap: 2px 8px; align-items: start; }
.cf-it .id { font: 500 12px var(--font-mono); color: var(--muted); padding-top: 2px; }
.cf-it .why { grid-column: 2 / 4; font-size: 12px; color: var(--muted); }
.cf-it .bt { display: flex; gap: 4px; }
.cf-it button, .cf-bar button { font: inherit; font-size: 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; cursor: pointer; color: var(--ink); }
.cf-it button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.cf-it textarea { grid-column: 2 / 4; font: inherit; font-size: 12.5px; border: 1px solid var(--accent); border-radius: 6px; padding: 4px 6px; min-height: 34px; resize: vertical; }
.cf-it.ok { background: color-mix(in srgb, var(--pass) 8%, transparent); }
.cf-bar { position: sticky; top: 0; z-index: 2; background: var(--panel); border-bottom: 1px solid var(--line); padding: 8px 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px; color: var(--muted); }
.cf-out { margin: 10px 14px 16px; }
.cf-it { cursor: pointer; border-left: 3px solid transparent; }
.cf-it:hover { background: color-mix(in srgb, var(--accent-soft) 55%, transparent); }
.cf-it.sel { background: var(--accent-soft); border-left-color: var(--accent); }
.cf-it .chip { cursor: pointer; }
.cf-done summary { padding: 12px 14px 4px; font: 600 12px var(--font-display); text-transform: uppercase; letter-spacing: .06em; color: var(--muted); cursor: pointer; }
.cf-out textarea { width: 100%; box-sizing: border-box; min-height: 120px; font: 12px var(--font-mono); border: 1px solid var(--line); border-radius: 6px; padding: 6px; }
`);
  comp.init = function (P) {
    const { V, S, $, store, reqs, res, fmt } = P;
    const key = "confirm:" + (V.title || "page");
    let marks = {}; try { marks = JSON.parse(store.get(key, "{}")) || {}; } catch (e) { marks = {}; }
    const save = () => store.set(key, JSON.stringify(marks));
    let sel = null, openDone = false;
    const topicOf = {}; Object.entries(V.req_topics || {}).forEach(([t, ids]) => ids.forEach(id => { topicOf[id] = t; }));
    const SRC = { implied: "implied by what it is for", assumed: "a limit I chose" };
    const items = () => {
      const R = reqs.filter(r => r.source !== "stated" && (res[r.id] || {}).standing !== "validated" && (!P.focus || r.applies_to.some(n => n === "P" || P.inFocus(n))));
      const shown = P.asShown(), A = shown.filter(a => !a.confirmed), D = shown.filter(a => a.confirmed);
      const ask = new Set(V.ask || []);           // the batch asked now: shown first, by itself
      return { R: R.filter(r => !ask.has(r.id)), A: A.filter(a => !ask.has(a.id)), D,
               Q: [...R.filter(r => ask.has(r.id)), ...A.filter(a => ask.has(a.id))] };
    };
    const limitText = (r) => r.limit != null ? ` (limit ${{ max: "≤", min: "≥", equal: "=" }[r.kind] || ""} ${fmt(r.limit)} ${r.unit || ""})` : "";
    function reply() {
      const ok = Object.entries(marks).filter(([, m]) => m.ok).map(([id]) => id), ch = Object.entries(marks).filter(([, m]) => !m.ok && m.text);
      return (ok.length ? `Confirmed: ${ok.join(", ")}.\n` : "") + ch.map(([id, m]) => `${id}: ${m.text}`).join("\n");
    }
    const feeds = (a) => (a.affects || []).length ? ` · feeds ${(a.affects || []).map(id => P.reqChip(id)).join(" ")}` : "";
    function row(id, text, why, item, done) {
      const m = marks[id] || {};
      return `<div class="cf-it${m.ok ? " ok" : ""}" data-id="${id}" data-item="${item}"><div class="id">${id}</div><div>${text}</div>
        <div class="bt">${done ? `<span class="pill pass">confirmed</span>` : `<button type="button" data-a="ok" class="${m.ok ? "on" : ""}">Confirm</button><button type="button" data-a="ch" class="${m.text != null && !m.ok ? "on" : ""}">Change</button>`}</div>
        <div class="why">${why}</div>${m.text != null && !m.ok && !done ? `<textarea placeholder="What it should be">${m.text}</textarea>` : ""}</div>`;
    }
    function render() {
      const el = $("p-conf"), { R, A, D, Q } = items();
      const n = Object.values(marks).filter(m => m.ok || m.text).length;
      let h = `<div class="cf-bar"><span>${Q.length ? `${Q.length} asked now · ` : ""}${R.length + A.length} more wait on you · ${n} answered</span>
        <button type="button" id="cf-all">Confirm all shown</button><button type="button" id="cf-clear">Clear answers</button></div>`;
      if (Q.length) h += `<div class="section-h">Asked now</div>` + Q.map(q => q.applies_to ? row(q.id, q.text + limitText(q), SRC[q.source] || q.source, "req:" + q.id)
                                                                                     : row(q.id, q.text, (q.reason || "") + feeds(q), "as:" + q.id)).join("") +
        `<div class="section-h">Also waiting, when you have time</div>`;
      if (!R.length && !A.length && !Q.length) h += `<div class="empty">Nothing waiting: every requirement is stated or confirmed, and every assumption confirmed.</div>`;
      const by = {}; R.forEach(r => { (by[topicOf[r.id] || "Other"] ||= []).push(r); });
      for (const [t, rs] of Object.entries(by)) h += `<div class="section-h">${t}</div>` + rs.map(r => row(r.id, r.text + limitText(r), SRC[r.source] || r.source, "req:" + r.id)).join("");
      if (A.length) h += `<div class="section-h">Assumptions</div>` + A.map(a => row(a.id, a.text, (a.reason || "") + feeds(a), "as:" + a.id)).join("");
      if (D.length) h += `<details class="cf-done"${openDone ? " open" : ""}><summary>Confirmed assumptions (${D.length})</summary>` + D.map(a => row(a.id, a.text, (a.reason || "") + feeds(a), "as:" + a.id, true)).join("") + `</details>`;
      h += `<div class="section-h">Your reply</div><div class="cf-out"><textarea id="cf-reply" readonly>${reply()}</textarea><div class="cf-bar" style="position:static;border:0;padding:6px 0"><button type="button" id="cf-copy">Copy reply</button><span>Paste it into the chat; the next run records it.</span></div></div>`;
      el.innerHTML = h;
      P.markItems(); if (sel) el.querySelector(`.cf-it[data-id="${sel}"]`)?.classList.add("sel");
      el.querySelector(".cf-done")?.addEventListener("toggle", (e) => { openDone = e.target.open; });
      P.bindReqChips(el);
      el.querySelectorAll(".cf-it").forEach(d => {
        const id = d.dataset.id;
        // the row itself shows it in 3D: a requirement as the requirements tab does, an assumption by what it feeds
        d.addEventListener("click", (e) => {
          if (e.target.closest("button, textarea, [data-req]")) return;
          const [k] = d.dataset.item.split(":");
          if (k === "req") { if (sel === id) { sel = null; P.viewReq(null); P.applyFocusView(); } else { sel = id; P.viewReq(id); } P.markItems(); el.querySelectorAll(".cf-it").forEach(x => x.classList.toggle("sel", x.dataset.id === sel)); }
          else { sel = null; P.showItem("as", id); }
        });
        if (!d.querySelector('[data-a="ok"]')) return;
        d.querySelector('[data-a="ok"]').onclick = () => { marks[id] = marks[id] && marks[id].ok ? {} : { ok: true }; save(); render(); };
        d.querySelector('[data-a="ch"]').onclick = () => { marks[id] = marks[id] && marks[id].text != null && !marks[id].ok ? {} : { text: "" }; save(); render(); $("p-conf").querySelector(`.cf-it[data-id="${id}"] textarea`)?.focus(); };
        const ta = d.querySelector("textarea");
        if (ta) ta.oninput = () => { marks[id] = { text: ta.value }; save(); $("cf-reply").value = reply(); };
      });
      $("cf-all").onclick = () => { [...Q, ...R, ...A].forEach(q => { if (!marks[q.id] || !marks[q.id].text) marks[q.id] = { ok: true }; }); save(); render(); };
      $("cf-clear").onclick = () => { marks = {}; save(); render(); };
      $("cf-copy").onclick = () => { const t = $("cf-reply"); t.select(); try { navigator.clipboard.writeText(t.value); } catch (e) { document.execCommand("copy"); } $("cf-copy").textContent = "Copied"; setTimeout(() => { if ($("cf-copy")) $("cf-copy").textContent = "Copy reply"; }, 1500); };
    }
    Object.assign(comp, {
      render,
      filterLabel: () => { const q = items(); return `${q.Q.length + q.R.length + q.A.length} to confirm`; },
      exit() { if (sel) { sel = null; P.applyFocusView(); } },
    });
    P.on("focus", render);
  };
})();
