from typing import Any, Dict, Optional

import httpx


class SupabaseAuthClient:
    """
    Minimal Supabase Auth client implemented with httpx to avoid adding heavy SDK dependencies.
    Uses Supabase auth endpoints:
      - POST {SUPABASE_URL}/auth/v1/signup
      - POST {SUPABASE_URL}/auth/v1/token?grant_type=password
    """

    def __init__(self, supabase_url: str, supabase_key: str, site_url: str):
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Key must be provided via environment variables.")
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self.site_url = site_url

        self._base_headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }

    async def sign_up(self, *, email: str, password: str, redirect_to: Optional[str]) -> Dict[str, Any]:
        """
        Calls Supabase signup endpoint.
        Docs: https://supabase.com/docs/reference/auth/signup
        """
        url = f"{self.supabase_url}/auth/v1/signup"
        payload: Dict[str, Any] = {"email": email, "password": password}
        if redirect_to:
            payload["data"] = {"emailRedirectTo": redirect_to}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._base_headers, json=payload, timeout=20.0)
            # Supabase returns 200/201; on error returns 400/422 with JSON body
            if resp.status_code >= 400:
                # raising HTTPStatusError lets caller discern code and message
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    # attach response text for context
                    ex.args = (*ex.args, f"Body: {resp.text}")
                    raise
            return resp.json()

    async def sign_in(self, *, email: str, password: str) -> Dict[str, Any]:
        """
        Calls Supabase password grant endpoint.
        Docs: https://supabase.com/docs/reference/auth/signinwithpassword
        """
        url = f"{self.supabase_url}/auth/v1/token?grant_type=password"
        payload = {"email": email, "password": password}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._base_headers, json=payload, timeout=20.0)
            if resp.status_code >= 400:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {resp.text}")
                    raise
            return resp.json()
