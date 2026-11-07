"""All user-facing (English) texts in one place.

Lines are joined with CR by the session; adapters translate line endings.
"""

from . import VERSION

BANNER = "TinyBox {version} - {mailbox}"
HELLO = "Welcome to TinyBox {mailbox}, hello {call}."
NEW_MSGS = "You have {n} new message(s)."
NO_NEW_MSGS = "No new messages."

PROMPT = "TinyBox (A,B,C,F,H,J,K,L,R,S,V,?) > "
PROMPT_SYSOP = "TinyBox SYSOP (A,B,C,E,H,J,K,L,R,S,V,?) > "

HELP = [
    "TinyBox commands:",
    "  A          Abort output (stop a long list or message)",
    "  B          Bye (log off)",
    "  C          Chat: list the chat boards",
    "  C board    Chat: join a board (name or number)",
    "  DICT       Download the brocast dictionary (text, for the listener import)",
    "  F text     Find messages with text in subject, text or calls (FIND text)",
    "  H or ?     This help",
    "  I call     Profile of a station: name, locator, home BBS (I: your own)",
    "  J          Recently connected stations",
    "  K n        Kill message n (K n n ... for several)",
    "  KM         Kill all read messages to you",
    "  L          List messages",
    "             TS = Type (P private, B bulletin) + Status (N new, Y read)",
    "             3rd letter: $ waiting for forward, F forwarded, H held",
    "  LB / LP    List bulletins / private messages only",
    "  L@ area    List messages @ area or mailbox, e.g. L@ WW",
    "  L> call    List messages to call (L< call: from call)",
    "  LM         List messages to you",
    "  N name     Your first name (N - clears it, N alone shows your profile)",
    "  NL loc     Your locator, 4 or 6 characters, e.g. NL JN88EP",
    "  NH call    Your home BBS, e.g. NH OE3XSR or NH OE3XSR.#NOE.AUT.EU",
    "  R n        Read message n (R n n ... for several)",
    "  RM         Read all unread messages to you",
    "  S call     Send private message (same as SP call)",
    "  SP call @ mailbox   Private message to a user of another mailbox,",
    "             e.g. SP OE1ABC @ OE1XAB.#WIE.AUT.EU",
    "  SB topic   Send bulletin, e.g. SB ALL  (SB ALL @ WW: to the whole network)",
    "             Optional at the end: $BID, e.g. SB DX @ EU $DX0815",
    "  QSO        Your last connects to this mailbox (QSO 30: the last 30)",
    "  STAT       Link quality of your radio connection (STAT ALL: all stations)",
    "  V          Version",
]
HELP_SYSOP = [
    "Sysop:",
    "  E n field value   Edit header, field = TO, FROM, TYPE, STATUS, SUBJ, AT",
    "  QSO ALL [n] / QSO call [n]   Connection log of all stations / of one",
]

VERSION_TEXT = f"TinyBox {VERSION} - {{mode}}."
VERSION_LOCAL = "local mailbox, no forwarding"
VERSION_FWD = "mailbox {address}, forwarding on"
DICT_NONE = "No brocast dictionary available here."
DICT_INTRO = ("brocast dictionary v{version}, {lines} lines. Save this output (capture/log) "
              "and import it in the brocast listener.")
DICT_DONE = "Dictionary sent. Import the saved text under Status > Dictionary importieren."
BYE = "73, bye from TinyBox."
ABORTED = "Output aborted."

UNKNOWN_CMD = "Unknown command. Type H for help."
NO_SUCH_MSG = "No such message: {id}"
NOT_ALLOWED = "Not allowed."
INVALID_CALL = "Invalid callsign: {call}"
INVALID_VALUE = "Invalid value: {value}"
TOO_LARGE = "Message too long (max {max} bytes), discarded."
THIRD_PARTY_OFF = "Sorry, you can only send messages to the sysop {sysop}."
INVALID_ADDRESS = "Invalid address: {addr}  (e.g. OE1XAB.#WIE.AUT.EU or WW)"
DUPLICATE_BID = "BID {bid} is already known here - message not sent."
NO_FORWARD = "This mailbox does not forward. Leave out @ {addr} for local mail."
BAD_RUBRIC = "Rubric {rubric} is not open for bulletins here. Rubrics: {rubrics}"

USAGE_R = "Usage: R n"
USAGE_K = "Usage: K n"
USAGE_S = "Usage: S call[,call...] [@ mailbox] [$BID]  or  SB topic [@ area] [$BID]"
USAGE_E = "Usage: E n field value  (field = TO, FROM, TYPE, STATUS, SUBJ, AT)"

