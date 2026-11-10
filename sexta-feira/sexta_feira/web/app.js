"use strict";
const $ = id => document.getElementById(id);
const API = "/api/v1";
let accessToken = "", role = "user", busy = false;
const collections={memories:[],tasks:[]}, counts={memories:0,tasks:0}, limits={memories:100,tasks:200};
const responseSources=new Map();
function notice(message) { $("notice").textContent = message; }
function connected(value) {
  $("status").textContent = value ? "Conectada" : "Desconectada";
  $("status").classList.toggle("connected", value);
  $("auth-form").hidden = value; $("logout").hidden = !value;
  for (const id of ["prompt", "send", "memory", "task", "export", "history", "refresh-status"]) $(id).disabled = !value;
  document.querySelectorAll(".stack button").forEach(button => button.disabled = !value);
  for(const name of ["memories","tasks"]) collectionControls(name);
}
async function request(path, body, method) {
  const offeredToken = accessToken;
  const options = {method: method || (body === undefined ? "GET" : "POST"), headers: {Authorization: "Bearer " + accessToken}, credentials: "omit", cache: "no-store", redirect: "error"};
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch(API + path, options);
  let payload; try { payload = await response.json(); } catch { throw new Error("Resposta inválida do servidor."); }
  if (offeredToken !== accessToken) throw new Error("A sessão foi encerrada.");
  if (!response.ok) {
    if (response.status === 401) { accessToken = ""; connected(false); }
    const message = typeof payload.error === "string" ? payload.error : payload.error?.message;
    throw new Error(message || "Falha na operação (" + response.status + ").");
  }
  return payload;
}
function message(role, content, source) {
  const article = document.createElement("article"); article.className = "message " + (role === "user" ? "user" : "assistant");
  const who = document.createElement("span"); who.className = "who"; who.textContent = role === "user" ? "Você" : "SEXTA-FEIRA";
  const text = document.createElement("span"); text.textContent = content; article.append(who, text);
  if(role !== "user" && source) { const label=document.createElement("span");label.className="message-source";label.textContent=source === "tool" ? "Ferramenta local" : "Texto gerado pelo GPT-2";article.append(label); }
  $("messages").append(article); $("messages").scrollTop = $("messages").scrollHeight;
}
function history(items) { $("messages").replaceChildren(); if (!items.length) message("assistant", "Olá. Sou a SEXTA-FEIRA. Como posso ajudar?"); for (const item of items) message(item.role, item.content, item.source || responseSources.get(item.id)); }
function button(label, action) { const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.addEventListener("click", async () => { b.disabled = true; try { await action(); } catch (error) { notice(error.message); } finally { b.disabled = false; } }); return b; }
function entries(name, items) {
  collections[name]=items;
  const list = $(name); list.replaceChildren();
  if (!items.length) { const empty = document.createElement("li"); empty.className = "empty"; empty.textContent = name === "memories" ? "Nenhuma memória salva." : "Nenhuma tarefa cadastrada."; list.append(empty); }
  for (const item of items) {
    const li = document.createElement("li"), label = document.createElement("span"), actions = document.createElement("div");
    label.textContent = item.content; if (item.completed) label.className = "done"; actions.className = "entry-actions";
    if (name === "tasks") actions.append(button(item.completed ? "Reabrir" : "Concluir", async () => { await request("/tasks/" + item.id, {completed: !item.completed}, "PATCH"); await refresh(); }));
    actions.append(button("Editar", async () => {
      const input = document.createElement("input"); input.value = item.content; input.maxLength = 480; input.setAttribute("aria-label", "Editar conteúdo"); label.replaceWith(input); actions.replaceChildren();
      actions.append(button("Salvar", async () => { await request("/" + name + "/" + item.id, {content: input.value}, "PATCH"); await refresh(); }), button("Cancelar", refresh)); input.focus();
    }), button("Excluir", async () => { await request("/" + name + "/" + item.id, undefined, "DELETE"); await refresh(); notice(name === "memories" ? "Memória excluída." : "Tarefa excluída."); }));
    li.append(label, actions); list.append(li);
  }
  collectionControls(name);
}
function collectionControls(name) {
  const total=counts[name],limit=limits[name],shown=collections[name].length;
  $(name+"-count").textContent=accessToken ? total+" registros · limite "+limit+" · "+shown+" exibidos" : "";
  $(name+"-more").hidden=!accessToken || shown>=total;
  const input=$(name === "memories" ? "memory" : "task"), form=$(name === "memories" ? "memory-form" : "task-form");
  input.disabled=!accessToken || total>=limit;
  form.querySelector("button").disabled=!accessToken || total>=limit;
  input.title=total>=limit ? "Limite atingido. Exclua um registro antes de adicionar outro." : "";
}
async function loadMore(name) {
  const control=$(name+"-more");control.disabled=true;
  try {
    const items=collections[name];if(!items.length) return;
    const before=Math.min(...items.map(item=>item.id));
    const data=await request("/"+name+"?limit="+limits[name]+"&before="+before);
    const known=new Set(items.map(item=>item.id));
    counts[name]=data.total ?? counts[name];
    const extra=(data[name] || []).filter(item=>!known.has(item.id));
    entries(name,items.concat(extra));
    if(!extra.length) control.hidden=true;
  } catch(error) { notice(error.message); } finally { control.disabled=false; }
}
function modelStatus(model = {}, metrics = {}) {
  const name = {small:"GPT-2 124M",medium:"GPT-2 355M"}[model.model] || model.model || "GPT-2 124M";
  const state = model.loading ? "Carregando" : model.processing ? "Gerando resposta" : model.closed ? "Encerrado" : model.loaded ? "Carregado" : "Sob demanda";
  const rows = [["Modelo",name],["Estado",state],["Dispositivo",model.device || "CPU"]];
  for (const [key,label] of [["queue_depth","Na fila"],["queue_limit","Limite da fila"],["cpu_threads","Threads de CPU"],["last_seconds","Última geração (s)"],["context_tokens","Contexto (tokens)"],["max_new_tokens","Geração máxima (tokens)"],["consecutive_failures","Falhas consecutivas"],["generated_tokens","Tokens gerados"]]) if (model[key] !== undefined) rows.push([label,model[key]]);
  if (metrics.requests !== undefined) rows.push(["Requisições HTTP",metrics.requests]);
  if (metrics.process_rss_bytes !== undefined) rows.push(["RAM do processo (MB)",(metrics.process_rss_bytes/1048576).toFixed(1)]);
  if (metrics.ram_available_bytes !== undefined || metrics.available_ram_bytes !== undefined) rows.push(["RAM disponível (MB)",((metrics.ram_available_bytes ?? metrics.available_ram_bytes)/1048576).toFixed(0)]);
  if (typeof metrics.process_cpu_percent === "number" && Number.isFinite(metrics.process_cpu_percent)) rows.push(["CPU do processo (%)",metrics.process_cpu_percent.toFixed(1)]);
  if (metrics.process_cpu_seconds !== undefined) rows.push(["Tempo de CPU do processo (s)",Number(metrics.process_cpu_seconds).toFixed(1)]);
  if (metrics.disk_free_bytes !== undefined) rows.push(["Disco disponível (GB)",(metrics.disk_free_bytes/1073741824).toFixed(1)]);
  $("model-status").replaceChildren(); for (const [key,value] of rows) { const dt=document.createElement("dt"),dd=document.createElement("dd"); dt.textContent=key;dd.textContent=value == null ? "Ainda não medida" : String(value);$("model-status").append(dt,dd); }
}
async function refresh(latestResponse) {
  const state=await request("/state");
  if(latestResponse && state.history?.length>=2) {
    const pair=state.history.slice(-2);
    if(pair[0].role==="user" && pair[0].content===latestResponse.message && pair[1].role==="assistant" && pair[1].content===latestResponse.reply) {
      responseSources.set(pair[1].id,latestResponse.source);
      if(responseSources.size>100) responseSources.delete(responseSources.keys().next().value);
    }
  }
  for(const name of ["memories","tasks"]) { counts[name]=state.counts?.[name] ?? (state[name] || []).length;limits[name]=state.limits?.[name] ?? limits[name]; }
  history(state.history || []);entries("memories",state.memories || []);entries("tasks",state.tasks || []);modelStatus(state.model || {});
  if (state.preferences) { $("speak").checked=!$("speak").disabled && state.preferences.voice_enabled===true;$("voice-rate").value=String(state.preferences.voice_rate || 1); }
}
async function refreshStatus() { const model = await request("/model"); let metrics = {}; if (role === "admin") metrics = await request("/metrics"); modelStatus(model, metrics); }
function localVoice() { return "speechSynthesis" in window ? speechSynthesis.getVoices().find(v => v.localService === true && v.lang.toLowerCase().startsWith("pt")) : undefined; }
function voiceAvailability() {
  const available=Boolean(localVoice()); $("speak").disabled=!available; $("voice-rate").disabled=!available;
  if (!available) $("speak").checked=false;
  $("speak").parentElement.title=available ? "Síntese de voz local disponível." : "Não há voz local em português disponível neste navegador.";
}
function speak(text) {
  if (!$("speak").checked || !("speechSynthesis" in window)) return;
  const voice = localVoice();
  if (!voice) { notice("Não foi encontrada uma voz local em português. Nenhum áudio foi enviado a serviços externos."); return; }
  speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.voice = voice; utterance.lang = voice.lang; utterance.rate = Number($("voice-rate").value); speechSynthesis.speak(utterance);
}
$("auth-form").addEventListener("submit", async event => {
  event.preventDefault(); accessToken = $("token").value.trim(); $("token").value = ""; $("connect").disabled = true;
  try { const session = await request("/sessions", {role: $("role").value}); accessToken = session.token; role = session.role; await refresh(); connected(true); await refreshStatus().catch(() => {}); notice("Sessão privada iniciada. O token não será salvo no navegador."); }
  catch (error) { accessToken = ""; connected(false); notice(error.message); } finally { $("connect").disabled = false; }
});
$("logout").addEventListener("click", async () => { try { await request("/sessions/current", undefined, "DELETE"); } catch {} accessToken = "";responseSources.clear();collections.memories=[];collections.tasks=[];counts.memories=0;counts.tasks=0;connected(false); $("messages").replaceChildren(); $("memories").replaceChildren(); $("tasks").replaceChildren(); if ("speechSynthesis" in window) speechSynthesis.cancel(); notice("Sessão encerrada. Recarregar a página também remove o token da memória."); });
$("chat-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy || !accessToken) return; const text = $("prompt").value.trim(); if (!text) return;
  const currentToken=accessToken; busy = true; $("send").disabled = true; $("processing").hidden = false; $("prompt").value = ""; message("user", text); notice("Gerando resposta localmente…");
  try { const result = await request("/conversations", {message:text}); message("assistant",result.reply,result.source);notice(result.source === "tool" ? "Ferramenta local executada." : "Texto gerado pelo GPT-2 local.");
    try { await refresh({message:text,reply:result.reply,source:result.source}); } catch(error) { notice("Resposta recebida. Não consegui atualizar os painéis: "+error.message); }
    speak(result.reply); }
  catch(error) { notice(error.message); if(accessToken===currentToken) $("prompt").value = text; }
  finally { busy = false; $("send").disabled = !accessToken; $("processing").hidden = true; $("prompt").focus(); }
});
for (const [form,input,path,label] of [["memory-form","memory","memories","Memória salva."],["task-form","task","tasks","Tarefa criada."]]) $(form).addEventListener("submit", async event => { event.preventDefault(); try { await request("/"+path,{content:$(input).value}); $(input).value=""; await refresh(); notice(label); } catch(error) { notice(error.message); } });
async function savePreferences() { if (!accessToken) return; try { await request("/preferences",{voice_enabled:$("speak").checked,voice_rate:Number($("voice-rate").value)},"PATCH"); } catch(error) { notice(error.message); } }
$("speak").addEventListener("change", savePreferences); $("voice-rate").addEventListener("change", savePreferences);
$("stop-speech").addEventListener("click", () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); });
$("refresh-status").addEventListener("click", async () => { try { await refreshStatus(); notice("Estado atualizado."); } catch(error) { notice(error.message); } });
$("history").addEventListener("click", async () => { try { const data = await request("/history?limit=100"); history(Array.isArray(data) ? data : data.history || []); notice("Histórico carregado (até 100 mensagens)."); } catch(error) { notice(error.message); } });
$("export").addEventListener("click", async () => { try { const data = await request("/export"); const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"})); const a=document.createElement("a"); a.href=url; a.download="sexta-feira-dados-"+new Date().toISOString().slice(0,10)+".json"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); notice("Exportação solicitada ao navegador. O arquivo contém dados privados."); } catch(error) { notice(error.message); } });
$("prompt").addEventListener("keydown", event => { if(event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("chat-form").requestSubmit(); } });
window.addEventListener("pagehide", () => { accessToken=""; if("speechSynthesis" in window) speechSynthesis.cancel(); });

voiceAvailability();
if("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged",voiceAvailability);

for(const name of ["memories","tasks"]) $(name+"-more").addEventListener("click",()=>loadMore(name));
