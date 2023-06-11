"""
경상북도 김천시 X=80, Y=96
TMP 1시간 기온, POP 강수확률, SKY 하늘상태, SNO 1시간 신적설
강수형태(PTY) 코드 : (초단기) 없음(0), 비(1), 비/눈(2), 눈(3), 빗방울(5), 빗방울눈날림(6), 눈날림(7)
단기예보조회
초단기실황
T1H : 기온(도씨), PYT : 강수형태
"""

from typing import overload
from flasgger import swag_from
from flask import jsonify, request, Blueprint
from elasticsearch import Elasticsearch
import datetime
from pytz import timezone, utc

# 'ec2-15-164-102-214.ap-northeast-2.compute.amazonaws.com:9220'
es = Elasticsearch('ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25)

weather = Blueprint("weather", __name__, url_prefix="/")

@swag_from('./swagger/weather.yml', methods=['POST'])
@weather.route('weather', methods=['POST'])
def weather_api():
    now = datetime.datetime.now(timezone('Asia/Seoul')) # 클라우드 서버가 amazon 서버이므로 현재 서울 시간을 얻기 위해

    # 시간설정
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H") + "00"
    hour = int(now.strftime("%H")) # 현재 시간만 추출

    # 시간대별 명칭 설정 (excel참조)
    if 0 < hour < 6:
        time_zone = '새벽'
    elif 6 <= hour < 11:
        time_zone = '아침'
    elif 11 <= hour < 15:
        time_zone = '점심'
    elif 15 <= hour < 18:
        time_zone = '낮'
    elif 18 <= hour < 21:
        time_zone = '저녁'
    elif 21 <= hour <= 24 or hour == 0:
        time_zone = '밤'

    # weather index에서 T1H, PTY를 추출하기 위한 query
    body = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "match": {
                            "category": "T1H PTY" # T1H, PTY 추출
                        }
                    }
                ]
            }
        },
        "_source": ["category", "obsrValue"]
    }

    current_weather_info = es.search(index='weather', body=body)

    tmp, pty = "", ""
    # 기온(T1H), 강수형태(PTY) 만 추출해서 tmp,pty에 저장
    for i in current_weather_info['hits']['hits']:
        if i['_source']['category'] == "T1H":
            tmp = float(i['_source']['obsrValue']) # 기온
        elif i['_source']['category'] == "PTY":
            pty = int(i['_source']['obsrValue']) # 강수형태태

    # 온도범위에따라 기온별 옷차림 출처: 월드크리닝 표 (http://daily.hankooki.com/news/articleView.html?idxno=677743)
    # es weather index tmp값의 범위에따라 tmp_state 값 수정
    # 데이터의 부족으로 인한 온도 범위 조절
    # if 27 <= tmp: # 27도 이상
    #     tmp_state = {
    #         "gte": 27,
    #     }
    if 23 <= tmp: # 23~26도
        tmp_state = {
            "gte": 23,
            # "lt": 27
        }
    # elif 17 <= tmp < 23: # 17~22도
    #     tmp_state = {
    #         "gte": 17,
    #         "lt": 23
    #     }
    elif 12 <= tmp < 23: # 12~16도
        tmp_state = {
            "gte": 12,
            "lt": 23
        }
    elif tmp < 12: # 6~11도
        tmp_state = {
            # "gte": 6,
            "lt": 12
        }
    # elif tmp < 6: # 5도 이하
    #     tmp_state = {
    #         "gte": -998, # 이상를 설정해주기 위해
    #         "lt": 6
    #     }

    # 강수형태(PTY) 코드 : (초단기) 없음(0), 비(1), 비/눈(2), 눈(3), 빗방울(5), 빗방울눈날림(6), 눈날림(7)
    if pty == 1 or pty == 2 or pty == 5 or pty == 6:  # 비오는 날 설정
        pty_state = {
            "skystate": "비오는 날"
        }
    elif pty == 3 or pty == 7:  # snow : 1, 눈 오는 경우 설정
        pty_state = {
            "snow": 1
        }
    else:
        pty_state = {}

    # 강수형태에 맞는 query문 설정
    # 비,눈 안오는 날 query
    if pty_state == {}:
        weather_body = {
            "query": {
                "bool": {
                    "must": [
                        # {
                        #     "match": {
                        #         "time": time_zone
                        #     }
                        # },
                        {
                            "range": {
                                "temperature": tmp_state
                            }
                        }
                    ],
                    "must_not": [
                        {
                            "match_phrase": {
                                "skystate": "비오는 날"
                            }
                        },
                        {
                            "match": {
                                "snow": 1
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "weather": {
                    "terms": {
                        "field": "reviewTarget"
                    },
                    "aggs": {
                        "subject": {
                            "terms": {
                                "field": "reviewSubject"

                            }
                        }
                    }
                }
            },
            "size": 0
        }
    # 비, 눈 오는 날
    else:
        weather_body = {
            "query": {
                "bool": {
                    "must": [
                        # {
                        #     "match": {
                        #         "time": time_zone
                        #     }
                        # },
                        {
                            "match": pty_state
                        },
                        {
                            "range": {
                                "temperature": tmp_state
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "weather": {
                    "terms": {
                        "field": "reviewTarget"
                    },
                    "aggs": {
                        "subject": {
                            "terms": {
                                "field": "reviewSubject"

                            }
                        }
                    }
                }
            },
            "size": 0
        }
    weather_es = es.search(index='siren-import-gimcheon-review', body=weather_body)

    res = {
        'tourspot': [],
        'accommodation': [],
        'restaurant': []
    }

    # 음식점 리스트는 siren-import-gimcheon-restaurant 에 따로요청하여 메뉴를 받아와야하기때문에 따로저장
    rest_list = []

    for i in weather_es['aggregations']['weather']['buckets']:
        if i["subject"]["buckets"][0]["key"] == "관광":
            res['tourspot'].append(i['key'])

        elif i["subject"]["buckets"][0]["key"] == "음식":
            rest_list.append(i['key'])

        elif i["subject"]["buckets"][0]["key"] == "숙박":
            res['accommodation'].append(i['key'])

    # 음식점에 해당하는 메뉴들을 추출하기 위해
    restaurant_body = {
        "query": {
            "bool": {
                "filter": {
                    "terms": {
                        "name": rest_list
                    },
                }
            }
        },
        "_source": ["name", "menu", 'address']
    }

    # siren-import-gimcheon-restaurant 에 따로 요청하여 메뉴를 받아오기
    restaurant_es = es.search(
        index='siren-import-gimcheon-restaurant', body=restaurant_body)

    for i in restaurant_es['hits']['hits']:
        # print(i)
        object = {}
        if i['_source']['name'] == '정보없음':
            continue

        # 메뉴정보가 없음("정보없음") 이면 object 에 식당명:"정보없음"
        if i['_source']['menu'] == "정보없음":
            object[i['_source']['name']] = {'address': i['_source']['address'], 'menu': '정보없음'} #
            res['restaurant'].append(object)

        # 메뉴정보가 있으면object 에 식당명:"메뉴"
        else:
            try:
                menu = [i['_source']['menu']]
                print(menu)
                menu = eval(menu[0][1:-1])
                object[i['_source']['name']] = {'address': i['_source']['address'], 'menu': list(menu)} #
                res['restaurant'].append(object)
            except:
                object[i['_source']['name']] = {'address': i['_source']['address'], 'menu': '정보없음'}  #
                res['restaurant'].append(object)

    # 중복제거
    queries = ["사명대사공원", "김천시립박물관", "직지사", "대웅전", "김천시립박물관", "직지문화공원", "연화지", "친환경생태공원",
               "김호중 소리길", "세계도자기박물관", "오봉저수지", "백수문학관", "빗내농악전수관", "출렁다리", "부항댐", "녹색미래과학관", "산내들오토캠핑장", "청솔수석박물관",
               "산내들패밀리어드벤처파크", "물소리생태숲", "옛날솜씨마을", "짚와이어", "이화만리녹색농촌체험마을", "경북수상레포츠", "방초정", "승마장", "무흘구곡", "시티투어",
               "나이트투어", "대한불교조계종 직지사",
               "장전폭포", "증산 수도계곡", "인현왕후길", "불영산 청암사", "황악산", "수도암", "금오산", "수도산", "삼도봉", "치유의숲", "자산동 벽화마을", "무주군 대덕산",
               "종합스포츠타운",
               "포도홍보관", "문화예술회관", "김산항교", "황금시장", "김천역", "수도녹색숲모티길", "물문화관", "평화시장", "용화사", "계림사", "도동서원", "자동서원",
               "대성전", "춘천서원", "원계서원", "하로서원",
               "섬계서원", "경양서원", "용추폭포", "평화성당", "미륵암석조미륵불입상", "시립도서관", "황금성당", "봉곡사", "남산공원"]

    result = {
        'tourspot': [],
        'accommodation': [],
        'restaurant': []
    }

    # 데이터 부족으로 인한 관광지 랜덤 반환
    if res['tourspot'] == []:
        import random
        res['tourspot'] = list(random.sample(queries, 3))

    for r in res:
        for i in res[r]:
            if r == 'accommodation' and i in queries:
                continue
            if i not in result[r]:
                result[r].append(i)

    return jsonify(result)