NO_MESSAGES = "No messages."
LIST_HEADER = " MSG# TS   SIZE TO        @BBS    FROM      DATE   UTC   SUBJECT"
LIST_ROW = ("{id:>5} {type}{status}{fwd} {size:>5} {to:<9} {at:<7} {frm:<9} {date} {time} "
            "{subject}")

READ_HEADER = [
    "Msg# {id}  Type/Status: {type}{status}{fwd}  BID: {bid}",
    "From: {frm}  To: {to}{at}",
    "Date: {date}",
    "Subject: {subject}",
    "",
]
HELD_NOTE = "*** Held: {note}"
READ_END = "[End of message {id}]"

KILLED = "Msg {id} killed."
KILLED_NONE = "No read messages to kill."
EDITED = "Msg {id} updated."

SUBJECT_PROMPT = "Subject: "
BODY_PROMPT = "Enter message, end with /EX or ^Z  (/AB = cancel):"
SAVED = "Msg {id} saved."
LONG_OUTPUT = "*** {n} lines follow - send A to abort"   # CR40 (replaces the pages of CR29)
CANCELLED = "Message cancelled."

# --- profile (CR73) ---
PROFILE_INTRO = "Please introduce yourself. Enter skips a question, /AB all of them."
PROFILE_ASK = {"name": "Your first name: ",
               "loc": "Your locator (e.g. JN88EP): ",
               "home": "Your home BBS (e.g. OE3XSR): "}
PROFILE_BAD = {"name": "Name: up to 12 letters, please.",
               "loc": "Locator: 4 or 6 characters, e.g. JN88 or JN88EP.",
               "home": "Home BBS: a mailbox call, e.g. OE3XSR or OE3XSR.#NOE.AUT.EU."}
PROFILE_THANKS = "Thank you. Change it any time with N, NL and NH."
PROFILE_LATER = "OK. Set it later with N name, NL locator, NH home BBS."
PROFILE_SHOW = "{call}: name {name}, locator {loc}, home BBS {home}"
PROFILE_NONE = "No profile for {call}."
USAGE_I = "Usage: I [call]"
INTERNAL_ERROR = "*** Internal error, command not completed. Sysop is informed."

# chat boards
CHAT_OFF = "Chat is not available here."
CHAT_NOT_CONSOLE = "The chat is for mailbox users (radio/telnet), not on the console."
CHAT_ACTIVE = "{n} station(s) in the chat right now - type C to see the boards."
CHAT_LIST_HEADER = " #  BOARD    KEEP  USERS  DESCRIPTION"
CHAT_LIST_ROW = "{n:>2}  {board:<8} {keep:<5} {users:>5}  {desc}"
CHAT_LIST_FOOT = "Join with C board (or C n). KEEP: history time, live = not stored."
CHAT_NO_BOARD = "No such chat board: {board}"
CHAT_ALREADY = "You are already in {board}."
CHAT_HEADER = "*** Chat board {board} - {desc} [{keep}]"
CHAT_LIVE_NOTE = "Live board: nothing is stored, only stations here now read along."
CHAT_HISTORY = "--- Last messages ({keep}, UTC) ---"
CHAT_HISTORY_ROW = "{time} {call}: {text}"
CHAT_HISTORY_END = "--- End of history ---"
CHAT_HISTORY_NONE = "No messages in the last {keep}."
CHAT_HISTORY_STORED = "*** {n} lines stored. Last from {last} UTC"
CHAT_HISTORY_ASK = "*** /H n to read"
CHAT_WHO = "In this board: {calls}"
CHAT_ALONE = "Nobody else is here right now."
CHAT_HINT = "Type your text and press Enter. /H help, /Q back to the mailbox."
CHAT_LINE = "{call}: {text}"
CHAT_JOINED = "*** {call} joined {board}"
CHAT_MOTD = "*** {text}"
CHAT_LEFT = "*** {call} left {board}{reason}"
CHAT_REASON_DISC = " (disconnected)"
CHAT_REASON_LOST = " (connection lost)"
CHAT_LOST_SYS = "Connection to {call} lost"
CHAT_REACT = "*** {call} {emoji} to: {target}"
CHAT_UPLOAD = "*** {call} is sending a picture ({size})"      # CR30
CHAT_QUOTE = '[re {call}: "{text}"] '                         # CR31
CHAT_QUOTE_GONE = "[re #{ref}] "
CHAT_BACK = "Left chat {board}, back in the mailbox."
CHAT_CUT = "(Line cut to {max} characters.)"
CHAT_UNKNOWN = "Unknown chat command. /H for help."
CHAT_HELP = [
    "Chat commands (everything else is sent to the board):",
    "  /Q         Back to the mailbox (also /EX or ^Z)",
    "  /W         Who is in this board",
    "  /L         List all boards",
    "  /J board   Change to another board",
    "  /R n emoji React to line #n with an emoji code, e.g. /R 4F :+1",
    "  /H n       Show the last n stored lines",
    "  /H         This help",
]

