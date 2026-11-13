import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from sexta_feira.storage import Storage
from sexta_feira.tools import execute_chat_command


class NaturalToolTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.storage=Storage(Path(self.directory.name)/"memory.sqlite3")
        self.research=Mock(side_effect=AssertionError("Local operations must not be searched"))

    def call(self,message,**kwargs):
        return execute_chat_command(message,self.storage,research_reader=self.research,**kwargs)

    def test_natural_read_requests_are_deterministic_and_never_sent_to_research(self):
        cases={
            "system_time":["Que horas são?","Que dia é hoje?","Qual é a data de hoje?","Sexta-feira, por favor, que horas são?","Mostre a data e hora, por favor."],
            "list_tasks":["Mostre minhas tarefas","Liste minhas tarefas","Quais são as minhas tarefas?","Minhas tarefas"],
            "list_memories":["Mostre minhas memórias","Liste minhas memorias","O que está salvo na memória?"],
            "server_temperatures":["Qual a temperatura da CPU?","Mostre os sensores do servidor"],
            "server_hardware":["Como está o servidor?","Qual o uso de RAM da VPS?"],
        }
        with patch("sexta_feira.tools.research_request",side_effect=AssertionError("Research priority is wrong")):
            for name,messages in cases.items():
                for message in messages:
                    with self.subTest(message=message):
                        result=self.call(message)
                        self.assertEqual(result['tool'],name)
                        self.assertEqual(result['source'],'tool')
                        self.assertFalse(result['generated'])
                        self.assertTrue(result['action_executed'])
        self.research.assert_not_called()

    def test_natural_tasks_persist_exact_user_content(self):
        cases=[("Crie uma tarefa: Comprar pão amanhã","Comprar pão amanhã"),
               ("Adicione uma tarefa para revisar o contrato","revisar o contrato"),
               ("Por favor, registre uma nova tarefa: Conferir os pneus","Conferir os pneus"),
               ("Quero que você crie uma tarefa: Testar a API","Testar a API"),
               ("Crie uma tarefa: Não esquecer o capacete","Não esquecer o capacete"),
               ("Crie uma tarefa: verificar se o site responde","verificar se o site responde")]
        for message,content in cases:
            result=self.call(message)
            self.assertEqual(result['tool'],'create_task')
            self.assertIn(content,result['reply'])
        self.assertEqual({item['content'] for item in self.storage.tasks()},{content for _,content in cases})
        self.research.assert_not_called()

    def test_natural_memories_only_save_explicitly_requested_facts(self):
        cases=[("Lembre que meu nome é Davi","meu nome é Davi"),
               ("Memorize que eu não gosto de café","eu não gosto de café"),
               ("Salve uma memória: prefiro respostas curtas","prefiro respostas curtas"),
               ("Guarde na memória: sou o criador","sou o criador"),
               ("Preciso que você lembre que trabalho com bicicletas","trabalho com bicicletas")]
        for message,content in cases:
            result=self.call(message)
            self.assertEqual(result['tool'],'save_memory')
            self.assertIn(content,result['reply'])
        self.assertEqual({item['content'] for item in self.storage.memories()},{content for _,content in cases})
        self.research.assert_not_called()

    def test_quoted_negative_hypothetical_and_ambiguous_messages_never_write(self):
        messages=[
            '"Crie uma tarefa: comprar pão"',
            "'Lembre que meu nome é Davi'",
            "`Crie uma tarefa: comprar pão`",
            "> Lembre que meu nome é Davi",
            "Não crie uma tarefa: comprar pão",
            "Por favor, não salve uma memória: sou o criador",
            "Se eu pedir para criar uma tarefa, o que acontece?",
            "Explique como criar uma tarefa: comprar pão",
            "Diga literalmente: Lembre que meu nome é Davi",
            "Crie uma tarefa se eu pedir amanhã",
            "Crie uma tarefa: comprar pão, mas não salve nada",
            "Crie uma tarefa: comprar pão e salve uma memória: gosto de café",
            "Lembra que meu nome é Davi?",
            "Lembre de comprar pão",
            "Salve isso",
            "Eu sou o criador",
            "Crie uma tarefa: comprar pão\nNão salve ainda",
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertIsNone(self.call(message,auto_research=False))
                self.assertEqual(self.storage.tasks(),[])
                self.assertEqual(self.storage.memories(),[])
        self.research.assert_not_called()

    def test_command_like_payload_is_data_not_a_second_executed_action(self):
        result=self.call("Crie uma tarefa: estudar o comando /lembrar e o script backup.ps1")
        self.assertEqual(result['tool'],'create_task')
        self.assertEqual(len(self.storage.tasks()),1)
        self.assertEqual(self.storage.memories(),[])

    def test_limits_and_legacy_commands_remain_validated(self):
        with self.assertRaises(ValueError):self.call('Crie uma tarefa: '+('x'*481))
        self.assertEqual(self.storage.tasks(),[])
        legacy={"/hora":"system_time","/tarefas":"list_tasks","/memorias":"list_memories",
                "/tarefa Comprar pão":"create_task","/lembrar Gosto de café":"save_memory",
                "/hardware":"server_hardware","/cpu":"server_hardware","/ram":"server_hardware",
                "/temperaturas":"server_temperatures"}
        for message,name in legacy.items():
            self.assertEqual(self.call(message)['tool'],name)
        with self.assertRaises(ValueError):self.call('/hora now')
        with self.assertRaises(ValueError):self.call('/reiniciar_servidor')
        with self.assertRaises(ValueError):self.call(None)
        with self.assertRaises(ValueError):self.call('Olá',auto_research='yes')

    def test_auto_research_flag_is_forwarded_after_local_routing(self):
        with patch('sexta_feira.tools.research_request',return_value=None) as lookup:
            self.assertIsNone(self.call('Olá'))
            lookup.assert_called_once_with('Olá',auto=True)
            lookup.reset_mock()
            self.assertIsNone(self.call('Conte uma história',auto_research=False))
            lookup.assert_called_once_with('Conte uma história',auto=False)
        result={'reply':'Sources','source':'tool','generated':False,'tool':'web_research'}
        reader=Mock(return_value=result)
        answer=execute_chat_command('/pesquisar documentação SQLite',self.storage,
                                    research_reader=reader,auto_research=False)
        self.assertEqual(answer,result)
        reader.assert_called_once_with(query='documentação SQLite')
