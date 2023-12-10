from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import create_engine, Column, Integer, String, MetaData, select
from databases import Database
from sqlalchemy.ext.declarative import declarative_base
from PIL import Image
from io import BytesIO
import base64

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
mongo_client = AsyncIOMotorClient("mongodb://username:password@mongodb:27017")

db = mongo_client["database"]
collection = db["Profile"]


DATABASE_URL = "postgresql://username:password@postgres:5432/database"

database = Database(DATABASE_URL)
metadata = MetaData()

engine = create_engine(DATABASE_URL)
Base = declarative_base()


class User(Base):
    __tablename__ = "Users"
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
    query = select(User).where(User.email == email or User.phone == phone)

    result = await database.fetch_one(query)
    if result:
        return templates.TemplateResponse(
            "success.html",
            {"request": request,
                "user_id": result["fullname"], "registered": True},
        )

    # Save to PostgresSQL
    query = User.__table__.insert().values(
        fullname=fullname, email=email, password=password, phone=phone
    )
    await database.execute(query)
    # Save to MongoDB
    contents = await profile.read()
    user_data = {"profile": contents, "email": email}
    await collection.insert_one(user_data)
    return templates.TemplateResponse(
        "success.html", {"request": request, "user_id": fullname}
    )


@app.get("/users/", response_class=HTMLResponse)
async def users(request: Request):
    query = User.__table__.select()
    users_result = await database.fetch_all(query)

    # Fetch all user profiles from MongoDB in a single query
    user_emails = [user.email for user in users_result]
    profiles_result = await collection.find({"email": {"$in": user_emails}}).to_list(
        length=len(user_emails)
    )

    # Combine user data and profiles into a single dictionary
    user_data = {user["email"]: dict(user) for user in users_result}
    for profile in profiles_result:
        image_data = profile["profile"]
        base64_image = base64.b64encode(image_data).decode("utf-8")
        user_data[profile["email"]]["profile"] = base64_image
        # user_data[profile["email"]]["profile"] = Image.open(BytesIO(profile["profile"])).tobytes()
    return templates.TemplateResponse(
        "users.html", {"request": request, "users": user_data.values()}
    )
