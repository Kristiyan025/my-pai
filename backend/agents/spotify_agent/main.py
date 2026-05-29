import os
import sys
import base64
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI(
    title="Spotify Agent",
    description="Spotify integration for music playback control",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


APIKEYS_SERVICE_URL = os.getenv("APIKEYS_SERVICE_URL", "http://apikeys-service:8004")
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
USER_ID = 1

_token_cache: Dict[int, Dict[str, Any]] = {}


class SpotifyCredentials(BaseModel):
    client_id: str
    client_secret: str
    refresh_token: str


class TrackInfo(BaseModel):
    name: str
    artist: str
    album: str
    duration_ms: int
    uri: str
    is_playing: bool = False


class PlaybackState(BaseModel):
    is_playing: bool
    track: Optional[TrackInfo] = None
    progress_ms: int = 0
    device_name: Optional[str] = None


class SearchResult(BaseModel):
    tracks: List[TrackInfo]


class PlayRequest(BaseModel):
    uri: Optional[str] = None
    search_query: Optional[str] = None


async def get_spotify_credentials(user_id: int) -> Optional[SpotifyCredentials]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{APIKEYS_SERVICE_URL}/apikeys/{user_id}/spotify")
            if response.status_code == 200:
                data = response.json()
                return SpotifyCredentials(
                    client_id=data.get("spotify_client_id", ""),
                    client_secret=data.get("spotify_client_secret", ""),
                    refresh_token=data.get("spotify_refresh_token", "")
                )
        except Exception as e:
            print(f"Error fetching credentials: {e}")
    return None


async def get_access_token(user_id: int) -> str:
    if user_id in _token_cache:
        cached = _token_cache[user_id]
        if cached["expires_at"] > datetime.now():
            return cached["access_token"]
    
    creds = await get_spotify_credentials(user_id)
    if not creds or not creds.refresh_token:
        raise HTTPException(status_code=401, detail="Spotify credentials not configured")
    
    auth_header = base64.b64encode(
        f"{creds.client_id}:{creds.client_secret}".encode()
    ).decode()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            SPOTIFY_AUTH_URL,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to refresh Spotify token")
        
        data = response.json()
        access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        
        _token_cache[user_id] = {
            "access_token": access_token,
            "expires_at": datetime.now() + timedelta(seconds=expires_in - 60)
        }
        
        return access_token


async def spotify_request(
    user_id: int,
    method: str,
    endpoint: str,
    data: Optional[Dict] = None
) -> Optional[Dict]:
    token = await get_access_token(user_id)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.request(
            method=method,
            url=f"{SPOTIFY_API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            json=data
        )
        
        if response.status_code == 204:
            return None
        elif response.status_code in (200, 201):
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Spotify API error: {response.text}"
            )


def parse_track(track_data: Dict) -> TrackInfo:
    artists = track_data.get("artists", [])
    artist_names = ", ".join(a.get("name", "") for a in artists)
    
    return TrackInfo(
        name=track_data.get("name", "Unknown"),
        artist=artist_names or "Unknown Artist",
        album=track_data.get("album", {}).get("name", "Unknown Album"),
        duration_ms=track_data.get("duration_ms", 0),
        uri=track_data.get("uri", "")
    )


@app.get("/playback", response_model=PlaybackState)
async def get_playback_state(user_id: int = USER_ID):
    data = await spotify_request(user_id, "GET", "/me/player")
    
    if not data:
        return PlaybackState(is_playing=False)
    
    track = None
    if data.get("item"):
        track = parse_track(data["item"])
        track.is_playing = data.get("is_playing", False)
    
    device = data.get("device", {})
    
    return PlaybackState(
        is_playing=data.get("is_playing", False),
        track=track,
        progress_ms=data.get("progress_ms", 0),
        device_name=device.get("name")
    )


@app.post("/playback/play")
async def play(request: PlayRequest, user_id: int = USER_ID):
    data = None
    
    if request.search_query:
        results = await spotify_request(
            user_id, "GET",
            f"/search?q={request.search_query}&type=track&limit=1"
        )
        tracks = results.get("tracks", {}).get("items", [])
        if tracks:
            data = {"uris": [tracks[0]["uri"]]}
        else:
            raise HTTPException(status_code=404, detail="No tracks found")
            
    elif request.uri:
        if request.uri.startswith("spotify:track:"):
            data = {"uris": [request.uri]}
        else:
            data = {"context_uri": request.uri}
    
    await spotify_request(user_id, "PUT", "/me/player/play", data)
    return {"status": "playing"}


@app.post("/playback/pause")
async def pause(user_id: int = USER_ID):
    await spotify_request(user_id, "PUT", "/me/player/pause")
    return {"status": "paused"}


@app.post("/playback/next")
async def next_track(user_id: int = USER_ID):
    await spotify_request(user_id, "POST", "/me/player/next")
    return {"status": "skipped"}


@app.post("/playback/previous")
async def previous_track(user_id: int = USER_ID):
    await spotify_request(user_id, "POST", "/me/player/previous")
    return {"status": "previous"}


@app.post("/playback/volume")
async def set_volume(volume: int = Query(..., ge=0, le=100), user_id: int = USER_ID):
    await spotify_request(user_id, "PUT", f"/me/player/volume?volume_percent={volume}")
    return {"status": "volume_set", "volume": volume}


@app.post("/playback/shuffle")
async def set_shuffle(state: bool = True, user_id: int = USER_ID):
    await spotify_request(user_id, "PUT", f"/me/player/shuffle?state={str(state).lower()}")
    return {"status": "shuffle_set", "shuffle": state}


@app.get("/search", response_model=SearchResult)
async def search_tracks(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    user_id: int = USER_ID
):
    results = await spotify_request(
        user_id, "GET",
        f"/search?q={query}&type=track&limit={limit}"
    )
    
    tracks = [
        parse_track(t)
        for t in results.get("tracks", {}).get("items", [])
    ]
    
    return SearchResult(tracks=tracks)


@app.get("/devices")
async def get_devices(user_id: int = USER_ID):
    data = await spotify_request(user_id, "GET", "/me/player/devices")
    return {"devices": data.get("devices", [])}


@app.post("/devices/transfer")
async def transfer_playback(device_id: str, user_id: int = USER_ID):
    await spotify_request(
        user_id, "PUT", "/me/player",
        {"device_ids": [device_id], "play": True}
    )
    return {"status": "transferred"}


@app.get("/profile")
async def get_profile(user_id: int = USER_ID):
    data = await spotify_request(user_id, "GET", "/me")
    return {
        "display_name": data.get("display_name"),
        "email": data.get("email"),
        "country": data.get("country"),
        "product": data.get("product")
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "spotify-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8014)
