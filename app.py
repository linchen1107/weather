import requests, math, random
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify
from collections import Counter

app = Flask(__name__)

def fetch_all_cities_weather():
    """
    從中央氣象局 O-A0001-001 API 擷取即時觀測資料，
    並依據 GeoInfo 裡的 "County" 欄位分組，計算每個縣市的最低與最高氣溫，
    以及最常見的天氣現象。
    """
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization=CWA-668AEE17-39AD-476B-A7E0-06602DA23C52"
    try:
        res = requests.get(url)
        resJson = res.json()
    except Exception as e:
        print("資料擷取失敗 (即時觀測)：", e)
        return {}
    stations = resJson.get("records", {}).get("Station", [])
    if not stations:
        return {}
    
    grouped = {}
    for station in stations:
        county = station.get("GeoInfo", {}).get("County", "").strip()
        if not county:
            continue
        try:
            temp = float(station.get("WeatherElement", {}).get("AirTemperature", "0"))
        except:
            continue
        weather = station.get("WeatherElement", {}).get("Weather", "未知")
        if county not in grouped:
            grouped[county] = {"temps": [], "weathers": []}
        grouped[county]["temps"].append(temp)
        grouped[county]["weathers"].append(weather)
    
    result = {}
    for county, data in grouped.items():
        if data["temps"]:
            low = min(data["temps"])
            high = max(data["temps"])
            weather_counter = Counter(data["weathers"])
            most_common_weather, _ = weather_counter.most_common(1)[0]
            result[county] = {"low": round(low), "high": round(high), "weather": most_common_weather, "place": county}
    return result

def fetch_36hour_forecast():
    """
    從中央氣象局 F-C0032-001 API 擷取36小時天氣預報資料，
    並整理成以縣市為鍵的字典，每個縣市包含：
      - day_min, day_max：兩個白天時段（12:00–18:00 與 06:00–18:00）的溫度區間
      - night_min, night_max：夜間（18:00–06:00）的溫度
      - overall_min, overall_max：綜合所有時段的最低與最高溫
      - day_weather, night_weather：分別取白天與夜間的 Wx 預報
      - day_pop, night_pop：分別取白天與夜間的降雨機率(PoP)
      - day_ci, night_ci：分別取白天與夜間的舒適度(CI)
      - place：縣市名稱
    假設 API time 陣列順序為：
      index0：12:00–18:00（白天1）
      index1：18:00–06:00（夜間）
      index2：06:00–18:00（白天2）
    """
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization=CWA-668AEE17-39AD-476B-A7E0-06602DA23C52"
    try:
        res = requests.get(url)
        data = res.json()
    except Exception as e:
        print("資料擷取失敗 (36小時預報)：", e)
        return {}
    
    locations = data.get("records", {}).get("location", [])
    forecast_data = {}
    for loc in locations:
        loc_name = loc.get("locationName")
        forecast = {}
        def get_param(element_name, idx):
            for elem in loc.get("weatherElement", []):
                if elem.get("elementName") == element_name:
                    times = elem.get("time", [])
                    if len(times) > idx:
                        return times[idx].get("parameter", {}).get("parameterName", "")
            return ""
        try:
            day_min_0 = float(get_param("MinT", 0))
        except:
            day_min_0 = None
        try:
            day_min_2 = float(get_param("MinT", 2))
        except:
            day_min_2 = None
        try:
            night_min = float(get_param("MinT", 1))
        except:
            night_min = None

        try:
            day_max_0 = float(get_param("MaxT", 0))
        except:
            day_max_0 = None
        try:
            day_max_2 = float(get_param("MaxT", 2))
        except:
            day_max_2 = None
        try:
            night_max = float(get_param("MaxT", 1))
        except:
            night_max = None

        day_temps_min = [t for t in [day_min_0, day_min_2] if t is not None]
        day_temps_max = [t for t in [day_max_0, day_max_2] if t is not None]
        day_min = min(day_temps_min) if day_temps_min else None
        day_max = max(day_temps_max) if day_temps_max else None

        temps = [t for t in [day_min, night_min, day_max, night_max] if t is not None]
        overall_min = min(temps) if temps else None
        overall_max = max(temps) if temps else None

        forecast["place"] = loc_name
        forecast["day_min"] = day_min
        forecast["day_max"] = day_max
        forecast["night_min"] = night_min
        forecast["night_max"] = night_max
        forecast["overall_min"] = overall_min
        forecast["overall_max"] = overall_max
        forecast["day_weather"] = get_param("Wx", 0)
        forecast["night_weather"] = get_param("Wx", 1)
        forecast["day_pop"] = get_param("PoP", 0)
        forecast["night_pop"] = get_param("PoP", 1)
        forecast["day_ci"] = get_param("CI", 0)
        forecast["night_ci"] = get_param("CI", 1)

        forecast_data[loc_name] = forecast
    return forecast_data

