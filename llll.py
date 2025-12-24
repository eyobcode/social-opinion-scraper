import requests

headers = {
    "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
    "User-Agent": "Mozilla/5.0"
}

response = requests.post(
    "https://api.x.com/1.1/guest/activate.json",
    headers=headers
)

print(response.status_code)
print(response.text)
