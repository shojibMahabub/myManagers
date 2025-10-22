import requests
import os
ACCESS_TOKEN = os.getenv('LINKEDIN_ACCESS_TOKEN')
AUTHOR_URN = f"urn:li:person:{os.getenv('LINKEDIN_USER_URN')}"

def post_text():
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202411",
        "Content-Type": "application/json"
    }
    body = {
        "author": AUTHOR_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": "Hello from the LinkedIn API!"},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }

    r = requests.post(url, json=body, headers=headers)
    print(r.status_code, r.text)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    updater = post_text()
