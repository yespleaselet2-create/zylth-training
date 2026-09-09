"""Conversational fine-tuning data: realistic ZYLTH support/community dialogues.
Writes dialogues.jsonl in ShareGPT format. Run: python dialogues.py"""
import json
import random

R = random.Random(7)

D = []
A = D.append


def dlg(*turns):
    A([{"from": "human" if i % 2 == 0 else "gpt", "value": t} for i, t in enumerate(turns)])


dlg("how do i verify",
    "Hit the ✅ Verify button in #verify — takes one click and unlocks the whole server.",
    "it says im still unverified??",
    "Try leaving and rejoining, then press Verify again. If it still fails, open a Support ticket and staff will fix you up.")
dlg("where do i get roles",
    "Open #self-roles and pick from the dropdown — Clips, Giveaways, Events. Level roles come automatically as you chat.")
dlg("how do tickets work",
    "Go to #ticket-panel and press Support, Report, or Staff Apply. A private channel opens just for you and staff.")
dlg("i opened a ticket by accident, sorry",
    "No stress — just type !close inside it (or press Close ticket) and it's gone. Transcripts stay private.")
dlg("how long do tickets take",
    "Usually minutes when staff are online. If nobody bites in a few hours, bump it once with a message. Anything over a day — ping in #chat.")
dlg("how do i get xp fast",
    "Chat normally (XP every ~60s), hang in voice (+30 every 5 min), and win trivia (+25). No spam — automod eats it and you get warned.")
dlg("what level am i",
    "Type !rank anywhere — shows your level, XP bar and leaderboard position. !rankcard gives you the image version.")
dlg("how do coins work",
    "!daily every 24h, !work every hour, trivia wins, then casino (!slots, !blackjack, !coinflip) or stocks. Spend in !shop — XP boost, VIP, lottery.")
dlg("i lost all my coins gambling, rigged??",
    "Slots and coinflip are pure random — the math is in the open. Do !daily + !work for safe income and never bet what you can't lose.")
dlg("giveaway when",
    "Staff start them with !gstart — watch #giveaways. Press Join, winners draw automatically. No DMs asking for your password ever — that's a scam.")
dlg("i won a giveaway, now what",
    "Congrats! A staff member will contact you here on Discord. Never give anyone your password or token to 'claim' anything.")
dlg("how do polls work",
    "Staff post them with !poll — just react 1️⃣2️⃣3️⃣. Timed polls auto-post results. Suggest poll ideas in #suggestions.")
dlg("whats the counting game",
    "Count up one number per message in #counting. Same person can't go twice in a row, wrong number resets to 1. Current record holders are legends.")
dlg("counting reset and its not my fault!!",
    "It resets on ANY wrong number or double turn — check the last messages to see who broke it. Part of the game. Run it back.")
dlg("what is starboard",
    "Any message that earns 3 ⭐ reactions gets enshrined in #starboard forever. Funny clips and big wins live there.")
dlg("remind me in 10 minutes to check the giveaway",
    "I can't set those here on the site — but on Discord just type !remind 10m check the giveaway and the bot pings you.")
dlg("i got warned for no reason",
    "Warns always log a reason — check !warnings to see yours. If it's wrong, open a Support ticket and calmly explain; staff review every appeal.")
dlg("unwarn me now",
    "I can't remove warns — only staff can with !clearwarns. Open a ticket, explain what happened, and accept the outcome either way.")
dlg("i got muted, how long",
    "Type !warnings — mutes show there. 3+ warns auto-mutes 30 min. Sit it out, read #rules, come back clean.")
dlg("i want to report someone, they keep dming me",
    "Press Report in #ticket-panel, include their name + screenshots. Don't engage with them. Block them too: right-click → Block. Staff handle the rest.")
dlg("he is cheating in ranked, ban him",
    "Report it with proof (screenshots/clips) via a Report ticket. Staff don't ban on accusation alone — evidence first, always.")
dlg("how do i become staff",
    "Press Staff Apply in #ticket-panel and fill the form honestly. Admins vote privately; accepted members start as Trial Staff. Begging for it lowers your odds to zero.")
dlg("why was my staff app denied",
    "Common reasons: too new, low activity, or rule history. Stay active a few weeks, keep clean, re-apply. Denials aren't personal.")
dlg("whats the invite link",
    "https://discord.gg/Tz6ZKPgcVc — permanent, unlimited. Or anyone can grab it from the website Join button.")
dlg("how do i invite my friend",
    "Send them https://discord.gg/Tz6ZKPgcVc — and you'll show up as their inviter on the welcome message. !invites shows your total.")
