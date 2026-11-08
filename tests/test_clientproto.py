"""TinyBox client protocol on the mailbox side (//CLIENT, TBCHAT events)."""

from __future__ import annotations

import unittest

from prcore.release import RELEASE
from tinybox import clientnews
from tinybox.session import Session, State
from tests.test_chat import chat_app
from tests.test_tinybox import FakeTransport, login, type_lines


def radio_login(app, call):
    t = FakeTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio")
    s.start()
    t.take()
    return s, t


class ClientProtoTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.ui = []
        self.app.service.chat.ui_send = lambda dest, text: self.ui.append((dest, text))

    def test_handshake_telnet_has_no_ui(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, f"//CLIENT TB1 v={clientnews.client_version()} caps=CHAT,UI,FOO sym=/-")
        out = t.take()
        self.assertTrue(out.startswith("\r//OK TB1 caps=CHAT\r"), out)
        self.assertNotIn("TinyBox (", out)            # no prompt in client mode
        self.assertEqual(s.client.symbol, "/-")

    def test_handshake_radio_ui_and_bad_symbol(self):
        s, t = radio_login(self.app, "OE3ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT,UI sym=xx")
        self.assertIn("//OK TB1 caps=CHAT,UI", t.take())
        self.assertEqual(s.client.symbol, "")

    def test_tb_probe_answers_and_changes_nothing(self):
        """CR76: //TB? gets one line, the session stays a terminal session."""
        s, t = radio_login(self.app, "OE3ABC")
        type_lines(s, "//TB? CLIENT v=2026.11.07 caps=PROF,HEARD")
        out = t.take()
        self.assertIn(f"//TB BOX v={RELEASE} call={self.app.cfg.station.mailbox_call}", out)
        self.assertIsNone(s.client)
        self.assertEqual(s.state, State.COMMAND)

    def test_tb_probe_keeps_profile_questions(self):
        """CR76: //TB? while the profile questions are up: answered, asked again."""
        s, t = radio_login(self.app, "OE3ABC")
        s._ask_fields, s._ask_answers = ["name"], {}
        s._ask_next()
        t.take()
        type_lines(s, "//TB?")
        out = t.take()
        self.assertIn("//TB BOX", out)
        self.assertEqual(s.state, State.PROFILE)

    def test_wrong_proto_and_not_client(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, "//BOARDS")
        self.assertIn("//ERR", t.take())
        type_lines(s, "//CLIENT TB9")
        self.assertIn("//ERR protocol", t.take())
        self.assertIsNone(s.client)

    def test_boards(self):
        s, t = login(self.app, "OE3ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT")
        t.take()
        type_lines(s, "//BOARDS")
        self.assertEqual(t.take(), "//B 1 TREFF 7d 0 Meeting point\r"
                                   "//B 2 RUNDE live 0 Live only\r//BEND\r")

    def test_ui_chat_flow(self):
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF", "vorher")
        tt.take()
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT,UI sym=/-")
        ct.take()
        type_lines(c, "C 1")
        out = ct.take().split("\r")
        self.assertRegex(out[0], r"^//IN 1 TREFF 7d 1 hist=1 last=\d+ now=\d+$")  # 0 = join, 1 = 'vorher'
        # a client without v= (older than CR13) still gets the history at once
        self.assertTrue(out[1].startswith("//H ") and out[1].endswith(" OE3XYZ: vorher"))
        self.assertEqual(out[2], "//WHO OE3XYZ")
        self.assertEqual(self.ui[-1], ("TBCHAT-1", "#2 +2 OE3GAS /-"))   # UI: member numbers (CR33)
        self.assertEqual(out[3], "#2 +OE3GAS /-")              # no NUM cap: old form as I-frame
        self.assertIn("*** OE3GAS joined TREFF", tt.take())
        self.assertEqual(c.state, State.CHAT)
        # terminal user speaks: one UI frame, the UI client gets no I-frame
        type_lines(term, "Servus :+1")
        self.assertEqual(self.ui[-1], ("TBCHAT-1", "#3 OE3XYZ: Servus :+1"))
        self.assertEqual(ct.take(), "")
        # client speaks and reacts
        type_lines(c, "Hallo ~0A", "/R 3 :+1")
        self.assertEqual(self.ui[-2:], [("TBCHAT-1", "#4 OE3GAS: Hallo ~0A"),
                                        ("TBCHAT-1", "#5 OE3GAS *3 :+1")])
        out = tt.take()
        self.assertIn("OE3GAS: Hallo ~0A", out)
        self.assertIn("*** OE3GAS :+1 to: OE3XYZ: Servus :+1", out)
        # resend, only to the client, as I-frames
        type_lines(c, "//RESEND 3-4")
        self.assertEqual(ct.take(), "#3 OE3XYZ: Servus :+1\r#4 OE3GAS: Hallo ~0A\r")
        type_lines(c, "/Q")
        self.assertEqual(ct.take(), "//OUT TREFF\r")
        self.assertIn("*** OE3GAS left TREFF", tt.take())

    def test_history_on_request(self):
        """CR13: a current client gets only hist=/last= and asks with //HIST."""
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF", *[f"z{i}" for i in range(7)], "/Q")
        c, ct = login(self.app, "OE3GAS")
        type_lines(c, f"//CLIENT TB1 v={clientnews.client_version()} caps=CHAT")
        ct.take()
        type_lines(c, "C 1")
        out = ct.take().split("\r")
        self.assertRegex(out[0], r"^//IN 1 TREFF 7d \S+ hist=7 last=\d+ now=\d+$")
        self.assertFalse(any(x.startswith("//H ") for x in out))
        # newest 3, 4 older left
        type_lines(c, "//HIST max=3")
        out = ct.take().split("\r")
        self.assertEqual([x.rsplit(" ", 1)[1] for x in out[:3]], ["z4", "z5", "z6"])
        self.assertEqual(out[3], "//HEND 3 4")
        # older than z4: at most history_lines (5) per request
        t4 = out[0].split()[1]
        type_lines(c, f"//HIST max=200 before={t4}")      # all in the same second here:
        out = ct.take().split("\r")                        # inclusive, nothing lost
        self.assertEqual(len(out), 7)                       # 5 lines, //HEND, ""
        self.assertEqual(out[5], "//HEND 5 2")
        # since: only newer lines; nothing newer -> 0 lines, all 7 are "older"
        type_lines(c, "//HIST max=20 since=4102444800")          # year 2100
        self.assertEqual(ct.take(), "//HEND 0 7\r")
        type_lines(c, "//HIST max=x")
        self.assertIn("//ERR hist", ct.take())

    def test_history_with_event_numbers(self):
        """HSEQ: //H lines carry the event number, so a quote finds its line."""
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF", "eins", "zwei", "/Q")
        c, ct = login(self.app, "OE3GAS")
        type_lines(c, f"//CLIENT TB1 v={clientnews.client_version()} caps=CHAT,HSEQ")
        ct.take()
        type_lines(c, "C 1")
        ct.take()
        type_lines(c, "//HIST max=5")
        out = ct.take().split("\r")
        self.assertRegex(out[0], r"^//H \d+ #[0-9A-F]{1,2} OE3XYZ: eins$")
        n1 = int(out[0].split()[2][1:], 16)
        n2 = int(out[1].split()[2][1:], 16)
        self.assertEqual((n1 + 1) % 256, n2)
        # without HSEQ the old form (older clients would drop the line otherwise)
        d, dt = login(self.app, "OE1ABC")
        type_lines(d, f"//CLIENT TB1 v={clientnews.client_version()} caps=CHAT")
        dt.take()
        type_lines(d, "C 1")
        dt.take()
        type_lines(d, "//HIST max=5")
        self.assertRegex(dt.take().split("\r")[0], r"^//H \d+ OE3XYZ: eins$")

    def test_symbol_change_at_once(self):
        """CR7: a new APRS symbol reaches the board at once, terminals get nothing."""
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT,UI sym=/-", "C 1")
        other, ot = login(self.app, "OE3TEC")             # client without UI (I-frames)
        type_lines(other, "//CLIENT TB1 caps=CHAT", "C 1")
        tt.take(); ct.take(); ot.take()
        type_lines(c, "//SYM /k")
        self.assertEqual(self.ui[-1][1].split(" ", 1)[1], "=2 /k")
        self.assertTrue(ot.take().endswith("=OE3GAS /k\r"))
        self.assertTrue(ct.take().endswith("=OE3GAS /k\r"))    # old UI client: I-frame copy
        self.assertEqual(tt.take(), "")                    # nothing for terminal users
        self.assertEqual(c.client.symbol, "/k")
        n = len(self.ui)
        type_lines(c, "//SYM /k")                          # unchanged: no event
        self.assertEqual(len(self.ui), n)
        type_lines(c, "//SYM -")                           # none
        self.assertEqual(self.ui[-1][1].split(" ", 1)[1], "=2")
        type_lines(c, "//SYM xx")
        self.assertIn("//ERR sym", ct.take())
        # outside a board: only remembered, the next join carries it
        type_lines(c, "/Q", "//SYM />", "C 1")
        self.assertEqual(self.ui[-1][1].split(" ", 1)[1], "+2 OE3GAS />")   # 2 was free again

    def test_member_numbers(self):
        """CR33: NUM clients get member numbers in //WHO and the events, //OK tells
        the bar settings; numbers are the lowest free ones and come back."""
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")                       # member 1
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 v=2026.10.13.2 caps=CHAT,UI,NUM sym=/-")
        ok = ct.take()
        self.assertIn("caps=CHAT,NUM,UI", ok)
        self.assertIn(" q=50/30/20/5,10,20,35,50", ok)
        type_lines(c, "C 1")
        out = ct.take().split("\r")
        self.assertEqual(out[1], "//WHO 1 OE3XYZ")
        self.assertEqual(self.ui[-1][1], "#1 +2 OE3GAS /-")
        self.assertEqual(out[2:], [""])                   # UI client with NUM: no I-frame copy
        old, ot = login(self.app, "OE3TEC")               # client without NUM, no UI
        type_lines(old, "//CLIENT TB1 caps=CHAT", "C 1")
        self.assertEqual(self.ui[-1][1], "#2 +3 OE3TEC")
        self.assertTrue(ot.take().endswith("//WHO OE3XYZ OE3GAS=/-\r#2 +OE3TEC\r"))
        type_lines(term, "/Q")                            # member 1 leaves
        self.assertEqual(self.ui[-1][1], "#3 -1")
        self.assertTrue(ot.take().endswith("#3 -OE3XYZ\r"))
        type_lines(term, "C TREFF")                       # gets 1 again
        self.assertEqual(self.ui[-1][1], "#4 +1 OE3XYZ")
        self.assertEqual(self.app.service.chat.member_no("TREFF", "OE3TEC"), 3)
        tt.take(); ct.take(); ot.take()
        type_lines(old, "//RESEND 3-4")                   # old client: old form
        self.assertEqual(ot.take(), "#3 -OE3XYZ\r#4 +OE3XYZ\r")

    def test_non_ui_client_gets_iframes_incl_own(self):
        c, ct = login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT")
        type_lines(c, "C RUNDE")
        ct.take()
        type_lines(c, "test")
        self.assertEqual(ct.take(), "#1 OE3GAS: test\r")
        self.assertEqual(self.ui, [])                 # nobody needs UI

    def test_restart_in_board_gets_in_without_anybody_hearing_it(self):
        """The client restarts while the link stays up: the session is still in
        the board, so //CLIENT is answered with //IN and //WHO - and the other
        members hear nothing (no leave, no join)."""
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT,UI sym=/-", "C 1")
        ct.take(), tt.take(), self.ui.clear()
        seq_before = self.app.service.chat._seq["TREFF"]

        type_lines(c, f"//CLIENT TB1 v={clientnews.client_version()} caps=CHAT,UI,NUM sym=/-")
        out = ct.take().split("\r")
        self.assertEqual(out[0], "")                      # the answer starts on a fresh line
        self.assertTrue(out[1].startswith("//OK TB1 "), out[1])
        self.assertRegex(out[2], r"^//IN 1 TREFF 7d \S+ hist=\d+( last=\d+)? now=\d+$")
        self.assertEqual(out[3], "//WHO 1 OE3XYZ 2 OE3GAS=/-")  # with us: we never left
        self.assertEqual(tt.take(), "")                   # the terminal user hears nothing
        self.assertEqual(self.ui, [])                     # and nothing goes out over UI
        self.assertEqual(self.app.service.chat._seq["TREFF"], seq_before)   # no event
        self.assertEqual(c.chat_board, "TREFF")
        self.assertEqual(c.state, State.CHAT)
        # and the client is live again: it speaks, the others hear it
        type_lines(c, "wieder da")
        self.assertIn("OE3GAS: wieder da", tt.take())

    def test_mailbox_command_from_a_client_is_not_chat(self):
        """An older client sends "C <n>" into the board after a restart. That
        must not land in the chat: the same board answers with //IN, another
        board is entered."""
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT", "C 1")
        ct.take(), tt.take()

        type_lines(c, "C 1")                      # the board it is already in
        self.assertTrue(ct.take().startswith("//IN 1 TREFF "))
        self.assertEqual(tt.take(), "")           # nobody saw a "C 1"
        type_lines(c, "C")                        # bare, without a board
        self.assertTrue(ct.take().startswith("//IN 1 TREFF "))
        self.assertEqual(tt.take(), "")
        # a terminal user in a board still says what it types
        type_lines(term, "C 1")
        self.assertIn("OE3XYZ: C 1", ct.take())
        type_lines(c, "C 2")                      # a different board: a real change
        self.assertTrue(ct.take().startswith("//IN 2 RUNDE "))
        self.assertEqual(c.chat_board, "RUNDE")
        self.assertIn("*** OE3GAS left TREFF", tt.take())

    def test_seq_wraps_and_board_over_15_has_no_ui(self):
        hub = self.app.service.chat
        hub._seq["TREFF"] = 0xFE
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT,UI", "C 1", "a")
        self.assertEqual([x[1] for x in self.ui], ["#FF +1 OE3GAS", "#0 OE3GAS: a"])
        self.assertEqual(hub.replay("TREFF", 0xFF, 0x0), ["#FF +1 OE3GAS", "#0 OE3GAS: a"])
        self.assertEqual(hub.replay("TREFF", 0xFF, 0x0, legacy=True),
                         ["#FF +OE3GAS", "#0 OE3GAS: a"])
        hub.boards[0:0] = [type(hub.boards[0])(f"B{i}", 1) for i in range(15)]
        self.ui.clear()
        type_lines(c, "b")          # TREFF is board 16 now
        self.assertEqual(self.ui, [])
        self.assertIn("OE3GAS: b", ct.take())


