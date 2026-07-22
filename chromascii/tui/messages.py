import random

from . import state

STAT_MESSAGES = [
    "You've rendered {n} characters. Your terminal thanks you for its suffering.",
    "{n} characters rendered. That's a lot of tiny colored squares.",
    "Lifetime total: {n} characters. Somewhere, a font is very tired.",
    "{n} characters and counting — chromascii salutes you.",
    "You just added to a grand total of {n} characters rendered. No refunds.",
    "{n} characters rendered so far. Michelangelo painted a ceiling. You painted a terminal.",
    "Fun fact: you've rendered {n} characters. Not that fun, but here we are.",
    "{n} characters rendered. Somewhere a GPU is jealous of your CPU's dedication.",
    "You've turned {n} characters into art. Or something adjacent to art.",
    "{n} characters rendered. That's enough to write a very confusing novel.",
    "Achievement unlocked: {n} characters rendered. No trophy included.",
    "{n} characters and still going. The terminal has seen things.",
    "You've rendered {n} characters in your chromascii career. Legendary.",
    "{n} characters rendered. Your keyboard is proud, probably.",
    "Total characters rendered: {n}. Please don't do the math on the electricity bill.",
    "{n} characters rendered so far — one pixel at a time, one character at a time.",
    "You are {n} characters deep into this. There is no shallow end.",
    "{n} characters rendered. Somewhere, an ASCII purist is nodding slowly.",
    "Congratulations, you've rendered {n} characters. Tell your friends. Or don't.",
    "{n} characters rendered. This message also counts as characters, technically.",
    "Running total: {n} characters. You could have written several emails instead.",
    "{n} characters rendered — chromascii approves of your life choices.",
    "You've rendered {n} characters. Somewhere, a rainbow feels seen.",
    "{n} characters and counting. The terminal never sleeps, and apparently neither do you.",
    "Lifetime rendering total: {n} characters. Frame by frame, one at a time.",
    "{n} characters rendered. That's a lot of @ # $ % symbols working overtime.",
    "You've officially rendered {n} characters. History will remember this. Probably not.",
    "{n} characters rendered so far. Your terminal has never felt so colorful.",
    "Total: {n} characters. Somewhere, a printer is quietly relieved it wasn't asked to do this.",
    "{n} characters rendered. This is either impressive or concerning. Maybe both.",
    "You've rendered {n} characters into existence. Chromascii is honored.",
    "{n} characters and counting — one terminal, infinite possibilities.",
    "Grand total: {n} characters rendered. No characters were harmed in the making of this stat.",
    "{n} characters rendered. You could tile a small room with this many symbols.",
    "You've rendered {n} characters. That's basically a modern art installation.",
    "{n} characters rendered so far. The ASCII gods are pleased.",
    "Running count: {n} characters. Somewhere, a designer is quietly impressed.",
    "{n} characters rendered. Your dedication to colored squares is unmatched.",
    "Total characters rendered: {n}. Keep going, the terminal believes in you.",
    "{n} characters rendered. This number only goes up. Much like your enthusiasm, hopefully.",
    "You've rendered {n} characters. Somewhere, a spreadsheet wishes it was this exciting.",
    "{n} characters and counting. chromascii: turning bytes into beauty since v0.1.",
    "Lifetime total: {n} characters. You've basically hand-painted the internet.",
    "{n} characters rendered. Not bad for something that runs in a terminal.",
    "You've rendered {n} characters. Somewhere, a cat is dancing in celebration. (Try the '?' menu.)",
]

FACTS = [
    "Fun fact: ASCII art predates the internet — it started on 1960s teletype printers.",
    "Fun fact: the term 'ASCII art' didn't catch on until BBS culture took off in the 1980s.",
    "Fun fact: the emoticon :-) was proposed by Scott Fahlman in 1982, timestamp and all.",
    "Fun fact: colored ASCII ('ANSI art') was a whole underground artscene on 1990s BBSes.",
    "Fun fact: the block characters █▓▒░ you might be seeing trace back to IBM's original PC character set from 1981.",
    "Fun fact: full ASCII renditions of Star Wars, frame by frame, were floating around BBSes in the 1990s — asciimation is still online today.",
    "Fun fact: the @ symbol is an ASCII-art favorite purely because of how visually dense it looks.",
    "Fun fact: monospace fonts exist so every character lines up — a proportional font would wreck any ASCII art instantly.",
    "Fun fact: some artists still hand-place every single character — no software, just patience.",
    "Fun fact: sextant block characters (the sharpest mode here) are from Unicode 13.0, released in 2020.",
    "Fun fact: ASCII itself dates to 1963 — this whole art form is older than color television.",
    "Fun fact: the first computer to display ASCII art was likely just a teletype with a very patient operator.",
]

MEDIA_MESSAGES = [
    "You've watched {videos} videos through chromascii so far.",
    "{gifs} gifs rendered and counting — loop after loop after loop.",
    "You've viewed {images} images in glorious terminal color.",
    "{webcams} webcam sessions and counting. Somewhere, a mirror feels replaced.",
    "Media diary: {videos} videos, {gifs} gifs, {images} images. A well-rounded terminal life.",
    "You've fired up the webcam {webcams} times. The camera knows you well by now.",
    "{gifs} gifs deep. Some things are just meant to loop forever.",
    "{images} images turned to color and light. Not bad for a terminal.",
]

FAREWELLS = [
    "Terminal's yours again. See you next time.",
    "Goodbye — may your terminal stay colorful.",
    "Session closed. The pixels shall be missed.",
    "Exiting. Thanks for the color.",
    "See you soon — the cat will be waiting. (Try the '?' menu.)",
    "chromascii signing off. Stay colorful.",
    "That's a wrap. Your terminal returns to its usual dull self now.",
    "Bye! The ASCII gods approve of this session.",
    "Closing up. Come back and render something beautiful again soon.",
    "Farewell — one more colorful terminal session in the books.",
    "Logging off. The rainbow will be here when you get back.",
    "Until next time — keep it colorful out there.",
]

DOWNLOAD_PHRASES = [
    'convincing the internet to cooperate…',
    'downloading pixels one by one…',
    'negotiating with the server…',
    'fetching bytes, please hold…',
    'summoning the video…',
    'asking nicely for the file…',
    'reticulating splines…',
    'unpacking the internet…',
    'chasing packets…',
    'politely requesting data…',
]

_POOL = STAT_MESSAGES + FACTS + MEDIA_MESSAGES


def _fmt_count(n):
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.1f}K'
    return str(n)


def next_message(total_chars):
    s = state.load()
    bag = s.get('msg_bag') or []
    if not bag:
        bag = list(range(len(_POOL)))
        random.shuffle(bag)
    idx = bag.pop(0)
    s['msg_bag'] = bag
    state.save(s)

    return _POOL[idx].format(
        n=_fmt_count(total_chars),
        videos=s.get('videos_watched', 0),
        gifs=s.get('gifs_watched', 0),
        images=s.get('images_viewed', 0),
        webcams=s.get('webcam_sessions', 0),
    )


def random_farewell():
    return random.choice(FAREWELLS)


def random_download_phrase():
    return random.choice(DOWNLOAD_PHRASES)
