"use strict";
const $ = id => document.getElementById(id);
const API = "/api/v1";
let accessToken = "", role = "user", busy = false;
let contextAfter = 0, lastMessageId = 0, contextInitialized = false, showAllHistory = false;
const collections={memories:[],tasks:[]}, counts={memories:0,tasks:0}, limits={memories:100,tasks:200};
const responseSources=new Map();
const sourceLabels={tool:"Ferramenta no servidor",gpt2:"Texto gerado pelo GPT-2",local_model:"Texto gerado pelo modelo local"};
function notice(message) { $("notice").textContent = message; }
function activateView(name) {
  if(!["chat","memories","tasks","status","settings"].includes(name)) return;
  document.querySelectorAll(".workspace-view").forEach(panel => panel.hidden=panel.id!=="view-"+name);
  document.querySelectorAll(".navigation [data-view]").forEach(button => { if(button.dataset.view===name) button.setAttribute("aria-current","page"); else button.removeAttribute("aria-current"); });
}
function connected(value) {
  document.body.classList.toggle("is-connected",value);
  $("status").textContent = value ? "Conectada" : "Desconectada";
  $("status").classList.toggle("connected", value);
  $("auth-form").hidden = value; $("logout").hidden = !value;
  for (const id of ["prompt", "send", "memory", "task", "export", "history", "refresh-status","new-chat"]) $(id).disabled = !value;
  document.querySelectorAll("[data-prompt]").forEach(button=>button.disabled=!value);
  document.querySelectorAll(".stack button").forEach(button => button.disabled = !value);
  for(const name of ["memories","tasks"]) collectionControls(name);
  voiceAvailability();
}
async function request(path, body, method) {
  const offeredToken = accessToken;
  const options = {method: method || (body === undefined ? "GET" : "POST"), headers: {Authorization: "Bearer " + accessToken}, credentials: "omit", cache: "no-store", redirect: "error"};
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const controller=new AbortController(); options.signal=controller.signal;
  const timer=setTimeout(()=>controller.abort(),path==="/conversations" ? 115000 : 15000);
  let response;
  try { response=await fetch(API+path,options); }
  catch(error) {clearTimeout(timer); $("status").textContent="Sem conexão";$("status").classList.remove("connected");$("status").classList.add("offline");throw new Error(error.name==="AbortError" ? "O servidor levou mais tempo que o esperado. Tente novamente em instantes." : "Não consegui acessar o servidor. Confira sua conexão e tente novamente."); }
  if(accessToken) { $("status").textContent="Conectada";$("status").classList.add("connected");$("status").classList.remove("offline"); }
  let payload; try { payload = await response.json(); } catch { throw new Error("Resposta inválida do servidor."); } finally {clearTimeout(timer);}
  if (offeredToken !== accessToken) throw new Error("A sessão foi encerrada.");
  if (!response.ok) {
    if (response.status === 401) { accessToken = ""; connected(false); }
    const message = typeof payload.error === "string" ? payload.error : payload.error?.message;
    throw new Error(message || "Falha na operação (" + response.status + ").");
  }
  return payload;
}
function message(role, content, source, model) {
  const article = document.createElement("article"); article.className = "message " + (role === "user" ? "user" : "assistant");
  const who = document.createElement("span"); who.className = "who"; who.textContent = role === "user" ? "Você" : "SEXTA-FEIRA";
  const text = document.createElement("span"); text.textContent = content; article.append(who, text);
  if(role !== "user") { const label=document.createElement("span");label.className="message-source";label.textContent=source ? (sourceLabels[source] || "Fonte não identificada")+(model ? " · "+model : "") : "Histórico anterior";article.append(label); const copy=document.createElement("button");copy.type="button";copy.className="copy-reply";copy.textContent="Copiar";copy.setAttribute("aria-label","Copiar resposta");copy.addEventListener("click",async()=>{try{await navigator.clipboard.writeText(content);notice("Resposta copiada.");}catch{notice("Não foi possível copiar automaticamente. Selecione o texto da resposta.");}});article.append(copy); }
  $("messages").append(article); $("messages").scrollTop = $("messages").scrollHeight;
}
function history(items) {
  $("messages").replaceChildren();
  if(!items.length) {
    const welcome=document.createElement("article");welcome.className="welcome";
    const symbol=document.createElement("span");symbol.className="welcome-symbol";symbol.textContent="✧";symbol.setAttribute("aria-hidden","true");
    const heading=document.createElement("h3");heading.textContent="O que vamos organizar hoje?";
    const text=document.createElement("p");text.textContent="Converse com a SEXTA-FEIRA ou use uma ferramenta do seu servidor.";
    const suggestions=document.createElement("div");suggestions.className="suggestions";
    for(const [label,prompt] of [["Que horas são? ↗","/hora"],["Ver minhas tarefas ↗","/tarefas"]]){const b=document.createElement("button");b.type="button";b.textContent=label;b.dataset.prompt=prompt;b.disabled=!accessToken;suggestions.append(b);}
    welcome.append(symbol,heading,text,suggestions);$("messages").append(welcome);
  }
  for (const item of items) message(item.role,item.content,item.source || responseSources.get(item.id),item.model);
}
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
  $("model-brand").textContent="Seu espaço privado · "+name;
  const rows = [["Modelo",name],["Estado",state],["Execução","Servidor da API"],["Dispositivo",model.device === "cpu" ? "CPU do servidor" : (model.device || "CPU do servidor")]];
  for (const [key,label] of [["queue_depth","Na fila"],["queue_limit","Limite da fila"],["cpu_threads","Threads de CPU"],["last_seconds","Última geração (s)"],["context_tokens","Contexto (tokens)"],["max_new_tokens","Geração máxima (tokens)"],["consecutive_failures","Falhas consecutivas"],["generated_tokens","Tokens gerados"]]) if (model[key] !== undefined) rows.push([label,model[key]]);
  if (metrics.requests !== undefined) rows.push(["Requisições HTTP",metrics.requests]);
  if (metrics.process_rss_bytes !== undefined) rows.push([metrics.inference_process_rss_bytes !== undefined ? "RAM API + modelo (MB)" : "RAM do processo (MB)",(metrics.process_rss_bytes/1048576).toFixed(1)]);
  if (metrics.inference_process_rss_bytes !== undefined) rows.push(["RAM do modelo (MB)",(metrics.inference_process_rss_bytes/1048576).toFixed(1)]);
  if (metrics.ram_available_bytes !== undefined || metrics.available_ram_bytes !== undefined) rows.push(["RAM disponível (MB)",((metrics.ram_available_bytes ?? metrics.available_ram_bytes)/1048576).toFixed(0)]);
  if (typeof metrics.process_cpu_percent === "number" && Number.isFinite(metrics.process_cpu_percent)) rows.push(["CPU do processo (%)",metrics.process_cpu_percent.toFixed(1)]);
  if (metrics.process_cpu_seconds !== undefined) rows.push(["Tempo de CPU do processo (s)",Number(metrics.process_cpu_seconds).toFixed(1)]);
  if (metrics.disk_free_bytes !== undefined) rows.push(["Disco disponível (GB)",(metrics.disk_free_bytes/1073741824).toFixed(1)]);
  $("model-status").replaceChildren(); for (const [key,value] of rows) { const dt=document.createElement("dt"),dd=document.createElement("dd"); dt.textContent=key;dd.textContent=value == null ? "Ainda não medida" : String(value);$("model-status").append(dt,dd); }
}
async function refresh(latestResponse) {
  const state=await request("/state");
  if(!contextInitialized){contextAfter=Number(state.model?.history_after_id)||0;contextInitialized=true;}
  if(state.history?.length) lastMessageId=Math.max(lastMessageId,...state.history.map(item=>item.id));
  if(latestResponse && state.history?.length>=2) {
    const pair=state.history.slice(-2);
    if(pair[0].role==="user" && pair[0].content===latestResponse.message && pair[1].role==="assistant" && pair[1].content===latestResponse.reply) {
      responseSources.set(pair[1].id,latestResponse.source);
      if(responseSources.size>100) responseSources.delete(responseSources.keys().next().value);
    }
  }
  for(const name of ["memories","tasks"]) { counts[name]=state.counts?.[name] ?? (state[name] || []).length;limits[name]=state.limits?.[name] ?? limits[name]; }
  if(!busy || latestResponse) history((state.history || []).filter(item=>showAllHistory || item.id>contextAfter));
  entries("memories",state.memories || []);entries("tasks",state.tasks || []);modelStatus(state.model || {});
  if (state.preferences) { $("speak").checked=!$("speak").disabled && state.preferences.voice_enabled===true;$("voice-rate").value=String(state.preferences.voice_rate || 1); }
}
async function refreshStatus() { const model = await request("/model"); let metrics = {}; if (role === "admin") metrics = await request("/metrics"); modelStatus(model, metrics);$("metrics-note").textContent=role==="admin" ? "Medidas reais no servidor. CPU é a média desde a última consulta; o modelo pode ficar ocioso entre mensagens." : "Métricas detalhadas exigem uma sessão de administrador."; }
function localVoice() { return "speechSynthesis" in window ? speechSynthesis.getVoices().find(v => v.localService === true && v.lang.toLowerCase().startsWith("pt")) : undefined; }
function voiceAvailability() {
  const available=Boolean(localVoice()); $("speak").disabled=!available || !accessToken; $("voice-rate").disabled=!available || !accessToken;
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
  try { const session = await request("/sessions", {role: $("role").value}); accessToken = session.token; role = session.role;contextInitialized=false;showAllHistory=false;connected(true);await refresh();await refreshStatus().catch(() => {});notice("Sessão privada iniciada. O modelo roda no seu servidor.");$("prompt").focus(); }
  catch (error) { accessToken = ""; connected(false); notice(error.message); } finally { $("connect").disabled = false; }
});
$("logout").addEventListener("click", async () => { try { await request("/sessions/current", undefined, "DELETE"); } catch {} accessToken = "";responseSources.clear();collections.memories=[];collections.tasks=[];counts.memories=0;counts.tasks=0;connected(false); $("messages").replaceChildren(); $("memories").replaceChildren(); $("tasks").replaceChildren(); if ("speechSynthesis" in window) speechSynthesis.cancel(); notice("Sessão encerrada. Recarregar a página também remove o token da memória."); });
$("chat-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy || !accessToken) return; const text = $("prompt").value.trim(); if (!text) return;
  const currentToken=accessToken; busy = true; $("send").disabled = true;$("new-chat").disabled=true; $("processing").hidden = false; $("prompt").value = ""; message("user", text); notice("Gerando resposta no servidor…");
  const started=Date.now();$("processing-text").textContent="Pensando no servidor…";const ticker=setInterval(()=>{$("processing-text").textContent="Pensando no servidor · "+Math.floor((Date.now()-started)/1000)+" s";},1000);
  try { const body={message:text};if(contextAfter>0) body.context_after=contextAfter;const result = await request("/conversations", body); message("assistant",result.reply,result.source,result.model);notice(result.source === "tool" ? "Ferramenta executada no servidor." : "Resposta gerada no servidor em "+((Date.now()-started)/1000).toFixed(1)+" s.");
    try { await refresh({message:text,reply:result.reply,source:result.source}); } catch(error) { notice("Resposta recebida. Não consegui atualizar os painéis: "+error.message); }
    await refreshStatus().catch(()=>{});speak(result.reply); }
  catch(error) { notice(error.message); if(accessToken===currentToken) $("prompt").value = text; }
  finally {clearInterval(ticker);busy = false; $("send").disabled = !accessToken;$("new-chat").disabled=!accessToken; $("processing").hidden = true;if(accessToken) $("prompt").focus(); }
});
const pendingForms=new Set();
for (const [form,input,path,label] of [["memory-form","memory","memories","Memória salva."],["task-form","task","tasks","Tarefa criada."]]) $(form).addEventListener("submit", async event => { event.preventDefault();if(pendingForms.has(form)) return;pendingForms.add(form);$(form).querySelector("button").disabled=true;try { await request("/"+path,{content:$(input).value}); $(input).value=""; await refresh(); notice(label); } catch(error) { notice(error.message); }finally{pendingForms.delete(form);collectionControls(path);} });
async function savePreferences() { if (!accessToken) return; try { await request("/preferences",{voice_enabled:$("speak").checked,voice_rate:Number($("voice-rate").value)},"PATCH"); } catch(error) { notice(error.message); } }
$("speak").addEventListener("change", savePreferences); $("voice-rate").addEventListener("change", savePreferences);
$("stop-speech").addEventListener("click", () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); });
$("refresh-status").addEventListener("click", async () => { try { await refreshStatus(); notice("Estado atualizado."); } catch(error) { notice(error.message); } });
$("history").addEventListener("click", async () => { try { const data = await request("/history?limit=100");showAllHistory=true; history(Array.isArray(data) ? data : data.history || []);activateView("chat"); notice("Histórico anterior carregado (até 100 mensagens). Os dados continuam salvos no servidor."); } catch(error) { notice(error.message); } });
$("export").addEventListener("click", async () => { try { const data = await request("/export"); const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"})); const a=document.createElement("a"); a.href=url; a.download="sexta-feira-dados-"+new Date().toISOString().slice(0,10)+".json"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); notice("Exportação solicitada ao navegador. O arquivo contém dados privados."); } catch(error) { notice(error.message); } });
$("prompt").addEventListener("keydown", event => { if(event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("chat-form").requestSubmit(); } });
$("new-chat").addEventListener("click",()=>{if(busy || !accessToken) return;contextAfter=Math.max(contextAfter,lastMessageId);showAllHistory=false;history([]);$("prompt").value="";activateView("chat");$("prompt").focus();notice("Nova conversa iniciada. O histórico anterior continua salvo.");});
document.querySelectorAll(".navigation [data-view]").forEach(button=>button.addEventListener("click",()=>activateView(button.dataset.view)));
$("workspace").addEventListener("click",event=>{const button=event.target.closest("[data-prompt]");if(!button || !accessToken || busy) return;$("prompt").value=button.dataset.prompt;$("chat-form").requestSubmit();});
window.addEventListener("pagehide", () => { accessToken=""; if("speechSynthesis" in window) speechSynthesis.cancel(); });

voiceAvailability();
if("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged",voiceAvailability);

for(const name of ["memories","tasks"]) $(name+"-more").addEventListener("click",()=>loadMore(name));
