# HNFM on air — the DJ (plans/20).
#
# Liquidsoap 2.4. Served by the API at GET /api/radio/script and run by the
# `liquidsoap` container, so a change here deploys with the backend and the
# chart never carries a copy.
#
# What it does, in order:
#   1. asks hn.fm what to play next (request.dynamic -> /api/radio/next)
#   2. skips dead air, crossfades between items
#   3. falls back to a safety loop, then silence, so the stream never drops
#   4. encodes one 128k MP3 and pushes it to Icecast
#   5. tells hn.fm about every track change (on_track -> /api/radio/events)
#   6. answers POST /skip on its own small HTTP port, for the page's button

settings.log.stdout := true
settings.log.level := 3

api = environment.get("HNFM_API_BASE")
mount = environment.get("RADIO_MOUNT")
icecast_host = environment.get("ICECAST_HOST")
icecast_port = int_of_string(environment.get("ICECAST_PORT"))
icecast_pass = environment.get("ICECAST_SOURCE_PASSWORD")
safety_file = environment.get("RADIO_SAFETY")

# 1. What's next. hn.fm answers with a path and the metadata to attach.
def next_item() =
  # Thirty seconds: the API answers from a planned block in milliseconds,
  # and plans a fast block inline when it has none.
  answer = http.get("#{api}/api/radio/next", timeout=30.0)
  let json.parse (j : {
    path: string, title: string, kind: string,
    ref: string?, host: string?, bank_id: string?, sheet_id: string?
  }) = answer
  meta = [
    ("title", j.title), ("hnfm_kind", j.kind),
    ("hnfm_ref", j.ref ?? ""), ("hnfm_host", j.host ?? ""),
    ("hnfm_bank_id", j.bank_id ?? ""), ("hnfm_sheet", j.sheet_id ?? ""),
  ]
  # Metadata rides on the request as an annotate: URI, the standard way to
  # attach it to a file before it plays.
  pairs = list.map(fun (kv) -> "#{fst(kv)}=#{string.quote(snd(kv))}", meta)
  joined = string.concat(separator=",", pairs)
  request.create("annotate:#{joined}:#{j.path}")
end

# Two items fetched ahead: the join between tracks must never wait on HTTP.
programme = request.dynamic(id="programme", prefetch=2, retry_delay=3.0, next_item)

# 2. Never more than a few seconds of silence, and gentle joins.
# Twelve seconds before dead air counts as a broken file: episodes pause.
programme = blank.skip(max_blank=12.0, programme)
# A short join, not a long one: every file the station makes already ends
# in a beat of silence, and a long crossfade ate the last words of a story.
programme = crossfade(duration=0.6, fade_in=0.2, fade_out=0.5, programme)

# 5. Tell hn.fm what just started.
def report(m) =
  ignore(http.post(
    "#{api}/api/radio/events",
    headers=[("content-type", "application/json")],
    data=json.stringify(m), timeout=10.0))
end
programme.on_track(synchronous=false, report)

# 3. Safety net: a music bed the bank keeps at a fixed path, then silence.
safety =
  if file.exists(safety_file) then
    single(id="safety", safety_file)
  else
    blank(id="silence", duration=10.0)
  end
radio = fallback(id="radio", track_sensitive=false, [programme, mksafe(safety)])

# 6. The page's skip button. POST /skip on port 8080 (inside the network only).
def skip_handler(_, response) =
  programme.skip()
  response.data("skipped\n")
end
harbor.http.register(port=8080, method="POST", "/skip", skip_handler)
# And a heartbeat for the Services page.
def health_handler(_, response) =
  response.data("ok\n")
end
harbor.http.register(port=8080, method="GET", "/health", health_handler)

# 4. On air.
output.icecast(
  %mp3(bitrate=128),
  host=icecast_host, port=icecast_port, password=icecast_pass,
  mount=mount, name="HNFM", description="Hacker News, on air", genre="Talk",
  radio)
