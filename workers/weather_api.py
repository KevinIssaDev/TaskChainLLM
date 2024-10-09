import requests

def weather_api(location: str) -> str:
    """
    Fetches weather data for a given location using wttr.in API.

    Args:
        location (str): The name of the city or location to fetch weather data for.

    Returns:
        str: A string describing the weather, including temperature and weather conditions.

    Example Usage:
        [[WORKER:weather_api, location="London"]]
    """
    base_url = "https://wttr.in"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Priority": "u=0, i",
        "Sec-CH-UA": "\"Google Chrome\";v=\"129\", \"Not=A?Brand\";v=\"8\", \"Chromium\";v=\"129\"",
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    
    response = requests.get(f"{base_url}/{location}?format=j1", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return data["current_condition"]
    else:
        return f"Error: Unable to fetch weather data for {location}."


worker = weather_api
