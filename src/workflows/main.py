"""Application setup - imports and middleware only"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.workflows.api.endpoints import router

app = FastAPI(title="Hospital Appointment Booking API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)