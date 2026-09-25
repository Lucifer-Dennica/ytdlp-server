from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import os
import base64

app = FastAPI()

class Req(BaseModel):
    url: str

@app.get("/")
def root():
    return {"status": "ok", "service": "yt-dlp"}

@app.post("/api/resolve")
async def resolve(req: Req):
    try:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best[height<=1080]/best',
            'skip_download': True,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web_creator', 'ios', 'mweb', 'tv_embedded', 'web_safari', 'android'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
            },
        }

        # Cookies через Base64 (если задана переменная)
        cookies_b64 = os.environ.get("YTDLP_COOKIES_B64")
        if cookies_b64:
            cookies_path = "/tmp/cookies.txt"
            with open(cookies_path, "wb") as f:
                f.write(base64.b64decode(cookies_b64))
            opts['cookiefile'] = cookies_path

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
            video_url = info.get('url')
            if not video_url and info.get('formats'):
                for f in reversed(info['formats']):
                    if f.get('ext') == 'mp4' and f.get('url'):
                        video_url = f['url']
                        break
            if not video_url:
                raise HTTPException(500, "No video URL found")
            return {
                "video_url": video_url,
                "thumbnail": info.get('thumbnail'),
                "title": info.get('title', 'video'),
            }
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(500, f"Download error: {str(e)[:300]}")
    except Exception as e:
        raise HTTPException(500, str(e)[:300])
