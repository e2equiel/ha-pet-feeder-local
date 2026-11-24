/** Local feeder controls. Editing a number never triggers a feeding command. */
class PetFeederLocalCard extends HTMLElement {
  setConfig(config) {
    if (!config.schedule_entity) throw new Error("Select a Pet Feeder Local schedule sensor");
    this.config = config;
    this.dirty = false;
    this.busy = false;
    this.timeDrafts = new WeakMap();
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this.config.schedule_entity];
    const available = state && !["unavailable", "unknown"].includes(state.state);
    if (!available) {
      if (!this.shadowRoot.querySelector("ha-card")) this.shadowRoot.innerHTML = '<ha-card style="padding:24px">Feeder unavailable. Check power and the integration connection.</ha-card>';
      else {
        const message = this.shadowRoot.querySelector("#availability");
        if (message) { message.hidden = false; message.textContent = "Feeder unavailable. Check power and the integration connection."; }
      }
      this.shadowRoot.querySelectorAll("button,input").forEach(node => node.disabled = true);
      return;
    }
    this.config = {...this.config,
      portions_entity: this.config.portions_entity || state.attributes.portions_entity,
      serve_entity: this.config.serve_entity || state.attributes.serve_entity};
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
    this.shadowRoot.querySelectorAll("button,input").forEach(node => node.disabled = this.busy);
    const serve = this.shadowRoot.querySelector("#serve");
    if (serve) serve.disabled = this.busy || !input.checkValidity() ||
      ["unavailable", undefined].includes(hass.states[this.config.serve_entity]?.state);
    const add = this.shadowRoot.querySelector("#add");
    if (add) add.disabled = this.busy || this.meals.length >= 8;
    const conflict = this.shadowRoot.querySelector("#conflict");
    if (conflict) conflict.hidden = !this.dirty || this.revision === state.attributes.revision;
  }

  load() {
    const state = this._hass.states[this.config.schedule_entity];
    this.revision = state.attributes.revision;
    this.meals = (state.attributes.meals || []).map(meal => ({ ...meal }));
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
    this.shadowRoot.querySelectorAll("button,input").forEach(node => node.disabled = true);
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
      :host{display:block;--pfl-line:var(--divider-color,rgba(127,127,127,.24));--pfl-muted:var(--secondary-text-color,#656d6b);--pfl-raised:var(--secondary-background-color,var(--card-background-color));color:var(--primary-text-color)}
      *{box-sizing:border-box}ha-card{display:block;overflow:hidden}h2,h3,p{margin:0}h2{font-size:20px;font-weight:600;line-height:1.3}h3{font-size:17px;font-weight:600;line-height:1.4}
      .header{display:flex;align-items:center;gap:12px;padding:20px 24px;border-bottom:1px solid var(--pfl-line)}.brand-mark{width:40px;height:40px;flex:none}.subtitle,.summary,.help{font-size:13px;line-height:1.5;color:var(--pfl-muted)}.subtitle{margin-top:2px}
      .content{padding:24px;display:grid;gap:28px}.section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}.summary{font-variant-numeric:tabular-nums}.manual{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-top:16px}
      label.field{display:grid;gap:6px;font-size:13px;font-weight:500}.manual .field{width:112px}input,button{font:inherit;color:var(--primary-text-color);border:1px solid var(--pfl-line);border-radius:8px;background:var(--card-background-color);min-height:44px;padding:8px 12px}input[type=number]{width:100%;font-variant-numeric:tabular-nums}input[type=time]{width:100%;font-variant-numeric:tabular-nums}
      button{cursor:pointer;font-weight:500}button:hover:not(:disabled){background:var(--pfl-raised)}button:disabled,input:disabled{opacity:.5;cursor:default}.primary{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}.primary:hover:not(:disabled){background:var(--primary-color);filter:brightness(.94)}
      button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}.schedule{border-top:1px solid var(--pfl-line);padding-top:24px}.meals{display:grid;gap:12px;margin-top:16px}.meal{border:1px solid var(--pfl-line);border-radius:12px;padding:16px}.meal-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.enabled{display:inline-flex;align-items:center;gap:8px;font-weight:600;min-height:44px}.enabled input{width:18px;height:18px;min-height:0;margin:0;padding:0;accent-color:var(--primary-color)}
      .meal-title{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.meal-title strong{font-size:15px;font-weight:600}.enabled{font-size:13px;font-weight:400;color:var(--pfl-muted)}.remove{background:transparent;border-color:transparent;color:var(--pfl-muted)}.fields{display:grid;grid-template-columns:minmax(0,1fr) minmax(88px,.65fr);gap:12px;margin-top:8px}.days{padding:0;border:0;margin:16px 0 0;min-width:0}.days legend{font-size:13px;color:var(--pfl-muted);padding:0;margin-bottom:8px}.day-list{display:flex;flex-wrap:wrap;gap:8px}.day{position:relative;display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;border:1px solid var(--pfl-line);border-radius:8px;color:var(--pfl-muted);font-size:13px;cursor:pointer}.day input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}.day:has(input:checked)::before{content:"✓";margin-right:4px;font-weight:600}.day:has(input:checked){background:var(--pfl-raised);border-color:var(--primary-color);color:var(--primary-text-color)}.day:has(input:focus-visible){outline:2px solid var(--primary-color);outline-offset:2px}
      .actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.help{margin-top:16px}.notice{border-left:3px solid var(--warning-color,var(--primary-color));padding:8px 12px;line-height:1.5;overflow-wrap:anywhere}.notice[hidden]{display:none}#message{font-size:13px;line-height:1.5;color:var(--pfl-muted);overflow-wrap:anywhere}#message:empty{display:none}
      @media(max-width:360px){.header{padding:16px}.content{padding:16px;gap:24px}.meal{padding:12px}.fields{grid-template-columns:minmax(0,1fr) minmax(80px,.65fr)}.day-list{gap:4px}}
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
      <div class="content"><p id="availability" class="notice" role="status" hidden></p>
      <section aria-labelledby="serve-title"><h3 id="serve-title">Serve now</h3><div class="manual"><label class="field">Portions<input id="portions" type="number" min="1" max="10" step="1" value="1" required aria-describedby="portion-help"></label><button id="serve" class="primary">Serve</button></div><p id="portion-help" class="help">Choose 1–10 portions, then select Serve</p></section>
      <section class="schedule" aria-labelledby="schedule-title"><div class="section-heading"><h3 id="schedule-title">Feeding schedule</h3><span id="schedule-summary" class="summary"></span></div><div id="meals" class="meals"></div>
      <div class="actions"><button id="add">Add meal</button><button id="save" class="primary">Save schedule</button><button id="reload">Reload</button></div>
      <p class="help">The feeder runs saved meals itself. Home Assistant does not need to stay online.</p>
      <p id="conflict" class="notice" role="status" hidden>The device schedule changed. Reload before saving.</p></section>
      <p id="message" role="status" aria-live="polite"></p></div></ha-card>`;
    const root = this.shadowRoot;
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
      const title = this.element("strong", `Meal ${index + 1}`);
      const label = this.element("label", "Enabled", "enabled"); label.prepend(enabled);
      const heading = this.element("div", undefined, "meal-title"); heading.append(title, label); head.append(heading);
      const remove = this.element("button", "Remove", "remove");
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
      fields.append(timeLabel, portionsLabel); row.append(fields);
      const days = this.element("fieldset", undefined, "days");
      days.append(this.element("legend", "Days"));
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

  getCardSize() { return 3 + (this.meals?.length || 0) * 2; }
}
if (!customElements.get("pet-feeder-local-card")) customElements.define("pet-feeder-local-card", PetFeederLocalCard);

class PetFeederLocalCardEditor extends HTMLElement {
  setConfig(config) { this.config = config; this.render(); }
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
    const description = document.createElement("p"); description.textContent = "Choose the feeder for this card";
    heading.append(title, description);
    const label = document.createElement("label"); label.textContent = "Feeder";
    const select = document.createElement("select");
    const blank = document.createElement("option"); blank.textContent = "Choose a feeder"; blank.value = ""; select.append(blank);
    Object.entries(this._hass.states).filter(([id, state]) => state.attributes?.integration === "pet_feeder_local" || id === this.config.schedule_entity)
      .forEach(([id,state]) => {const option = document.createElement("option"); option.value=id; option.textContent=state.attributes?.friendly_name || id; select.append(option);});
    select.value = this.config.schedule_entity || "";
    select.onchange = () => {
      this.config = {type: "custom:pet-feeder-local-card", schedule_entity: select.value};
      this.dispatchEvent(new CustomEvent("config-changed", {detail:{config:this.config},bubbles:true,composed:true}));
    };
    label.append(select);
    const help = document.createElement("p"); help.textContent="Portions, Serve and the schedule editor are linked automatically. Saved meals run on the feeder.";
    panel.append(heading, label, help); this.append(style, panel);
  }
}
if (!customElements.get("pet-feeder-local-card-editor")) customElements.define("pet-feeder-local-card-editor", PetFeederLocalCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "pet-feeder-local-card")) window.customCards.push({type:"pet-feeder-local-card",name:"Pet Feeder Local",description:"Explicit feeding and an MCU schedule editor"});
