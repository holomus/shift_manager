import uvicorn

from fastapi import FastAPI
from router import SolveRouter

app = FastAPI(title="Shift Scheduler API")

app.include_router(SolveRouter)

@app.get("/")
def root():
    return {"message": "Shift Scheduler is running 🚀"}


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="debug"
    )