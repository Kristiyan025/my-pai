import os
import sys
from typing import List, Optional, Any
import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Web Search Agent",
    description="Web search and content fetching agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]


class FetchURLRequest(BaseModel):
    url: str
    extract_text: bool = True
    max_length: int = 10000


class FetchedContent(BaseModel):
    url: str
    title: Optional[str] = None
    content: str
    content_type: str


async def duckduckgo_search(query: str, max_results: int = 5) -> List[SearchResult]:
    results = []
    
    try:
        # Use DuckDuckGo HTML version
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        data = {"q": query}
        
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for result in soup.find_all("div", class_="result")[:max_results]:
                title_elem = result.find("a", class_="result__a")
                snippet_elem = result.find("a", class_="result__snippet")
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")
                    
                    if "uddg=" in href:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = parsed.get("uddg", [href])[0]
                    
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append(SearchResult(
                        title=title,
                        url=href,
                        snippet=snippet
                    ))
                    
    except Exception as e:
        print(f"Search error: {e}")
        
    return results


async def fetch_url_content(url: str, extract_text: bool = True, max_length: int = 10000) -> FetchedContent:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "text/html")
        title = None
        
        if "text/html" in content_type and extract_text:
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            main_content = soup.find("main") or soup.find("article") or soup.find("body")
            
            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)
            
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)
            
            if len(text) > max_length:
                text = text[:max_length] + "...[truncated]"
            
            content = text
        else:
            content = response.text[:max_length]
            if len(response.text) > max_length:
                content += "...[truncated]"
        
        return FetchedContent(
            url=str(response.url),
            title=title,
            content=content,
            content_type=content_type.split(";")[0]
        )


@app.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=1, description="Search query"),
    max_results: int = Query(5, ge=1, le=20, description="Maximum results")
):
    results = await duckduckgo_search(query, max_results)
    return SearchResponse(query=query, results=results)


@app.post("/search", response_model=SearchResponse)
async def search_post(query: str, max_results: int = 5):
    results = await duckduckgo_search(query, max_results)
    return SearchResponse(query=query, results=results)


