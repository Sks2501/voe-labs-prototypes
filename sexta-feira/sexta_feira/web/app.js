"use strict";
const $ = id => document.getElementById(id);
const API = "/api/v1";
let accessToken = "", role = "user", busy = false;
let contextAfter = 0, lastMessageId = 0, contextInitialized = false, showAllHistory = false;
let selectedThread=null, threadItems=[], visibleMessages=[], profileState={}, profileDirty=false, noticeTimer;
const profileFields={preferred_name:"preferred-name",about_me:"about-me",goals:"goals",response_style:"response-style"};
const collections={memories:[],tasks:[]}, counts={memories:0,tasks:0}, limits={memories:100,tasks:200};
const responseSources=new Map();
const sourceLabels={tool:"Ferramenta no servidor",gpt2:"Texto gerado pelo GPT-2",local_model:"Texto gerado pelo modelo local"};
function notice(message) { clearTimeout(noticeTimer);$("notice").textContent=message;$("notice").classList.add("visible");noticeTimer=setTimeout(()=>$("notice").classList.remove("visible"),6000); }
function activateView(name) {
  if(!["chat","memories","tasks","profile","status","settings"].includes(name)) return;
  document.querySelectorAll(".workspace-view").forEach(panel => panel.hidden=panel.id!=="view-"+name);
  document.querySelectorAll(".navigation [data-view]").forEach(button => { if(button.dataset.view===name) button.setAttribute("aria-current","page"); else button.removeAttribute("aria-current"); });
  if(window.matchMedia("(max-width:700px)").matches) setSidebar(false);
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
  for(const id of [...Object.values(profileFields),"save-profile","clear-profile"]) $(id).disabled=!value;
  $("rename-chat").hidden=!value || !selectedThread;
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
  $("messages").querySelector(".welcome")?.remove();
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
    const heading=document.createElement("h3");heading.textContent=profileState.preferred_name ? "O que vamos fazer hoje, "+profileState.preferred_name+"?" : "O que vamos fazer hoje?";
    const text=document.createElement("p");text.textContent="Estou por aqui. Vamos cuidar do que importa.";
    const suggestions=document.createElement("div");suggestions.className="suggestions";
    for(const [label,prompt] of [["Organizar meu dia","Me ajude a organizar meu dia. Por onde começamos?"],["Uma ideia nova","Me ajude a transformar uma ideia em um plano simples."],["Minhas tarefas","/tarefas"]]){const b=document.createElement("button");b.type="button";b.textContent=label;b.dataset.prompt=prompt;b.disabled=!accessToken;suggestions.append(b);}
    const invite=document.createElement("button");invite.type="button";invite.className="profile-invite";invite.textContent="Personalizar o que você sabe sobre mim";invite.addEventListener("click",()=>activateView("profile"));
    welcome.append(symbol,heading,text,suggestions,invite);$("messages").append(welcome);
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
  $(name+"-count").textContent=accessToken ? total+(total===1 ? " registro" : " registros")+" · limite "+limit+" · "+shown+(shown===1 ? " exibido" : " exibidos") : "";
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
  $("model-brand").textContent=name.split(" · ")[0]+" · no seu servidor";
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
  if(!contextInitialized){contextAfter=Number(state.model?.history_after_id)||0;contextInitialized=true;selectedThread=state.threads?.[0]?.id || null;}
  if(state.history?.length) lastMessageId=Math.max(lastMessageId,...state.history.map(item=>item.id));
  if(latestResponse && state.history?.length>=2) {
    const pair=state.history.slice(-2);
    if(pair[0].role==="user" && pair[0].content===latestResponse.message && pair[1].role==="assistant" && pair[1].content===latestResponse.reply) {
      responseSources.set(pair[1].id,latestResponse.source);
      if(responseSources.size>100) responseSources.delete(responseSources.keys().next().value);
    }
  }
  for(const name of ["memories","tasks"]) { counts[name]=state.counts?.[name] ?? (state[name] || []).length;limits[name]=state.limits?.[name] ?? limits[name]; }
  fillProfile(state.preferences || {});renderThreads(state.threads || []);
  if(!busy || latestResponse) {
    if(selectedThread){const thread=await request("/threads/"+selectedThread);visibleMessages=thread.history;history(visibleMessages);$("thread-more").hidden=visibleMessages.length<100;}
    else if(!showAllHistory){visibleMessages=[];history([]);$("thread-more").hidden=true;}
  }
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
  try { const session = await request("/sessions", {role: $("role").value}); accessToken = session.token; role = session.role;contextInitialized=false;showAllHistory=false;connected(true);await refresh();await refreshStatus().catch(() => {});notice("Sessão privada iniciada. O modelo roda no seu servidor.");if(!window.matchMedia("(max-width:700px)").matches)$("prompt").focus(); }
  catch (error) { accessToken = ""; connected(false); notice(error.message); } finally { $("connect").disabled = false; }
});
$("logout").addEventListener("click", async () => { try { await request("/sessions/current", undefined, "DELETE"); } catch {} accessToken="";selectedThread=null;visibleMessages=[];profileDirty=false;fillProfile({});renderThreads([]);responseSources.clear();collections.memories=[];collections.tasks=[];counts.memories=0;counts.tasks=0;connected(false);$("messages").replaceChildren();$("memories").replaceChildren();$("tasks").replaceChildren();$("model-brand").textContent="Sua assistente privada";$("model-status").replaceChildren();activateView("chat");if("speechSynthesis" in window) speechSynthesis.cancel();notice("Sessão encerrada."); });
$("chat-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy || !accessToken) return; const text = $("prompt").value.trim(); if (!text) return;
  const currentToken=accessToken; busy = true; $("send").disabled = true;$("new-chat").disabled=true; $("processing").hidden = false; $("prompt").value = ""; message("user", text); notice("Gerando resposta no servidor…");
  const started=Date.now();$("processing-text").textContent="Pensando no servidor…";const ticker=setInterval(()=>{$("processing-text").textContent="Pensando no servidor · "+Math.floor((Date.now()-started)/1000)+" s";},1000);
  try { if(!selectedThread){const thread=await request("/threads",{title:text.replace(/\s+/g," ").slice(0,80)});selectedThread=thread.id;renderThreads([thread,...threadItems]);}const body={message:text,thread_id:selectedThread};const result = await request("/conversations", body); message("assistant",result.reply,result.source,result.model);notice(result.source === "tool" ? "Ferramenta executada no servidor." : "Resposta gerada no servidor em "+((Date.now()-started)/1000).toFixed(1)+" s.");
    try { await refresh({message:text,reply:result.reply,source:result.source}); } catch(error) { notice("Resposta recebida. Não consegui atualizar os painéis: "+error.message); }
    await refreshStatus().catch(()=>{});speak(result.reply); }
  catch(error) { notice(error.message); if(accessToken===currentToken) $("prompt").value = text; }
  finally {clearInterval(ticker);busy = false; $("send").disabled = !accessToken;$("new-chat").disabled=!accessToken; $("processing").hidden = true;if(accessToken) if(!window.matchMedia("(max-width:700px)").matches)$("prompt").focus(); }
});
const pendingForms=new Set();
for (const [form,input,path,label] of [["memory-form","memory","memories","Memória salva."],["task-form","task","tasks","Tarefa criada."]]) $(form).addEventListener("submit", async event => { event.preventDefault();if(pendingForms.has(form)) return;pendingForms.add(form);$(form).querySelector("button").disabled=true;try { await request("/"+path,{content:$(input).value}); $(input).value=""; await refresh(); notice(label); } catch(error) { notice(error.message); }finally{pendingForms.delete(form);collectionControls(path);} });
async function savePreferences() { if (!accessToken) return; try { await request("/preferences",{voice_enabled:$("speak").checked,voice_rate:Number($("voice-rate").value)},"PATCH"); } catch(error) { notice(error.message); } }
$("speak").addEventListener("change", savePreferences); $("voice-rate").addEventListener("change", savePreferences);
$("stop-speech").addEventListener("click", () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); });
$("refresh-status").addEventListener("click", async () => { try { await refreshStatus(); notice("Estado atualizado."); } catch(error) { notice(error.message); } });
$("history").addEventListener("click", async () => { if(busy)return;try { const data=await request("/history?limit=100");selectedThread=null;showAllHistory=true;visibleMessages=data.history || [];renderThreads(threadItems);history(visibleMessages);$("thread-more").hidden=true;activateView("chat");notice("Histórico geral preservado (até 100 mensagens). Enviar uma mensagem inicia uma conversa separada."); } catch(error) { notice(error.message); } });
$("export").addEventListener("click", async () => { try { const data = await request("/export"); const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"})); const a=document.createElement("a"); a.href=url; a.download="sexta-feira-dados-"+new Date().toISOString().slice(0,10)+".json"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); notice("Exportação solicitada ao navegador. O arquivo contém dados privados."); } catch(error) { notice(error.message); } });
$("prompt").addEventListener("keydown", event => { if(event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("chat-form").requestSubmit(); } });
$("new-chat").addEventListener("click",()=>{if(busy || !accessToken)return;selectedThread=null;showAllHistory=false;visibleMessages=[];renderThreads(threadItems);history([]);$("thread-more").hidden=true;$("prompt").value="";resizePrompt();activateView("chat");if(!window.matchMedia("(max-width:700px)").matches)$("prompt").focus();});
document.querySelectorAll(".navigation [data-view]").forEach(button=>button.addEventListener("click",()=>activateView(button.dataset.view)));
$("workspace").addEventListener("click",event=>{const button=event.target.closest("[data-prompt]");if(!button || !accessToken || busy) return;$("prompt").value=button.dataset.prompt;$("chat-form").requestSubmit();});
window.addEventListener("pagehide", () => { accessToken=""; if("speechSynthesis" in window) speechSynthesis.cancel(); });

voiceAvailability();
if("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged",voiceAvailability);

for(const name of ["memories","tasks"]) $(name+"-more").addEventListener("click",()=>loadMore(name));

function fillProfile(values) {
  profileState=values;
  if(!profileDirty) for(const [key,id] of Object.entries(profileFields)) $(id).value=values[key] || "";
  const name=values.preferred_name || "Sobre você";$("account-name").textContent=name;$("account-initial").textContent=(values.preferred_name || "V").slice(0,1).toLocaleUpperCase("pt-BR");
}
function renderThreads(items) {
  threadItems=items;const list=$("conversation-list");list.replaceChildren();$("thread-count").textContent=accessToken && items.length ? items.length+"/100" : "";
  if(!items.length){const empty=document.createElement("p");empty.className="sidebar-empty";empty.textContent=accessToken ? "Suas novas conversas aparecem aqui." : "Entre para ver suas conversas.";list.append(empty);}
  for(const item of items){const row=document.createElement("div");row.className="thread-row"+(item.id===selectedThread ? " active" : "");const entry=document.createElement("button");entry.type="button";entry.className="thread-item";entry.textContent=item.title;entry.title=item.title;if(item.id===selectedThread)entry.setAttribute("aria-current","true");entry.addEventListener("click",()=>openThread(item.id));const remove=document.createElement("button");remove.type="button";remove.className="thread-delete";remove.textContent="×";remove.setAttribute("aria-label","Excluir conversa "+item.title);remove.addEventListener("click",async()=>{if(busy || !confirm('Excluir a conversa "'+item.title+'" e suas mensagens? A recuperação exige um backup.'))return;remove.disabled=true;try{await request("/threads/"+item.id,undefined,"DELETE");if(selectedThread===item.id){selectedThread=null;showAllHistory=false;}await refresh();notice("Conversa excluída.");}catch(error){notice(error.message);}finally{remove.disabled=false;}});row.append(entry,remove);list.append(row);}
  $("conversation-title").textContent=items.find(item=>item.id===selectedThread)?.title || (showAllHistory ? "Histórico anterior" : "");$("rename-chat").hidden=!accessToken || !selectedThread;
}
async function openThread(id) {
  if(busy || !accessToken)return;
  try{const data=await request("/threads/"+id);selectedThread=id;showAllHistory=false;visibleMessages=data.history;history(visibleMessages);renderThreads(threadItems);$("thread-more").hidden=visibleMessages.length<100;activateView("chat");}catch(error){notice(error.message);}
}
$("thread-more").addEventListener("click",async()=>{if(!selectedThread || busy || !visibleMessages.length)return;const button=$("thread-more");button.disabled=true;try{const data=await request("/threads/"+selectedThread+"?limit=100&before="+visibleMessages[0].id);visibleMessages=[...data.history,...visibleMessages].slice(0,500);history(visibleMessages);$("messages").scrollTop=0;button.hidden=data.history.length<100 || visibleMessages.length>=500;if(visibleMessages.length>=500)notice("Exibindo até 500 mensagens. A exportação inclui o histórico completo, dentro do limite de tamanho.");}catch(error){notice(error.message);}finally{button.disabled=false;}});
$("rename-chat").addEventListener("click",()=>{if(!selectedThread || busy)return;$("thread-name").value=threadItems.find(item=>item.id===selectedThread)?.title || "";$("rename-dialog").showModal();});
$("cancel-rename").addEventListener("click",()=>$("rename-dialog").close());
$("rename-form").addEventListener("submit",async event=>{event.preventDefault();if(!selectedThread)return;const submit=event.target.querySelector('[type="submit"]');submit.disabled=true;try{await request("/threads/"+selectedThread,{title:$("thread-name").value.trim()},"PATCH");$("rename-dialog").close();const data=await request("/threads");renderThreads(data.threads);notice("Título atualizado.");}catch(error){notice(error.message);}finally{submit.disabled=false;}});
for(const id of Object.values(profileFields)) $(id).addEventListener("input",()=>profileDirty=true);
$("profile-form").addEventListener("submit",async event=>{event.preventDefault();if(!accessToken)return;$("save-profile").disabled=true;try{const values=Object.fromEntries(Object.entries(profileFields).map(([key,id])=>[key,$(id).value.trim()]));const saved=await request("/preferences",values,"PATCH");profileDirty=false;fillProfile(saved);if(!selectedThread && !showAllHistory)history([]);notice("Perfil salvo. Vou usar essas informações nas próximas mensagens.");}catch(error){notice(error.message);}finally{$("save-profile").disabled=!accessToken;}});
$("clear-profile").addEventListener("click",async()=>{if(!accessToken || !confirm("Limpar apenas os quatro campos do perfil? Memórias e conversas continuam salvas."))return;$("clear-profile").disabled=true;try{const saved=await request("/preferences",Object.fromEntries(Object.keys(profileFields).map(key=>[key,""])),"PATCH");profileDirty=false;fillProfile(saved);if(!selectedThread && !showAllHistory)history([]);notice("Perfil limpo.");}catch(error){notice(error.message);}finally{$("clear-profile").disabled=!accessToken;}});
function syncSidebar(){const mobile=window.matchMedia("(max-width:700px)").matches;const open=mobile ? document.body.classList.contains("sidebar-open") : !document.body.classList.contains("sidebar-collapsed");$("sidebar").inert=!open;$("show-sidebar").setAttribute("aria-expanded",String(open));$("close-sidebar").hidden=!mobile || !open;}
function setSidebar(open){if(window.matchMedia("(max-width:700px)").matches)document.body.classList.toggle("sidebar-open",open);else document.body.classList.toggle("sidebar-collapsed",!open);syncSidebar();}
$("show-sidebar").addEventListener("click",()=>{setSidebar(true);$("hide-sidebar").focus();});
$("hide-sidebar").addEventListener("click",()=>{setSidebar(false);$("show-sidebar").focus();});
$("close-sidebar").addEventListener("click",()=>{setSidebar(false);$("show-sidebar").focus();});
window.addEventListener("resize",syncSidebar);
document.addEventListener("keydown",event=>{if(event.key==="Escape" && document.body.classList.contains("sidebar-open")){setSidebar(false);$("show-sidebar").focus();}if(event.key==="Tab" && window.matchMedia("(max-width:700px)").matches && document.body.classList.contains("sidebar-open")){const controls=[...$("sidebar").querySelectorAll('button:not([disabled])')];const first=controls[0],last=controls.at(-1);if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}}});
$("commands-toggle").addEventListener("click",()=>{const hidden=!$("command-hint").hidden;$("command-hint").hidden=hidden;$("commands-toggle").setAttribute("aria-expanded",String(!hidden));});
function resizePrompt(){$("prompt").style.height="auto";$("prompt").style.height=Math.min($("prompt").scrollHeight,window.matchMedia("(max-width:700px)").matches ? 125 : 160)+"px";}
$("prompt").addEventListener("input",resizePrompt);
syncSidebar();