class MailNotifyTests(unittest.TestCase):
    def setUp(self):
        from tinybox import notify
        self.app = chat_app()
        self.ui = []
        self.app.service.chat.ui_send = lambda dest, text: self.ui.append((dest, text))
        self.n = notify.MailNotifier(self.app)

    def mail(self, to, type="P", **kw):
        return self.app.service.create(from_call="OE3XYZ", to_call=to, type=type,
                                       subject="s", body="b", origin="telnet", **kw)

    def test_private_mail_once_per_minute(self):
        self.mail("OE3ABC-7")
        self.assertEqual(self.ui, [("TBMAIL", "OE3ABC 1 new")])
        self.mail("OE3ABC")                   # within the minute, no loop: not repeated
        self.assertEqual(len(self.ui), 1)
        self.mail("OE1DEF")
        self.assertEqual(self.ui[-1], ("TBMAIL", "OE1DEF 1 new"))

    def test_no_bulletins_and_switch_off(self):
        self.mail("ALL", type="B")
        self.assertEqual(self.ui, [])
        self.app.cfg.client.mail_notify = False
        self.mail("OE3ABC")
        self.assertEqual(self.ui, [])

    def test_example_config(self):
        self.assertTrue(self.app.cfg.client.mail_notify)


if __name__ == "__main__":
    unittest.main()
