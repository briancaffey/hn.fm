# 21 — The Studio: watch the station work

## Why

The radio (plans/20) is five components talking to each other, and a page
of numbers does not show that. The Studio draws the station as a place —
a retro-futurist radio set staffed by robots — where each component is a
thing you can see doing its job, in real time, with its own commentary
beside it. It is the explanation of how the pieces fit, and it is also
just fun to watch.

## The feed

`radio_log` is the station's running commentary: one row per thing a
component did, written by the components themselves through `radio.log()`
(never fatal). The DJ asks what's next; the director serves item 4 of 13;
the producer is thinking, then planned a block; the bank recorded a line
in Sofia's voice; the monitor finished its round. `GET /api/radio/stream`
is server-sent events: every new line as it lands, plus a `snapshot` frame
of the whole station every few seconds. `GET /api/radio/studio` is one
frame for the first paint.

## The set (TresJS, all primitives, no models to load)

Left to right on a dark floor, isometric camera, orbit allowed:

| What you see | What it is | What moves |
|---|---|---|
| **The Library** — shelves of records and cassettes, a rack of glowing cards | the bank (music beds, station IDs) and the finished episodes | stacks grow as the bank fills; a card lights when its episode is queued |
| **The Producer's desk** — a boxy robot with one big eye, a dot-matrix printer, a paper strip of coloured tiles | the producer and the current block | the eye pulses while the model is thinking; the printer chatters and a new strip comes out when a block is planned; a cursor moves along the tiles as items are served |
| **The Switchboard** — a hexagonal hub with tubes to every station | the hn.fm API | glowing packets travel the tubes: DJ → hub ("what's next?"), hub → DJ (the answer), DJ → hub ("on air"), hub → desk ("plan a block") |
| **The DJ booth** — a robot in headphones, two decks, a tonearm on a robotic arm, a VU meter, an ON AIR sign | Liquidsoap | deck A spins the item on air (disc colour by kind); the arm swaps discs on every track change; the meter bounces while broadcasting; the sign lights when Icecast has the mount |
| **The Transmitter** — a mast on the right | Icecast | rings expand while on air; one orb orbits per listener |
| **The Drone** — a small patrol drone | the station manager (the monitor task) | flies a lap and hovers at the desk when a round completes |

Colour: charcoal set, warm white light, the HNFM orange for anything on
air, one cyan for data packets. Kinds: episode orange, music cyan, station
ID white, coming-up amber, time check lavender.

## The commentary, in the scene

The live log is not a panel beside the scene; each line appears as a
small label next to the component that said it and fades after a few
seconds, so you watch the conversation happen where it happens. A compact
ticker at the bottom keeps the last dozen lines for reading back, colour-
coded by component, and clicking a component in the legend explains what
it is in two sentences.

## The jokes (kept to a few, and placed)

A "works on my machine" sticker on the DJ console. A rubber duck on the
producer's desk. A mug that says `kubectl get pods`. A neon sign reading
NOT A BOT (mostly). A whiteboard with "TODO: prod" and a `tabs | spaces`
scale toy. Nothing that needs explaining, nothing that moves.

## Cost

The scene is a few hundred primitives and one SSE connection. It renders
on an integrated GPU at 60 fps and costs the backend one cheap query a
second per open tab. It is a page under `/radio/studio` and is gated like
the rest of the radio: absent when the station is off.
