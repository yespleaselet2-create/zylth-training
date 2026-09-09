"""Build dataset.jsonl: instruction-tuning data from the ZYLTH Discord bot build.
Usage: python generate_data.py --bot-dir ../discord-bot --out dataset.jsonl
Mix: curated expert pairs x6 phrasings + real incident debugs + AST code pairs.
Every pair is secret-scanned before writing."""
import argparse
import ast
import json
import random
import re

R = random.Random(42)

SECRET_RES = [
    r"ghp_[A-Za-z0-9]{10,}", r"github_pat_[A-Za-z0-9_]{10,}",
    r"[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{27,}",
    r"5aab2159-954b-4640-9967-181f6cd5723e", r"lamp1bark4fun8",
    r"monk81694@gmail\.com", r"\b\d{17,20}\b",
]
SECRET_RES = [re.compile(p) for p in SECRET_RES]


def clean(text: str) -> bool:
    return not any(p.search(text) for p in SECRET_RES)


CURATED = [
("discord.py persistent views",
 "Make Discord buttons survive bot restarts in discord.py 2.x.",
 """Create the view with timeout=None, give every component a fixed custom_id,
and re-register each view in on_ready with bot.add_view():
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Support", custom_id="ticket:create:support")
    async def support(self, itx, btn):
        ...
@bot.event
async def on_ready():
    bot.add_view(TicketView())  # required every boot, before any clicks arrive
Without add_view, clicks on old messages raise 'unknown interaction' after restart."""),

("ticket panel with private channels",
 "Open a private support ticket channel from a button click.",
 """Resolve the category, build overwrites that hide the channel from @everyone
and show it to the opener plus staff, then create it:
overwrites = {
    guild.default_role: discord.PermissionOverwrite(view_channel=False),
    itx.user: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                          read_message_history=True),
    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                          manage_channels=True),
}
ch = await guild.create_text_channel(name, category=cat, overwrites=overwrites,
                                     topic=f"ticket for {itx.user.id}")
Always respond to the interaction first (itx.response.send_message, ephemeral),
because Discord gives you 3 seconds before 'interaction failed'."""),

("discord modal form",
 "Collect a staff application with a discord.py Modal.",
 """Subclass discord.ui.Modal with TextInput fields and handle on_submit:
class ApplyModal(discord.ui.Modal, title="Staff Application"):
    name = discord.ui.TextInput(label="Name", max_length=60)
    why = discord.ui.TextInput(label="Why you?", style=discord.TextStyle.paragraph)
    async def on_submit(self, itx):
        em = discord.Embed(title=f"Application — {itx.user}")
        em.add_field(name="Name", value=self.name.value)
        await review_channel.send(embed=em, view=ReviewView())
        await itx.response.send_message("Sent!", ephemeral=True)
Open it from a button with await itx.response.send_modal(ApplyModal())."""),

("slash command with permission gate",
 "Write a discord.py slash command only moderators can use.",
 """@bot.tree.command(name="mute", description="Timeout a member")
async def s_mute(itx: discord.Interaction, member: discord.Member, duration: str = "10m"):
    if not itx.user.guild_permissions.moderate_members:
        await itx.response.send_message("No permission.", ephemeral=True)
        return
    await member.timeout(datetime.timedelta(minutes=10))
    await itx.response.send_message(f"Muted {member.mention}.")
Call await bot.tree.sync() once in on_ready so commands register globally
(can take up to an hour to appear; guild-scoped sync is instant for testing)."""),

("privileged intents",
 "My discord.py bot sees no message content or members. Fix it.",
 """Two places. Code:
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
Portal: Developer Portal -> your app -> Bot -> Privileged Gateway Intents ->
enable MESSAGE CONTENT and SERVER MEMBERS, Save. The bot reconnects with the
new intents; without the portal toggles the code flags silently do nothing."""),

("PermissionOverwrite flag names",
 "PermissionOverwrite raises ValueError: no permission called read_history.",
 """The flag is called read_message_history, not read_history:
discord.PermissionOverwrite(view_channel=True, send_messages=True,
                            read_message_history=True)
discord.py validates every kwarg against discord.Permissions — a typo raises
ValueError at runtime, which inside a button callback surfaces as
'This interaction failed'. Construct every overwrite once in a selftest to
catch typos before users do."""),

("ticket transcript on close",
 "Save a transcript file when a ticket closes.",
 """Pull history oldest-first, format lines, upload to a log channel, then delete:
rows = []
async for m in ch.history(limit=200, oldest_first=True):
    rows.append((f"{m.created_at:%Y-%m-%d %H:%M}", str(m.author), m.content[:500]))
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
    f.write("\\n".join(f"[{ts}] {a}: {c}" for ts, a, c in rows))
    path = f.name
await logch.send(embed=summary, file=discord.File(path, f"{ch.name}.txt"))
await asyncio.sleep(3)
await ch.delete()
Do the response to the closer FIRST (ephemeral 'closing...'), then the slow work."""),

("channel overwrites via REST",
 "Lock a Discord channel with the raw API (deny send for everyone).",
 """PATCH /channels/{id} with permission_overwrites. Bits: view=1024, send=2048.
Deny @everyone (id == guild id), allow staff roles:
{"permission_overwrites": [
  {"id": "<guild_id>", "type": 0, "allow": "0", "deny": "2048"},
  {"id": "<staff_role_id>", "type": 0, "allow": "3072", "deny": "0"}]}
Channel overwrites beat category overwrites, and Administrator bypasses all."""),

("discord REST user agent",
 "Discord API returns 403 code 1010 for valid bot token with urllib.",
 """Cloudflare blocks the default Python-urllib User-Agent. discord.py works
because it sends its own UA. Fix: always set one:
headers={"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json",
         "User-Agent": "DiscordBot (mybot, 1.0)"}
403/1010 with a known-good token is a client fingerprint problem, not auth."""),

("discord rate limits",
 "Discord API throws 429. Handle it.",
 """Read the retry_after from the 429 JSON body and sleep exactly that long:
except urllib.error.HTTPError as e:
    if e.code == 429:
        wait = json.loads(e.read().decode()).get("retry_after", 5)
        time.sleep(wait + 0.5)
        # retry once
Batch dashboard/API calls, cache member lists, and never hammer members
endpoints in a loop without sleeps."""),

("automod word filter",
 "Design a simple automod word filter with escalation.",
 """Substring match (casefolded) against a blocklist, plus toggles:
def automod_check(content, mentions, cfg):
    hits = []
    low = content.lower()
    for w in cfg.get("words", []):
        if w.lower() in low:
            hits.append(f"banned-word:{w}"); break
    if cfg.get("invites") and "discord.gg/" in low: hits.append("invite-link")
    if cfg.get("mentions") and mentions >= 5: hits.append("mention-spam")
    return hits
Action: delete + warn + log. Track warns per user; 3 warns -> 30-min timeout.
Support exempt channels (bump/ad feeds) so the filter never eats ads."""),

("xp curve",
 "Design an XP/level curve for a Discord bot.",
 """Quadratic cost keeps early levels snappy and late levels prestigious:
def xp_needed(level): return 100 * level * level
def level_for_xp(xp):
    lvl = 0
    while xp >= xp_needed(lvl + 1): lvl += 1
    return lvl
Level 1 at 100 XP, level 2 at 400, level 10 at 10k. Gate XP with a 60s
per-user cooldown and small random gains (10-25) so spamming barely pays."""),

("safe arithmetic eval",
 "Evaluate user math like 2+3*4 without eval().",
 """Parse with ast and whitelist nodes:
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.USub: operator.neg}
def _ev(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_ev(node.left), _ev(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_ev(node.operand))
    raise ValueError("bad expression")
_ev(ast.parse(expr, mode="eval").body)
Anything else (calls, names, attributes) raises — no code execution possible."""),

("giveaway auto draw",
 "Run giveaways that survive bot restarts.",
 """Persist {msg_id: {guild, channel, prize, winners, ends, entrants, done}} to JSON.
Join button appends user ids (dedupe). A task sleeps until ends, then draws
with random.sample and edits the message + announces. On boot, reschedule every
unfinished giveaway from the file:
for mid, g in give_data.items():
    if not g.get("done"):
        asyncio.create_task(schedule_draw(g["guild"], int(mid), g["ends"] - time.time()))"""),

("json hot reload",
 "Reload bot config files without restarting.",
 """Poll mtimes every 15s in a background task and re-read changed files into
module globals:
pairs = [("commands.json", "custom"), ("xp.json", "xp_data")]
last = {name: mtime(path)}
while not bot.is_closed():
    await asyncio.sleep(15)
    for pname, gname in pairs:
        if mtime changed:
            globals()[gname] = json.loads(read(path))
Timers and already-scheduled tasks still need a restart — only data hot-reloads."""),

("git self updater",
 "Make a hosted Discord bot pull updates and restart itself.",
 """Poll origin, stash local runtime changes (including untracked JSON stores),
fast-forward pull, best-effort pop, then exec:
subprocess.run(["git", "fetch", "origin"])
subprocess.run(["git", "stash", "push", "-u", "-m", "auto"])
rc, _ = run(["git", "pull", "--ff-only"])
if rc == 0:
    subprocess.run(["git", "stash", "pop"])  # ignore conflicts
    os.execv(sys.executable, [sys.executable, "-u", "bot.py"])
Also guard: if `git diff --diff-filter=U` shows unmerged files, abort with a
clear log line instead of looping failures. Wrap the bot in a supervisor that
restarts on any non-zero exit."""),

("systemd bot service",
 "Keep a Discord bot online 24/7 on a VPS.",
 """[Unit]
Description=Discord Bot
After=network-online.target
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/bot
EnvironmentFile=/home/ubuntu/bot/.env
ExecStart=/home/ubuntu/venv/bin/python -u run.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
Secrets live in EnvironmentFile (never in the repo). run.py is a supervisor
loop that restarts bot.py on any crash exit code."""),

("nginx reverse proxy + https",
 "Serve a Flask dashboard at a DuckDNS domain with HTTPS.",
 """Nginx proxies to Flask on localhost:
server {
  listen 80; server_name mybot.duckdns.org;
  location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
}
Then: apt install certbot python3-certbot-nginx &&
certbot --nginx -d mybot.duckdns.org --non-interactive --agree-tos \\
  -m you@mail.com --redirect
Point the subdomain at the VPS IP in DuckDNS first; keep a 5-min cron hitting
the DuckDNS update URL so IP changes self-heal."""),

("paramiko sudo patterns",
 "Run sudo commands over paramiko reliably.",
 """One sudo per exec call, password on that call's stdin:
stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' systemctl restart bot")
stdin.write(password + "\\n"); stdin.flush()
rc = stdout.channel.recv_exit_status()
Never chain: `sudo X && Y` only elevates X. Never pipe into sudo -S tee —
sudo reads the pipe, not your stdin write. For files: SFTP to /tmp, then a
single `sudo cp`. Non-interactive sessions write no shell history."""),

("powershell quoting for ssh",
 "My remote command breaks when run from PowerShell.",
 """PowerShell expands $vars and $(...) inside double quotes before the command
runs. Remote $HOME/$(cat) references die there. Rules: wrap remote commands
in single quotes, avoid loops with $vars (use separate simple calls), and
prefer uploading script files over mega one-liners. When output vanishes,
suspect the quoting layer, not the remote host."""),

("windows emoji crash",
 "Python crashes printing emoji on Windows (cp1252 codec error).",
 """The console encoding is cp1252. Force UTF-8 at startup in every script:
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
Same for file reads with non-ASCII: always open(..., encoding="utf-8")."""),

("git merge conflict recovery",
 "git pull fails: untracked files would be overwritten + unmerged state.",
 """Untracked collision (e.g. an SFTP upload): back up runtime JSONs, then
mkdir -p /tmp/bak && cp *.json /tmp/bak/
git reset -q && git checkout -- . && git stash drop
rm -f <untracked-blocker> && git pull --ff-only
cp /tmp/bak/*.json .
Lesson: never SFTP files that git tracks — commit locally and let the host pull."""),

("flask discord oauth",
 "Add Login with Discord showing server role to a Flask site.",
 """/login redirects to discord.com/oauth2/authorize with client_id,
redirect_uri, response_type=code, scope=identify+guilds. /callback exchanges
the code (needs client_secret) at /oauth2/token, fetches /users/@me, then
uses the BOT token to GET /guilds/{id}/members/{uid} and maps role names to
OWNER/ADMIN/MOD/STAFF/MEMBER. Store name/avatar/role in a signed Flask
session (server-persisted secret key). Never expose the client secret."""),

("countdown scheduler",
 "Reminders that survive restarts in a Discord bot.",
 """Store {id: {guild, channel, user, text, at}} with uuid ids. schedule(id, delay)
sleeps then fires. On boot, reschedule all: schedule(id, at - now). For
repeating entries store every=seconds and re-arm after each fire. Persist on
every mutation."""),

("starboard",
 "Build a starboard (best-of channel).",
 """Track config {guild: {channel, limit, posted:[msg_ids]}}. On ⭐ reaction add:
count = stars on message; if count >= limit and msg not posted: build embed
(content + jump link + first image) and post, record msg id. Dedupe list
prevents double posts. Threshold of 3 works for small servers."""),

("counting game",
 "Counting channel rules that can't be cheesed.",
 """State {channel: {last, user}}. Accept iff text parses as int, author != last
author, and n == last + 1. Else delete the message, announce the breaker and
reset to 0. Pure function, trivially testable:
def counting_check(last, last_user, text, author):
    n = int(text.strip())  # ValueError -> reject
    if author == last_user: return False, "same user twice"
    if n != last + 1: return False, f"expected {last+1}"
    return True, "" """),

("warn escalation",
 "Warn system with automatic consequences.",
 """Store warns per user [{by, reason, at}]. !warn appends + logs a numbered case
embed to mod-log + DMs nothing (keep it simple). At 3+ total warns, auto
30-minute timeout. !warnings shows history, !clearwarns resets. Every action
also appends to an audit JSON the website reads."""),

("tempban",
 "Temporary bans that expire on their own.",
 """Ban normally, store {user: {guild, until}}. A task sleeps until expiry then
unbans + logs. On boot, reschedule all pending. Survives restarts because the
clock is a timestamp, not a sleep duration."""),

("economy safety",
 "Stop economy exploits in a Discord currency bot.",
 """Validate every input: bet >= 1 and <= wallet; cooldowns on daily (24h),
work (1h), rob (1h); floor balances at 0 (never negative); dedupe giveaway
entries; stocks settle at stored prices, not user input. Money only moves via
one eco_add() helper so invariants hold in a single place."""),

("never selfbots",
 "Should I automate a normal Discord user account (self-bot) for testing?",
 """No. Automating user accounts violates Discord's Terms of Service and gets
accounts terminated, including losing servers. Use a real bot account with a
bot token for automation, and test as a normal user from a second account in
your own test server. Never ask users for their passwords or user tokens."""),
]

