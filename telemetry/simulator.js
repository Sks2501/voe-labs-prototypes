/**
 * VOE LAB — simulador público de telemetria v2.
 *
 * Garantias deliberadas de segurança:
 * - gera somente dados sintéticos;
 * - não acessa rede;
 * - não acessa Bluetooth;
 * - não acessa UART/serial;
 * - não lê arquivos locais;
 * - não envia comandos;
 * - não controla dispositivos.
 */

"use strict";

const SCHEMA = "voe.lab.telemetry.demo.v1";
const SOURCE = "local-simulator";
const INTERVAL_MS = 3000;

const vehicles = Object.freeze([
  Object.freeze({ id: "VOE-DEMO-01", model: "LAB-SCOOTER-A", zone: "Estação Coral" }),
  Object.freeze({ id: "VOE-DEMO-02", model: "LAB-SCOOTER-A", zone: "Praça Demo" }),
  Object.freeze({ id: "VOE-DEMO-03", model: "LAB-SCOOTER-B", zone: "VOE LAB" })
]);

const eventTypes = Object.freeze([
  "heartbeat.demo",
  "battery.sample.demo",
  "position.sample.demo",
  "state.sample.demo"
]);

let sequence = 0;
let eventCounter = 0;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function pad(value, width) {
  return String(value).padStart(width, "0");
}

function nextEventId() {
  eventCounter += 1;
  return `evt_demo_${pad(eventCounter, 6)}`;
}

function batteryFor(index) {
  const oscillation = (sequence * 3 + index * 11) % 77;
  return clamp(96 - oscillation, 19, 96);
}

function statusFor(batteryPercent, index) {
  if (batteryPercent < 25) {
    return "maintenance-demo";
  }

  if ((sequence + index) % 17 === 0) {
    return "charging-demo";
  }

  if ((sequence + index) % 29 === 0) {
    return "offline-demo";
  }

  return "available-demo";
}

function coordinatesFor(index) {
  const drift = (sequence % 10) * 0.00001;

  return Object.freeze({
    latitude: Number((-22.9 + index * 0.001 + drift).toFixed(6)),
    longitude: Number((-43.18 - index * 0.001 - drift).toFixed(6)),
    precision: "synthetic"
  });
}

function baseEvent(vehicle, eventType) {
  return {
    schema: SCHEMA,
    eventId: nextEventId(),
    eventType,
    sequence,
    vehicleId: vehicle.id,
    recordedAt: new Date().toISOString(),
    source: SOURCE
  };
}

function buildEvent(vehicle, index, eventType) {
  const batteryPercent = batteryFor(index);
  const status = statusFor(batteryPercent, index);
  const event = baseEvent(vehicle, eventType);

  switch (eventType) {
    case "heartbeat.demo":
      return {
        ...event,
        payload: {
          model: vehicle.model,
          status,
          zone: vehicle.zone
        }
      };

    case "battery.sample.demo":
      return {
        ...event,
        payload: {
          batteryPercent,
          status,
          zone: vehicle.zone
        }
      };

    case "position.sample.demo":
      return {
        ...event,
        payload: {
          status,
          zone: vehicle.zone,
          coordinates: coordinatesFor(index)
        }
      };

    case "state.sample.demo":
      return {
        ...event,
        payload: {
          batteryPercent,
          status,
          zone: vehicle.zone,
          coordinates: coordinatesFor(index)
        }
      };

    default:
      throw new Error(`Tipo de evento demonstrativo não suportado: ${eventType}`);
  }
}

function validateEvent(event) {
  if (event.schema !== SCHEMA) {
    throw new Error("Schema demonstrativo inválido.");
  }

  if (!/^evt_demo_[0-9]{6}$/.test(event.eventId)) {
    throw new Error("eventId demonstrativo inválido.");
  }

  if (!eventTypes.includes(event.eventType)) {
    throw new Error("eventType demonstrativo inválido.");
  }

  if (!Number.isInteger(event.sequence) || event.sequence < 0) {
    throw new Error("Sequência demonstrativa inválida.");
  }

  if (!/^VOE-DEMO-[0-9]{2}$/.test(event.vehicleId)) {
    throw new Error("vehicleId demonstrativo inválido.");
  }

  if (event.source !== SOURCE) {
    throw new Error("Fonte demonstrativa inválida.");
  }

  if (Number.isNaN(Date.parse(event.recordedAt))) {
    throw new Error("Timestamp demonstrativo inválido.");
  }

  if (typeof event.payload !== "object" || event.payload === null || Array.isArray(event.payload)) {
    throw new Error("Payload demonstrativo inválido.");
  }

  return true;
}

function emit(event) {
  validateEvent(event);
  process.stdout.write(`${JSON.stringify(event)}\n`);
}

function tick() {
  for (const [index, vehicle] of vehicles.entries()) {
    const eventType = eventTypes[(sequence + index) % eventTypes.length];
    emit(buildEvent(vehicle, index, eventType));
  }

  sequence += 1;
}

function shutdown(signal) {
  process.stderr.write(`VOE LAB telemetry demo encerrado por ${signal}.\n`);
  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

process.stderr.write(
  `VOE LAB telemetry demo v2 iniciado | schema=${SCHEMA} | intervalo=${INTERVAL_MS}ms | sem rede/hardware real\n`
);

tick();
setInterval(tick, INTERVAL_MS);
