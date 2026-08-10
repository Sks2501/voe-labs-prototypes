/**
 * VOE LAB — simulador público de telemetria.
 * Gera somente dados fictícios no terminal.
 * Não acessa rede, Bluetooth, serial, arquivos ou dispositivos.
 */
const vehicles = ["VOE-DEMO-01", "VOE-DEMO-02", "VOE-DEMO-03"];
const zones = ["Estação Coral", "Praça Demo", "VOE LAB"];
let sequence = 0;

function eventFor(vehicleId, index) {
  const battery = Math.max(20, 96 - ((sequence * 3 + index * 7) % 72));
  return {
    schema: "voe.lab.telemetry.demo.v1",
    sequence,
    vehicleId,
    recordedAt: new Date().toISOString(),
    batteryPercent: battery,
    status: battery < 30 ? "maintenance-demo" : "available-demo",
    zone: zones[(sequence + index) % zones.length],
    coordinates: {
      latitude: -22.9000 + index * 0.001,
      longitude: -43.1800 - index * 0.001,
      precision: "synthetic"
    }
  };
}

function tick() {
  for (const [index, vehicleId] of vehicles.entries()) {
    console.log(JSON.stringify(eventFor(vehicleId, index)));
  }
  sequence += 1;
}

console.log("VOE LAB telemetry demo — pressione Ctrl+C para encerrar.");
tick();
setInterval(tick, 3000);
