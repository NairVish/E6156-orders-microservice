from flask import g
from middleware import context
import requests


def find_user_db_id():
    """
    Find user in database.
    """
    user_address_base_url = context.get_user_address_microservice_base_url()
    url = f"{user_address_base_url}/users?googleID={g.google_user_id}"
    headers = {"Authorization": f"Bearer {g.access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        resp_body = resp.json()
        if resp_body:
            return resp_body[0].get("ID", None)
    return None
