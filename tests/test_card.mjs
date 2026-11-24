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
assert.equal(autoCard.constructor.getStubConfig(hass).schedule_entity,"sensor.schedule");
hass.states["sensor.schedule"].state="unavailable";autoCard.hass=hass;
assert.equal(autoCard.shadowRoot.querySelector("#serve").disabled,true);
console.log("Automatic links, visual editor, and unavailable feeder controls passed");

await window.happyDOM.abort();
