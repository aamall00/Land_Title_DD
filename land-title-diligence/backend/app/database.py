from supabase import create_client, Client
from app.config import get_settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return a cached Supabase client using the service-role key.
    The service-role key bypasses RLS — use only server-side.
    """
    global _client
    if _client is None:
        s = get_settings()
        _client = create_client(s.supabase_url, s.supabase_service_key)
    return _client
