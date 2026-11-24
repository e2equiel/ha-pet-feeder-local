/** Local feeder controls. Editing a number never triggers a feeding command. */
class PetFeederLocalCard extends HTMLElement {
  setConfig(config) {
    if (!config.schedule_entity) {
      throw new Error("Select a Pet Feeder Local schedule sensor");
    }
    this.config = config;
    this.dirty = false;
    this.busy = false;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this.config.schedule_entity];
    if (!state || ["unavailable", "unknown"].includes(state.state)) {
      if (!this.shadowRoot.querySelector("ha-card")) this.shadowRoot.innerHTML = '<ha-card style="padding:20px">Feeder unavailable. Check power and the integration connection.</ha-card>';
      this.shadowRoot.querySelectorAll("button,input").forEach(node => node.disabled = true);
      return;
    }
    this.config = {...this.config,
      portions_entity: this.config.portions_entity || state.attributes.portions_entity,
      serve_entity: this.config.serve_entity || state.attributes.serve_entity};
    if (!this.config.portions_entity || !this.config.serve_entity) {
      this.shadowRoot.innerHTML = '<ha-card style="padding:20px">Waiting for feeder controls. This can take 30 seconds after setup.</ha-card>';
      return;
    }
    this.shadowRoot.querySelectorAll("input").forEach(node => node.disabled = false);
    if (!this.shadowRoot.querySelector("#portions") || (!this.dirty && !this.busy &&
        this.revision !== state.attributes.revision)) this.load();
    const input = this.shadowRoot.querySelector("#portions");
    if (input && this.shadowRoot.activeElement !== input) {
      input.value = hass.states[this.config.portions_entity]?.state || "1";
    }
    const serve = this.shadowRoot.querySelector("#serve");
    if (serve) serve.disabled = this.busy ||
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

  async action(callback) {
    if (this.busy) return;
    this.busy = true;
    this.shadowRoot.querySelectorAll("button").forEach(button => button.disabled = true);
    const message = this.shadowRoot.querySelector("#message");
    message.textContent = "Working…";
    try {
      await callback();
      message.textContent = "Done";
    } catch (error) {
      message.textContent = error.message || String(error);
    } finally {
      this.busy = false;
      this.shadowRoot.querySelectorAll("button").forEach(button => button.disabled = false);
      this.hass = this._hass;
    }
  }

