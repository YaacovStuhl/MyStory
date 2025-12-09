import os
import time
import requests


def generate_story_images(child_image_path, story_key, child_name, gender):
    """Generate 12 scene images using an external image API.

    Configuration via env:
      IMAGE_API_URL: POST endpoint that accepts JSON with fields: prompt, image_url(optional), num_images
      IMAGE_API_KEY: Bearer token for Authorization

    Expected response: JSON with key 'images' listing direct image URLs.
    This is a generic adapter; adjust to your provider's schema as needed.
    """
    provider = (os.getenv("IMAGE_API_PROVIDER") or "").lower()
    prompts = build_scene_prompts(story_key, child_name, gender)

    if provider == "openai":
        return _generate_with_openai(child_image_path, prompts)

    # Generic provider via IMAGE_API_URL/IMAGE_API_KEY (expects URLs in 'images')
    api_url = os.getenv("IMAGE_API_URL")
    api_key = os.getenv("IMAGE_API_KEY")
    if api_url and api_key:
        files = {"image": open(child_image_path, "rb")}
        headers = {"Authorization": f"Bearer {api_key}"}
        images = []
        for prompt in prompts:
            try:
                resp = requests.post(api_url, headers=headers, files=files, data={"prompt": prompt})
                resp.raise_for_status()
                payload = resp.json()
                url = extract_first_image_url(payload)
                if url:
                    images.append(download_image(url))
            except Exception:
                continue
            time.sleep(0.2)
        return images

    return []


def build_scene_prompts(story_key, name, gender):
    style = (
        "whimsical storybook, soft lighting, vibrant colors, consistent child character, "
        "clean line art, gentle shading, cinematic framing, high quality illustration"
    )
    if (story_key or "").lower() == "red":
        scenes = [
            f"{name} wearing a red hood sets out with a basket through a sunny forest, {style}",
            f"{name} greeting birds and flowers along the path, {style}",
            f"A clever wolf meets {name} on the trail, {style}",
            f"{name} wandering a bright meadow while the wolf sneaks away, {style}",
            f"A cozy cottage in the woods, {name} approaches the door, {style}",
            f"Inside the cottage, a disguised figure in bed, {name} looks puzzled, {style}",
            f"Close-up of surprised {name}: big eyes, ears, and teeth moment, {style}",
            f"{name} stalls for time, calling for help, {style}",
            f"A friendly woodcutter enters, the wolf bolts, {style}",
            f"{name} and grandmother reunite, warm embrace, {style}",
            f"Sharing treats at a small table, laughter, {style}",
            f"Sunset over the forest as {name} heads home, {style}",
        ]
    else:
        scenes = [
            f"{name} and {('his' if (gender or '').lower()=='boy' else 'her')} mother at a small cottage, {style}",
            f"{name} trades a cow for magic beans at a market stall, {style}",
            f"A towering beanstalk rises to the clouds overnight, {style}",
            f"{name} climbing the beanstalk against a bright sky, {style}",
            f"A castle among clouds with a gentle giant inside, {style}",
            f"A golden harp sings softly as {name} listens, {style}",
            f"Giant returns: {name} hides behind a chest, {style}",
            f"{name} grabs the harp and runs toward the beanstalk, {style}",
            f"Chase down the beanstalk, wind and motion, {style}",
            f"On the ground: {name} calls for an axe, {style}",
            f"Beanstalk falls, scene of relief and safety, {style}",
            f"{name} and family celebrate at home, warm glow, {style}",
        ]
    return scenes


def extract_first_image_url(payload):
    if isinstance(payload, dict):
        if "images" in payload and payload["images"]:
            first = payload["images"][0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url")
        if "output" in payload and payload["output"]:
            first = payload["output"][0]
            if isinstance(first, str):
                return first
    return None


def download_image(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def _generate_with_openai(child_image_path, prompts):
    """Use OpenAI Images Edits API per scene with the uploaded child photo as reference.

    Env vars:
      OPENAI_API_KEY: required
      OPENAI_IMAGE_MODEL: optional (default gpt-image-1)
      OPENAI_IMAGE_SIZE: optional (default 1024x1024)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []

    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")
    url = "https://api.openai.com/v1/images/edits"

    images = []
    for prompt in prompts:
        try:
            with open(child_image_path, "rb") as f:
                files = {
                    "image": (os.path.basename(child_image_path), f, "application/octet-stream"),
                }
                data = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    # You can set response_format to b64_json to avoid another GET
                    "response_format": "url",
                }
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = requests.post(url, headers=headers, data=data, files=files, timeout=120)
                resp.raise_for_status()
                js = resp.json()
                # OpenAI returns { data: [ { url: ... } ] }
                if isinstance(js, dict) and js.get("data"):
                    first = js["data"][0]
                    if first.get("url"):
                        images.append(download_image(first["url"]))
        except Exception:
            continue
        time.sleep(0.2)
    return images