STAT_TITLE = "Link quality, last {frames} frames per direction (max. {minutes} min):"
STAT_ROW = ("{call:<10} {bars:<5}  {out:>4}  {inn:>4}  {rxq:>4}  {retry:>5} {rej_rx:>5} "
            "{rej_tx:>5} {t1:>3}  {net:>11}  {srt}")
STAT_HEADER = STAT_ROW.format(call="Call", bars="Bars", out="Out", inn="In", rxq="RXq",
                              retry="Retry", rej_rx="REJrx", rej_tx="REJtx", t1="T1",
                              net="Net/Rep", srt="SRT")
STAT_LEGEND = ["Bars ##### = best, X.... = over half lost, ----- = no frames yet, ~~~~~ = tentative (under 20",
               "frames: each repeat costs a bar). Out = loss to the station,",
               "In = loss from the station, RXq = chat frames a TinyBox client received."]
STAT_NONE = "No link quality data yet (radio connections and TinyBox clients only)."
STAT_NOBODY = "No radio connections with link quality data."
STAT_USAGE = "Usage: STAT or STAT ALL"

JLOG_HEADER = "Call       Last seen (UTC)   Count"
JLOG_ROW = "{call:<10} {last:<17} {count:>5}"
JLOG_EMPTY = "No stations logged yet."
USAGE_FIND = "Usage: F text  (at least 2 characters)"
FIND_NONE = "Nothing found for '{text}'."
FIND_COUNT = "{n} message(s) with '{text}':"
QSO_HEADER = "Connect (UTC)     Time   Call       Via     In/out bytes"
QSO_ROW = "{start:<16}  {dur:>6} {call:<10} {via:<7} {rx}/{tx}{ended}"
QSO_EMPTY = "No connects logged."
QSO_MORE = "Older connects: QSO {next}"
USAGE_QSO = "Usage: QSO [n]   (sysop: QSO ALL [n], QSO call [n])"

BUSY = "Sorry, TinyBox is busy. Please try again later."
IDLE_TIMEOUT = "Idle timeout, disconnecting. 73."

DISC_BY_SYSOP = "Disconnected by sysop. 73."
SHUTDOWN = "TinyBox is shutting down. 73."
SHUTDOWN_WARNING = ("*** System message from {sysop}: {mailbox} goes down in {left}. "
                    "Please finish and disconnect (B). ***")
SHUTDOWN_CANCELLED = "*** System message: shutdown of {mailbox} cancelled. ***"
RESTART_WARNING = ("*** System message from {sysop}: {mailbox} restarts in {left} "
                   "and is back shortly. Please finish and disconnect (B). ***")