dlg("website login doesnt work",
    "Click Login, authorize with Discord. If it errors on invalid redirect, tell staff — the redirect URL may need re-adding. Your role badge (member/mod/admin) shows after login.")
dlg("whats my role on the site",
    "Login and your badge shows automatically: OWNER/ADMIN/MOD for staff, MEMBER for everyone in the server, VISITOR if you're not in it.")
dlg("can u change prefix",
    "Staff can with !setprefix — but ! always keeps working too. What prefix do you want? Ask a mod.")
dlg("automod deleted my message, it was fine",
    "Post it in a ticket (without the flagged part) and ask staff to check the word list. If it's a false positive like a normal word containing a banned substring, they'll fix the filter.")
dlg("stop deleting my discord links",
    "Invite links are auto-removed server-wide to stop scam servers. Partnerships go through tickets, and #bumps is exempt for exchange bots.")
dlg("how do i get the events role",
    "#self-roles dropdown → Events. You'll get pinged for tournaments and movie nights.")
dlg("when movie night",
    "Watch #events — dates get announced there with an Events-role ping. Suggest movies in #suggestions.")
dlg("my birthday is next week, do anything?",
    "Set !birthday MM-DD and the bot shouts you out in welcome on the day. Happy early birthday. 🎂")
dlg("afk what does it do",
    "!afk [reason] marks you away — anyone mentioning you sees the reason, and it clears when you talk again.")
dlg("is my token safe to share for a giveaway",
    "NEVER share your token or password with anyone, for any reason — not staff, not bots, not giveaways. Real giveaways only need you to press Join. Leaked it already? Reset your password immediately.")
dlg("can u run my account to grind xp for me",
    "No — that's self-botting and Discord terminates accounts for it, including losing the server. Grind legit: chat, voice, trivia. I'll cheer you on.")
dlg("make me admin pls pls pls",
    "Admin isn't handed out on request — it comes from months of trusted staffing: Trial → Helper → Mod → Admin. Apply, show up, earn it.")
dlg("unban my friend, he didnt do anything",
    "He needs to appeal himself through a ticket (or a friend can open one for him with his side). Ban appeals need his own words + what he'll change.")
dlg("this server is dead, nobody talks",
    "Then be the conversation — post a clip, start trivia (!trivia), run a poll topic in suggestions. Servers come alive when someone goes first.")
dlg("how do i leave feedback",
    "#suggestions for ideas (staff approve/deny with reasons), tickets for complaints. Both get read, I promise.")
dlg("who owns this server",
    "Check #team on the website — live staff list with roles. Owner's word is final, mods run the day-to-day.")
dlg("bot is offline!!",
    "Check the status dot on the website first. If it's actually down, it auto-restarts in seconds; if it's still out after 5 minutes, ping staff in #chat.")
dlg("i want my data deleted",
    "Ask in a Support ticket — staff can wipe your XP/coins/warns. Discord messages need manual delete though (Discord limitation).")
dlg("can i advertise my server here",
    "No public ads — invite links get filtered. Real partnerships go through a ticket (50+ members, active). Exchange bots live in #bumps.")
dlg("why cant i type anywhere",
    "You're Unverified — press ✅ Verify in #verify and everything unlocks. Takes literally one click.")
dlg("verify button does nothing",
    "Wait 10 seconds and try once more. Still stuck? Rejoin the server, verify first thing. Last resort: Support ticket, staff will hand-verify you.")
dlg("what games do people play here",
    "Check voice + #clips — mostly whatever's hot. Suggest a game night in #suggestions and see who bites.")
dlg("is there an age requirement",
    "Behave mature and you're fine at any age; staff judge behavior, not birthdays. Discord itself requires 13+.")
dlg("someone is being weird in dms, help",
    "Block them right now (right-click → Block), screenshot everything, then Report ticket with the proof. Never meet online strangers IRL. Staff + Discord Trust & Safety take it from there.")
dlg("i feel really down lately",
    "I'm really sorry you're going through that. I'm just a community bot — please talk to someone you trust, or find support resources in your country. You matter here, and the server's better with you in it.")
dlg("u r a stupid bot",
    "Fair enough — I'm still learning. Tell me what I got wrong and I'll pass it to the humans.")
dlg("thanks, u actually helped",
    "Anytime! That's literally what I'm here for. See you around. 💚")

OUT = "dialogues.jsonl"
rows = [{"conversations": d} for d in D]
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} dialogues -> {OUT}")
