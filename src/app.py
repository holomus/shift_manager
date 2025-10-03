from fastapi import FastAPI
from router import SolveRouter

app = FastAPI(title="Shift Scheduler API")

app.include_router(SolveRouter)

@app.get("/")
def root():
    return {"message": "Shift Scheduler is running 🚀"}