# sysop console only
CONSOLE_BANNER = "*** TinyBox sysop console - type H for help ***"
HELP_CONSOLE = [
    "Console:",
    "  INFO       Start block again: version, calls, radio values, log, config",
    "  W          Who is connected",
    "  MON [ON|OFF]  Live monitor of user sessions",
    "  LOG        Log file, level and debug components",
    "  LOG DEBUG comp  Extra DEBUG for one component (agw, fwd, sync, ...)",
    "  LOG OFF [comp]  Back to the normal level (without comp: all of them)",
    "  LOG MARK text   Write a marker line into the log before a test",
    "  LOG BUNDLE      One file with log, version and config, to hand over",
    "  DISC call  Disconnect a user",
    "  STATUS     Mailbox status",
    "  BEACON     Send the beacon now and show it",
    "  UPDATE     Ask GitHub now for a new release (otherwise once a day)",
    "  UPDATE NEWS  Send the TBNEWS bulletin of the new release now",
    "  WEB        Show the web GUI login link",
    "  FWD        Forward status of all partners",
    "  FWD call   Connect to a partner mailbox now",
    "  FWQ        Messages waiting for forwarding",
    "  HOLD n     Keep message n from forwarding (held, only the sysop sees it)",
    "  REL n      Release message n: forward it, or make it a normal local message",
    "  SHUTDOWN [s]   Stop TinyBox in s seconds (default 60), users are warned",
    "  SHUTDOWN NOW   Stop at once",
    "  SHUTDOWN CANCEL  Call off a pending shutdown",
    "  RESTART [s]    Restart TinyBox (e.g. after changing tinybox.conf) in s",
    "                 seconds (default 60), users are warned; NOW, CANCEL as above",
]
UPDATE_ASKING = "Asking GitHub for the newest release ..."
UPDATE_UNKNOWN = "Update: no answer from GitHub (offline?)."
UPDATE_CURRENT = "Update: release {cur} is current."
UPDATE_NEWER = "Update: new release {tag} on GitHub (running {cur}): {url}"
UPDATE_ANNOUNCED = "Update: the TBNEWS bulletin for it is out."
UPDATE_NOT_ANNOUNCED = "Update: no bulletin yet ([update] announce = no) - UPDATE NEWS sends it."
UPDATE_NO_NEWS = "Update: no newer release known (running {cur}) - ask first with UPDATE."
UPDATE_NEWS_SENT = "Update: bulletin {n} in TBNEWS for {tag}."
BEACON_SENT = "Beacon to {dest}: {text}"
BEACON_EMPTY = "Beacon: nothing to send ([beacon] text is empty, no new mail)."
BEACON_NO_RADIO = "Beacon not sent: the radio (Direwolf / KISS) is not connected."
BEACON_STATE = "Beacon {state}, {n} sent since the start."
CONSOLE_NO_BYE = "This is the local console. Use SHUTDOWN to stop or RESTART to restart TinyBox."
WHO_HEADER = "Call       Via     Since (UTC)       State"
WHO_ROW = "{call:<10} {via:<7} {since:<17} {state}"
WHO_EMPTY = "No users connected."
MON_STATE = "Monitor is {state}."
# LOG (CR32)
LOG_LINES = [
    "Level {level}, extra DEBUG: {debug}",
    "Log file: {file} ({size})",
]
LOG_NO_FILE = "No log file: [logging] log_dir in tinybox.conf is empty."
LOG_MARKED = "Mark written to the log."
LOG_UNKNOWN = "Unknown component. Known: {comps}"
LOG_BUNDLE_DONE = "Debug bundle written: {path}"
LOG_BUNDLE_FAILED = "Debug bundle failed: {error}"
USAGE_LOG = "Usage: LOG | LOG DEBUG comp | LOG OFF [comp] | LOG MARK text | LOG BUNDLE"
DISC_DONE = "{call} disconnected."
DISC_NONE = "{call} is not connected."
USAGE_DISC = "Usage: DISC call"
STATUS_LINES = [
    "TinyBox {version}  mailbox {mailbox}  sysop {sysop}",
    "Up since:  {since}",
    "Direwolf:  {agw}",
    "Users:     {users} of {max_users}",
    "Messages:  {msgs} ({private} private, {bulletins} bulletins, {unread} unread)",
    "Data:      {data_dir}",
]
STATUS_AXUDP = "AXUDP:     {listen} {up}, peers {peers}, links {links}, rx {rx} tx {tx}{dropped}"
SHUTTING_DOWN = "Shutting down ..."
SHUTDOWN_SCHEDULED = ("Shutdown in {sec} s, {n} station(s) warned. "
                      "SHUTDOWN CANCEL calls it off.")
SHUTDOWN_PENDING = "Shutdown pending: {sec} s left."
SHUTDOWN_CANCEL_DONE = "Shutdown cancelled, stations informed."
SHUTDOWN_NONE = "No shutdown pending."
USAGE_SHUTDOWN = "Usage: SHUTDOWN [seconds | NOW | CANCEL]"
USAGE_RESTART = "Usage: RESTART [seconds | NOW | CANCEL]"
RESTARTING = "TinyBox restarts now ..."
RESTART_SCHEDULED = ("Restart in {sec} s, {n} station(s) warned. "
                     "RESTART CANCEL calls it off.")
RESTART_BAD_CONFIG = "tinybox.conf has an error, NOT restarted: {error}"
RESTART_CONFIG_OK = "tinybox.conf checked: OK."
FWD_OFF = "Forwarding is off ([forward] enabled = no)."
FWD_START = "Connecting to {call} ..."
FWD_DONE = "Forward {call}: {result}"
FWD_FAILED = "Forward {call} failed: {error}"
FWQ_EMPTY = "Forward queue is empty."
FWQ_HEADER = "Partner  Msg#  State  Since (UTC)"
FWQ_ROW = "{partner:<8} {id:>4}  {state:<6} {changed}"
USAGE_HOLD = "Usage: HOLD n  /  REL n"
HELD = "Msg {id} held."
RELEASED = {"$": "Msg {id} released, queued for forwarding.",
            "": "Msg {id} released, local message.",
            "H": "Msg {id}: no partner for {at} - still held."}

# telnet test port only
TELNET_LOGIN = "Callsign: "
TELNET_BAD_CALL = "Invalid callsign."
TELNET_TEST_NOTE = "*** TinyBox telnet test port (local only) ***"
