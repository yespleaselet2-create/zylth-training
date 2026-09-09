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

CURATED3 = [
("slash sync", "Register discord.py slash commands.",
 "Call await bot.tree.sync() once in on_ready. Global sync can take an hour to propagate; for instant testing sync to one guild: await bot.tree.sync(guild=discord.Object(id=GUILD_ID))."),
("interaction 3s rule", "Avoid 'interaction failed' on buttons.",
 "You have ~3 seconds to respond. For slow work: await itx.response.defer(ephemeral=True) first, then itx.followup.send(...) when done. Never do network/DB calls before the first response."),
("defer pattern", "Handle slow button clicks.",
 "await itx.response.defer() immediately, run the work, then await itx.followup.send(result). Deferred interactions stay valid ~15 minutes."),
("converters", "Parse members/roles/channels from command text.",
 "Type-hint the parameter: async def kick(ctx, member: discord.Member). discord.py converts mentions/IDs/names automatically and errors cleanly if not found. Same for discord.Role, discord.TextChannel."),
("cooldowns", "Rate-limit a command per user.",
 "@commands.cooldown(1, 60, commands.BucketType.user) above the command plus an on_command_error handler for CommandOnCooldown telling them when to retry."),
("wait_for", "Wait for a user's next message.",
 "msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=30). Always timeout + try/except asyncio.TimeoutError."),
("tasks loop", "Run background jobs in discord.py.",
 "from discord.ext import tasks. @tasks.loop(minutes=5) async def job(): ...; call job.start() in on_ready (guard job.is_running()). Wrap body in try/except so one failure never kills the loop."),
("cogs", "Split a big discord.py bot into files.",
 "class Mod(commands.Cog): ... with @commands.command methods. Load with await bot.load_extension('cogs.mod') where cogs/mod.py defines async def setup(bot): await bot.add_cog(Mod(bot)). One file per feature area."),
("hybrid commands", "One command as both prefix and slash.",
 "@commands.hybrid_command(name='ping') works as !ping and /ping after tree sync. Best of both worlds for user-facing commands."),
("error handler", "Friendly command errors.",
 "@bot.event on_command_error: if isinstance(error, commands.MissingPermissions): reply what perm is missing; if CommandNotFound: ignore silently; else log the traceback."),
("audit log reads", "Find who deleted a channel.",
 "async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete): user = entry.user. Needs View Audit Log permission; entries arrive with slight delay so check twice on bursts."),
("role hierarchy", "Why Manage Roles fails on some members.",
 "Bots can only manage roles BELOW their highest role. Owner bypasses everything. Fix: drag the bot role above staff roles in Server Settings, or catch discord.Forbidden and explain it."),
("webhooks", "Post to Discord from a script without a bot.",
 "Create channel Integrations -> Webhooks -> New, POST JSON {content} to the URL. One-way only (no reading). Rotate the URL if leaked — anyone with it can post."),
("threads", "Auto-discussion threads on media posts.",
 "await message.create_thread(name='...', auto_archive_duration=1440). Threads inherit channel perms; bots need Send Messages in Threads (covered by channel perms)."),
("forum tags", "Organize a forum channel.",
 "Forum channels need available_tags configured; bots post with applied_tags=[tag_ids]. Read tags from channel.available_tags. Great for suggestions/bug reports."),
("scheduled events", "Create a Discord event from a bot.",
 "await guild.create_scheduled_event(name=..., start_time=aware_datetime, entity_type=discord.EntityType.external, location='...'). List with guild.scheduled_events. Announce it in the events channel."),
("emoji steal", "Copy a custom emoji into your server.",
 "Match <a:name:id> or <:name:id>, download https://cdn.discordapp.com/emojis/{id}.gif/png, guild.create_custom_emoji(name=name, image=bytes). Needs Manage Emojis; animated needs the gif URL."),
("slowmode", "Slow a raid-heated channel.",
 "await channel.edit(slowmode_delay=seconds) (0-21600). Lift with 0. For server-wide panic, loop text channels. Log who did it."),
("member timeout", "Mute without a mute role (modern).",
 "await member.timeout(timedelta(minutes=10)) — native, shows in clients, auto-expires. Unmute: timeout(None). Max 28 days. Needs Moderate Members."),
("purge safely", "Bulk delete without nuking the command.",
 "channel.purge(limit=n, check=predicate) excluding the invoking message; cap 100; messages older than 14 days can't bulk-delete (API limit) — catch and fall back."),
("embed limits", "Discord embed constraints.",
 "Title 256, description 4096, 25 fields (name 256/value 1024 each), footer 2048, total 6000 chars, 10 embeds/message. Truncate defensively with [:n] everywhere."),
("message limits", "Discord message constraints.",
 "2000 chars content, 2000/nitro more with files; 8MB files (50MB boosted). Split long outputs or attach .txt. Buttons: 5 rows x 5, 100-char labels/ids."),
("asyncio sleep tasks", "Delayed actions that survive restarts.",
 "Never rely on bare asyncio.sleep for anything important: persist {id, run_at} to JSON, and on boot schedule(id, run_at - now). Sleep only in-memory for the current session."),
("atomic json writes", "Don't corrupt JSON stores on crash.",
 "Write to path.tmp then os.replace(tmp, path). Readers never see half-written files. Also cap log-style lists ([-200:]) so files can't grow forever."),
("logging setup", "Proper logging in a bot.",
 "logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s'). Use logger.exception inside except blocks — free tracebacks. Keep a journald/systemd unit for persistence."),
("retry backoff", "Retry flaky network calls.",
 "for attempt in range(4): try: return call(); except Transient: sleep(2 ** attempt + random()). Retry timeouts/429/5xx only — never retry 400/401/403/404."),
("env config", "Configure deploys without hardcoding.",
 "Read os.environ with sane defaults; fail fast with a clear message when required vars are missing. .env file locally (gitignored), real env vars or EnvironmentFile in prod."),
("argparse cli", "Ship a control CLI for your bot's API.",
 "argparse subparsers: one function per command, set_defaults(f=fn). Each function prints short human lines. Never print secrets; mask tokens in any echo."),
("regex ids", "Extract Discord IDs safely.",
 "re.fullmatch(r'<@!?(\\d+)>', text) for mentions; r'<#(\\d+)>' channels; r'<(a)?:(\\w+):(\\d+)>' emojis. fullmatch (not search) avoids partial garbage."),
("timezones", "Timestamps that don't confuse.",
 "Store UTC ISO (datetime.now(timezone.utc)); display with Discord <t:unix:R> so every user sees their own timezone. Never store naive local times."),
("pathlib", "File paths that work on Windows and Linux.",
 "Path(__file__).parent / 'data.json'. Never hardcode separators; open(..., encoding='utf-8') always. Expand ~ with Path.home()."),
("subprocess safety", "Run shell tools from Python safely.",
 "subprocess.run(list_args, capture_output=True, text=True, timeout=60) — list form, no shell=True, always a timeout. Check returncode; slice output tails for logs."),
("pip freeze", "Reproducible deploys.",
 "pip freeze > requirements.txt after it works; install with pip install -r. Pin discord.py major (discord.py>=2,<3) so a v3 rewrite never surprises prod."),
("pytest pattern", "Test Discord helpers without a token.",
 "Pure functions get direct asserts. Async handlers get fakes (author/channel/guild stubs) + asyncio.run. No-token suite must exit 0 offline — gate network tests behind env flags."),
("jinja layout", "Multi-page Flask site without duplication.",
 "templates/base.html with {% block content %}; pages extend it. One nav partial means new pages plug in with route + template only."),
("flask sessions", "Login sessions without a database.",
 "app.secret_key persisted to a 600 file; flask.session signed cookie stores uid/name/role. Clear on /logout. Never store tokens in the cookie."),
("reverse proxy headers", "Flask behind nginx correctness.",
 "proxy_set_header Host/X-Real-IP; Flask builds absolute URLs (OAuth redirect_uri!) from Host — a wrong Host breaks OAuth. Test /login Location header end-to-end."),
("seo basics", "Get a small community site indexed.",
 "/sitemap.xml with all routes, /robots.txt pointing at it, og:*/twitter meta, favicon + apple-touch-icon, semantic h1, real copy (no lorem). Submit once in Search Console."),
("fetch api pattern", "Robust frontend data loading.",
 "async function getJSON(u){const r=await fetch(u,{headers:{Accept:'application/json'}}); if(!r.ok) throw 0; return r.json()} with skeleton UI first, error panel on catch, setInterval refresh."),
("clipboard", "Copy-to-clipboard buttons.",
 "navigator.clipboard.writeText(t).catch(()=>{}) with a transient 'copied!' label swap. Requires secure context (https/localhost) — provide manual-select fallback."),
("localstorage theme", "Persist dark/light theme.",
 "On load: localStorage theme -> documentElement dataset. Toggle swaps + saves. Respect prefers-color-scheme on first visit. CSS vars do the rest."),
("ufw firewall", "Minimum VPS firewall.",
 "ufw allow 22,80,443/tcp; ufw enable. Everything else closed. Fail2ban optional next. Never expose Flask/dev ports publicly — bind 127.0.0.1 + nginx proxy."),
("cron jobs", "Scheduled shell tasks that don't spam.",
 "*/5 * * * * /path/job.sh >/dev/null 2>&1. Scripts must be idempotent + quiet on success. Secrets via env file sourced inside, never on the cron line."),
("backups", "Cheap disaster recovery.",
 "Nightly tar of data dir + sqlite to /backups with 7-day rotation; restic/rclone to object storage when it matters. Test restores quarterly — untested backups don't exist."),
("logrotate", "Stop disk-full crashes.",
 "If you log to files, ship /etc/logrotate.d/app with rotate 7 + compress + missingok. Prefer journald (auto-managed) for systemd services."),
("disk alerts", "Notice disk pressure early.",
 "Health check prints df -h + alerts over 80%. SQLite WAL + unbounded JSON logs are the usual culprits — cap lists, vacuum monthly."),
("git workflows", "Sane solo-dev git habits.",
 "main only + feature commits with verbs; pull --ff-only on hosts; never force-push shared branches; .gitignore secrets/env/venvs/logs before the first commit, not after."),
("gh cli", "GitHub without the browser.",
 "gh repo create/clone/view, gh api for REST, gh auth login once (keyring) then non-interactive forever. Script everything; never paste tokens into chat when gh auth exists."),
("gitignore hygiene", "Keep secrets out of git history.",
 ".env, *.pem, *token*, __pycache__, *.log at repo root on day one. Verify with git ls-files | grep -i env. Leaked secret? Rotate it immediately — history never forgets."),
("merge strategies", "Update hosts without losing local data.",
 "fetch, stash push -u (runtime JSON), pull --ff-only, stash pop best-effort. Abort loudly on unmerged state instead of looping. Runtime data files stay untracked-safe."),
("minimal bot perms", "Least-privilege Discord bots.",
 "Request Administrator only if truly needed; prefer granular (Manage Channels/Messages/Roles, Kick/Ban, Moderate). Document why in README so server owners trust the invite."),
("input validation", "Never trust user input in commands.",
 "Clamp numbers (1..100), cap string lengths, validate URLs start with http, parse durations with strict regex. Every !command is a public API endpoint."),
("owner gates", "Protect dangerous commands.",
 "OWNER_IDS set in env; helper _is_owner_id(uid) checked FIRST in eval/shell/update/restart commands. Admins get moderation; only owners get code execution."),
("string Snowflakes", "Discord IDs are strings in JSON.",
 "API returns ids as strings; int() them for arithmetic, str() for dict keys. Mixed-type lookups silently miss — normalize at the boundary (roles_by_id with str keys)."),
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


def _safe_call(fn, *args, **kwargs):
    try:
        return repr(fn(*args, **kwargs))
    except Exception as e:
        return f"raises {type(e).__name__}: {e}"


def behavioral(bot_dir):
    """Execute real bot helpers on sampled inputs -> grounded Q&A."""
    import sys as _sys
    _sys.path.insert(0, bot_dir)
    import bot as _b
    out = []

    def q(fn_name, call_src, thunk):
        try:
            out.append((f"In Python, what does `{call_src}` return?",
                        "", _safe_call(thunk)))
        except Exception:
            pass

    r = R
    for s in ["10s", "5m", "2h", "7d", "90s", "1d", "xx", "10x", ""]:
        q("parse_duration", f"parse_duration({s!r})",
          (lambda s=s: _b.parse_duration(s)))
    for n in [0, 1, 2, 5, 10, 15]:
        q("xp_needed", f"xp_needed({n})", (lambda n=n: _b.xp_needed(n)))
    for x in [0, 50, 99, 100, 101, 399, 400, 401, 1000, 2500, 10000]:
        q("level_for_xp", f"level_for_xp({x})", (lambda x=x: _b.level_for_xp(x)))
    for cur, need in [(0, 10), (5, 10), (7, 10), (10, 10), (3, 7)]:
        q("progress_bar", f"progress_bar({cur}, {need})",
          (lambda c=cur, n=need: _b.progress_bar(c, n)))
    for seed in [1, 2, 3]:
        q("pick_winners", f"pick_winners([1,2,3,4], 2, seed={seed})",
          (lambda s=seed: _b.pick_winners([1, 2, 3, 4], 2, seed=s)))
    for expr in ["2+3*4", "(10-4)/3", "2**8", "7%3", "10/4", "__import__('os')",
                 "1/0", "2+"]:
        q("safe_calc", f"safe_calc({expr!r})", (lambda e=expr: _b.safe_calc(e)))
    for w, g in [(("dragon", {"d", "a"})), (("python", set("py"))),
                 (("knight", set("knight")))]:
        q("hangman_display", f"hangman_display({w!r}, ...)",
          (lambda w=w, g=g: _b.hangman_display(w, g)))
    for b in [["X", "X", "X", "", "", "", "", "", ""],
              ["O", "", "", "", "O", "", "", "", "O"],
              ["X", "O", "X", "X", "O", "O", "O", "X", "X"],
              [""] * 9, ["X", "", "", "", "", "", "", "", ""]]:
        q("ttt_winner", f"ttt_winner({b})", (lambda b=b: _b.ttt_winner(b)))
    for b, s in [(["O", "O", "", "X", "X", "", "", "", ""], 0),
                 (["X", "X", "", "O", "", "", "", "", ""], 1),
                 ([""] * 9, 7)]:
        q("ttt_bot_move", f"ttt_bot_move(board, seed={s})",
          (lambda b=b, s=s: _b.ttt_bot_move(b, seed=s)))
    for gu, an in [("arose", "arose"), ("zzzzz", "arose"), ("erase", "arose"),
                   ("speed", "creed"), ("gamer", "gamer"), ("abcde", "fghij")]:
        q("wordle_feedback", f"wordle_feedback({gu!r}, {an!r})",
          (lambda g=gu, a=an: _b.wordle_feedback(g, a)))
    for h in [["A♠", "K♥"], ["A♠", "9♥", "A♦"], ["10♠", "9♥", "3♦"], ["5♣", "5♦"],
              ["J♦", "Q♣"], ["A♥", "A♦", "9♣"]]:
        q("bj_value", f"bj_value({h})", (lambda h=h: _b.bj_value(h)))
    for n, p, w in [("number", "7", 7), ("number", "7", 8), ("red", "", 7),
                    ("black", "", 7), ("red", "", 0), ("even", "", 4),
                    ("odd", "", 4), ("high", "", 20), ("low", "", 20),
                    ("even", "", 0)]:
        q("roulette_payout", f"roulette_payout({n!r}, {p!r}, {w})",
          (lambda n=n, p=p, w=w: _b.roulette_payout(n, p, w)))
    for s in [1, 2, 3]:
        q("roulette_spin", f"roulette_spin(seed={s})",
          (lambda s=s: _b.roulette_spin(seed=s)))
        q("coinflip_outcome", f"coinflip_outcome(50, 'heads', seed={s})",
          (lambda s=s: _b.coinflip_outcome(50, "heads", seed=s)))
        q("slots_outcome", f"slots_outcome(10, seed={s})",
          (lambda s=s: _b.slots_outcome(10, seed=s)))
    cfg = {"words": ["badword"], "spam": True, "invites": True, "mentions": True}
    for txt, men in [("hello world", 1), ("this has BadWord!", 0),
                     ("join discord.gg/abc", 0), ("hi", 6), ("hi", 2)]:
        q("automod_check", f"automod_check({txt!r}, {men}, cfg)",
          (lambda t=txt, m=men: _b.automod_check(t, m, cfg)))
    for last, lu, txt, au in [(5, 111, "6", 222), (5, 111, "8", 222),
                              (5, 111, "6", 111), (5, 111, "hi", 222), (0, 0, "1", 9)]:
        q("counting_check", f"counting_check({last}, {lu}, {txt!r}, {au})",
          (lambda a=last, b=lu, c=txt, d=au: _b.counting_check(a, b, c, d)))
    for c, lim in [(3, 3), (2, 3), (5, 3), (0, 1)]:
        q("starboard_qualifies", f"starboard_qualifies({c}, {lim})",
          (lambda c=c, l=lim: _b.starboard_qualifies(c, l)))
    for given, ans in [("Mars", ["mars"]), ("venus", ["mars"]), ("  TOKYO ", ["tokyo"])]:
        q("trivia_check", f"trivia_check({given!r}, {ans})",
          (lambda g=given, a=ans: _b.trivia_check(g, a)))
    for txt in ["hello there", "nothing here", "HEY BUDDY"]:
        q("trigger_match", f"trigger_match({txt!r}, {{'hello': 'hi!'}})",
          (lambda t=txt: _b.trigger_match(t, {"hello": "hi!"})))
    for old, new in [({"a": 5}, [("a", 5, "x"), ("b", 1, "y")]),
                     ({"a": 5}, [("a", 5, "x")])]:
        q("invite_finder", f"invite_finder({old}, ...)",
          (lambda o=old, n=new: _b.invite_finder(o, n)))
    for lo, now in [(1000.0, 1000.0 + 25 * 3600), (1000.0, 1000.0 + 3600)]:
        q("idle_close_due", f"idle_close_due({lo}, {now})",
          (lambda a=lo, b=now: _b.idle_close_due(a, b)))
    for last, per, now in [(1000.0, 60, 1030.0), (1000.0, 60, 1200.0), (0.0, 3600, 100.0)]:
        q("cooldown_left", f"cooldown_left({last}, {per}, {now})",
          (lambda a=last, b=per, c=now: _b.cooldown_left(a, b, c)))
    for u in ["https://discord.gg/abc", "<https://discord.gg/abc>", "nope", ""]:
        q("clean_invite", f"clean_invite({u!r})", (lambda u=u: _b.clean_invite(u)))
    _roles = {"1": "👑 Owner", "2": "Admin", "3": "Mod", "4": "Helper", "5": "Member"}
    for rids in [["1", "5"], ["2"], ["3"], ["4"], ["5"], []]:
        q("classify_member", f"classify_member({rids}, ...)",
          (lambda r=rids: _b.classify_member(r, _roles)))
    for hatk, mhp, matk, hhp, s in [(10, 30, 6, 100, 5), (12, 50, 10, 80, 7)]:
        q("rpg_round", f"rpg_round({hatk}, {mhp}, {matk}, {hhp}, seed={s})",
          (lambda a=hatk, b=mhp, c=matk, d=hhp, s=s: _b.rpg_round(a, b, c, d, seed=s)))
    for xp in [0, 99, 100, 250]:
        q("hero_level_check", f"hero_level_check(lvl1 {xp}xp)",
          (lambda x=xp: _b.hero_level_check({"lvl": 1, "xp": x, "maxhp": 100,
                                             "hp": 100, "atk": 10})))
    q("format_transcript", "format_transcript('support-x', [('t', 'u', 'hi')])",
      (lambda: _b.format_transcript("support-x", [("t", "u", "hi")])))
    for txt in ['py print(1)', '```py\nprint(1)\n```']:
        q("parse_code_arg", f"parse_code_arg({txt!r})",
          (lambda t=txt: _b.parse_code_arg(t)))
    bstate = dict(_b._stock_state["prices"])
    try:
        for s in [1, 2]:
            q("stocks_tick", f"stocks_tick(seed={s})",
              (lambda s=s: _b.stocks_tick(seed=s)))
    finally:
        _b._stock_state["prices"] = bstate
    for uid in [900001, 900002, 900003]:
        now = 1000.0 + (uid - 900001) * 0.4
        q("spam_hit", f"spam burst user {uid}",
          (lambda u=uid, n=now: [_b.spam_hit(u, n + i * 0.5) for i in range(6)][-1]))
    for expr in ["print(6*7)", "print(1+1)"]:
        q("run_py", f"run_py({expr!r})",
          (lambda e=expr: _b.run_py(e)[:60]))
    return out


def explain_pairs(bot_dir):
    """Explain-this-code pairs from documented functions."""
    import ast as _ast
    pairs = []
    for fn in ["bot.py", "control.py", "web.py", "cards.py"]:
        p = f"{bot_dir}/{fn}"
        try:
            src = open(p, encoding="utf-8").read()
            tree = _ast.parse(src)
        except Exception:
            continue
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = _ast.get_docstring(node)
            if not doc or len(doc) < 40:
                continue
            seg = _ast.get_source_segment(src, node) or ""
            if not seg or len(seg) > 1500:
                continue
            pairs.append(("Explain what this Python code does:", seg.strip(),
                          doc.strip()[:800]))
            if len(pairs) >= 60:
                return pairs
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot-dir", default=".")
    ap.add_argument("--out", default="dataset.jsonl")
    a = ap.parse_args()

    out = []
    for topic in (CURATED, CURATED2, CURATED3):
        for title, short, body in topic:
            for i, f in enumerate(REPHRASES):
                out.append({"instruction": f(short), "input": "", "output": body.strip()})
    out.extend({"instruction": i, "input": "", "output": o} for i, o in code_pairs(a.bot_dir))
    out.extend({"instruction": i, "input": inp, "output": o}
               for i, inp, o in behavioral(a.bot_dir) + explain_pairs(a.bot_dir))

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
             "curated_topics": len(CURATED) + len(CURATED2) + len(CURATED3),
             "generators": ["curated-x6", "code-ast", "behavioral-exec", "explain-code"]}
    json.dump(stats, open("stats.json", "w"), indent=2)
    print(f"wrote {len(final)} pairs, skipped {skipped} — {a.out}")


if __name__ == "__main__":
    main()
