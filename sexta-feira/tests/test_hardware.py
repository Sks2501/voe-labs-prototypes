import unittest
from sexta_feira.hardware import hardware_snapshot, hardware_reply, is_hardware_request
from sexta_feira.observability import cpu_usage
from sexta_feira.tools import execute_chat_command, execute_tool


class HardwareTests(unittest.TestCase):
    def test_cpu_kernel_includes_idle_and_handles_first_or_invalid_sample(self):
        self.assertEqual(cpu_usage(160,260,140,(100,200,100)),40.0)
        self.assertIsNone(cpu_usage(160,260,140,None))
        self.assertIsNone(cpu_usage(100,200,100,(100,200,100)))
        self.assertIsNone(cpu_usage(99,210,110,(100,200,100)))

    def test_owner_snapshot_excludes_admin_inventory_and_credentials(self):
        result=hardware_snapshot({"cpu_model":"CPU","cpu_logical":4,"system_cpu_percent":12.5,
            "pid":42,"token":"secret","requests":99,"path":"private","ram_total_bytes":16*2**30,
            "ram_available_bytes":6*2**30}, {"status":"unavailable","readings":[]})
        self.assertEqual(set(result["resources"]),{"cpu_model","cpu_logical","system_cpu_percent","ram_total_bytes","ram_available_bytes"})
        self.assertNotIn("secret",str(result))
        reply=hardware_reply(result)
        self.assertIn("12.5%",reply)
        self.assertIn("10.00 GiB",reply)
        self.assertNotIn("normal",reply)

    def test_read_only_intent_bypasses_model_and_cannot_run_commands(self):
        data={"scope":"server","resources":{},"temperatures":{"status":"unavailable"}}
        for message in ("/hardware","/cpu","/ram","Como está o estado da máquina e api tudo certo e etc?","Qual o uso de RAM da VPS?"):
            result=execute_chat_command(message,None,hardware_reader=lambda:data)
            self.assertEqual(result["tool"],"server_hardware")
            self.assertFalse(result["generated"])
        for message in ("Escreva código para medir CPU", "Explique RAM", "Reinicie o servidor", "Oi"):
            self.assertFalse(is_hardware_request(message))
        with self.assertRaises(ValueError):execute_tool("server_hardware",{"command":"whoami"},None)