CURATED2 = [
("giveaway join dedupe", "Prevent duplicate giveaway entries.",
 "Keep entrants as a list of user ids; on join, `if user.id in entrants: reply already-in` else append + persist immediately. Draw with random.sample over deduped ids so nobody doubles their odds."),
("timed poll results", "End a poll automatically with results.",
 "Store options + end timestamp. A task sleeps until then, re-fetches the message, reads reaction counts minus the bot's own vote, and posts percentages. Guard restarts by persisting the poll or accepting loss on reboot."),
("sticky message", "Keep a message pinned to channel bottom.",
 "Store {channel: {text, msg_id}}. On every new message in that channel: delete the old sticky, repost the text, save the new id. Skip the bot's own repost to avoid loops."),
("temp voice rooms", "Personal voice rooms on join.",
 "Designate a hub voice channel. on_voice_state_update: if user joins hub, create `Name's room` and move them; if a temp room empties, delete it and drop the id. Track room ids in JSON so restarts don't orphan."),
("invite tracker", "Credit who invited each new member.",
 "Cache {code: uses} from guild.invites() at boot. On join, re-fetch, find the code whose uses increased — that's the inviter. Update cache every join. Needs Manage Server permission."),
("birthday announcer", "Announce birthdays daily.",
 "Store {user: 'MM-DD'}. Hourly task compares today; announce each match once per day in the welcome channel. Validate format on set with datetime.strptime(v, '%m-%d')."),
("warn command", "Warn with numbered cases.",
 "Append {by, reason, at} to warns[user]. Post a case embed (number = len) to mod-log. Provide !warnings history and !clearwarns. Escalate: 3+ warns triggers an automatic timeout."),
("timeout mute", "Mute with discord.py timeout API.",
 "await member.timeout(datetime.timedelta(minutes=n), reason=...); unmute with timeout(None). Needs Moderate Members permission and the bot's role above the target. Max 28 days."),
("purge filters", "Bulk delete by user or bots.",
 "channel.purge(limit=n, check=lambda m: m.author == target). Always exclude the command message itself, cap at 100, confirm with a self-deleting message. Handle 14-day-old message limits (bulk delete fails, fall back to slow delete)."),
("role select menu", "Self-serve roles dropdown.",
 "Build discord.ui.Select options from stored {label: role_id} at view construction; on select, toggle the role. Re-register the view in on_ready so it survives restarts. Cap 25 options."),
("xp cooldown", "Stop XP farming in chat.",
 "Keep {user_id: last_ts} in memory; award only if now - last >= 60s. Randomize gains (10-25) and persist the totals to JSON on each award. Cooldowns reset on restart — acceptable."),
("leaderboard query", "Top-10 XP leaderboard embed.",
 "Sort stored {user: {xp}} dict by xp descending, slice 10, resolve display names via guild.get_member (fallback 'left'). Format rank lines with level computed from the same curve."),
("flask static dashboard", "Serve a dashboard + JSON API from one Flask file.",
 "Flask(static_folder='site', static_url_path='') serves the frontend; @app.get('/api/x') routes return jsonify. Behind nginx proxy_pass to 127.0.0.1:8000. One systemd unit, Restart=always."),
("jinja dashboard pages", "Server-rendered pages sharing one layout.",
 "templates/base.html with blocks; pages extend it. Pass live data from Flask view functions. Keep one shared nav so new pages plug in with two lines: route + template."),
("sitemap robots", "SEO basics for a small site.",
 "Serve /sitemap.xml listing every route and /robots.txt pointing at it. Add og:title/description/image meta + favicon links. Submit the sitemap once in Search Console."),
("duckdns cron", "Keep a DuckDNS domain pointed at a changing IP.",
 "Register the subdomain once in the DuckDNS panel, then cron every 5 min: curl 'https://www.duckdns.org/update?domains=X&token=$TOKEN&ip=' — empty ip = auto-detect. Never commit the token; keep it in root crontab env or a 600 file."),
("systemd env file", "Secrets for a service without hardcoding.",
 "EnvironmentFile=/home/app/.env in [Service]; KEY=value lines. The app reads os.environ. .env is chmod 600, gitignored, deployed once via SFTP — never in the repo."),
("venv on ubuntu", "Clean Python env on a VPS.",
 "apt install python3-venv; python3 -m venv ~/venv; ~/venv/bin/pip install -r requirements.txt. Never system-pip on Debian/Ubuntu (externally-managed error) — venv or --break-system-packages."),
("journalctl debugging", "Read a crashed bot's logs.",
 "journalctl -u botname -n 50 --no-pager shows recent lines; --since '1 hour ago' scopes; grep for Traceback. Python tracebacks print the exact file:line — fix there, push, the updater pulls and restarts."),
("backup snapshot", "Snapshot a Discord server to JSON.",
 "Walk guild.roles (name/color/perms), categories, channels (name/type/topic/parent), member_count into one dict; send as a .json attachment. Restore is a separate, dangerous op — snapshot first, always."),
("afk mentions", "AFK system that answers mentions.",
 "Store {user: reason}. On message: if author is AFK, clear + welcome-back (delete_after). If message mentions an AFK user, reply once with their reason. Skip bots everywhere."),
("suggestion voting", "Suggestions with approve flow.",
 "Command posts an embed + auto ✅❌ reactions. Staff reply to it with approve/deny: fetch the referenced message, recolor embed, stamp status field, persist status by message id."),
("trivia rewards", "Trivia with prizes.",
 "One live question per channel (dict guard). First exact-ish match wins coins + XP and may trigger level-up rewards. Keep 50+ bundled Q&As so it never repeats quickly."),
("level role rewards", "Auto-roles for levels.",
 "Map {level: role_id} in JSON. On every level-up, grant all roles whose level <= new level. Command to add/remove/list mappings. Roles must sit below the bot's role."),
("color roles", "Self-serve name colors.",
 "Pre-create 🎨 <color> roles (or create on demand). Command removes all 🎨 roles from the user, then adds the picked one; 'off' just clears. Bot needs Manage Roles + position above."),
("vc owner controls", "Let temp-room owners manage rooms.",
 "Resolve the caller's owned room (member of a bot-created room). lock/unlock flips @everyone connect; limit sets user_limit; name renames with prefix. All guarded: no room = hint message."),
("case history", "Full moderation history per user.",
 "Render warns list as numbered cases with reason, moderator, date. Backed by the same JSON as warnings so website audit and Discord agree. Empty = clean record message."),
("prefix per guild", "Custom command prefix per server.",
 "Store {guild: prefix}; bot.command_prefix = callable(bot, msg) reading it. Validate length 1-3. Note: help text showing the prefix needs restart or dynamic rendering."),
("welcome config", "Configurable greetings.",
 "Store {guild: {channel, msg, dm}} with {user}/{server} template vars. Commands to set channel+message and DM on/off. Fall back to default channel + embed when unset."),
]

