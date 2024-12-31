import uvicorn
from fastapi.responses import RedirectResponse
from fastapi import FastAPI
from src.routers import users_router,qna_router
from src.config import APPNAME, VERSION

from datetime import timedelta
# Defining the application
app = FastAPI(
    title=APPNAME,
    version=VERSION,
)

# Including all the routes for the 'users' module
app.include_router(users_router)
app.include_router(qna_router)

@app.get("/")
def main_function():
    """
    Redirect to documentation (`/docs/`).
    """
    return RedirectResponse(url="/docs/")

@app.post("/token")
def forward_to_login():
    """
    Redirect to token-generation (`/auth/token`). Used to make Auth in Swagger-UI work.
    """
    return RedirectResponse(url="/token")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
