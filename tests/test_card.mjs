/** Run with happy-dom installed: node tests/test_card.mjs */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Window } from "happy-dom";

const window = new Window({url:"http://homeassistant.test/"});
window.eval(await readFile(new URL("../custom_components/pet_feeder_local/frontend/pet-feeder-local-card.js",import.meta.url),"utf8"));
const card = window.document.createElement("pet-feeder-local-card");
card.setConfig({schedule_entity:"sensor.schedule",portions_entity:"number.portions",serve_entity:"button.serve"});
const calls = [];
const hass = {
  states:{
    "sensor.schedule":{state:"1",attributes:{revision:"12345678",config_entry_id:"test-entry",
      meals:[{weekdays:62,hour:8,minute:30,portions:2,enabled:false}]}},
    "number.portions":{state:"1"},"button.serve":{state:"unknown"},
  },
  async callService(domain,service,data) {
    calls.push({domain,service,data});
    if (domain === "number") hass.states["number.portions"].state = String(data.value);
  },
};
card.hass = hass;
window.document.body.append(card);
const root = card.shadowRoot;
assert.equal(root.querySelector("#serve").disabled,false);
const portions = root.querySelector("#portions");
portions.value = "3"; portions.dispatchEvent(new window.Event("change"));
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(calls.length,1);
assert.equal(calls[0].domain,"number");
assert.equal(calls[0].data.value,3);
root.querySelector("#serve").click();
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(calls.length,2);
assert.equal(calls[1].domain,"button");
assert.equal(root.querySelector("#message").textContent,"Serve request sent to Home Assistant");
portions.value = ""; portions.dispatchEvent(new window.Event("input"));
assert.equal(portions.checkValidity(),false);
assert.equal(root.querySelector("#serve").disabled,true);
root.querySelector("#serve").click();
assert.equal(calls.length,2);
portions.value = "11"; portions.dispatchEvent(new window.Event("input"));
assert.equal(root.querySelector("#serve").disabled,true);
root.querySelector("#serve").click();
assert.equal(calls.length,2);
portions.value = "3"; portions.dispatchEvent(new window.Event("input"));
assert.equal(root.querySelector("#serve").disabled,false);
root.querySelector("#add").click();
assert.equal(card.meals.length,2);
assert.equal(card.meals[1].enabled,false);
assert.equal(calls.length,2);
root.querySelector("#save").click();
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(calls.length,3);
assert.equal(calls[2].domain,"pet_feeder_local");
assert.equal(calls[2].data.expected_revision,"12345678");
assert.equal(calls[2].data.meals.length,2);
assert.equal(calls[2].data.meals[1].enabled,false);
card.dirty = true;
hass.states["sensor.schedule"].attributes.revision = "87654321";
card.hass = hass;
assert.equal(root.querySelector("#conflict").hidden,false);
assert.equal(card.revision,"12345678");
hass.states["button.serve"].state = "unavailable";
card.hass = hass;
assert.equal(root.querySelector("#serve").disabled,true);
console.log("Card separation, disabled defaults, revision handling, and availability passed");

// The visual editor discovers links from one schedule entity, with no YAML.
const autoCard = window.document.createElement("pet-feeder-local-card");
hass.states["sensor.schedule"].attributes = {...hass.states["sensor.schedule"].attributes,
  integration:"pet_feeder_local",portions_entity:"number.portions",serve_entity:"button.serve"};
autoCard.setConfig({schedule_entity:"sensor.schedule"});autoCard.hass=hass;
assert.equal(autoCard.config.portions_entity,"number.portions");
const editor=window.document.createElement("pet-feeder-local-card-editor");
editor.setConfig({type:"custom:pet-feeder-local-card",schedule_entity:"sensor.schedule"});editor.hass=hass;
assert.equal(editor.querySelector("select").value,"sensor.schedule");
assert.equal(editor.querySelectorAll("option").length,2);
assert.equal(editor.querySelector("label").textContent.startsWith("Feeder"),true);
let configChange; editor.addEventListener("config-changed", event => { configChange = event.detail.config; });
editor.querySelector("select").value=""; editor.querySelector("select").dispatchEvent(new window.Event("change"));
assert.equal(configChange.type,"custom:pet-feeder-local-card");
assert.equal(configChange.schedule_entity,"");
assert.equal(autoCard.constructor.getStubConfig(hass).schedule_entity,"sensor.schedule");
hass.states["sensor.schedule"].state="unavailable";autoCard.hass=hass;
assert.equal(autoCard.shadowRoot.querySelector("#serve").disabled,true);
console.log("Automatic links, visual editor, and unavailable feeder controls passed");


// Derived counts describe enabled rows, never all saved rows as active.
const summaryCard = window.document.createElement("pet-feeder-local-card");
const schedule = hass.states["sensor.schedule"];
schedule.state = "3";
schedule.attributes = {...schedule.attributes, revision:"new-revision", meals:[
  {weekdays:127,hour:8,minute:0,portions:1,enabled:false},
  {weekdays:127,hour:12,minute:0,portions:2,enabled:false},
  {weekdays:127,hour:18,minute:0,portions:3,enabled:false},
]};
summaryCard.setConfig({schedule_entity:"sensor.schedule"}); summaryCard.hass=hass;
const summaryRoot = summaryCard.shadowRoot;
assert.equal(summaryRoot.querySelector("#schedule-summary").textContent,"0 enabled · 3 meals");
const enabled = summaryRoot.querySelector(".enabled input");
enabled.checked = true; enabled.dispatchEvent(new window.Event("change"));
assert.equal(summaryRoot.querySelector("#schedule-summary").textContent,"1 enabled · 3 meals · Unsaved changes");
assert.equal(summaryRoot.querySelectorAll("fieldset input[type=checkbox]").length,21);
assert.equal(summaryRoot.querySelector(".remove").getAttribute("aria-label"),"Remove meal 1");
window.confirm = () => false;
summaryRoot.querySelector("#reload").click();
assert.equal(summaryCard.dirty,true);
assert.equal(summaryCard.meals[0].enabled,true);
const timeDraft = summaryRoot.querySelector("input[type=time]");
timeDraft.value = ""; timeDraft.dispatchEvent(new window.Event("change"));
summaryRoot.querySelector("#add").click();
assert.equal(summaryRoot.querySelector("input[type=time]").value,"");
assert.equal(summaryCard.meals[3].enabled,false);
const countBeforeInvalid = calls.length;
summaryRoot.querySelector("#save").click();
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(calls.length,countBeforeInvalid);
assert.equal(summaryCard.dirty,true);
window.confirm = () => true;
summaryRoot.querySelector("#reload").click();
assert.equal(summaryCard.dirty,false);
assert.equal(summaryRoot.querySelector("#schedule-summary").textContent,"0 enabled · 3 meals");
console.log("Derived counts, accessible weekdays, and unsaved edits passed");

await window.happyDOM.abort();
