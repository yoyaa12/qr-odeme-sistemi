import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

# Sayfalar asla önbelleğe alınmamalı. HTML, script etiketlerinin sürüm
# numarasını (`app.js?v=84`) taşıyor; tarayıcı eski HTML'i saklarsa eski sürümü
# istemeye devam eder ve düzeltmeler telefona hiç ulaşmaz. Statik dosyalar bu
# kuralın dışında: onlar sürüm parametresiyle zaten güvenle önbelleklenebilir.
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def get_html_content(filename: str):
    path = os.path.join("templates", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"<h1>Sayfa Bulunamadı: {filename}</h1>"


def html_page(filename: str) -> HTMLResponse:
    return HTMLResponse(content=get_html_content(filename), headers=_NO_CACHE_HEADERS)


@router.get("/", response_class=HTMLResponse)
async def home_page():
    return html_page("index.html")

@router.get("/m/{masa_id}")
async def masa_qr_redirect(masa_id: int, token: str = None):
    url = f"/menu?masa={masa_id}"
    if token:
        url += f"&token={token}"
    return RedirectResponse(url=url)

@router.get("/menu", response_class=HTMLResponse)
async def customer_menu_page():
    return html_page("menu.html")

@router.get("/mutfak", response_class=HTMLResponse)
async def kitchen_panel_page():
    return html_page("mutfak.html")

@router.get("/garson", response_class=HTMLResponse)
async def waiter_panel_page():
    return html_page("garson.html")

@router.get("/admin", response_class=HTMLResponse)
async def admin_panel_page():
    return html_page("admin.html")

@router.get("/kasa", response_class=HTMLResponse)
async def kasa_panel_page():
    return html_page("kasa.html")






