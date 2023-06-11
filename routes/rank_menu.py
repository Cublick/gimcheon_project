from flasgger import swag_from
from flask import jsonify,  Blueprint
from elasticsearch import Elasticsearch
es = Elasticsearch(
    'ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25)
    # http://ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220
# Blueprint(이름, 모둘명, URL프리픽스) / restaurant라는 이름을 가진 blueprint생성
rank_menu = Blueprint("rank_menu", __name__, url_prefix="/rank")

pasta_list = ['봉골레', '로제', '알리올리오', '알리오올리오', '까르보나라', '오일', '토마토']
pizza_list = ['페퍼로니', '포테이토', '마르게리따', '고르곤졸라', '루꼴라', '콤비네이션', '하와이안', '치즈']

# 이번달 데이터
this_month = {
    "gte": "now-3y-11M/M", # 현재 - 1년 (월 만출력)
    "lt": "now/M"
}

# 저번달 데이터
last_month = {
    "gte": "now-3y-11M/M",
    "lt": "now-1y-11M/M"
}

# 해당 달의 데이터를 얻고자하는 쿼리body


def setting_date(foodname, select_date):
    # 음식 리스트를 받아 dict형태로 변환
    temp = {}
    for i in foodname:
        temp[i] = {
            "term": {
                "reviewText": i
            }
        }

    # aggs쿼리문을 이용하여 해당되는 카운트 집계
    body_two = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "reviewDate": select_date
                        }
                    }
                ]
            }
        },
        "aggs": {
            "count": {
                "filters": {
                    "filters": temp
                }
            }
        },
        "size": 10
    }
    return body_two

# 이번달과 저번달 음식 카운트 비교


def compare_count(category, total_food_list):
    review_count = category['aggregations']['count']['buckets']  # aggregations에서 각 음식들이 나온 횟수 추출
    for key, val in review_count.items():
        if key in pasta_list or '파스타' in key:  # 파스타 종류
            key = '파스타'

        if key in pizza_list:
            key = '피자'

        if key == '짜장' or key == '자장면':  # 짜장면 예외처리
            key = '짜장면'

        if key == '스시':
            key = '초밥'

        if list(val.values())[0] != 0:
            if key in total_food_list:
                total_food_list[key] += list(val.values())[0]
            else:
                total_food_list[key] = list(val.values())[0]

    # 이음동의어 제거
    for val in list(total_food_list):
        if val[-2:] in total_food_list and val != val[-2:]:
            total_food_list[val[-2:]] += total_food_list[val]
            del total_food_list[val]

    return total_food_list


@swag_from('./swagger/rank_menu.yml', methods=['POST'])
# /rank/menu 로 접근
@rank_menu.route('/menu', methods=['GET', 'POST'])
def menu_categorys():
    # keyword = request.form.get('keyword', False).strip()
    keyword = ['한식', '일식', '양식', '중식']
    res = {'한식': [], '일식': [], '양식': [], '중식': []}

    # query설정 문 (restaurantCategory필드에서 keyword점에 해당하는 menu정보 반환)
    for key in keyword:
        # 음식 추천을 위한 카테고리별 총 음식 리스트
        total_food_list = {}

        # multi_match로 다중 검색, 한식 + '점'을 이용하여 category검색 후 메뉴만 추출
        body = {
            "query": {
                "multi_match": {
                    "query": key + '점',
                    "fields": ["restaurantCategory"]
                }
            },
            "size": 100,
            "_source": ["menu"]
        }

        category = es.search(
            index='siren-import-gimcheon-restaurant', body=body)

        food = {}  # 음식 리스트
        for tmp in category['hits']['hits']:
            tmp = tmp['_source']['menu'].replace(
                '[', '').replace(']', '')  # 필요한 부분 중 원하고자 하는 menu부분을 추출
            # str형태를 dict형태로 뽑기위해 str -> list -> dict
            tmp = list(tmp.split(','))

            for i in tmp:
                val = eval(i.strip())  # dict형태 변환
                if list(val.values())[0] == key:  # keyword랑 값 비교하여 dict음식리스트 생성
                    if not list(val.keys())[0] in food:
                        food[list(val.keys())[0]] = 0

        # dict음식 리스트에서 하나씩 음식을 추출하여 음식이 들어있는 reviewText의 갯수를 반환
        this_category = es.search(
            index='siren-import-gimcheon-review', body=setting_date(food, this_month))
        last_category = es.search(
            index='siren-import-gimcheon-review', body=setting_date(food, last_month))

        this_food_list = sorted(compare_count(this_category, total_food_list).items(), key=lambda x: x[1], reverse=True)
        last_food_list = sorted(compare_count(last_category, total_food_list).items(), key=lambda x: x[1], reverse=True)

        # 10개 까지만 추출
        this_food_list = [this_food_list[i]
                          for i in range(len(this_food_list))][:10]
        last_food_list = [last_food_list[i]
                          for i in range(len(last_food_list))][:10]

        # 저번달 데이터와 현재 데이터를 비교하여 dict형태로 반환
        for this_idx, (this_name, this_cnt) in enumerate(this_food_list):
            obj = {}
            for last_idx, (last_name, last_cnt) in enumerate(last_food_list):
                # index와 음식이름이 같을때(순위 변동 없음)
                if this_idx == last_idx and this_name == last_name:
                    obj['rank'] = this_idx
                    obj['value'] = this_name
                    obj['updown'] = '-'
                    res[key].append(obj)
                    break
                # index가 다를때(순위변동이 있을때)
                elif this_idx != last_idx and this_name == last_name:
                    obj['rank'] = this_idx
                    obj['value'] = this_name
                    obj['updown'] = last_idx - this_idx
                    res[key].append(obj)
                    break
            else:  # 위의 조건에 걸리지 않았을 경우(새로 들어온 음식)
                obj['rank'] = this_idx
                obj['value'] = this_name
                obj['updown'] = 'new'
                res[key].append(obj)

    return jsonify(res)
