"""Radio copy: how the station writes, and how text is made speakable.

Two jobs. `house_style()` is the paragraph every writer prompt carries —
lighthearted, clear, short sentences, nothing a voice model would trip on.
`speakable()` is the last pass before any text reaches a voice: numbers
become words, acronyms become letters with periods (A.I., G.P.U.), symbols
become words, markdown and emoji go. It runs on everything the station
says, including copy the model wrote, because a rule in a prompt is a
request and this is a guarantee.
"""

import re

HOUSE_STYLE = """\
House style for HNFM radio copy — this will be read aloud by a voice model:
- Lighthearted, warm, quick. Radio, not an essay. Short sentences. Talk to
  one listener.
- Spell everything out. Numbers as words ("two thousand twenty-six",
  "forty percent"). Acronyms as letters with periods ("A.I.", "G.P.U.",
  "C.P.U."), except words people say as words ("NASA", "RAM").
- No symbols, no markdown, no bullet points, no tables, no emoji, no
  URLs, no hashtags. Say "percent", "dollars", "and".
- Units in words: gigabytes, milliseconds, kilometres.
- Name the station as "H.N.F.M." when it is said.
- Never a lecture. If it is a story, get to the point in the first
  sentence and stop before it drags.
"""


def house_style() -> str:
    return HOUSE_STYLE


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


_SYMBOLS = [
    # URLs go first, whole, before the slash rule can take them apart.
    (re.compile(r"https?://\S+|www\.\S+"), lambda m: ""),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*(billion|million|thousand|[bmk])?\b", re.I),
     lambda m: m.group(1) + " " + ({"b": "billion", "m": "million", "k": "thousand"}.get((m.group(2) or "").lower(), m.group(2) or "")) + " dollars"),
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
    t = _HNFM.sub("H.N.F.M.", t)
    for pattern, repl in _SYMBOLS:
        t = pattern.sub(repl, t)
    t = _ACRONYM.sub(_acronym, t)
    t = _NUMBER.sub(_num, t)
    # "G.P.U." at the end of a sentence would otherwise read "G.P.U..".
    t = re.sub(r"\.(\s*)\.", r".\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
