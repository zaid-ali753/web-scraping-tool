from fastapi import FastAPI, Query
from pydantic import BaseModel
from bs4 import BeautifulSoup
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from retry import retry
from requests.exceptions import RequestException
import json
import re
import requests
# import uuid

app = FastAPI()

# def generate_uuid():
#     return uuid.uuid4().hex
# random_uuid = generate_uuid()
# print(random_uuid)

STATIC_TOKEN = "7fc682b04628438a87ed4b1a9622d580"

security = HTTPBearer()

async def authenticate_credentials(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.scheme != "Bearer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication scheme")
    if credentials.credentials != STATIC_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
    return True


class Item(BaseModel):
    base_url: str
    max_pages: int = 0
    proxy: str

scraped_cache = {}

@app.get("/scrape")
async def scrape(item: Item, authenticated: bool = Depends(authenticate_credentials)):
    scarped_data = []
    for page_number in range(1, item.max_pages + 1):
        url = f"{item.base_url}?page={page_number}"
        try:
            response = await fetch_with_retry(url, item.proxy)
            response.raise_for_status()
        except RequestException as e:
            print(f"Error accessing page {url}: {e}")
            continue
        soup = BeautifulSoup(response.content, "html.parser")
        h2_text = soup.find_all('div', class_='mf-product-content')
        img_src = soup.find_all('div', class_='mf-product-thumbnail')
        price_text = soup.find_all('div', class_='mf-product-price-box')
        for title, price, img in zip(h2_text, price_text, img_src):
            product_name = title.a.text
            path_to_image = img.find('img')
            if path_to_image:
              src_value = path_to_image.get('src')
            product_price_raw = price.find('span', class_='price').text.strip()
            product_price = re.search(r'₹([\d.]+)', product_price_raw).group(1)
            if product_name in scraped_cache and scraped_cache[product_name]["product_price"] == product_price:
                continue
            product_info = {
                "product_name": product_name,
                "product_price":  "Rs. " + product_price,
                "path_to_image": src_value
            }
            scraped_cache[product_name] = product_info
            product_info_json = json.dumps(product_info)
            scarped_data.append(product_info_json)
            

    with open("products.json", "w") as f:
        json.dump(scarped_data, f, indent=4)

    return {"message": f"Scraped {len(h2_text)* item.max_pages} products from {item.max_pages} pages",
            "DB Updates" : f"{len(h2_text)* item.max_pages} Products Added"}

@retry(RequestException, tries=3, delay=5)
async def fetch_with_retry(url: str, proxy: str = None) -> requests.Response:
    return requests.get(url, proxies={"http": proxy} if proxy else None)