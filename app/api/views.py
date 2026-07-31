import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

def get_html_content(filename: str):
    path = os.path.join("templates", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"<h1>Sayfa Bulunamadı: {filename}</h1>"

@router.get("/", response_class=HTMLResponse)
async def home_page():
    return get_html_content("index.html")

@router.get("/menu", response_class=HTMLResponse)
async def customer_menu_page():
    return get_html_content("menu.html")

@router.get("/mutfak", response_class=HTMLResponse)
async def kitchen_panel_page():
    return get_html_content("mutfak.html")

@router.get("/garson", response_class=HTMLResponse)
async def waiter_panel_page():
    return get_html_content("garson.html")

@router.get("/admin", response_class=HTMLResponse)
async def admin_panel_page():
    return get_html_content("admin.html")

@router.get("/kasa", response_class=HTMLResponse)
async def kasa_panel_page():
    return get_html_content("kasa.html")