  render() {
    this.shadowRoot.innerHTML = `<style>
      ha-card{padding:20px;display:block}h2{margin:0 0 16px;font-size:20px}
      h3{margin:24px 0 12px;font-size:17px}label{display:inline-flex;align-items:center;gap:6px}
      input,button{font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:6px;padding:8px}
      button{cursor:pointer}button:disabled{opacity:.5;cursor:default}.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}
      .controls,.fields,.actions,.days{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
      .meal{padding:14px 0;border-top:1px solid var(--divider-color)}.days{margin-top:12px;gap:8px}
      input[type=number]{width:54px}input[type=checkbox]{accent-color:var(--primary-color)}
      .actions{margin-top:16px}p{color:var(--secondary-text-color);line-height:1.5;font-size:14px}
      #message,#conflict{overflow-wrap:anywhere}#conflict{color:var(--warning-color)}
    </style><ha-card><h2>Pet Feeder Local</h2>
      <div class="controls"><label>Portions <input id="portions" type="number" min="1" max="10" step="1" value="1"></label>
      <button id="serve" class="primary">Serve</button></div>
      <h3>Feeding schedule</h3><div id="meals"></div>
      <div class="actions"><button id="add">Add meal</button><button id="save" class="primary">Save schedule</button><button id="reload">Reload</button></div>
      <p>The feeder runs saved meals itself. Home Assistant does not need to stay online.</p>
      <p id="conflict" hidden>The device schedule changed. Reload before saving.</p>
      <p id="message" role="status"></p></ha-card>`;
    const root = this.shadowRoot;
    root.querySelector("#portions").value = this._hass.states[this.config.portions_entity]?.state || "1";
    root.querySelector("#portions").onchange = event => {
      const value = Number(event.target.value);
      if (!Number.isInteger(value) || value < 1 || value > 10) {
        event.target.reportValidity(); return;
      }
      this.action(() => this._hass.callService("number", "set_value", {
        entity_id: this.config.portions_entity, value,
      }));
    };
    root.querySelector("#serve").onclick = () => this.action(() =>
      this._hass.callService("button", "press", { entity_id: this.config.serve_entity }));
    root.querySelector("#reload").onclick = () => this.load();
    root.querySelector("#add").onclick = () => {
      if (this.meals.length >= 8) return;
      this.meals.push({weekdays:127,hour:12,minute:0,portions:1,enabled:false});
      this.dirty = true; this.render();
    };
    root.querySelector("#save").onclick = () => this.action(async () => {
      for (const input of root.querySelectorAll("#meals input")) {
        if (!input.checkValidity()) { input.reportValidity(); return; }
      }
      await this._hass.callService("pet_feeder_local", "set_schedule", {
        config_entry_id: this._hass.states[this.config.schedule_entity].attributes.config_entry_id,
        expected_revision: this.revision, meals: this.meals.map(meal => ({ ...meal })),
      });
      this.dirty = false;
    });
    this.meals.forEach((meal, index) => {
      const row = this.element("div", undefined, "meal");
      const fields = this.element("div", undefined, "fields");
      const enabled = this.element("input"); enabled.type = "checkbox"; enabled.checked = meal.enabled;
      enabled.onchange = () => { meal.enabled = enabled.checked; this.dirty = true; };
      const label = this.element("label", `Meal ${index + 1}`); label.prepend(enabled); fields.append(label);
      const time = this.element("input"); time.type = "time"; time.required = true;
      time.value = `${String(meal.hour).padStart(2,"0")}:${String(meal.minute).padStart(2,"0")}`;
      time.setAttribute("aria-label", `Meal ${index + 1} time`);
      time.onchange = () => {
        if (!time.value) return;
        [meal.hour,meal.minute] = time.value.split(":").map(Number); this.dirty = true;
      };
      const portions = this.element("input"); portions.type = "number"; portions.min = "1";
      portions.max = "10"; portions.step = "1"; portions.required = true; portions.value = meal.portions;
      portions.setAttribute("aria-label", `Meal ${index + 1} portions`);
      portions.onchange = () => { meal.portions = Number(portions.value); this.dirty = true; };
      const remove = this.element("button", "Remove");
      remove.onclick = () => { this.meals.splice(index,1); this.dirty = true; this.render(); };
      fields.append(time, portions, remove); row.append(fields);
      const days = this.element("div", undefined, "days");
      ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach((name, bit) => {
        const check = this.element("input"); check.type = "checkbox"; check.checked = !!(meal.weekdays & (1 << bit));
        check.onchange = () => {
          meal.weekdays = check.checked ? meal.weekdays | (1 << bit) : meal.weekdays & ~(1 << bit);
          this.dirty = true;
        };
        const day = this.element("label", name); day.prepend(check); days.append(day);
      });
      row.append(days); root.querySelector("#meals").append(row);
    });
    root.querySelector("#add").disabled = this.meals.length >= 8;
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
    const label = document.createElement("label");
    label.textContent = "Feeder ";
    const select = document.createElement("select");
    select.style.cssText = "font:inherit;padding:12px;width:100%;margin:12px 0;border-radius:8px";
    const blank = document.createElement("option"); blank.textContent = "Choose a feeder"; blank.value = ""; select.append(blank);
    Object.entries(this._hass.states).filter(([id, state]) => state.attributes?.integration === "pet_feeder_local" || id === this.config.schedule_entity)
      .forEach(([id,state]) => {const option = document.createElement("option"); option.value=id; option.textContent=state.attributes?.friendly_name || id; select.append(option);});
    select.value = this.config.schedule_entity || "";
    select.onchange = () => {
      this.config = {type: "custom:pet-feeder-local-card", schedule_entity: select.value};
      this.dispatchEvent(new CustomEvent("config-changed", {detail:{config:this.config},bubbles:true,composed:true}));
    };
    label.append(select); this.append(label);
    const help = document.createElement("p"); help.textContent="Portions, Serve and the schedule editor are linked automatically. Saved meals run on the feeder."; this.append(help);
  }
}
if (!customElements.get("pet-feeder-local-card-editor")) customElements.define("pet-feeder-local-card-editor", PetFeederLocalCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "pet-feeder-local-card")) window.customCards.push({type:"pet-feeder-local-card",name:"Pet Feeder Local",description:"Explicit feeding and an MCU schedule editor"});
