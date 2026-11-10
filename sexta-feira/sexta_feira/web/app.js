"use strict";

const $ = (id) => document.getElementById(id);
let accessToken = "";
let busy = false;

function notice(message) { $("notice").textContent = message; }

function showConnected(connected) {
  $("status").textContent = connected ? "Conectada" : "Desconectada";
  $("status").classList.toggle("connected", connected);
}

async function request(path, body = null) {
  const options = {
    method: body === null ? "GET" : "POST",
    headers: { "X-Session-Token": accessToken }
  };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error("Resposta inválida do servidor."); }
  if (!response.ok) throw new Error(payload.error || "Falha na operação.");
  return payload;
}

function addMessage(role, content) {
  const article = document.createElement("article");
  article.className = "message " + (role === "user" ? "user" : "assistant");
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? "Você" : "SEXTA-FEIRA";
  const text = document.createElement("span");
  text.textContent = content;
  article.append(who, text);
  $("messages").appendChild(article);
  $("messages").scrollTop = $("messages").scrollHeight;
}

function renderHistory(history) {
  $("messages").replaceChildren();
  if (history.length === 0) addMessage("assistant", "Olá. Estou pronta para conversar localmente.");
  for (const item of history) addMessage(item.role, item.content);
}

function renderMemories(items) {
  $("memories").replaceChildren();
  for (const item of items) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = item.content;
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "Excluir";
    del.setAttribute("aria-label", "Excluir memória");
    del.addEventListener("click", async () => {
      try { await request("/api/memory/delete", { id: item.id }); await refresh(); }
      catch (error) { notice(error.message); }
    });
    li.append(label, del);
    $("memories").appendChild(li);
  }
}

function renderTasks(items) {
  $("tasks").replaceChildren();
  for (const item of items) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = item.content;
    if (item.completed) label.className = "done";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.textContent = item.completed ? "Reabrir" : "Concluir";
    toggle.addEventListener("click", async () => {
      try { await request("/api/task/toggle", { id: item.id }); await refresh(); }
      catch (error) { notice(error.message); }
    });
    li.append(label, toggle);
    $("tasks").appendChild(li);
  }
}

async function refresh() {
  const state = await request("/api/state");
  renderHistory(state.history);
  renderMemories(state.memories);
  renderTasks(state.tasks);
}

function speak(text) {
  if (!$("speak").checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "pt-BR";
  utterance.rate = 1.06;
  speechSynthesis.speak(utterance);
}

$("connect").addEventListener("click", async () => {
  accessToken = $("token").value.trim();
  if (!accessToken) { notice("Cole o token exibido pelo servidor."); return; }
  try {
    await refresh();
    showConnected(true);
    notice("Conexão local autorizada.");
    $("token").value = "";
  } catch (error) {
    accessToken = "";
    showConnected(false);
    notice(error.message);
  }
});

$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy || !accessToken) { notice("Conecte usando o token antes de conversar."); return; }
  const message = $("prompt").value.trim();
  if (!message) return;
  busy = true;
  $("send").disabled = true;
  $("prompt").value = "";
  addMessage("user", message);
  notice("Gerando resposta no processador. O GPT-2 pode demorar alguns segundos.");
  try {
    const result = await request("/api/chat", { message });
    addMessage("assistant", result.reply);
    speak(result.reply);
    await refresh();
    notice("Resposta gerada localmente.");
  } catch (error) {
    notice(error.message);
  } finally {
    busy = false;
    $("send").disabled = false;
    $("prompt").focus();
  }
});

$("memory-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await request("/api/memory", { content: $("memory").value });
    $("memory").value = "";
    await refresh();
    notice("Memória salva neste computador.");
  } catch (error) { notice(error.message); }
});

$("task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await request("/api/task", { content: $("task").value });
    $("task").value = "";
    await refresh();
    notice("Tarefa criada.");
  } catch (error) { notice(error.message); }
});

$("stop-speech").addEventListener("click", () => {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
});

$("prompt").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    $("chat-form").requestSubmit();
  }
});
