// confirm.js: the To confirm tab of the requirements-elicitation skill, a component of the page framework (core.js).
// Needs no data of its own: from systems.json it lists every requirement the user has not confirmed (implied by
// what the thing is for, or a limit the agent chose) and every assumption not yet confirmed, grouped by topic. The
// user marks each one confirmed or writes the change, and copies one reply to paste back into the chat; the agent
// records it with confirm() and by rewriting what changed. Marks are kept in this browser only.
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
.cf-out textarea { width: 100%; box-sizing: border-box; min-height: 120px; font: 12px var(--font-mono); border: 1px solid var(--line); border-radius: 6px; padding: 6px; }
`);
  comp.init = function (P) {
    const { V, S, $, store, reqs, res, fmt } = P;
    const key = "confirm:" + (V.title || "page");
    let marks = {}; try { marks = JSON.parse(store.get(key, "{}")) || {}; } catch (e) { marks = {}; }
    const save = () => store.set(key, JSON.stringify(marks));
    const topicOf = {}; Object.entries(V.req_topics || {}).forEach(([t, ids]) => ids.forEach(id => { topicOf[id] = t; }));
    const SRC = { implied: "implied by what it is for", assumed: "a limit I chose" };
    const items = () => {
      const R = reqs.filter(r => r.source !== "stated" && (res[r.id] || {}).standing !== "validated" && (!P.focus || r.applies_to.some(n => n === "P" || P.inFocus(n))));
      const A = S.assumptions.filter(a => !a.confirmed);
      return { R, A };
    };
    const limitText = (r) => r.limit != null ? ` (limit ${{ max: "≤", min: "≥", equal: "=" }[r.kind] || ""} ${fmt(r.limit)} ${r.unit || ""})` : "";
    function reply() {
      const ok = Object.entries(marks).filter(([, m]) => m.ok).map(([id]) => id), ch = Object.entries(marks).filter(([, m]) => !m.ok && m.text);
      return (ok.length ? `Confirmed: ${ok.join(", ")}.\n` : "") + ch.map(([id, m]) => `${id}: ${m.text}`).join("\n");
    }
    function row(id, text, why) {
      const m = marks[id] || {};
      return `<div class="cf-it${m.ok ? " ok" : ""}" data-id="${id}"><div class="id">${id}</div><div>${text}</div>
        <div class="bt"><button type="button" data-a="ok" class="${m.ok ? "on" : ""}">Confirm</button><button type="button" data-a="ch" class="${m.text != null && !m.ok ? "on" : ""}">Change</button></div>
        <div class="why">${why}</div>${m.text != null && !m.ok ? `<textarea placeholder="What it should be">${m.text}</textarea>` : ""}</div>`;
    }
    function render() {
      const el = $("p-conf"), { R, A } = items();
      const n = Object.values(marks).filter(m => m.ok || m.text).length;
      let h = `<div class="cf-bar"><span>${R.length} requirements and ${A.length} assumptions wait on you · ${n} answered</span>
        <button type="button" id="cf-all">Confirm all shown</button><button type="button" id="cf-clear">Clear answers</button></div>`;
      if (!R.length && !A.length) h += `<div class="empty">Nothing waiting: every requirement is stated or confirmed, and every assumption confirmed.</div>`;
      const by = {}; R.forEach(r => { (by[topicOf[r.id] || "Other"] ||= []).push(r); });
      for (const [t, rs] of Object.entries(by)) h += `<div class="section-h">${t}</div>` + rs.map(r => row(r.id, r.text + limitText(r), SRC[r.source] || r.source)).join("");
      if (A.length) h += `<div class="section-h">Assumptions</div>` + A.map(a => row(a.id, a.text, a.reason || "")).join("");
      h += `<div class="section-h">Your reply</div><div class="cf-out"><textarea id="cf-reply" readonly>${reply()}</textarea><div class="cf-bar" style="position:static;border:0;padding:6px 0"><button type="button" id="cf-copy">Copy reply</button><span>Paste it into the chat; the next run records it.</span></div></div>`;
      el.innerHTML = h;
      el.querySelectorAll(".cf-it").forEach(d => {
        const id = d.dataset.id;
        d.querySelector('[data-a="ok"]').onclick = () => { marks[id] = marks[id] && marks[id].ok ? {} : { ok: true }; save(); render(); };
        d.querySelector('[data-a="ch"]').onclick = () => { marks[id] = marks[id] && marks[id].text != null && !marks[id].ok ? {} : { text: "" }; save(); render(); d.querySelector("textarea")?.focus(); };
        const ta = d.querySelector("textarea");
        if (ta) ta.oninput = () => { marks[id] = { text: ta.value }; save(); $("cf-reply").value = reply(); };
      });
      $("cf-all").onclick = () => { R.forEach(r => { if (!marks[r.id] || !marks[r.id].text) marks[r.id] = { ok: true }; }); A.forEach(a => { if (!marks[a.id] || !marks[a.id].text) marks[a.id] = { ok: true }; }); save(); render(); };
      $("cf-clear").onclick = () => { marks = {}; save(); render(); };
      $("cf-copy").onclick = () => { const t = $("cf-reply"); t.select(); try { navigator.clipboard.writeText(t.value); } catch (e) { document.execCommand("copy"); } $("cf-copy").textContent = "Copied"; setTimeout(() => { if ($("cf-copy")) $("cf-copy").textContent = "Copy reply"; }, 1500); };
    }
    Object.assign(comp, {
      render,
      filterLabel: () => `${items().R.length} requirements to confirm`,
    });
    P.on("focus", render);
  };
})();
