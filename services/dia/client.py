import os
from pathlib import Path

import requests


BASE_URL = os.environ.get("DIA_API", "http://0.0.0.0:8491")


def save_bytes_to_file(content: bytes, dest_path: Path) -> None:
    with open(dest_path, "wb") as f:
        f.write(content)


def post_generate(form: dict, files=None) -> requests.Response:
    url = f"{BASE_URL}/generate"
    resp = requests.post(url, data=form, files=files, timeout=600)
    resp.raise_for_status()
    return resp


def main():
    # 1) Health
    health = requests.get(f"{BASE_URL}/health", timeout=30).json()
    print("Health:", health)

    # Common text
    gen_text = (
        "[S1] Dia is an open weights text to dialogue model. "
        "[S2] You get full control over scripts and voices."
    )

    # 2) First generation without prompt
    print("Generating without audio prompt...")
    resp1 = post_generate(
        {
            "text": gen_text,
            "max_new_tokens": 1024,
            "cfg_scale": 3.0,
            "temperature": 1.8,
            "top_p": 0.95,
            "cfg_filter_top_k": 45,
            "speed_factor": 1.0,
            "seed": -1,
        }
    )
    print("Response 1 headers:", dict(resp1.headers))

    wav1 = Path("output_no_prompt.wav").resolve()
    save_bytes_to_file(resp1.content, wav1)
    print("Saved:", wav1)

    # 3) Second generation with example prompt
    print("Generating with audio prompt...")
    prompt_path = Path("example_prompt.mp3").resolve()
    if not prompt_path.exists():
        raise SystemExit(f"Missing prompt file: {prompt_path}")

    audio_prompt_text = (
        "[S1] Open weights text to dialogue model. \n[S2] You get full control over scripts and voices."
    )
    files = {"audio_prompt": (prompt_path.name, open(prompt_path, "rb"), "audio/mpeg")}
    try:
        resp2 = post_generate(
            {
                "text": gen_text,
                "audio_prompt_text": audio_prompt_text,
                "max_new_tokens": 1024,
                "cfg_scale": 3.0,
                "temperature": 1.8,
                "top_p": 0.95,
                "cfg_filter_top_k": 45,
                "speed_factor": 1.0,
                "seed": -1,
            },
            files=files,
        )
    finally:
        files["audio_prompt"][1].close()

    print("Response 2 headers:", dict(resp2.headers))
    wav2 = Path("output_with_prompt.wav").resolve()
    save_bytes_to_file(resp2.content, wav2)
    print("Saved:", wav2)

    # 4) Cleanup
    cleanup = requests.post(f"{BASE_URL}/cleanup", timeout=30).json()
    print("Cleanup:", cleanup)


    # Common text
    gen_text = (
        "[S1] Cleanup has been performed. "
        "[S2] Now we will run the model again to profile the memory usage."
    )

    # 3) First generation without prompt
    print("Generating without audio prompt...")
    try:
        resp3 = post_generate(
            {
                "text": gen_text,
                "max_new_tokens": 1024,
                "cfg_scale": 3.0,
                "temperature": 1.8,
                "top_p": 0.95,
                "cfg_filter_top_k": 45,
                "speed_factor": 1.0,
                "seed": -1,
            }
        )
    finally:
        files["audio_prompt"][1].close()

    print("Response 3 headers:", dict(resp3.headers))
    wav3 = Path("output_with_prompt_3.wav").resolve()
    save_bytes_to_file(resp3.content, wav3)
    print("Saved:", wav3)

    # Cleanup
    cleanup = requests.post(f"{BASE_URL}/cleanup", timeout=30).json()
    print("Cleanup:", cleanup)


if __name__ == "__main__":
    main()


