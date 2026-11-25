/** Synthetic multi-device safety checks. No network or real feeder is used. */
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {Window} from "happy-dom";

const window = new Window({url:"http://homeassistant.test/"});
window.eval(await readFile(new URL("../custom_components/pet_feeder_local/frontend/pet-feeder-local-card.js",import.meta.url),"utf8"));
const ids = ["sensor.kitchen", "sensor.pantry", "sensor.study"];
const meal = {weekdays:127,hour:8,minute:0,portions:1,enabled:false};
const calls = [];
let failEntry;
const hass = {states:{}, async callService(domain,service,data) {
  calls.push({domain,service,data});
  if (data.config_entry_id === failEntry) throw new Error("Connection lost; outcome unknown");
  if (domain === "number") this.states[data.entity_id].state = String(data.value);
}};
for (const [i,id] of ids.entries()) {
  hass.states[id] = {state:"1",attributes:{integration:"pet_feeder_local",friendly_name:["Kitchen","Pantry","Study"][i],
    revision:`revision-${i}`,config_entry_id:`entry-${i}`,portions_entity:`number.portions_${i}`,serve_entity:`button.serve_${i}`,meals:[{...meal}]}};
  hass.states[`number.portions_${i}`] = {state:String(i+1)};
  hass.states[`button.serve_${i}`] = {state:"unknown"};
}
const tick = () => new Promise(resolve=>setTimeout(resolve,0));
function create() {
  const card = window.document.createElement("pet-feeder-local-card");
  card.setConfig({schedule_entity:ids[0],schedule_entities:ids});card.hass=hass;window.document.body.append(card);return card;
}
const card = create(), root = card.shadowRoot;
assert.equal(root.querySelectorAll("#feeder-select option").length,3);
assert.equal(root.querySelectorAll(".copy-target:checked").length,0);
assert.equal(root.querySelector("#copy-schedule").disabled,true);
assert.equal(root.querySelector(".days").getAttribute("aria-label"),"Meal 1 weekdays");
assert.equal(root.querySelector(".days legend"),null);

// Switching preserves incomplete per-device drafts, and resolves manual controls afresh.
const time = root.querySelector("input[type=time]");time.value="";time.dispatchEvent(new window.Event("change"));
card.selectFeeder(ids[1]);
assert.equal(card.config.portions_entity,"number.portions_1");
assert.equal(root.querySelector("#portions").value,"2");
root.querySelector("#serve").click();await tick();
assert.equal(calls.at(-1).data.entity_id,"button.serve_1");
card.selectFeeder(ids[0]);
assert.equal(root.querySelector("input[type=time]").value,"");assert.equal(card.dirty,true);
assert.equal(card.config.portions_entity,"number.portions_0");
window.confirm=()=>true;root.querySelector("#reload").click();

// One explicit confirmation copies only to selected targets, using each target's revision.
let confirmed;
window.confirm=message=>{confirmed=message;return true;};
root.querySelectorAll(".copy-target").forEach(input=>input.checked=true);
card.updateCopyControls();assert.equal(root.querySelector("#copy-schedule").disabled,false);
const before=calls.length;await card.copySchedule();
assert.match(confirmed,/Pantry, Study/);
assert.equal(calls.length,before+2);
assert.deepEqual(calls.slice(before).map(call=>call.data.config_entry_id),["entry-1","entry-2"]);
assert.deepEqual(calls.slice(before).map(call=>call.data.expected_revision),["revision-1","revision-2"]);
assert.ok(calls.slice(before).every(call=>call.domain==="pet_feeder_local" && call.service==="set_schedule"));
assert.equal(root.querySelectorAll(".copy-target:checked").length,0);
assert.equal(root.querySelector("#copy-schedule").disabled,true);

// A known unavailable target prevents every write; confirmation cancellation also does.
root.querySelectorAll(".copy-target").forEach(input=>input.checked=true);
hass.states[ids[2]].state="unavailable";
let count=calls.length;await card.copySchedule();assert.equal(calls.length,count);
hass.states[ids[2]].state="1";window.confirm=()=>false;await card.copySchedule();assert.equal(calls.length,count);

// Runtime failures are reported per feeder without retrying or concealing partial success.
window.confirm=()=>true;failEntry="entry-1";await card.copySchedule();
assert.equal(calls.length,count+2);
assert.match(root.querySelector("#copy-results").textContent,/Pantry: Not confirmed/);
assert.match(root.querySelector("#copy-results").textContent,/Study: Saved/);
failEntry=undefined;

// A separate dirty target draft cannot be silently overwritten by a copy.
card.selectFeeder(ids[1]);card.meals[0].portions=4;card.changed();card.selectFeeder(ids[0]);
root.querySelector(`.copy-target[value="${ids[1]}"]`).checked=true;
count=calls.length;await card.copySchedule();assert.equal(calls.length,count);
assert.match(root.querySelector("#message").textContent,/unsaved edits/);

// An offline selected feeder must not trap the user on a disabled selector.
hass.states[ids[0]].state="unavailable";card.hass=hass;
assert.equal(root.querySelector("#serve").disabled,true);
assert.equal(root.querySelector("#feeder-select").disabled,false);
card.selectFeeder(ids[2]);assert.equal(root.querySelector("#serve").disabled,false);
hass.states[ids[0]].state="1";

// The visual editor creates a multi-feeder config without inheriting cross-device overrides.
const editor=window.document.createElement("pet-feeder-local-card-editor");
editor.setConfig({schedule_entity:ids[0],portions_entity:"number.legacy",serve_entity:"button.legacy"});editor.hass=hass;
let configuration;editor.addEventListener("config-changed",event=>configuration=event.detail.config);
const second=editor.querySelector(`input[value="${ids[1]}"]`);second.checked=true;second.dispatchEvent(new window.Event("change"));
assert.deepEqual(Array.from(configuration.schedule_entities),ids.slice(0,2));
assert.equal(configuration.portions_entity,undefined);assert.equal(configuration.serve_entity,undefined);

// A full active schedule keeps every field and row, with separate payloads per destination.
const fullMeals=[1,2,4,8,16,32,64,127].map((weekdays,index)=>({weekdays,hour:index*3,minute:5,portions:index+1,enabled:true}));
hass.states[ids[0]].state="8";hass.states[ids[0]].attributes.meals=fullMeals;
const fullCard=create(), fullRoot=fullCard.shadowRoot;
assert.equal(fullRoot.querySelectorAll(".meal").length,8);
assert.equal(fullRoot.querySelector("#add").disabled,true);
fullRoot.querySelectorAll(".copy-target").forEach(input=>input.checked=true);
count=calls.length;await fullCard.copySchedule();
assert.equal(calls.length,count+2);
assert.deepEqual(calls.slice(count).map(call=>call.data.config_entry_id),["entry-1","entry-2"]);
for (const call of calls.slice(count)) assert.deepEqual(JSON.parse(JSON.stringify(call.data.meals)),fullMeals);
calls[count].data.meals[7].portions=10;
assert.equal(calls[count+1].data.meals[7].portions,8);
assert.equal(fullCard.meals[7].portions,8);
console.log("Multi-feeder drafts, exact targeting, full active tables, preflight, confirmation, partial results and editor passed");
await window.happyDOM.abort();
