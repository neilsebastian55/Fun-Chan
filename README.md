## Fun-chan

Discord bot created for H2HF (an art collective founded by @tthree). Serves as an elo/point tracker for members as well as event organization tool.

## Install and run (Windows)

You need Python 3.10 or newer (https://python.org — tick "Add Python to PATH" when installing).

Open a terminal in this folder:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Open `.env` in Notepad, fill in the values, save, then:

```
python bot.py
```

You should see `Logged in as ...`. The slash commands appear in your server right away
(if not, restart Discord with Ctrl+R).

## Commands

| Command                                        | Permissions            |
| ---------------------------------------------- | ---------------------- |
| `/points add @user amount reason`              | Admins (Manage Server) |
| `/points remove @user amount reason`           | Admins                 |
| `/leaderboard`                                 | Everyone               |
| `/profile [@user]`                             | Everyone               |
| `/history [@user]`                             | Everyone               |
| `/deadline add name date [time] [description]` | Admins                 |
| `/deadline remove name`                        | Admins                 |
| `/deadlines`                                   | Everyone               |
| `/birthday set month day [@user]`              | Everyone (`@user`: mods) |
| `/birthday remove [@user]`                     | Everyone (`@user`: mods) |
| `/birthdays`                                   | Everyone               |
| `/help`                                        | Everyone               |

Admin commands are hidden from anyone without **Manage Server**. To let a specific role
use them instead, go to **Server Settings → Integrations → your bot** and adjust.



## Customizing the personality

Edit `personality.py`. Add lines to any list; restart the bot to load them.

## Files

- `bot.py` — commands
- `db.py` — database (creates `points.db` automatically; back this file up!)
- `personality.py` — personality