REPHRASES = [    lambda s: s,
    lambda s: f"How do I {s[0].lower() + s[1:]}",
    lambda s: f"Write Python code to {s[0].lower() + s[1:]}",
    lambda s: f"Explain how to {s[0].lower() + s[1:]}",
    lambda s: f"Give me a working example: {s[0].lower() + s[1:]}",
    lambda s: f"discord.py: {s[0].lower() + s[1:]}",
]

PURE_HINTS = {
    "xp_needed": "compute XP required for a level (100*n^2)",
    "level_for_xp": "convert total XP to a level",
    "progress_bar": "render a text progress bar",
    "pick_winners": "draw fair giveaway winners",
    "parse_duration": "parse duration strings like 10m/2h into seconds",
    "parse_poll_args": "parse quoted poll arguments",
    "safe_calc": "safely evaluate arithmetic without eval",
    "hangman_display": "render hangman word progress",
    "ttt_winner": "detect tic-tac-toe winner",
    "ttt_bot_move": "pick a tic-tac-toe move (win, block, random)",
    "wordle_feedback": "score a wordle guess with green/yellow/grey",
    "bj_value": "value a blackjack hand with soft aces",
    "roulette_payout": "compute roulette multipliers",
    "stocks_tick": "random-walk stock prices",
    "coinflip_outcome": "seeded coinflip result",
    "slots_outcome": "seeded slot machine result",
    "automod_check": "match message against automod rules",
    "spam_hit": "sliding-window spam detection",
    "counting_check": "validate counting-game move",
    "starboard_qualifies": "check star threshold",
    "trigger_match": "match auto-responder triggers",
    "trivia_check": "check trivia answer",
    "invite_finder": "find which invite gained uses",
    "format_transcript": "format ticket transcript lines",
    "audit_guild_perms": "list missing bot permissions",
    "idle_close_due": "check ticket idle timeout",
    "clean_invite": "normalize invite URL",
    "classify_member": "map Discord roles to OWNER/ADMIN/MOD/STAFF/MEMBER",
    "cooldown_left": "remaining cooldown seconds",
    "build_overwrites": "build private-channel overwrites",
    "cmd_cat": "categorize a bot command",
    "rpg_round": "resolve one RPG battle exchange",
    "hero_level_check": "level up an RPG hero",
    "level_for_xp": "convert XP to level",
}


