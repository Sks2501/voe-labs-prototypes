/**
 * Systems Lab — simulador público e genérico de telemetria.
 * Gera somente dados sintéticos e não acessa rede, hardware ou arquivos privados.
 */

"use strict";

const SCHEMA = "systems.lab.telemetry.demo.v1";
const SOURCE = "local-simulator";
const INTERVAL_MS = 3000;

const resources = Object.freeze([
  Object.freeze({ id: "SYS-DEMO-01", model: "GENERIC-NODE-A", zone: "Zona Sintética A" }),
  Object.freeze({ id: "SYS-DEMO-02", model: "GENERIC-NODE-A", zone: "Zona Sintética B" }),
  Object.freeze({ id: "SYS-DEMO-03", model: "GENERIC-NODE-B", zone: "Zona Sintética C" })
]);

const eventTypes = Object.freeze([
  "heartbeat.demo",
  "metric.sample.demo",
  "position.sample.demo",
  "state.sample.demo"
]);

let sequence = 0;
let eventCounter = 0;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function nextEventId() {
  eventCounter += 1;
  return `evt_demo_${String(eventCounter).padStart(6, "0")}`;
}

function metricFor(index) {
  const oscillation = (sequence * 3 + index * 11) % 77;
  return clamp(96 - oscillation, 19, 96);
}

function statusFor(metricPercent, index) {
  if (metricPercent < 25) return "maintenance-demo";
  if ((sequence + index) % 17 === 0) return "busy-demo";
  if ((sequence + index) % 29 === 0) return "offline-demo";
  return "ready-demo";
}

function coordinatesFor(index) {
  const drift = (sequence % 10) * 0.00001;
  return Object.freeze({
    latitude: Number((-10 + index * 0.001 + drift).toFixed(6)),
    longitude: Number((-20 - index * 0.001 - drift).toFixed(6)),
    precision: "synthetic"
  });
}

function buildEvent(resource, index, eventType) {
  const metricPercent = metricFor(index);
  const status = statusFor(metricPercent, index);
  const base = {
    schema: SCHEMA,
    eventId: nextEventId(),
    eventType,
    sequence,
    resourceId: resource.id,
    recordedAt: new Date().toISOString(),
    source: SOURCE
  };

  switch (eventType) {
    case "heartbeat.demo":
      return { ...base, payload: { model: resource.model, status, zone: resource.zone } };
    case "metric.sample.demo":
      return { ...base, payload: { metricPercent, status, zone: resource.zone } };
    case "position.sample.demo":
      return { ...base, payload: { status, zone: resource.zone, coordinates: coordinatesFor(index) } };
    case "state.sample.demo":
      return { ...base, payload: { metricPercent, status, zone: resource.zone, coordinates: coordinatesFor(index) } };
    default:
      throw new Error(`Tipo de evento não suportado: ${eventType}`);
  }
}

function validateEvent(event) {
  if (event.schema !== SCHEMA) throw new Error("schema_invalido");
  if (!/^evt_demo_[0-9]{6}$/.test(event.eventId)) throw new Error("event_id_invalido");
  if (!eventTypes.includes(event.eventType)) throw new Error("event_type_invalido");
  if (!Number.isInteger(event.sequence) || event.sequence < 0) throw new Error("sequence_invalida");
  if (!/^SYS-DEMO-[0-9]{2}$/.test(event.resourceId)) throw new Error("resource_id_invalido");
  if (event.source !== SOURCE) throw new Error("source_invalido");
  if (Number.isNaN(Date.parse(event.recordedAt))) throw new Error("timestamp_invalido");
  if (typeof event.payload !== "object" || event.payload === null || Array.isArray(event.payload)) {
    throw new Error("payload_invalido");
  }
}

function emit(event) {
  validateEvent(event);
  process.stdout.write(`${JSON.stringify(event)}\n`);
}

function tick() {
  for (const [index, resource] of resources.entries()) {
    const eventType = eventTypes[(sequence + index) % eventTypes.length];
    emit(buildEvent(resource, index, eventType));
  }
  sequence += 1;
}

function shutdown(signal) {
  process.stderr.write(`simulador encerrado por ${signal}\n`);
  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

process.stderr.write(`Systems Lab simulator | schema=${SCHEMA} | intervalo=${INTERVAL_MS}ms | dados sintéticos\n`);
tick();
setInterval(tick, INTERVAL_MS);
