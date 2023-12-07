from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
import databases
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, MetaData, select
from databases import Database
from sqlalchemy.ext.declarative import declarative_base

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
mongo_client = AsyncIOMotorClient("mongodb://your_username:your_password@mongodb:27017")

db = mongo_client["mongodb"]
collection = db["users"]

DATABASE_URL = "postgresql://your_username:your_password@postgres:5432/your_database"

database = Database(DATABASE_URL)
metadata = MetaData()

engine = create_engine(DATABASE_URL)
Base = declarative_base()


class User(Base):
    __tablename__ = "postgres"
    id = Column(Integer, primary_key=True, index=True)
    fullname = Column(String, index=True)
    email = Column(String, index=True)
    password = Column(String)
    phone = Column(String)


Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def startup_db_client():
    await database.connect()


@app.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/register/", response_class=HTMLResponse)
async def registered(
        request: Request,
        fullname: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        phone: str = Form(...),
        profile: UploadFile = File(...),
):
    query = select(User).where(User.email == email)
    result = await database.fetch_one(query)
    if result:
        return templates.TemplateResponse("success.html", {"request": request, "user_id": result["fullname"], "registered": True})


    # Save to PostgreSQL
    query = User.__table__.insert().values(
        fullname=fullname, email=email, password=password, phone=phone
    )
    await database.execute(query)
    # Save to MongoDB
    contents = await profile.read()
    user_data = {"profile": contents}
    await collection.insert_one(user_data)
    return templates.TemplateResponse("success.html", {"request": request, "user_id": fullname})