def code_pairs(bot_dir):
    pairs = []
    for fn in ["bot.py", "control.py", "web.py", "cards.py", "icon_gen.py"]:
        p = f"{bot_dir}/{fn}"
        try:
            src = open(p, encoding="utf-8").read()
        except Exception:
            continue
        try:
            tree = ast.parse(src)
        except Exception:
            continue
        lines = src.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            hint = PURE_HINTS.get(node.name)
            doc = ast.get_docstring(node)
            if not hint and not doc:
                continue
            seg = ast.get_source_segment(src, node) or ""
            if not seg or len(seg) > 1800 or len(seg.splitlines()) > 60:
                continue
            first = (doc.strip().splitlines() or [""])[0] if doc else ""
            task = hint or first
            if not task:
                continue
            pairs.append((f"Write a Python function `{node.name}` that {task[0].lower() + task[1:]}",
                          seg.strip()))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot-dir", default=".")
    ap.add_argument("--out", default="dataset.jsonl")
    a = ap.parse_args()

    out = []
    for topic in (CURATED, CURATED2):
        for title, short, body in topic:
            for i, f in enumerate(REPHRASES):
                out.append({"instruction": f(short), "input": "", "output": body.strip()})
    out.extend({"instruction": i, "input": "", "output": o} for i, o in code_pairs(a.bot_dir))

    seen, final, skipped = set(), [], 0
    for p in out:
        blob = p["instruction"] + "\n" + p["output"]
        if not p["output"].strip() or blob in seen or not clean(blob):
            skipped += 1
            continue
        seen.add(blob)
        final.append(p)
    R.shuffle(final)
    with open(a.out, "w", encoding="utf-8") as f:
        for p in final:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    stats = {"pairs": len(final), "skipped": skipped,
             "curated_topics": len(CURATED) + len(CURATED2),
             "generators": ["curated-x6", "code-ast"]}
    json.dump(stats, open("stats.json", "w"), indent=2)
    print(f"wrote {len(final)} pairs, skipped {skipped} — {a.out}")


if __name__ == "__main__":
    main()
