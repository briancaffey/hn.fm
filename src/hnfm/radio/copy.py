"""Text a voice can read.

`speakable()` is the last pass before any text reaches a voice: numbers
become words, acronyms become letters with periods (A.I., G.P.U.), symbols
become words, markdown and emoji go. It runs on everything the station
says, including copy the model wrote, because a rule in a prompt is a
request and this is a guarantee. The house style itself is the system
prompt of `prompts/radio.write.yaml`.
"""

import re


# --- numbers to words ------------------------------------------------------

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALE = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (10 ** 3, "thousand"), (100, "hundred")]


def number_words(n: int) -> str:
    if n < 0:
        return "minus " + number_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    for value, name in _SCALE:
        if n >= value:
            head = number_words(n // value) + " " + name
            rest = n % value
            return head if not rest else head + " " + number_words(rest)
    return str(n)


def _year_words(n: int) -> str:
    """Years read the way people say them: nineteen ninety-four, twenty
    twenty-six, two thousand and eight."""
    if 1100 <= n <= 1999 or 2010 <= n <= 2099:
        hi, lo = divmod(n, 100)
        return number_words(hi) + " " + (number_words(lo) if lo >= 10 else "oh-" + _ONES[lo] if lo else "hundred")
    return number_words(n)


def _num(match: re.Match) -> str:
    raw = match.group(0)
    digits = raw.replace(",", "")
    if "." in digits:
        whole, frac = digits.split(".", 1)
        return (number_words(int(whole)) if whole else "zero") + " point " + " ".join(_ONES[int(c)] for c in frac if c.isdigit())
    n = int(digits)
    if 1100 <= n <= 2099 and "," not in raw and len(digits) == 4:
        return _year_words(n)
    return number_words(n)


def clock_words(hour: int, minute: int) -> str:
    """4:04 -> four oh four; 12:30 -> twelve thirty; 9:00 -> nine o'clock."""
    h = hour % 12 or 12
    if minute == 0:
        return number_words(h) + " o'clock"
    if minute < 10:
        return number_words(h) + " oh " + number_words(minute)
    return number_words(h) + " " + number_words(minute)


def time_words(dt) -> str:
    """A datetime the way a host says it: four oh four in the morning."""
    part = "in the morning" if dt.hour < 12 else "in the afternoon" if dt.hour < 18 else "in the evening"
    return clock_words(dt.hour, dt.minute) + " " + part


def _clock(match: re.Match) -> str:
    h, m, ampm = int(match.group(1)), int(match.group(2)), (match.group(3) or "").replace(".", "").upper()
    if h > 23 or m > 59:
        return match.group(0)
    if ampm == "PM" and h < 12:
        h += 12
    if ampm == "AM" and h == 12:
        h = 0
    return clock_words(h, m) + (" " + ".".join(ampm) + "." if ampm else "")


_SYMBOLS = [
    (re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM|am|pm|a\.m\.|p\.m\.)?\b"), _clock),
    # URLs go first, whole, before the slash rule can take them apart.
    (re.compile(r"https?://\S+|www\.\S+"), lambda m: ""),
    # The unit is optional and so is the space before it; the space is only
    # consumed with a unit, or "$2.11 one run" becomes "dollarsone run".
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)(?:\s*(billion|million|thousand|[bmk])\b)?", re.I),
     lambda m: m.group(1) + (" " + {"b": "billion", "m": "million", "k": "thousand"}.get(m.group(2).lower(), m.group(2).lower()) if m.group(2) else "") + " dollars"),
    (re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*%"), lambda m: m.group(1) + " percent"),
    (re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(GB|MB|KB|TB)\b"), lambda m: m.group(1) + " " + {"GB": "gigabytes", "MB": "megabytes", "KB": "kilobytes", "TB": "terabytes"}[m.group(2)]),
    (re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(ms)\b"), lambda m: m.group(1) + " milliseconds"),
    (re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(km)\b"), lambda m: m.group(1) + " kilometres"),
    (re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*x\b"), lambda m: m.group(1) + " times"),
    (re.compile(r"\s*&\s*"), lambda m: " and "),
    (re.compile(r"\s*\+\s*"), lambda m: " plus "),
    (re.compile(r"(?<=\w)/(?=\w)"), lambda m: " slash "),
    (re.compile(r"[#*_`>|~\[\]{}<>=^]"), lambda m: " "),
]

# Said as words, not spelled.
_SAY_AS_WORD = {"NASA", "RAM", "ROM", "LASER", "SCUBA", "RADAR", "NATO", "UNIX", "LINUX", "JSON", "SQL", "GNU",
                "MIT", "HNFM", "ASAP", "FAQ", "WIFI", "OK", "CEO", "USB"}
# Spelled with periods even though they could be read as a word.
_SPELL = {"AI", "API", "CPU", "GPU", "LLM", "TTS", "CLI", "SDK", "UI", "UX", "HTTP", "HTML", "CSS", "URL",
          "SSD", "HDD", "PDF", "IPO", "EU", "US", "UK", "PR", "OS", "VR", "AR", "ML", "NLP", "AWS", "GCP", "IBM"}
_ACRONYM = re.compile(r"\b([A-Z]{2,6})(s?)\b")
_HNFM = re.compile(r"\bHNFM\b")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


_ORDINAL_WORDS = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                  "nine": "ninth", "twelve": "twelfth"}
_ORDINAL = re.compile(r"\b(\d{1,4})(?:st|nd|rd|th)\b")


def ordinal_words(n: int) -> str:
    """10 -> tenth, 21 -> twenty-first, 30 -> thirtieth."""
    words = number_words(n)
    head, sep, last = words.rpartition("-") if "-" in words.split()[-1] else words.rpartition(" ")
    if last in _ORDINAL_WORDS:
        last = _ORDINAL_WORDS[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return head + sep + last


def _acronym(match: re.Match) -> str:
    word, plural = match.group(1), match.group(2)
    if word in _SAY_AS_WORD:
        return word + plural
    if word in _SPELL or len(word) <= 4:
        return ".".join(word) + "." + plural
    return word + plural


def speakable(text: str) -> str:
    """Text a voice model will read the way a person would."""
    t = text or ""
    t = _EMOJI.sub("", t)
    # Dashes read as a pause; curly quotes and ellipses as their plain kin.
    t = re.sub(r"\s*[—–]\s*|\s+-\s+", ", ", t)
    t = t.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "…": "."}))
    t = _HNFM.sub("H.N.F.M.", t)
    # "10th-century" is "tenth-century", not "ten th".
    t = _ORDINAL.sub(lambda m: ordinal_words(int(m.group(1))), t)
    for pattern, repl in _SYMBOLS:
        t = pattern.sub(repl, t)
    t = _ACRONYM.sub(_acronym, t)
    # "arm64" and "30B" are a word and a number; without the space they
    # came out as "armsixty-four".
    t = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", t)
    t = _NUMBER.sub(_num, t)
    # "G.P.U." at the end of a sentence would otherwise read "G.P.U..", and
    # an ellipsis is just a full stop to a voice.
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"\.(\s*)\.", r".\1", t)
    # A whole line wrapped in quote marks is the writer, not the speaker.
    t = t.strip()
    if len(t) > 2 and t[0] == '"' and t[-1] == '"' and t.count('"') == 2:
        t = t[1:-1]
    t = re.sub(r"\s+", " ", t).strip()
    return t
