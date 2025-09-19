import requests


def get_jwt_token(site_url, username, password):
    """
    Generate JWT token for self-hosted WordPress
    """
    token_url = f"{site_url}/wp-json/jwt-auth/v1/token"
    data = {"username": username, "password": password}

    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()

        token_data = response.json()
        if "token" in token_data:
            print(f"✅ JWT Token Generated Successfully!")
            print(f"Token: {token_data['token']}")
            print(f"User: {token_data.get('user_display_name', 'Unknown')}")
            print(f"Email: {token_data.get('user_email', 'Unknown')}")
            return token_data["token"]
        else:
            print(f"❌ Error in response: {token_data}")
            return None

    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


# Usage
if __name__ == "__main__":
    TOKEN = get_jwt_token(
        site_url="https://webshielddaily.com",
        username="eneon54321@gmail.com",  # Replace with your WP username
        password="Eeneon12138!",  # Replace with your WP password
    )

    if TOKEN:
        print(f"\n📋 Update your credentials with this token:")
        print(f'    "ACCESS_TOKEN": "{TOKEN}",')