@app.post("/fetch", response_model=FetchedContent)
async def fetch_url(request: FetchURLRequest):
    try:
        return await fetch_url_content(
            url=request.url,
            extract_text=request.extract_text,
            max_length=request.max_length
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch URL: {e.response.status_code}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


@app.get("/fetch")
async def fetch_url_get(
    url: str = Query(..., description="URL to fetch"),
    extract_text: bool = Query(True, description="Extract text from HTML"),
    max_length: int = Query(10000, description="Max content length")
):
    try:
        return await fetch_url_content(
            url=url,
            extract_text=extract_text,
            max_length=max_length
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


@app.post("/search-and-fetch")
async def search_and_fetch(
    query: str,
    max_results: int = 3,
    max_fetch_length: int = 5000
):
    search_results = await duckduckgo_search(query, max_results)
    
    results_with_content = []
    for result in search_results:
        try:
            fetched = await fetch_url_content(
                url=result.url,
                extract_text=True,
                max_length=max_fetch_length
            )
            results_with_content.append({
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "fetched_content": fetched.content
            })
        except Exception as e:
            results_with_content.append({
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "fetched_content": None,
                "fetch_error": str(e)
            })
    
    return {
        "query": query,
        "results": results_with_content
    }


class ImageSearchResult(BaseModel):
    title: str
    url: str
    image_url: str
    thumbnail_url: Optional[str] = None
    source: str


async def search_images_unsplash(query: str, max_results: int = 5) -> List[ImageSearchResult]:
    results = []
    
    # Use picsum for reliable random images with seeded URLs for consistency
    for i in range(min(max_results, 3)):
        seed = f"{query.replace(' ', '')}{i}"
        image_url = f"https://picsum.photos/seed/{seed}/800/600"
        results.append(ImageSearchResult(
            title=f"{query} image {i+1}",
            url=f"https://picsum.photos/",
            image_url=image_url,
            thumbnail_url=f"https://picsum.photos/seed/{seed}/200/150",
            source="picsum"
        ))
    
    return results


async def search_wikipedia_images(query: str, max_results: int = 5) -> List[ImageSearchResult]:
    results = []
    
    try:
        headers = {
            "User-Agent": "PAI-Assistant/1.0 (Educational project)"
        }
        
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": "6",
            "gsrlimit": max_results,
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "iiurlwidth": 800
        }
        
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.get(search_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                pages = data.get("query", {}).get("pages", {})
                
                for page_id, page_data in pages.items():
                    if page_data.get("imageinfo"):
                        info = page_data["imageinfo"][0]
                        if "image" in info.get("mime", ""):
                            results.append(ImageSearchResult(
                                title=page_data.get("title", "").replace("File:", ""),
                                url=info.get("descriptionurl", ""),
                                image_url=info.get("thumburl", info.get("url", "")),
                                thumbnail_url=info.get("thumburl", ""),
                                source="wikipedia"
                            ))
    except Exception as e:
        print(f"Wikipedia image search error: {e}")
    
    return results


async def search_images_loremflickr(query: str, max_results: int = 5) -> List[ImageSearchResult]:
    results = []
    
    for i in range(min(max_results, 3)):
        image_url = f"https://loremflickr.com/800/600/{query}?random={i}"
        results.append(ImageSearchResult(
            title=f"{query} image {i+1}",
            url=f"https://loremflickr.com/",
            image_url=image_url,
            thumbnail_url=f"https://loremflickr.com/200/150/{query}?random={i}",
            source="loremflickr"
        ))
    
    return results


async def duckduckgo_image_search(query: str, max_results: int = 5) -> List[ImageSearchResult]:
    results = []
    
    try:
        url = "https://duckduckgo.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.get(url, headers=headers, params={"q": query})
            
            import re
            vqd_match = re.search(r'vqd=([^&]+)', response.text)
            if not vqd_match:
                vqd_match = re.search(r'vqd"?:\s*"?(\d+-\d+)', response.text)
            
            if vqd_match:
                vqd = vqd_match.group(1)
                
                img_url = "https://duckduckgo.com/i.js"
                params = {
                    "l": "us-en",
                    "o": "json",
                    "q": query,
                    "vqd": vqd,
                    "f": ",,,",
                    "p": "1"
                }
                
                img_response = await client.get(img_url, headers=headers, params=params)
                if img_response.status_code == 200:
                    data = img_response.json()
                    for item in data.get("results", [])[:max_results]:
                        results.append(ImageSearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            image_url=item.get("image", ""),
                            thumbnail_url=item.get("thumbnail", ""),
                            source=item.get("source", "duckduckgo")
                        ))
    except Exception as e:
        print(f"DuckDuckGo image search error: {e}")
    
    if not results:
        print(f"DDG image search returned no results, trying Wikipedia")
        results = await search_wikipedia_images(query, max_results)
    
    if not results:
        print(f"Wikipedia image search also failed, using picsum fallback")
        results = await search_images_unsplash(query, max_results)
    
    if not results:
        try:
            web_results = await duckduckgo_search(f"{query} image", max_results)
            for r in web_results:
                if any(ext in r.url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    results.append(ImageSearchResult(
                        title=r.title,
                        url=r.url,
                        image_url=r.url,
                        source="web_search"
                    ))
        except Exception as e:
            print(f"Fallback search error: {e}")
    
    return results


@app.get("/images/search")
async def search_images(
    query: str = Query(..., description="Image search query"),
    max_results: int = Query(5, ge=1, le=20, description="Maximum results")
):
    results = await duckduckgo_image_search(query, max_results)
    return {"query": query, "results": results}


class DownloadImageRequest(BaseModel):
    query: str
    save_path: Optional[str] = None


@app.post("/images/download")
async def download_image(request: DownloadImageRequest):
    import base64
    
    results = await duckduckgo_image_search(request.query, max_results=5)
    
    if not results:
        raise HTTPException(status_code=404, detail="No images found for query")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
        for result in results:
            try:
                image_url = result.image_url or result.url
                response = await client.get(image_url, headers=headers)
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                if "image" in content_type or any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    if "jpeg" in content_type or "jpg" in content_type or ".jpg" in image_url.lower():
                        ext = ".jpg"
                    elif "png" in content_type or ".png" in image_url.lower():
                        ext = ".png"
                    elif "gif" in content_type or ".gif" in image_url.lower():
                        ext = ".gif"
                    elif "webp" in content_type or ".webp" in image_url.lower():
                        ext = ".webp"
                    else:
                        ext = ".jpg"
                    
                    image_data = base64.b64encode(response.content).decode()
                    
                    return {
                        "success": True,
                        "query": request.query,
                        "source_url": image_url,
                        "title": result.title,
                        "content_type": content_type,
                        "extension": ext,
                        "image_base64": image_data,
                        "size_bytes": len(response.content)
                    }
            except Exception as e:
                print(f"Failed to download from {result.image_url}: {e}")
                continue
    
    raise HTTPException(status_code=500, detail="Failed to download any images from search results")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "web-search-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8013)
