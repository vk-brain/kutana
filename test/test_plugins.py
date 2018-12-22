from kutana import Plugin, Message, Attachment, DebugEnvironment
from test_framework import KutanaTest
import asyncio
import re


class TestPlugins(KutanaTest):
    def test_plugin_creation(self):
        plugin = Plugin(name="Name", cmds=["cmd1", "cmd2"])

        self.assertEqual(plugin.name, "Name")  # pylint: disable=E1101
        self.assertEqual(plugin.cmds, ["cmd1", "cmd2"])  # pylint: disable=E1101

        plugin = Plugin(priority=1000)

    def test_echo_plugin(self):
        queue = ["message", "echo message", "echonotecho"]

        self.target = ["message"]

        with self.debug_manager(queue) as plugin:

            async def on_echo(message, env):
                await env.reply(env.meta["body"])

            plugin.on_startswith_text("echo ", "echo\n")(on_echo)

    def test_plugin_on_startup(self):
        self.called = 0

        with self.debug_manager(["message"]) as plugin:

            async def on_startup(update, env):
                self.called += 1

            plugin.on_startup()(on_startup)

        self.assertEqual(self.called, 1)

    def test_plugin_register_special(self):
        self.answers = []

        with self.debug_manager(["message"]) as plugin:

            async def cb_1(update, env):
                self.answers.append(1)

            async def cb_2(update, env):
                self.answers.append(2)

            async def cb_3(update, env):
                self.answers.append(3)

            plugin.register_special()(cb_1)
            plugin.register_special(cb_2, early=True)
            plugin.register_special(cb_3)

        self.assertEqual(self.answers, [2, 1, 3])

    def test_plugin_register_special_two_plugins(self):
        self.answers = []

        with self.debug_manager(["message"]) as plugin1:

            plugin2 = Plugin(priority=500)

            self.plugins.append(plugin2)

            async def cb_1(update, env):
                self.answers.append(1)

            async def cb_2(update, env):
                self.answers.append(2)

            async def cb_3(update, env):
                self.answers.append(3)

            plugin1.register_special()(cb_1)
            plugin1.register_special(cb_2, early=True)
            plugin2.register_special(cb_3)

        self.assertEqual(self.answers, [2, 3, 1])

    def test_args_on_startswith_text(self):
        queue = ["pr a b c", "pr a \"b c\"", "pr ab c"]

        queue_answer = [
            ["a", "b", "c"], ["a", "\"b", "c\""], ["ab", "c"]
        ]

        with self.debug_manager(queue) as plugin:

            async def on_startswith_text(message, env):
                self.assertEqual(env.meta["args"], queue_answer.pop(0))

            plugin.on_startswith_text("pr")(on_startswith_text)

        self.assertFalse(queue_answer)

    def test_plugins_callbacks_done(self):
        self.counter = 0

        with self.debug_manager(["123"]) as plugin:

            async def on_has_text(message, env):
                self.counter += 1

                return "DONE"

            plugin.on_has_text("123")(on_has_text)

            async def on_has_text_2(message, env):
                self.counter += 1

            plugin.on_has_text("123")(on_has_text_2)

        self.assertEqual(self.counter, 1)

    def test_plugins_callbacks_not_done(self):
        self.counter = 0

        with self.debug_manager(["123"]) as plugin:

            async def on_has_text(message, env):
                self.counter += 1

                return "GOON"

            plugin.on_has_text("123")(on_has_text)

            async def on_has_text_2(message, env):
                self.counter += 1

            plugin.on_has_text("123")(on_has_text_2)

        self.assertEqual(self.counter, 2)

    def test_multiple_plugins(self):
        self.counter = 0

        with self.debug_manager(["message"]):

            self.plugins.append(Plugin())
            self.plugins.append(Plugin())

            async def on_has_text(message, env):
                self.counter += 1

                self.assertNotIn("key", env.meta)
                env.meta["key"] = "value"

                return "GOON"

            for pl in self.plugins:
                pl.on_has_text()(on_has_text)

        self.assertEqual(self.counter, 3)

    def test_early_callbacks(self):
        self.answers = []

        with self.debug_manager(["message"]):

            self.plugins.append(Plugin())

            async def on_has_text_early(message, env):
                self.answers.append("early")

                return "GOON"

            async def on_has_text(message, env):
                self.answers.append("late")

            for pl in self.plugins:
                pl.on_has_text()(on_has_text)
                pl.on_has_text(early=True)(on_has_text_early)

        self.assertEqual(self.answers, ["early", "early", "late"])

    def test_early_callbacks_raw(self):
        self.answers = []

        with self.debug_manager([None]):

            self.plugins.append(Plugin())

            async def on_raw_early(update, env):
                self.answers.append("early")

                return "GOON"

            async def on_raw(update, env):
                self.answers.append("late")

            for pl in self.plugins:
                pl.on_raw()(on_raw)
                pl.on_raw(early=True)(on_raw_early)

        self.assertEqual(self.answers, ["early", "early", "late"])

    def test_plugin_callbacks(self):
        self.disposed = 0
        self.counter = 0

        with self.debug_manager(["123", "321"]) as plugin:
            async def on_123(message, env):
                self.assertEqual(message.text, "123")
                self.counter += 1

            plugin.on_text("123")(on_123)


            async def on_everything(message, env):
                self.assertNotEqual(message.text, "123")
                self.counter += 1

            plugin.on_has_text()(on_everything)


            async def on_raw(update, env):
                raise RuntimeError

            plugin.on_raw()(on_raw)


            async def on_dispose():
                self.disposed += 1

            plugin.on_dispose()(on_dispose)

        self.assertEqual(self.counter, 2)
        self.assertEqual(self.disposed, 1)

    def test_environment_reply(self):
        self.target = ["echo message"]

        with self.debug_manager(self.target) as plugin:

            async def on_echo(message, env):
                await env.reply(message.text)

            plugin.on_startswith_text("echo")(on_echo)

    def test_environments(self):
        self.target = ["echo message"]

        with self.debug_manager(self.target):

            plugin1 = Plugin()
            plugin2 = Plugin()

            self.plugins = (plugin1, plugin2)

            async def do_skip(message, env):
                env.meta["A"] = "A"
                env.parent_environment.meta["B"] = "B"

                return "GOON"

            async def do_check_one(message, env):
                self.assertEqual(env.meta.get("A"), "A")

                return "GOON"

            plugin1.on_has_text()(do_skip)
            plugin1.on_has_text()(do_check_one)

            async def do_check(message, env):
                self.assertIsNone(env.meta.get("A"))
                self.assertEqual(env.parent_environment.meta["B"], "B")

                await env.reply("echo message")

            plugin2.on_has_text()(do_check)

    def test_plugin_attachments_type(self):
        plugin = Plugin()

        decorator = plugin.on_attachment("photo")

        async def on_attachment(message, env):
            return "DONE"

        wrapper = decorator(on_attachment)

        attachments = [
            Attachment("audio", 0, 0, 0, 0, {}),
            Attachment("image", 0, 0, 0, 0, {})
        ]

        res = asyncio.get_event_loop().run_until_complete(
            wrapper(
                Message("", attachments, 0, 0, {}),
                DebugEnvironment(None, 0)
            )
        )

        self.assertEqual(res, None)

    def test_plugin_attachments(self):
        plugin = Plugin()

        decorator = plugin.on_attachment()

        async def on_attachment(message, env):
            return "DONE"

        wrapper = decorator(on_attachment)

        res = asyncio.get_event_loop().run_until_complete(
            wrapper(
                Message("no text", ("attachment"), 0, 0, {}),
                DebugEnvironment(None, 0)
            )
        )

        self.assertEqual(res, "DONE")

    def test_plugin_onstar(self):
        queue = ["привет", "отлично привет", "ecHo", "ab", "ae", "hello"]
        self.result = 0

        with self.debug_manager(queue) as plugin:

            async def no_trigger(message, env):
                self.assertTrue(False)

            plugin.on_attachment("photo", "audio")(no_trigger)


            async def zero_trigger(message, env):
                self.result |= 1 << 0

            plugin.on_has_text("привет")(zero_trigger)


            async def one_trigger(message, env):
                self.result |= 1 << 1

            plugin.on_regexp_text(r"a(b|c)")(one_trigger)


            async def two_trigger(message, env):
                self.result |= 1 << 2

            plugin.on_regexp_text(re.compile(r"a(e|z)"))(two_trigger)


            async def three_trigger(message, env):
                self.result |= 1 << 3

            plugin.on_startswith_text("hell")(three_trigger)


            async def four_trigger(message, env):
                self.result |= 1 << 4

            plugin.on_text("ecHo")(four_trigger)

        self.assertEqual(self.result, (1 << 5) - 1)
