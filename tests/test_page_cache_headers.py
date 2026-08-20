"""HTML pages must never be cached by the browser.

The page carries the versioned script tag (`app.js?v=85`). If the browser keeps
an old copy of the HTML it keeps asking for the old script version, so a fix
shipped to `static/js` never reaches the phone no matter how many times the
version is bumped. That is the likeliest reason a corrected client behaviour
appears not to work on a device that has visited the page before.

Static assets are deliberately not covered: they carry a version parameter and
are safe to cache.
"""

import unittest

from app.api import views


REQUIRED = {
    "cache-control": "no-store",
    "pragma": "no-cache",
    "expires": "0",
}


class PageCacheHeaderTests(unittest.IsolatedAsyncioTestCase):

    async def _headers_for(self, handler):
        response = await handler()
        return {key.lower(): value for key, value in response.headers.items()}

    async def test_every_page_route_forbids_caching(self):
        handlers = {
            "/": views.home_page,
            "/menu": views.customer_menu_page,
            "/mutfak": views.kitchen_panel_page,
            "/garson": views.waiter_panel_page,
            "/admin": views.admin_panel_page,
            "/kasa": views.kasa_panel_page,
        }
        for path, handler in handlers.items():
            with self.subTest(path=path):
                headers = await self._headers_for(handler)
                self.assertIn("no-store", headers.get("cache-control", ""))
                self.assertEqual(headers.get("pragma"), REQUIRED["pragma"])
                self.assertEqual(headers.get("expires"), REQUIRED["expires"])

    async def test_a_page_still_returns_its_html(self):
        response = await views.customer_menu_page()
        self.assertEqual(response.status_code, 200)
        body = response.body.decode("utf-8")
        self.assertIn("<html", body.lower())
        self.assertIn("app.js?v=", body)

    async def test_the_qr_redirect_is_untouched(self):
        response = await views.masa_qr_redirect(5, token="123456")
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/menu?masa=5&token=123456")


if __name__ == "__main__":
    unittest.main()
