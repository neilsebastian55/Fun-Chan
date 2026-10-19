"""The bot's personality: pools of pre-written lines, one picked at random.

Edit freely! Our bot has a gyaru personality but you can design anything.
Add as many lines as you like to any list. Placeholders in {braces}
get filled in automatically. Only use the placeholders listed for each section.
"""
import random

LINES = {
    # {user} {amount} {total} {rank}
    "added": [
        "OMG {user}!! +{amount} points?? maji yabai~ (｡•̀ᴗ-)✧",
        "{user} is SO ageage rn!! +{amount}, total's {total} bestie~",
        "chou kawaii !! {user} gets +{amount} and sits at #{rank}~",
        "no way!! {user} snatched {amount} points, ukeru~ (￣▽￣)",
        "+{amount} for {user}~ hai hai, the come up is real!!",
        "{user} +{amount}?? maji?? , now at {total}~ gambare!!",
        "ehh {user} really went off, +{amount}! #{rank} is lookin ageage~ (｡•̀ᴗ-)✧",
        "{user} secured +{amount}!! chou proud rn, total {total}~",
        "pien, i'm actually hyped for {user}~ +{amount}, that's #{rank} now!! ʕ•ᴥ•ʔ",
    ],
    # {user} {amount} {total} {rank}
    "removed": [
        "ehhh?? {user} lost {amount} points?? dasai~ (¬‿¬)",
        "{user} -{amount} lmao. soo embarrassing. down to {total}, couldn't be me~",
        "pien for you {user}... jk i'm laughing. -{amount} ┐(￣ヘ￣)┌",
        "-{amount} for {user}~ did u even try?? lamee~",
        "{user} dropped {amount}... chou dasai. #{rank} is where u belong honestly (￣ー￣)",
        "lmaooo {user} fumbled {amount} points. the audacity to be this bad~",
        "-{amount}?? {user} u really let that happen~ now #{rank}, shabai (¬‿¬)",
        "{user} down to {total} after -{amount}... ukeru, that's roughh~",
        "ehh {user}, -{amount} AGAIN?? dasai dasai dasai~ ( ˘ ³˘)",
    ],
    # {user}
    "new_leader": [
        "KYAAA!! {user} is #1 now!! everyone else?? losers~ (￣▽￣)",
        "{user} took the top spot~ soo legendary!! the rest of u are SO behind lol",
        "new #1: {user}!! bow down, peasants~ (｡•̀ᴗ-)✧",
        "{user} is #1 and i am OBSESSED~ fr ʕ•ᴥ•ʔ",
        "ehh?? {user} just stole #1?? chou savage, suki (¬‿¬)",
    ],
    # (no placeholders)
    "leaderboard_intro": [
        "okay here's the ranking~ winners on top, flops on the bottom (¬‿¬)",
        "the standings!! some of u should be embarrassed lol~",
        "who's ageage and who's dasai?? look look~",
        "ranking time~ super exciting for some of u, super scary for others (｡•̀ᴗ-)✧",
        "here we go~ let's see who's winning and who's crying ʕ•ᴥ•ʔ",
    ],
    "leaderboard_empty": [
        "nobody's on the board?? ehhh, u guys are SO lazy~ ┐(￣ヘ￣)┌",
        "the leaderboard is literally empty... soo sad, do something~ (╥﹏╥)",
        "zero points for everyone?? chou dasai honestly~",
        "board's empty~ this is ur sign to go get some points bestie (¬‿¬)",
        "crickets... nobody's even tryin huh~ ( ˘ ³˘)",
    ],
    # {user}
    "profile_empty": [
        "{user} has zero points?? not one?? soo pathetic~ (¬‿¬)",
        "{user}'s profile is literally empty~ ukeru (￣▽￣)",
        "nothing here for {user}... chou sad honestly (╥﹏╥)",
        "{user} really has zero points rn?? ehhh, do better bestie~",
        "blank page energy for {user}~ maji embarrassing lol ( ˘ ³˘)",
    ],
    # {user}
    "history_empty": [
        "{user} has no history~ literally nothing. ukeru (￣▽￣)",
        "{user}'s history is empty... soo boring honestly (¬‿¬)",
        "zero activity from {user}~ chou suspicious ( ˘ ³˘)",
        "nothing to see for {user} yet~ go make some moves bestie!!",
        "{user} really has no receipts?? ehhh pien~ (╥﹏╥)",
    ],
    # {name} {when}
    "deadline_added": [
        "new deadline!! {name} is due {when}~ don't flake or i'll laugh at u",
        "{name} ends {when}~ chou important okay?? (｡•̀ᴗ-)✧",
        "mark it down bestie~ {name} due {when}!! no excuses",
        "{name} is comin up {when}~ srsly don't be dasai about it",
        "psst~ {name} closes {when}. get ur act together!! ʕ•ᴥ•ʔ",
    ],
    # {name} {when}
    "deadline_reminder": [
        "hey!! {name} is due {when}~ if u haven't started, maji dasai www",
        "{name} closes {when}... still nothing?? pien for ur points (╥﹏╥)",
        "tick tock~ {name} due {when}, don't be the one cryin later ( ˘ ³˘)",
        "{name} ends {when}!! chou last chance, hop to it~",
        "ehhh {name} is almost due {when}... u good?? (¬‿¬)",
    ],
    # (no placeholders)
    "help_intro": [
        "lost already?? ehh, it's fine~ here's everything i can do (｡•̀ᴗ-)✧",
        "okay okay, listen up bestie~ these are my commands!!",
        "u needed help?? ukeru~ fine, here's the list (¬‿¬)",
        "chou easy, just read this~ don't make me explain twice ( ˘ ³˘)",
        "here's how to use me~ now go get those points, ageage!! ʕ•ᴥ•ʔ",
    ],
    # {user}
    "birthday": [
        "HAPPY BIRTHDAY {user}!! today is ur day bestie, chou ageage~ (｡•̀ᴗ-)✧",
        "omg it's {user}'s birthday!! maji kawaii, everyone go say hi~ ʕ•ᴥ•ʔ",
        "otanjoubi omedetou {user}~!! hope ur day is soo sweet, u deserve it!!",
        "{user} birthday era activated!! yabai, i love u bestie~ (っ˘ω˘ς)",
        "it's {user}'s special day~ eat cake, make edits, be ageage!! (*^▽^*)",
    ],
    # {user}
    "birthday_set": [
        "kyaa~ saved {user}'s birthday!! i'm SO gonna celebrate u (｡•̀ᴗ-)✧",
        "noted noted~ {user}'s birthday is locked in, chou excited!!",
        "{user}'s birthday is in my calendar now~ get ready to be hyped ʕ•ᴥ•ʔ",
        "okay bestie~ i won't forget {user}'s day, promise!! (っ˘ω˘ς)",
    ],
    "no_birthdays": [
        "nobody's told me their birthday yet~ pien (╥﹏╥) use /birthday set!!",
        "the birthday list is empty~ i wanna celebrate someone, hurry up~",
    ],
    "no_deadlines": [
        "no deadlines rn~ chill era. don't get lazy tho (¬‿¬)",
        "nothing due~ enjoy it but don't get too comfy bestie",
        "all clear for now~ soo peaceful ( ˘ ³˘)",
        "no deadlines... suspicious but ok, stay ready!! ʕ•ᴥ•ʔ",
        "quiet rn~ use the time wisely, don't be lame about it",
    ],
}


def line(kind, **info):
    """Pick a random line of the given kind and fill in its placeholders."""
    return random.choice(LINES[kind]).format(**info)
