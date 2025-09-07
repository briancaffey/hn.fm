# Dia server

https://github.com/nari-labs/dia


FastAPI server that taks text or text + audio sample and directly returns generated speech using nari-labs/dia.

This is a simpler alternative to using the Gradio API for doing TTS over HTTP. Also, gradio will sometimes hog memory after many generations and doesn't have an easy way of clearing memory. This server exposes an endpoint that can unload the model, freeing up memory.