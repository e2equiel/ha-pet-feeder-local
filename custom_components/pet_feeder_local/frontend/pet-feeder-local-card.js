/** Local feeder controls. Editing a number never triggers a feeding command. */
class PetFeederLocalCard extends HTMLElement {
  setConfig(config) {
    const entries = config.schedule_entities || [config.schedule_entity];
    if (!Array.isArray(entries) || !entries.length || entries.some(id => typeof id !== "string" || !id.startsWith("sensor."))) {
      throw new Error("Select at least one Pet Feeder Local schedule sensor");
    }
    this.scheduleEntities = [...new Set(entries)];
    this.baseConfig = {...config};
    this.config = {...config, schedule_entity:this.scheduleEntities.includes(config.schedule_entity) ? config.schedule_entity : this.scheduleEntities[0]};
    this.dirty = false; this.busy = false; this.drafts = new Map(); this.timeDrafts = new WeakMap();
    this.revision = undefined; this.meals = undefined;
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    this.shadowRoot.replaceChildren();
  }

  feederName(id) {
    const name = this._hass.states[id]?.attributes.friendly_name || id;
    return this.scheduleEntities.some(other => other !== id && this._hass.states[other]?.attributes.friendly_name === name)
      ? `${name} (${id})` : name;
  }
  available(id) { return !!this._hass.states[id] && !["unavailable","unknown"].includes(this._hass.states[id].state); }
  rememberDraft() {
    if (this.meals) this.drafts.set(this.config.schedule_entity, {meals:this.meals, revision:this.revision, dirty:this.dirty, timeDrafts:this.timeDrafts});
  }
  selectFeeder(id) {
    if (this.busy || !this.scheduleEntities.includes(id) || id === this.config.schedule_entity) return;
    this.rememberDraft(); this.config = {...this.config, schedule_entity:id};
    const draft = this.drafts.get(id);
    if (draft) { Object.assign(this,draft); this.render(); }
    else this.load();
    this.hass = this._hass;
  }
  updateCopyControls() {
    const root = this.shadowRoot;
    root.querySelectorAll(".copy-target").forEach(input => input.disabled = this.busy || !this.available(input.value));
    const button = root.querySelector("#copy-schedule");
    if (button) button.disabled = this.busy || !this.available(this.config.schedule_entity) || ![...root.querySelectorAll(".copy-target:checked")].some(input => !input.disabled);
  }
  copySchedule() {
    const root = this.shadowRoot;
    for (const input of root.querySelectorAll("#meals input")) if (!input.reportValidity()) return;
    const ids = [...root.querySelectorAll(".copy-target:checked")].map(input => input.value);
    if (!ids.length || this.busy || !this.available(this.config.schedule_entity)) return;
    let targets;
    try {
      const seen = new Set([this._hass.states[this.config.schedule_entity]?.attributes.config_entry_id]);
      targets = ids.map(id => {
        if (!this.scheduleEntities.includes(id) || !this.available(id)) throw new Error("A selected feeder is unavailable. No schedule was copied");
        if (this.drafts.get(id)?.dirty) throw new Error(`${this.feederName(id)} has unsaved edits. Save or reload them before copying`);
        const a = this._hass.states[id].attributes;
        if (a.integration !== "pet_feeder_local" || !a.config_entry_id || typeof a.revision !== "string" || seen.has(a.config_entry_id)) {
          throw new Error("Select distinct Pet Feeder Local devices with current schedules. No schedule was copied");
        }
        seen.add(a.config_entry_id); return {id, entry:a.config_entry_id, revision:a.revision};
      });
    } catch (error) { root.querySelector("#message").textContent=error.message; return; }
    const enabled = this.meals.filter(meal => meal.enabled).length;
    if (!confirm(`Replace the schedules on ${targets.map(t => this.feederName(t.id)).join(", ")} with ${this.meals.length} meals (${enabled} enabled)? Each feeder is updated separately. This does not save unsaved edits on the source feeder.`)) return;
    const meals = this.meals.map(meal => ({...meal}));
    return this.action(async () => {
      const results = root.querySelector("#copy-results"); results.replaceChildren();
      for (const target of targets) {
        let outcome;
        try {
          await this._hass.callService("pet_feeder_local","set_schedule",{config_entry_id:target.entry,expected_revision:target.revision,meals:meals.map(meal=>({...meal}))});
          this.drafts.delete(target.id); outcome="Saved";
        } catch (error) { outcome=`Not confirmed: ${error.message || String(error)}`; }
        results.append(this.element("li",`${this.feederName(target.id)}: ${outcome}`));
      }
      root.querySelectorAll(".copy-target").forEach(input=>input.checked=false);
    }, "Copy finished. Review each result; failed or uncertain writes are not repeated automatically");
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this.config.schedule_entity];
    const links = state?.attributes || {};
    this.config = {...this.config,
      portions_entity:(this.scheduleEntities.length === 1 && this.baseConfig.portions_entity) || links.portions_entity,
      serve_entity:(this.scheduleEntities.length === 1 && this.baseConfig.serve_entity) || links.serve_entity};
    if (!this.available(this.config.schedule_entity)) {
      if (!this.shadowRoot.querySelector("#portions")) this.load();
      const message = this.shadowRoot.querySelector("#availability");
      if (message) { message.hidden=false; message.textContent="Feeder unavailable. Check power and the integration connection."; }
      this.shadowRoot.querySelectorAll("button,input").forEach(node=>node.disabled=true);
      const picker = this.shadowRoot.querySelector("#feeder-select"); if (picker) picker.disabled = this.busy;
      this.updateCopyControls(); return;
    }
    if (!this.config.portions_entity || !this.config.serve_entity) {
      if (!this.shadowRoot.querySelector("#portions")) this.shadowRoot.innerHTML = '<ha-card style="padding:24px">Waiting for feeder controls. This can take 30 seconds after setup.</ha-card>';
      return;
    }
    if (!this.shadowRoot.querySelector("#portions") || (!this.dirty && !this.busy &&
        this.revision !== state.attributes.revision)) this.load();
    const availability = this.shadowRoot.querySelector("#availability");
    if (availability) availability.hidden = true;
    const input = this.shadowRoot.querySelector("#portions");
    if (input && this.shadowRoot.activeElement !== input && !this.busy) {
      input.value = hass.states[this.config.portions_entity]?.state || "1";
    }
    this.shadowRoot.querySelectorAll("button,input,select").forEach(node => node.disabled = this.busy);
    const serve = this.shadowRoot.querySelector("#serve");
    if (serve) serve.disabled = this.busy || !input.checkValidity() ||
      ["unavailable", undefined].includes(hass.states[this.config.serve_entity]?.state);
    const add = this.shadowRoot.querySelector("#add");
    if (add) add.disabled = this.busy || this.meals.length >= 8;
    const conflict = this.shadowRoot.querySelector("#conflict");
    if (conflict) conflict.hidden = !this.dirty || this.revision === state.attributes.revision;
    this.updateCopyControls();
  }

  load() {
    const state = this._hass.states[this.config.schedule_entity];
    this.revision = state?.attributes.revision;
    this.meals = (state?.attributes.meals || []).map(meal => ({ ...meal }));
    this.timeDrafts = new WeakMap();
    this.drafts.delete(this.config.schedule_entity);
    this.dirty = false;
    this.render();
  }

  element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  changed() {
    this.dirty = true;
    this.rememberDraft();
    this.updateSummary();
  }

  updateSummary() {
    const summary = this.shadowRoot.querySelector("#schedule-summary");
    if (!summary) return;
    const enabled = this.meals.filter(meal => meal.enabled).length;
    const total = this.meals.length;
    summary.textContent = `${enabled} enabled · ${total} ${total === 1 ? "meal" : "meals"}${this.dirty ? " · Unsaved changes" : ""}`;
  }

  async action(callback, success) {
    if (this.busy) return;
    this.busy = true;
    this.shadowRoot.querySelectorAll("button,input,select").forEach(node => node.disabled = true);
    const message = this.shadowRoot.querySelector("#message");
    message.textContent = "Working…";
    try {
      await callback();
      message.textContent = success;
    } catch (error) {
      message.textContent = error.message || String(error);
    } finally {
      this.busy = false;
      this.hass = this._hass;
    }
  }

  render() {
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;container-type:inline-size;--pfl-line:var(--divider-color,rgba(127,127,127,.24));--pfl-muted:var(--secondary-text-color,#656d6b);--pfl-raised:var(--secondary-background-color,var(--card-background-color));color:var(--primary-text-color)}
      *{box-sizing:border-box}ha-card{display:block;overflow:hidden}h2,h3,p{margin:0}h2{font-size:20px;font-weight:600;line-height:1.3}h3{font-size:17px;font-weight:600;line-height:1.4}
      .header{display:flex;align-items:center;gap:12px;padding:20px 24px;border-bottom:1px solid var(--pfl-line)}.brand-mark{width:40px;height:40px;flex:none}.subtitle,.summary,.help{font-size:13px;line-height:1.5;color:var(--pfl-muted)}.subtitle{margin-top:2px}
      .content{padding:24px;display:grid;gap:28px}.section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}.summary{font-variant-numeric:tabular-nums}.manual{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-top:16px}
      label.field{display:grid;min-width:0;gap:4px;font-size:13px;font-weight:500}.manual .field{width:112px}input,button{font:inherit;color:var(--primary-text-color);border:1px solid var(--pfl-line);border-radius:8px;background:var(--card-background-color);min-height:44px;padding:8px 12px}input[type=number]{width:100%;font-variant-numeric:tabular-nums}input[type=time]{width:100%;font-variant-numeric:tabular-nums}
      button{cursor:pointer;font-weight:500}button:hover:not(:disabled){background:var(--pfl-raised)}button:disabled,input:disabled{opacity:.5;cursor:default}.primary{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}.primary:hover:not(:disabled){background:var(--primary-color);filter:brightness(.94)}
      button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}.schedule{border-top:1px solid var(--pfl-line);padding-top:20px}.meals{display:grid;gap:8px;margin-top:12px}.meal{border:1px solid var(--pfl-line);border-radius:12px;padding:12px}.meal-head{display:grid;grid-template-columns:minmax(72px,.8fr) minmax(110px,1.3fr) minmax(70px,.8fr) 44px;align-items:end;gap:8px}.enabled{display:inline-flex;align-items:center;gap:8px;font-weight:600;min-height:44px}.enabled input{width:18px;height:18px;min-height:0;margin:0;padding:0;accent-color:var(--primary-color)}
      .meal-title{min-width:0;display:flex;align-items:center}.meal-title strong{font-size:15px;font-weight:600}.enabled{font-size:13px;font-weight:500;color:var(--primary-text-color);white-space:nowrap}.remove{display:grid;place-items:center;width:44px;padding:0;background:transparent;border-color:transparent;color:var(--pfl-muted)}.remove svg{width:18px;height:18px}.fields{display:contents}.fields input{min-width:0}.days{padding:0;border:0;margin:8px 0 0;min-width:0}.day-list{display:flex;flex-wrap:wrap;width:100%;gap:4px}.day{position:relative;display:inline-flex;flex:1 0 44px;align-items:center;justify-content:center;min-width:44px;min-height:44px;border:1px solid var(--pfl-line);border-radius:8px;color:var(--pfl-muted);font-size:13px;cursor:pointer}.day input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}.day:has(input:checked)::before{content:"✓";margin-right:4px;font-weight:600}.day:has(input:checked){background:var(--pfl-raised);border-color:var(--primary-color);color:var(--primary-text-color)}.day:has(input:focus-visible){outline:2px solid var(--primary-color);outline-offset:2px}
      .actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.help{margin-top:16px}.notice{border-left:3px solid var(--warning-color,var(--primary-color));padding:8px 12px;line-height:1.5;overflow-wrap:anywhere}.notice[hidden]{display:none}#message{font-size:13px;line-height:1.5;color:var(--pfl-muted);overflow-wrap:anywhere}#message:empty{display:none}
      select{font:inherit;color:var(--primary-text-color);background:var(--card-background-color);min-height:44px;border:1px solid var(--pfl-line);border-radius:8px;padding:8px 12px;width:100%;max-width:100%}select:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}.copy-panel{margin-top:16px;border-top:1px solid var(--pfl-line);padding-top:16px}.copy-panel summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-size:14px;font-weight:500}.copy-list{display:grid;gap:4px;margin:8px 0;padding:0;border:0}.copy-choice{display:flex;align-items:center;gap:8px;min-height:44px;font-size:13px}.copy-choice input{min-height:0;width:18px;height:18px;accent-color:var(--primary-color)}#copy-results{font-size:13px;line-height:1.5;padding-left:20px;overflow-wrap:anywhere}#feeder-picker[hidden],.copy-panel[hidden]{display:none}
      @container(max-width:430px){.meal-head{grid-template-columns:minmax(0,1fr) minmax(72px,.65fr) 44px}.meal-title{grid-column:1/3}.remove{grid-column:3;grid-row:1}.fields>.field:first-child{grid-column:1}.fields>.field:last-child{grid-column:2/4}}
      @media(max-width:430px){.header{padding:16px}.content{padding:16px;gap:24px}}
    </style><ha-card>
      <header class="header"><svg class="brand-mark" viewBox="0 0 512 512" aria-hidden="true">
  <defs>
    <linearGradient id="house" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#298f80"/><stop offset="1" stop-color="#21796f"/></linearGradient>
    <linearGradient id="bowl" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#88dfb9"/><stop offset="1" stop-color="#4bb18e"/></linearGradient>
  </defs>
  <path d="M58 228 236 76a31 31 0 0 1 40 0l178 152" fill="none" stroke="url(#house)" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M108 227v170c0 26 21 47 47 47h202c26 0 47-21 47-47V227" fill="none" stroke="url(#house)" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="166" y="175" width="180" height="192" rx="43" fill="#237b6e"/>
  <path d="M201 197h110" stroke="#a8e9cd" stroke-width="10" stroke-linecap="round"/>
  <circle cx="256" cy="260" r="39" fill="#dcf5e7"/>
  <circle cx="256" cy="260" r="25" fill="#124a46"/>
  <circle cx="265" cy="251" r="7" fill="#85dbb7"/>
  <path d="M223 328h66v37h-66z" fill="#124a46"/>
  <path d="M147 363h218l-17 52a31 31 0 0 1-30 21H194a31 31 0 0 1-30-21z" fill="url(#bowl)"/>
  <path d="M145 363h222" stroke="#ddf9e8" stroke-width="14" stroke-linecap="round"/>
  <circle cx="380" cy="136" r="15" fill="#f5b961"/>
</svg><div><h2>Pet Feeder Local</h2><p class="subtitle">Local feeding controls</p></div></header>
      <div class="content"><p id="availability" class="notice" role="status" hidden></p><label class="field" id="feeder-picker" hidden>Feeder<select id="feeder-select"></select></label>
      <section aria-labelledby="serve-title"><h3 id="serve-title">Serve now</h3><div class="manual"><label class="field">Portions<input id="portions" type="number" min="1" max="10" step="1" value="1" required aria-describedby="portion-help"></label><button id="serve" class="primary">Serve</button></div><p id="portion-help" class="help">Choose 1–10 portions, then select Serve</p></section>
      <section class="schedule" aria-labelledby="schedule-title"><div class="section-heading"><h3 id="schedule-title">Feeding schedule</h3><span id="schedule-summary" class="summary"></span></div><div id="meals" class="meals"></div>
      <div class="actions"><button id="add">Add meal</button><button id="save" class="primary">Save schedule</button><button id="reload">Reload</button></div>
      <p class="help">The feeder runs saved meals itself. Home Assistant does not need to stay online.</p>
      <p id="conflict" class="notice" role="status" hidden>The device schedule changed. Reload before saving.</p><details class="copy-panel" id="copy-panel" hidden><summary>Copy schedule to feeders</summary><p class="help">Replace selected feeders’ schedules with the displayed meals. Save this feeder separately if it has unsaved edits. Each feeder is updated individually.</p><fieldset class="copy-list" id="copy-list" aria-label="Feeders receiving the displayed schedule"></fieldset><button id="copy-schedule" disabled>Copy schedule</button><ul id="copy-results" role="status" aria-live="polite"></ul></details></section>
      <p id="message" role="status" aria-live="polite"></p></div></ha-card>`;
    const root = this.shadowRoot;
    if (this.scheduleEntities.length > 1) {
      root.querySelector("#feeder-picker").hidden=false; root.querySelector("#copy-panel").hidden=false;
      const select=root.querySelector("#feeder-select");
      for (const id of this.scheduleEntities) {
        const option=this.element("option",this.feederName(id)); option.value=id;select.append(option);
        if (id !== this.config.schedule_entity) {
          const label=this.element("label",this.feederName(id),"copy-choice");
          const check=this.element("input",undefined,"copy-target");check.type="checkbox";check.value=id;check.onchange=()=>this.updateCopyControls();
          label.prepend(check);root.querySelector("#copy-list").append(label);
        }
      }
      select.value=this.config.schedule_entity;select.onchange=()=>this.selectFeeder(select.value);
      root.querySelector("#portion-help").textContent=`Choose 1–10 portions for ${this.feederName(this.config.schedule_entity)}, then select Serve`;
      root.querySelector("#copy-schedule").onclick=()=>this.copySchedule();
    }
    root.querySelector("#portions").value = this._hass.states[this.config.portions_entity]?.state || "1";
    root.querySelector("#portions").oninput = () => {
      root.querySelector("#serve").disabled = !root.querySelector("#portions").checkValidity() || this.busy ||
        ["unavailable", undefined].includes(this._hass.states[this.config.serve_entity]?.state);
    };
    root.querySelector("#portions").onchange = event => {
      const value = Number(event.target.value);
      if (!Number.isInteger(value) || value < 1 || value > 10) {
        event.target.reportValidity(); return;
      }
      this.action(() => this._hass.callService("number", "set_value", {
        entity_id: this.config.portions_entity, value,
      }), "Portion selection sent to Home Assistant");
    };
    root.querySelector("#serve").onclick = () => {
      if (!root.querySelector("#portions").reportValidity()) return;
      this.action(() => this._hass.callService("button", "press", { entity_id: this.config.serve_entity }),
      "Serve request sent to Home Assistant");
    };
    root.querySelector("#reload").onclick = () => {
      if (this.dirty && !confirm("Discard unsaved schedule changes and reload?")) return;
      this.load();
    };
    root.querySelector("#add").onclick = () => {
      if (this.meals.length >= 8) return;
      this.meals.push({weekdays:127,hour:12,minute:0,portions:1,enabled:false});
      this.changed(); this.render();
    };
    root.querySelector("#save").onclick = () => {
      for (const input of root.querySelectorAll("#meals input")) {
        if (!input.checkValidity()) { input.reportValidity(); return; }
      }
      this.action(async () => {
        await this._hass.callService("pet_feeder_local", "set_schedule", {
          config_entry_id: this._hass.states[this.config.schedule_entity].attributes.config_entry_id,
          expected_revision: this.revision, meals: this.meals.map(meal => ({ ...meal })),
        });
        this.dirty = false;
        this.updateSummary();
      }, "Schedule request sent to Home Assistant");
    };
    this.meals.forEach((meal, index) => {
      const row = this.element("div", undefined, "meal");
      const head = this.element("div", undefined, "meal-head");
      const enabled = this.element("input"); enabled.type = "checkbox"; enabled.checked = meal.enabled;
      enabled.onchange = () => { meal.enabled = enabled.checked; this.changed(); };
      enabled.setAttribute("aria-label", `Meal ${index + 1} enabled`);
      const label = this.element("label", `Meal ${index + 1}`, "enabled"); label.prepend(enabled);
      const heading = this.element("div", undefined, "meal-title"); heading.append(label); head.append(heading);
      const remove = this.element("button", undefined, "remove");
      remove.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
      remove.setAttribute("aria-label", `Remove meal ${index + 1}`);
      remove.onclick = () => { this.meals.splice(index,1); this.changed(); this.render(); };
      head.append(remove); row.append(head);
      const fields = this.element("div", undefined, "fields");
      const time = this.element("input"); time.type = "time"; time.required = true;
      time.value = this.timeDrafts.has(meal) ? this.timeDrafts.get(meal) : `${String(meal.hour).padStart(2,"0")}:${String(meal.minute).padStart(2,"0")}`;
      time.setAttribute("aria-label", `Meal ${index + 1} time`);
      time.onchange = () => {
        this.timeDrafts.set(meal, time.value);
        if (time.value) [meal.hour,meal.minute] = time.value.split(":").map(Number);
        this.changed();
      };
      const portions = this.element("input"); portions.type = "number"; portions.min = "1";
      portions.max = "10"; portions.step = "1"; portions.required = true; portions.value = meal.portions;
      portions.setAttribute("aria-label", `Meal ${index + 1} portions`);
      portions.onchange = () => { meal.portions = Number(portions.value); this.changed(); };
      const timeLabel = this.element("label", "Time", "field"); timeLabel.append(time);
      const portionsLabel = this.element("label", "Portions", "field"); portionsLabel.append(portions);
      fields.append(timeLabel, portionsLabel); head.insertBefore(fields, remove);
      const days = this.element("fieldset", undefined, "days");
      days.setAttribute("aria-label", `Meal ${index + 1} weekdays`);
      const dayList = this.element("div", undefined, "day-list");
      ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach((name, bit) => {
        const check = this.element("input"); check.type = "checkbox"; check.checked = !!(meal.weekdays & (1 << bit));
        check.setAttribute("aria-label", `Meal ${index + 1} ${name}`);
        check.onchange = () => {
          meal.weekdays = check.checked ? meal.weekdays | (1 << bit) : meal.weekdays & ~(1 << bit);
          this.changed();
        };
        const day = this.element("label", name, "day"); day.prepend(check); dayList.append(day);
      });
      days.append(dayList); row.append(days); root.querySelector("#meals").append(row);
    });
    this.updateSummary();
    root.querySelector("#add").disabled = this.meals.length >= 8;
    this.hass = this._hass;
  }

  static getConfigElement() { return document.createElement("pet-feeder-local-card-editor"); }
  static getStubConfig(hass) {
    return {schedule_entity: Object.keys(hass.states).find(id => hass.states[id].attributes?.integration === "pet_feeder_local") || ""};
  }

  getCardSize() { return 4 + Math.ceil((this.meals?.length || 0) * 1.5); }
}
if (!customElements.get("pet-feeder-local-card")) customElements.define("pet-feeder-local-card", PetFeederLocalCard);

class PetFeederLocalCardEditor extends HTMLElement {
  setConfig(config) { this.config = config; this.render(); }
  emitConfig(ids, defaultId) {
    const next = {...this.config, type:"custom:pet-feeder-local-card", schedule_entity:defaultId};
    if (ids.length > 1) next.schedule_entities = [...ids]; else delete next.schedule_entities;
    if (ids.length > 1 || defaultId !== this.config.schedule_entity) { delete next.portions_entity; delete next.serve_entity; }
    this.config = next;
    this.dispatchEvent(new CustomEvent("config-changed", {detail:{config:next}, bubbles:true, composed:true}));
  }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    if (!this.config || !this._hass) return;
    this.replaceChildren();
    const style = document.createElement("style");
    style.textContent = `
      pet-feeder-local-card-editor .pfl-editor{color:var(--primary-text-color);font-family:inherit;display:grid;gap:16px;padding:4px 0}
      pet-feeder-local-card-editor .pfl-editor h3,pet-feeder-local-card-editor .pfl-editor p{margin:0}
      pet-feeder-local-card-editor .pfl-editor h3{font-size:16px;line-height:1.4;font-weight:600}
      pet-feeder-local-card-editor .pfl-editor p{font-size:13px;line-height:1.5;color:var(--secondary-text-color)}
      pet-feeder-local-card-editor .pfl-editor label{display:grid;gap:8px;font-size:14px;font-weight:500}
      pet-feeder-local-card-editor .pfl-editor select{box-sizing:border-box;width:100%;min-height:44px;padding:8px 12px;font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:8px}
      pet-feeder-local-card-editor .pfl-editor select:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
    `;
    const panel = document.createElement("div"); panel.className = "pfl-editor";
    const heading = document.createElement("div");
    const title = document.createElement("h3"); title.textContent = "Feeder controls";
    const description = document.createElement("p"); description.textContent = "Choose the default feeder and any others to manage in this card";
    heading.append(title, description);
    const label = document.createElement("label"); label.textContent = "Feeder";
    const select = document.createElement("select");
    const blank = document.createElement("option"); blank.textContent = "Choose a feeder"; blank.value = ""; select.append(blank);
    const candidates = Object.entries(this._hass.states).filter(([id,state]) => state.attributes?.integration === "pet_feeder_local" || id === this.config.schedule_entity);
    const selected = this.config.schedule_entities || [this.config.schedule_entity].filter(Boolean);
    for (const [id,state] of candidates) { const option=document.createElement("option");option.value=id;option.textContent=state.attributes?.friendly_name || id;select.append(option); }
    select.value = this.config.schedule_entity || selected[0] || "";
    select.onchange = () => {
      this.emitConfig(select.value ? [...new Set([select.value, ...selected])] : [], select.value);
    };
    const choices = document.createElement("fieldset"); choices.style.cssText="border:0;padding:0;margin:0;display:grid;gap:4px";
    const legend=document.createElement("legend");legend.textContent="Feeders in this card";legend.style.cssText="font-size:14px;margin-bottom:8px";choices.append(legend);
    for (const [id,state] of candidates) {
      const row=document.createElement("label");row.style.cssText="display:flex;align-items:center;gap:8px;min-height:44px;font-size:13px";
      const check=document.createElement("input");check.type="checkbox";check.value=id;check.checked=selected.includes(id);check.style.cssText="width:18px;height:18px;accent-color:var(--primary-color)";
      check.onchange=()=>{
        const ids=[...choices.querySelectorAll("input:checked")].map(input=>input.value);
        this.emitConfig(ids, ids.includes(this.config.schedule_entity) ? this.config.schedule_entity : ids[0] || "");this.render();
      };
      row.append(check,document.createTextNode(`${state.attributes?.friendly_name || id} (${id})`));choices.append(row);
    }
    label.append(select);
    const help = document.createElement("p"); help.textContent="Controls link automatically. Switch between selected feeders or copy a schedule to several. Serve always acts on one feeder. Saved meals run on each device.";
    panel.append(heading, label, choices, help); this.append(style, panel);
  }
}
if (!customElements.get("pet-feeder-local-card-editor")) customElements.define("pet-feeder-local-card-editor", PetFeederLocalCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "pet-feeder-local-card")) window.customCards.push({type:"pet-feeder-local-card",name:"Pet Feeder Local",description:"Explicit feeding and an MCU schedule editor"});