def fetch_specific_station_data(district="大社區", lat=None, lon=None):
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization=CWA-668AEE17-39AD-476B-A7E0-06602DA23C52"
    try:
        res = requests.get(url)
        resJson = res.json()
    except Exception as e:
        print("資料擷取失敗 (即時觀測)：", e)
        return []
    stations = resJson.get("records", {}).get("Station", [])
    if not stations:
        return []
    ds_stations = [station for station in stations if station.get("GeoInfo", {}).get("TownName", "").strip() == district.strip()]
    data_list = []
    if ds_stations:
        current_time = datetime.now().strftime("%H:%M:%S")
        for station in ds_stations:
            station_name = station.get("StationName", "未知")
            station_district = station.get("GeoInfo", {}).get("TownName", "未知")
            obs_time = current_time
            weather = station.get("WeatherElement", {})
            air_temp = weather.get("AirTemperature", "未知")
            weather_status = weather.get("Weather", "未知")
            wind_speed = weather.get("WindSpeed", "0")
            relative_humidity = weather.get("RelativeHumidity", "0")
            rain_prob = weather.get("Precipitation", "0")
            try:
                T = float(air_temp)
                air_temp_val = round(T)
            except Exception:
                T = 0.0
                air_temp_val = "未知"
            try:
                V = float(wind_speed)
            except Exception:
                V = 0.0
            try:
                RH = float(relative_humidity)
            except Exception:
                RH = 0.0
            try:
                rain_prob_val = float(rain_prob)
            except Exception:
                rain_prob_val = 0.0
            try:
                e = (RH/100)*6.105*math.exp(17.27*T/(237.7+T))
                AT = 1.07*T + 0.2*e - 0.65*V - 2.7
                AT = round(AT, 1)
            except Exception:
                AT = "未知"
            data_list.append({
                'station': station_name,
                'district': station_district,
                'time': obs_time,
                'temperature': air_temp_val,
                'weather_status': weather_status,
                'rain_prob': rain_prob_val,
                'apparent_temperature': AT
            })
    return data_list

def generate_kaohsiung_weekly_forecast():
    """
    產生高雄市所有鄉鎮市區的一周天氣預報假資料。
    每個預報項目包含：日期、區域、天氣狀況、最高溫、最低溫、降雨機率、體感描述。
    """
    kaohsiung_districts = [
        "新興區", "前金區", "苓雅區", "鹽埕區", "鼓山區", 
        "旗津區", "前鎮區", "三民區", "楠梓區", "小港區", 
        "左營區", "鳳山區", "大寮區", "鳥松區", "大樹區", 
        "大社區", "仁武區", "岡山區", "橋頭區", "燕巢區",
        "田寮區", "阿蓮區", "路竹區", "湖內區", "茄萣區", 
        "彌陀區", "永安區", "杉林區", "甲仙區", "內門區", 
        "茂林區", "桃源區", "那瑪夏區"
    ]
    forecast_list = []
    today = date.today()
    for district in kaohsiung_districts:
        for i in range(7):
            forecast_list.append({
                "date": (today + timedelta(days=i)).strftime("%Y-%m-%d"),
                "district": district,
                "weather": "晴" if random.random() < 0.6 else "雨",
                "max_temp": round(30 + random.uniform(-3, 3), 1),
                "min_temp": round(25 + random.uniform(-3, 3), 1),
                "rain_prob": round(random.uniform(0, 100), 1),
                "comfort": "舒適" if random.random() < 0.5 else "炎熱"
            })
    return forecast_list

