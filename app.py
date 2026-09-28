from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import os
import base64

app = FastAPI()

class Req(BaseModel):
    url: str
    audio_only: bool = False
    quality: str = "max"  # max / 1080 / 720 / 480 / 360

@app.get("/")
def root():
    return {"status": "ok", "service": "yt-dlp"}

def build_format(quality: str, audio_only: bool) -> str:
    if audio_only:
        # Только аудио, m4a предпочтительнее (нативно поддерживается Android)
        return "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best"
    if quality == "max":
        return "best[ext=mp4]/best"
    # quality = "1080", "720", "480", "360"
    return f"best[height<={quality}][ext=mp4]/best[height<={quality}]/best"

@app.post("/api/resolve")
async def resolve(req: Req):
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": build_format(req.quality, req.audio_only),
            "skip_download": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["tv", "mweb"],
                    "player_skip": ["webpage", "configs"],
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
            },
        }

        cookies_b64 = os.environ.get("YTDLP_COOKIES_B64")
        if cookies_b64:
            cookies_path = "/tmp/cookies.txt"
            with open(cookies_path, "wb") as f:
                f.write(base64.b64decode(cookies_b64))
            opts["cookiefile"] = cookies_path

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=False)

            # Иногда yt-dlp возвращает playlist-структуру
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            media_url = info.get("url")
            ext = info.get("ext", "mp4")

            # Fallback: ищем в formats
            if not media_url and info.get("formats"):
                if req.audio_only:
                    for f in reversed(info["formats"]):
                        if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none"):
                            media_url = f.get("url")
                            ext = f.get("ext", "m4a")
                            if media_url:
                                break
                else:
                    for f in reversed(info["formats"]):
                        if f.get("ext") == "mp4" and f.get("url"):
                            media_url = f["url"]
                            ext = "mp4"
                            break

            if not media_url:
                raise HTTPException(500, "No media URL found")

            return {
                "video_url": media_url,
                "thumbnail": info.get("thumbnail"),
                "title": info.get("title", "media"),
                "ext": ext,
            }
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(500, f"Download error: {str(e)[:300]}")
    except Exception as e:
        raise HTTPException(500, str(e)[:300])
