import uvicorn

if __name__ == "__main__":
    uvicorn.run("scraper.scraper:app", reload=True)