@app.route('/api/weather_data')
def api_weather_data():
    city_mapping = {
        "taipei_city": "臺北市",
        "new_taipei_city": "新北市",
        "taichung_city": "臺中市",
        "tainan_city": "臺南市",
        "kaohsiung_city": "高雄市",
        "keelung_city": "基隆市",
        "taoyuan_country": "桃園市",
        "hsinchu_city": "新竹市",
        "hsinchu_country": "新竹縣",
        "miaoli_country": "苗栗縣",
        "changhua_country": "彰化縣",
        "nantou_country": "南投縣",
        "yunlin_country": "雲林縣",
        "chiayi_city": "嘉義市",
        "chiayi_country": "嘉義縣",
        "pingtung_country": "屏東縣",
        "yilan_country": "宜蘭縣",
        "hualien_country": "花蓮縣",
        "taitung_country": "臺東縣",
        "penghu_country": "澎湖縣",
        "kinmen_country": "金門縣",
        "lienchiang_country": "連江縣"
    }
    all_weather = fetch_all_cities_weather()
    weather_response = {}
    for key, county_name in city_mapping.items():
        if county_name in all_weather:
            weather_response[key] = all_weather[county_name]
        else:
            weather_response[key] = {"low": None, "high": None, "weather": "資料不足", "place": county_name}
    return jsonify(weather_response)

@app.route('/api/forecast36')
def api_forecast36():
    city_mapping = {
        "taipei_city": "臺北市",
        "new_taipei_city": "新北市",
        "taichung_city": "臺中市",
        "tainan_city": "臺南市",
        "kaohsiung_city": "高雄市",
        "keelung_city": "基隆市",
        "taoyuan_country": "桃園市",
        "hsinchu_city": "新竹市",
        "hsinchu_country": "新竹縣",
        "miaoli_country": "苗栗縣",
        "changhua_country": "彰化縣",
        "nantou_country": "南投縣",
        "yunlin_country": "雲林縣",
        "chiayi_city": "嘉義市",
        "chiayi_country": "嘉義縣",
        "pingtung_country": "屏東縣",
        "yilan_country": "宜蘭縣",
        "hualien_country": "花蓮縣",
        "taitung_country": "臺東縣",
        "penghu_country": "澎湖縣",
        "kinmen_country": "金門縣",
        "lienchiang_country": "連江縣",
    }
    forecast_data = fetch_36hour_forecast()
    response = {}
    for key, city_name in city_mapping.items():
        if forecast_data and city_name in forecast_data:
            response[key] = forecast_data[city_name]
        else:
            response[key] = {
                "place": city_name,
                "day_min": None,
                "day_max": None,
                "night_min": None,
                "night_max": None,
                "overall_min": None,
                "overall_max": None,
                "day_weather": "資料不足",
                "night_weather": "",
                "day_pop": "",
                "night_pop": "",
                "day_ci": "",
                "night_ci": ""
            }
    return jsonify(response)

@app.route("/realtime")
def realtime():
    district = request.args.get("district", "大社區")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    data = fetch_specific_station_data(district, lat, lon)
    return jsonify(data)

@app.route('/')
def weather_week():
    # 取得預設即時觀測資料（預設大社區）
    weather_data = fetch_specific_station_data("大社區")
    # 產生高雄市所有鄉鎮市區一周的天氣預報假資料
    forecast = generate_kaohsiung_weekly_forecast()
    # 從預報資料中取得所有區域，供下拉選單使用
    districts = sorted(list(set([item["district"] for item in forecast])))
    return render_template("WeatherWeek.html",
                           title="WeatherWeek",
                           weather_data=weather_data,
                           forecast=forecast,
                           districts=districts)

@app.route('/index')
def taiwan_map():
    return render_template('taiwanmap.html')

if __name__ == "__main__":
    app.run(debug=True)
